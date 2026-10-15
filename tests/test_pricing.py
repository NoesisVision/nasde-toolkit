"""Tests for the model pricing catalog."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from nasde_toolkit.pricing import (
    compute_cost_usd,
    effective_pricing_with_source,
    load_pricing,
    load_pricing_layered,
    pricing_as_of,
    resolve_pricing_layers,
)


def test_model_price_is_frozen() -> None:
    price = load_pricing()["claude-sonnet-4-6"]
    with pytest.raises(FrozenInstanceError):
        price.input_per_1m = 0.01  # type: ignore[misc]


def test_layered_malformed_toml_exits_with_path(tmp_path: Path, empty_user_layer: Path) -> None:
    (tmp_path / "pricing.toml").write_text('[models."m"]\ninput_per_1m = 2,5\noutput_per_1m = 1.0\n')
    with pytest.raises(SystemExit):
        load_pricing_layered(tmp_path)


def test_layered_missing_required_field_exits(tmp_path: Path, empty_user_layer: Path) -> None:
    (tmp_path / "pricing.toml").write_text('[models."m"]\ninput_per_1m = 2.5\n')
    with pytest.raises(SystemExit):
        load_pricing_layered(tmp_path)


def _write_pricing(directory: Path, body: str) -> Path:
    path = directory / "pricing.toml"
    path.write_text(body)
    return path


def _model_block(name: str, input_per_1m: float, output_per_1m: float, source: str | None = None) -> str:
    block = f'[models."{name}"]\ninput_per_1m = {input_per_1m}\noutput_per_1m = {output_per_1m}\n'
    if source is not None:
        block += f'source = "{source}"\n'
    return block


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


def test_compute_cost_without_cache_reduces_to_full_rate() -> None:
    pricing = load_pricing()
    # claude-sonnet-4-6 = $3 in / $15 out: 1M input + 0.1M output = 3.0 + 1.5 = 4.5
    cost = compute_cost_usd(1_000_000, 100_000, "claude-sonnet-4-6", pricing)
    assert cost == pytest.approx(4.5)


def test_compute_cost_cache_aware_matches_harbor_accounting() -> None:
    # Real trial ayg7ckA (claude-fable-5): Harbor's own per-step total was $8.841665.
    cost = compute_cost_usd(
        3_070_507,
        66_456,
        "claude-fable-5",
        load_pricing(),
        cache_read_tokens=2_939_665,
        cache_write_tokens=127_078,
    )
    assert cost == pytest.approx(8.841665, abs=0.0005)


def test_compute_cost_cache_aware_matches_harbor_accounting_fable_5_1() -> None:
    # Real trial qoVXn7k (claude-fable-5-1, xhigh): Harbor's own per-step total was
    # $3.57704175 — it applies the same 0.025x read rate. Pricing reads at 0.1x
    # like every other Claude model would land at $4.38 (+22% on this token mix).
    cost = compute_cost_usd(
        1_160_418,
        30_522,
        "claude-fable-5-1",
        load_pricing(),
        cache_read_tokens=1_070_967,
        cache_write_tokens=88_869,
    )
    assert cost == pytest.approx(3.57704175, abs=0.0005)


def test_fable_5_1_cache_reads_bill_at_the_published_quarter_rate() -> None:
    # Fable 5.1 reads are 0.025x base input ($0.25 on $10), not the 0.1x every
    # other Claude model uses — guards the entry against a "consistency" fix.
    pricing = load_pricing()
    assert pricing["claude-fable-5-1"].cached_input_per_1m == 0.25
    # 1M prompt tokens, all cache reads, 0.1M output: 0.25 + 5.0
    cost = compute_cost_usd(1_000_000, 100_000, "claude-fable-5-1", pricing, cache_read_tokens=1_000_000)
    assert cost == pytest.approx(5.25)


def test_opus_5_5_and_sonnet_5_5_cache_reads_bill_at_the_published_half_rate() -> None:
    # Opus 5.5 and Sonnet 5.5 read at 0.05x base input ($0.20 on $4, $0.10 on
    # $2) — the second published exception after Fable 5.1's 0.025x. Guards
    # both entries against a "consistency" fix back to 0.1x.
    pricing = load_pricing()
    assert pricing["claude-opus-5-5"].cached_input_per_1m == 0.20
    assert pricing["claude-sonnet-5-5"].cached_input_per_1m == 0.10
    # 1M prompt tokens, all cache reads, 0.1M output
    assert compute_cost_usd(
        1_000_000, 100_000, "claude-opus-5-5", pricing, cache_read_tokens=1_000_000
    ) == pytest.approx(0.20 + 2.0)
    assert compute_cost_usd(
        1_000_000, 100_000, "claude-sonnet-5-5", pricing, cache_read_tokens=1_000_000
    ) == pytest.approx(0.10 + 1.0)


def test_gpt_5_6_and_gpt_6_families_bill_cache_writes() -> None:
    # Unlike gpt-5.5 and older, the GPT-5.6 / GPT-6 families list a cache-write
    # rate (1.25x base input) — it must be a live input, not the base-rate fallback.
    pricing = load_pricing()
    assert pricing["gpt-5.6-sol"].cache_write_per_1m == 5.0
    assert pricing["gpt-6.1-sol"].cached_input_per_1m == 0.10
    assert pricing["gpt-5.5"].cache_write_per_1m is None
    assert compute_cost_usd(1_000_000, 100_000, "gpt-5.6-sol", pricing, cache_write_tokens=1_000_000) == pytest.approx(
        5.0 + 2.0
    )


def test_claude_haiku_5_5_is_deliberately_unsupported() -> None:
    # Tiered pricing (<=100K vs >100K prompts) has no representation in
    # ModelPrice, so the model is absent on purpose: an unpriced model yields
    # cost_usd = None rather than a figure that understates cost ~5x.
    assert "claude-haiku-5-5" not in load_pricing()


def test_compute_cost_missing_cache_rates_falls_back_to_full_rate(tmp_path: Path) -> None:
    custom = tmp_path / "pricing.toml"
    custom.write_text('[models."bare"]\ninput_per_1m = 2.0\noutput_per_1m = 10.0\n')
    pricing = load_pricing(custom)
    # no cached/cache-write rates -> reads and writes bill at the full input rate
    cost = compute_cost_usd(1_000_000, 0, "bare", pricing, cache_read_tokens=900_000, cache_write_tokens=50_000)
    assert cost == pytest.approx(2.0)


def test_compute_cost_unknown_model_returns_none() -> None:
    assert compute_cost_usd(1000, 100, "nonexistent-model", load_pricing()) is None


def test_pricing_as_of_unknown_model_is_none() -> None:
    assert pricing_as_of("nonexistent-model", load_pricing()) is None
    assert pricing_as_of("gpt-5.4", load_pricing()) == "2026-10-14"


def test_layered_no_overrides_returns_bundled(tmp_path: Path, empty_user_layer: Path) -> None:
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == set(load_pricing())


def test_layered_project_overrides_bundled(tmp_path: Path, empty_user_layer: Path) -> None:
    _write_pricing(tmp_path, _model_block("claude-sonnet-5-5", 99.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-sonnet-5-5"].input_per_1m == 99.0
    assert merged["gpt-5.5"].input_per_1m == load_pricing()["gpt-5.5"].input_per_1m


def test_layered_project_adds_new_model(tmp_path: Path, empty_user_layer: Path) -> None:
    _write_pricing(tmp_path, _model_block("my-model", 7.0, 8.0))
    merged = load_pricing_layered(tmp_path)
    assert "my-model" in merged
    assert set(load_pricing()).issubset(set(merged))


def test_layered_user_layer_applied(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-5-5", 4.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-opus-5-5"].input_per_1m == 4.0


def test_layered_project_beats_user(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-5-5", 4.0, 1.0))
    _write_pricing(tmp_path, _model_block("claude-opus-5-5", 6.0, 2.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-opus-5-5"].input_per_1m == 6.0


def test_layered_missing_user_file_skipped(tmp_path: Path, empty_user_layer: Path) -> None:
    assert not empty_user_layer.exists()
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == set(load_pricing())


def test_layered_whole_entry_replacement(tmp_path: Path, empty_user_layer: Path) -> None:
    bundled = load_pricing()["claude-sonnet-5-5"]
    assert bundled.cached_input_per_1m is not None and bundled.source
    _write_pricing(tmp_path, _model_block("claude-sonnet-5-5", 2.0, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["claude-sonnet-5-5"].input_per_1m == 2.0
    assert merged["claude-sonnet-5-5"].cached_input_per_1m is None
    assert merged["claude-sonnet-5-5"].source == ""


def test_layered_three_layers_compose(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-5-5", 4.0, 1.0) + _model_block("azure-gpt5", 1.0, 2.0))
    _write_pricing(
        tmp_path,
        _model_block("claude-sonnet-5-5", 2.0, 1.0)
        + _model_block("azure-gpt5", 0.5, 1.0)
        + _model_block("enterprise-claude", 10.0, 20.0),
    )
    merged = load_pricing_layered(tmp_path)
    assert set(merged) == set(load_pricing()) | {"azure-gpt5", "enterprise-claude"}
    assert merged["gpt-5.5"].input_per_1m == 5.0
    assert merged["gpt-5.4"].input_per_1m == 2.50
    assert merged["claude-opus-5-5"].input_per_1m == 4.0
    assert merged["claude-sonnet-5-5"].input_per_1m == 2.0
    assert merged["azure-gpt5"].input_per_1m == 0.5
    assert merged["enterprise-claude"].input_per_1m == 10.0


def test_layered_three_layers_whole_entry_on_overlap(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("azure-gpt5", 1.0, 2.0, source="azure-contract"))
    _write_pricing(tmp_path, _model_block("azure-gpt5", 0.5, 1.0))
    merged = load_pricing_layered(tmp_path)
    assert merged["azure-gpt5"].input_per_1m == 0.5
    assert merged["azure-gpt5"].source == ""


def test_resolve_layers_no_overrides_is_bundled_only(tmp_path: Path, empty_user_layer: Path) -> None:
    layers = resolve_pricing_layers(tmp_path)
    assert [layer.name for layer in layers] == ["bundled"]
    assert layers[0].present is True
    assert layers[0].path is None
    assert set(layers[0].models) == set(load_pricing())


def test_resolve_layers_three_present(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-5-5", 4.0, 1.0))
    _write_pricing(tmp_path, _model_block("my-model", 7.0, 8.0))
    layers = {layer.name: layer for layer in resolve_pricing_layers(tmp_path)}
    assert set(layers) == {"bundled", "user", "project"}
    assert set(layers["user"].models) == {"claude-opus-5-5"}
    assert set(layers["project"].models) == {"my-model"}
    assert layers["project"].path == tmp_path / "pricing.toml"


def test_effective_pricing_with_source_three_layers(tmp_path: Path, empty_user_layer: Path) -> None:
    empty_user_layer.parent.mkdir(parents=True, exist_ok=True)
    empty_user_layer.write_text(_model_block("claude-opus-5-5", 4.0, 1.0) + _model_block("azure-gpt5", 1.0, 2.0))
    _write_pricing(tmp_path, _model_block("azure-gpt5", 0.5, 1.0) + _model_block("enterprise-claude", 10.0, 20.0))
    eff = effective_pricing_with_source(tmp_path)
    assert eff["gpt-5.5"][1] == "bundled"
    assert eff["claude-opus-5-5"][1] == "user"
    assert eff["azure-gpt5"][1] == "project"
    assert eff["azure-gpt5"][0].input_per_1m == 0.5
    assert eff["enterprise-claude"][1] == "project"


def test_load_pricing_layered_matches_effective_keys(tmp_path: Path, empty_user_layer: Path) -> None:
    _write_pricing(tmp_path, _model_block("my-model", 7.0, 8.0))
    assert set(load_pricing_layered(tmp_path)) == set(effective_pricing_with_source(tmp_path))
