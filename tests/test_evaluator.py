"""Tests for evaluator trajectory integration."""

from __future__ import annotations

from nasde_toolkit.evaluator import _build_evaluator_prompt


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
