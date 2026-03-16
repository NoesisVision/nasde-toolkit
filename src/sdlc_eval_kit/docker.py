"""Docker environment preparation for benchmark tasks.

Generates Dockerfiles that clone a git repo (local path or URL) at a specific
ref and run build commands to prepare the environment for agent evaluation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from rich.console import Console

from sdlc_eval_kit.config import DockerConfig, SourceConfig

console = Console()


def generate_dockerfile(
    source: SourceConfig,
    docker: DockerConfig,
) -> str:
    """Generate a Dockerfile that clones a git repo at a specific ref."""
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

    image_tag = f"sdlc-eval-{task_name}:latest"

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


def _normalize_git_url(git_path: str) -> str:
    """Convert local filesystem paths to file:// URLs, pass URLs through."""
    if git_path.startswith(("http://", "https://", "git://", "file://")):
        return git_path
    if git_path == ".":
        return "file://."
    resolved = Path(git_path).resolve()
    return f"file://{resolved}"
