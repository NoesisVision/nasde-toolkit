"""CLI entry point for nasde.

Core commands (run, eval, init) use Harbor/Opik Python APIs directly.
Pass-through commands (harbor, opik) delegate to the respective CLIs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer._click.formatting import HelpFormatter as ClickHelpFormatter
from typer.core import TyperGroup

if TYPE_CHECKING:
    from collections.abc import Callable

    from nasde_toolkit.calibration_publisher import TrialComments
    from nasde_toolkit.calibration_resolve import ResolvedSink
    from nasde_toolkit.config import ProjectConfig

console = Console()


class _BannerGroup(TyperGroup):
    def format_help(self, ctx: ClickContext, formatter: ClickHelpFormatter) -> None:
        from nasde_toolkit.banner import print_banner

        print_banner(console)
        super().format_help(ctx, formatter)

    def get_command(self, ctx: ClickContext, cmd_name: str) -> ClickCommand | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            original_format_help = cmd.format_help

            def patched_format_help(ctx: ClickContext, formatter: ClickHelpFormatter) -> None:
                from nasde_toolkit.banner import print_banner

                print_banner(console)
                original_format_help(ctx, formatter)

            cmd.format_help = patched_format_help  # type: ignore[assignment]
        return cmd


app = typer.Typer(
    name="nasde",
    help="Noesis Agentic Software Development Evals Toolkit",
    rich_markup_mode="rich",
    cls=_BannerGroup,
)


def _version_callback(value: bool) -> None:
    if value:
        from nasde_toolkit.banner import print_banner

        print_banner(console)
        raise typer.Exit()


def _no_banner_callback(value: bool) -> None:
    if value:
        from nasde_toolkit.banner import suppress_banner

        suppress_banner()


def _override_eval_repetitions(config: ProjectConfig, eval_repetitions: int | None) -> None:
    if eval_repetitions is None:
        return
    if eval_repetitions < 1:
        console.print("[red]ERROR: --eval-repetitions must be >= 1.[/red]")
        raise typer.Exit(1)
    config.evaluation.eval_repetitions = eval_repetitions


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    no_banner: bool = typer.Option(
        False,
        "--no-banner",
        help="Suppress ASCII banner. Also: NASDE_NO_BANNER=1.",
        callback=_no_banner_callback,
        is_eager=True,
    ),
) -> None:
    """Noesis Agentic Software Development Evals Toolkit."""
    from nasde_toolkit._version import __version__
    from nasde_toolkit.update_check import maybe_notify_update

    maybe_notify_update(console, current_version=__version__)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


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
    from nasde_toolkit.banner import print_banner
    from nasde_toolkit.scaffold import create_project

    print_banner(console)
    project_name = name or project_dir.resolve().name
    create_project(project_dir.resolve(), project_name)


@app.command(name="install-skills")
def install_skills(
    scope: str = typer.Option(
        "user",
        "--scope",
        help="Where to install: 'user' (~/.claude/skills) or 'project' (./.claude/skills).",
    ),
    target_dir: Path | None = typer.Option(
        None,
        "--target-dir",
        help="Custom skills directory (overrides --scope).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing skill files.",
    ),
) -> None:
    """Install NASDE authoring skills into a Claude Code skills directory."""
    from nasde_toolkit.banner import print_banner
    from nasde_toolkit.skills_installer import install_bundled_skills

    print_banner(console)
    install_bundled_skills(console=console, scope=scope, target_dir=target_dir, force=force)


@app.command()
def run(
    variant: str | None = typer.Option(
        None,
        "--variant",
        help="Variant to run (defaults to config default).",
    ),
    all_variants: bool = typer.Option(
        False,
        "--all-variants",
        help="Run all available variants (Cartesian product with tasks).",
    ),
    tasks: str | None = typer.Option(
        None,
        "--tasks",
        help="Comma-separated task names to run.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model override.",
    ),
    timeout: int | None = typer.Option(
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
    job_suffix: str | None = typer.Option(
        None,
        "--job-suffix",
        help="Custom suffix for job directory name (default: random 6-char hex).",
    ),
    max_concurrent_eval: int = typer.Option(
        10,
        "--max-concurrent-eval",
        help="Max concurrent assessment evaluations (default: 10).",
    ),
    eval_repetitions: int | None = typer.Option(
        None,
        "--eval-repetitions",
        help="Judge evaluations per trial (default: from nasde.toml [evaluation], fallback 3).",
    ),
    harbor_env: str | None = typer.Option(
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

    if not variant and not all_variants:
        console.print("[red]ERROR: Specify --variant NAME or --all-variants.[/red]")
        raise typer.Exit(1)

    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.runner import collect_available_variants, run_benchmark

    config = load_project_config(project_dir.resolve())
    _override_eval_repetitions(config, eval_repetitions)
    tasks_filter = [t.strip() for t in tasks.split(",")] if tasks else None
    resolved_harbor_env = harbor_env or config.default_harbor_env
    resolved_model = model
    resolved_timeout = timeout

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
        asyncio.run(
            _run_all_variants(
                config=config,
                variants=variants_list,
                model=resolved_model,
                timeout_sec=resolved_timeout,
                tasks_filter=tasks_filter,
                with_opik=with_opik,
                with_eval=not without_eval,
                harbor_env=resolved_harbor_env,
                n_attempts=attempts,
                job_suffix=job_suffix,
                max_concurrent_eval=max_concurrent_eval,
            )
        )
    else:
        assert variant is not None
        resolved_variant = variant
        from nasde_toolkit.runner import (
            _resolve_model,
            load_variant_agent_type,
            resolve_variant_dir,
            scope_tasks_for_variant,
        )

        variant_dir = resolve_variant_dir(config.project_dir, resolved_variant)
        agent_type = load_variant_agent_type(variant_dir)
        display_model = _resolve_model(resolved_model, variant_dir, config)

        base_task_names = [t.name for t in config.tasks]
        if tasks_filter:
            base_task_names = [n for n in base_task_names if n in set(tasks_filter)]
        scoped_tasks = scope_tasks_for_variant(variant_dir, base_task_names, tasks_filter)
        if not scoped_tasks:
            console.print(
                f"[red]ERROR: variant '{resolved_variant}' is task-scoped (variant.toml `tasks`) "
                f"and none of the requested tasks fall within its scope.[/red]"
            )
            raise typer.Exit(1)

        _print_run_header(
            variant=resolved_variant,
            model=display_model,
            timeout=resolved_timeout,
            tasks_filter=scoped_tasks,
            with_opik=with_opik,
            with_eval=not without_eval,
            harbor_env=resolved_harbor_env,
            attempts=attempts,
            agent_type=agent_type,
        )

        asyncio.run(
            run_benchmark(
                config=config,
                variant=resolved_variant,
                model=resolved_model,
                timeout_sec=resolved_timeout,
                tasks_filter=scoped_tasks,
                with_opik=with_opik,
                with_eval=not without_eval,
                harbor_env=resolved_harbor_env,
                n_attempts=attempts,
                job_suffix=job_suffix,
                max_concurrent_eval=max_concurrent_eval,
            )
        )


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
    max_concurrent_eval: int = typer.Option(
        10,
        "--max-concurrent-eval",
        help="Max concurrent assessment evaluations (default: 10).",
    ),
    eval_repetitions: int | None = typer.Option(
        None,
        "--eval-repetitions",
        help="Judge evaluations per trial (default: from nasde.toml [evaluation], fallback 3).",
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
    _override_eval_repetitions(config, eval_repetitions)

    from nasde_toolkit.banner import print_banner

    print_banner(console)
    console.print(
        Panel(
            f"[bold]Assessment Evaluation[/bold]\nJob: {job_dir}\nOpik: {'enabled' if with_opik else 'disabled'}",
            title="nasde",
        )
    )

    asyncio.run(
        evaluate_job(
            job_dir=job_dir.resolve(),
            project_root=config.project_dir,
            project_name=config.reporting.project_name,
            with_opik=with_opik,
            max_concurrent=max_concurrent_eval,
            eval_config=config.evaluation,
        )
    )


@app.command(name="results-export")
def results_export_command(
    paths: list[Path] = typer.Argument(
        ...,
        help="Job and/or trial directories to export (mixed OK — type is auto-detected).",
    ),
    to: Path = typer.Option(
        ...,
        "--to",
        "-t",
        help="Destination directory (iCloud, Dropbox, a git repo — any plain path).",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """[EXPERIMENTAL] Export the essence of trial artifacts to a plain directory.

    Copies metrics, assessment scores, the agent trajectory, and a code patch for
    each trial into a flat per-trial layout, so results survive even when jobs/ is
    cleared and without relying on Opik or EXPERIMENT_LOG.md.
    """
    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.results_exporter import export_results

    load_project_config(project_dir.resolve())

    from nasde_toolkit.banner import print_banner

    print_banner(console)
    console.print(
        Panel(
            f"[bold]Results Export[/bold] [yellow](experimental)[/yellow]\nDest: {to}\nInputs: {len(paths)}",
            title="nasde",
        )
    )

    export_results([p.resolve() for p in paths], to.resolve())


@app.command(name="migrate-evals", hidden=True)
def migrate_evals_command(
    path: Path = typer.Argument(
        ...,
        help="A jobs/ root or a single trial directory whose eval files to normalize.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without touching any files.",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """[internal] Normalize legacy assessment eval files to the numbered + summary scheme.

    Hidden from `nasde --help`: this is a one-shot migration tool for legacy
    jobs/ trees (pre-numbered-eval scheme), not a routine user command. Still
    invokable for future migrations.

    Renames a bare assessment_eval.json to assessment_eval_1.json, removes a
    bare file that duplicates the highest numbered one, and (re)computes
    assessment_summary.json. Idempotent.

    Pass a jobs/ root (recurses into all trials) or a single trial directory.
    A single job directory is not supported — pass the jobs/ root instead, since
    a job dir's own job-level result.json is not a trial.
    """
    from nasde_toolkit.config import load_project_config
    from nasde_toolkit.eval_migration import migrate_job_evals

    load_project_config(project_dir.resolve())

    from nasde_toolkit.banner import print_banner

    print_banner(console)
    console.print(
        Panel(
            f"[bold]Migrate Evals[/bold]{' [yellow](dry-run)[/yellow]' if dry_run else ''}\nPath: {path}",
            title="nasde",
        )
    )

    outcomes = migrate_job_evals(path.resolve(), dry_run=dry_run)

    from rich.table import Table

    table = Table(title="Migration outcomes")
    table.add_column("Outcome", style="bold")
    table.add_column("Trials", justify="right")
    for name, count in outcomes.items():
        table.add_row(name, str(count))
    console.print(table)


# ---------------------------------------------------------------------------
# Calibration sub-app (nasde calibrate ...)
# ---------------------------------------------------------------------------

calibrate_app = typer.Typer(
    name="calibrate",
    help="Calibrate assessment rubrics via PR/MR review (GitHub or GitLab).",
    no_args_is_help=True,
)
app.add_typer(calibrate_app, name="calibrate")


@calibrate_app.command(name="publish")
def calibrate_publish(
    paths: list[Path] = typer.Argument(
        ...,
        help="Job and/or trial directories to publish (mixed OK — type is auto-detected).",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Sink repo URL or owner/repo slug (default: [calibration] repo in nasde.toml).",
    ),
    throttle: float | None = typer.Option(
        None,
        "--throttle",
        help="Seconds to sleep between PR-creating calls (default: [calibration] throttle_sec).",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Publish trial diffs + assessments as PRs/MRs for human rubric calibration.

    Each trial becomes one PR: an orphan base branch holds the agent's start-state
    codebase, the feature branch carries the agent's diff (so the PR diff is exactly
    the agent's work), and the description renders the per-dimension judge scores.
    Idempotent — re-running skips trials whose PR already exists.
    """
    from nasde_toolkit.calibration_publisher import publish_trials
    from nasde_toolkit.calibration_resolve import resolve_sink
    from nasde_toolkit.config import load_project_config

    config = load_project_config(project_dir.resolve())
    sink = _resolve_calibration_sink(config, repo, resolve_sink)
    throttle_sec = throttle if throttle is not None else config.calibration.throttle_sec

    from nasde_toolkit.banner import print_banner

    print_banner(console)
    console.print(
        Panel(
            f"[bold]Calibrate · Publish[/bold]\nSink: {sink.slug} ({sink.platform})\nInputs: {len(paths)}",
            title="nasde",
        )
    )

    publish_trials(
        [p.resolve() for p in paths],
        repo=sink.slug,
        repo_url=sink.push_url,
        base_branch=config.calibration.base_branch,
        platform_override=sink.platform,
        throttle_sec=throttle_sec,
        project_root=config.project_dir,
    )


@calibrate_app.command(name="pull-comments")
def calibrate_pull_comments(
    paths: list[Path] = typer.Argument(
        ...,
        help="Job and/or trial directories whose PR/MR comments to fetch.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Sink repo URL or owner/repo slug (default: [calibration] repo in nasde.toml).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON (for the calibration orchestrator agent).",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-C",
        help="Path to evaluation project.",
    ),
) -> None:
    """Fetch human review comments from each trial's PR/MR.

    Returns issue-level and inline comments normalized across platforms, so the
    calibration orchestrator can diagnose where the judge disagreed with the human.
    """
    from dataclasses import asdict

    from nasde_toolkit.calibration_publisher import pull_trial_comments
    from nasde_toolkit.calibration_resolve import resolve_sink
    from nasde_toolkit.config import load_project_config

    config = load_project_config(project_dir.resolve())
    sink = _resolve_calibration_sink(config, repo, resolve_sink)

    collected = pull_trial_comments(
        [p.resolve() for p in paths],
        repo=sink.slug,
        repo_url=sink.push_url,
        platform_override=sink.platform,
    )

    if as_json:
        import json

        console.print_json(json.dumps([asdict(tc) for tc in collected]))
        return

    _print_pulled_comments(collected)


def _resolve_calibration_sink(
    config: ProjectConfig,
    repo_flag: str | None,
    resolver: Callable[[str, str], ResolvedSink],
) -> ResolvedSink:
    from nasde_toolkit.calibration_resolve import SystemExitMessage

    repo_value = repo_flag or config.calibration.repo
    try:
        return resolver(repo_value, config.calibration.platform)
    except SystemExitMessage as error:
        console.print(f"[red]ERROR: {error}[/red]")
        raise SystemExit(1) from error


def _print_pulled_comments(collected: list[TrialComments]) -> None:
    from rich.table import Table

    table = Table(title="Pulled PR/MR comments")
    table.add_column("Trial", style="bold")
    table.add_column("PR/MR", justify="right")
    table.add_column("Comments", justify="right")
    for trial_comments in collected:
        table.add_row(trial_comments.label, str(trial_comments.pr_number), str(len(trial_comments.comments)))
    console.print(table)


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
    model: str | None,
    timeout: int | None,
    tasks_filter: list[str] | None,
    with_opik: bool,
    with_eval: bool,
    harbor_env: str | None = None,
    attempts: int = 1,
    agent_type: str = "claude",
) -> None:
    from nasde_toolkit.banner import print_banner

    print_banner(console)

    tasks_str = ", ".join(tasks_filter) if tasks_filter else "all"
    eval_str = "enabled" if with_eval else "[yellow]disabled[/yellow]"
    env_str = harbor_env or "docker"
    attempts_str = f"{attempts}" if attempts > 1 else "1"
    timeout_str = f"{timeout}s (override)" if timeout is not None else "per task.toml"
    agent_labels = {"codex": "Codex (OpenAI)", "gemini": "Gemini CLI (Google)"}
    agent_label = agent_labels.get(agent_type, "Claude Code")
    console.print(
        Panel(
            f"[bold]Benchmark Runner[/bold]\n"
            f"Agent: {agent_label}\n"
            f"Variant: {variant}\n"
            f"Model: {model}\n"
            f"Timeout: {timeout_str}\n"
            f"Tasks: {tasks_str}\n"
            f"Attempts: {attempts_str}\n"
            f"Environment: {env_str}\n"
            f"Opik: {'enabled' if with_opik else 'disabled'}\n"
            f"Assessment: {eval_str}",
            title="nasde",
        )
    )


def _confirm_multi_variant_run(
    variants: list[str],
    config: ProjectConfig,
    tasks_filter: list[str] | None,
    attempts: int,
) -> None:
    from rich.table import Table

    from nasde_toolkit.banner import print_banner

    print_banner(console)

    from nasde_toolkit.runner import resolve_variant_dir, scope_tasks_for_variant

    task_names = [t.name for t in config.tasks]
    if tasks_filter:
        task_names = [n for n in task_names if n in set(tasks_filter)]

    table = Table(title="Multi-Variant Run")
    table.add_column("Variant", style="cyan")
    table.add_column("Tasks", style="green")
    table.add_column("Trials", justify="right", style="bold")

    total_trials = 0
    for variant in variants:
        variant_dir = resolve_variant_dir(config.project_dir, variant)
        scoped = scope_tasks_for_variant(variant_dir, task_names, tasks_filter)
        n = len(scoped) * attempts
        total_trials += n
        table.add_row(
            variant,
            ", ".join(scoped) if scoped else "[yellow](skipped — task-scoped)[/yellow]",
            str(n),
        )
    console.print(table)

    typer.confirm(
        f"Run {total_trials} trials across {len(variants)} variants (x {attempts} attempts each)?",
        abort=True,
    )


async def _run_all_variants(
    config: ProjectConfig,
    variants: list[str],
    model: str | None,
    timeout_sec: int | None,
    tasks_filter: list[str] | None,
    with_opik: bool,
    with_eval: bool,
    harbor_env: str | None,
    n_attempts: int,
    job_suffix: str | None = None,
    max_concurrent_eval: int = 10,
) -> None:

    from nasde_toolkit.runner import resolve_variant_dir, run_benchmark, scope_tasks_for_variant

    results: list[tuple[str, str, str]] = []
    all_task_names = [t.name for t in config.tasks]
    base_tasks = [t for t in all_task_names if t in set(tasks_filter)] if tasks_filter else all_task_names

    for i, variant_name in enumerate(variants, 1):
        console.print(f"\n[bold]===  Variant {i}/{len(variants)}: {variant_name}  ===[/bold]\n")
        variant_dir = resolve_variant_dir(config.project_dir, variant_name)
        scoped_tasks = scope_tasks_for_variant(variant_dir, base_tasks, tasks_filter)
        if not scoped_tasks:
            console.print(
                f"[yellow]SKIP: variant '{variant_name}' is task-scoped and none of its tasks are in this run.[/yellow]"
            )
            results.append((variant_name, "[yellow]SKIPPED[/yellow]", "task-scoped, no matching task"))
            continue
        try:
            await run_benchmark(
                config=config,
                variant=variant_name,
                model=model,
                timeout_sec=timeout_sec,
                tasks_filter=scoped_tasks,
                with_opik=with_opik,
                with_eval=with_eval,
                harbor_env=harbor_env,
                n_attempts=n_attempts,
                job_suffix=job_suffix,
                max_concurrent_eval=max_concurrent_eval,
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
