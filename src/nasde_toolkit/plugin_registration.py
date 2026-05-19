"""Shared skill + MCP registration machinery (ADR-009).

Two nasde features need to put a *whole skill directory* (not just
``SKILL.md`` — ``references/`` and any sibling files too) where the Claude
Code agent discovers it, and one of them also needs to wire an MCP server:

1. ``[nasde.plugin]`` in task.toml ships a local Claude Code plugin into the
   sandbox image. A baked-not-installed plugin's ``skills/`` is not
   auto-discovered by ``claude`` and its ``.mcp.json`` is not honored, so
   nasde must register both explicitly.
2. The ``[[skill]]`` array in variant.toml references a skill from a source
   path instead of copying it into ``variants/<v>/skills/``.

Both feed :func:`stage_skill_dir`, which expands a skill directory into the
flat ``{container_path: host_file}`` mapping ConfigurableClaude uploads
(it only uploads regular files, mirroring ``_collect_codex_skills``). The
plugin path additionally calls :func:`inject_mcp_server` to register the
plugin's MCP server in the task's Harbor config.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from nasde_toolkit.docker import StagedPlugin

WorktreeFactory = Callable[[Path, str], Path]

console = Console()

_MCP_BEGIN = "# >>> nasde plugin MCP server (generated — do not edit) >>>"
_MCP_END = "# <<< nasde plugin MCP server <<<"


def stage_skill_dir(skill_dir: Path, sandbox_files: dict[str, str]) -> None:
    """Map every file under a skill dir into sandbox_files, preserving layout.

    Targets ``/app/.claude/skills/<skill-name>/<relative>`` for each regular
    file (ConfigurableClaude mirrors that to ``~/.claude/skills`` so Claude's
    auto-discovery picks it up). Unlike the legacy per-variant collector this
    carries ``references/`` and any other sibling files — some skills
    (e.g. analyze-conversation) read ``references/*.md`` at runtime.
    """
    skill_name = skill_dir.name
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(skill_dir).as_posix()
        target = f"/app/.claude/skills/{skill_name}/{relative}"
        sandbox_files[target] = str(file_path)


def register_plugin_skills(staged: StagedPlugin, sandbox_files: dict[str, str]) -> None:
    """Register a shipped plugin's own ``skills/`` for the agent.

    A plugin COPYed into the image (not ``claude plugin install``ed) has its
    skills invisible to auto-discovery. Each ``<plugin>/skills/<name>/`` is
    staged whole (incl. ``references/``) into the agent's skills location,
    using the on-host staged copy as the upload source.
    """
    skills_root = staged.staged_dir / "skills"
    if not skills_root.is_dir():
        return
    for skill_dir in sorted(skills_root.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            stage_skill_dir(skill_dir, sandbox_files)
            console.print(f"  [dim]Registered plugin skill '{skill_dir.name}'[/dim]")


def stage_referenced_skills(
    variant_dir: Path,
    sandbox_files: dict[str, str],
    worktree_factory: WorktreeFactory,
) -> None:
    """Stage skills referenced by the ``[[skill]]`` array in variant.toml.

    Each entry: ``path`` (relative to the variant dir) and optional ``ref``.
    With a ref, the skill is read from a temporary git worktree at that
    commit (``worktree_factory`` is :func:`nasde_toolkit.docker` worktree
    creator, injected to avoid a hard import cycle). The *whole* skill dir
    is staged — the existing ``variants/<v>/skills/`` copy path is untouched.
    """
    for entry in _read_skill_entries(variant_dir):
        skill_path = entry["path"]
        ref = entry.get("ref", "")
        resolved = _resolve_skill_source(variant_dir, skill_path, ref, worktree_factory)
        if not (resolved / "SKILL.md").exists():
            raise RuntimeError(f"[[skill]] '{resolved}' has no SKILL.md")
        stage_skill_dir(resolved, sandbox_files)
        console.print(f"  [dim]Registered referenced skill '{resolved.name}'[/dim]")


def inject_mcp_server(task_dir: Path, staged: StagedPlugin) -> None:
    """Write the plugin's MCP server into the task's task.toml.

    Harbor reads ``[environment.mcp_servers]`` only from each task's
    task.toml (``trial.py`` → ``self._task.config.environment.mcp_servers``),
    so that is the injection point. The block is fenced with sentinel
    comments: idempotent (re-runs replace it) and visibly generated. If the
    author already declares a server with the plugin's name, nasde leaves
    task.toml untouched and respects the explicit declaration.

    The stdio command wraps the plugin's server with the env the
    baked-not-installed plugin needs (the CC plugin loader does NOT inject
    ``CLAUDE_PLUGIN_ROOT`` etc. for a COPYed plugin). Env is taken from
    ``[nasde.plugin].env`` plus sensible defaults derived from the plugin's
    ``.mcp.json`` command.
    """
    task_toml = task_dir / "task.toml"
    original = task_toml.read_text()
    stripped = _strip_mcp_block(original)

    server = _build_mcp_server(staged)
    if server is None:
        task_toml.write_text(stripped)
        return

    if _author_declares_server(stripped, server["name"]):
        console.print(
            f"  [yellow]task.toml already declares MCP server '{server['name']}' — "
            "respecting the explicit declaration, skipping auto-registration[/yellow]"
        )
        task_toml.write_text(stripped)
        return

    block = _render_mcp_block(server)
    task_toml.write_text(stripped.rstrip() + "\n\n" + block)
    console.print(f"  [dim]Registered plugin MCP server '{server['name']}' in task.toml[/dim]")


def _read_skill_entries(variant_dir: Path) -> list[dict]:
    variant_toml = variant_dir / "variant.toml"
    if not variant_toml.exists():
        return []
    with open(variant_toml, "rb") as f:
        data = tomllib.load(f)
    entries = data.get("skill", [])
    if not isinstance(entries, list):
        raise RuntimeError(f"{variant_toml}: [[skill]] must be an array of tables")
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("path"):
            raise RuntimeError(f"{variant_toml}: every [[skill]] needs a 'path'")
    return entries


def _resolve_skill_source(
    variant_dir: Path,
    skill_path: str,
    ref: str,
    worktree_factory: WorktreeFactory,
) -> Path:
    skill_abs = (variant_dir / skill_path).resolve()
    if not skill_abs.exists():
        raise RuntimeError(f"[[skill]] path does not exist: {skill_abs}")
    if not ref:
        return skill_abs
    repo_root, relative = _git_repo_root_and_rel(skill_abs)
    worktree = worktree_factory(repo_root, ref)
    return worktree / relative


def _git_repo_root_and_rel(path: Path) -> tuple[Path, Path]:
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"[[skill]] '{path}' is not inside a git repo: {result.stderr.strip()}")
    repo_root = Path(result.stdout.strip())
    return repo_root, path.relative_to(repo_root)


def _build_mcp_server(staged: StagedPlugin) -> dict | None:
    """Derive a stdio MCP server entry from the plugin's .mcp.json.

    Reads ``<plugin>/.mcp.json`` (Claude Code plugin convention). The first
    server is wrapped so the configured env (CLAUDE_PLUGIN_ROOT etc.) is
    exported before the plugin's own command runs inside the container.
    """
    mcp_json = staged.staged_dir / ".mcp.json"
    if not mcp_json.exists():
        return None
    try:
        servers = json.loads(mcp_json.read_text()).get("mcpServers", {})
    except (OSError, json.JSONDecodeError):
        return None
    if not servers:
        return None

    name, spec = next(iter(servers.items()))
    inner_command = spec.get("command", "")
    inner_args = spec.get("args", [])
    if not inner_command:
        return None

    env = _default_mcp_env(staged)
    env.update(staged.env)
    exports = " ".join(f"{k}={_shell_quote(v)}" for k, v in env.items())
    prefix = f"export {exports} && cd {staged.install_root} && "

    if inner_command == "sh" and len(inner_args) == 2 and inner_args[0] == "-c":
        script = prefix + inner_args[1]
    else:
        import shlex

        script = prefix + "exec " + shlex.join([inner_command, *inner_args])
    return {"name": name, "command": "sh", "args": ["-c", script]}


def _default_mcp_env(staged: StagedPlugin) -> dict[str, str]:
    """Defaults for a baked-not-installed plugin's MCP server.

    ``CLAUDE_PLUGIN_ROOT`` points at the install root; ``CLAUDE_PLUGIN_DATA``
    at a sibling data dir; the project dir defaults to ``/app`` (Harbor's
    workspace). Anything explicit in ``[nasde.plugin].env`` overrides these.
    """
    return {
        "CLAUDE_PLUGIN_ROOT": staged.install_root,
        "CLAUDE_PLUGIN_DATA": f"{staged.install_root.rstrip('/')}-data",
        "CLAUDE_PROJECT_DIR": "/app",
    }


def _shell_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def _author_declares_server(toml_text: str, name: str) -> bool:
    try:
        data = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError:
        return False
    servers = data.get("environment", {}).get("mcp_servers", [])
    return any(isinstance(s, dict) and s.get("name") == name for s in servers)


def _strip_mcp_block(toml_text: str) -> str:
    if _MCP_BEGIN not in toml_text:
        return toml_text
    before, _, rest = toml_text.partition(_MCP_BEGIN)
    _, _, after = rest.partition(_MCP_END)
    return before.rstrip() + "\n" + after.lstrip("\n")


def _render_mcp_block(server: dict) -> str:
    args_lines = ",\n".join(f"  {json.dumps(a)}" for a in server["args"])
    return (
        f"{_MCP_BEGIN}\n"
        "[[environment.mcp_servers]]\n"
        f"name = {json.dumps(server['name'])}\n"
        'transport = "stdio"\n'
        f"command = {json.dumps(server['command'])}\n"
        f"args = [\n{args_lines}\n]\n"
        f"{_MCP_END}\n"
    )
