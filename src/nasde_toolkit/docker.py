"""Docker environment preparation for benchmark tasks.

Generates Dockerfiles that clone a git repo (remote URL) or copy from a local
path at a specific ref, and run build commands to prepare the environment for
agent evaluation. For local repos, creates a temporary git worktree at the
specified ref so Docker builds from a clean snapshot — not the current working
tree. Also generates a docker-compose.yaml that overrides the build context.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

from rich.console import Console

from nasde_toolkit.config import DockerConfig, SourceConfig

console = Console()

_active_worktrees: list[Path] = []


def ensure_task_environment(
    task_dir: Path,
    source: SourceConfig,
    docker: DockerConfig,
) -> None:
    """Generate environment/Dockerfile (and docker-compose.yaml for local repos) if missing.

    For local repos with a ref, creates a temporary git worktree checked out
    at the specified commit so Docker builds from that snapshot — not the
    current working tree which may contain later changes.
    """
    env_dir = task_dir / "environment"
    if (env_dir / "Dockerfile").exists():
        return

    env_dir.mkdir(parents=True, exist_ok=True)

    dockerfile_content = generate_dockerfile(source, docker)
    (env_dir / "Dockerfile").write_text(dockerfile_content)
    console.print(f"  [dim]Generated Dockerfile in {env_dir}[/dim]")

    if _is_local_path(source.git):
        build_context_dir = _resolve_local_build_context(task_dir, source)
        compose_content = _generate_build_context_compose(env_dir, build_context_dir)
        (env_dir / "docker-compose.yaml").write_text(compose_content)
        console.print(f"  [dim]Generated docker-compose.yaml in {env_dir}[/dim]")


def generate_dockerfile(
    source: SourceConfig,
    docker: DockerConfig,
) -> str:
    """Generate a Dockerfile for the given source — dispatches on local vs remote."""
    if _is_local_path(source.git):
        return _generate_local_dockerfile(source, docker)
    return _generate_remote_dockerfile(source, docker)


def build_task_image(
    task_name: str,
    source: SourceConfig,
    docker: DockerConfig,
    build_dir: Path,
) -> str:
    """Build a Docker image for a benchmark task."""
    dockerfile_content = generate_dockerfile(source, docker)

    build_dir.mkdir(parents=True, exist_ok=True)
    dockerfile_path = build_dir / "Dockerfile"
    dockerfile_path.write_text(dockerfile_content)

    image_tag = f"nasde-{task_name}:latest"

    console.print(f"  Building Docker image [bold]{image_tag}[/bold]...")

    result = subprocess.run(
        ["docker", "build", "-t", image_tag, "-f", str(dockerfile_path), str(build_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"  [red]Docker build failed:[/red]\n{result.stderr}")
        raise RuntimeError(f"Docker build failed for {task_name}")

    console.print(f"  [green]Image built:[/green] {image_tag}")
    return image_tag


def _generate_build_context_compose(env_dir: Path, build_context_dir: Path) -> str:
    """Generate a docker-compose.yaml that overrides the build context.

    Also sets dockerfile to point back to environment/Dockerfile since
    changing the context moves the Dockerfile lookup root.
    """
    relative_context = os.path.relpath(build_context_dir, env_dir)
    dockerfile_from_context = os.path.relpath(env_dir / "Dockerfile", build_context_dir)

    return dedent(f"""\
        services:
          main:
            build:
              context: {relative_context}
              dockerfile: {dockerfile_from_context}
    """)


def cleanup_worktrees() -> None:
    """Remove all temporary worktrees created during the run."""
    for worktree_path in _active_worktrees:
        with contextlib.suppress(OSError):
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                capture_output=True,
                check=False,
            )
    _active_worktrees.clear()


def _resolve_local_build_context(task_dir: Path, source: SourceConfig) -> Path:
    """Determine the Docker build context directory for a local repo.

    If source has a ref, creates a temporary git worktree at that commit
    so Docker builds from a clean historical snapshot. Without a ref,
    falls back to the repo directory as-is.
    """
    repo_abs = (task_dir / source.git).resolve()

    if not source.ref:
        return repo_abs

    return _create_ref_worktree(repo_abs, source.ref)


def _create_ref_worktree(repo_dir: Path, ref: str) -> Path:
    """Create a temporary git worktree checked out at the given ref."""
    worktree_dir = Path(tempfile.mkdtemp(prefix="nasde-build-"))

    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_dir), ref],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree at {ref} in {repo_dir}: {result.stderr}")

    _active_worktrees.append(worktree_dir)
    atexit.register(cleanup_worktrees)
    console.print(f"  [dim]Created build worktree at {ref} → {worktree_dir}[/dim]")
    return worktree_dir


def _generate_local_dockerfile(source: SourceConfig, docker: DockerConfig) -> str:
    """Generate a Dockerfile that copies from a local repo.

    Uses COPY instead of git clone. The build context is set by the
    compose override — either the repo root (no ref) or a temporary
    worktree checked out at the specified ref.
    """
    build_steps = "\n".join(f"RUN {cmd}" for cmd in docker.build_commands)

    return dedent(f"""\
        FROM {docker.base_image}

        ENV PATH="/root/.local/bin:$PATH"

        RUN apt-get update && apt-get install -y \\
            git curl wget ca-certificates \\
            && rm -rf /var/lib/apt/lists/*

        WORKDIR /app
        COPY . /app

        {build_steps}

        CMD ["/bin/bash"]
    """)


def _generate_remote_dockerfile(source: SourceConfig, docker: DockerConfig) -> str:
    """Generate a Dockerfile that clones a remote git repo at a specific ref."""
    git_url = _normalize_git_url(source.git)
    build_steps = "\n".join(f"RUN {cmd}" for cmd in docker.build_commands)

    return dedent(f"""\
        FROM {docker.base_image}

        RUN apt-get update && apt-get install -y \\
            git curl wget ca-certificates \\
            && rm -rf /var/lib/apt/lists/*

        WORKDIR /app
        RUN git clone {git_url} . && git checkout {source.ref}

        {build_steps}

        CMD ["/bin/bash"]
    """)


def _is_local_path(git_path: str) -> bool:
    """Return True if the git path is a local filesystem path rather than a URL."""
    return not git_path.startswith(("http://", "https://", "git://", "file://"))


def _normalize_git_url(git_path: str) -> str:
    """Convert local filesystem paths to file:// URLs, pass URLs through."""
    if git_path.startswith(("http://", "https://", "git://", "file://")):
        return git_path
    if git_path == ".":
        return "file://."
    resolved = Path(git_path).resolve()
    return f"file://{resolved}"
