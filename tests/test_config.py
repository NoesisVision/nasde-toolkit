"""Tests for config module — harbor_env and evaluation settings in nasde.toml."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import load_project_config


def _write_nasde_toml(project_dir: Path, content: str) -> None:
    (project_dir / "nasde.toml").write_text(content)


def test_default_harbor_env_is_none(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[defaults]
variant = "vanilla"
""",
    )
    config = load_project_config(tmp_path)
    assert config.default_harbor_env is None


def test_harbor_env_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[defaults]
variant = "vanilla"
harbor_env = "daytona"
""",
    )
    config = load_project_config(tmp_path)
    assert config.default_harbor_env == "daytona"


def test_harbor_env_docker_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[defaults]
harbor_env = "docker"
""",
    )
    config = load_project_config(tmp_path)
    assert config.default_harbor_env == "docker"


def test_evaluation_defaults_when_section_absent(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"
""",
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.model == "claude-opus-4-6"
    assert config.evaluation.dimensions_file == "assessment_dimensions.json"
    assert config.evaluation.max_turns == 30
    assert config.evaluation.allowed_tools is None
    assert config.evaluation.mcp_config is None
    assert config.evaluation.skills_dir is None
    assert config.evaluation.append_system_prompt is None
    assert config.evaluation.include_trajectory is False


def test_evaluation_all_fields_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[evaluation]
model = "claude-sonnet-4-6"
dimensions_file = "custom_dims.json"
max_turns = 50
allowed_tools = ["Read", "Glob", "Grep", "Bash"]
mcp_config = "./evaluator_mcp.json"
skills_dir = "./evaluator_skills"
append_system_prompt = "Focus on SOLID principles."
""",
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.model == "claude-sonnet-4-6"
    assert config.evaluation.dimensions_file == "custom_dims.json"
    assert config.evaluation.max_turns == 50
    assert config.evaluation.allowed_tools == ["Read", "Glob", "Grep", "Bash"]
    assert config.evaluation.mcp_config == "./evaluator_mcp.json"
    assert config.evaluation.skills_dir == "./evaluator_skills"
    assert config.evaluation.append_system_prompt == "Focus on SOLID principles."


def test_evaluation_partial_override(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[evaluation]
model = "claude-sonnet-4-6"
max_turns = 15
""",
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.model == "claude-sonnet-4-6"
    assert config.evaluation.max_turns == 15
    assert config.evaluation.mcp_config is None
    assert config.evaluation.skills_dir is None


def test_evaluation_include_trajectory_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[evaluation]
include_trajectory = true
""",
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.include_trajectory is True
