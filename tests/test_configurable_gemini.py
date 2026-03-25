"""Tests for ConfigurableGemini agent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nasde_toolkit.agents.configurable_gemini import (
    ConfigurableGemini,
    _expand_skill_targets,
    _read_gemini_oauth_creds,
)


def test_name_returns_configurable_gemini_cli() -> None:
    assert ConfigurableGemini.name() == "configurable-gemini-cli"


def test_constructor_stores_sandbox_files() -> None:
    files = {"/app/GEMINI.md": "/tmp/GEMINI.md"}
    agent = ConfigurableGemini(
        sandbox_files=files,
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )
    assert agent._sandbox_files == files


def test_constructor_defaults_to_empty_sandbox_files() -> None:
    agent = ConfigurableGemini(
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )
    assert agent._sandbox_files == {}


def test_setup_calls_dns_fix_then_upload_then_parent() -> None:
    agent = ConfigurableGemini(
        sandbox_files={"/app/GEMINI.md": __file__},
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with patch.object(ConfigurableGemini.__bases__[0], "setup", new_callable=AsyncMock) as mock_parent_setup:
        asyncio.run(agent.setup(env))

    dns_call = env.exec.call_args_list[0]
    cmd = dns_call.kwargs.get("command", dns_call.args[0] if dns_call.args else "")
    assert "generativelanguage.googleapis.com" in cmd
    mock_parent_setup.assert_awaited_once_with(env)
    assert env.upload_file.await_count >= 1


def test_upload_raises_on_missing_source() -> None:
    agent = ConfigurableGemini(
        sandbox_files={"/app/GEMINI.md": "/nonexistent/path.md"},
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with (
        patch.object(ConfigurableGemini.__bases__[0], "setup", new_callable=AsyncMock),
        pytest.raises(FileNotFoundError, match="does not exist"),
    ):
        asyncio.run(agent.setup(env))


# ---------------------------------------------------------------------------
# Skill target expansion
# ---------------------------------------------------------------------------


def test_expand_skill_targets_gemini_skills_path() -> None:
    targets = _expand_skill_targets("/app/.gemini/skills/tactical-ddd/SKILL.md")
    assert len(targets) == 2
    assert "/app/.gemini/skills/tactical-ddd/SKILL.md" in targets
    assert "/root/.gemini/skills/tactical-ddd/SKILL.md" in targets


def test_expand_skill_targets_non_skill_path() -> None:
    targets = _expand_skill_targets("/app/GEMINI.md")
    assert targets == ["/app/GEMINI.md"]


# ---------------------------------------------------------------------------
# OAuth creds tests
# ---------------------------------------------------------------------------

_SAMPLE_OAUTH_CREDS = {
    "access_token": "ya29.test-access-token",
    "refresh_token": "1//test-refresh-token",
    "token_type": "Bearer",
    "expiry_date": 1742900000000,
}


def test_read_gemini_oauth_creds_returns_json(tmp_path: Path) -> None:
    creds_file = tmp_path / ".gemini" / "oauth_creds.json"
    creds_file.parent.mkdir()
    creds_file.write_text(json.dumps(_SAMPLE_OAUTH_CREDS))

    with patch("nasde_toolkit.agents.configurable_gemini.Path.home", return_value=tmp_path):
        result = _read_gemini_oauth_creds()

    assert result is not None
    parsed = json.loads(result)
    assert parsed["access_token"] == "ya29.test-access-token"


def test_read_gemini_oauth_creds_returns_none_when_no_file(tmp_path: Path) -> None:
    with patch("nasde_toolkit.agents.configurable_gemini.Path.home", return_value=tmp_path):
        result = _read_gemini_oauth_creds()

    assert result is None


def test_read_gemini_oauth_creds_returns_none_for_empty_json(tmp_path: Path) -> None:
    creds_file = tmp_path / ".gemini" / "oauth_creds.json"
    creds_file.parent.mkdir()
    creds_file.write_text("{}")

    with patch("nasde_toolkit.agents.configurable_gemini.Path.home", return_value=tmp_path):
        result = _read_gemini_oauth_creds()

    assert result is None


def test_setup_injects_oauth_when_no_api_key() -> None:
    agent = ConfigurableGemini(
        sandbox_files={},
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")
    oauth_json = json.dumps(_SAMPLE_OAUTH_CREDS)

    with (
        patch.dict("os.environ", {}, clear=True),
        patch.object(ConfigurableGemini.__bases__[0], "setup", new_callable=AsyncMock),
        patch(
            "nasde_toolkit.agents.configurable_gemini._read_gemini_oauth_creds",
            return_value=oauth_json,
        ),
    ):
        asyncio.run(agent.setup(env))

    upload_targets = [
        call.kwargs.get("target_path", call.args[1] if len(call.args) > 1 else "")
        for call in env.upload_file.call_args_list
    ]
    assert any("oauth_creds.json" in t for t in upload_targets)
    assert any("settings.json" in t for t in upload_targets)


def test_setup_skips_oauth_when_api_key_set() -> None:
    agent = ConfigurableGemini(
        sandbox_files={},
        logs_dir=Path("/tmp/logs"),
        model_name="google/gemini-3-flash-preview",
    )

    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")
    oauth_json = json.dumps(_SAMPLE_OAUTH_CREDS)

    with (
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True),
        patch.object(ConfigurableGemini.__bases__[0], "setup", new_callable=AsyncMock),
        patch(
            "nasde_toolkit.agents.configurable_gemini._read_gemini_oauth_creds",
            return_value=oauth_json,
        ),
    ):
        asyncio.run(agent.setup(env))

    upload_targets = [
        call.kwargs.get("target_path", call.args[1] if len(call.args) > 1 else "")
        for call in env.upload_file.call_args_list
    ]
    assert not any("oauth_creds.json" in t for t in upload_targets)
