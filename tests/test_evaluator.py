"""Tests for evaluator trajectory integration."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator import _build_claude_code_options, _build_evaluator_prompt, _resolve_trajectory_path


def test_prompt_no_trajectory_section_when_disabled() -> None:
    prompt = _build_evaluator_prompt(
        instruction="Fix the bug",
        criteria="Check correctness",
        expected_dimensions=[{"name": "correctness", "title": "Correctness", "max_score": 25}],
        ground_truth="",
        artifacts_dir="/workspace",
        trajectory_path=None,
    )
    assert "trajectory" not in prompt.lower()


def test_prompt_includes_trajectory_section_when_path_provided() -> None:
    prompt = _build_evaluator_prompt(
        instruction="Fix the bug",
        criteria="Check correctness",
        expected_dimensions=[{"name": "correctness", "title": "Correctness", "max_score": 25}],
        ground_truth="",
        artifacts_dir="/workspace",
        trajectory_path="../../agent/trajectory.json",
    )
    assert "## Agent trajectory" in prompt
    assert "../../agent/trajectory.json" in prompt
    assert "ATIF" in prompt


def test_claude_code_options_adds_trial_dir_when_trajectory_enabled(tmp_path: Path) -> None:
    workspace_path = tmp_path / "artifacts" / "workspace"
    workspace_path.mkdir(parents=True)
    trial_dir = tmp_path

    eval_config = EvaluationConfig(include_trajectory=True)
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root=Path(),
        trial_dir=trial_dir,
    )
    assert str(trial_dir) in [str(d) for d in options.add_dirs]

    if temp_dir:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
    if stderr_path:
        stderr_path.unlink(missing_ok=True)


def test_claude_code_options_no_trial_dir_when_trajectory_disabled(tmp_path: Path) -> None:
    workspace_path = tmp_path / "artifacts" / "workspace"
    workspace_path.mkdir(parents=True)
    trial_dir = tmp_path

    eval_config = EvaluationConfig(include_trajectory=False)
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root=Path(),
        trial_dir=trial_dir,
    )
    assert str(trial_dir) not in [str(d) for d in options.add_dirs]

    if temp_dir:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
    if stderr_path:
        stderr_path.unlink(missing_ok=True)


def test_resolve_trajectory_path_returns_none_when_disabled(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text("{}")

    eval_config = EvaluationConfig(include_trajectory=False)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result is None


def test_resolve_trajectory_path_returns_none_when_file_missing(tmp_path: Path) -> None:
    eval_config = EvaluationConfig(include_trajectory=True)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result is None


def test_resolve_trajectory_path_returns_relative_path_when_file_exists(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text("{}")

    eval_config = EvaluationConfig(include_trajectory=True)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result == "../../agent/trajectory.json"
