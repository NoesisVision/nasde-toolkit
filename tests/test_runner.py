"""Tests for runner module — harbor_env propagation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

from nasde_toolkit.config import (
    ProjectConfig,
    SourceConfig,
    TaskConfig,
)
from nasde_toolkit.runner import (
    _build_merged_config,
    _collect_sandbox_files,
    _ensure_auth,
    _generate_harbor_config,
    _is_codex_agent,
    _is_gemini_agent,
    collect_available_variants,
    load_variant_agent_type,
    load_variant_task_scope,
    scope_tasks_for_variant,
)


@pytest.fixture()
def tmp_project(tmp_path: Path) -> ProjectConfig:
    task_dir = tmp_path / "tasks" / "sample-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        dedent(
            """\
            version = "1.0"

            [task]
            name = "nasde/sample-task"

            [nasde.source]
            git = "https://example.com/repo.git"
            ref = "main"
            """
        )
    )

    variant_dir = tmp_path / "variants" / "vanilla"
    variant_dir.mkdir(parents=True)
    harbor_config = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "vanilla",
                "kwargs": {"sandbox_files": {}},
            }
        ]
    }
    (variant_dir / "harbor_config.json").write_text(json.dumps(harbor_config))

    return ProjectConfig(
        name="test-benchmark",
        version="1.0.0",
        project_dir=tmp_path,
        tasks=[
            TaskConfig(
                name="sample-task",
                path=task_dir,
                source=SourceConfig(git="https://example.com/repo.git", ref="main"),
            )
        ],
    )


def test_build_merged_config_default_has_no_environment(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
    )
    assert "environment" not in result


def test_build_merged_config_with_harbor_env_daytona(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env="daytona",
    )
    assert result["environment"] == {"type": "daytona"}


def test_build_merged_config_with_harbor_env_modal(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env="modal",
    )
    assert result["environment"] == {"type": "modal"}


def test_build_merged_config_none_harbor_env_omits_environment(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-4-6",
        timeout_sec=720,
        tasks_filter=None,
        harbor_env=None,
    )
    assert "environment" not in result


# ---------------------------------------------------------------------------
# collect_available_variants
# ---------------------------------------------------------------------------


def test_collect_available_variants_discovers_multiple(tmp_path: Path) -> None:
    (tmp_path / "variants" / "vanilla").mkdir(parents=True)
    (tmp_path / "variants" / "enhanced").mkdir(parents=True)
    (tmp_path / "variants" / "minimal").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["enhanced", "minimal", "vanilla"]


def test_collect_available_variants_nasde_subdir(tmp_path: Path) -> None:
    (tmp_path / ".nasde" / "variants" / "alpha").mkdir(parents=True)
    (tmp_path / ".nasde" / "variants" / "beta").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["alpha", "beta"]


def test_collect_available_variants_merges_both_locations(tmp_path: Path) -> None:
    (tmp_path / "variants" / "vanilla").mkdir(parents=True)
    (tmp_path / ".nasde" / "variants" / "special").mkdir(parents=True)
    assert collect_available_variants(tmp_path) == ["special", "vanilla"]


def test_collect_available_variants_empty(tmp_path: Path) -> None:
    assert collect_available_variants(tmp_path) == []


def test_collect_available_variants_ignores_files(tmp_path: Path) -> None:
    (tmp_path / "variants").mkdir(parents=True)
    (tmp_path / "variants" / "vanilla").mkdir()
    (tmp_path / "variants" / "README.md").write_text("docs")
    assert collect_available_variants(tmp_path) == ["vanilla"]


# ---------------------------------------------------------------------------
# load_variant_agent_type
# ---------------------------------------------------------------------------


def test_load_variant_agent_type_claude(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"')
    assert load_variant_agent_type(tmp_path) == "claude"


def test_load_variant_agent_type_codex(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "codex"')
    assert load_variant_agent_type(tmp_path) == "codex"


def test_load_variant_agent_type_gemini(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "gemini"')
    assert load_variant_agent_type(tmp_path) == "gemini"


def test_load_variant_agent_type_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        load_variant_agent_type(tmp_path)


def test_load_variant_agent_type_invalid_value_raises(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "gpt"')
    with pytest.raises(SystemExit):
        load_variant_agent_type(tmp_path)


def test_load_variant_agent_type_missing_field_raises(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('model = "o3"')
    with pytest.raises(SystemExit):
        load_variant_agent_type(tmp_path)


# ---------------------------------------------------------------------------
# variant task-scope
# ---------------------------------------------------------------------------


def test_load_variant_task_scope_absent_is_none(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"')
    assert load_variant_task_scope(tmp_path) is None


def test_load_variant_task_scope_empty_list_is_none(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"\ntasks = []')
    assert load_variant_task_scope(tmp_path) is None


def test_load_variant_task_scope_returns_list(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"\ntasks = ["a", "b"]')
    assert load_variant_task_scope(tmp_path) == ["a", "b"]


def test_load_variant_task_scope_non_string_entries_raise(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"\ntasks = [1, 2]')
    with pytest.raises(SystemExit):
        load_variant_task_scope(tmp_path)


def test_scope_tasks_unscoped_variant_keeps_all(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"')
    assert scope_tasks_for_variant(tmp_path, ["a", "b", "c"], None) == ["a", "b", "c"]


def test_scope_tasks_scoped_variant_intersects(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "claude"\ntasks = ["b"]')
    assert scope_tasks_for_variant(tmp_path, ["a", "b", "c"], None) == ["b"]


def test_scope_tasks_scope_wins_over_explicit_filter(tmp_path: Path) -> None:
    # Even if the user asked for task "a" via --tasks, a variant scoped to "b"
    # only runs "b" — and here "b" was filtered out, so nothing runs.
    (tmp_path / "variant.toml").write_text('agent = "claude"\ntasks = ["b"]')
    assert scope_tasks_for_variant(tmp_path, ["a"], ["a"]) == []


# ---------------------------------------------------------------------------
# _is_codex_agent
# ---------------------------------------------------------------------------


def test_is_codex_agent_with_codex_import_path() -> None:
    assert _is_codex_agent("nasde_toolkit.agents.configurable_codex:ConfigurableCodex")


def test_is_codex_agent_with_harbor_codex() -> None:
    assert _is_codex_agent("harbor.agents.installed.codex:Codex")


def test_is_codex_agent_with_claude_import_path() -> None:
    assert not _is_codex_agent("nasde_toolkit.agents.configurable_claude:ConfigurableClaude")


def test_is_codex_agent_with_none() -> None:
    assert not _is_codex_agent(None)


# ---------------------------------------------------------------------------
# _is_gemini_agent
# ---------------------------------------------------------------------------


def test_is_gemini_agent_with_gemini_import_path() -> None:
    assert _is_gemini_agent("nasde_toolkit.agents.configurable_gemini:ConfigurableGemini")


def test_is_gemini_agent_with_harbor_gemini() -> None:
    assert _is_gemini_agent("harbor.agents.installed.gemini_cli:GeminiCli")


def test_is_gemini_agent_with_claude_import_path() -> None:
    assert not _is_gemini_agent("nasde_toolkit.agents.configurable_claude:ConfigurableClaude")


def test_is_gemini_agent_with_none() -> None:
    assert not _is_gemini_agent(None)


# ---------------------------------------------------------------------------
# _generate_harbor_config — agent type detection
# ---------------------------------------------------------------------------


def test_generate_harbor_config_claude_variant(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "vanilla"
    variant_dir.mkdir(parents=True)
    (variant_dir / "CLAUDE.md").write_text("# Claude")
    (variant_dir / "variant.toml").write_text('agent = "claude"')

    _generate_harbor_config(variant_dir, "vanilla")

    config = json.loads((variant_dir / "harbor_config.json").read_text())
    assert "configurable_claude" in config["agents"][0]["import_path"]


def test_generate_harbor_config_codex_variant(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "codex-baseline"
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# Codex")
    (variant_dir / "variant.toml").write_text('agent = "codex"')

    _generate_harbor_config(variant_dir, "codex-baseline")

    config = json.loads((variant_dir / "harbor_config.json").read_text())
    assert "configurable_codex" in config["agents"][0]["import_path"]
    assert config["agents"][0]["name"] == "codex-baseline"
    assert "/app/AGENTS.md" in config["agents"][0]["kwargs"]["sandbox_files"]


# ---------------------------------------------------------------------------
# _ensure_auth — multi-provider
# ---------------------------------------------------------------------------


def test_ensure_auth_claude_with_anthropic_key() -> None:
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
        _ensure_auth()


def test_ensure_auth_claude_with_oauth_token() -> None:
    with patch.dict("os.environ", {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-test"}, clear=True):
        _ensure_auth()


def test_ensure_auth_claude_missing_raises() -> None:
    with patch.dict("os.environ", {}, clear=True), pytest.raises(SystemExit):
        _ensure_auth()


def test_ensure_auth_codex_with_codex_api_key() -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    with patch.dict("os.environ", {"CODEX_API_KEY": "sk-test"}, clear=True):
        _ensure_auth(codex_path)


def test_ensure_auth_codex_with_openai_api_key() -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
        _ensure_auth(codex_path)


def test_ensure_auth_codex_with_oauth_file_forces_auth_json(tmp_path: Path) -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "t"}}')

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        _ensure_auth(codex_path)
        assert os.environ["CODEX_FORCE_AUTH_JSON"] == "true"


def test_ensure_auth_codex_oauth_does_not_override_existing_force_flag(tmp_path: Path) -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "t"}}')

    with (
        patch.dict("os.environ", {"CODEX_FORCE_AUTH_JSON": "0"}, clear=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        _ensure_auth(codex_path)
        assert os.environ["CODEX_FORCE_AUTH_JSON"] == "0"


def test_ensure_auth_codex_oauth_does_not_override_explicit_auth_json_path(tmp_path: Path) -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "t"}}')

    with (
        patch.dict("os.environ", {"CODEX_AUTH_JSON_PATH": "/custom/auth.json"}, clear=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        _ensure_auth(codex_path)
        assert "CODEX_FORCE_AUTH_JSON" not in os.environ
        assert os.environ["CODEX_AUTH_JSON_PATH"] == "/custom/auth.json"


def test_ensure_auth_codex_with_api_key_does_not_force_auth_json(tmp_path: Path) -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "t"}}')

    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        _ensure_auth(codex_path)
        assert "CODEX_FORCE_AUTH_JSON" not in os.environ


def test_ensure_auth_codex_missing_raises() -> None:
    codex_path = "nasde_toolkit.agents.configurable_codex:ConfigurableCodex"
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("nasde_toolkit.runner.Path") as mock_path_cls,
        pytest.raises(SystemExit),
    ):
        mock_home = mock_path_cls.home.return_value
        mock_home.joinpath.return_value.exists.return_value = False
        _ensure_auth(codex_path)


# ---------------------------------------------------------------------------
# _generate_harbor_config — gemini variant
# ---------------------------------------------------------------------------


def test_generate_harbor_config_gemini_variant(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "gemini-vanilla"
    variant_dir.mkdir(parents=True)
    (variant_dir / "GEMINI.md").write_text("# Gemini")
    (variant_dir / "variant.toml").write_text('agent = "gemini"')

    _generate_harbor_config(variant_dir, "gemini-vanilla")

    config = json.loads((variant_dir / "harbor_config.json").read_text())
    assert "configurable_gemini" in config["agents"][0]["import_path"]
    assert config["agents"][0]["name"] == "gemini-vanilla"
    assert "/app/GEMINI.md" in config["agents"][0]["kwargs"]["sandbox_files"]


def test_generate_harbor_config_gemini_with_skills(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "gemini-skilled"
    variant_dir.mkdir(parents=True)
    (variant_dir / "GEMINI.md").write_text("# Gemini")
    (variant_dir / "variant.toml").write_text('agent = "gemini"')
    skill_dir = variant_dir / "gemini_skills" / "tactical-ddd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# TDD Skill")

    _generate_harbor_config(variant_dir, "gemini-skilled")

    config = json.loads((variant_dir / "harbor_config.json").read_text())
    agent = config["agents"][0]
    sandbox = agent["kwargs"]["sandbox_files"]
    assert not any(k.startswith("/app/.gemini/skills/") for k in sandbox)
    assert agent["skills"] == [str(skill_dir.resolve())]


def test_generate_harbor_config_codex_with_skills(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "codex-skilled"
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# Codex")
    (variant_dir / "variant.toml").write_text('agent = "codex"')
    skill_dir = variant_dir / "agents_skills" / "tactical-ddd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# TDD Skill")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "patterns.md").write_text("# Patterns")

    _generate_harbor_config(variant_dir, "codex-skilled")

    config = json.loads((variant_dir / "harbor_config.json").read_text())
    agent = config["agents"][0]
    sandbox = agent["kwargs"]["sandbox_files"]
    assert not any(k.startswith("/app/.agents/skills/") for k in sandbox)
    assert agent["skills"] == [str(skill_dir.resolve())]


# ---------------------------------------------------------------------------
# _ensure_auth — gemini provider
# ---------------------------------------------------------------------------


def test_ensure_auth_gemini_with_gemini_api_key() -> None:
    gemini_path = "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True):
        _ensure_auth(gemini_path)


def test_ensure_auth_gemini_with_google_api_key() -> None:
    gemini_path = "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=True):
        _ensure_auth(gemini_path)


def test_ensure_auth_gemini_with_google_credentials() -> None:
    gemini_path = "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    with patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}, clear=True):
        _ensure_auth(gemini_path)


def test_ensure_auth_gemini_with_oauth_file(tmp_path: Path) -> None:
    gemini_path = "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    creds_file = tmp_path / ".gemini" / "oauth_creds.json"
    creds_file.parent.mkdir(parents=True)
    creds_file.write_text('{"access_token": "test"}')

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        _ensure_auth(gemini_path)


def test_ensure_auth_gemini_missing_raises() -> None:
    gemini_path = "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini"
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("nasde_toolkit.runner.Path") as mock_path_cls,
        pytest.raises(SystemExit),
    ):
        mock_home = mock_path_cls.home.return_value
        mock_home.joinpath.return_value.exists.return_value = False
        _ensure_auth(gemini_path)


# ---------------------------------------------------------------------------
# _collect_sandbox_files — claude_config.json
# ---------------------------------------------------------------------------


def test_collect_sandbox_files_includes_claude_config_json(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "with-mcp"
    variant_dir.mkdir(parents=True)
    (variant_dir / "claude_config.json").write_text('{"mcpServers": {}}')

    result = _collect_sandbox_files(variant_dir)

    assert "/logs/agent/sessions/.claude.json" in result
    assert result["/logs/agent/sessions/.claude.json"] == str(variant_dir / "claude_config.json")


def test_collect_sandbox_files_omits_claude_config_when_absent(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "vanilla"
    variant_dir.mkdir(parents=True)

    result = _collect_sandbox_files(variant_dir)

    assert "/logs/agent/sessions/.claude.json" not in result
