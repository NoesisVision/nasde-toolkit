"""Tests for results_exporter — flat per-trial export of Harbor artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nasde_toolkit.results_exporter import (
    _capture_patch,
    _classify_path,
    export_results,
)


def _git(workspace: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _init_workspace_repo(workspace: Path) -> None:
    workspace.mkdir(parents=True)
    (workspace / "kept.txt").write_text("original\n")
    _git(workspace, "init", "-q")
    _git(workspace, "config", "user.email", "test@example.com")
    _git(workspace, "config", "user.name", "test")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", "baseline")
    (workspace / "kept.txt").write_text("modified by agent\n")
    (workspace / "created.txt").write_text("brand new untracked file\n")


def _make_trial(trial_dir: Path, *, with_repo: bool = True) -> None:
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": trial_dir.name,
                "task_name": "demo-task",
                "source": "demo-bench",
                "started_at": "2026-06-03T10:00:00Z",
                "finished_at": "2026-06-03T10:10:00Z",
                "verifier_result": {"rewards": {"reward": 1.0}},
            }
        )
    )
    (trial_dir / "config.json").write_text(
        json.dumps({"agent": {"name": "demo-variant", "model_name": "claude-sonnet-4-6"}})
    )
    (trial_dir / "assessment_eval_1.json").write_text(json.dumps({"normalized_score": 0.6}))
    (trial_dir / "assessment_eval_2.json").write_text(json.dumps({"normalized_score": 0.7}))
    (trial_dir / "assessment_summary.json").write_text(
        json.dumps(
            {"groups": [{"n": 2, "dominant": True, "normalized_score_mean": 0.65, "normalized_score_std": 0.05}]}
        )
    )
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir()
    (agent_dir / "trajectory.json").write_text(
        json.dumps(
            {
                "steps": [],
                "final_metrics": {
                    "total_prompt_tokens": 1_000_000,
                    "total_completion_tokens": 50_000,
                    "total_cached_tokens": 800_000,
                    "extra": {"reasoning_output_tokens": 10_000},
                },
            }
        )
    )
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir()
    (verifier_dir / "test-stdout.txt").write_text("tests passed\n")
    (verifier_dir / "reward.txt").write_text("1\n")
    if with_repo:
        _init_workspace_repo(trial_dir / "artifacts" / "workspace")


@pytest.fixture()
def job_dir(tmp_path: Path) -> Path:
    job = tmp_path / "jobs" / "2026-06-03__demo-job"
    job.mkdir(parents=True)
    (job / "result.json").write_text(json.dumps({"job": "level"}))
    (job / "config.json").write_text(json.dumps({"job": "config"}))
    _make_trial(job / "demo-task__aaa111")
    _make_trial(job / "demo-task__bbb222")
    return job


def test_classify_job_vs_trial(job_dir: Path) -> None:
    assert _classify_path(job_dir) == "job"
    assert _classify_path(job_dir / "demo-task__aaa111") == "trial"
    assert _classify_path(job_dir / "result.json") is None


def test_classify_job_dir_without_result_children_is_skipped(tmp_path: Path) -> None:
    job = tmp_path / "2026-06-03__orphan-job"
    job.mkdir()
    (job / "result.json").write_text(json.dumps({"n_total_trials": 2, "stats": {}}))
    (job / "partial-child").mkdir()

    assert _classify_path(job) is None


def test_classify_trial_requires_trial_name(tmp_path: Path) -> None:
    no_name = tmp_path / "no-name"
    no_name.mkdir()
    (no_name / "result.json").write_text(json.dumps({"foo": 1}))
    assert _classify_path(no_name) is None

    with_name = tmp_path / "with-name"
    with_name.mkdir()
    (with_name / "result.json").write_text(json.dumps({"trial_name": "demo__abc"}))
    assert _classify_path(with_name) == "trial"


def test_classify_jobs_root_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    for job_name in ("2026-06-03__job-a", "2026-06-03__job-b"):
        job = root / job_name
        job.mkdir(parents=True)
        (job / "result.json").write_text(json.dumps({"id": "x", "n_total_trials": 1, "stats": {}}))
        _make_trial(job / "demo-task__child", with_repo=False)

    assert _classify_path(root) is None
    assert _classify_path(root / "2026-06-03__job-a") == "job"


def test_export_flat_layout(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    summary = export_results([job_dir], dest)

    assert len(summary.exported) == 2
    out = dest / "2026-06-03__demo-job__demo-task__aaa111"
    assert out.is_dir()
    assert (out / "metrics.json").exists()
    assert (out / "assessment_eval_1.json").exists()
    assert (out / "assessment_eval_2.json").exists()
    assert (out / "assessment_summary.json").exists()
    assert not (out / "assessment_eval.json").exists()
    assert (out / "trajectory.json").exists()
    assert (out / "verifier_stdout.txt").exists()
    assert (out / "reward.txt").exists()
    assert (out / "changes.patch").exists()
    assert not (out / "artifacts").exists()

    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["agent_name"] == "demo-variant"
    assert metrics["model_name"] == "claude-sonnet-4-6"
    assert metrics["duration_sec"] == 600.0
    assert metrics["harbor_reward"] == 1.0


def test_export_includes_token_cost_economics(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)
    metrics = json.loads((dest / "2026-06-03__demo-job__demo-task__aaa111" / "metrics.json").read_text())

    usage = metrics["token_usage"]
    assert usage["input_tokens"] == 1_000_000
    assert usage["output_tokens"] == 60_000  # completion 50k + reasoning 10k
    assert usage["total_tokens"] == 1_060_000
    # claude-sonnet-4-6: 1M*$3 + 0.06M*$15 = 3.0 + 0.9 = 3.9
    assert metrics["cost_usd"] == pytest.approx(3.9)
    assert metrics["pricing_as_of"] == "2026-06-08"
    assert "cost_efficiency" not in metrics  # removed: arbitrary zero → use Pareto front
    assert "token_efficiency" not in metrics
    assert metrics["reasoning_effort"] == ""  # fixture set no override
    # statistical rigor: judge-noise std + eval n + single-eval flag
    assert metrics["score"] == pytest.approx(0.65)
    assert metrics["score_eval_std"] == pytest.approx(0.05)
    assert metrics["score_eval_n"] == 2
    assert metrics["single_eval"] is False


def test_export_unpriced_model_leaves_cost_null(job_dir: Path, tmp_path: Path) -> None:
    trial = job_dir / "demo-task__aaa111"
    config = json.loads((trial / "config.json").read_text())
    config["agent"]["model_name"] = "some-unpriced-model"
    (trial / "config.json").write_text(json.dumps(config))

    dest = tmp_path / "export"
    export_results([job_dir], dest)
    metrics = json.loads((dest / "2026-06-03__demo-job__demo-task__aaa111" / "metrics.json").read_text())

    assert metrics["token_usage"]["total_tokens"] == 1_060_000  # tokens always computed
    assert metrics["cost_usd"] is None  # but cost left unset


def test_export_stamps_reasoning_effort_from_config(job_dir: Path, tmp_path: Path) -> None:
    trial = job_dir / "demo-task__aaa111"
    config = json.loads((trial / "config.json").read_text())
    config["agent"]["kwargs"] = {"reasoning_effort": "high"}
    (trial / "config.json").write_text(json.dumps(config))

    dest = tmp_path / "export"
    export_results([job_dir], dest)
    metrics = json.loads((dest / "2026-06-03__demo-job__demo-task__aaa111" / "metrics.json").read_text())

    assert metrics["reasoning_effort"] == "high"


def test_idempotent_skip(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)
    second = export_results([job_dir], dest)
    assert len(second.exported) == 0
    assert len(second.skipped) == 2


def test_patch_captures_modified_and_untracked(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)
    patch = (dest / "2026-06-03__demo-job__demo-task__aaa111" / "changes.patch").read_text()
    assert "modified by agent" in patch
    assert "brand new untracked file" in patch


def test_export_does_not_mutate_workspace_index(job_dir: Path, tmp_path: Path) -> None:
    workspace = job_dir / "demo-task__aaa111" / "artifacts" / "workspace"
    before = _git(workspace, "status", "--porcelain")
    export_results([job_dir], tmp_path / "export")
    after = _git(workspace, "status", "--porcelain")
    assert before == after
    assert _git(workspace, "diff", "--cached", "--name-only") == ""


def test_mixed_job_and_trial_paths(job_dir: Path, tmp_path: Path) -> None:
    standalone = tmp_path / "jobs" / "2026-06-03__other-job" / "demo-task__ccc333"
    _make_trial(standalone, with_repo=False)
    dest = tmp_path / "export"

    summary = export_results([job_dir, standalone], dest)

    assert len(summary.exported) == 3
    assert (dest / "2026-06-03__other-job__demo-task__ccc333").is_dir()


def test_dedup_trial_inside_listed_job(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    summary = export_results([job_dir, job_dir / "demo-task__aaa111"], dest)
    assert len(summary.exported) == 2


def test_export_merges_new_evals(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)

    trial = job_dir / "demo-task__aaa111"
    (trial / "assessment_eval_3.json").write_text(json.dumps({"normalized_score": 0.8}))

    second = export_results([job_dir], dest)

    out = dest / "2026-06-03__demo-job__demo-task__aaa111"
    assert (out / "assessment_eval_3.json").exists()
    assert out.name in second.exported


def test_export_preserves_immutable_files_on_merge(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)

    out = dest / "2026-06-03__demo-job__demo-task__aaa111"
    (out / "changes.patch").write_text("SENTINEL")
    (out / "trajectory.json").write_text("SENTINEL")

    trial = job_dir / "demo-task__aaa111"
    (trial / "assessment_eval_3.json").write_text(json.dumps({"normalized_score": 0.8}))
    export_results([job_dir], dest)

    assert (out / "changes.patch").read_text() == "SENTINEL"
    assert (out / "trajectory.json").read_text() == "SENTINEL"


def _make_bare_only_trial(trial_dir: Path) -> None:
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": trial_dir.name,
                "task_name": "demo-task",
                "source": "demo-bench",
                "verifier_result": {"rewards": {"reward": 1.0}},
            }
        )
    )
    (trial_dir / "config.json").write_text(json.dumps({"agent": {"name": "demo-variant"}}))
    (trial_dir / "assessment_eval.json").write_text(json.dumps({"normalized_score": 0.7}))


def test_export_copies_legacy_bare_assessment(tmp_path: Path) -> None:
    trial = tmp_path / "jobs" / "2026-06-03__legacy-job" / "demo-task__bare1"
    _make_bare_only_trial(trial)
    dest = tmp_path / "export"

    summary = export_results([trial], dest)

    out = dest / "2026-06-03__legacy-job__demo-task__bare1"
    assert (out / "assessment_eval_1.json").exists()
    assert not (out / "assessment_eval.json").exists()
    assert out.name in summary.exported


def test_export_legacy_bare_idempotent(tmp_path: Path) -> None:
    trial = tmp_path / "jobs" / "2026-06-03__legacy-job" / "demo-task__bare2"
    _make_bare_only_trial(trial)
    dest = tmp_path / "export"

    export_results([trial], dest)
    second = export_results([trial], dest)

    out = dest / "2026-06-03__legacy-job__demo-task__bare2"
    assert out.name in second.skipped


def test_capture_patch_includes_non_ascii_untracked_filename(tmp_path: Path) -> None:
    workspace = tmp_path / "artifacts" / "workspace"
    workspace.mkdir(parents=True)
    _git(workspace, "init", "-q")
    _git(workspace, "config", "user.email", "test@example.com")
    _git(workspace, "config", "user.name", "test")
    _git(workspace, "config", "core.quotepath", "true")
    (workspace / "seed.txt").write_text("seed\n")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", "baseline")
    (workspace / "café.txt").write_text("accented untracked body\n")

    patch = _capture_patch(workspace)

    assert "accented untracked body" in patch
