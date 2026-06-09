"""Benchmark runner — Harbor Python API.

Merges variant configuration with task registry, launches Harbor Job
directly via Python API, and triggers post-hoc assessment evaluation.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from rich.console import Console
from rich.table import Table

from nasde_toolkit.config import ProjectConfig
from nasde_toolkit.docker import (
    cleanup_worktrees,
    create_ref_worktree,
    ensure_task_environment,
    ensure_task_plugin,
)
from nasde_toolkit.plugin_registration import (
    inject_mcp_server,
    register_plugin_skills,
    stage_referenced_skills,
)
from nasde_toolkit.token_metrics import dominant_normalized_score

if TYPE_CHECKING:
    from harbor.models.job.result import JobResult

console = Console()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_available_variants(project_dir: Path) -> list[str]:
    """Discover all variant directories in a benchmark project."""
    variants: set[str] = set()
    for base in [project_dir / ".nasde", project_dir]:
        variants_parent = base / "variants"
        if variants_parent.exists():
            variants.update(d.name for d in variants_parent.iterdir() if d.is_dir())
    return sorted(variants)


async def run_benchmark(
    config: ProjectConfig,
    variant: str,
    model: str | None = None,
    effort: str | None = None,
    timeout_sec: int | None = None,
    tasks_filter: list[str] | None = None,
    with_opik: bool = False,
    with_eval: bool = True,
    harbor_env: str | None = None,
    n_attempts: int = 1,
    job_suffix: str | None = None,
    max_concurrent_eval: int = 10,
) -> None:
    """Run a benchmark variant against configured tasks via Harbor."""
    _load_env_file(config.project_dir)

    variant_dir = resolve_variant_dir(config.project_dir, variant)

    extra_sandbox_files = _prepare_task_environments(config, variant_dir)

    harbor_config_path = _ensure_harbor_config(variant_dir, variant, extra_sandbox_files)

    _ensure_auth(_read_agent_import_path(harbor_config_path))

    resolved_model = _resolve_model(model, variant_dir, config)
    resolved_effort = _resolve_effort(effort, variant_dir)

    merged_config = _build_merged_config(
        config=config,
        variant_config_path=harbor_config_path,
        variant_name=variant,
        model=resolved_model,
        reasoning_effort=resolved_effort,
        timeout_sec=timeout_sec,
        tasks_filter=tasks_filter,
        harbor_env=harbor_env,
        n_attempts=n_attempts,
        job_suffix=job_suffix,
    )

    if with_eval:
        os.environ.pop("CLAUDECODE", None)
        await _run_job_with_streaming_eval(
            config=config,
            merged_config=merged_config,
            with_opik=with_opik,
            harbor_env=harbor_env,
            max_concurrent_eval=max_concurrent_eval,
        )
    else:
        result = await _run_job(
            merged_config,
            with_opik=with_opik,
            project_name=config.reporting.project_name or config.name,
            project_dir=config.project_dir,
        )
        _print_job_summary(result, _job_dir_from_config(merged_config))
        console.print("\n[bold green]Benchmark execution completed[/bold green]\n")


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def _prepare_task_environments(config: ProjectConfig, variant_dir: Path) -> dict[str, str]:
    """Generate per-task Docker environments and collect agent skill files.

    Per task: auto-generate the source Dockerfile/compose ([nasde.source]),
    then stage the [nasde.plugin] tree into the build context, register the
    plugin's own skills, and inject its MCP server into the task's task.toml.
    Then add the variant's referenced [[skill]] dirs. Returns the extra
    ``{container_path: host_file}`` entries to merge into the variant's
    harbor_config.json sandbox_files.

    Plugin skills go to a single variant-wide ``/app/.claude/skills/`` path,
    so heterogeneous ``[nasde.plugin]`` across tasks in one project would
    silently contaminate every trial with the union of all plugins' skills.
    We fail fast on that, requiring all tasks that declare a plugin to
    declare the *same* one (path, ref, install_root). See ADR-009.
    """
    _require_homogeneous_plugins(config)

    extra_sandbox_files: dict[str, str] = {}

    for task in config.tasks:
        if task.source is not None:
            ensure_task_environment(task.path, task.source, config.docker)
        if task.plugin is not None:
            staged = ensure_task_plugin(
                task.path,
                task.plugin,
                config.docker,
                has_source=task.source is not None,
            )
            register_plugin_skills(staged, extra_sandbox_files)
            inject_mcp_server(task.path, staged)

    stage_referenced_skills(variant_dir, extra_sandbox_files, create_ref_worktree)
    return extra_sandbox_files


def _require_homogeneous_plugins(config: ProjectConfig) -> None:
    """Fail fast when tasks declare different [nasde.plugin]s.

    Plugin skills stage into a variant-wide sandbox_files dict — so two tasks
    with different plugins would silently see each other's skills. Until
    plugin skills are made task-scoped (Harbor-side change), enforce that
    every task declaring a plugin agrees on path/ref/install_root.
    """
    plugins_by_task = [(t.name, t.plugin) for t in config.tasks if t.plugin is not None]
    if len(plugins_by_task) < 2:
        return
    first_name, first = plugins_by_task[0]
    fingerprint = (first.path, first.ref, first.install_root)
    for name, plugin in plugins_by_task[1:]:
        other = (plugin.path, plugin.ref, plugin.install_root)
        if other != fingerprint:
            first_desc = f"path={first.path!r}, ref={first.ref!r}, install_root={first.install_root!r}"
            other_desc = f"path={plugin.path!r}, ref={plugin.ref!r}, install_root={plugin.install_root!r}"
            console.print(
                "[red]ERROR: tasks in this project declare different [nasde.plugin] entries.[/red]\n"
                f"  task '{first_name}': {first_desc}\n"
                f"  task '{name}': {other_desc}\n"
                "[red]Plugin skills register into a variant-wide sandbox; heterogeneous plugins would "
                "silently contaminate trials. Make all [nasde.plugin] declarations identical.[/red]"
            )
            raise SystemExit(1)


def _resolve_model(
    cli_model: str | None,
    variant_dir: Path,
    config: ProjectConfig,
) -> str:
    """Resolve model from CLI flag or variant.toml.

    Priority: --model flag > variant.toml model. Every variant must
    declare a ``model`` field; the model defines the agent's behavior
    and cannot meaningfully default across agent families (claude,
    codex, gemini). Raises SystemExit if no model is found.
    """
    if cli_model:
        return cli_model

    variant_data = load_variant_config(variant_dir)
    variant_model: str | None = variant_data.get("model")
    if variant_model:
        return variant_model

    console.print(
        f"[red]ERROR: No model specified. Set 'model' in {variant_dir / 'variant.toml'} "
        "or pass --model on the command line.[/red]"
    )
    raise SystemExit(1)


def _resolve_effort(cli_effort: str | None, variant_dir: Path) -> str | None:
    """Resolve the reasoning-effort override from CLI flag or variant.toml.

    Priority: --effort flag > variant.toml ``reasoning_effort`` > unset. Unset
    (None) means no override is passed to Harbor, which then applies its own
    per-family default — a deliberately valid state, so effort is optional.

    The value is NOT validated here: effort scales differ per model family and
    change often, so any non-empty value is passed straight to Harbor, which is
    the source of truth (Claude/Gemini reject unknown values via their own
    ``choices``; Codex takes a free-form string). A stale local allow-list would
    do more harm than good — wrongly blocking a newly-valid level.
    """
    effort = cli_effort or load_variant_config(variant_dir).get("reasoning_effort")
    return effort or None


def _ensure_auth(agent_import_path: str | None = None) -> None:
    if _is_codex_agent(agent_import_path):
        if not os.environ.get("OPENAI_API_KEY") and os.environ.get("CODEX_API_KEY"):
            os.environ["OPENAI_API_KEY"] = os.environ["CODEX_API_KEY"]
        if os.environ.get("OPENAI_API_KEY"):
            return
        if Path.home().joinpath(".codex", "auth.json").exists():
            _force_codex_oauth_auth_json()
            return
        console.print("[red]ERROR: Set CODEX_API_KEY, OPENAI_API_KEY, or run 'codex login' for OAuth[/red]")
        raise SystemExit(1)
    if _is_gemini_agent(agent_import_path):
        if (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or Path.home().joinpath(".gemini", "oauth_creds.json").exists()
        ):
            return
        console.print("[red]ERROR: Set GEMINI_API_KEY, GOOGLE_API_KEY, or run 'gemini login' for OAuth[/red]")
        raise SystemExit(1)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return
    console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
    raise SystemExit(1)


def _force_codex_oauth_auth_json() -> None:
    if os.environ.get("CODEX_AUTH_JSON_PATH") or os.environ.get("CODEX_FORCE_AUTH_JSON"):
        return
    os.environ["CODEX_FORCE_AUTH_JSON"] = "true"


def _validate_opik_env() -> None:
    missing = [v for v in ("OPIK_API_KEY", "OPIK_WORKSPACE") if not os.environ.get(v)]
    if missing:
        console.print(f"[red]ERROR: Missing Opik env vars: {', '.join(missing)}[/red]")
        console.print("[dim]Set them via .env or 'export OPIK_API_KEY=... OPIK_WORKSPACE=...'[/dim]")
        raise SystemExit(1)


def _load_env_file(project_dir: Path) -> None:
    for env_path in [project_dir / ".env", project_dir.parent / ".env"]:
        if env_path.exists():
            _parse_env_file(env_path)
            return


def _parse_env_file(env_path: Path) -> None:
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# ---------------------------------------------------------------------------
# Variant resolution
# ---------------------------------------------------------------------------


def resolve_variant_dir(project_dir: Path, variant: str) -> Path:
    for base in [project_dir / ".nasde", project_dir]:
        variant_dir = base / "variants" / variant
        if variant_dir.exists():
            return variant_dir

    available: list[str] = []
    for base in [project_dir / ".nasde", project_dir]:
        variants_parent = base / "variants"
        if variants_parent.exists():
            available.extend(d.name for d in variants_parent.iterdir() if d.is_dir())

    console.print(f"[red]ERROR: Variant '{variant}' not found.[/red]")
    if available:
        console.print("Available variants:")
        for v in sorted(set(available)):
            console.print(f"  {v}")
    raise SystemExit(1)


def _collect_sandbox_files(variant_dir: Path) -> dict[str, str]:
    sandbox_files: dict[str, str] = {}
    claude_md = variant_dir / "CLAUDE.md"
    if claude_md.exists():
        sandbox_files["/app/CLAUDE.md"] = str(claude_md)
    agents_md = variant_dir / "AGENTS.md"
    if agents_md.exists():
        sandbox_files["/app/AGENTS.md"] = str(agents_md)
    gemini_md = variant_dir / "GEMINI.md"
    if gemini_md.exists():
        sandbox_files["/app/GEMINI.md"] = str(gemini_md)
    _collect_claude_skills(variant_dir, sandbox_files)
    _collect_codex_skills(variant_dir, sandbox_files)
    _collect_gemini_skills(variant_dir, sandbox_files)
    claude_config = variant_dir / "claude_config.json"
    if claude_config.exists():
        sandbox_files["/logs/agent/sessions/.claude.json"] = str(claude_config)
    return sandbox_files


def _collect_claude_skills(variant_dir: Path, sandbox_files: dict[str, str]) -> None:
    """Map each variants/<v>/skills/<name>/ skill into sandbox_files.

    Carries the WHOLE skill dir (incl. ``references/`` and sibling files),
    not just ``SKILL.md`` — skills like analyze-conversation read
    ``references/*.md`` at runtime. Uses the shared staging helper so the
    copy-into-variants path and the ADR-009 by-reference path behave
    identically.
    """
    from nasde_toolkit.plugin_registration import stage_skill_dir

    skills_dir = variant_dir / "skills"
    if not skills_dir.is_dir():
        return
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            stage_skill_dir(skill_dir, sandbox_files)


def _collect_codex_skills(variant_dir: Path, sandbox_files: dict[str, str]) -> None:
    agents_skills_dir = variant_dir / "agents_skills"
    if not agents_skills_dir.is_dir():
        return
    for skill_dir in sorted(agents_skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(agents_skills_dir).as_posix()
                target = f"/app/.agents/skills/{relative}"
                sandbox_files[target] = str(file_path)


def _collect_gemini_skills(variant_dir: Path, sandbox_files: dict[str, str]) -> None:
    gemini_skills_dir = variant_dir / "gemini_skills"
    if not gemini_skills_dir.is_dir():
        return
    for skill_dir in sorted(gemini_skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(gemini_skills_dir).as_posix()
                target = f"/app/.gemini/skills/{relative}"
                sandbox_files[target] = str(file_path)


_VALID_AGENT_TYPES = {"claude", "codex", "gemini"}


def load_variant_config(variant_dir: Path) -> dict:
    """Read variant.toml and return its contents as a dict.

    Every variant directory must contain a ``variant.toml`` with at least
    an ``agent`` field set to ``"claude"`` or ``"codex"``.
    """
    variant_toml = variant_dir / "variant.toml"
    if not variant_toml.exists():
        console.print(
            f"[red]ERROR: {variant_toml} not found. Every variant must have a variant.toml with 'agent' field.[/red]"
        )
        raise SystemExit(1)

    import tomllib

    with open(variant_toml, "rb") as f:
        data = tomllib.load(f)

    agent_type: str = data.get("agent", "")
    if agent_type not in _VALID_AGENT_TYPES:
        console.print(
            f"[red]ERROR: variant.toml 'agent' must be one of {_VALID_AGENT_TYPES}, got: {agent_type!r}[/red]"
        )
        raise SystemExit(1)

    return data


def load_variant_agent_type(variant_dir: Path) -> str:
    """Read the agent type from variant.toml."""
    agent_type: str = load_variant_config(variant_dir)["agent"]
    return agent_type


def load_variant_task_scope(variant_dir: Path) -> list[str] | None:
    """Read the optional ``tasks`` task-scope list from variant.toml.

    A repo-specific variant (e.g. a skill whose examples reference one repo's
    conventions) declares the tasks it is meant to run against:

        tasks = ["csharp-anemic-to-rich-domain"]

    Returns the declared task names, or ``None`` when the variant is unscoped
    (applies to every task). An empty list is treated as unscoped.
    """
    scope = load_variant_config(variant_dir).get("tasks")
    if not scope:
        return None
    if not isinstance(scope, list) or not all(isinstance(t, str) for t in scope):
        console.print(f"[red]ERROR: variant.toml 'tasks' must be a list of task names, got: {scope!r}[/red]")
        raise SystemExit(1)
    return scope


def scope_tasks_for_variant(
    variant_dir: Path,
    task_names: list[str],
    explicit_tasks_filter: list[str] | None,
) -> list[str]:
    """Intersect a variant's task-scope with the run's task list.

    ``task_names`` are the tasks that would otherwise run (already narrowed by
    any ``--tasks`` filter). If the variant declares a ``tasks`` scope, keep
    only the tasks in that scope. An explicit ``--tasks`` filter that names a
    task outside the variant's scope is dropped (the scope wins) so that
    ``--all-variants`` never runs a repo-specific variant against the wrong repo.
    """
    scope = load_variant_task_scope(variant_dir)
    if scope is None:
        return task_names
    return [t for t in task_names if t in set(scope)]


def _agent_import_path(agent_type: str) -> str:
    if agent_type == "codex":
        return "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    if agent_type == "gemini":
        return "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    return "nasde_toolkit.agents.configurable_claude:ConfigurableClaude"


def _is_codex_agent(agent_import_path: str | None) -> bool:
    return bool(agent_import_path and "codex" in agent_import_path.lower())


def _is_gemini_agent(agent_import_path: str | None) -> bool:
    return bool(agent_import_path and "gemini" in agent_import_path.lower())


def _read_agent_import_path(harbor_config_path: Path) -> str | None:
    """Extract the first agent's import_path from a harbor_config.json."""
    try:
        with open(harbor_config_path) as f:
            data = json.load(f)
        agents = data.get("agents", [])
        if agents:
            result: str | None = agents[0].get("import_path")
            return result
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _ensure_harbor_config(
    variant_dir: Path,
    variant: str,
    extra_sandbox_files: dict[str, str],
) -> Path:
    """Generate harbor_config.json if absent, then refresh sandbox_files.

    ``sandbox_files`` is regenerated from scratch every run — authored block
    from ``_collect_sandbox_files(variant_dir)`` plus derived entries
    (``extra_sandbox_files``: plugin skills + variant ``[[skill]]`` dirs,
    ADR-009). This is unconditional so removed/renamed ``[[skill]]`` or
    ``[nasde.plugin]`` entries between runs do not linger as stale mappings
    pointing at now-deleted worktree paths.
    """
    harbor_config_path = variant_dir / "harbor_config.json"
    if not harbor_config_path.exists():
        _generate_harbor_config(variant_dir, variant)

    _refresh_sandbox_files(harbor_config_path, variant_dir, extra_sandbox_files)
    return harbor_config_path


def _generate_harbor_config(variant_dir: Path, variant: str) -> None:
    sandbox_files = _collect_sandbox_files(variant_dir)
    agent_type = load_variant_agent_type(variant_dir)
    import_path = _agent_import_path(agent_type)

    config = {
        "agents": [
            {
                "import_path": import_path,
                "name": variant,
                "kwargs": {
                    "sandbox_files": sandbox_files,
                },
                "_nasde_derived_keys": [],
            }
        ]
    }

    variant_dir.mkdir(parents=True, exist_ok=True)
    (variant_dir / "harbor_config.json").write_text(json.dumps(config, indent=2))
    console.print(f"[dim]Generated harbor_config.json in {variant_dir}[/dim]")


def _refresh_sandbox_files(
    harbor_config_path: Path,
    variant_dir: Path,
    extra: dict[str, str],
) -> None:
    """Rebuild each agent's sandbox_files, preserving hand-written entries.

    Three sources, in collision-precedence (right wins, so hand-written
    overrides everything):

    1. ``extra`` — derived this run from ``[nasde.plugin]`` + variant
       ``[[skill]]``. Tracked via ``_nasde_derived_keys`` meta on the agent.
    2. ``authored`` — what ``_collect_sandbox_files(variant_dir)`` produces
       from on-disk ``variant_dir`` files (``CLAUDE.md``, ``skills/``, …).
       Regenerated each run, so changes in ``variant_dir`` propagate.
    3. ``handwritten`` — keys previously in the file that were neither
       authored nor tracked-derived. The user put them there explicitly.

    Stale derived entries (a ``[[skill]]`` that was removed between runs)
    are dropped: the previous ``_nasde_derived_keys`` list says which keys
    nasde owns, so removing the entry from that list lets it disappear.
    Hand-written keys are never on the derived list and never removed.

    Collisions (a key reachable from two sources) are surfaced as warnings.
    The user's choice wins (hand-written) but the conflict is logged so the
    duplication doesn't become silent footgun.
    """
    config = json.loads(harbor_config_path.read_text())
    for agent in config.get("agents", []):
        _refresh_agent_sandbox_files(agent, variant_dir, extra)
    harbor_config_path.write_text(json.dumps(config, indent=2))


def _refresh_agent_sandbox_files(
    agent: dict,
    variant_dir: Path,
    extra: dict[str, str],
) -> None:
    kwargs = agent.setdefault("kwargs", {})
    current = kwargs.get("sandbox_files", {}) or {}
    prev_derived_keys = set(agent.get("_nasde_derived_keys", []) or [])
    authored = _collect_sandbox_files(variant_dir)

    handwritten = {k: v for k, v in current.items() if k not in prev_derived_keys and authored.get(k) != v}

    _warn_sandbox_collisions(
        agent_name=str(agent.get("name", "<unnamed>")),
        extra=extra,
        authored=authored,
        handwritten=handwritten,
    )

    kwargs["sandbox_files"] = {**extra, **authored, **handwritten}
    agent["_nasde_derived_keys"] = sorted(extra.keys())


def _warn_sandbox_collisions(
    agent_name: str,
    extra: dict[str, str],
    authored: dict[str, str],
    handwritten: dict[str, str],
) -> None:
    """Surface every sandbox_files key reachable from two sources.

    Hand-written wins on every collision (right-most in the merge). The
    warnings exist so a hand-written entry that *accidentally* masks a
    ``[[skill]]`` or a ``CLAUDE.md`` change does not silently degrade the
    benchmark. Each warning names both sides so the user can decide whether
    the override was intentional.
    """
    extra_keys = set(extra.keys())
    authored_keys = set(authored.keys())
    handwritten_keys = set(handwritten.keys())

    for key in sorted(handwritten_keys & extra_keys):
        console.print(
            f"[yellow]WARNING ({agent_name}): hand-written sandbox_files entry "
            f"collides with a derived entry — hand-written wins.\n"
            f"  container path : {key}\n"
            f"  hand-written   : {handwritten[key]}   (kept)\n"
            f"  derived (ignored): {extra[key]}\n"
            r"  → remove the hand-written entry from harbor_config.json if you did not "
            r"intend to override \[\[skill]]/\[nasde.plugin]."
            "[/yellow]"
        )
    for key in sorted(handwritten_keys & authored_keys):
        console.print(
            f"[yellow]WARNING ({agent_name}): hand-written sandbox_files entry collides "
            f"with a file collected from variants/ — hand-written wins.\n"
            f"  container path  : {key}\n"
            f"  hand-written    : {handwritten[key]}   (kept)\n"
            f"  variants/ source: {authored[key]}\n"
            f"  → remove the hand-written entry if you did not intend to override the "
            f"file in the variant directory.[/yellow]"
        )
    for key in sorted(extra_keys & authored_keys):
        console.print(
            f"[yellow]WARNING ({agent_name}): the same container path is produced by "
            r"both \[\[skill]]/\[nasde.plugin] AND a file in variants/ — the variant "
            "directory wins.\n"
            f"  container path: {key}\n"
            f"  variants/     : {authored[key]}   (kept)\n"
            f"  derived       : {extra[key]}   (ignored)\n"
            r"  → if you meant \[\[skill]] to win, delete the copy under "
            "variants/<v>/skills/.[/yellow]"
        )


# ---------------------------------------------------------------------------
# Config merging
# ---------------------------------------------------------------------------


def _build_merged_config(
    config: ProjectConfig,
    variant_config_path: Path,
    variant_name: str,
    model: str,
    timeout_sec: int | None,
    tasks_filter: list[str] | None,
    reasoning_effort: str | None = None,
    harbor_env: str | None = None,
    n_attempts: int = 1,
    job_suffix: str | None = None,
) -> dict:
    from datetime import datetime

    with open(variant_config_path) as f:
        variant = json.load(f)

    for agent in variant.get("agents", []):
        agent.setdefault("model_name", model)
        if timeout_sec is not None:
            agent.setdefault("override_timeout_sec", timeout_sec)
        if reasoning_effort is not None:
            agent.setdefault("kwargs", {})["reasoning_effort"] = reasoning_effort

    registry = _build_registry(config, tasks_filter)
    registry_path = _write_temp_json(registry, prefix="nasde-registry-")

    jobs_dir = _resolve_jobs_dir(config.project_dir).resolve()
    jobs_dir.mkdir(parents=True, exist_ok=True)

    suffix = job_suffix or uuid4().hex[:6]
    job_name = f"{datetime.now().strftime('%Y-%m-%d__%H-%M-%S')}__{variant_name}__{suffix}"

    merged = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_attempts": n_attempts,
        "agents": variant["agents"],
        "datasets": [
            {
                "name": config.name,
                "registry_path": registry_path,
            }
        ],
        "artifacts": [{"source": "/app", "destination": "workspace"}],
    }

    if harbor_env:
        merged["environment"] = {"type": harbor_env}

    return merged


def _build_registry(config: ProjectConfig, tasks_filter: list[str] | None) -> list[dict]:
    tasks = config.tasks
    if tasks_filter:
        allowed = set(tasks_filter)
        tasks = [t for t in tasks if t.name in allowed]

    return [
        {
            "name": config.name,
            "description": f"Benchmark: {config.name}",
            "version": config.version,
            "tasks": [{"name": t.name, "path": str(t.path.resolve())} for t in tasks],
        }
    ]


def _write_temp_json(data: object, prefix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix=prefix)
    with open(fd, "w") as f:
        json.dump(data, f, indent=2)
    return path


def _resolve_jobs_dir(project_dir: Path) -> Path:
    nasde_dir = project_dir / ".nasde"
    if nasde_dir.exists():
        return nasde_dir / "jobs"
    return project_dir / "jobs"


def _job_dir_from_config(merged_config: dict) -> Path | None:
    """Resolve this run's own job directory from the config it submitted.

    Harbor writes each job into ``jobs_dir / job_name`` — both stamped onto the
    merged config by ``_build_merged_config`` before the job starts. Reading
    them back is exact and race-free: it never depends on scanning ``jobs/``
    for the newest directory, which under concurrent runs can belong to a
    different, still-running job.
    """
    jobs_dir = merged_config.get("jobs_dir")
    job_name = merged_config.get("job_name")
    if not jobs_dir or not job_name:
        return None
    job_dir: Path = Path(jobs_dir) / job_name
    return job_dir


# ---------------------------------------------------------------------------
# Opik monkey-patch: deferred Step metrics (ADR-006)
# ---------------------------------------------------------------------------


def _patch_opik_deferred_metrics() -> None:
    """Fix opik Harbor integration: defer Step span creation until metrics assigned.

    opik's ``_patch_step_class`` reads ``self.metrics`` during ``Step.__init__``,
    but Harbor assigns metrics *after* construction (``step.metrics = m``).
    Result: every Opik span has ``usage=None`` and "Total tokens" is empty.

    This re-patches Step so that ``__init__`` only stashes the Opik trace context,
    and span creation is deferred to ``__setattr__`` when ``metrics`` is set.

    Origin: SDLC repo commit 66c2c11 (2026-03-09).
    Remove when: opik changelog mentions harbor token/metrics fix.
    """
    from typing import Any

    import opik
    from harbor.models.trajectories.step import Step
    from opik import datetime_helpers, id_helpers, opik_context

    if getattr(_patch_opik_deferred_metrics, "_applied", False):
        return

    def _build_usage_from_metrics(
        metrics: Any,
    ) -> tuple[dict[str, Any] | None, float | None]:
        if not metrics:
            return None, None
        usage: dict[str, Any] = {}
        if metrics.prompt_tokens is not None:
            usage["prompt_tokens"] = metrics.prompt_tokens
        if metrics.completion_tokens is not None:
            usage["completion_tokens"] = metrics.completion_tokens
        if metrics.prompt_tokens and metrics.completion_tokens:
            usage["total_tokens"] = metrics.prompt_tokens + metrics.completion_tokens
        if not usage:
            return None, None
        total_cost: float | None = getattr(metrics, "cost_usd", None)
        return usage, total_cost

    from opik.types import SpanType

    def _source_to_span_type(source: str) -> SpanType:
        return "llm" if source == "agent" else "general"

    def _create_span_for_step(step: Step) -> None:
        trace_data = getattr(step, "_opik_trace_data", None)
        if trace_data is None:
            return
        parent_span_id: str | None = getattr(step, "_opik_parent_span_id", None)
        try:
            client = opik.get_global_client()
            span_project_name: str = (
                getattr(trace_data, "project_name", None) or os.environ.get("OPIK_PROJECT_NAME") or "Default Project"
            )

            input_dict: dict[str, Any] = {}
            if step.message:
                input_dict["message"] = step.message
            if step.tool_calls:
                input_dict["tool_calls"] = [
                    {
                        "tool_call_id": tc.tool_call_id,
                        "function_name": tc.function_name,
                        "arguments": tc.arguments,
                    }
                    for tc in step.tool_calls
                ]

            output_dict: dict[str, Any] | None = None
            if step.observation and step.observation.results:
                output_dict = {"results": [{"content": r.content} for r in step.observation.results]}

            metadata: dict[str, Any] = {
                "source": step.source,
                "created_from": "harbor",
            }
            if step.reasoning_content:
                metadata["reasoning"] = step.reasoning_content

            usage, total_cost = _build_usage_from_metrics(step.metrics)

            client.__internal_api__span__(
                id=id_helpers.generate_id(),
                trace_id=trace_data.id,
                parent_span_id=parent_span_id,
                name=f"step_{step.step_id}",
                type=_source_to_span_type(step.source),
                start_time=datetime_helpers.parse_iso_timestamp(step.timestamp),
                input=input_dict if input_dict else None,
                output=output_dict,
                metadata=metadata,
                usage=usage,
                total_cost=total_cost,
                model=step.model_name if step.source == "agent" else None,
                tags=["harbor", step.source],
                project_name=span_project_name,
                provider="anthropic" if step.source == "agent" else None,
            )
            object.__setattr__(step, "_opik_span_emitted", True)
        except Exception:
            pass

    original_init = Step.__init__

    def patched_init(self: Step, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        trace_data = opik_context.get_current_trace_data()
        if trace_data is None:
            return

        parent_span = opik_context.get_current_span_data()
        parent_span_id = parent_span.id if parent_span else None

        object.__setattr__(self, "_opik_trace_data", trace_data)
        object.__setattr__(self, "_opik_parent_span_id", parent_span_id)
        object.__setattr__(self, "_opik_span_emitted", False)

        if self.metrics or self.source != "agent":
            _create_span_for_step(self)

    original_setattr = Step.__setattr__

    def patched_setattr(self: Step, name: str, value: Any) -> None:
        original_setattr(self, name, value)
        if name != "metrics" or value is None:
            return
        if getattr(self, "_opik_span_emitted", False):
            return
        _create_span_for_step(self)

    Step.__init__ = patched_init  # type: ignore[assignment]
    Step.__setattr__ = patched_setattr  # type: ignore[assignment]
    _patch_opik_deferred_metrics._applied = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------


async def _run_job_with_streaming_eval(
    config: ProjectConfig,
    merged_config: dict,
    with_opik: bool,
    harbor_env: str | None,
    max_concurrent_eval: int,
) -> None:
    """Run Harbor job with assessment eval starting per trial as they complete."""
    from nasde_toolkit.evaluator import evaluate_and_record_trial

    project_name = config.reporting.project_name or config.name
    eval_semaphore = asyncio.Semaphore(max_concurrent_eval)
    assessment_tasks: list[asyncio.Task] = []

    async def _on_trial_complete(event: object) -> None:
        trial_dir = Path(event.config.trials_dir) / event.config.trial_name  # type: ignore[attr-defined]
        task = asyncio.create_task(
            evaluate_and_record_trial(
                trial_dir=trial_dir,
                project_root=config.project_dir,
                project_name=project_name,
                with_opik=with_opik,
                semaphore=eval_semaphore,
                eval_config=config.evaluation,
            )
        )
        assessment_tasks.append(task)

    result = None
    try:
        result = await _run_job(
            merged_config,
            with_opik=with_opik,
            project_name=project_name,
            project_dir=config.project_dir,
            on_trial_ended=_on_trial_complete,
        )
    finally:
        if assessment_tasks:
            console.print(f"[dim]Waiting for {len(assessment_tasks)} assessment evaluation(s)...[/dim]")
            await asyncio.gather(*assessment_tasks, return_exceptions=True)
    _print_job_summary(result, _job_dir_from_config(merged_config))
    console.print("\n[bold green]Benchmark execution completed[/bold green]\n")


async def _run_job(
    config_dict: dict,
    with_opik: bool,
    project_name: str,
    project_dir: Path | None = None,
    on_trial_ended: Callable | None = None,
) -> JobResult:
    """Run a Harbor job via Python API."""
    from harbor.job import Job
    from harbor.models.job.config import JobConfig

    if with_opik:
        _validate_opik_env()
        from opik.integrations.harbor import track_harbor

        console.print("Opik tracking enabled\n")
        track_harbor(project_name=project_name)
        _patch_opik_deferred_metrics()

    saved_cwd = Path.cwd()
    if project_dir:
        os.chdir(project_dir)
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))

    try:
        job_config = JobConfig.model_validate(config_dict)
        job = await Job.create(job_config)
        if on_trial_ended:
            job.on_trial_ended(on_trial_ended)
        return await job.run()
    finally:
        cleanup_worktrees()
        os.chdir(saved_cwd)


def _print_job_summary(result: JobResult, job_dir: Path | None = None) -> None:
    console.print()
    console.print("[bold]Job completed[/bold]")
    console.print(f"  Trials: {result.stats.n_completed_trials}")
    console.print(f"  Errors: {result.stats.n_errored_trials}")

    if job_dir is not None:
        rows = _collect_economics_rows(job_dir)
        if rows:
            _print_economics_table(rows)
            _print_label_legend(rows)
            _print_location_hints(job_dir)
        elif result.stats.evals:
            _warn_missing_economics(job_dir)
            _print_eval_counts_table(result)
    elif result.stats.evals:
        _print_eval_counts_table(result)
    console.print()


def _warn_missing_economics(job_dir: Path) -> None:
    console.print(
        f"[yellow]WARN: no assessment_summary.json found under {job_dir} — "
        "cost table skipped. Did assessment evaluation complete? "
        f"Re-run with [bold]nasde eval {job_dir}[/bold].[/yellow]"
    )


def _print_economics_table(rows: list[dict]) -> None:
    table = Table(title="Results by agent/model/effort (per-trial averages)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Agent / Model", style="cyan")
    table.add_column("Effort", justify="left")
    table.add_column("Trials", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("$ Cost", justify="right")
    for index, row in enumerate(rows, start=1):
        table.add_row(
            f"[{index}]",
            row["short_label"],
            row["reasoning_effort"] or "—",
            str(row["trials"]),
            _fmt_score(row["score"], row["score_std"], row["trials"]),
            _fmt_tokens(row["tokens"], row["tokens_std"]),
            _fmt_cost(row["cost"], row["cost_std"]),
        )
    console.print(table)


def _print_label_legend(rows: list[dict]) -> None:
    if all(row["short_label"] == row["full_label"] for row in rows):
        return
    console.print("[dim]Legend:[/dim]")
    for index, row in enumerate(rows, start=1):
        console.print(f"[dim]  [{index}] {row['full_label']}[/dim]")


def _print_location_hints(job_dir: Path) -> None:
    console.print(
        "[dim]Score = mean ±std across trials (agent noise). Per-trial judge-noise std + eval n in metrics.json.[/dim]"
    )
    console.print(f"[dim]→ Job: {job_dir}[/dim]")
    console.print(f"[dim]→ Export: uv run nasde results-export {job_dir} --to <dir>[/dim]")


def _print_eval_counts_table(result: JobResult) -> None:
    table = Table(title="Results by agent/dataset")
    table.add_column("Agent / Dataset", style="cyan")
    table.add_column("Trials", justify="right")
    table.add_column("Errors", justify="right")
    for eval_key, stats in result.stats.evals.items():
        table.add_row(eval_key, str(stats.n_trials), str(stats.n_errors))
    console.print(table)


def _collect_economics_rows(job_dir: Path) -> list[dict]:
    from nasde_toolkit.evaluator import _collect_trial_dirs

    groups: dict[tuple[str, str, str], dict] = {}
    for trial_dir in _collect_trial_dirs(job_dir):
        summary_path = trial_dir / "assessment_summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text())
        _accumulate_economics(groups, summary)
    return [_finalize_economics_row(label, agg) for label, agg in sorted(groups.items())]


def _accumulate_economics(groups: dict[tuple[str, str, str], dict], summary: dict) -> None:
    key = (summary.get("agent_name", ""), summary.get("model_name", ""), summary.get("reasoning_effort", ""))
    agg = groups.setdefault(key, {"trials": 0, "scores": [], "tokens": [], "costs": []})
    agg["trials"] += 1
    score = dominant_normalized_score(summary.get("groups", []))
    if score is not None:
        agg["scores"].append(score)
    usage = summary.get("token_usage")
    if usage:
        agg["tokens"].append(usage.get("total_tokens", 0))
    if summary.get("cost_usd") is not None:
        agg["costs"].append(summary["cost_usd"])


def _finalize_economics_row(label: tuple[str, str, str], agg: dict) -> dict:
    agent, model, effort = label
    return {
        "full_label": f"{agent} / {model}" if model else agent,
        "short_label": _short_label(agent, model),
        "reasoning_effort": effort,
        "trials": agg["trials"],
        "score": _mean(agg["scores"]),
        "score_std": _sample_std(agg["scores"]),
        "tokens": _mean(agg["tokens"]),
        "tokens_std": _sample_std(agg["tokens"]),
        "cost": _mean(agg["costs"]),
        "cost_std": _sample_std(agg["costs"]),
    }


def _short_label(agent: str, model: str) -> str:
    short_agent = agent.removeprefix("claude-").removeprefix("codex-").removeprefix("gemini-")
    short_agent = short_agent.replace("ntcoding-tactical-ddd-", "").replace("ntcoding-tactical-ddd", "tactical-ddd")
    short_model = model.removeprefix("claude-").removeprefix("google/")
    return f"{short_agent} / {short_model}" if short_model else short_agent


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _sample_std(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def _fmt_score(mean: float | None, std: float | None, n: int) -> str:
    if mean is None:
        return "—"
    if n < 2 or std is None:
        return f"{mean:.2f} (n=1)" if n == 1 else f"{mean:.2f}"
    return f"{mean:.2f} ±{std:.2f}"


def _fmt_cost(mean: float | None, std: float | None) -> str:
    if mean is None:
        return "—"
    if std is None:
        return f"${mean:.2f}"
    return f"${mean:.2f} ±{std:.2f}"


def _fmt_tokens(mean: float | None, std: float | None = None) -> str:
    if not mean:
        return "—"
    formatted = _scale_tokens(mean)
    if std is None:
        return formatted
    return f"{formatted} ±{_scale_tokens(std)}"


def _scale_tokens(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return str(int(value))
