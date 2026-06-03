"""Tests for results_exporter — flat per-trial export of Harbor artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nasde_toolkit.results_exporter import (
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
    (trial_dir / "assessment_eval.json").write_text(json.dumps({"normalized_score": 0.7}))
    (trial_dir / "assessment_eval_1.json").write_text(json.dumps({"normalized_score": 0.6}))
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir()
    (agent_dir / "trajectory.json").write_text(json.dumps({"steps": []}))
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


def test_export_flat_layout(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    summary = export_results([job_dir], dest)

    assert len(summary.exported) == 2
    out = dest / "2026-06-03__demo-job__demo-task__aaa111"
    assert out.is_dir()
    assert (out / "metrics.json").exists()
    assert (out / "assessment_eval.json").exists()
    assert (out / "assessment_eval_1.json").exists()
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
