"""Cursor CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends.protocol import AGENT_DIFF_FILENAME

console = Console()

_CURSOR_CLI = "cursor-agent"


class CursorSubprocessBackend:
    """Evaluator backend that spawns `cursor-agent -p` as a subprocess.

    Runs with ``--mode ask`` (read-only; Cursor has no per-tool allow-list) from a
    throwaway ``--workspace`` that holds the evaluator's ``.cursor/skills`` and
    ``.cursor/mcp.json``. The trial workspace is attached with ``--add-dir``, so
    nothing the CLI writes lands in the agent's diff. The prompt is passed as the
    final positional argument. Authenticates via ``CURSOR_API_KEY`` or the host's
    ``cursor-agent login`` (ADR-015).
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_cli_installed()
        self.validate_auth()
        self._warn_unsupported_options(eval_config)
        temp_workspace = self._prepare_temp_workspace(eval_config, project_root)
        try:
            cmd = self._build_command(prompt, workspace_path, eval_config, temp_workspace, trial_dir)
            return await self._run_subprocess(cmd, temp_workspace)
        finally:
            shutil.rmtree(temp_workspace, ignore_errors=True)

    def validate_auth(self) -> None:
        if os.environ.get("CURSOR_API_KEY"):
            return
        if _cursor_cli_logged_in():
            return
        console.print("[red]ERROR: Set CURSOR_API_KEY or log in via `cursor-agent login`[/red]")
        raise SystemExit(1)

    def validate_cli_installed(self) -> None:
        if shutil.which(_CURSOR_CLI) is not None:
            return
        console.print(
            "[red]ERROR: `cursor-agent` CLI not found on PATH.[/red]\n"
            "[yellow]Assessment evaluation with the Cursor backend requires the Cursor CLI.[/yellow]\n"
            "Install it with `curl https://cursor.com/install -fsS | bash`, then re-run. "
            'To use a different backend, set \\[evaluation] backend = "claude" in nasde.toml, '
            "or pass --without-eval to skip assessment evaluation."
        )
        raise SystemExit(1)

    def _warn_unsupported_options(self, eval_config: EvaluationConfig) -> None:
        if eval_config.allowed_tools:
            _warn_allowed_tools_ignored()

    def _prepare_temp_workspace(self, eval_config: EvaluationConfig, project_root: Path) -> Path:
        temp_workspace = Path(tempfile.mkdtemp(prefix="nasde_eval_cursor_"))
        try:
            _populate_cursor_dir(temp_workspace / ".cursor", eval_config, project_root)
        except BaseException:
            shutil.rmtree(temp_workspace, ignore_errors=True)
            raise
        return temp_workspace

    def _build_command(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        temp_workspace: Path,
        trial_dir: Path | None,
    ) -> list[str]:
        cmd = [
            _CURSOR_CLI,
            "-p",
            "--output-format",
            "json",
            "--mode",
            "ask",
            "--trust",
            "--model",
            eval_config.model,
            "--workspace",
            str(temp_workspace),
            "--add-dir",
            str(workspace_path),
        ]
        if trial_dir is not None and _needs_trial_dir(eval_config, trial_dir):
            cmd.extend(["--add-dir", str(trial_dir)])
        if eval_config.mcp_config:
            cmd.append("--approve-mcps")
        cmd.extend(["--", _compose_prompt(prompt, eval_config.append_system_prompt)])
        return cmd

    async def _run_subprocess(self, cmd: list[str], cwd: Path) -> str:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=dict(os.environ),
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout_text = stdout_bytes.decode(errors="replace")
        if process.returncode != 0:
            raise RuntimeError(_failure_message(process.returncode, cmd, stdout_text, stderr_bytes))
        return _extract_result_text(stdout_text)


@functools.lru_cache(maxsize=1)
def _warn_allowed_tools_ignored() -> None:
    console.print(
        "[yellow]WARNING: \\[evaluation] allowed_tools is ignored by the cursor backend — "
        "it runs read-only via --mode ask.[/yellow]"
    )


@functools.lru_cache(maxsize=1)
def _cursor_cli_logged_in() -> bool:
    try:
        completed = subprocess.run([_CURSOR_CLI, "status"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "logged in as" in completed.stdout.lower()


def _populate_cursor_dir(cursor_dir: Path, eval_config: EvaluationConfig, project_root: Path) -> None:
    cursor_dir.mkdir()
    if eval_config.skills_dir:
        skills_source = _resolve_path(eval_config.skills_dir, project_root)
        if skills_source.is_dir():
            shutil.copytree(skills_source, cursor_dir / "skills")
    if eval_config.mcp_config:
        shutil.copyfile(_resolve_path(eval_config.mcp_config, project_root), cursor_dir / "mcp.json")


def _resolve_path(relative_or_absolute: str, project_root: Path) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return project_root / path


def _needs_trial_dir(eval_config: EvaluationConfig, trial_dir: Path) -> bool:
    return eval_config.include_trajectory or (trial_dir / AGENT_DIFF_FILENAME).exists()


def _compose_prompt(prompt: str, preamble: str | None) -> str:
    if not preamble:
        return prompt
    return f"{preamble}\n\n{prompt}"


def _failure_message(returncode: int | None, cmd: list[str], stdout_text: str, stderr_bytes: bytes) -> str:
    stderr_text = stderr_bytes.decode(errors="replace").strip()
    stderr_tail = "\n".join(stderr_text.splitlines()[-10:]) or "<empty>"
    stdout_tail = "\n".join(stdout_text.strip().splitlines()[-10:]) or "<empty>"
    model = cmd[cmd.index("--model") + 1]
    return (
        f"Cursor process failed (exit code {returncode}). Model: {model}. "
        f"stderr (last 10 lines):\n{stderr_tail}\n"
        f"stdout (last 10 lines):\n{stdout_tail}"
    )


def _extract_result_text(stdout: str) -> str:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
    if not isinstance(data, dict):
        return stdout
    if data.get("is_error"):
        raise RuntimeError(f"cursor-agent reported an error: {data.get('result', '')}")
    result = data.get("result", "")
    return result if isinstance(result, str) else ""
