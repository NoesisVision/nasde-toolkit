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
    Authenticates via OPENAI_API_KEY, CODEX_API_KEY, or ChatGPT OAuth
    (`~/.codex/auth.json` created by `codex login`).
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
