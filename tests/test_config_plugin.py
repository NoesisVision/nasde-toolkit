"""Tests for [nasde.plugin] parsing in task.toml (ADR-009)."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import PluginConfig, load_project_config


def _scaffold_project(tmp_path: Path, task_toml: str) -> Path:
    (tmp_path / "nasde.toml").write_text('[project]\nname = "p"\n')
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(task_toml)
    (task_dir / "instruction.md").write_text("do it")
    return task_dir


def test_plugin_absent_yields_none(tmp_path: Path) -> None:
    _scaffold_project(tmp_path, '[task]\nname = "p/t"\n')
    config = load_project_config(tmp_path)
    assert config.tasks[0].plugin is None


def test_plugin_minimal_path_only(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        '[task]\nname = "p/t"\n\n[nasde.plugin]\npath = "../../../plugin"\n',
    )
    config = load_project_config(tmp_path)
    plugin = config.tasks[0].plugin
    assert plugin == PluginConfig(path="../../../plugin")
    assert plugin.ref == ""
    assert plugin.install_root == ""
    assert plugin.build == ""
    assert plugin.env == {}


def test_plugin_all_fields(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        """
[task]
name = "p/t"

[nasde.plugin]
path = "../../../src/plugins/noesis"
ref = "abc1234"
install_root = "/opt/noesis-plugin"
build = "bun install --frozen-lockfile"

[nasde.plugin.env]
CLAUDE_PLUGIN_DATA = "/opt/noesis-data"
NOESIS_PROJECT_DIR = "/app"
""",
    )
    config = load_project_config(tmp_path)
    plugin = config.tasks[0].plugin
    assert plugin is not None
    assert plugin.path == "../../../src/plugins/noesis"
    assert plugin.ref == "abc1234"
    assert plugin.install_root == "/opt/noesis-plugin"
    assert plugin.build == "bun install --frozen-lockfile"
    assert plugin.env == {"CLAUDE_PLUGIN_DATA": "/opt/noesis-data", "NOESIS_PROJECT_DIR": "/app"}


def test_plugin_partial_ref_only(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        '[task]\nname = "p/t"\n\n[nasde.plugin]\npath = "../plugin"\nref = "v1.2.0"\n',
    )
    config = load_project_config(tmp_path)
    plugin = config.tasks[0].plugin
    assert plugin is not None
    assert plugin.ref == "v1.2.0"
    assert plugin.install_root == ""


def test_plugin_without_path_is_ignored(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        '[task]\nname = "p/t"\n\n[nasde.plugin]\nref = "abc1234"\n',
    )
    config = load_project_config(tmp_path)
    assert config.tasks[0].plugin is None


def test_plugin_and_source_coexist(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        """
[task]
name = "p/t"

[nasde.source]
git = "../../../.."
ref = "deadbeef"

[nasde.plugin]
path = "../../../src/plugins/noesis"
""",
    )
    config = load_project_config(tmp_path)
    task = config.tasks[0]
    assert task.source is not None
    assert task.source.git == "../../../.."
    assert task.plugin is not None
    assert task.plugin.path == "../../../src/plugins/noesis"


def test_plugin_env_values_coerced_to_str(tmp_path: Path) -> None:
    _scaffold_project(
        tmp_path,
        """
[task]
name = "p/t"

[nasde.plugin]
path = "../plugin"

[nasde.plugin.env]
PORT = 8080
""",
    )
    config = load_project_config(tmp_path)
    plugin = config.tasks[0].plugin
    assert plugin is not None
    assert plugin.env == {"PORT": "8080"}
