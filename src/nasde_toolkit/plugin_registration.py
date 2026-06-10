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

For **Claude** both feed :func:`stage_skill_dir`, which expands a skill
directory into the flat ``{container_path: host_file}`` mapping
ConfigurableClaude uploads to ``/app/.claude/skills`` (Claude's cwd discovery
root). The plugin path additionally calls :func:`inject_mcp_server` to register
the plugin's MCP server in the task's Harbor config.

For **Codex/Gemini** the same skill *directories* are resolved by
:func:`collect_referenced_skill_dirs` / :func:`collect_plugin_skill_dirs` and
fed to Harbor's native ``config.agent.skills`` instead — those CLIs scan only a
HOME-scoped dir (``$HOME/.agents/skills``, ``~/.gemini/skills``), never the
``/app`` cwd the sandbox map targets. See ADR-012.
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


_SKILL_IGNORE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", ".gitignore", ".gitattributes"})
_SKILL_IGNORE_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv"})
_SKILL_IGNORE_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".bak", "~")


def stage_skill_dir(skill_dir: Path, sandbox_files: dict[str, str]) -> None:
    """Map every file under a skill dir into sandbox_files, preserving layout.

    Targets ``/app/.claude/skills/<skill-name>/<relative>`` for each regular
    file (ConfigurableClaude mirrors that to ``~/.claude/skills`` so Claude's
    auto-discovery picks it up). Unlike the legacy per-variant collector this
    carries ``references/`` and any other sibling files — some skills
    (e.g. analyze-conversation) read ``references/*.md`` at runtime.

    Filters OS junk (``.DS_Store``, ``Thumbs.db``), VCS data (``.git/``),
    Python/editor temp files (``__pycache__/``, ``.venv/``, ``*.pyc``, swap
    files, ``*~``, ``*.bak``) so live developer source dirs referenced via
    ``[[skill]]`` don't leak workstation state or ``.git/`` history into the
    sandbox. Mirrors the ignore list used by ``docker._stage_plugin_tree``.
    """
    skill_name = skill_dir.name
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if _should_ignore_skill_file(file_path.relative_to(skill_dir)):
            continue
        relative = file_path.relative_to(skill_dir).as_posix()
        target = f"/app/.claude/skills/{skill_name}/{relative}"
        sandbox_files[target] = str(file_path)


def _should_ignore_skill_file(relative: Path) -> bool:
    if any(part in _SKILL_IGNORE_DIRS for part in relative.parts):
        return True
    name = relative.name
    if name in _SKILL_IGNORE_NAMES:
        return True
    if name.startswith(".#"):
        return True
    return name.endswith(_SKILL_IGNORE_SUFFIXES)


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


def collect_referenced_skill_dirs(
    variant_dir: Path,
    worktree_factory: WorktreeFactory,
) -> list[Path]:
    """Resolve the ``[[skill]]`` array to a list of whole skill directories.

    Same resolution as :func:`stage_referenced_skills` (each entry's ``path``
    relative to the variant dir, optional ``ref`` read from a temporary git
    worktree) but returns the resolved *directories* instead of flattening them
    into a ``sandbox_files`` map under ``/app/.claude/skills``. Codex and Gemini
    auto-discover skills only from a HOME-scoped dir, never from the agent's
    ``/app`` cwd, so they take this dir list through Harbor's native
    ``config.agent.skills`` mechanism. Claude keeps using
    :func:`stage_referenced_skills`. See ADR-012.

    Paths are fully ``resolve()``d so they compare equal to the snapshot dirs
    from ``runner._collect_native_skill_dirs`` — the union/dedup, stale-drop and
    basename-collision logic in ``_refresh_agent_skills`` key on string equality,
    which would break on a symlinked ``/tmp`` (macOS) or a ``ref`` worktree path.
    """
    dirs: list[Path] = []
    for entry in _read_skill_entries(variant_dir):
        resolved = _resolve_skill_source(variant_dir, entry["path"], entry.get("ref", ""), worktree_factory)
        if not (resolved / "SKILL.md").exists():
            raise RuntimeError(f"[[skill]] '{resolved}' has no SKILL.md")
        dirs.append(resolved.resolve())
    return dirs


def collect_plugin_skill_dirs(staged: StagedPlugin) -> list[Path]:
    """Resolve a shipped plugin's own ``skills/`` to a list of skill dirs.

    The dir-list counterpart of :func:`register_plugin_skills`, for the same
    reason as :func:`collect_referenced_skill_dirs`: Codex/Gemini take these
    dirs through Harbor's native ``config.agent.skills`` rather than a
    cwd ``sandbox_files`` mapping. Paths are ``resolve()``d for the same
    string-equality reason as :func:`collect_referenced_skill_dirs`.
    """
    skills_root = staged.staged_dir / "skills"
    if not skills_root.is_dir():
        return []
    return [
        skill_dir.resolve()
        for skill_dir in sorted(skills_root.iterdir())
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    ]


def inject_mcp_server(task_dir: Path, staged: StagedPlugin) -> None:
    """Write the plugin's MCP servers into the task's task.toml.

    Harbor reads ``[environment.mcp_servers]`` only from each task's
    task.toml (``trial.py`` → ``self._task.config.environment.mcp_servers``),
    so that is the injection point. The block is fenced with sentinel
    comments: idempotent (re-runs replace it) and visibly generated.

    All servers declared in the plugin's ``.mcp.json`` are wired (not just the
    first — Claude Code plugins routinely ship multiple). Per-server ``env``
    declared in ``.mcp.json`` is honored. Precedence on env: nasde defaults →
    plugin's ``.mcp.json`` env → ``[nasde.plugin].env`` overrides.

    For each server, if the author already declares one with the same name in
    ``task.toml``, nasde respects the explicit declaration (logs + skips that
    one server, keeps wiring the rest).
    """
    task_toml = task_dir / "task.toml"
    original = task_toml.read_text()
    stripped = _strip_mcp_block(original)

    servers = _build_mcp_servers(staged)
    if not servers:
        task_toml.write_text(stripped)
        return

    new_servers = []
    for server in servers:
        if _author_declares_server(stripped, server["name"]):
            console.print(
                f"  [yellow]task.toml already declares MCP server '{server['name']}' — "
                "respecting the explicit declaration, skipping auto-registration[/yellow]"
            )
            continue
        new_servers.append(server)

    if not new_servers:
        task_toml.write_text(stripped)
        return

    block = _render_mcp_blocks(new_servers)
    task_toml.write_text(stripped.rstrip() + "\n\n" + block)
    names = ", ".join(s["name"] for s in new_servers)
    console.print(f"  [dim]Registered plugin MCP server(s) '{names}' in task.toml[/dim]")


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


def _build_mcp_servers(staged: StagedPlugin) -> list[dict]:
    """Derive stdio MCP server entries from the plugin's .mcp.json.

    Reads ``<plugin>/.mcp.json`` (Claude Code plugin convention) and wraps
    every declared server. For each, env is composed in this order so values
    closer to the user override those further from them:

    1. nasde defaults (``CLAUDE_PLUGIN_ROOT``, ``CLAUDE_PLUGIN_DATA``, …)
    2. ``spec.env`` from the plugin's own ``.mcp.json``
    3. ``[nasde.plugin].env`` from the benchmark's task.toml

    Returns one dict per server, ready for ``_render_mcp_blocks``.
    """
    mcp_json = staged.staged_dir / ".mcp.json"
    if not mcp_json.exists():
        return []
    try:
        servers = json.loads(mcp_json.read_text()).get("mcpServers", {})
    except (OSError, json.JSONDecodeError):
        return []
    if not servers:
        return []

    built: list[dict] = []
    for name, spec in servers.items():
        wrapped = _wrap_single_server(name, spec, staged)
        if wrapped is not None:
            built.append(wrapped)
    return built


def _wrap_single_server(name: str, spec: dict, staged: StagedPlugin) -> dict | None:
    inner_command = spec.get("command", "")
    inner_args = spec.get("args", [])
    if not inner_command:
        return None

    env = _default_mcp_env(staged)
    spec_env = spec.get("env", {})
    if isinstance(spec_env, dict):
        env.update({str(k): str(v) for k, v in spec_env.items()})
    env.update(staged.env)
    exports = " ".join(f"{k}={_shell_quote(v)}" for k, v in env.items())
    quoted_install_root = _shell_quote(staged.install_root)
    prefix = f"export {exports} && cd {quoted_install_root} && "

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
    """Remove the previously generated MCP block, fenced by sentinel markers.

    If only the BEGIN sentinel is present (END was hand-deleted, e.g. during a
    merge-conflict cleanup), refuse to strip — ``str.partition`` would silently
    return an empty ``after`` and the rewrite would truncate every section
    below the BEGIN sentinel (``[verifier]``, ``[agent]``, …). Raise instead so
    the user can restore the sentinel or remove the block manually.
    """
    if _MCP_BEGIN not in toml_text:
        return toml_text
    if _MCP_END not in toml_text:
        raise RuntimeError(
            "task.toml has the nasde MCP BEGIN sentinel but no END sentinel — "
            "refusing to rewrite to avoid silently truncating user-authored sections. "
            "Restore the END sentinel or remove the generated block manually."
        )
    before, _, rest = toml_text.partition(_MCP_BEGIN)
    _, _, after = rest.partition(_MCP_END)
    return before.rstrip() + "\n" + after.lstrip("\n")


def _render_mcp_blocks(servers: list[dict]) -> str:
    """Render one or more MCP server entries inside a single sentinel-fenced block."""
    rendered_servers = "\n".join(_render_single_mcp_server(s) for s in servers)
    return f"{_MCP_BEGIN}\n{rendered_servers}{_MCP_END}\n"


def _render_single_mcp_server(server: dict) -> str:
    args_lines = ",\n".join(f"  {json.dumps(a)}" for a in server["args"])
    return (
        "[[environment.mcp_servers]]\n"
        f"name = {json.dumps(server['name'])}\n"
        'transport = "stdio"\n'
        f"command = {json.dumps(server['command'])}\n"
        f"args = [\n{args_lines}\n]\n"
    )
