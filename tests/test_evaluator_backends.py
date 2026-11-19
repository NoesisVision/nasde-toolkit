from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends import EvaluatorBackend, create_backend
from nasde_toolkit.evaluator_backends.claude_subprocess import ClaudeSubprocessBackend
from nasde_toolkit.evaluator_backends.codex_subprocess import CodexSubprocessBackend
from nasde_toolkit.evaluator_backends.cursor_subprocess import CursorSubprocessBackend


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


def test_claude_backend_validate_cli_installed_succeeds_when_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "nasde_toolkit.evaluator_backends.claude_subprocess.shutil.which"
    monkeypatch.setattr(target, lambda _: "/usr/local/bin/claude")
    backend = ClaudeSubprocessBackend()
    backend.validate_cli_installed()


def test_claude_backend_validate_cli_installed_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("nasde_toolkit.evaluator_backends.claude_subprocess.shutil.which", lambda _: None)
    backend = ClaudeSubprocessBackend()
    with pytest.raises(SystemExit):
        backend.validate_cli_installed()
    captured = capsys.readouterr()
    assert "claude" in captured.out.lower()
    assert "cli not found" in captured.out.lower()
    assert "install" in captured.out.lower()
    assert "[evaluation]" in captured.out
    assert "nasde.toml" in captured.out
    assert "--without-eval" in captured.out


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


def test_claude_backend_validate_auth_tolerates_missing_env_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keychain OAuth (subscription accounts) is invisible to the environment;
    # validate_auth must not hard-fail — the subprocess fails loudly if the
    # CLI truly has no auth.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    backend = ClaudeSubprocessBackend()
    backend.validate_auth()


def test_claude_backend_builds_command(tmp_path: Path) -> None:
    backend = ClaudeSubprocessBackend()
    eval_config = EvaluationConfig(model="claude-sonnet-5-5", max_turns=10)
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
    assert "claude-sonnet-5-5" in cmd
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


def test_claude_backend_command_includes_add_dir_for_agent_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    (trial_dir / "agent_changes.diff").write_text("diff --git a/x b/x\n", encoding="utf-8")
    backend = ClaudeSubprocessBackend()
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=EvaluationConfig(),
        project_root=tmp_path.parent,
        trial_dir=trial_dir,
    )
    assert "--add-dir" in cmd
    assert str(trial_dir) in cmd


def test_claude_backend_command_no_add_dir_without_trajectory_or_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    backend = ClaudeSubprocessBackend()
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=EvaluationConfig(),
        project_root=tmp_path.parent,
        trial_dir=trial_dir,
    )
    assert "--add-dir" not in cmd


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


def test_codex_backend_validate_cli_installed_succeeds_when_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "nasde_toolkit.evaluator_backends.codex_subprocess.shutil.which"
    monkeypatch.setattr(target, lambda _: "/usr/local/bin/codex")
    backend = CodexSubprocessBackend()
    backend.validate_cli_installed()


def test_codex_backend_validate_cli_installed_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("nasde_toolkit.evaluator_backends.codex_subprocess.shutil.which", lambda _: None)
    backend = CodexSubprocessBackend()
    with pytest.raises(SystemExit):
        backend.validate_cli_installed()
    captured = capsys.readouterr()
    assert "codex" in captured.out.lower()
    assert "cli not found" in captured.out.lower()
    assert "install" in captured.out.lower()
    assert "[evaluation]" in captured.out
    assert "nasde.toml" in captured.out
    assert "--without-eval" in captured.out


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
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_fails_without_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    backend = CodexSubprocessBackend()
    with pytest.raises(SystemExit):
        backend.validate_auth()


def test_codex_backend_builds_command(tmp_path: Path) -> None:
    backend = CodexSubprocessBackend()
    eval_config = EvaluationConfig(backend="codex", model="gpt-6.1-sol")
    cmd = backend._build_command(
        workspace_path=tmp_path,
        eval_config=eval_config,
    )
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--full-auto" in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--color" in cmd
    assert "never" in cmd
    assert "--model" in cmd
    assert "gpt-6.1-sol" in cmd
    assert "--quiet" not in cmd


def test_codex_backend_env_strips_api_keys_when_oauth_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "tok"}}')
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("CODEX_API_KEY", "sk-stale-key-from-dotenv")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    backend = CodexSubprocessBackend()
    env = backend._build_env()

    assert "CODEX_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env


def test_codex_backend_env_promotes_codex_key_to_openai_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("CODEX_API_KEY", "sk-codex-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    backend = CodexSubprocessBackend()
    env = backend._build_env()

    assert env["OPENAI_API_KEY"] == "sk-codex-key"
    assert env["CODEX_API_KEY"] == "sk-codex-key"


def test_codex_backend_env_preserves_openai_key_priority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode": "chatgpt", "tokens": {"access_token": "tok"}}')
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-explicit-openai-key")
    monkeypatch.setenv("CODEX_API_KEY", "sk-stale-codex-key")

    backend = CodexSubprocessBackend()
    env = backend._build_env()

    assert env["OPENAI_API_KEY"] == "sk-explicit-openai-key"
    assert env.get("CODEX_API_KEY") == "sk-stale-codex-key"


CURSOR_MODULE = "nasde_toolkit.evaluator_backends.cursor_subprocess"


def test_create_backend_returns_cursor_when_configured() -> None:
    backend = create_backend(EvaluationConfig(backend="cursor"))
    assert isinstance(backend, CursorSubprocessBackend)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_unknown_lists_cursor() -> None:
    with pytest.raises(ValueError, match="'cursor'"):
        create_backend(EvaluationConfig(backend="unknown-agent"))


def test_cursor_backend_validate_cli_installed_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(f"{CURSOR_MODULE}.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        CursorSubprocessBackend().validate_cli_installed()
    out = capsys.readouterr().out
    assert "cursor-agent" in out
    assert "cli not found" in out.lower()
    assert "[evaluation]" in out
    assert "--without-eval" in out


def test_cursor_backend_validate_auth_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "key_test")
    monkeypatch.setattr(f"{CURSOR_MODULE}.subprocess.run", lambda *a, **k: pytest.fail("status must not run"))
    CursorSubprocessBackend().validate_auth()


def test_cursor_backend_validate_auth_with_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr(
        f"{CURSOR_MODULE}.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="✓ Logged in as dev@example.com\n", stderr=""),
    )
    CursorSubprocessBackend().validate_auth()


def test_cursor_backend_validate_auth_fails_when_logged_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr(
        f"{CURSOR_MODULE}.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Not logged in\n", stderr=""),
    )
    with pytest.raises(SystemExit):
        CursorSubprocessBackend().validate_auth()


def test_cursor_backend_builds_read_only_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    temp_workspace = tmp_path / "temp"
    cmd = CursorSubprocessBackend()._build_command(
        "PROMPT", workspace, EvaluationConfig(backend="cursor", model="claude-opus-5-5-high"), temp_workspace, None
    )
    assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "json"]
    assert cmd[cmd.index("--mode") + 1] == "ask"
    assert "--trust" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5-high"
    assert cmd[cmd.index("--workspace") + 1] == str(temp_workspace)
    assert cmd[cmd.index("--add-dir") + 1] == str(workspace)
    assert "--approve-mcps" not in cmd
    assert cmd[-2:] == ["--", "PROMPT"]


def test_cursor_backend_adds_trial_dir_for_agent_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    (trial_dir / "agent_changes.diff").write_text("diff --git a/x b/x\n")
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path / "ws", EvaluationConfig(backend="cursor"), tmp_path / "tmp", trial_dir
    )
    add_dirs = [cmd[i + 1] for i, part in enumerate(cmd) if part == "--add-dir"]
    assert add_dirs == [str(tmp_path / "ws"), str(trial_dir)]


def test_cursor_backend_skips_trial_dir_without_trajectory_or_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path / "ws", EvaluationConfig(backend="cursor"), tmp_path / "tmp", trial_dir
    )
    assert cmd.count("--add-dir") == 1


def test_cursor_backend_approves_mcps_when_configured(tmp_path: Path) -> None:
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path, EvaluationConfig(backend="cursor", mcp_config="./mcp.json"), tmp_path / "tmp", None
    )
    assert "--approve-mcps" in cmd


def test_cursor_backend_prepends_system_prompt(tmp_path: Path) -> None:
    cmd = CursorSubprocessBackend()._build_command(
        "PROMPT", tmp_path, EvaluationConfig(backend="cursor", append_system_prompt="Be strict."), tmp_path / "t", None
    )
    assert cmd[-1] == "Be strict.\n\nPROMPT"


def test_cursor_backend_temp_workspace_holds_skills_and_mcp(tmp_path: Path) -> None:
    skill = tmp_path / "evaluator_skills" / "rubric-helper"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# helper")
    (tmp_path / "evaluator_mcp.json").write_text('{"mcpServers": {}}')
    eval_config = EvaluationConfig(backend="cursor", skills_dir="evaluator_skills", mcp_config="evaluator_mcp.json")

    temp_workspace = CursorSubprocessBackend()._prepare_temp_workspace(eval_config, tmp_path)

    try:
        assert (temp_workspace / ".cursor" / "skills" / "rubric-helper" / "SKILL.md").exists()
        assert json.loads((temp_workspace / ".cursor" / "mcp.json").read_text()) == {"mcpServers": {}}
    finally:
        shutil.rmtree(temp_workspace, ignore_errors=True)


def test_cursor_backend_warns_on_allowed_tools(capsys: pytest.CaptureFixture[str]) -> None:
    CursorSubprocessBackend()._warn_unsupported_options(EvaluationConfig(backend="cursor", allowed_tools=["Read"]))
    assert "allowed_tools" in capsys.readouterr().out


def _fake_cursor_process(stdout: str, returncode: int = 0) -> object:
    class FakeProcess:
        def __init__(self) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return stdout.encode(), b"stderr line"

    async def fake_exec(*_args: object, **_kwargs: object) -> FakeProcess:
        return FakeProcess()

    return fake_exec


def _patch_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CursorSubprocessBackend, "validate_cli_installed", lambda self: None)
    monkeypatch.setattr(CursorSubprocessBackend, "validate_auth", lambda self: None)


def test_cursor_backend_run_returns_result_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    created: list[Path] = []
    real_prepare = CursorSubprocessBackend._prepare_temp_workspace

    def tracking_prepare(self: CursorSubprocessBackend, eval_config: EvaluationConfig, project_root: Path) -> Path:
        path = real_prepare(self, eval_config, project_root)
        created.append(path)
        return path

    monkeypatch.setattr(CursorSubprocessBackend, "_prepare_temp_workspace", tracking_prepare)
    payload = json.dumps({"type": "result", "is_error": False, "result": '{"score": 7}'})
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process(payload))

    text = asyncio.run(
        CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
    )

    assert text == '{"score": 7}'
    assert created and not created[0].exists()


def test_cursor_backend_run_raises_on_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    payload = json.dumps({"type": "result", "is_error": True, "result": "model not available"})
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process(payload))

    with pytest.raises(RuntimeError, match="model not available"):
        asyncio.run(
            CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
        )


def test_cursor_backend_run_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process("", returncode=2))

    with pytest.raises(RuntimeError, match="exit code 2"):
        asyncio.run(
            CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
        )


def _redirect_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    scratch = tmp_path / "scratch_tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    return scratch


def test_cursor_backend_run_leaks_no_temp_workspace_when_preparation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_preflight(monkeypatch)
    scratch = _redirect_tempdir(tmp_path, monkeypatch)
    eval_config = EvaluationConfig(backend="cursor", mcp_config="missing_mcp.json")

    with pytest.raises(FileNotFoundError):
        asyncio.run(CursorSubprocessBackend().run_evaluation("P", tmp_path, eval_config, tmp_path))

    assert list(scratch.glob("nasde_eval_cursor_*")) == []


def test_cursor_backend_run_cleans_up_temp_workspace_on_is_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_preflight(monkeypatch)
    scratch = _redirect_tempdir(tmp_path, monkeypatch)
    payload = json.dumps({"type": "result", "is_error": True, "result": "boom"})
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process(payload))

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
        )

    assert list(scratch.glob("nasde_eval_cursor_*")) == []


def test_cursor_backend_run_cleans_up_temp_workspace_on_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_preflight(monkeypatch)
    scratch = _redirect_tempdir(tmp_path, monkeypatch)
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process("", returncode=2))

    with pytest.raises(RuntimeError, match="exit code 2"):
        asyncio.run(
            CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
        )

    assert list(scratch.glob("nasde_eval_cursor_*")) == []
