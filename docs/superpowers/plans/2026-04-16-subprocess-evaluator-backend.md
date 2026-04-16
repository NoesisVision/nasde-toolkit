# Subprocess Evaluator Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude Code SDK-based evaluator with a subprocess-based architecture that supports both Claude Code CLI and Codex CLI as pluggable evaluator backends, enabling evaluation via subscription billing (OAuth) without Agent SDK restrictions.

**Architecture:** Introduce an `EvaluatorBackend` Protocol with two implementations: `ClaudeSubprocessBackend` (spawns `claude -p --output-format json`) and `CodexSubprocessBackend` (spawns `codex exec --quiet --json`). The existing SDK-based code in `_run_claude_code_evaluation()` is replaced. Backend selection is driven by a new `backend` field in `EvaluationConfig` (`"claude"` default, `"codex"` available). Everything upstream of the backend call (prompt construction, response parsing, Opik upload) remains unchanged.

**Tech Stack:** Python 3.12, asyncio subprocess, NDJSON parsing, pytest

---

### File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/nasde_toolkit/evaluator_backends/__init__.py` | Re-exports `EvaluatorBackend`, `create_backend()` |
| Create | `src/nasde_toolkit/evaluator_backends/protocol.py` | `EvaluatorBackend` Protocol definition |
| Create | `src/nasde_toolkit/evaluator_backends/claude_subprocess.py` | Claude CLI subprocess backend |
| Create | `src/nasde_toolkit/evaluator_backends/codex_subprocess.py` | Codex CLI subprocess backend |
| Modify | `src/nasde_toolkit/config.py:32-42` | Add `backend` field to `EvaluationConfig` |
| Modify | `src/nasde_toolkit/evaluator.py:20-56,458-585` | Remove SDK imports/monkeypatch, use backend |
| Create | `tests/test_evaluator_backends.py` | Tests for both backends |
| Modify | `tests/test_evaluator.py` | Update existing tests for new backend flow |
| Modify | `CLAUDE.md` | Update architecture decisions section |
| Modify | `README.md` | Document new evaluator backend config |
| Modify | `ARCHITECTURE.md` | Update evaluator section |

---

### Task 1: Add `backend` field to `EvaluationConfig`

**Files:**
- Modify: `src/nasde_toolkit/config.py:32-42`
- Modify: `src/nasde_toolkit/config.py:127-135`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_config.py — add to existing tests

def test_evaluation_config_default_backend() -> None:
    config = EvaluationConfig()
    assert config.backend == "claude"


def test_evaluation_config_codex_backend(tmp_path: Path) -> None:
    toml_content = """
[project]
name = "test"

[evaluation]
backend = "codex"
model = "o3"
"""
    (tmp_path / "nasde.toml").write_text(toml_content)
    config = load_project_config(tmp_path)
    assert config.evaluation.backend == "codex"
    assert config.evaluation.model == "o3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_evaluation_config_default_backend tests/test_config.py::test_evaluation_config_codex_backend -v`
Expected: FAIL — `EvaluationConfig` has no `backend` attribute

- [ ] **Step 3: Add `backend` field to `EvaluationConfig` and parsing**

In `src/nasde_toolkit/config.py`, add to `EvaluationConfig` dataclass:

```python
@dataclass
class EvaluationConfig:
    """Assessment evaluation settings."""

    backend: str = "claude"
    model: str = "claude-opus-4-6"
    dimensions_file: str = "assessment_dimensions.json"
    max_turns: int = 30
    allowed_tools: list[str] | None = None
    mcp_config: str | None = None
    skills_dir: str | None = None
    append_system_prompt: str | None = None
    include_trajectory: bool = False
```

In `_parse_toml()`, add backend parsing in the `EvaluationConfig(...)` constructor:

```python
        evaluation=EvaluationConfig(
            backend=eval_raw.get("backend", "claude"),
            model=eval_raw.get("model", "claude-opus-4-6"),
            # ... rest unchanged
        ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/config.py tests/test_config.py
git commit -m "feat: add backend field to EvaluationConfig for pluggable evaluator"
```

---

### Task 2: Define `EvaluatorBackend` Protocol

**Files:**
- Create: `src/nasde_toolkit/evaluator_backends/__init__.py`
- Create: `src/nasde_toolkit/evaluator_backends/protocol.py`
- Test: `tests/test_evaluator_backends.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evaluator_backends.py
from __future__ import annotations

from pathlib import Path

from nasde_toolkit.evaluator_backends import EvaluatorBackend, create_backend
from nasde_toolkit.config import EvaluationConfig


def test_create_backend_returns_claude_by_default() -> None:
    config = EvaluationConfig()
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_returns_codex_when_configured() -> None:
    config = EvaluationConfig(backend="codex")
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_raises_on_unknown() -> None:
    import pytest

    config = EvaluationConfig(backend="unknown-agent")
    with pytest.raises(ValueError, match="Unknown evaluator backend"):
        create_backend(config)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator_backends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nasde_toolkit.evaluator_backends'`

- [ ] **Step 3: Create the Protocol and factory**

`src/nasde_toolkit/evaluator_backends/protocol.py`:

```python
"""Evaluator backend protocol — defines the interface for CLI-based evaluators."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from nasde_toolkit.config import EvaluationConfig


@runtime_checkable
class EvaluatorBackend(Protocol):
    """Interface for subprocess-based evaluator backends.

    Each backend spawns a CLI agent (claude, codex, etc.) as a subprocess,
    passes the evaluation prompt, and returns the agent's text response.
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str: ...

    def validate_auth(self) -> None: ...
```

`src/nasde_toolkit/evaluator_backends/__init__.py`:

```python
"""Pluggable evaluator backends for nasde assessment evaluation."""

from nasde_toolkit.evaluator_backends.protocol import EvaluatorBackend

__all__ = ["EvaluatorBackend", "create_backend"]


def create_backend(eval_config: "EvaluationConfig") -> EvaluatorBackend:
    from nasde_toolkit.config import EvaluationConfig

    if eval_config.backend == "claude":
        from nasde_toolkit.evaluator_backends.claude_subprocess import ClaudeSubprocessBackend

        return ClaudeSubprocessBackend()
    elif eval_config.backend == "codex":
        from nasde_toolkit.evaluator_backends.codex_subprocess import CodexSubprocessBackend

        return CodexSubprocessBackend()
    else:
        raise ValueError(
            f"Unknown evaluator backend: '{eval_config.backend}'. "
            f"Supported: 'claude', 'codex'"
        )
```

- [ ] **Step 4: Create stub backend files so imports resolve**

`src/nasde_toolkit/evaluator_backends/claude_subprocess.py`:

```python
"""Claude Code CLI subprocess evaluator backend."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import EvaluationConfig


class ClaudeSubprocessBackend:
    """Evaluator backend that spawns `claude -p` as a subprocess."""

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        raise NotImplementedError

    def validate_auth(self) -> None:
        raise NotImplementedError
```

`src/nasde_toolkit/evaluator_backends/codex_subprocess.py`:

```python
"""Codex CLI subprocess evaluator backend."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import EvaluationConfig


class CodexSubprocessBackend:
    """Evaluator backend that spawns `codex exec` as a subprocess."""

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        raise NotImplementedError

    def validate_auth(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_evaluator_backends.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/ tests/test_evaluator_backends.py
git commit -m "feat: add EvaluatorBackend protocol and factory with stub implementations"
```

---

### Task 3: Implement `ClaudeSubprocessBackend`

**Files:**
- Modify: `src/nasde_toolkit/evaluator_backends/claude_subprocess.py`
- Test: `tests/test_evaluator_backends.py`

- [ ] **Step 1: Write the failing test for auth validation**

```python
# Add to tests/test_evaluator_backends.py
import os

from nasde_toolkit.evaluator_backends.claude_subprocess import ClaudeSubprocessBackend


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator_backends.py::test_claude_backend_validate_auth_succeeds_with_api_key -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Write the failing test for command construction**

```python
# Add to tests/test_evaluator_backends.py

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
    assert "--bare" in cmd
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_evaluator_backends.py -k "claude_backend" -v`
Expected: FAIL — methods not implemented

- [ ] **Step 5: Implement `ClaudeSubprocessBackend`**

Replace `src/nasde_toolkit/evaluator_backends/claude_subprocess.py`:

```python
"""Claude Code CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig

console = Console()


class ClaudeSubprocessBackend:
    """Evaluator backend that spawns `claude -p` as a subprocess.

    Uses `--output-format json` to get structured output with a `result`
    field containing the agent's text response. Authenticates via whatever
    credentials are configured (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN).
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_auth()
        cmd = self._build_command(workspace_path, eval_config, project_root, trial_dir)
        env = self._build_env()
        return await self._run_subprocess(cmd, prompt, workspace_path, env)

    def validate_auth(self) -> None:
        has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_oauth = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
        if not has_api_key and not has_oauth:
            console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
            raise SystemExit(1)

    def _build_command(
        self,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None,
    ) -> list[str]:
        cmd = [
            "claude",
            "-p",
            "--output-format", "json",
            "--bare",
            "--no-session-persistence",
            "--model", eval_config.model,
            "--max-turns", str(eval_config.max_turns),
        ]

        allowed_tools = eval_config.allowed_tools or ["Read", "Glob", "Grep"]
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        if eval_config.include_trajectory and trial_dir:
            cmd.extend(["--add-dir", str(trial_dir)])

        if eval_config.mcp_config:
            mcp_path = _resolve_path(eval_config.mcp_config, project_root)
            cmd.extend(["--mcp-config", str(mcp_path)])

        if eval_config.append_system_prompt:
            cmd.extend(["--append-system-prompt", eval_config.append_system_prompt])

        return cmd

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("CLAUDECODE", None)
        return env

    async def _run_subprocess(
        self,
        cmd: list[str],
        prompt: str,
        workspace_path: Path,
        env: dict[str, str],
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_path),
            env=env,
        )
        stdout_bytes, stderr_bytes = await process.communicate(input=prompt.encode())

        if process.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            last_lines = "\n".join(stderr_text.splitlines()[-10:]) if stderr_text else ""
            raise RuntimeError(
                f"Claude Code process failed (exit code {process.returncode}). "
                f"Model: {cmd[cmd.index('--model') + 1]}, cwd: {workspace_path}. "
                f"stderr (last 10 lines):\n{last_lines}"
            )

        return _extract_result_text(stdout_bytes.decode())


def _resolve_path(relative_or_absolute: str, project_root: Path) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return project_root / path


def _extract_result_text(stdout: str) -> str:
    try:
        data = json.loads(stdout)
        return data.get("result", "")
    except json.JSONDecodeError:
        return stdout
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_evaluator_backends.py -k "claude_backend" -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/claude_subprocess.py tests/test_evaluator_backends.py
git commit -m "feat: implement ClaudeSubprocessBackend with claude -p subprocess"
```

---

### Task 4: Implement `CodexSubprocessBackend`

**Files:**
- Modify: `src/nasde_toolkit/evaluator_backends/codex_subprocess.py`
- Test: `tests/test_evaluator_backends.py`

- [ ] **Step 1: Write the failing tests for auth and command**

```python
# Add to tests/test_evaluator_backends.py
from nasde_toolkit.evaluator_backends.codex_subprocess import CodexSubprocessBackend


def test_codex_backend_validate_auth_succeeds_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_succeeds_with_codex_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_API_KEY", "sk-test-key")
    backend = CodexSubprocessBackend()
    backend.validate_auth()


def test_codex_backend_validate_auth_succeeds_with_chatgpt_oauth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator_backends.py -k "codex_backend" -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `CodexSubprocessBackend`**

Replace `src/nasde_toolkit/evaluator_backends/codex_subprocess.py`:

```python
"""Codex CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig

console = Console()


class CodexSubprocessBackend:
    """Evaluator backend that spawns `codex exec` as a subprocess.

    Uses `--json` for JSONL event streaming. Extracts the final
    agent_message from the event stream as the evaluation response.
    Authenticates via OPENAI_API_KEY, CODEX_API_KEY, or ChatGPT OAuth.
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_auth()
        cmd = self._build_command(workspace_path, eval_config)
        cmd.append(prompt)
        return await self._run_subprocess(cmd, workspace_path)

    def validate_auth(self) -> None:
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_codex_key = bool(os.environ.get("CODEX_API_KEY"))
        has_chatgpt_oauth = _has_chatgpt_oauth()
        if not has_openai_key and not has_codex_key and not has_chatgpt_oauth:
            console.print(
                "[red]ERROR: Set OPENAI_API_KEY, CODEX_API_KEY, "
                "or log in via `codex login`[/red]"
            )
            raise SystemExit(1)

    def _build_command(
        self,
        workspace_path: Path,
        eval_config: EvaluationConfig,
    ) -> list[str]:
        cmd = [
            "codex",
            "exec",
            "--json",
            "--quiet",
            "--full-auto",
            "--model", eval_config.model,
        ]
        return cmd

    async def _run_subprocess(
        self,
        cmd: list[str],
        workspace_path: Path,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_path),
        )
        stdout_bytes, stderr_bytes = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            last_lines = "\n".join(stderr_text.splitlines()[-10:]) if stderr_text else ""
            raise RuntimeError(
                f"Codex process failed (exit code {process.returncode}). "
                f"cwd: {workspace_path}. "
                f"stderr (last 10 lines):\n{last_lines}"
            )

        return _extract_agent_messages(stdout_bytes.decode())


def _has_chatgpt_oauth() -> bool:
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return False
    try:
        raw = json.loads(auth_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return (
        raw.get("auth_mode") == "chatgpt"
        and bool(raw.get("tokens", {}).get("access_token"))
    )


def _extract_agent_messages(stdout: str) -> str:
    messages: list[str] = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                text = item.get("text", "")
                if text:
                    messages.append(text)
    return "\n".join(messages)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_evaluator_backends.py -k "codex_backend" -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/codex_subprocess.py tests/test_evaluator_backends.py
git commit -m "feat: implement CodexSubprocessBackend with codex exec subprocess"
```

---

### Task 5: Wire backend into `evaluator.py` — remove SDK dependency

**Files:**
- Modify: `src/nasde_toolkit/evaluator.py`
- Modify: `tests/test_evaluator.py`

This is the core refactoring task. We remove all `claude_code_sdk` imports, the monkeypatch, and `_run_claude_code_evaluation()` + `_build_claude_code_options()`. Replace with backend dispatch.

- [ ] **Step 1: Write test for backend dispatch in evaluator**

```python
# Add to tests/test_evaluator.py
from unittest.mock import AsyncMock, patch

from nasde_toolkit.config import EvaluationConfig


def test_evaluate_trial_uses_configured_backend(tmp_path: Path) -> None:
    """Verify evaluator creates the right backend type based on config."""
    from nasde_toolkit.evaluator_backends import create_backend

    claude_config = EvaluationConfig(backend="claude")
    codex_config = EvaluationConfig(backend="codex")

    claude_backend = create_backend(claude_config)
    codex_backend = create_backend(codex_config)

    assert type(claude_backend).__name__ == "ClaudeSubprocessBackend"
    assert type(codex_backend).__name__ == "CodexSubprocessBackend"
```

- [ ] **Step 2: Run test to verify it passes (factory already works)**

Run: `uv run pytest tests/test_evaluator.py::test_evaluate_trial_uses_configured_backend -v`
Expected: PASS

- [ ] **Step 3: Refactor `evaluator.py` — remove SDK, use backend**

Key changes to `src/nasde_toolkit/evaluator.py`:

1. **Remove** these imports (lines 20-25):
```python
# DELETE these lines:
from claude_code_sdk import ClaudeCodeOptions, query
from claude_code_sdk._errors import ProcessError
from claude_code_sdk._internal import client as _sdk_client
from claude_code_sdk._internal import message_parser as _mp
from claude_code_sdk.types import AssistantMessage, TextBlock
```

2. **Remove** the entire monkeypatch block (lines 29-56)

3. **Add** new import:
```python
from nasde_toolkit.evaluator_backends import create_backend
```

4. **Replace** the `_run_claude_code_evaluation()` call in `evaluate_trial()` (lines 246-252) with:
```python
    backend = create_backend(eval_config)
    backend.validate_auth()
    raw_response = await backend.run_evaluation(
        prompt=prompt,
        workspace_path=workspace_path,
        eval_config=eval_config,
        project_root=project_root,
        trial_dir=trial_dir,
    )
```

5. **Delete** these functions entirely:
   - `_run_claude_code_evaluation()` (lines 459-497)
   - `_extract_stderr_detail()` (lines 500-506)
   - `_build_claude_code_options()` (lines 509-558)
   - `_prepare_skills_workspace()` (lines 561-566)
   - `_resolve_path()` (lines 569-573)
   - `_validate_auth()` (lines 576-585)

6. **Update** the console message (line 244) to be backend-aware:
```python
    console.print(f"  Running {eval_config.backend} evaluation...")
```

- [ ] **Step 4: Update existing tests**

In `tests/test_evaluator.py`, update tests that reference `_build_claude_code_options`:

- Remove `test_claude_code_options_adds_trial_dir_when_trajectory_enabled` — this is now tested via `ClaudeSubprocessBackend._build_command()`
- Remove `test_claude_code_options_no_trial_dir_when_trajectory_disabled` — same reason
- Keep all prompt-building and trajectory-path tests (they're unchanged)

Add import fix at top:
```python
# Remove this import:
from nasde_toolkit.evaluator import _build_claude_code_options, _build_evaluator_prompt, _resolve_trajectory_path
# Replace with:
from nasde_toolkit.evaluator import _build_evaluator_prompt, _resolve_trajectory_path
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/nasde_toolkit/evaluator.py tests/test_evaluator.py
git commit -m "refactor: replace Claude Code SDK with subprocess-based evaluator backend"
```

---

### Task 6: Handle skills_dir in Claude subprocess backend

**Files:**
- Modify: `src/nasde_toolkit/evaluator_backends/claude_subprocess.py`
- Test: `tests/test_evaluator_backends.py`

The current SDK-based evaluator has special handling for `skills_dir`: it creates a temp directory, copies skills into `.claude/skills/`, and sets that as `cwd` with the workspace as an `add_dir`. We need to replicate this in the subprocess backend.

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_evaluator_backends.py

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator_backends.py::test_claude_backend_command_includes_skills_dir_setup -v`
Expected: FAIL — `_build_command_with_skills` doesn't exist

- [ ] **Step 3: Add skills_dir handling to `ClaudeSubprocessBackend`**

Add to `claude_subprocess.py`:

```python
import shutil
import tempfile

# Modify run_evaluation to handle skills cleanup:
    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_auth()
        cmd, temp_dir = self._build_command_with_skills(
            workspace_path, eval_config, project_root, trial_dir
        )
        env = self._build_env()
        cwd = temp_dir if temp_dir else workspace_path
        try:
            return await self._run_subprocess(cmd, prompt, cwd, env)
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_command_with_skills(
        self,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None,
    ) -> tuple[list[str], Path | None]:
        cmd = self._build_command(workspace_path, eval_config, project_root, trial_dir)
        temp_dir: Path | None = None

        if eval_config.skills_dir:
            skills_source = _resolve_path(eval_config.skills_dir, project_root)
            temp_dir = Path(tempfile.mkdtemp(prefix="nasde_eval_"))
            target = temp_dir / ".claude" / "skills"
            if skills_source.is_dir():
                shutil.copytree(skills_source, target)
            cmd.extend(["--add-dir", str(workspace_path)])

        return cmd, temp_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_evaluator_backends.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/claude_subprocess.py tests/test_evaluator_backends.py
git commit -m "feat: add skills_dir support to ClaudeSubprocessBackend"
```

---

### Task 7: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Update CLAUDE.md architecture decisions**

Replace the **Evaluator** bullet in the "Architecture decisions" section:

```markdown
- **Evaluator**: Subprocess-based assessment evaluation with pluggable backends. The evaluator spawns a CLI agent (`claude -p` or `codex exec`) as a subprocess to read trial artifacts and score them against assessment criteria. Backend selection via `[evaluation] backend` in `nasde.toml` (`"claude"` default, `"codex"` available). Claude backend uses `--output-format json --bare` for clean non-interactive output. Codex backend uses `--json --quiet --full-auto` for JSONL event streaming. Both backends respect the user's existing CLI authentication (OAuth subscription or API key) — no Agent SDK required. Configurable via `[evaluation]` in `nasde.toml` — model, tools, MCP servers, skills, system prompt, trajectory inclusion, and backend can all be customized. Results written to `assessment_eval.json` per trial and optionally uploaded to Opik.
```

Also update the dependencies bullet to remove `claude-code-sdk`:
```markdown
- **All dependencies are core**: `harbor`, `opik` are in `[project.dependencies]`. No optional extras — `uv tool install .` gives full functionality. Assessment evaluation requires `claude` CLI (default) or `codex` CLI to be installed and authenticated. Evaluation is on by default (`--without-eval` to skip).
```

- [ ] **Step 2: Update README.md**

Add a section about evaluator backend configuration in the relevant place:

```markdown
### Evaluator backend

By default, nasde uses Claude Code CLI for assessment evaluation. You can switch to Codex:

```toml
[evaluation]
backend = "codex"
model = "o3"
```

Supported backends:
- `claude` (default) — requires `claude` CLI installed and authenticated
- `codex` — requires `codex` CLI installed and authenticated

Both backends use your existing CLI authentication (subscription or API key).
```

- [ ] **Step 3: Update ARCHITECTURE.md evaluator section**

Update the evaluator description to reflect subprocess-based architecture.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md ARCHITECTURE.md
git commit -m "docs: update documentation for subprocess-based evaluator backends"
```

---

### Task 8: Remove `claude-code-sdk` dependency from `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove `claude-code-sdk` from dependencies**

In `pyproject.toml`, remove `claude-code-sdk` from `[project.dependencies]`. The evaluator no longer imports it.

- [ ] **Step 2: Verify no remaining imports**

Run: `uv run python -c "from nasde_toolkit.evaluator import evaluate_job; print('OK')"`
Expected: `OK` — no ImportError

Run: `grep -r "claude_code_sdk\|claude-code-sdk" src/`
Expected: No matches

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: remove claude-code-sdk dependency — evaluator uses subprocess now"
```

---

### Task 9: Integration smoke test

**Files:** (no new files — manual verification)

- [ ] **Step 1: Verify Claude backend works end-to-end**

Run with an existing job directory (if available):

```bash
uv run nasde eval <job-dir> -C <benchmark-project>
```

Verify it spawns `claude -p` and produces `assessment_eval.json`.

- [ ] **Step 2: Verify Codex backend configuration is recognized**

Create a test `nasde.toml` with `backend = "codex"` and run:

```bash
uv run python -c "
from nasde_toolkit.config import load_project_config
from nasde_toolkit.evaluator_backends import create_backend
from pathlib import Path

# Point to a benchmark with backend = 'codex' in nasde.toml
config = load_project_config(Path('<test-project>'))
backend = create_backend(config.evaluation)
print(f'Backend type: {type(backend).__name__}')
print(f'Model: {config.evaluation.model}')
"
```

Expected: `Backend type: CodexSubprocessBackend`

- [ ] **Step 3: Verify linting passes**

Run: `uv run ruff check src/ tests/`
Expected: No errors

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address integration test findings"
```
