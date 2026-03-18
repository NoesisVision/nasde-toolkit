"""CLI entry point for nasde.

Core commands (run, eval, init) use Harbor/Opik Python APIs directly.
Pass-through commands (harbor, opik) delegate to the respective CLIs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from nasde_toolkit import __version__

app = typer.Typer(
    name="nasde",
    help="Noesis Agentic Software Development Evals Toolkit",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"nasde [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Noesis Agentic Software Development Evals Toolkit."""


@app.command()
def init(
    project_dir: Path = typer.Argument(
        Path("."),
        help="Directory to scaffold the evaluation project in.",
    ),
    name: str = typer.Option(
        "",
        "--name",
        "-n",
        help="Project name (defaults to directory name).",
    ),
) -> None:
    """Scaffold a new evaluation project."""
    from nasde_toolkit.scaffold import create_project

    project_name = name or project_dir.resolve().name
    create_project(project_dir.resolve(), project_name)


@app.command()
def run(
    variant: Optional[str] = typer.Option(
        None,
        "--variant",
        help="Variant to run (defaults to config default).",
    ),
    tasks: Optional[str] = typer.Option(
        None,
        "--tasks",
        help="Comma-separated task names to run.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Model override.",
    ),
    timeout: Optional[int] = typer.Option(
        None,
        "--timeout",
        help="Agent timeout in seconds.",
    ),
    with_opik: bool = typer.Option(
        False,
        "--with-opik",
        help="Enable Opik tracing.",
    ),
    without_eval: bool = typer.Option(
        False,
        "--without-eval",
        help="Skip assessment evaluation after benchmark.",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Run benchmark tasks via Harbor."""
    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.runner import run_benchmark

    config = load_project_config(project_dir.resolve())

    tasks_filter = [t.strip() for t in tasks.split(",")] if tasks else None

    _print_run_header(
        variant=variant or config.default_variant,
        model=model or config.default_model,
        timeout=timeout or config.default_timeout_sec,
        tasks_filter=tasks_filter,
        with_opik=with_opik,
        with_eval=not without_eval,
    )

    asyncio.run(run_benchmark(
        config=config,
        variant=variant or config.default_variant,
        model=model or config.default_model,
        timeout_sec=timeout or config.default_timeout_sec,
        tasks_filter=tasks_filter,
        with_opik=with_opik,
        with_eval=not without_eval,
    ))


@app.command(name="eval")
def eval_command(
    job_dir: Path = typer.Argument(
        ...,
        help="Path to job directory to evaluate.",
    ),
    with_opik: bool = typer.Option(
        False,
        "--with-opik",
        help="Upload scores to Opik.",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Run post-hoc assessment of trial artifacts."""
    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.evaluator import evaluate_job

    config = load_project_config(project_dir.resolve())

    console.print(Panel(
        f"[bold]Assessment Evaluation[/bold]\n"
        f"Job: {job_dir}\n"
        f"Opik: {'enabled' if with_opik else 'disabled'}",
        title="nasde",
    ))

    asyncio.run(evaluate_job(
        job_dir=job_dir.resolve(),
        project_root=config.project_dir,
        project_name=config.reporting.project_name,
        with_opik=with_opik,
    ))


# ---------------------------------------------------------------------------
# Harbor pass-through (Typer → Typer)
# ---------------------------------------------------------------------------

from harbor.cli.main import app as harbor_app

app.add_typer(harbor_app, name="harbor", help="Harbor CLI (pass-through).")


# ---------------------------------------------------------------------------
# Opik pass-through (Click → Typer via ctx.args)
# ---------------------------------------------------------------------------


@app.command(
    name="opik",
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
def opik_passthrough(ctx: typer.Context) -> None:
    """Opik CLI commands (pass-through)."""
    from opik.cli.main import cli as opik_cli

    opik_cli(ctx.args, standalone_mode=False)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _print_run_header(
    variant: str,
    model: str,
    timeout: int,
    tasks_filter: list[str] | None,
    with_opik: bool,
    with_eval: bool,
) -> None:
    tasks_str = ", ".join(tasks_filter) if tasks_filter else "all"
    eval_str = "enabled" if with_eval else "[yellow]disabled[/yellow]"
    console.print(Panel(
        f"[bold]Benchmark Runner[/bold]\n"
        f"Variant: {variant}\n"
        f"Model: {model}\n"
        f"Timeout: {timeout}s\n"
        f"Tasks: {tasks_str}\n"
        f"Opik: {'enabled' if with_opik else 'disabled'}\n"
        f"Assessment: {eval_str}",
        title="nasde",
    ))
