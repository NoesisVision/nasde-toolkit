"""Model pricing catalog for token-cost metrics.

Loads per-model rates from a bundled ``pricing.toml`` and computes USD cost from
token volumes. The catalog is overridable by convention via layered files —
``<project>/pricing.toml`` > ``~/.nasde/pricing.toml`` > bundled, merged per-model
(see ``load_pricing_layered`` and ADR-013). Cost is the full catalog rate applied
to the full prompt-token volume (cache included, no discount) — see ``pricing.toml``
and ADR-011.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path

from rich.console import Console

console = Console()


@dataclass
class ModelPrice:
    """Catalog rate for one model (USD per 1M tokens)."""

    input_per_1m: float
    output_per_1m: float
    cached_input_per_1m: float | None = None
    as_of: str = ""
    source: str = ""


def compute_cost_usd(
    input_tokens: int,
    output_tokens: int,
    model: str,
    pricing: dict[str, ModelPrice],
) -> float | None:
    """Full-rate USD cost for the given token volumes, or None if model is unpriced."""
    price = pricing.get(model)
    if price is None:
        console.print(
            f"  [yellow]No pricing for model {model!r} — cost left unset. "
            f"Add it to pricing.toml to enable cost metrics.[/yellow]"
        )
        return None
    return input_tokens / 1_000_000 * price.input_per_1m + output_tokens / 1_000_000 * price.output_per_1m


def load_pricing(path: str | Path | None = None) -> dict[str, ModelPrice]:
    """Load the model pricing catalog, defaulting to the bundled pricing.toml.

    The bundled catalog (``path=None``) is read and parsed once per process and
    cached, since it is invariant — callers (one per trial) must treat the
    returned mapping as read-only.
    """
    if path is None:
        return _load_bundled_pricing()
    raw = _read_pricing_toml(path)
    return _pricing_from_raw(raw)


def load_pricing_layered(project_dir: Path | None = None) -> dict[str, ModelPrice]:
    """Load the pricing catalog with convention-based layered overrides.

    Merges three layers, higher wins, per-model whole-entry replacement:
      1. ``<project_dir>/pricing.toml``  (project layer, highest)
      2. ``~/.nasde/pricing.toml``       (user layer)
      3. bundled ``pricing.toml``        (the floor, always present)

    An override file lists only the models it changes or adds; every other model
    is inherited from the layer below. A missing project/user file is silently
    skipped — only the bundled floor is required. See ADR-013.
    """
    merged = dict(load_pricing())
    for override_path in _layered_override_paths(project_dir):
        if not override_path.is_file():
            continue
        layer = load_pricing(override_path)
        merged.update(layer)
        console.print(f"  [dim]pricing: applied override {override_path} ({len(layer)} model(s))[/dim]")
    return merged


def pricing_as_of(model: str, pricing: dict[str, ModelPrice]) -> str | None:
    """Return the as_of date stamped on the model's price, if priced."""
    price = pricing.get(model)
    return price.as_of if price is not None else None


@lru_cache(maxsize=1)
def _load_bundled_pricing() -> dict[str, ModelPrice]:
    return _pricing_from_raw(_read_pricing_toml(None))


def _layered_override_paths(project_dir: Path | None) -> list[Path]:
    paths = [_user_pricing_path()]
    if project_dir is not None:
        paths.append(project_dir / "pricing.toml")
    return _deduped_paths(paths)


def _user_pricing_path() -> Path:
    return Path.home() / ".nasde" / "pricing.toml"


def _deduped_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    deduped: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


def _pricing_from_raw(raw: dict) -> dict[str, ModelPrice]:
    return {name: _model_price_from_dict(entry) for name, entry in raw.get("models", {}).items()}


def _read_pricing_toml(path: str | Path | None) -> dict:
    if path is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)
    with open(_bundled_pricing_path(), "rb") as f:
        return tomllib.load(f)


def _bundled_pricing_path() -> Path:
    resource = files("nasde_toolkit").joinpath("pricing.toml")
    with as_file(resource) as path:
        bundled = Path(path)
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parent / "pricing.toml"


def _model_price_from_dict(entry: dict) -> ModelPrice:
    return ModelPrice(
        input_per_1m=entry["input_per_1m"],
        output_per_1m=entry["output_per_1m"],
        cached_input_per_1m=entry.get("cached_input_per_1m"),
        as_of=entry.get("as_of", ""),
        source=entry.get("source", ""),
    )
