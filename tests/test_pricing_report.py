"""Tests for the effective-pricing table renderer."""

from __future__ import annotations

import pytest

from nasde_toolkit.pricing import ModelPrice
from nasde_toolkit.pricing_report import _fmt_rate, render_pricing_table


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (3.0, "$3"),
        (2.5, "$2.5"),
        (0.5, "$0.5"),
        (0.0125, "$0.0125"),
        (0.0001, "$0.0001"),
        (0.0, "$0"),
        (75.0, "$75"),
        (1_000_000.0, "$1000000"),
    ],
)
def test_fmt_rate_no_scientific_notation(rate: float, expected: str) -> None:
    assert _fmt_rate(rate) == expected


def test_render_pricing_table_source_column_toggles() -> None:
    entries = {"m": (ModelPrice(input_per_1m=3.0, output_per_1m=15.0, as_of="2026-06-08"), "bundled")}
    with_source = render_pricing_table(entries, show_source=True)
    without_source = render_pricing_table(entries, show_source=False)
    assert with_source.columns[-2].header == "Layer"
    assert all(column.header != "Layer" for column in without_source.columns)
