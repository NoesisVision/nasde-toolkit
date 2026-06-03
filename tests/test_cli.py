"""Tests for CLI — --all-variants flag behavior."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from nasde_toolkit.cli import app

runner = CliRunner()


@pytest.fixture()
def benchmark_project(tmp_path: Path) -> Path:
    (tmp_path / "nasde.toml").write_text('[project]\nname = "test"\n[defaults]\nvariant = "vanilla"\n')

    for variant_name in ["vanilla", "enhanced"]:
        variant_dir = tmp_path / "variants" / variant_name
        variant_dir.mkdir(parents=True)
        (variant_dir / "CLAUDE.md").write_text(f"# {variant_name}")
        (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "claude-sonnet-4-6"\n')

    task_dir = tmp_path / "tasks" / "sample"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        dedent(
            """\
            version = "1.0"

            [task]
            name = "nasde/sample"

            [nasde.source]
            git = "https://example.com/repo.git"
            ref = "main"
            """
        )
    )

    return tmp_path


def test_no_variant_flag_requires_one(benchmark_project: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "-C", str(benchmark_project)],
    )
    assert result.exit_code != 0
    assert "--variant" in result.output.lower() or "--all-variants" in result.output.lower()


def test_variant_and_all_variants_mutually_exclusive(benchmark_project: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "--variant", "vanilla", "--all-variants", "-C", str(benchmark_project)],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_all_variants_discovers_and_confirms(benchmark_project: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "--all-variants", "-C", str(benchmark_project)],
        input="n\n",
    )
    assert "enhanced" in result.output
    assert "vanilla" in result.output
    assert "2" in result.output


@patch("nasde_toolkit.runner.run_benchmark", new_callable=AsyncMock)
def test_all_variants_runs_each_variant(mock_run: AsyncMock, benchmark_project: Path) -> None:
    runner.invoke(
        app,
        ["run", "--all-variants", "-C", str(benchmark_project)],
        input="y\n",
    )
    assert mock_run.await_count == 2
    called_variants = sorted(call.kwargs["variant"] for call in mock_run.call_args_list)
    assert called_variants == ["enhanced", "vanilla"]


@patch("nasde_toolkit.runner.run_benchmark", new_callable=AsyncMock)
def test_all_variants_continues_on_failure(mock_run: AsyncMock, benchmark_project: Path) -> None:
    mock_run.side_effect = [Exception("boom"), AsyncMock()]
    result = runner.invoke(
        app,
        ["run", "--all-variants", "-C", str(benchmark_project)],
        input="y\n",
    )
    assert mock_run.await_count == 2
    assert "FAILED" in result.output
    assert "OK" in result.output


@patch("nasde_toolkit.runner.run_benchmark", new_callable=AsyncMock)
def test_single_variant_task_scope_aborts_when_no_task_in_scope(mock_run: AsyncMock, benchmark_project: Path) -> None:
    scoped = benchmark_project / "variants" / "scoped"
    scoped.mkdir(parents=True)
    (scoped / "CLAUDE.md").write_text("# scoped")
    (scoped / "variant.toml").write_text(
        'agent = "claude"\nmodel = "claude-sonnet-4-6"\ntasks = ["nasde/other-task"]\n'
    )
    result = runner.invoke(
        app,
        ["run", "--variant", "scoped", "-C", str(benchmark_project)],
    )
    assert result.exit_code != 0
    assert "task-scoped" in result.output.lower()
    mock_run.assert_not_awaited()


@patch("nasde_toolkit.runner.run_benchmark", new_callable=AsyncMock)
def test_single_variant_task_scope_passes_only_scoped_tasks(mock_run: AsyncMock, benchmark_project: Path) -> None:
    scoped = benchmark_project / "variants" / "scoped"
    scoped.mkdir(parents=True)
    (scoped / "CLAUDE.md").write_text("# scoped")
    # task names are stored stripped of Harbor's "org/" prefix (nasde/sample -> sample),
    # so the scope must reference the stripped name — same as the --tasks filter does.
    (scoped / "variant.toml").write_text('agent = "claude"\nmodel = "claude-sonnet-4-6"\ntasks = ["sample"]\n')
    result = runner.invoke(
        app,
        ["run", "--variant", "scoped", "-C", str(benchmark_project)],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.await_count == 1
    assert mock_run.call_args.kwargs["tasks_filter"] == ["sample"]


@patch("nasde_toolkit.evaluator.evaluate_job", new_callable=AsyncMock)
def test_eval_command_forwards_evaluation_config(mock_evaluate_job: AsyncMock, tmp_path: Path) -> None:
    (tmp_path / "nasde.toml").write_text(
        '[project]\nname = "test"\n[defaults]\nvariant = "vanilla"\n[evaluation]\ninclude_trajectory = true\n'
    )
    job_dir = tmp_path / "jobs" / "job1"
    job_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["eval", str(job_dir), "-C", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert mock_evaluate_job.await_count == 1
    eval_config = mock_evaluate_job.call_args.kwargs["eval_config"]
    assert eval_config.include_trajectory is True


@patch("nasde_toolkit.results_exporter.export_results")
def test_results_export_command_forwards_paths_and_dest(mock_export: object, tmp_path: Path) -> None:
    (tmp_path / "nasde.toml").write_text('[project]\nname = "test"\n[defaults]\nvariant = "vanilla"\n')
    job_dir = tmp_path / "jobs" / "job1"
    job_dir.mkdir(parents=True)
    dest = tmp_path / "export"

    result = runner.invoke(
        app,
        ["results-export", str(job_dir), "--to", str(dest), "-C", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert mock_export.call_count == 1  # type: ignore[attr-defined]
    passed_paths, passed_dest = mock_export.call_args.args  # type: ignore[attr-defined]
    assert passed_paths == [job_dir.resolve()]
    assert passed_dest == dest.resolve()
