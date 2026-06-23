"""Rendering for the effective (merged) pricing catalog.

Shared by ``nasde pricing show`` and the ``nasde run`` summary so the rate table
looks identical wherever it appears. See ADR-013.
"""

from __future__ import annotations

from rich.table import Table

from nasde_toolkit.pricing import ModelPrice


def render_pricing_table(
    entries: dict[str, tuple[ModelPrice, str]],
    show_source: bool = False,
    title: str = "Effective pricing",
) -> Table:
    """Build a Rich table of model rates, optionally with the source layer column."""
    table = Table(title=title)
    table.add_column("Model", style="cyan")
    table.add_column("In / 1M", justify="right")
    table.add_column("Out / 1M", justify="right")
    if show_source:
        table.add_column("Layer", justify="left")
    table.add_column("as_of", justify="left", style="dim")
    for model in sorted(entries):
        price, layer = entries[model]
        row = [model, _fmt_rate(price.input_per_1m), _fmt_rate(price.output_per_1m)]
        if show_source:
            row.append(layer)
        row.append(price.as_of or "—")
        table.add_row(*row)
    return table


def _fmt_rate(rate: float) -> str:
    return f"${rate:g}"
