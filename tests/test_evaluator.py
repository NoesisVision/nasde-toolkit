"""Tests for evaluator trajectory integration and dimension scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator import (
    _build_evaluator_prompt,
    _load_expected_dimensions,
    _parse_evaluation_response,
    _resolve_trajectory_path,
)


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


# ---------------------------------------------------------------------------
# Per-dimension max_score (ADR-008)
# ---------------------------------------------------------------------------


def _write_dimensions(tmp_path: Path, dims: list[dict]) -> Path:
    path = tmp_path / "assessment_dimensions.json"
    path.write_text(json.dumps({"dimensions": dims}))
    return path


def test_load_dimensions_accepts_arbitrary_max_scores(tmp_path: Path) -> None:
    raw = [
        {"name": "a", "max_score": 10},
        {"name": "b", "max_score": 5},
        {"name": "c", "max_score": 100},
        {"name": "d", "max_score": 3},
        {"name": "e", "max_score": 50},
        {"name": "f", "max_score": 20},
        {"name": "g", "max_score": 1},
    ]
    path = _write_dimensions(tmp_path, raw)
    loaded = _load_expected_dimensions(path)
    assert loaded == raw


def test_load_dimensions_rejects_missing_max_score(tmp_path: Path) -> None:
    path = _write_dimensions(tmp_path, [{"name": "a"}])
    with pytest.raises(ValueError, match="missing required field 'max_score'"):
        _load_expected_dimensions(path)


def test_load_dimensions_rejects_non_positive_max_score(tmp_path: Path) -> None:
    path = _write_dimensions(tmp_path, [{"name": "a", "max_score": 0}])
    with pytest.raises(ValueError, match="invalid max_score"):
        _load_expected_dimensions(path)


def test_parse_response_normalizes_against_actual_max_sum() -> None:
    expected = [
        {"name": "a", "max_score": 10},
        {"name": "b", "max_score": 5},
        {"name": "c", "max_score": 100},
        {"name": "d", "max_score": 3},
        {"name": "e", "max_score": 50},
        {"name": "f", "max_score": 20},
        {"name": "g", "max_score": 1},
    ]
    response = """```json
{
  "dimensions": [
    {"name": "a", "score": 10, "max_score": 10, "reasoning": ""},
    {"name": "b", "score": 5, "max_score": 5, "reasoning": ""},
    {"name": "c", "score": 100, "max_score": 100, "reasoning": ""},
    {"name": "d", "score": 3, "max_score": 3, "reasoning": ""},
    {"name": "e", "score": 50, "max_score": 50, "reasoning": ""},
    {"name": "f", "score": 20, "max_score": 20, "reasoning": ""},
    {"name": "g", "score": 1, "max_score": 1, "reasoning": ""}
  ],
  "summary": "perfect"
}
```"""
    result = _parse_evaluation_response(response, expected)
    assert result is not None
    assert result.total_score == 189
    assert result.normalized_score == 1.0


def test_parse_response_clamps_per_dimension_not_to_25() -> None:
    expected = [{"name": "rich", "max_score": 50}]
    response = """```json
{
  "dimensions": [
    {"name": "rich", "score": 47, "max_score": 50, "reasoning": "ok"}
  ],
  "summary": "high"
}
```"""
    result = _parse_evaluation_response(response, expected)
    assert result is not None
    assert result.dimensions[0].score == 47
    assert result.dimensions[0].max_score == 50
    assert result.normalized_score == 0.94


def test_parse_response_clamps_overshoot_to_dimension_max() -> None:
    expected = [{"name": "small", "max_score": 10}]
    response = """```json
{
  "dimensions": [
    {"name": "small", "score": 999, "max_score": 10, "reasoning": "x"}
  ],
  "summary": "overshoot"
}
```"""
    result = _parse_evaluation_response(response, expected)
    assert result is not None
    assert result.dimensions[0].score == 10


def test_parse_response_backwards_compat_4x25() -> None:
    expected = [
        {"name": "a", "max_score": 25},
        {"name": "b", "max_score": 25},
        {"name": "c", "max_score": 25},
        {"name": "d", "max_score": 25},
    ]
    response = """```json
{
  "dimensions": [
    {"name": "a", "score": 25, "max_score": 25, "reasoning": ""},
    {"name": "b", "score": 25, "max_score": 25, "reasoning": ""},
    {"name": "c", "score": 25, "max_score": 25, "reasoning": ""},
    {"name": "d", "score": 25, "max_score": 25, "reasoning": ""}
  ],
  "summary": "ok"
}
```"""
    result = _parse_evaluation_response(response, expected)
    assert result is not None
    assert result.total_score == 100
    assert result.normalized_score == 1.0


def test_prompt_lists_per_dimension_ranges_not_shared_25() -> None:
    prompt = _build_evaluator_prompt(
        instruction="x",
        criteria="y",
        expected_dimensions=[
            {"name": "small", "max_score": 3},
            {"name": "medium", "max_score": 20},
            {"name": "large", "max_score": 100},
        ],
    )
    assert "0–25 points" not in prompt
    assert "Each dimension is 0–25" not in prompt
    assert "`small`: 0–3 points" in prompt
    assert "`medium`: 0–20 points" in prompt
    assert "`large`: 0–100 points" in prompt
