from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends import EvaluatorBackend, create_backend
from nasde_toolkit.evaluator_backends.claude_subprocess import ClaudeSubprocessBackend
from nasde_toolkit.evaluator_backends.codex_subprocess import CodexSubprocessBackend


def test_create_backend_returns_claude_by_default() -> None:
    config = EvaluationConfig()
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_returns_codex_when_configured() -> None:
    config = EvaluationConfig(backend="codex")
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_raises_on_unknown() -> None:
    config = EvaluationConfig(backend="unknown-agent")
    with pytest.raises(ValueError, match="Unknown evaluator backend"):
        create_backend(config)


def test_claude_backend_validate_auth_succeeds_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    backend = ClaudeSubprocessBackend()
    backend.validate_auth()


def test_claude_backend_validate_auth_succeeds_with_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-oat-test")
    backend = ClaudeSubprocessBackend()
    backend.validate_auth()


def test_claude_backend_validate_auth_fails_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    backend = ClaudeSubprocessBackend()
    with pytest.raises(SystemExit):
        backend.validate_auth()


def test_claude_backend_builds_command(tmp_path: Path) -> None:
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(model="claude-sonnet-4-6", max_turns=10)
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
        project_root=tmp_path.parent,
        trial_dir=None,
    )
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "--model" in cmd
    assert "claude-sonnet-4-6" in cmd
    assert "--max-turns" in cmd
    assert "10" in cmd
    assert "--bare" not in cmd
    assert "--allowedTools" in cmd


def test_claude_backend_command_includes_add_dir_for_trajectory(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(include_trajectory=True)
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
        project_root=tmp_path.parent,
        trial_dir=trial_dir,
    )
    assert "--add-dir" in cmd
    assert str(trial_dir) in cmd


def test_claude_backend_command_includes_mcp_config(tmp_path: Path) -> None:
    mcp_file = tmp_path / "mcp.json"
    mcp_file.write_text("{}")
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(mcp_config=str(mcp_file))
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
        project_root=tmp_path.parent,
        trial_dir=None,
    )
    assert "--mcp-config" in cmd
    assert str(mcp_file) in cmd


def test_claude_backend_command_includes_append_system_prompt(tmp_path: Path) -> None:
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(append_system_prompt="Be strict.")
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
        project_root=tmp_path.parent,
        trial_dir=None,
    )
    assert "--append-system-prompt" in cmd
    assert "Be strict." in cmd


def test_claude_backend_command_includes_skills_dir_setup(tmp_path: Path) -> None:
    skills_dir = tmp_path / "evaluator_skills" / "my-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Skill content")

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(skills_dir=str(tmp_path / "evaluator_skills"))
    cmd, temp_dir = backend._build_command_with_skills(
        workspace_path=workspace_path,
        eval_config=eval_config,
        project_root=tmp_path,
        trial_dir=None,
    )
    assert temp_dir is not None
    assert (temp_dir / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
    assert "--add-dir" in cmd
    assert str(workspace_path) in cmd

    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_claude_backend_no_skills_returns_no_temp_dir(tmp_path: Path) -> None:
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig()  # no skills_dir
    cmd, temp_dir = backend._build_command_with_skills(
        workspace_path=tmp_path,
        eval_config=eval_config,
        project_root=tmp_path.parent,
        trial_dir=None,
    )
    assert temp_dir is None


def test_codex_backend_validate_auth_succeeds_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_succeeds_with_codex_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_API_KEY", "sk-test-key")
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_succeeds_with_chatgpt_oauth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_file = codex_home / "auth.json"
    auth_file.write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "tok"}}')
    monkeypatch.setenv("HOME", str(tmp_path))
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_fails_without_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    backend = CodexSubprocessBackend()
    with pytest.raises(SystemExit):
        backend.validate_auth()


def test_codex_backend_builds_command(tmp_path: Path) -> None:
    backend = CodexSubprocessBackend()
    eval_config = EvaluationConfig(backend="codex", model="o3")
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
    )
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--quiet" in cmd
    assert "--full-auto" in cmd
    assert "--model" in cmd
    assert "o3" in cmd
