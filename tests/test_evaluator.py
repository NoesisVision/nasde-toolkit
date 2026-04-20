"""Tests for evaluator trajectory integration."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator import _build_evaluator_prompt, _resolve_trajectory_path


def test_evaluate_trial_uses_configured_backend() -> None:
    """Verify factory returns the right backend type based on config."""
    from nasde_toolkit.evaluator_backends import create_backend

    claude_config = EvaluationConfig(backend="claude")
    codex_config = EvaluationConfig(backend="codex")

    claude_backend = create_backend(claude_config)
    codex_backend = create_backend(codex_config)

    assert type(claude_backend).__name__ == "ClaudeSubprocessBackend"
    assert type(codex_backend).__name__ == "CodexSubprocessBackend"


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
