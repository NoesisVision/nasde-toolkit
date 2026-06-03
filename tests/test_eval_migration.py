"""Tests for eval_migration — normalizing legacy assessment eval files."""

from __future__ import annotations

import json
from pathlib import Path

from nasde_toolkit.eval_migration import migrate_trial_evals


def _eval_payload(normalized_score: float, evaluator_model: str = "claude-opus-4-7") -> dict:
    return {
        "task_name": "demo-task",
        "trial_name": "demo-task__abc",
        "agent_name": "demo-variant",
        "evaluator_model": evaluator_model,
        "timestamp": "2026-06-03T10:00:00+00:00",
        "dimensions": [{"name": "domain_modeling", "score": 8, "max_score": 10, "reasoning": "ok"}],
        "total_score": 8,
        "normalized_score": normalized_score,
        "summary": "summary",
        "harbor_reward": 1.0,
        "duration_sec": 100.0,
    }


def _write(trial_dir: Path, name: str, payload: dict) -> None:
    (trial_dir / name).write_text(json.dumps(payload))


def test_migrate_bare_only_renames_to_1(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.6))

    outcome = migrate_trial_evals(tmp_path)

    assert outcome == "migrated"
    assert not (tmp_path / "assessment_eval.json").exists()
    assert (tmp_path / "assessment_eval_1.json").exists()
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 1


def test_migrate_numbered_plus_duplicate_bare_deletes_bare(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval_1.json", _eval_payload(0.6))
    _write(tmp_path, "assessment_eval_2.json", _eval_payload(0.7))
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.7))

    outcome = migrate_trial_evals(tmp_path)

    assert outcome == "migrated"
    assert not (tmp_path / "assessment_eval.json").exists()
    assert (tmp_path / "assessment_eval_1.json").exists()
    assert (tmp_path / "assessment_eval_2.json").exists()
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 2


def test_migrate_picks_highest_numerically_not_lexicographically(tmp_path: Path) -> None:
    for i in range(1, 10):
        _write(tmp_path, f"assessment_eval_{i}.json", _eval_payload(0.5))
    _write(tmp_path, "assessment_eval_10.json", _eval_payload(0.9))
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.9))

    outcome = migrate_trial_evals(tmp_path)

    assert outcome == "migrated"
    assert not (tmp_path / "assessment_eval.json").exists()
    assert not (tmp_path / "assessment_eval_11.json").exists()
    numbered = sorted(p.name for p in tmp_path.glob("assessment_eval_*.json"))
    assert "assessment_eval_10.json" in numbered
    assert len(numbered) == 10
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 10


def test_migrate_divergent_bare_is_promoted(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval_1.json", _eval_payload(0.6))
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.9))

    outcome = migrate_trial_evals(tmp_path)

    assert outcome == "migrated"
    assert not (tmp_path / "assessment_eval.json").exists()
    assert (tmp_path / "assessment_eval_2.json").exists()
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    assert summary["groups"][0]["n"] == 2


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.6))
    migrate_trial_evals(tmp_path)
    first_summary = (tmp_path / "assessment_summary.json").read_text()

    second_outcome = migrate_trial_evals(tmp_path)
    second_summary = (tmp_path / "assessment_summary.json").read_text()

    assert second_outcome == "summarized"
    assert first_summary == second_summary
    assert sorted(p.name for p in tmp_path.glob("assessment_eval_*.json")) == ["assessment_eval_1.json"]


def test_migrate_dry_run_touches_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval.json", _eval_payload(0.6))

    outcome = migrate_trial_evals(tmp_path, dry_run=True)

    assert outcome == "migrated"
    assert (tmp_path / "assessment_eval.json").exists()
    assert not (tmp_path / "assessment_eval_1.json").exists()
    assert not (tmp_path / "assessment_summary.json").exists()


def test_migrate_mixed_models_yields_two_groups(tmp_path: Path) -> None:
    _write(tmp_path, "assessment_eval_1.json", _eval_payload(0.6, evaluator_model="claude-opus-4-7"))
    _write(tmp_path, "assessment_eval_2.json", _eval_payload(0.5, evaluator_model="codex-gpt-5"))

    outcome = migrate_trial_evals(tmp_path)

    assert outcome == "summarized"
    summary = json.loads((tmp_path / "assessment_summary.json").read_text())
    models = {g["evaluator_model"] for g in summary["groups"]}
    assert models == {"claude-opus-4-7", "codex-gpt-5"}
