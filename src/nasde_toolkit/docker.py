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
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from rich.console import Console

from nasde_toolkit.config import DockerConfig, PluginConfig, SourceConfig

console = Console()

_active_worktrees: list[Path] = []

_PLUGIN_STAGE_DIR = "_nasde-plugin"
_PLUGIN_STAGE_MARKER = "# >>> nasde plugin stage (generated — do not edit) >>>"


@dataclass
class StagedPlugin:
    """Result of staging a [nasde.plugin] dir into a task's build context.

    Returned by ensure_task_plugin so the runner can register the plugin's
    skills and MCP server. ``staged_dir`` is the on-host plugin copy (used
    to read .claude-plugin/plugin.json, .mcp.json and enumerate skills/);
    ``install_root`` is where the plugin lands inside the sandbox image.
    """

    staged_dir: Path
    install_root: str
    plugin_name: str
    env: dict[str, str]


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

    if not (env_dir / "Dockerfile").exists():
        env_dir.mkdir(parents=True, exist_ok=True)
        dockerfile_content = generate_dockerfile(source, docker)
        (env_dir / "Dockerfile").write_text(dockerfile_content)
        console.print(f"  [dim]Generated Dockerfile in {env_dir}[/dim]")

    if _is_local_path(source.git):
        build_context_dir = _resolve_local_build_context(task_dir, source)
        compose_content = _generate_build_context_compose(env_dir, build_context_dir)
        (env_dir / "docker-compose.yaml").write_text(compose_content)
        console.print(f"  [dim]Generated docker-compose.yaml in {env_dir}[/dim]")


def ensure_task_plugin(
    task_dir: Path,
    plugin: PluginConfig,
    docker: DockerConfig,
    has_source: bool,
) -> StagedPlugin:
    """Stage a local Claude Code plugin into the task's Docker build context.

    Mirrors ensure_task_environment for [nasde.source]. The plugin tree is
    copied (at ``plugin.ref`` via a temporary git worktree, when set) into a
    gitignored staging dir inside the *active* build context, and a plugin
    stage is appended to the Dockerfile so the image ``COPY``s it to
    ``install_root`` and runs the optional ``build`` command at build time.

    Build-context precedence (see ADR-009):

    - No [nasde.source] and no docker-compose: Harbor's context is
      ``environment/``. Plugin is staged at ``environment/_nasde-plugin/``;
      the Dockerfile (generated here if absent, else the hand-written one)
      gets a ``COPY _nasde-plugin/ <install_root>`` stage appended.
    - With [nasde.source]: ensure_task_environment already redirected the
      compose build context to the repo/worktree. The plugin is staged
      *inside that context* so the same relative ``COPY`` works.

    Returns a StagedPlugin describing the on-host copy and sandbox location,
    consumed by the runner to register skills + the MCP server.
    """
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)

    plugin_src = _resolve_plugin_source(task_dir, plugin)
    plugin_name = _read_plugin_name(plugin_src, fallback=plugin_src.name)
    install_root = plugin.install_root or f"/opt/{plugin_name}"

    context_dir = _plugin_build_context_dir(env_dir, has_source)
    staged_dir = context_dir / _PLUGIN_STAGE_DIR
    _stage_plugin_tree(plugin_src, staged_dir)

    if not has_source and not _dockerfile_has_real_content(env_dir):
        (env_dir / "Dockerfile").write_text(_generate_plugin_base_dockerfile(docker))
        console.print(f"  [dim]Generated Dockerfile in {env_dir}[/dim]")

    copy_src = os.path.relpath(staged_dir, context_dir)
    _append_plugin_stage(env_dir / "Dockerfile", copy_src, install_root, plugin.build)
    console.print(f"  [dim]Staged plugin '{plugin_name}' → {install_root} (build context: {context_dir})[/dim]")

    return StagedPlugin(
        staged_dir=staged_dir,
        install_root=install_root,
        plugin_name=plugin_name,
        env=dict(plugin.env),
    )


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


def create_ref_worktree(repo_dir: Path, ref: str) -> Path:
    """Public entry to create a temporary git worktree at ``ref``.

    Used by skill-by-reference (variant.toml ``[[skill]]``) to read a skill
    from a clean historical snapshot, same mechanism as [nasde.source].
    """
    return _create_ref_worktree(repo_dir, ref)


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


def _resolve_plugin_source(task_dir: Path, plugin: PluginConfig) -> Path:
    """Resolve the plugin directory on the host, at ``plugin.ref`` if set.

    Without a ref, uses the plugin path as-is (working tree). With a ref,
    creates a temporary git worktree of the repo containing the plugin and
    returns the plugin's path *inside* that worktree — so the staged copy
    is a clean historical snapshot, same semantics as [nasde.source].

    The plugin manifest (``.claude-plugin/plugin.json``) is validated against
    the *resolved* path — worktree-at-ref when set, working tree otherwise.
    This is what users expect from ``ref``: pin to a historical commit even
    if the working tree is mid-refactor and the plugin path is temporarily
    missing/renamed there.
    """
    plugin_abs = (task_dir / plugin.path).resolve()
    if not plugin_abs.exists():
        raise RuntimeError(f"[nasde.plugin] path does not exist: {plugin_abs}")

    if not plugin.ref:
        resolved = plugin_abs
    else:
        repo_root = _git_repo_root(plugin_abs)
        relative_in_repo = plugin_abs.relative_to(repo_root)
        worktree = _create_ref_worktree(repo_root, plugin.ref)
        resolved = worktree / relative_in_repo

    if not (resolved / ".claude-plugin" / "plugin.json").exists():
        raise RuntimeError(
            f"[nasde.plugin] '{resolved}' is not a Claude Code plugin (missing .claude-plugin/plugin.json)"
        )
    return resolved


def _git_repo_root(path: Path) -> Path:
    """Return the git toplevel of the repo containing ``path``."""
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"[nasde.plugin] '{path}' is not inside a git repo: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def _read_plugin_name(plugin_dir: Path, fallback: str) -> str:
    """Read the plugin's name from .claude-plugin/plugin.json."""
    import json

    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    with contextlib.suppress(OSError, json.JSONDecodeError):
        data = json.loads(manifest.read_text())
        name = data.get("name")
        if isinstance(name, str) and name:
            return name
    return fallback


def _plugin_build_context_dir(env_dir: Path, has_source: bool) -> Path:
    """Where to stage the plugin so the active Docker build context reaches it.

    With a *local* [nasde.source] the compose override moved the build context
    to the repo/worktree (recorded in environment/docker-compose.yaml); stage
    there. With a *remote* [nasde.source] no compose is generated (Harbor's
    default context = environment/ stands), so we stage in env_dir. Same for
    the no-source case.
    """
    if has_source and (env_dir / "docker-compose.yaml").exists():
        return _compose_context_dir(env_dir)
    return env_dir


def _compose_context_dir(env_dir: Path) -> Path:
    """Parse environment/docker-compose.yaml to recover the build context dir."""
    compose_path = env_dir / "docker-compose.yaml"
    for line in compose_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("context:"):
            relative = stripped.split("context:", 1)[1].strip()
            return (env_dir / relative).resolve()
    raise RuntimeError(f"No build context found in {compose_path}")


def _stage_plugin_tree(plugin_src: Path, staged_dir: Path) -> None:
    """Copy the plugin tree into the staging dir (fresh each run).

    node_modules/.git are skipped — the optional ``build`` command
    reinstalls deps inside the image; copying them bloats the context.
    """
    if staged_dir.exists():
        shutil.rmtree(staged_dir)
    staged_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        plugin_src,
        staged_dir,
        ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__", ".venv"),
    )


def _dockerfile_has_real_content(env_dir: Path) -> bool:
    """True if the Dockerfile has content other than a generated plugin stage.

    A hand-written or [nasde.source]-generated Dockerfile counts as real
    content and is preserved. A Dockerfile that contains *only* a previously
    generated plugin stage (a stale plugin-only run) does not — it is
    regenerated from a fresh base.
    """
    dockerfile = env_dir / "Dockerfile"
    if not dockerfile.exists():
        return False
    head = _strip_existing_plugin_stage(dockerfile.read_text())
    return any(line.strip() and not line.strip().startswith("#") for line in head.splitlines())


def _append_plugin_stage(
    dockerfile: Path,
    copy_src: str,
    install_root: str,
    build: str,
) -> None:
    """Append (or replace) the generated plugin stage in the Dockerfile.

    The stage is fenced by sentinel markers so re-runs replace it idempotently
    rather than appending duplicates. It is inserted before any trailing
    ``CMD``/``ENTRYPOINT`` so those remain the final instruction.

    ``install_root`` is shell-quoted in the ``RUN cd … && build`` line and the
    ``COPY`` line uses the JSON-array form, so an install_root containing
    spaces or shell-special characters does not silently mis-parse.
    """
    import shlex

    text = dockerfile.read_text() if dockerfile.exists() else ""
    text = _strip_existing_plugin_stage(text)

    quoted_root = shlex.quote(install_root)
    build_line = f"RUN cd {quoted_root} && {build}\n" if build else ""
    copy_dest = install_root.rstrip("/") + "/"
    copy_line = f"COPY [{json.dumps(copy_src + '/')}, {json.dumps(copy_dest)}]\n"
    stage = f"\n{_PLUGIN_STAGE_MARKER}\n{copy_line}{build_line}{_PLUGIN_STAGE_END}"

    head, tail = _split_before_trailing_cmd(text)
    dockerfile.write_text(head + stage + tail)


_PLUGIN_STAGE_END = "# <<< nasde plugin stage <<<\n"


def _strip_existing_plugin_stage(text: str) -> str:
    """Remove a previously generated plugin stage (between sentinel markers).

    If only the BEGIN sentinel is present (END was hand-deleted), refuse to
    strip — ``str.partition`` would otherwise return an empty ``after`` and
    silently truncate everything below the BEGIN marker. Raise instead.
    """
    if _PLUGIN_STAGE_MARKER not in text:
        return text
    if _PLUGIN_STAGE_END not in text:
        raise RuntimeError(
            "Dockerfile has the nasde plugin stage BEGIN sentinel but no END sentinel — "
            "refusing to rewrite to avoid silently truncating instructions below. "
            "Restore the END sentinel or remove the generated stage manually."
        )
    before, _, rest = text.partition(_PLUGIN_STAGE_MARKER)
    _, _, after = rest.partition(_PLUGIN_STAGE_END)
    return before.rstrip() + "\n" + after.lstrip("\n")


def _split_before_trailing_cmd(text: str) -> tuple[str, str]:
    """Split Dockerfile text so trailing CMD/ENTRYPOINT stay last."""
    lines = text.splitlines(keepends=True)
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("CMD ", "CMD[", "ENTRYPOINT ", "ENTRYPOINT[")):
            return "".join(lines[:i]), "".join(lines[i:])
        break
    return text, ""


def _generate_plugin_base_dockerfile(docker: DockerConfig) -> str:
    """Minimal base Dockerfile for a plugin-only task (no [nasde.source]).

    The plugin stage is appended separately by _append_plugin_stage.
    """
    build_steps = "\n".join(f"RUN {cmd}" for cmd in docker.build_commands)
    return dedent(f"""\
        FROM {docker.base_image}

        ENV PATH="/root/.local/bin:$PATH"

        RUN apt-get update && apt-get install -y \\
            git curl wget ca-certificates \\
            && rm -rf /var/lib/apt/lists/*

        WORKDIR /app

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
