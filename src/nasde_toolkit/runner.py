"""Benchmark runner — Harbor Python API.

Merges variant configuration with task registry, launches Harbor Job
directly via Python API, and triggers post-hoc assessment evaluation.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from rich.console import Console
from rich.table import Table

from nasde_toolkit.config import ProjectConfig

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
            variants.update(
                d.name for d in variants_parent.iterdir() if d.is_dir()
            )
    return sorted(variants)


async def run_benchmark(
    config: ProjectConfig,
    variant: str,
    model: str = "claude-sonnet-4-6",
    timeout_sec: int = 720,
    tasks_filter: list[str] | None = None,
    with_opik: bool = False,
    with_eval: bool = True,
    harbor_env: str | None = None,
    n_attempts: int = 1,
    job_suffix: str | None = None,
) -> None:
    """Run a benchmark variant against configured tasks via Harbor."""
    _load_env_file(config.project_dir)
    _ensure_auth()

    variant_dir = _resolve_variant_dir(config.project_dir, variant)
    harbor_config_path = variant_dir / "harbor_config.json"

    if not harbor_config_path.exists():
        _generate_harbor_config(variant_dir, variant)
        harbor_config_path = variant_dir / "harbor_config.json"

    merged_config = _build_merged_config(
        config=config,
        variant_config_path=harbor_config_path,
        variant_name=variant,
        model=model,
        timeout_sec=timeout_sec,
        tasks_filter=tasks_filter,
        harbor_env=harbor_env,
        n_attempts=n_attempts,
        job_suffix=job_suffix,
    )

    result = await _run_job(
        merged_config,
        with_opik=with_opik,
        project_name=config.reporting.project_name or config.name,
        project_dir=config.project_dir,
    )
    _print_job_summary(result)

    console.print("\n[bold green]Benchmark execution completed[/bold green]\n")

    if with_eval:
        job_dir = _resolve_jobs_dir(config.project_dir).resolve() / merged_config["job_name"]
        await _run_post_hoc_assessment(config, with_opik, job_dir=job_dir)


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def _ensure_auth() -> None:
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


def _resolve_variant_dir(project_dir: Path, variant: str) -> Path:
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
    skills_dir = variant_dir / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_dir.is_dir() and skill_md.exists():
                target = f"/app/.claude/skills/{skill_dir.name}/SKILL.md"
                sandbox_files[target] = str(skill_md)
    return sandbox_files


def _generate_harbor_config(variant_dir: Path, variant: str) -> None:
    sandbox_files = _collect_sandbox_files(variant_dir)

    config = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
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
            "tasks": [
                {"name": t.name, "path": str(t.path.resolve())}
                for t in tasks
            ],
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


async def _run_job(
    config_dict: dict,
    with_opik: bool,
    project_name: str,
    project_dir: Path | None = None,
) -> "JobResult":
    """Run a Harbor job via Python API.

    Args:
        config_dict: Merged Harbor config as a dict.
        with_opik: Enable Opik tracking.
        project_name: Opik project name.
        project_dir: Project directory to chdir into before running.
            Harbor resolves task paths and agent import_path relative to
            CWD, so we must be in the project directory.
    """
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
        return await job.run()
    finally:
        os.chdir(saved_cwd)


def _print_job_summary(result: "JobResult") -> None:
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
