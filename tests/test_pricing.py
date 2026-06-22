"""Tests for the model pricing catalog."""

from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit import pricing as pricing_module
from nasde_toolkit.pricing import (
    compute_cost_usd,
    load_pricing,
    load_pricing_layered,
    pricing_as_of,
)


def _write_pricing(directory: Path, body: str) -> Path:
    path = directory / "pricing.toml"
    path.write_text(body)
    return path


def _model_block(name: str, input_per_1m: float, output_per_1m: float, source: str | None = None) -> str:
    block = f'[models."{name}"]\ninput_per_1m = {input_per_1m}\noutput_per_1m = {output_per_1m}\n'
    if source is not None:
        block += f'source = "{source}"\n'
    return block


@pytest.fixture
def empty_user_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    user_file = tmp_path / "user-home" / ".nasde" / "pricing.toml"
    monkeypatch.setattr(pricing_module, "_user_pricing_path", lambda: user_file)
    return user_file


def test_load_bundled_pricing_has_matrix_models() -> None:
    pricing = load_pricing()
    for model in ("gpt-5.5", "gpt-5.4", "claude-opus-4-8", "claude-sonnet-4-6"):
        assert model in pricing
        assert pricing[model].input_per_1m > 0
        assert pricing[model].output_per_1m > 0
        assert pricing[model].as_of


def test_load_custom_pricing_file(tmp_path: Path) -> None:
    custom = tmp_path / "pricing.toml"
    custom.write_text(
        '[models."my-model"]\ninput_per_1m = 1.0\noutput_per_1m = 2.0\nas_of = "2026-01-01"\nsource = "test"\n'
    )
    pricing = load_pricing(custom)
    assert set(pricing) == {"my-model"}
    assert pricing["my-model"].input_per_1m == 1.0


def test_compute_cost_full_rate_no_cache_discount() -> None:
    pricing = load_pricing()
    # claude-sonnet-4-6 = $3 in / $15 out: 1M input + 0.1M output = 3.0 + 1.5 = 4.5
    cost = compute_cost_usd(1_000_000, 100_000, "claude-sonnet-4-6", pricing)
    assert cost == pytest.approx(4.5)


def test_compute_cost_unknown_model_returns_none() -> None:
    assert compute_cost_usd(1000, 100, "nonexistent-model", load_pricing()) is None


def test_pricing_as_of_unknown_model_is_none() -> None:
    assert pricing_as_of("nonexistent-model", load_pricing()) is None
    assert pricing_as_of("gpt-5.4", load_pricing()) == "2026-06-08"


def test_layered_no_overrides_returns_bundled(tmp_path: Path, empty_user_layer: Path) -> None:
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == set(load_pricing())


def test_layered_project_overrides_bundled(tmp_path: Path, empty_user_layer: Path) -> None:
    _write_pricing(tmp_path, _model_block("claude-sonnet-4-6", 99.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-sonnet-4-6"].input_per_1m == 99.0
    assert merged["gpt-5.5"].input_per_1m == load_pricing()["gpt-5.5"].input_per_1m


def test_layered_project_adds_new_model(tmp_path: Path, empty_user_layer: Path) -> None:
    _write_pricing(tmp_path, _model_block("my-model", 7.0, 8.0))
    merged = load_pricing_layered(tmp_path)
    assert "my-model" in merged
    assert set(load_pricing()).issubset(set(merged))


def test_layered_user_layer_applied(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-4-8", 4.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-opus-4-8"].input_per_1m == 4.0


def test_layered_project_beats_user(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-4-8", 4.0, 1.0))
    _write_pricing(tmp_path, _model_block("claude-opus-4-8", 6.0, 2.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-opus-4-8"].input_per_1m == 6.0


def test_layered_missing_user_file_skipped(tmp_path: Path, empty_user_layer: Path) -> None:
    assert not empty_user_layer.exists()
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == set(load_pricing())


def test_layered_whole_entry_replacement(tmp_path: Path, empty_user_layer: Path) -> None:
    bundled = load_pricing()["claude-sonnet-4-6"]
    assert bundled.cached_input_per_1m is not None and bundled.source
    _write_pricing(tmp_path, _model_block("claude-sonnet-4-6", 2.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-sonnet-4-6"].input_per_1m == 2.0
    assert merged["claude-sonnet-4-6"].cached_input_per_1m is None
    assert merged["claude-sonnet-4-6"].source == ""


def test_layered_three_layers_compose(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-4-8", 4.0, 1.0) + _model_block("azure-gpt5", 1.0, 2.0))
    _write_pricing(
        tmp_path,
        _model_block("claude-sonnet-4-6", 2.0, 1.0)
        + _model_block("azure-gpt5", 0.5, 1.0)
        + _model_block("enterprise-claude", 10.0, 20.0),
    )
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == {
        "gpt-5.5",
        "gpt-5.4",
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        "azure-gpt5",
        "enterprise-claude",
    }
    assert merged["gpt-5.5"].input_per_1m == 5.0
    assert merged["gpt-5.4"].input_per_1m == 2.50
    assert merged["claude-opus-4-8"].input_per_1m == 4.0
    assert merged["claude-sonnet-4-6"].input_per_1m == 2.0
    assert merged["azure-gpt5"].input_per_1m == 0.5
    assert merged["enterprise-claude"].input_per_1m == 10.0


def test_layered_three_layers_whole_entry_on_overlap(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("azure-gpt5", 1.0, 2.0, source="azure-contract"))
    _write_pricing(tmp_path, _model_block("azure-gpt5", 0.5, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["azure-gpt5"].input_per_1m == 0.5
    assert merged["azure-gpt5"].source == ""
