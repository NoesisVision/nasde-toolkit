from __future__ import annotations

import subprocess
from pathlib import Path

from nasde_toolkit.calibration_publisher import (
    _base_branch_name,
    _feature_branch_name,
    _render_pr_body,
    _slug_from_origin,
)
from nasde_toolkit.evaluator import (
    AssessmentSummary,
    DimensionStats,
    EvaluatorGroupSummary,
)
from nasde_toolkit.git_platform_backends.git_ops import _apply_agent_patch


def _summary_with_dominant() -> AssessmentSummary:
    dominant = EvaluatorGroupSummary(
        evaluator_model="claude-opus-4-7",
        dimensions_fingerprint="abc123",
        n=3,
        dominant=True,
        dimensions=[
            DimensionStats(name="domain_modeling", max_score=30, mean=18.0, std=1.5, min=16, max=20),
            DimensionStats(name="separation", max_score=25, mean=22.0, std=0.5, min=21, max=23),
        ],
        normalized_score_mean=0.72,
        normalized_score_std=0.03,
    )
    non_dominant = EvaluatorGroupSummary(
        evaluator_model="other-model",
        dimensions_fingerprint="xyz789",
        n=1,
        dominant=False,
        dimensions=[DimensionStats(name="domain_modeling", max_score=30, mean=29.0, std=0.0, min=29, max=29)],
        normalized_score_mean=0.95,
    )
    return AssessmentSummary(
        task_name="movie",
        trial_name="movie__abc",
        agent_name="vanilla",
        groups=[dominant, non_dominant],
    )


def test_render_pr_body_shows_dominant_dimensions() -> None:
    body = _render_pr_body(_summary_with_dominant(), {"model_name": "claude-sonnet-4-6", "harbor_reward": 1.0})
    assert "domain_modeling" in body
    assert "18.00 ± 1.50" in body
    assert "22.00 ± 0.50" in body
    assert "0.7200" in body
    assert "n=3" in body
    assert "movie" in body
    assert "How to calibrate" in body


def test_render_pr_body_excludes_non_dominant_cluster() -> None:
    body = _render_pr_body(_summary_with_dominant(), {"model_name": "x", "harbor_reward": 0})
    assert "0.95" not in body
    assert "29.00" not in body


def test_render_pr_body_handles_no_evaluations() -> None:
    summary = AssessmentSummary(task_name="t", trial_name="t__1", agent_name="a", groups=[])
    body = _render_pr_body(summary, {"model_name": "", "harbor_reward": 0})
    assert "No assessment evaluations" in body


def test_branch_names_are_deterministic_and_keyed_on_repo_sha() -> None:
    base = _base_branch_name("owner-repo", "deadbee")
    feat_a = _feature_branch_name("owner-repo", "deadbee", "movie__A")
    feat_b = _feature_branch_name("owner-repo", "deadbee", "movie__B")
    assert base == "base/owner-repo-deadbee"
    assert feat_a == "calib/owner-repo-deadbee/movie__A"
    assert feat_a != feat_b
    assert _base_branch_name("owner-repo", "deadbee") == base


def test_slug_normalizes_ssh_and_https_to_same_key() -> None:
    ssh = _slug_from_origin("git@github.com:christianhujer/expensereport.git")
    https = _slug_from_origin("https://github.com/christianhujer/expensereport.git")
    assert ssh == https == "christianhujer-expensereport"


def _git(work: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(work), *args], capture_output=True, text=True, check=True)


def test_apply_agent_patch_reproduces_clean_diff(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-q")
    _git(base, "config", "user.email", "t@t.co")
    _git(base, "config", "user.name", "t")
    (base / "tracked.txt").write_text("line one\nline two\n")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "start state")

    (base / "tracked.txt").write_text("line one CHANGED\nline two\n")
    (base / "new_file.txt").write_text("brand new\n")
    tracked_diff = subprocess.run(
        ["git", "-C", str(base), "diff", "HEAD"], capture_output=True, text=True, check=True
    ).stdout
    untracked_diff = subprocess.run(
        ["git", "-C", str(base), "diff", "--no-index", "--", "/dev/null", "new_file.txt"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    patch_text = tracked_diff + untracked_diff

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _git(fresh, "init", "-q")
    _git(fresh, "config", "user.email", "t@t.co")
    _git(fresh, "config", "user.name", "t")
    (fresh / "tracked.txt").write_text("line one\nline two\n")
    _git(fresh, "add", "-A")
    _git(fresh, "commit", "-q", "-m", "start state")

    _apply_agent_patch(fresh, patch_text)

    assert (fresh / "tracked.txt").read_text() == "line one CHANGED\nline two\n"
    assert (fresh / "new_file.txt").read_text() == "brand new\n"
