"""Tests for ConfigurableCodex agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nasde_toolkit.agents.configurable_codex import ConfigurableCodex


def test_name_returns_configurable_codex() -> None:
    assert ConfigurableCodex.name() == "configurable-codex"


def test_constructor_stores_sandbox_files() -> None:
    files = {"/app/AGENTS.md": "/tmp/AGENTS.md"}
    agent = ConfigurableCodex(
        sandbox_files=files,
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )
    assert agent._sandbox_files == files


def test_constructor_defaults_to_empty_sandbox_files() -> None:
    agent = ConfigurableCodex(
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )
    assert agent._sandbox_files == {}


def test_setup_calls_dns_fix_then_parent_then_upload() -> None:
    agent = ConfigurableCodex(
        sandbox_files={"/app/AGENTS.md": __file__},
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with patch.object(ConfigurableCodex.__bases__[0], "setup", new_callable=AsyncMock) as mock_parent_setup:
        asyncio.run(agent.setup(env))

    dns_call = env.exec.call_args_list[0]
    assert "api.openai.com" in dns_call.kwargs.get("command", dns_call.args[0] if dns_call.args else "")
    mock_parent_setup.assert_awaited_once_with(env)
    assert env.upload_file.await_count == 1


def test_upload_raises_on_missing_source() -> None:
    agent = ConfigurableCodex(
        sandbox_files={"/app/AGENTS.md": "/nonexistent/path.md"},
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with (
        patch.object(ConfigurableCodex.__bases__[0], "setup", new_callable=AsyncMock),
        pytest.raises(FileNotFoundError, match="does not exist"),
    ):
        asyncio.run(agent.setup(env))
