"""Codex CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig

console = Console()


class CodexSubprocessBackend:
    """Evaluator backend that spawns `codex exec` as a subprocess.

    Uses `--json` for JSONL event streaming on stdout. The CLI writes clean
    NDJSON to stdout (banner and diagnostics go to stderr), so parsing is
    straightforward. Extracts the final `agent_message` items as the
    evaluation response. Authenticates via OPENAI_API_KEY, CODEX_API_KEY, or
    ChatGPT OAuth (`~/.codex/auth.json` created by `codex login`).
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
        cmd = self._build_command(workspace_path, eval_config)
        cmd.append("-")
        env = self._build_env()
        return await self._run_subprocess(cmd, prompt, workspace_path, env)

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        has_openai_key = bool(env.get("OPENAI_API_KEY"))
        has_codex_key = bool(env.get("CODEX_API_KEY"))
        if not has_openai_key and not has_codex_key:
            return env
        if _has_chatgpt_oauth() and not has_openai_key:
            env.pop("CODEX_API_KEY", None)
            return env
        if has_codex_key and not has_openai_key:
            env["OPENAI_API_KEY"] = env["CODEX_API_KEY"]
        return env

    def validate_cli_installed(self) -> None:
        if shutil.which("codex") is not None:
            return
        console.print(
            "[red]ERROR: `codex` CLI not found on PATH.[/red]\n"
            "[yellow]Assessment evaluation with the Codex backend requires the Codex CLI.[/yellow]\n"
            "Install it from https://github.com/openai/codex, then re-run. "
            'To use a different backend, set [evaluation] backend = "claude" in nasde.toml, '
            "or pass --without-eval to skip assessment evaluation."
        )
        raise SystemExit(1)

    def validate_auth(self) -> None:
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_codex_key = bool(os.environ.get("CODEX_API_KEY"))
        has_chatgpt_oauth = _has_chatgpt_oauth()
        if not has_openai_key and not has_codex_key and not has_chatgpt_oauth:
            console.print("[red]ERROR: Set OPENAI_API_KEY, CODEX_API_KEY, or log in via `codex login`[/red]")
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
            "--full-auto",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--model",
            eval_config.model,
        ]
        return cmd

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

        stdout_text = stdout_bytes.decode(errors="replace")
        if process.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            stderr_tail = "\n".join(stderr_text.splitlines()[-10:]) or "<empty>"
            stdout_tail = "\n".join(stdout_text.strip().splitlines()[-10:]) or "<empty>"
            raise RuntimeError(
                f"Codex process failed (exit code {process.returncode}). "
                f"cwd: {workspace_path}. "
                f"stderr (last 10 lines):\n{stderr_tail}\n"
                f"stdout (last 10 lines):\n{stdout_tail}"
            )

        return _extract_agent_messages(stdout_text)


def _has_chatgpt_oauth() -> bool:
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return False
    try:
        raw = json.loads(auth_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return raw.get("auth_mode") == "chatgpt" and bool(raw.get("tokens", {}).get("access_token"))


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
