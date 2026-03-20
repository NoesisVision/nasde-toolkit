"""Tests for CLI — --all-variants flag behavior."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from nasde_toolkit.cli import app

runner = CliRunner()


@pytest.fixture()
def benchmark_project(tmp_path: Path) -> Path:
    (tmp_path / "nasde.toml").write_text(
        '[project]\nname = "test"\n'
        '[defaults]\nvariant = "vanilla"\n'
    )

    for variant_name in ["vanilla", "enhanced"]:
        variant_dir = tmp_path / "variants" / variant_name
        variant_dir.mkdir(parents=True)
        (variant_dir / "CLAUDE.md").write_text(f"# {variant_name}")

    task_dir = tmp_path / "tasks" / "sample"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps({
        "name": "sample",
        "source": {"git": "https://example.com/repo.git", "ref": "main"},
    }))

    return tmp_path


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
def test_all_variants_runs_each_variant(
    mock_run: AsyncMock, benchmark_project: Path
) -> None:
    result = runner.invoke(
        app,
        ["run", "--all-variants", "-C", str(benchmark_project)],
        input="y\n",
    )
    assert mock_run.await_count == 2
    called_variants = sorted(
        call.kwargs["variant"] for call in mock_run.call_args_list
    )
    assert called_variants == ["enhanced", "vanilla"]


@patch("nasde_toolkit.runner.run_benchmark", new_callable=AsyncMock)
def test_all_variants_continues_on_failure(
    mock_run: AsyncMock, benchmark_project: Path
) -> None:
    mock_run.side_effect = [Exception("boom"), AsyncMock()]
    result = runner.invoke(
        app,
        ["run", "--all-variants", "-C", str(benchmark_project)],
        input="y\n",
    )
    assert mock_run.await_count == 2
    assert "FAILED" in result.output
    assert "OK" in result.output
