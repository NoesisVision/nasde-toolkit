"""Tests for runner module — harbor_env propagation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nasde_toolkit.config import (
    DockerConfig,
    EvaluationConfig,
    ProjectConfig,
    ReportingConfig,
    SourceConfig,
    TaskConfig,
)
from nasde_toolkit.runner import _build_merged_config, collect_available_variants


@pytest.fixture()
def tmp_project(tmp_path: Path) -> ProjectConfig:
    task_dir = tmp_path / "tasks" / "sample-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps({
        "name": "sample-task",
        "source": {"git": "https://example.com/repo.git", "ref": "main"},
    }))

    variant_dir = tmp_path / "variants" / "vanilla"
    variant_dir.mkdir(parents=True)
    harbor_config = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "vanilla",
                "kwargs": {"sandbox_files": {}},
            }
        ]
    }
    (variant_dir / "harbor_config.json").write_text(json.dumps(harbor_config))

    return ProjectConfig(
        name="test-benchmark",
        version="1.0.0",
        project_dir=tmp_path,
        tasks=[
            TaskConfig(
                name="sample-task",
                path=task_dir,
                source=SourceConfig(git="https://example.com/repo.git", ref="main"),
            )
        ],
    )


def test_build_merged_config_default_has_no_environment(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
    )
    assert "environment" not in result


def test_build_merged_config_with_harbor_env_daytona(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env="daytona",
    )
    assert result["environment"] == {"type": "daytona"}


def test_build_merged_config_with_harbor_env_modal(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env="modal",
    )
    assert result["environment"] == {"type": "modal"}


def test_build_merged_config_none_harbor_env_omits_environment(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env=None,
    )
    assert "environment" not in result


# ---------------------------------------------------------------------------
# collect_available_variants
# ---------------------------------------------------------------------------


def test_collect_available_variants_discovers_multiple(tmp_path: Path) -> None:
    (tmp_path / "variants" / "vanilla").mkdir(parents=True)
    (tmp_path / "variants" / "enhanced").mkdir(parents=True)
    (tmp_path / "variants" / "minimal").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["enhanced", "minimal", "vanilla"]


def test_collect_available_variants_nasde_subdir(tmp_path: Path) -> None:
    (tmp_path / ".nasde" / "variants" / "alpha").mkdir(parents=True)
    (tmp_path / ".nasde" / "variants" / "beta").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["alpha", "beta"]


def test_collect_available_variants_merges_both_locations(tmp_path: Path) -> None:
    (tmp_path / "variants" / "vanilla").mkdir(parents=True)
    (tmp_path / ".nasde" / "variants" / "special").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["special", "vanilla"]


def test_collect_available_variants_empty(tmp_path: Path) -> None:
    assert collect_available_variants(tmp_path) == []


def test_collect_available_variants_ignores_files(tmp_path: Path) -> None:
    (tmp_path / "variants").mkdir(parents=True)
    (tmp_path / "variants" / "vanilla").mkdir()
    (tmp_path / "variants" / "README.md").write_text("docs")
    assert collect_available_variants(tmp_path) == ["vanilla"]
