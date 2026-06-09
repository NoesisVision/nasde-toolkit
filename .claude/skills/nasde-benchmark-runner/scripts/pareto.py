#!/usr/bin/env python3
"""Quality-vs-cost / quality-vs-tokens scatter for nasde benchmark results.

Plots one point per `(agent_name, model_name, reasoning_effort)` configuration —
raw position only. Color encodes the provider, marker shape encodes the variant
(circle = vanilla, square = a skill variant, triangle = other), and a thin line
links the variants of one model so the "shift from adding a skill" is visible at
a glance. It does NOT paint a verdict on each point: no "Pareto front" line, no
green/red "dominated" tags. The convention this follows (cf. Artificial
Analysis intelligence-vs-tokens charts) is to show the data honestly, mark the
*direction* of "better" with a shaded attractive quadrant and an arrow, and let
the reader draw conclusions. That is also safer at small n, where a hard
"dominated" label on a point with no variance over-claims.

Two axes answer different questions, so two panels are drawn:
  - quality vs cost ($)     — price-dependent (moves with the price catalog)
  - quality vs tokens       — price-independent (pure model behaviour)
Token axis defaults to OUTPUT tokens on a log scale (the Artificial Analysis
convention); pass --token-axis total for total tokens.

SCOPING — a comparison is only meaningful within ONE task, the SAME
dimensions_fingerprint, and the SAME reasoning_effort. Pass --task to keep an
export dir that spans many tasks honest; never let points from tasks of
different difficulty share one chart.

Usage
-----
From a `nasde results-export` dir (one subdir per trial), scoped to one task:

    python pareto.py --export-dir /path/to/nasde-results --task ddd-weather-discount \
        --out /tmp/quality_vs_cost.png

Or with explicit points `name,effort,score,cost_usd,output_tokens`:

    python pareto.py \
        --point "claude-opus-4-8,,0.92,26.30,69055" \
        --point "claude-sonnet-4-6,,0.80,8.55,33430" \
        --out /tmp/quality_vs_cost.png

Trials sharing one (agent, model, effort) are averaged; per-axis inter-trial std
is reported on stdout (n>=2 → a real signal; n=1 → a preliminary signal only).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

QUADRANT_COLOR = "#bfe3cf"

PROVIDER_COLORS = {
    "claude": "#d97757",
    "gpt": "#000000",
    "gemini": "#1a73e8",
    "codex": "#000000",
    "unknown": "#888888",
}

VANILLA_MARKER = "o"
SKILL_MARKER = "s"
OTHER_MARKER = "^"


@dataclass
class TrialPoint:
    name: str
    agent: str
    effort: str
    score: float
    cost_usd: float | None
    output_tokens_millions: float
    total_tokens_millions: float


@dataclass
class ModelGroup:
    name: str
    agent: str
    effort: str
    n: int
    score: float
    cost_usd: float | None
    output_tokens_millions: float
    total_tokens_millions: float
    score_std: float = 0.0
    cost_std: float | None = None
    output_tokens_std: float = 0.0
    total_tokens_std: float = 0.0
    members: list[TrialPoint] = field(default_factory=list)

    @property
    def label(self) -> str:
        effort = f", effort={self.effort}" if self.effort else ""
        variant = f"{self.agent} / " if self.agent and self.agent != self.name else ""
        return f"{variant}{self.name} (n={self.n}{effort})"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    trials = _collect_trials(args)
    if not trials:
        print("no trial points found", file=sys.stderr)
        return 1
    groups = _group_trials(trials)
    _print_groups(groups, args.token_axis)
    figure = _build_figure(groups, args.title, args.token_axis)
    out = Path(args.out)
    figure.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-dir", type=Path, help="A `nasde results-export` dir (one subdir per trial).")
    parser.add_argument(
        "--task",
        default="",
        help="Keep only trials whose task_name matches this (scoping: one task per chart).",
    )
    parser.add_argument(
        "--point",
        action="append",
        default=[],
        metavar="name,effort,score,cost_usd,output_tokens",
        help="An explicit data point; repeatable. cost_usd may be empty for unpriced models.",
    )
    parser.add_argument("--out", default="quality_chart.png", help="Output PNG path.")
    parser.add_argument(
        "--token-axis",
        choices=("output", "total"),
        default="output",
        help="Which token count on the tokens panel (default output, the Artificial Analysis convention).",
    )
    parser.add_argument(
        "--title",
        default="Quality vs cost and tokens — one task, same fingerprint, same effort",
        help="Figure suptitle; state the task + scope here.",
    )
    return parser.parse_args(argv)


def _collect_trials(args: argparse.Namespace) -> list[TrialPoint]:
    trials: list[TrialPoint] = []
    if args.export_dir:
        trials.extend(_read_export_dir(args.export_dir, args.task))
    trials.extend(_parse_point(spec) for spec in args.point)
    return trials


def _read_export_dir(export_dir: Path, task: str) -> list[TrialPoint]:
    trials: list[TrialPoint] = []
    for trial_dir in sorted(p for p in export_dir.iterdir() if p.is_dir()):
        metrics = _load_json(trial_dir / "metrics.json")
        summary = _load_json(trial_dir / "assessment_summary.json")
        if task and _extract_task_name(metrics, summary) != task:
            continue
        point = _trial_point_from_artifacts(metrics, summary)
        if point is not None:
            trials.append(point)
    return trials


def _trial_point_from_artifacts(metrics: dict, summary: dict) -> TrialPoint | None:
    score = _extract_score(summary, metrics)
    total = _extract_total_tokens(metrics, summary)
    if score is None or total is None:
        return None
    output = _extract_output_tokens(metrics, summary)
    return TrialPoint(
        name=_extract_model_name(metrics, summary),
        agent=_extract_agent_name(metrics, summary),
        effort=_extract_effort(metrics, summary),
        score=score,
        cost_usd=_extract_cost(metrics, summary),
        output_tokens_millions=(output if output is not None else total) / 1e6,
        total_tokens_millions=total / 1e6,
    )


def _extract_score(summary: dict, metrics: dict) -> float | None:
    for source in (summary, metrics):
        for key in ("normalized_score_mean", "normalized_score", "score"):
            value = source.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _extract_total_tokens(metrics: dict, summary: dict) -> float | None:
    return _extract_usage_field(metrics, summary, "total_tokens")


def _extract_output_tokens(metrics: dict, summary: dict) -> float | None:
    return _extract_usage_field(metrics, summary, "output_tokens")


def _extract_usage_field(metrics: dict, summary: dict, field_name: str) -> float | None:
    for source in (metrics, summary):
        usage = source.get("token_usage")
        if isinstance(usage, dict) and isinstance(usage.get(field_name), (int, float)):
            return float(usage[field_name])
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


def _extract_agent_name(metrics: dict, summary: dict) -> str:
    for source in (metrics, summary):
        value = source.get("agent_name")
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_effort(metrics: dict, summary: dict) -> str:
    for source in (summary, metrics):
        value = source.get("reasoning_effort")
        if isinstance(value, str):
            return value
    return ""


def _extract_task_name(metrics: dict, summary: dict) -> str:
    for source in (metrics, summary):
        value = source.get("task_name")
        if isinstance(value, str) and value:
            return value
    return ""


def _parse_point(spec: str) -> TrialPoint:
    parts = [field.strip() for field in spec.split(",")]
    if len(parts) != 5:
        raise SystemExit(
            f"--point needs 5 comma-separated fields (name,effort,score,cost_usd,output_tokens); got: {spec!r}"
        )
    name, effort, score_raw, cost_raw, tokens_raw = parts
    tokens = float(tokens_raw)
    tokens_millions = tokens if tokens < 1000 else tokens / 1e6
    return TrialPoint(
        name=name,
        agent=name,
        effort=effort,
        score=float(score_raw),
        cost_usd=float(cost_raw) if cost_raw else None,
        output_tokens_millions=tokens_millions,
        total_tokens_millions=tokens_millions,
    )


def _group_trials(trials: list[TrialPoint]) -> list[ModelGroup]:
    buckets: dict[tuple[str, str, str], list[TrialPoint]] = {}
    for trial in trials:
        buckets.setdefault((trial.agent, trial.name, trial.effort), []).append(trial)
    return [_aggregate_bucket(key, members) for key, members in buckets.items()]


def _aggregate_bucket(key: tuple[str, str, str], members: list[TrialPoint]) -> ModelGroup:
    agent, name, effort = key
    scores = [member.score for member in members]
    output = [member.output_tokens_millions for member in members]
    total = [member.total_tokens_millions for member in members]
    costs = [member.cost_usd for member in members if member.cost_usd is not None]
    return ModelGroup(
        name=name,
        agent=agent,
        effort=effort,
        n=len(members),
        score=statistics.fmean(scores),
        cost_usd=statistics.fmean(costs) if costs else None,
        output_tokens_millions=statistics.fmean(output),
        total_tokens_millions=statistics.fmean(total),
        score_std=statistics.stdev(scores) if len(scores) >= 2 else 0.0,
        cost_std=statistics.stdev(costs) if len(costs) >= 2 else None,
        output_tokens_std=statistics.stdev(output) if len(output) >= 2 else 0.0,
        total_tokens_std=statistics.stdev(total) if len(total) >= 2 else 0.0,
        members=members,
    )


def _build_figure(groups: list[ModelGroup], title: str, token_axis: str):
    figure, (axis_cost, axis_tokens) = plt.subplots(1, 2, figsize=(14, 5.6))
    _draw_panel(axis_cost, groups, "cost_usd", "Cost (USD per trial)", "Quality vs Cost", log_x=False)
    token_attr = "output_tokens_millions" if token_axis == "output" else "total_tokens_millions"
    token_label = f"{token_axis.capitalize()} tokens (millions per trial, log scale)"
    _draw_panel(axis_tokens, groups, token_attr, token_label, "Quality vs Tokens (price-independent)", log_x=True)
    _add_shape_legend(figure, groups)
    figure.suptitle(
        f"{title}\nColor = provider · shape = variant · line links variants of one model · "
        "shaded = most attractive region, arrow toward 'better'",
        fontsize=10,
    )
    figure.tight_layout(rect=[0, 0, 1, 0.89])
    return figure


def _add_shape_legend(figure, groups: list[ModelGroup]) -> None:
    from matplotlib.lines import Line2D

    kinds = {_variant_kind(group.agent) for group in groups}
    marker_for = {"vanilla": VANILLA_MARKER, "skill": SKILL_MARKER, "guided": OTHER_MARKER}
    name_for = {"vanilla": "vanilla", "skill": "+skill", "guided": "guided"}
    handles = [
        Line2D(
            [],
            [],
            marker=marker_for.get(kind, OTHER_MARKER),
            color="#555555",
            linestyle="none",
            markersize=9,
            label=name_for.get(kind, kind),
        )
        for kind in sorted(kinds)
    ]
    if len(handles) > 1:
        figure.legend(handles=handles, loc="upper right", fontsize=8, title="variant", framealpha=0.95)


def _draw_panel(axis, groups: list[ModelGroup], x_attr: str, x_label: str, title: str, log_x: bool) -> None:
    plottable = [group for group in groups if getattr(group, x_attr) is not None]
    if not plottable:
        axis.set_title(f"{title}\n(no priced data)", fontweight="bold")
        return
    xs = [getattr(group, x_attr) for group in plottable]
    scores = [group.score for group in plottable]
    _shade_attractive_quadrant(axis, xs, scores, log_x)
    _connect_same_model(axis, plottable, x_attr)
    for group in plottable:
        axis.scatter(
            getattr(group, x_attr),
            group.score,
            s=200,
            color=_provider_color(group.name),
            edgecolor="white",
            linewidth=1.4,
            marker=_variant_marker(group.agent),
            zorder=3,
        )
        axis.annotate(
            group.label,
            (getattr(group, x_attr), group.score),
            xytext=(7, 4),
            textcoords="offset points",
            fontsize=8,
            zorder=4,
        )
    if log_x:
        axis.set_xscale("log")
    axis.set_xlabel(x_label)
    axis.set_ylabel("Quality (normalized rubric score)")
    axis.set_title(title, fontweight="bold")
    axis.grid(True, alpha=0.25, which="both")


def _connect_same_model(axis, groups: list[ModelGroup], x_attr: str) -> None:
    by_model: dict[str, list[ModelGroup]] = {}
    for group in groups:
        by_model.setdefault(group.name, []).append(group)
    for model_groups in by_model.values():
        if len(model_groups) < 2:
            continue
        ordered = sorted(model_groups, key=lambda g: getattr(g, x_attr))
        axis.plot(
            [getattr(g, x_attr) for g in ordered],
            [g.score for g in ordered],
            "-",
            color=_provider_color(ordered[0].name),
            alpha=0.35,
            lw=1.3,
            zorder=2,
        )


def _shade_attractive_quadrant(axis, xs: list[float], scores: list[float], log_x: bool) -> None:
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(scores), max(scores)
    x_pad = (x_max / x_min) ** 0.08 if log_x and x_min > 0 else 1.0
    x_lo = x_min / x_pad if log_x else x_min - 0.06 * (x_max - x_min or 1)
    x_hi = x_max * x_pad if log_x else x_max + 0.06 * (x_max - x_min or 1)
    y_pad = 0.06 * (y_max - y_min or 0.1)
    axis.set_xlim(x_lo, x_hi)
    axis.set_ylim(y_min - y_pad, y_max + y_pad)
    x_mid = (x_min * x_max) ** 0.5 if log_x else (x_min + x_max) / 2
    axis.axvspan(x_lo, x_mid, ymin=0.5, ymax=1.0, color=QUADRANT_COLOR, alpha=0.45, zorder=0)
    axis.add_patch(
        FancyArrowPatch(
            (x_mid, y_min - y_pad / 2),
            (x_lo + (x_mid - x_lo) * 0.15 if not log_x else x_lo * (x_mid / x_lo) ** 0.15, y_max + y_pad / 2),
            arrowstyle="-|>",
            mutation_scale=16,
            color="#2a9d8f",
            alpha=0.8,
            lw=1.6,
            zorder=1,
        )
    )
    axis.text(
        x_lo if not log_x else x_lo * 1.02,
        y_max + y_pad / 2,
        "better",
        fontsize=8,
        color="#2a9d8f",
        fontweight="bold",
        va="top",
        zorder=2,
    )


def _provider_color(model_name: str) -> str:
    lowered = model_name.lower()
    for key, color in PROVIDER_COLORS.items():
        if key in lowered:
            return color
    return PROVIDER_COLORS["unknown"]


def _variant_kind(agent: str) -> str:
    lowered = agent.lower()
    if not lowered or lowered.endswith("vanilla") or lowered == "vanilla":
        return "vanilla"
    if "guided" in lowered:
        return "guided"
    return "skill"


def _variant_marker(agent: str) -> str:
    kind = _variant_kind(agent)
    if kind == "vanilla":
        return VANILLA_MARKER
    if kind == "skill":
        return SKILL_MARKER
    return OTHER_MARKER


def _print_groups(groups: list[ModelGroup], token_axis: str) -> None:
    print("Groups (averaged within (agent, model, reasoning_effort)):")
    for group in sorted(groups, key=lambda g: g.score, reverse=True):
        cost = "n/a" if group.cost_usd is None else f"${group.cost_usd:.2f}"
        tok = group.output_tokens_millions if token_axis == "output" else group.total_tokens_millions
        note = "  [n=1 preliminary signal, no variance]" if group.n < 2 else ""
        print(
            f"  {_group_id(group):<46} effort={group.effort or 'default':<8} "
            f"n={group.n}  score={group.score:.3f}±{group.score_std:.3f}  "
            f"{token_axis}_tok={tok:.2f}M  cost={cost}{note}"
        )


def _group_id(group: ModelGroup) -> str:
    if group.agent and group.agent != group.name:
        return f"{group.agent} / {group.name}"
    return group.name


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
