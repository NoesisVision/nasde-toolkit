"""Tests for ConfigurableCursor agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from harbor.agents.installed.cursor_cli import CursorCli
from harbor.models.task.config import MCPServerConfig

from nasde_toolkit.agents.configurable_cursor import ConfigurableCursor

MODEL = "cursor/composer-2.5"


def test_name_returns_configurable_cursor_cli() -> None:
    assert ConfigurableCursor.name() == "configurable-cursor-cli"


def test_constructor_stores_sandbox_files() -> None:
    files = {"/app/AGENTS.md": "/tmp/AGENTS.md"}
    agent = ConfigurableCursor(sandbox_files=files, logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert agent._sandbox_files == files


def test_constructor_defaults_to_empty_sandbox_files() -> None:
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert agent._sandbox_files == {}


def test_cli_flags_approve_mcps_when_servers_declared() -> None:
    server = MCPServerConfig(name="docs", transport="stdio", command="node")
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL, mcp_servers=[server])
    assert "--approve-mcps" in agent.build_cli_flags()


def test_cli_flags_omit_approve_mcps_without_servers() -> None:
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert "--approve-mcps" not in agent.build_cli_flags()


def test_cli_flags_keep_harbor_flags_alongside_approve_mcps() -> None:
    server = MCPServerConfig(name="docs", transport="stdio", command="node")
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL, mcp_servers=[server], mode="ask")
    flags = agent.build_cli_flags()
    assert "--mode" in flags
    assert "--approve-mcps" in flags


def test_setup_uploads_sandbox_files_before_harbor_setup() -> None:
    agent = ConfigurableCursor(sandbox_files={"/app/AGENTS.md": __file__}, logs_dir=Path("/tmp/logs"), model_name=MODEL)
    order: list[str] = []
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    async def record_upload(**_: object) -> None:
        order.append("upload")

    async def record_harbor_setup(_self: CursorCli, _environment: object) -> None:
        order.append("harbor-setup")

    env.upload_file.side_effect = record_upload
    with patch.object(CursorCli, "setup", record_harbor_setup):
        asyncio.run(agent.setup(env))

    assert order == ["upload", "harbor-setup"]


def test_setup_raises_on_missing_source() -> None:
    agent = ConfigurableCursor(
        sandbox_files={"/app/AGENTS.md": "/nonexistent/AGENTS.md"}, logs_dir=Path("/tmp/logs"), model_name=MODEL
    )
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with (
        patch.object(CursorCli, "setup", new_callable=AsyncMock),
        pytest.raises(FileNotFoundError, match="does not exist"),
    ):
        asyncio.run(agent.setup(env))
