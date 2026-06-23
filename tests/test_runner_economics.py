"""Tests for the per-(agent, model) economics summary in `nasde run` output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.runner import (
    _collect_economics_rows,
    _fmt_cost,
    _fmt_score,
    _fmt_tokens,
    _job_dir_from_config,
    _print_job_summary,
    _sample_std,
    _short_label,
)


def _write_trial(
    job: Path,
    name: str,
    agent: str,
    model: str,
    score: float,
    tokens: int,
    cost: float,
    effort: str = "",
) -> None:
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
                "reasoning_effort": effort,
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


def test_fmt_cost_shows_spread_only_with_std() -> None:
    assert _fmt_cost(4.0, None) == "$4.00"  # n=1 → bare value
    assert _fmt_cost(4.0, 2.0) == "$4.00 ±2.00"  # n≥2 → spread
    assert _fmt_cost(None, None) == "—"


def test_fmt_tokens_scales_and_shows_spread() -> None:
    assert _fmt_tokens(2_000_000, None) == "2.0M"  # n=1 → bare value
    assert _fmt_tokens(2_000_000, 500_000) == "2.0M ±500k"  # n≥2 → spread
    assert _fmt_tokens(None, None) == "—"


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
    assert row["short_label"] == "vanilla / sonnet-4-6"
    assert row["full_label"] == "claude-vanilla / claude-sonnet-4-6"
    assert "cost_efficiency" not in row  # removed: arbitrary zero → use Pareto front
    assert "token_efficiency" not in row


def test_economics_row_raw_metric_std_needs_two_trials(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)
    _write_trial(job, "t__b", "claude-vanilla", "claude-sonnet-4-6", 0.8, 3_000_000, 6.0)
    row = _collect_economics_rows(job)[0]
    assert row["tokens_std"] == pytest.approx(_sample_std([1_000_000, 3_000_000]))
    assert row["cost_std"] == pytest.approx(_sample_std([2.0, 6.0]))


def test_economics_row_single_trial_has_no_raw_metric_std(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)
    row = _collect_economics_rows(job)[0]
    assert row["tokens_std"] is None  # n=1 → no spread
    assert row["cost_std"] is None


def test_economics_groups_split_by_model(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "codex-vanilla", "gpt-5.4", 0.7, 1_000_000, 2.0)
    _write_trial(job, "t__b", "codex-vanilla", "gpt-5.5", 0.7, 1_000_000, 5.0)

    rows = _collect_economics_rows(job)
    assert len(rows) == 2  # same agent_name, different model_name → two rows
    assert {r["full_label"] for r in rows} == {"codex-vanilla / gpt-5.4", "codex-vanilla / gpt-5.5"}


def test_economics_groups_split_by_effort(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.7, 1_000_000, 2.0, effort="high")
    _write_trial(job, "t__b", "claude-vanilla", "claude-sonnet-4-6", 0.9, 1_000_000, 2.0, effort="xhigh")

    rows = _collect_economics_rows(job)
    assert len(rows) == 2  # same agent+model, different effort → two rows, never averaged
    assert {r["reasoning_effort"] for r in rows} == {"high", "xhigh"}


def test_job_dir_from_config_resolves_own_job(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    merged = {"jobs_dir": str(jobs_dir), "job_name": "2026-06-09__20-29-49__claude-vanilla__abc123"}
    assert _job_dir_from_config(merged) == jobs_dir / "2026-06-09__20-29-49__claude-vanilla__abc123"


def test_job_dir_from_config_ignores_newer_concurrent_job(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    own = jobs_dir / "2026-06-09__20-29-49__claude-sonnet__own456"
    newer_concurrent = jobs_dir / "2026-06-09__20-30-03__codex-gpt__newer789"
    _write_trial(own, "t__a", "claude-sonnet", "claude-sonnet-4-6", 0.7, 1_000_000, 2.0)
    newer_concurrent.mkdir(parents=True)  # newer by name, still running → no result.json yet

    newest_by_name = sorted((d for d in jobs_dir.iterdir() if d.is_dir()), key=lambda p: p.name)[-1]
    assert newest_by_name == newer_concurrent  # what the old _find_latest_job scan WOULD have picked

    merged = {"jobs_dir": str(jobs_dir), "job_name": own.name}
    resolved = _job_dir_from_config(merged)

    assert resolved == own  # config-based resolution wins over the newest-by-name sibling
    assert resolved != newest_by_name  # the exact divergence the race fix guarantees
    assert _collect_economics_rows(resolved)[0]["score"] == pytest.approx(0.7)


def test_job_dir_from_config_returns_none_without_keys() -> None:
    assert _job_dir_from_config({}) is None
    assert _job_dir_from_config({"jobs_dir": "/x"}) is None
    assert _job_dir_from_config({"job_name": "j"}) is None


def _job_result(n_completed: int) -> object:
    from harbor.models.job.result import AgentDatasetStats, JobResult, JobStats

    return JobResult(
        id="00000000-0000-0000-0000-000000000000",
        started_at="2026-06-09T20:29:49Z",
        n_total_trials=n_completed,
        stats=JobStats(
            n_completed_trials=n_completed,
            n_errored_trials=0,
            evals={"claude-vanilla/t": AgentDatasetStats(n_trials=n_completed, n_errors=0)},
        ),
    )


def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    import nasde_toolkit.runner as runner

    monkeypatch.setattr(runner, "console", Console(width=10_000))


def _flat(out: str) -> str:
    return " ".join(out.split())


def test_print_job_summary_warns_when_own_job_has_no_economics(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _wide_console(monkeypatch)
    job = tmp_path / "job"
    job.mkdir()  # our own completed job, but assessment never wrote a summary

    _print_job_summary(_job_result(n_completed=1), job)

    out = _flat(capsys.readouterr().out)
    assert "no assessment_summary.json found" in out
    assert "nasde eval" in out


def test_print_job_summary_renders_economics_for_own_job(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _wide_console(monkeypatch)
    job = tmp_path / "job"
    _write_trial(job, "t__a", "claude-vanilla", "claude-sonnet-4-6", 0.6, 1_000_000, 2.0)

    _print_job_summary(_job_result(n_completed=1), job)

    out = _flat(capsys.readouterr().out)
    assert "Results by agent/model" in out
    assert "no assessment_summary.json found" not in out


def test_economics_row_carries_model_name(tmp_path: Path) -> None:
    job = tmp_path / "job"
    _write_trial(job, "t__a", "codex-vanilla", "gpt-5.4", 0.7, 1000, 1.0)
    _write_trial(job, "t__b", "claude-vanilla", "claude-sonnet-4-6", 0.8, 1000, 1.0)

    rows = _collect_economics_rows(job)
    assert {row["model"] for row in rows} == {"gpt-5.4", "claude-sonnet-4-6"}
