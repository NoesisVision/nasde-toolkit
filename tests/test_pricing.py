"""Tests for the model pricing catalog."""

from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit.pricing import compute_cost_usd, load_pricing, pricing_as_of


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
        '[models."my-model"]\n'
        "input_per_1m = 1.0\n"
        "output_per_1m = 2.0\n"
        'as_of = "2026-01-01"\n'
        'source = "test"\n'
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
