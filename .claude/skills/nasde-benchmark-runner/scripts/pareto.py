#!/usr/bin/env python3
"""Pareto-front comparison of agent/model trials — quality vs cost AND quality vs tokens.

This is the PRIMARY comparison method for nasde benchmark results. A model is
*dominated* iff some other model is no-worse in quality AND no-worse on the
cost/token axis AND strictly better on at least one. The non-dominated set (the
"front") is the set of real options to choose between; it is invariant to where
you put the rubric-score zero, unlike a scalar "efficiency = score / denominator".

Two panels are drawn because the two axes answer different questions:
  - quality vs cost ($)     — price-dependent (changes with the price catalog)
  - quality vs tokens (1M)  — price-independent (pure model behaviour)
When both fronts agree on the front membership, the conclusion is stronger.

SCOPING (enforced by the caller, not this script): only feed points from ONE
task, the SAME dimensions_fingerprint, and the SAME reasoning_effort. Never
aggregate across tasks of different difficulty into a single number.

Usage
-----
From a `nasde results-export` directory (one subdir per trial, each with a
`metrics.json` / `assessment_summary.json`):

    python pareto.py --export-dir /path/to/export --out /tmp/pareto.png

Or with explicit data points (no export to read), as repeatable triples
`name,effort,score,cost_usd,total_tokens` (tokens in raw count or millions):

    python pareto.py \
        --point "claude-sonnet-4-6,,0.803,8.55,2720000" \
        --point "claude-opus-4-8,,0.920,26.30,5120000" \
        --out /tmp/pareto.png

Points sharing the same (name, effort) across multiple trials are averaged, and
their per-axis inter-trial std is reported on stdout (n>=2 → a real signal; n=1
→ a preliminary signal only, no variance).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt

FRONT_COLOR = "#2a9d8f"
DOMINATED_COLOR = "#e76f51"


@dataclass
class TrialPoint:
    name: str
    effort: str
    score: float
    cost_usd: float | None
    tokens_millions: float


@dataclass
class ModelGroup:
    name: str
    effort: str
    n: int
    score: float
    cost_usd: float | None
    tokens_millions: float
    score_std: float = 0.0
    cost_std: float | None = None
    tokens_std: float = 0.0
    members: list[TrialPoint] = field(default_factory=list)

    @property
    def label(self) -> str:
        effort = self.effort or "default"
        return f"{self.name} (effort={effort}, n={self.n})"


def pareto_nondominated(groups: list[ModelGroup], x_attr: str) -> list[ModelGroup]:
    """Groups not dominated on (x_attr, score): lower x is better, higher score is better."""
    front: list[ModelGroup] = []
    for a in groups:
        a_x = getattr(a, x_attr)
        if a_x is None:
            continue
        if not _is_dominated(a, a_x, groups, x_attr):
            front.append(a)
    return front


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    trials = _collect_trials(args)
    if not trials:
        print("no trial points found", file=sys.stderr)
        return 1
    groups = _group_trials(trials)
    _print_groups(groups)
    figure = _build_figure(groups, args.title)
    out = Path(args.out)
    figure.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")
    _print_fronts(groups)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="A `nasde results-export` dir; reads metrics.json/assessment_summary.json per trial.",
    )
    parser.add_argument(
        "--point",
        action="append",
        default=[],
        metavar="name,effort,score,cost_usd,total_tokens",
        help="An explicit data point; repeatable. cost_usd may be empty for unpriced models.",
    )
    parser.add_argument("--out", default="pareto.png", help="Output PNG path.")
    parser.add_argument(
        "--title",
        default="Pareto front — one task, same fingerprint, same reasoning effort",
        help="Figure suptitle; state the task + scope here.",
    )
    return parser.parse_args(argv)


def _collect_trials(args: argparse.Namespace) -> list[TrialPoint]:
    trials: list[TrialPoint] = []
    if args.export_dir:
        trials.extend(_read_export_dir(args.export_dir))
    trials.extend(_parse_point(spec) for spec in args.point)
    return trials


def _read_export_dir(export_dir: Path) -> list[TrialPoint]:
    trials: list[TrialPoint] = []
    for trial_dir in sorted(p for p in export_dir.iterdir() if p.is_dir()):
        metrics = _load_json(trial_dir / "metrics.json")
        summary = _load_json(trial_dir / "assessment_summary.json")
        point = _trial_point_from_artifacts(metrics, summary)
        if point is not None:
            trials.append(point)
    return trials


def _trial_point_from_artifacts(metrics: dict, summary: dict) -> TrialPoint | None:
    score = _extract_score(summary, metrics)
    tokens = _extract_total_tokens(metrics, summary)
    if score is None or tokens is None:
        return None
    return TrialPoint(
        name=_extract_model_name(metrics, summary),
        effort=_extract_effort(metrics, summary),
        score=score,
        cost_usd=_extract_cost(metrics, summary),
        tokens_millions=tokens / 1e6,
    )


def _extract_score(summary: dict, metrics: dict) -> float | None:
    for source in (summary, metrics):
        for key in ("normalized_score_mean", "normalized_score", "score"):
            value = source.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _extract_total_tokens(metrics: dict, summary: dict) -> float | None:
    for source in (metrics, summary):
        usage = source.get("token_usage")
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), (int, float)):
            return float(usage["total_tokens"])
    return None


def _extract_cost(metrics: dict, summary: dict) -> float | None:
    for source in (metrics, summary):
        value = source.get("cost_usd")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _extract_model_name(metrics: dict, summary: dict) -> str:
    for source in (summary, metrics):
        value = source.get("model_name") or source.get("model")
        if isinstance(value, str) and value:
            return value
    return "unknown-model"


def _extract_effort(metrics: dict, summary: dict) -> str:
    for source in (summary, metrics):
        value = source.get("reasoning_effort")
        if isinstance(value, str):
            return value
    return ""


def _parse_point(spec: str) -> TrialPoint:
    parts = [field.strip() for field in spec.split(",")]
    if len(parts) != 5:
        raise SystemExit(
            f"--point needs 5 comma-separated fields "
            f"(name,effort,score,cost_usd,total_tokens); got: {spec!r}"
        )
    name, effort, score_raw, cost_raw, tokens_raw = parts
    tokens = float(tokens_raw)
    tokens_millions = tokens if tokens < 1000 else tokens / 1e6
    return TrialPoint(
        name=name,
        effort=effort,
        score=float(score_raw),
        cost_usd=float(cost_raw) if cost_raw else None,
        tokens_millions=tokens_millions,
    )


def _group_trials(trials: list[TrialPoint]) -> list[ModelGroup]:
    buckets: dict[tuple[str, str], list[TrialPoint]] = {}
    for trial in trials:
        buckets.setdefault((trial.name, trial.effort), []).append(trial)
    return [_aggregate_bucket(key, members) for key, members in buckets.items()]


def _aggregate_bucket(key: tuple[str, str], members: list[TrialPoint]) -> ModelGroup:
    name, effort = key
    scores = [member.score for member in members]
    tokens = [member.tokens_millions for member in members]
    costs = [member.cost_usd for member in members if member.cost_usd is not None]
    return ModelGroup(
        name=name,
        effort=effort,
        n=len(members),
        score=statistics.fmean(scores),
        cost_usd=statistics.fmean(costs) if costs else None,
        tokens_millions=statistics.fmean(tokens),
        score_std=statistics.stdev(scores) if len(scores) >= 2 else 0.0,
        cost_std=statistics.stdev(costs) if len(costs) >= 2 else None,
        tokens_std=statistics.stdev(tokens) if len(tokens) >= 2 else 0.0,
        members=members,
    )


def _is_dominated(group: ModelGroup, x_value: float, groups: list[ModelGroup], x_attr: str) -> bool:
    for other in groups:
        if other is group:
            continue
        other_x = getattr(other, x_attr)
        if other_x is None:
            continue
        not_worse = other_x <= x_value and other.score >= group.score
        strictly_better = other_x < x_value or other.score > group.score
        if not_worse and strictly_better:
            return True
    return False


def _build_figure(groups: list[ModelGroup], title: str):
    figure, (axis_cost, axis_tokens) = plt.subplots(1, 2, figsize=(13, 5.2))
    _draw_panel(axis_cost, groups, "cost_usd", "Cost (USD per trial)", "Quality vs Cost")
    _draw_panel(
        axis_tokens,
        groups,
        "tokens_millions",
        "Tokens (millions per trial)",
        "Quality vs Tokens (price-independent)",
    )
    figure.suptitle(
        f"{title}\n"
        "Green ● = efficient choices (Pareto front) · "
        "Red ✗ = dominated (worse on both axes, never worth picking)",
        fontsize=10,
    )
    figure.tight_layout(rect=[0, 0, 1, 0.91])
    return figure


def _draw_panel(axis, groups: list[ModelGroup], x_attr: str, x_label: str, title: str) -> None:
    plottable = [group for group in groups if getattr(group, x_attr) is not None]
    front = pareto_nondominated(plottable, x_attr)
    front_keys = {(group.name, group.effort) for group in front}
    front_sorted = sorted(front, key=lambda group: getattr(group, x_attr))

    axis.plot(
        [getattr(group, x_attr) for group in front_sorted],
        [group.score for group in front_sorted],
        "-",
        color=FRONT_COLOR,
        lw=2,
        zorder=1,
        label="Pareto front",
    )
    for group in plottable:
        on_front = (group.name, group.effort) in front_keys
        axis.scatter(
            getattr(group, x_attr),
            group.score,
            s=180,
            color=FRONT_COLOR if on_front else DOMINATED_COLOR,
            edgecolor="black",
            linewidth=1.2,
            zorder=3,
            marker="o" if on_front else "X",
            label=f'{group.label}{"" if on_front else "  — dominated"}',
        )
    axis.set_xlabel(x_label)
    axis.set_ylabel("Quality (normalized rubric score)")
    axis.set_title(title, fontweight="bold")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="lower right", fontsize=7.5, framealpha=0.95)


def _print_groups(groups: list[ModelGroup]) -> None:
    print("Model groups (averaged within (model, reasoning_effort)):")
    for group in sorted(groups, key=lambda g: g.score, reverse=True):
        cost = "n/a" if group.cost_usd is None else f"${group.cost_usd:.2f}"
        note = "  [n=1 preliminary signal, no variance]" if group.n < 2 else ""
        print(
            f"  {group.name:<24} effort={group.effort or 'default':<12} "
            f"n={group.n}  score={group.score:.3f}±{group.score_std:.3f}  "
            f"tok={group.tokens_millions:.2f}M  cost={cost}{note}"
        )


def _print_fronts(groups: list[ModelGroup]) -> None:
    for x_attr, axis_name in (("cost_usd", "cost"), ("tokens_millions", "tokens")):
        plottable = [group for group in groups if getattr(group, x_attr) is not None]
        front = sorted(pareto_nondominated(plottable, x_attr), key=lambda g: getattr(g, x_attr))
        names = " < ".join(group.name for group in front) or "(none)"
        print(f"front[{axis_name}]: {names}")


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
