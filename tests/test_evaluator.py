"""Tests for evaluator trajectory integration and dimension scoring."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator import (
    DimensionScore,
    EvaluationResult,
    _aggregate_evaluations,
    _build_evaluator_prompt,
    _build_opik_scores,
    _dimensions_fingerprint,
    _dominant_group,
    _evaluate_and_record_trial,
    _evaluation_from_dict,
    _load_expected_dimensions,
    _next_eval_index,
    _parse_evaluation_response,
    _resolve_trajectory_path,
    _write_assessment_summary,
    _write_evaluation_result,
)


def _make_evaluation(
    normalized_score: float,
    evaluator_model: str = "claude-opus-4-7",
    dim_score: int = 8,
    timestamp: str = "2026-06-03T10:00:00+00:00",
    dimensions_fingerprint: str = "fp-default",
) -> EvaluationResult:
    return EvaluationResult(
        task_name="demo-task",
        trial_name="demo-task__abc",
        agent_name="demo-variant",
        evaluator_model=evaluator_model,
        timestamp=timestamp,
        dimensions=[DimensionScore(name="domain_modeling", score=dim_score, max_score=10, reasoning="ok")],
        total_score=dim_score,
        normalized_score=normalized_score,
        summary="summary text",
        harbor_reward=1.0,
        duration_sec=100.0,
        dimensions_fingerprint=dimensions_fingerprint,
    )


def test_next_eval_index_empty_dir_is_one(tmp_path: Path) -> None:
    assert _next_eval_index(tmp_path) == 1


def test_next_eval_index_skips_to_highest_plus_one(tmp_path: Path) -> None:
    (tmp_path / "assessment_eval_1.json").write_text("{}")
    (tmp_path / "assessment_eval_2.json").write_text("{}")
    assert _next_eval_index(tmp_path) == 3


def test_next_eval_index_ignores_bare_file(tmp_path: Path) -> None:
    (tmp_path / "assessment_eval.json").write_text("{}")
    assert _next_eval_index(tmp_path) == 1


def test_write_evaluation_result_is_append_only(tmp_path: Path) -> None:
    first = _write_evaluation_result(tmp_path, _make_evaluation(0.5))
    second = _write_evaluation_result(tmp_path, _make_evaluation(0.7))

    assert first.name == "assessment_eval_1.json"
    assert second.name == "assessment_eval_2.json"
    assert not (tmp_path / "assessment_eval.json").exists()
    assert json.loads(first.read_text())["normalized_score"] == 0.5
    assert json.loads(second.read_text())["normalized_score"] == 0.7


def test_aggregate_mean_std_minmax() -> None:
    evals = [
        _make_evaluation(0.6, dim_score=6),
        _make_evaluation(0.7, dim_score=7),
        _make_evaluation(0.62, dim_score=8),
    ]
    summary = _aggregate_evaluations(evals)

    assert len(summary.groups) == 1
    group = summary.groups[0]
    assert group.n == 3
    dim = group.dimensions[0]
    assert dim.mean == 7.0
    assert dim.min == 6.0
    assert dim.max == 8.0
    assert dim.std == 1.0
    assert group.normalized_score_mean == 0.64


def test_aggregate_groups_by_evaluator_model_never_mixes() -> None:
    evals = [
        _make_evaluation(0.6, evaluator_model="claude-opus-4-7", dim_score=6),
        _make_evaluation(0.7, evaluator_model="claude-opus-4-7", dim_score=7),
        _make_evaluation(0.5, evaluator_model="codex-gpt-5", dim_score=4),
    ]
    summary = _aggregate_evaluations(evals)

    by_model = {g.evaluator_model: g for g in summary.groups}
    assert set(by_model) == {"claude-opus-4-7", "codex-gpt-5"}
    assert by_model["claude-opus-4-7"].n == 2
    assert by_model["codex-gpt-5"].n == 1
    assert by_model["claude-opus-4-7"].dimensions[0].mean == 6.5


def test_dominant_group_is_max_n() -> None:
    evals = [
        _make_evaluation(0.6, evaluator_model="claude-opus-4-7"),
        _make_evaluation(0.7, evaluator_model="claude-opus-4-7"),
        _make_evaluation(0.5, evaluator_model="codex-gpt-5"),
    ]
    summary = _aggregate_evaluations(evals)

    dominant = [g for g in summary.groups if g.dominant]
    assert len(dominant) == 1
    assert dominant[0].evaluator_model == "claude-opus-4-7"


def test_build_opik_scores_uses_dominant_group_with_std_and_n() -> None:
    evals = [
        _make_evaluation(0.6, evaluator_model="claude-opus-4-7", dim_score=6),
        _make_evaluation(0.7, evaluator_model="claude-opus-4-7", dim_score=8),
        _make_evaluation(0.5, evaluator_model="codex-gpt-5", dim_score=4),
    ]
    summary = _aggregate_evaluations(evals)
    group = _dominant_group(summary)
    scores = _build_opik_scores("trace-1", group)

    by_name = {s["name"]: s for s in scores}
    assert group.evaluator_model == "claude-opus-4-7"
    assert by_name["arch_domain_modeling"]["value"] == 0.7
    assert "arch_domain_modeling_std" in by_name
    assert "arch_total" in by_name
    assert "arch_total_std" in by_name
    assert by_name["eval_n"]["value"] == 2.0
    assert "reward" in by_name
    assert "duration_sec" in by_name


def test_aggregate_std_n1_is_zero() -> None:
    summary = _aggregate_evaluations([_make_evaluation(0.6, dim_score=6)])
    group = summary.groups[0]
    assert group.n == 1
    assert group.dimensions[0].std == 0.0
    assert group.normalized_score_std == 0.0


def test_aggregate_same_model_different_fingerprints_yields_two_groups() -> None:
    evals = [
        _make_evaluation(0.6, dimensions_fingerprint="aaa"),
        _make_evaluation(0.7, dimensions_fingerprint="aaa"),
        _make_evaluation(0.9, dimensions_fingerprint="bbb"),
    ]
    summary = _aggregate_evaluations(evals)

    by_fp = {g.dimensions_fingerprint: g for g in summary.groups}
    assert set(by_fp) == {"aaa", "bbb"}
    assert by_fp["aaa"].n == 2
    assert by_fp["bbb"].n == 1
    assert by_fp["aaa"].evaluator_model == "claude-opus-4-7"


def test_aggregate_legacy_no_fingerprint_is_empty_cluster() -> None:
    evals = [
        _make_evaluation(0.6, dimensions_fingerprint=""),
        _make_evaluation(0.7, dimensions_fingerprint=""),
    ]
    summary = _aggregate_evaluations(evals)

    assert len(summary.groups) == 1
    assert summary.groups[0].dimensions_fingerprint == ""
    assert summary.groups[0].n == 2


def test_dimensions_fingerprint_stable_under_whitespace_reformat(tmp_path: Path) -> None:
    payload = {
        "dimensions": [
            {"name": "a", "title": "A", "max_score": 10, "description": "desc a"},
            {"name": "b", "title": "B", "max_score": 5, "description": "desc b"},
        ]
    }
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps(payload, separators=(",", ":")))
    pretty = tmp_path / "pretty.json"
    pretty.write_text(json.dumps(payload, indent=4))

    assert _dimensions_fingerprint(compact) == _dimensions_fingerprint(pretty)


def test_dimensions_fingerprint_changes_on_description_edit(tmp_path: Path) -> None:
    base = {"dimensions": [{"name": "a", "max_score": 10, "description": "original"}]}
    p1 = tmp_path / "v1.json"
    p1.write_text(json.dumps(base))
    p2 = tmp_path / "v2.json"
    p2.write_text(json.dumps({"dimensions": [{"name": "a", "max_score": 10, "description": "EDITED"}]}))
    p3 = tmp_path / "v3.json"
    p3.write_text(json.dumps({"dimensions": [{"name": "a", "max_score": 50, "description": "original"}]}))
    p4 = tmp_path / "v4.json"
    added_dim = {
        "dimensions": [
            {"name": "a", "max_score": 10, "description": "original"},
            {"name": "b", "max_score": 5},
        ]
    }
    p4.write_text(json.dumps(added_dim))

    fp1 = _dimensions_fingerprint(p1)
    assert fp1 != _dimensions_fingerprint(p2)
    assert fp1 != _dimensions_fingerprint(p3)
    assert fp1 != _dimensions_fingerprint(p4)


def test_dimensions_fingerprint_empty_when_file_missing(tmp_path: Path) -> None:
    assert _dimensions_fingerprint(tmp_path / "nope.json") == ""


def test_evaluation_fingerprint_survives_json_round_trip() -> None:
    evaluation = _make_evaluation(0.6, dimensions_fingerprint="abc123")
    reloaded = _evaluation_from_dict(json.loads(json.dumps(asdict(evaluation))))
    assert reloaded.dimensions_fingerprint == "abc123"
    legacy = _evaluation_from_dict({"trial_name": "t", "dimensions": []})
    assert legacy.dimensions_fingerprint == ""


def test_write_assessment_summary_has_no_reasoning(tmp_path: Path) -> None:
    _write_evaluation_result(tmp_path, _make_evaluation(0.6, dim_score=6))
    _write_evaluation_result(tmp_path, _make_evaluation(0.7, dim_score=7))

    summary = _write_assessment_summary(tmp_path)
    assert summary is not None
    raw = (tmp_path / "assessment_summary.json").read_text()
    assert "reasoning" not in raw
    parsed = json.loads(raw)
    assert parsed["groups"][0]["n"] == 2


def _seed_trajectory(trial_dir: Path) -> None:
    (trial_dir / "config.json").write_text(
        json.dumps({"agent": {"name": "demo-variant", "model_name": "claude-sonnet-4-6"}})
    )
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir()
    (agent_dir / "trajectory.json").write_text(
        json.dumps(
            {
                "final_metrics": {
                    "total_prompt_tokens": 1_000_000,
                    "total_completion_tokens": 50_000,
                    "total_cached_tokens": 800_000,
                    "extra": {"reasoning_output_tokens": 10_000},
                }
            }
        )
    )


def test_assessment_summary_includes_economics(tmp_path: Path) -> None:
    _seed_trajectory(tmp_path)
    _write_evaluation_result(tmp_path, _make_evaluation(0.6, dim_score=6))
    _write_evaluation_result(tmp_path, _make_evaluation(0.7, dim_score=7))

    summary = _write_assessment_summary(tmp_path)
    assert summary is not None
    assert summary.model_name == "claude-sonnet-4-6"
    assert summary.token_usage["total_tokens"] == 1_060_000
    # sonnet $3/$15: 1M*3 + 0.06M*15 = 3.9
    assert summary.cost_usd == pytest.approx(3.9)
    assert summary.cost_efficiency is not None
    assert summary.pricing_as_of == "2026-06-08"


def test_assessment_summary_economics_null_without_trajectory(tmp_path: Path) -> None:
    _write_evaluation_result(tmp_path, _make_evaluation(0.6, dim_score=6))

    summary = _write_assessment_summary(tmp_path)
    assert summary is not None
    assert summary.token_usage is None
    assert summary.cost_usd is None
    assert summary.cost_efficiency is None


def test_eval_repetitions_writes_n_files(tmp_path: Path) -> None:
    scores = iter([0.6, 0.7, 0.62])
    config = EvaluationConfig(eval_repetitions=3)

    async def fake_evaluate_trial(
        trial_dir: Path, project_root: Path, eval_config: EvaluationConfig
    ) -> EvaluationResult:
        return _make_evaluation(next(scores), dim_score=6)

    with patch("nasde_toolkit.evaluator.evaluate_trial", side_effect=fake_evaluate_trial):
        asyncio.run(
            _evaluate_and_record_trial(
                tmp_path,
                tmp_path,
                "proj",
                with_opik=False,
                semaphore=asyncio.Semaphore(10),
                eval_config=config,
            )
        )

    numbered = sorted(p.name for p in tmp_path.glob("assessment_eval_*.json"))
    assert numbered == ["assessment_eval_1.json", "assessment_eval_2.json", "assessment_eval_3.json"]
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 3


def test_eval_repetitions_one_writes_single_file(tmp_path: Path) -> None:
    config = EvaluationConfig(eval_repetitions=1)

    async def fake_evaluate_trial(
        trial_dir: Path, project_root: Path, eval_config: EvaluationConfig
    ) -> EvaluationResult:
        return _make_evaluation(0.6, dim_score=6)

    with patch("nasde_toolkit.evaluator.evaluate_trial", side_effect=fake_evaluate_trial):
        asyncio.run(
            _evaluate_and_record_trial(
                tmp_path,
                tmp_path,
                "proj",
                with_opik=False,
                semaphore=asyncio.Semaphore(10),
                eval_config=config,
            )
        )

    numbered = sorted(p.name for p in tmp_path.glob("assessment_eval_*.json"))
    assert numbered == ["assessment_eval_1.json"]


def test_evaluate_and_record_trial_writes_surviving_reps_on_partial_failure(tmp_path: Path) -> None:
    call_count = iter(range(3))
    config = EvaluationConfig(eval_repetitions=3)

    async def flaky_evaluate_trial(
        trial_dir: Path, project_root: Path, eval_config: EvaluationConfig
    ) -> EvaluationResult:
        index = next(call_count)
        if index == 1:
            raise RuntimeError("backend boom")
        return _make_evaluation(0.6, dim_score=6)

    with patch("nasde_toolkit.evaluator.evaluate_trial", side_effect=flaky_evaluate_trial):
        asyncio.run(
            _evaluate_and_record_trial(
                tmp_path,
                tmp_path,
                "proj",
                with_opik=False,
                semaphore=asyncio.Semaphore(10),
                eval_config=config,
            )
        )

    numbered = sorted(p.name for p in tmp_path.glob("assessment_eval_*.json"))
    assert numbered == ["assessment_eval_1.json", "assessment_eval_2.json"]
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 2


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
