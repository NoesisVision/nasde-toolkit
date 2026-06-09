"""Tests for token usage + cost economics extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.pricing import load_pricing
from nasde_toolkit.token_metrics import (
    build_trial_economics,
    dominant_normalized_score,
    extract_token_usage,
    read_trajectory,
)

CLAUDE_TRAJ = {
    "final_metrics": {
        "total_prompt_tokens": 1_109_410,
        "total_completion_tokens": 55_518,
        "total_cached_tokens": 1_031_868,
        "extra": {"total_cache_creation_input_tokens": 74_666},
    }
}

CODEX_TRAJ = {
    "final_metrics": {
        "total_prompt_tokens": 2_817_494,
        "total_completion_tokens": 23_401,
        "total_cached_tokens": 2_646_272,
        "extra": {"reasoning_output_tokens": 13_921, "total_tokens": 2_840_895},
    }
}


def test_extract_claude_shape() -> None:
    usage = extract_token_usage(CLAUDE_TRAJ)
    assert usage is not None
    assert usage.input_tokens == 1_109_410
    assert usage.reasoning_tokens == 0
    assert usage.output_tokens == 55_518  # no reasoning to fold in
    assert usage.total_tokens == 1_109_410 + 55_518


def test_extract_codex_folds_reasoning_into_output() -> None:
    usage = extract_token_usage(CODEX_TRAJ)
    assert usage is not None
    assert usage.completion_tokens == 23_401
    assert usage.reasoning_tokens == 13_921
    assert usage.output_tokens == 23_401 + 13_921  # reasoning folded in
    assert usage.total_tokens == 2_817_494 + 23_401 + 13_921


def test_extract_legacy_without_final_metrics_is_none() -> None:
    assert extract_token_usage({"steps": []}) is None
    assert extract_token_usage({"final_metrics": {"total_steps": 5}}) is None


def test_dominant_normalized_score_picks_dominant() -> None:
    groups = [
        {"dominant": False, "normalized_score_mean": 0.3},
        {"dominant": True, "normalized_score_mean": 0.8},
    ]
    assert dominant_normalized_score(groups) == 0.8


def test_dominant_normalized_score_falls_back_to_first() -> None:
    groups = [{"normalized_score_mean": 0.5}, {"normalized_score_mean": 0.9}]
    assert dominant_normalized_score(groups) == 0.5  # no dominant flag → first


def test_dominant_normalized_score_empty_is_none() -> None:
    assert dominant_normalized_score([]) is None


def test_read_trajectory_run_layout(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CODEX_TRAJ))
    assert read_trajectory(tmp_path) == CODEX_TRAJ


def test_read_trajectory_export_layout(tmp_path: Path) -> None:
    (tmp_path / "trajectory.json").write_text(json.dumps(CLAUDE_TRAJ))
    assert read_trajectory(tmp_path) == CLAUDE_TRAJ


def test_read_trajectory_missing_is_none(tmp_path: Path) -> None:
    assert read_trajectory(tmp_path) is None


def test_build_trial_economics_priced_model(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CODEX_TRAJ))
    econ = build_trial_economics(tmp_path, "gpt-5.4", load_pricing())

    assert econ["model_name"] == "gpt-5.4"
    assert econ["token_usage"]["total_tokens"] == 2_854_816
    # gpt-5.4 = $2.50 in / $15 out: 2.817494M*2.5 + 0.037322M*15
    assert econ["cost_usd"] == pytest.approx(2_817_494 / 1e6 * 2.5 + 37_322 / 1e6 * 15)
    assert econ["pricing_as_of"] == "2026-06-08"


def test_build_trial_economics_no_trajectory_is_empty(tmp_path: Path) -> None:
    econ = build_trial_economics(tmp_path, "gpt-5.4", load_pricing())
    assert econ["token_usage"] is None
    assert econ["cost_usd"] is None
    assert econ["pricing_as_of"] is None


def test_build_trial_economics_unpriced_model_keeps_tokens(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CODEX_TRAJ))
    econ = build_trial_economics(tmp_path, "unpriced", load_pricing())

    assert econ["token_usage"]["total_tokens"] == 2_854_816  # tokens still computed
    assert econ["cost_usd"] is None


def test_build_trial_economics_has_no_scalar_efficiency_keys(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CODEX_TRAJ))
    econ = build_trial_economics(tmp_path, "gpt-5.4", load_pricing())
    assert "token_efficiency" not in econ  # removed: arbitrary zero → use Pareto front
    assert "cost_efficiency" not in econ
