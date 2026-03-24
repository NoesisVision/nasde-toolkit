"""Tests for ConfigurableCodex agent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nasde_toolkit.agents.configurable_codex import (
    ConfigurableCodex,
    _read_codex_oauth_auth,
)


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


# ---------------------------------------------------------------------------
# OAuth auth.json tests
# ---------------------------------------------------------------------------

_SAMPLE_OAUTH_AUTH = {
    "auth_mode": "chatgpt",
    "OPENAI_API_KEY": None,
    "tokens": {
        "id_token": "eyJ-id",
        "access_token": "eyJ-access",
        "refresh_token": "rt-refresh",
        "account_id": "00000000-0000-0000-0000-000000000000",
    },
    "last_refresh": "2026-03-23T19:24:40.239461Z",
}


def test_read_codex_oauth_auth_returns_json_for_chatgpt_mode(tmp_path: Path) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(json.dumps(_SAMPLE_OAUTH_AUTH))

    with patch("nasde_toolkit.agents.configurable_codex.Path.home", return_value=tmp_path):
        result = _read_codex_oauth_auth()

    assert result is not None
    parsed = json.loads(result)
    assert parsed["auth_mode"] == "chatgpt"
    assert parsed["tokens"]["access_token"] == "eyJ-access"


def test_read_codex_oauth_auth_returns_none_for_api_key_mode(tmp_path: Path) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(json.dumps({"OPENAI_API_KEY": "sk-test"}))

    with patch("nasde_toolkit.agents.configurable_codex.Path.home", return_value=tmp_path):
        result = _read_codex_oauth_auth()

    assert result is None


def test_read_codex_oauth_auth_returns_none_when_no_file(tmp_path: Path) -> None:
    with patch("nasde_toolkit.agents.configurable_codex.Path.home", return_value=tmp_path):
        result = _read_codex_oauth_auth()

    assert result is None


def test_create_run_agent_commands_injects_oauth_when_no_api_key() -> None:
    from harbor.agents.installed.base import ExecInput

    agent = ConfigurableCodex(
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )

    parent_commands = [
        ExecInput(
            command=(
                "mkdir -p /tmp/codex-secrets\n"
                "cat >/tmp/codex-secrets/auth.json <<EOF\n"
                '{"OPENAI_API_KEY": ""}\nEOF\n'
                'ln -sf /tmp/codex-secrets/auth.json "$CODEX_HOME/auth.json"'
            ),
            env={"OPENAI_API_KEY": "", "CODEX_HOME": "/agent"},
        ),
        ExecInput(
            command="codex exec --model o3 --json -- 'do stuff'",
            env={"OPENAI_API_KEY": "", "CODEX_HOME": "/agent"},
        ),
    ]

    oauth_json = json.dumps(_SAMPLE_OAUTH_AUTH)

    with (
        patch.dict("os.environ", {}, clear=True),
        patch.object(
            ConfigurableCodex.__bases__[0],
            "create_run_agent_commands",
            return_value=parent_commands,
        ),
        patch(
            "nasde_toolkit.agents.configurable_codex._read_codex_oauth_auth",
            return_value=oauth_json,
        ),
    ):
        result = agent.create_run_agent_commands("do stuff")

    assert len(result) == 2
    assert "printf" in result[0].command
    assert "_CODEX_OAUTH_AUTH_JSON" in result[0].env
    assert "OPENAI_API_KEY" not in result[0].env
    assert "OPENAI_API_KEY" not in result[1].env


def test_create_run_agent_commands_prefers_api_key_over_oauth() -> None:
    from harbor.agents.installed.base import ExecInput

    agent = ConfigurableCodex(
        logs_dir=Path("/tmp/logs"),
        model_name="o3",
    )

    parent_commands = [
        ExecInput(
            command="setup auth.json",
            env={"OPENAI_API_KEY": "sk-real", "CODEX_HOME": "/agent"},
        ),
        ExecInput(
            command="codex exec --model o3 --json -- 'do stuff'",
            env={"OPENAI_API_KEY": "sk-real", "CODEX_HOME": "/agent"},
        ),
    ]

    oauth_json = json.dumps(_SAMPLE_OAUTH_AUTH)

    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-real"}, clear=True),
        patch.object(
            ConfigurableCodex.__bases__[0],
            "create_run_agent_commands",
            return_value=parent_commands,
        ),
        patch(
            "nasde_toolkit.agents.configurable_codex._read_codex_oauth_auth",
            return_value=oauth_json,
        ),
    ):
        result = agent.create_run_agent_commands("do stuff")

    assert result[0].env["OPENAI_API_KEY"] == "sk-real"
    assert "_CODEX_OAUTH_AUTH_JSON" not in result[0].env
