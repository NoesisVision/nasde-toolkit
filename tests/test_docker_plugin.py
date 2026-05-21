"""Tests for [nasde.plugin] staging + Dockerfile generation (ADR-009)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nasde_toolkit.config import DockerConfig, PluginConfig, SourceConfig
from nasde_toolkit.docker import (
    cleanup_worktrees,
    ensure_task_environment,
    ensure_task_plugin,
)


@pytest.fixture()
def default_docker() -> DockerConfig:
    return DockerConfig(base_image="ubuntu:22.04", build_commands=["apt-get install -y python3"])


def _make_plugin(root: Path, name: str = "noesis") -> Path:
    plugin = root / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name, "version": "0.1.0"}))
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "noesis-graph": {
                        "command": "bun",
                        "args": ["run", "mcp/noesis-graph/server.ts"],
                    }
                }
            }
        )
    )
    skill = plugin / "skills" / "analyze-conversation"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: analyze-conversation\n---\nbody")
    (skill / "references" / "extract-topics.md").write_text("rules A")
    (skill / "references" / "analyze-topic.md").write_text("rules B")
    (plugin / "node_modules").mkdir()
    (plugin / "node_modules" / "junk.js").write_text("// huge")
    return plugin


def _init_git_repo(repo_dir: Path) -> str:
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, capture_output=True, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_plugin_only_generates_base_dockerfile_and_stages(tmp_path: Path, default_docker: DockerConfig) -> None:
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    staged = ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=False)

    env_dir = task_dir / "environment"
    dockerfile = (env_dir / "Dockerfile").read_text()
    assert "FROM ubuntu:22.04" in dockerfile
    assert 'COPY ["_nasde-plugin/", "/opt/noesis/"]' in dockerfile
    assert dockerfile.rstrip().endswith('CMD ["/bin/bash"]')
    assert (env_dir / "_nasde-plugin" / ".claude-plugin" / "plugin.json").exists()
    assert not (env_dir / "_nasde-plugin" / "node_modules").exists()
    assert staged.install_root == "/opt/noesis"
    assert staged.plugin_name == "noesis"


def test_plugin_install_root_override(tmp_path: Path, default_docker: DockerConfig) -> None:
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    staged = ensure_task_plugin(
        task_dir,
        PluginConfig(path="../../plugin", install_root="/opt/noesis-plugin"),
        default_docker,
        has_source=False,
    )

    dockerfile = (task_dir / "environment" / "Dockerfile").read_text()
    assert 'COPY ["_nasde-plugin/", "/opt/noesis-plugin/"]' in dockerfile
    assert staged.install_root == "/opt/noesis-plugin"


def test_plugin_build_command_emitted(tmp_path: Path, default_docker: DockerConfig) -> None:
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    ensure_task_plugin(
        task_dir,
        PluginConfig(path="../../plugin", build="bun install --frozen-lockfile"),
        default_docker,
        has_source=False,
    )

    dockerfile = (task_dir / "environment" / "Dockerfile").read_text()
    assert "RUN cd /opt/noesis && bun install --frozen-lockfile" in dockerfile


def test_plugin_appends_to_handwritten_dockerfile(tmp_path: Path, default_docker: DockerConfig) -> None:
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    (env_dir / "Dockerfile").write_text('FROM oven/bun:1-debian\nWORKDIR /app\nCMD ["/bin/bash"]\n')

    ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=False)

    dockerfile = (env_dir / "Dockerfile").read_text()
    assert "FROM oven/bun:1-debian" in dockerfile
    assert "FROM ubuntu:22.04" not in dockerfile
    assert 'COPY ["_nasde-plugin/", "/opt/noesis/"]' in dockerfile
    assert dockerfile.rstrip().endswith('CMD ["/bin/bash"]')
    assert dockerfile.index('COPY ["_nasde-plugin') < dockerfile.rindex("CMD ")


def test_plugin_stage_is_idempotent(tmp_path: Path, default_docker: DockerConfig) -> None:
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    (env_dir / "Dockerfile").write_text('FROM oven/bun:1-debian\nCMD ["/bin/bash"]\n')

    for _ in range(3):
        ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=False)

    dockerfile = (env_dir / "Dockerfile").read_text()
    assert dockerfile.count('COPY ["_nasde-plugin/", "/opt/noesis/"]') == 1


def test_plugin_with_source_stages_into_compose_context(tmp_path: Path, default_docker: DockerConfig) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("repo")
    _make_plugin(tmp_path)
    task_dir = tmp_path / "proj" / "tasks" / "t"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git=str(repo), ref="")
    ensure_task_environment(task_dir, source, default_docker)
    staged = ensure_task_plugin(task_dir, PluginConfig(path="../../../plugin"), default_docker, has_source=True)

    env_dir = task_dir / "environment"
    compose = (env_dir / "docker-compose.yaml").read_text()
    context_line = [ln.strip() for ln in compose.splitlines() if "context:" in ln][0]
    context_dir = (env_dir / context_line.split("context:")[1].strip()).resolve()

    assert context_dir == repo.resolve()
    assert staged.staged_dir == repo / "_nasde-plugin"
    assert (repo / "_nasde-plugin" / ".claude-plugin" / "plugin.json").exists()
    dockerfile = (env_dir / "Dockerfile").read_text()
    assert 'COPY ["_nasde-plugin/", "/opt/noesis/"]' in dockerfile


def test_plugin_ref_uses_historical_snapshot(tmp_path: Path, default_docker: DockerConfig) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_plugin(repo)
    initial = _init_git_repo(repo)
    (repo / "plugin" / "skills" / "analyze-conversation" / "SKILL.md").write_text("CHANGED LATER")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "later"], cwd=repo, capture_output=True, check=True)

    task_dir = tmp_path / "proj" / "tasks" / "t"
    task_dir.mkdir(parents=True)

    try:
        staged = ensure_task_plugin(
            task_dir,
            PluginConfig(path="../../../repo/plugin", ref=initial),
            default_docker,
            has_source=False,
        )
        skill_md = staged.staged_dir / "skills" / "analyze-conversation" / "SKILL.md"
        assert "CHANGED LATER" not in skill_md.read_text()
        assert "body" in skill_md.read_text()
    finally:
        cleanup_worktrees()


def test_plugin_missing_manifest_raises(tmp_path: Path, default_docker: DockerConfig) -> None:
    not_a_plugin = tmp_path / "plugin"
    not_a_plugin.mkdir()
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="not a Claude Code plugin"):
        ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=False)


def test_plugin_missing_path_raises(tmp_path: Path, default_docker: DockerConfig) -> None:
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="does not exist"):
        ensure_task_plugin(task_dir, PluginConfig(path="../../nope"), default_docker, has_source=False)


def test_plugin_install_root_with_special_chars_is_quoted(tmp_path: Path, default_docker: DockerConfig) -> None:
    """Bug 005: install_root with whitespace or shell-special chars must be
    safely quoted in the `RUN cd … && build` line and use JSON-array form for
    COPY so Docker doesn't mis-split arguments."""
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    ensure_task_plugin(
        task_dir,
        PluginConfig(path="../../plugin", install_root="/opt/My Plugin", build="bun install"),
        default_docker,
        has_source=False,
    )

    dockerfile = (task_dir / "environment" / "Dockerfile").read_text()
    assert 'COPY ["_nasde-plugin/", "/opt/My Plugin/"]' in dockerfile
    assert "RUN cd '/opt/My Plugin' && bun install" in dockerfile


def test_plugin_dockerfile_strip_refuses_when_END_sentinel_missing(
    tmp_path: Path, default_docker: DockerConfig
) -> None:
    """Bug 003 (Dockerfile side): if the plugin stage END sentinel was hand-
    deleted, refuse to rewrite. Otherwise the next ensure_task_plugin run
    would silently truncate every instruction below the BEGIN marker."""
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    broken = (
        "FROM oven/bun:1-debian\nWORKDIR /app\n"
        "# >>> nasde plugin stage (generated — do not edit) >>>\n"
        "COPY _nasde-plugin/ /opt/noesis/\n"
        # END sentinel MISSING
        'CMD ["/bin/bash"]\n'
    )
    (env_dir / "Dockerfile").write_text(broken)

    with pytest.raises(RuntimeError, match="END sentinel"):
        ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=False)

    assert (env_dir / "Dockerfile").read_text() == broken


def test_plugin_ref_validates_manifest_against_worktree_not_working_tree(
    tmp_path: Path, default_docker: DockerConfig
) -> None:
    """Bug 010: with ref set, the .claude-plugin/plugin.json check must run
    against the worktree-at-ref, not the working tree. A working tree mid-
    refactor (plugin dir present as a stub, manifest removed) must NOT fail
    when ref points at a commit where the manifest existed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_plugin(repo)
    initial = _init_git_repo(repo)
    (repo / "plugin" / ".claude-plugin" / "plugin.json").unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "remove manifest"], cwd=repo, capture_output=True, check=True)
    assert not (repo / "plugin" / ".claude-plugin" / "plugin.json").exists()
    assert (repo / "plugin").exists()

    task_dir = tmp_path / "proj" / "tasks" / "t"
    task_dir.mkdir(parents=True)

    try:
        staged = ensure_task_plugin(
            task_dir,
            PluginConfig(path="../../../repo/plugin", ref=initial),
            default_docker,
            has_source=False,
        )
        assert (staged.staged_dir / ".claude-plugin" / "plugin.json").exists()
    finally:
        cleanup_worktrees()


def test_plugin_with_remote_source_falls_back_to_env_dir(tmp_path: Path, default_docker: DockerConfig) -> None:
    """Bug 001: remote [nasde.source] generates no compose; plugin must not
    crash trying to read a non-existent docker-compose.yaml. Stage falls back
    to environment/ (same as the no-source case)."""
    _make_plugin(tmp_path)
    task_dir = tmp_path / "tasks" / "t"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git="https://github.com/some/repo.git", ref="main")
    ensure_task_environment(task_dir, source, default_docker)
    env_dir = task_dir / "environment"
    assert not (env_dir / "docker-compose.yaml").exists()

    staged = ensure_task_plugin(task_dir, PluginConfig(path="../../plugin"), default_docker, has_source=True)

    assert staged.staged_dir == env_dir / "_nasde-plugin"
    assert (env_dir / "_nasde-plugin" / ".claude-plugin" / "plugin.json").exists()
