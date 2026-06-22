"""Normalize legacy assessment eval files to the numbered + summary scheme.

Older jobs carry a bare assessment_eval.json (a duplicate of the highest
numbered file) and/or only the bare file. This brings every trial to the
current scheme: numbered assessment_eval_<N>.json plus a recomputed
assessment_summary.json. Idempotent and re-runnable.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from nasde_toolkit.evaluator import (
    _load_json,
    _next_eval_index,
    _write_assessment_summary,
)
from nasde_toolkit.pricing import ModelPrice, load_pricing_layered

console = Console()


def migrate_job_evals(path: Path, dry_run: bool = False) -> dict[str, int]:
    outcomes = {"migrated": 0, "summarized": 0, "noop": 0}
    pricing = load_pricing_layered()
    for trial_dir in _find_trial_dirs(path):
        outcome = migrate_trial_evals(trial_dir, pricing, dry_run=dry_run)
        outcomes[outcome] += 1
    return outcomes


def migrate_trial_evals(trial_dir: Path, pricing: dict[str, ModelPrice] | None = None, dry_run: bool = False) -> str:
    bare = trial_dir / "assessment_eval.json"
    numbered = _numbered_eval_files(trial_dir)

    if not bare.exists() and not numbered:
        return "noop"

    pricing = pricing if pricing is not None else load_pricing_layered()
    changed = _normalize_raw_files(trial_dir, bare, numbered, dry_run)
    if not dry_run:
        _write_assessment_summary(trial_dir, pricing)
    if changed:
        return "migrated"
    return "summarized"


def _find_trial_dirs(path: Path) -> list[Path]:
    if (path / "result.json").exists():
        return [path]
    trial_dirs = {result.parent for result in path.rglob("result.json") if result.parent != path}
    return sorted(trial_dirs)


def _numbered_eval_files(trial_dir: Path) -> list[Path]:
    pattern = re.compile(r"assessment_eval_(\d+)\.json$")
    indexed = [
        (int(match.group(1)), path)
        for path in trial_dir.glob("assessment_eval_*.json")
        if (match := pattern.search(path.name))
    ]
    return [path for _, path in sorted(indexed, key=lambda pair: pair[0])]


def _normalize_raw_files(trial_dir: Path, bare: Path, numbered: list[Path], dry_run: bool) -> bool:
    if not bare.exists():
        return False
    if not numbered:
        _log(f"rename {bare.name} -> assessment_eval_1.json in {trial_dir.name}", dry_run)
        if not dry_run:
            bare.rename(trial_dir / "assessment_eval_1.json")
        return True
    return _resolve_bare_against_numbered(trial_dir, bare, numbered, dry_run)


def _resolve_bare_against_numbered(trial_dir: Path, bare: Path, numbered: list[Path], dry_run: bool) -> bool:
    highest = numbered[-1]
    if _load_json(bare) == _load_json(highest):
        _log(f"delete duplicate {bare.name} (== {highest.name}) in {trial_dir.name}", dry_run)
        if not dry_run:
            bare.unlink()
        return True
    promoted = f"assessment_eval_{_next_eval_index(trial_dir)}.json"
    console.print(
        f"  [yellow]Warning: {bare.name} differs from {highest.name} in {trial_dir.name}; "
        f"promoting to {promoted} instead of deleting.[/yellow]"
    )
    _log(f"rename {bare.name} -> {promoted} in {trial_dir.name}", dry_run)
    if not dry_run:
        bare.rename(trial_dir / promoted)
    return True


def _log(message: str, dry_run: bool) -> None:
    prefix = "[dim]would[/dim] " if dry_run else ""
    console.print(f"  {prefix}{message}")
