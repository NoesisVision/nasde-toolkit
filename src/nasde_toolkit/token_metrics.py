"""Token usage and cost economics extracted from an agent trajectory.

Single source of truth shared by the run path (evaluator.py → assessment_summary.json)
and the export path (results_exporter.py → metrics.json), so the two never diverge.

Token volumes come from the trajectory's top-level ``final_metrics`` (written by
Harbor for both Claude and Codex agents):
  input  = total_prompt_tokens            (full, cache included)
  output = total_completion_tokens + extra.reasoning_output_tokens
  total  = input + output

Cost applies the full catalog rate to those volumes (no cache discount) — see ADR-011.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from nasde_toolkit.pricing import ModelPrice, compute_cost_usd, pricing_as_of


@dataclass
class TokenUsage:
    """Token volumes for one trial (one agent run)."""

    input_tokens: int
    output_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    total_tokens: int


def extract_token_usage(trajectory: dict) -> TokenUsage | None:
    """Build TokenUsage from a trajectory's final_metrics, or None if unavailable."""
    final_metrics = trajectory.get("final_metrics") or {}
    prompt_tokens = final_metrics.get("total_prompt_tokens")
    if prompt_tokens is None:
        return None
    completion_tokens = final_metrics.get("total_completion_tokens", 0) or 0
    reasoning_tokens = (final_metrics.get("extra") or {}).get("reasoning_output_tokens", 0) or 0
    cached_tokens = final_metrics.get("total_cached_tokens", 0) or 0
    output_tokens = completion_tokens + reasoning_tokens
    return TokenUsage(
        input_tokens=prompt_tokens,
        output_tokens=output_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        total_tokens=prompt_tokens + output_tokens,
    )


def dominant_normalized_score(groups: list[dict]) -> float | None:
    """Pick the dominant evaluator cluster's mean score from a summary's groups dict."""
    if not groups:
        return None
    dominant = next((g for g in groups if g.get("dominant")), groups[0])
    return dominant.get("normalized_score_mean")


def read_trajectory(trial_dir: Path) -> dict | None:
    """Read a trajectory from a run trial dir (agent/) or an export dir (flat)."""
    for candidate in (trial_dir / "agent" / "trajectory.json", trial_dir / "trajectory.json"):
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                data: dict = json.load(f)
            return data
    return None


def build_trial_economics(
    trial_dir: Path,
    model: str,
    pricing: dict[str, ModelPrice],
) -> dict:
    """Assemble the economics block for one trial (used by run and export paths).

    Only raw, baseline-invariant signals are recorded — token volumes, USD cost,
    and the price catalog date. Quality-vs-cost comparison is a Pareto front over
    these raw axes (in the nasde-benchmark-runner skill), not a scalar
    score/cost ratio whose zero point is arbitrary. See ADR-011.
    """
    trajectory = read_trajectory(trial_dir)
    usage = extract_token_usage(trajectory) if trajectory is not None else None
    if usage is None:
        return _empty_economics(model)
    cost_usd = compute_cost_usd(usage.input_tokens, usage.output_tokens, model, pricing)
    return {
        "model_name": model,
        "token_usage": asdict(usage),
        "cost_usd": cost_usd,
        "pricing_as_of": pricing_as_of(model, pricing) if cost_usd is not None else None,
    }


def _empty_economics(model: str) -> dict:
    return {
        "model_name": model,
        "token_usage": None,
        "cost_usd": None,
        "pricing_as_of": None,
    }
