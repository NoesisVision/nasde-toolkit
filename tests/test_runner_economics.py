"""Tests for the per-(agent, model) economics summary in `nasde run` output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.runner import _collect_economics_rows, _fmt_score, _sample_std, _short_label


def _write_trial(job: Path, name: str, agent: str, model: str, score: float, tokens: int, cost: float) -> None:
    trial = job / name
    trial.mkdir(parents=True)
    trial.joinpath("result.json").write_text(json.dumps({"trial_name": name}))
    trial.joinpath("assessment_summary.json").write_text(
        json.dumps(
            {
                "task_name": "t",
                "trial_name": name,
                "agent_name": agent,
                "model_name": model,
                "groups": [{"dominant": True, "normalized_score_mean": score}],
                "token_usage": {"total_tokens": tokens},
                "cost_usd": cost,
            }
        )
    )


def test_short_label_strips_family_and_skill_prefixes() -> None:
    assert _short_label("claude-vanilla", "claude-sonnet-4-6") == "vanilla / sonnet-4-6"
    assert _short_label("claude-ntcoding-tactical-ddd-movie-tuned", "claude-sonnet-4-6") == "movie-tuned / sonnet-4-6"
    assert _short_label("claude-ntcoding-tactical-ddd", "claude-sonnet-4-6") == "tactical-ddd / sonnet-4-6"
    assert _short_label("codex-vanilla", "gpt-5.4") == "vanilla / gpt-5.4"


def test_sample_std_needs_two_points() -> None:
    assert _sample_std([]) is None
    assert _sample_std([0.5]) is None  # single trial → no spread
    assert _sample_std([0.6, 0.8]) == pytest.approx(0.1414, rel=1e-3)


def test_fmt_score_shows_spread_and_single_run_flag() -> None:
    assert _fmt_score(0.64, 0.08, 5) == "0.64 ±0.08"
    assert _fmt_score(0.64, None, 1) == "0.64 (n=1)"  # single run flagged
    assert _fmt_score(None, None, 0) == "—"


def test_economics_row_includes_score_std(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)
    _write_trial(job, "t__b", "claude-vanilla", "claude-sonnet-4-6", 0.8, 1_000_000, 2.0)
    row = _collect_economics_rows(job)[0]
    assert row["score"] == pytest.approx(0.7)
    assert row["score_std"] == pytest.approx(0.1414, rel=1e-3)


def test_economics_row_single_trial_has_no_std(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)
    row = _collect_economics_rows(job)[0]
    assert row["score"] == pytest.approx(0.6)
    assert row["score_std"] is None  # n=1 → no spread


def test_economics_row_averages_per_trial(tmp_path: Path) -> None:
    job = tmp_path / "job"
    # two trials of the same (agent, model): tokens 1M and 3M, cost $2 and $6, score 0.6 and 0.8
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)
    _write_trial(job, "t__b", "claude-vanilla", "claude-sonnet-4-6", 0.8, 3_000_000, 6.0)

    rows = _collect_economics_rows(job)
    assert len(rows) == 1
    row = rows[0]
    assert row["trials"] == 2
    assert row["score"] == pytest.approx(0.7)  # mean of 0.6, 0.8
    assert row["tokens"] == pytest.approx(2_000_000)  # mean tokens, NOT sum
    assert row["cost"] == pytest.approx(4.0)  # mean cost, NOT sum
    # efficiencies from the means
    assert row["cost_efficiency"] == pytest.approx(0.7 / 4.0)
    assert row["token_efficiency"] == pytest.approx(0.7 / 2.0)  # 0.7 per 2M tokens
    assert row["short_label"] == "vanilla / sonnet-4-6"
    assert row["full_label"] == "claude-vanilla / claude-sonnet-4-6"


def test_economics_groups_split_by_model(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "codex-vanilla", "gpt-5.4", 0.7, 1_000_000, 2.0)
    _write_trial(job, "t__b", "codex-vanilla", "gpt-5.5", 0.7, 1_000_000, 5.0)

    rows = _collect_economics_rows(job)
    assert len(rows) == 2  # same agent_name, different model_name → two rows
    assert {r["full_label"] for r in rows} == {"codex-vanilla / gpt-5.4", "codex-vanilla / gpt-5.5"}
