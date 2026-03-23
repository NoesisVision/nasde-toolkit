"""Tests for docker module — Dockerfile generation and task environment setup."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nasde_toolkit.config import DockerConfig, SourceConfig
from nasde_toolkit.docker import (
    cleanup_worktrees,
    ensure_task_environment,
    generate_dockerfile,
)


@pytest.fixture()
def default_docker() -> DockerConfig:
    return DockerConfig(base_image="ubuntu:22.04", build_commands=["apt-get install -y python3"])


def _init_git_repo(repo_dir: Path, *, with_commit: bool = True) -> str:
    """Initialize a git repo and optionally create a commit. Returns the commit hash."""
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    if not with_commit:
        return ""

    (repo_dir / "hello.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_generate_dockerfile_remote_url(default_docker: DockerConfig) -> None:
    source = SourceConfig(git="https://github.com/org/repo.git", ref="main")
    dockerfile = generate_dockerfile(source, default_docker)

    assert "FROM ubuntu:22.04" in dockerfile
    assert "git clone https://github.com/org/repo.git . && git checkout main" in dockerfile
    assert "COPY . /app" not in dockerfile
    assert "apt-get install -y python3" in dockerfile


def test_generate_dockerfile_local_absolute_path(default_docker: DockerConfig) -> None:
    source = SourceConfig(git="/tmp/my-repo", ref="feature-branch")
    dockerfile = generate_dockerfile(source, default_docker)

    assert "FROM ubuntu:22.04" in dockerfile
    assert "COPY . /app" in dockerfile
    assert "git clone" not in dockerfile
    assert "git checkout" not in dockerfile
    assert "apt-get install -y python3" in dockerfile


def test_generate_dockerfile_relative_path(default_docker: DockerConfig) -> None:
    source = SourceConfig(git="../..", ref="HEAD")
    dockerfile = generate_dockerfile(source, default_docker)

    assert "COPY . /app" in dockerfile
    assert "git clone" not in dockerfile
    assert "git checkout" not in dockerfile


def test_ensure_task_environment_existing_dockerfile_skips(
    tmp_path: Path,
    default_docker: DockerConfig,
) -> None:
    task_dir = tmp_path / "tasks" / "my-task"
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    (env_dir / "Dockerfile").write_text("FROM scratch\n")

    source = SourceConfig(git="https://github.com/org/repo.git", ref="main")

    ensure_task_environment(task_dir, source, default_docker)

    assert (env_dir / "Dockerfile").read_text() == "FROM scratch\n"
    assert not (env_dir / "docker-compose.yaml").exists()


def test_ensure_task_environment_generates_for_remote(
    tmp_path: Path,
    default_docker: DockerConfig,
) -> None:
    task_dir = tmp_path / "tasks" / "my-task"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git="https://github.com/org/repo.git", ref="main")

    ensure_task_environment(task_dir, source, default_docker)

    env_dir = task_dir / "environment"
    assert (env_dir / "Dockerfile").exists()
    dockerfile = (env_dir / "Dockerfile").read_text()
    assert "git clone https://github.com/org/repo.git" in dockerfile
    assert not (env_dir / "docker-compose.yaml").exists()


def test_ensure_task_environment_generates_compose_for_local_no_ref(
    tmp_path: Path,
    default_docker: DockerConfig,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "project" / "tasks" / "my-task"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git=str(repo_dir), ref="")

    ensure_task_environment(task_dir, source, default_docker)

    env_dir = task_dir / "environment"
    assert (env_dir / "Dockerfile").exists()
    assert (env_dir / "docker-compose.yaml").exists()
    compose = (env_dir / "docker-compose.yaml").read_text()
    assert "context:" in compose
    assert "dockerfile:" in compose


def test_ensure_task_environment_compose_context_resolves_to_repo_no_ref(
    tmp_path: Path,
    default_docker: DockerConfig,
) -> None:
    repo_dir = tmp_path / "upstream-repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "project" / "tasks" / "my-task"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git=str(repo_dir), ref="")

    ensure_task_environment(task_dir, source, default_docker)

    env_dir = task_dir / "environment"
    compose = (env_dir / "docker-compose.yaml").read_text()

    context_line = [line.strip() for line in compose.splitlines() if "context:" in line][0]
    relative_context = context_line.split("context:")[1].strip()

    resolved_from_env = (env_dir / relative_context).resolve()
    assert resolved_from_env == repo_dir.resolve()

    dockerfile_line = [line.strip() for line in compose.splitlines() if "dockerfile:" in line][0]
    relative_dockerfile = dockerfile_line.split("dockerfile:")[1].strip()

    resolved_dockerfile = (repo_dir / relative_dockerfile).resolve()
    assert resolved_dockerfile == (env_dir / "Dockerfile").resolve()


def test_ensure_task_environment_creates_worktree_for_local_with_ref(
    tmp_path: Path,
    default_docker: DockerConfig,
) -> None:
    repo_dir = tmp_path / "my-repo"
    repo_dir.mkdir()
    initial_commit = _init_git_repo(repo_dir)

    (repo_dir / "new_file.txt").write_text("later change")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    task_dir = tmp_path / "project" / "tasks" / "my-task"
    task_dir.mkdir(parents=True)

    source = SourceConfig(git=str(repo_dir), ref=initial_commit)

    try:
        ensure_task_environment(task_dir, source, default_docker)

        env_dir = task_dir / "environment"
        compose = (env_dir / "docker-compose.yaml").read_text()

        context_line = [line.strip() for line in compose.splitlines() if "context:" in line][0]
        relative_context = context_line.split("context:")[1].strip()
        worktree_dir = (env_dir / relative_context).resolve()

        assert worktree_dir.exists()
        assert (worktree_dir / "hello.txt").exists()
        assert not (worktree_dir / "new_file.txt").exists()
    finally:
        cleanup_worktrees()
