"""Tests for config module — harbor_env in nasde.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit.config import load_project_config


def _write_nasde_toml(project_dir: Path, content: str) -> None:
    (project_dir / "nasde.toml").write_text(content)


def test_default_harbor_env_is_none(tmp_path: Path) -> None:
    _write_nasde_toml(tmp_path, """
[project]
name = "test"

[defaults]
variant = "vanilla"
""")
    config = load_project_config(tmp_path)
    assert config.default_harbor_env is None


def test_harbor_env_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(tmp_path, """
[project]
name = "test"

[defaults]
variant = "vanilla"
harbor_env = "daytona"
""")
    config = load_project_config(tmp_path)
    assert config.default_harbor_env == "daytona"


def test_harbor_env_docker_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(tmp_path, """
[project]
name = "test"

[defaults]
harbor_env = "docker"
""")
    config = load_project_config(tmp_path)
    assert config.default_harbor_env == "docker"
