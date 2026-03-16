"""Benchmark runner — Harbor wrapper.

Merges variant configuration with task registry, launches Harbor via
subprocess, and optionally triggers post-hoc assessment evaluation.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from sdlc_eval_kit.config import ProjectConfig

console = Console()


def run_benchmark(
    config: ProjectConfig,
    variant: str,
    model: str = "claude-sonnet-4-6",
    timeout_sec: int = 720,
    tasks_filter: list[str] | None = None,
    with_opik: bool = False,
    with_eval: bool = False,
) -> None:
    """Run a benchmark variant against configured tasks via Harbor."""
    _ensure_harbor_installed()
    _load_env_file(config.project_dir)
    _ensure_auth()

    variant_dir = _resolve_variant_dir(config.project_dir, variant)
    harbor_config_path = variant_dir / "harbor_config.json"

    if not harbor_config_path.exists():
        _generate_harbor_config(variant_dir, variant)
        harbor_config_path = variant_dir / "harbor_config.json"

    merged_config_path = _build_merged_config(
        config=config,
        variant_config_path=harbor_config_path,
        model=model,
        timeout_sec=timeout_sec,
        tasks_filter=tasks_filter,
    )

    try:
        _run_harbor(merged_config_path, with_opik)
    finally:
        merged_config_path.unlink(missing_ok=True)

    console.print("\n[bold green]Benchmark execution completed[/bold green]\n")

    if with_eval:
        _run_post_hoc_assessment(config, with_opik)


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def _ensure_auth() -> None:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return
    console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
    raise SystemExit(1)


def _ensure_harbor_installed() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import harbor"],
        capture_output=True,
    )
    if result.returncode != 0:
        console.print("[red]ERROR: Harbor is not installed.[/red]")
        console.print("  pip install harbor-ai")
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
            os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Variant resolution
# ---------------------------------------------------------------------------


def _resolve_variant_dir(project_dir: Path, variant: str) -> Path:
    for base in [project_dir / ".sdlc-eval", project_dir]:
        variant_dir = base / "variants" / variant
        if variant_dir.exists():
            return variant_dir

    available: list[str] = []
    for base in [project_dir / ".sdlc-eval", project_dir]:
        variants_parent = base / "variants"
        if variants_parent.exists():
            available.extend(d.name for d in variants_parent.iterdir() if d.is_dir())

    console.print(f"[red]ERROR: Variant '{variant}' not found.[/red]")
    if available:
        console.print("Available variants:")
        for v in sorted(set(available)):
            console.print(f"  {v}")
    raise SystemExit(1)


def _generate_harbor_config(variant_dir: Path, variant: str) -> None:
    claude_md = variant_dir / "CLAUDE.md"
    sandbox_files: dict[str, str] = {}
    if claude_md.exists():
        sandbox_files["/app/CLAUDE.md"] = str(claude_md)

    config = {
        "agents": [
            {
                "import_path": "sdlc_eval_kit.agents.configurable_claude:ConfigurableClaude",
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
    model: str,
    timeout_sec: int,
    tasks_filter: list[str] | None,
) -> Path:
    with open(variant_config_path) as f:
        variant = json.load(f)

    for agent in variant.get("agents", []):
        agent.setdefault("model_name", model)
        agent.setdefault("override_timeout_sec", timeout_sec)

    registry = _build_registry(config, tasks_filter)
    registry_path = _write_temp_json(registry, prefix="sdlc-eval-registry-")

    jobs_dir = _resolve_jobs_dir(config.project_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    merged = {
        "jobs_dir": str(jobs_dir),
        "n_attempts": 1,
        "agents": variant["agents"],
        "datasets": [
            {
                "name": config.name,
                "registry": {"path": registry_path},
            }
        ],
        "artifacts": [{"source": "/app/src", "destination": "workspace"}],
    }

    return Path(_write_temp_json(merged, prefix="sdlc-eval-config-"))


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
                {"name": t.name, "path": str(t.path)}
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
    sdlc_eval_dir = project_dir / ".sdlc-eval"
    if sdlc_eval_dir.exists():
        return sdlc_eval_dir / "jobs"
    return project_dir / "jobs"


# ---------------------------------------------------------------------------
# Harbor execution
# ---------------------------------------------------------------------------


def _run_harbor(config_path: Path, with_opik: bool) -> None:
    console.print("\n[bold]Running benchmark...[/bold]\n")

    harbor_bin = _find_cli_binary("harbor")

    if with_opik:
        console.print("Opik tracking enabled\n")
        opik_bin = _find_cli_binary("opik")
        cmd = [opik_bin, "harbor", "run", "--config", str(config_path)]
    else:
        cmd = [harbor_bin, "run", "--config", str(config_path)]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        console.print("[red]Harbor run failed[/red]")
        raise SystemExit(1)


def _find_cli_binary(name: str) -> str:
    """Find a CLI binary in the same venv as the current Python interpreter."""
    venv_bin = Path(sys.executable).parent / name
    if venv_bin.exists():
        return str(venv_bin)

    import shutil
    system_bin = shutil.which(name)
    if system_bin:
        return system_bin

    console.print(f"[red]ERROR: '{name}' CLI not found. Install it: pip install {name}[/red]")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Post-hoc assessment
# ---------------------------------------------------------------------------


def _run_post_hoc_assessment(config: ProjectConfig, with_opik: bool) -> None:
    latest_job = _find_latest_job(config.project_dir)
    if not latest_job:
        console.print("[yellow]WARN: No job directory found for assessment[/yellow]")
        return

    console.print("\n[bold]Running assessment evaluation...[/bold]\n")

    os.environ.pop("CLAUDECODE", None)

    from sdlc_eval_kit.evaluator import evaluate_job

    asyncio.run(evaluate_job(
        job_dir=latest_job,
        project_root=config.project_dir,
        project_name=config.reporting.project_name,
        with_opik=with_opik,
    ))


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
