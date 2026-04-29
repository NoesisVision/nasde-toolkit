"""Claude Code CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig

console = Console()


class ClaudeSubprocessBackend:
    """Evaluator backend that spawns `claude -p` as a subprocess.

    Uses `--output-format json` to get structured output with a `result`
    field containing the agent's text response. Authenticates via whatever
    credentials are configured (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN).

    Does NOT use `--bare` mode — preserves OAuth/keychain auth reads
    (required for subscription-based billing) and auto-discovery of user-level
    skills. Trades a slightly slower startup for full compatibility with
    subscription accounts.
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
        cmd, temp_dir = self._build_command_with_skills(workspace_path, eval_config, project_root, trial_dir)
        env = self._build_env()
        cwd = temp_dir if temp_dir else workspace_path
        try:
            return await self._run_subprocess(cmd, prompt, cwd, env)
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def validate_cli_installed(self) -> None:
        if shutil.which("claude") is not None:
            return
        console.print(
            "[red]ERROR: `claude` CLI not found on PATH.[/red]\n"
            "[yellow]Assessment evaluation with the Claude backend requires the Claude Code CLI.[/yellow]\n"
            "Install it from https://docs.claude.com/en/docs/claude-code/setup, "
            'then re-run. To use a different backend, set \\[evaluation] backend = "codex" '
            "in nasde.toml, or pass --without-eval to skip assessment evaluation."
        )
        raise SystemExit(1)

    def validate_auth(self) -> None:
        has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_oauth = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
        if not has_api_key and not has_oauth:
            console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
            raise SystemExit(1)

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
            "--output-format",
            "json",
            "--no-session-persistence",
            "--model",
            eval_config.model,
            "--max-turns",
            str(eval_config.max_turns),
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
            model = cmd[cmd.index("--model") + 1]
            raise RuntimeError(
                f"Claude Code process failed (exit code {process.returncode}). "
                f"Model: {model}, cwd: {workspace_path}. "
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
    except json.JSONDecodeError:
        return stdout
    result = data.get("result", "")
    return result if isinstance(result, str) else ""
