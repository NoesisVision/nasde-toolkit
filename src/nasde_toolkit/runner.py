"""Benchmark runner — Harbor Python API.

Merges variant configuration with task registry, launches Harbor Job
directly via Python API, and triggers post-hoc assessment evaluation.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from rich.console import Console
from rich.table import Table

from nasde_toolkit.config import ProjectConfig
from nasde_toolkit.docker import cleanup_worktrees, ensure_task_environment

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
    timeout_sec: int = 720,
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
    harbor_config_path = variant_dir / "harbor_config.json"

    if not harbor_config_path.exists():
        _generate_harbor_config(variant_dir, variant)
        harbor_config_path = variant_dir / "harbor_config.json"

    _ensure_auth(_read_agent_import_path(harbor_config_path))

    resolved_model = _resolve_model(model, variant_dir, config)

    for task in config.tasks:
        ensure_task_environment(task.path, task.source, config.docker)

    merged_config = _build_merged_config(
        config=config,
        variant_config_path=harbor_config_path,
        variant_name=variant,
        model=resolved_model,
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
        _print_job_summary(result)
        console.print("\n[bold green]Benchmark execution completed[/bold green]\n")


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def _resolve_model(
    cli_model: str | None,
    variant_dir: Path,
    config: ProjectConfig,
) -> str:
    """Resolve model from CLI flag, variant.toml, or nasde.toml.

    Priority: --model flag > variant.toml model > nasde.toml [defaults] model.
    Raises SystemExit if no model is found at any level.
    """
    if cli_model:
        return cli_model

    variant_data = load_variant_config(variant_dir)
    variant_model: str | None = variant_data.get("model")
    if variant_model:
        return variant_model

    if config.default_model:
        return config.default_model

    console.print(
        "[red]ERROR: No model specified. Set model via --model flag, "
        "variant.toml 'model' field, or nasde.toml [defaults] model.[/red]"
    )
    raise SystemExit(1)


def _ensure_auth(agent_import_path: str | None = None) -> None:
    if _is_codex_agent(agent_import_path):
        if (
            os.environ.get("CODEX_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or Path.home().joinpath(".codex", "auth.json").exists()
        ):
            return
        console.print("[red]ERROR: Set CODEX_API_KEY, OPENAI_API_KEY, or run 'codex login' for OAuth[/red]")
        raise SystemExit(1)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return
    console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
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
    _collect_claude_skills(variant_dir, sandbox_files)
    _collect_codex_skills(variant_dir, sandbox_files)
    return sandbox_files


def _collect_claude_skills(variant_dir: Path, sandbox_files: dict[str, str]) -> None:
    skills_dir = variant_dir / "skills"
    if not skills_dir.is_dir():
        return
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_dir.is_dir() and skill_md.exists():
            target = f"/app/.claude/skills/{skill_dir.name}/SKILL.md"
            sandbox_files[target] = str(skill_md)


def _collect_codex_skills(variant_dir: Path, sandbox_files: dict[str, str]) -> None:
    agents_skills_dir = variant_dir / "agents_skills"
    if not agents_skills_dir.is_dir():
        return
    for skill_dir in sorted(agents_skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(agents_skills_dir)
                target = f"/app/.agents/skills/{relative}"
                sandbox_files[target] = str(file_path)


_VALID_AGENT_TYPES = {"claude", "codex"}


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


def _agent_import_path(agent_type: str) -> str:
    if agent_type == "codex":
        return "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    return "nasde_toolkit.agents.configurable_claude:ConfigurableClaude"


def _is_codex_agent(agent_import_path: str | None) -> bool:
    return bool(agent_import_path and "codex" in agent_import_path.lower())


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
            }
        ]
    }

    variant_dir.mkdir(parents=True, exist_ok=True)
    (variant_dir / "harbor_config.json").write_text(json.dumps(config, indent=2))
    console.print(f"[dim]Generated harbor_config.json in {variant_dir}[/dim]")


# ---------------------------------------------------------------------------
# Config merging
# ---------------------------------------------------------------------------


def _build_merged_config(
    config: ProjectConfig,
    variant_config_path: Path,
    variant_name: str,
    model: str,
    timeout_sec: int,
    tasks_filter: list[str] | None,
    harbor_env: str | None = None,
    n_attempts: int = 1,
    job_suffix: str | None = None,
) -> dict:
    from datetime import datetime

    with open(variant_config_path) as f:
        variant = json.load(f)

    for agent in variant.get("agents", []):
        agent.setdefault("model_name", model)
        agent.setdefault("override_timeout_sec", timeout_sec)

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
                "registry": {"path": registry_path},
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

    try:
        result = await _run_job(
            merged_config,
            with_opik=with_opik,
            project_name=project_name,
            project_dir=config.project_dir,
            on_trial_ended=_on_trial_complete,
        )
        _print_job_summary(result)
        console.print("\n[bold green]Benchmark execution completed[/bold green]\n")
    finally:
        if assessment_tasks:
            console.print(f"[dim]Waiting for {len(assessment_tasks)} assessment evaluation(s)...[/dim]")
            await asyncio.gather(*assessment_tasks, return_exceptions=True)


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
        from opik.integrations.harbor import track_harbor

        console.print("Opik tracking enabled\n")
        track_harbor(project_name=project_name)

    saved_cwd = Path.cwd()
    if project_dir:
        os.chdir(project_dir)
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))

    try:
        job_config = JobConfig.model_validate(config_dict)
        job = Job(job_config)
        if on_trial_ended:
            job.on_trial_ended(on_trial_ended)
        return await job.run()
    finally:
        cleanup_worktrees()
        os.chdir(saved_cwd)


def _print_job_summary(result: JobResult) -> None:
    console.print()
    console.print("[bold]Job completed[/bold]")
    console.print(f"  Trials: {result.stats.n_trials}")
    console.print(f"  Errors: {result.stats.n_errors}")

    table = Table(title="Results by agent/dataset")
    table.add_column("Agent / Dataset", style="cyan")
    table.add_column("Trials", justify="right")
    table.add_column("Errors", justify="right")

    for eval_key, stats in result.stats.evals.items():
        table.add_row(
            eval_key,
            str(stats.n_trials),
            str(stats.n_errors),
        )

    if result.stats.evals:
        console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Post-hoc assessment
# ---------------------------------------------------------------------------


async def _run_post_hoc_assessment(
    config: ProjectConfig,
    with_opik: bool,
    job_dir: Path | None = None,
    max_concurrent_eval: int = 10,
) -> None:
    target_job = job_dir or _find_latest_job(config.project_dir)
    if not target_job:
        console.print("[yellow]WARN: No job directory found for assessment[/yellow]")
        return

    console.print("\n[bold]Running assessment evaluation...[/bold]\n")

    os.environ.pop("CLAUDECODE", None)

    from nasde_toolkit.evaluator import evaluate_job

    await evaluate_job(
        job_dir=target_job,
        project_root=config.project_dir,
        project_name=config.reporting.project_name,
        with_opik=with_opik,
        max_concurrent=max_concurrent_eval,
        eval_config=config.evaluation,
    )


def _find_latest_job(project_dir: Path) -> Path | None:
    jobs_dir = _resolve_jobs_dir(project_dir)
    if not jobs_dir.exists():
        return None

    job_dirs = sorted(
        [d for d in jobs_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    return job_dirs[0] if job_dirs else None
