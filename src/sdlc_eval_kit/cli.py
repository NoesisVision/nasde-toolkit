"""CLI entry point for sdlc-eval.

Commands:
    sdlc-eval init    — Scaffold a new evaluation project
    sdlc-eval run     — Run benchmark tasks via Harbor
    sdlc-eval eval    — Post-hoc assessment of trial artifacts
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from sdlc_eval_kit import __version__

app = typer.Typer(
    name="sdlc-eval",
    help="AI coding agent evaluation toolkit",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"sdlc-eval [bold]{__version__}[/bold]")
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
    """AI coding agent evaluation toolkit."""


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
    from sdlc_eval_kit.scaffold import create_project

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
    with_eval: bool = typer.Option(
        False,
        "--with-eval",
        help="Run post-hoc assessment after benchmark.",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Run benchmark tasks via Harbor."""
    from sdlc_eval_kit.config import load_project_config
    from sdlc_eval_kit.runner import run_benchmark

    config = load_project_config(project_dir.resolve())

    tasks_filter = [t.strip() for t in tasks.split(",")] if tasks else None

    _print_run_header(
        variant=variant or config.default_variant,
        model=model or config.default_model,
        timeout=timeout or config.default_timeout_sec,
        tasks_filter=tasks_filter,
        with_opik=with_opik,
        with_eval=with_eval,
    )

    run_benchmark(
        config=config,
        variant=variant or config.default_variant,
        model=model or config.default_model,
        timeout_sec=timeout or config.default_timeout_sec,
        tasks_filter=tasks_filter,
        with_opik=with_opik,
        with_eval=with_eval,
    )


@app.command()
def eval(
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
    import asyncio

    from sdlc_eval_kit.config import load_project_config
    from sdlc_eval_kit.evaluator import evaluate_job

    config = load_project_config(project_dir.resolve())

    console.print(Panel(
        f"[bold]Assessment Evaluation[/bold]\n"
        f"Job: {job_dir}\n"
        f"Opik: {'enabled' if with_opik else 'disabled'}",
        title="sdlc-eval",
    ))

    asyncio.run(evaluate_job(
        job_dir=job_dir.resolve(),
        project_root=config.project_dir,
        project_name=config.reporting.project_name,
        with_opik=with_opik,
    ))


def _print_run_header(
    variant: str,
    model: str,
    timeout: int,
    tasks_filter: list[str] | None,
    with_opik: bool,
    with_eval: bool,
) -> None:
    tasks_str = ", ".join(tasks_filter) if tasks_filter else "all"
    console.print(Panel(
        f"[bold]Benchmark Runner[/bold]\n"
        f"Variant: {variant}\n"
        f"Model: {model}\n"
        f"Timeout: {timeout}s\n"
        f"Tasks: {tasks_str}\n"
        f"Opik: {'enabled' if with_opik else 'disabled'}\n"
        f"Assessment: {'enabled' if with_eval else 'disabled'}",
        title="sdlc-eval",
    ))
