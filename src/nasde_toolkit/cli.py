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
    all_variants: bool = typer.Option(
        False,
        "--all-variants",
        help="Run all available variants (Cartesian product with tasks).",
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
    attempts: int = typer.Option(
        1,
        "--attempts",
        "-n",
        help="Number of independent attempts per task (Harbor n_attempts).",
    ),
    without_eval: bool = typer.Option(
        False,
        "--without-eval",
        help="Skip assessment evaluation after benchmark.",
    ),
    harbor_env: Optional[str] = typer.Option(
        None,
        "--harbor-env",
        help="Harbor execution environment (docker, daytona, modal, e2b, runloop, gke). Default: docker.",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Run benchmark tasks via Harbor."""
    if variant and all_variants:
        console.print("[red]ERROR: --variant and --all-variants are mutually exclusive.[/red]")
        raise typer.Exit(1)

    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.runner import collect_available_variants, run_benchmark

    config = load_project_config(project_dir.resolve())
    tasks_filter = [t.strip() for t in tasks.split(",")] if tasks else None
    resolved_harbor_env = harbor_env or config.default_harbor_env
    resolved_model = model or config.default_model
    resolved_timeout = timeout or config.default_timeout_sec

    if all_variants:
        variants_list = collect_available_variants(config.project_dir)
        if not variants_list:
            console.print("[red]ERROR: No variants found.[/red]")
            raise typer.Exit(1)

        _confirm_multi_variant_run(
            variants=variants_list,
            config=config,
            tasks_filter=tasks_filter,
            attempts=attempts,
        )

        # TODO: Parallel variant execution is possible but requires refactoring
        # _run_job() to eliminate os.chdir() and isolate Opik tracking.
        asyncio.run(_run_all_variants(
            config=config,
            variants=variants_list,
            model=resolved_model,
            timeout_sec=resolved_timeout,
            tasks_filter=tasks_filter,
            with_opik=with_opik,
            with_eval=not without_eval,
            harbor_env=resolved_harbor_env,
            n_attempts=attempts,
        ))
    else:
        resolved_variant = variant or config.default_variant
        _print_run_header(
            variant=resolved_variant,
            model=resolved_model,
            timeout=resolved_timeout,
            tasks_filter=tasks_filter,
            with_opik=with_opik,
            with_eval=not without_eval,
            harbor_env=resolved_harbor_env,
            attempts=attempts,
        )

        asyncio.run(run_benchmark(
            config=config,
            variant=resolved_variant,
            model=resolved_model,
            timeout_sec=resolved_timeout,
            tasks_filter=tasks_filter,
            with_opik=with_opik,
            with_eval=not without_eval,
            harbor_env=resolved_harbor_env,
            n_attempts=attempts,
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
    harbor_env: str | None = None,
    attempts: int = 1,
) -> None:
    tasks_str = ", ".join(tasks_filter) if tasks_filter else "all"
    eval_str = "enabled" if with_eval else "[yellow]disabled[/yellow]"
    env_str = harbor_env or "docker"
    attempts_str = f"{attempts}" if attempts > 1 else "1"
    console.print(Panel(
        f"[bold]Benchmark Runner[/bold]\n"
        f"Variant: {variant}\n"
        f"Model: {model}\n"
        f"Timeout: {timeout}s\n"
        f"Tasks: {tasks_str}\n"
        f"Attempts: {attempts_str}\n"
        f"Environment: {env_str}\n"
        f"Opik: {'enabled' if with_opik else 'disabled'}\n"
        f"Assessment: {eval_str}",
        title="nasde",
    ))


def _confirm_multi_variant_run(
    variants: list[str],
    config: "ProjectConfig",
    tasks_filter: list[str] | None,
    attempts: int,
) -> None:
    from rich.table import Table

    task_names = [t.name for t in config.tasks]
    if tasks_filter:
        task_names = [n for n in task_names if n in set(tasks_filter)]

    n_variants = len(variants)
    n_tasks = len(task_names)
    total_trials = n_variants * n_tasks * attempts

    table = Table(title="Multi-Variant Run")
    table.add_column("Variants", style="cyan")
    table.add_column("Tasks", style="green")
    table.add_column("Attempts", justify="right")
    table.add_column("Total trials", justify="right", style="bold")
    table.add_row(
        ", ".join(variants),
        ", ".join(task_names) if task_names else "(none)",
        str(attempts),
        str(total_trials),
    )
    console.print(table)

    typer.confirm(
        f"Run {total_trials} trials ({n_variants} variants x {n_tasks} tasks x {attempts} attempts)?",
        abort=True,
    )


async def _run_all_variants(
    config: "ProjectConfig",
    variants: list[str],
    model: str,
    timeout_sec: int,
    tasks_filter: list[str] | None,
    with_opik: bool,
    with_eval: bool,
    harbor_env: str | None,
    n_attempts: int,
) -> None:
    from rich.table import Table

    from nasde_toolkit.runner import run_benchmark

    results: list[tuple[str, str, str]] = []

    for i, variant_name in enumerate(variants, 1):
        console.print(
            f"\n[bold]===  Variant {i}/{len(variants)}: {variant_name}  ===[/bold]\n"
        )
        try:
            await run_benchmark(
                config=config,
                variant=variant_name,
                model=model,
                timeout_sec=timeout_sec,
                tasks_filter=tasks_filter,
                with_opik=with_opik,
                with_eval=with_eval,
                harbor_env=harbor_env,
                n_attempts=n_attempts,
            )
            results.append((variant_name, "[green]OK[/green]", ""))
        except SystemExit:
            results.append((variant_name, "[red]FAILED[/red]", "system exit"))
        except Exception as exc:
            console.print(f"[red]ERROR running variant '{variant_name}': {exc}[/red]")
            results.append((variant_name, "[red]FAILED[/red]", str(exc)))

    _print_multi_variant_summary(results)


def _print_multi_variant_summary(
    results: list[tuple[str, str, str]],
) -> None:
    from rich.table import Table

    table = Table(title="Multi-Variant Summary")
    table.add_column("Variant", style="cyan")
    table.add_column("Status")
    table.add_column("Error")
    for variant_name, status, error in results:
        table.add_row(variant_name, status, error)
    console.print(table)
