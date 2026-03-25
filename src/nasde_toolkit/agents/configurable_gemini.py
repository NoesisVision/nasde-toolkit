"""Configurable Gemini CLI agent for Harbor evaluations.

Harbor's built-in GeminiCli agent handles CLI installation, command construction,
trajectory parsing, and MCP server configuration natively.  However, it has no
mechanism to inject arbitrary files (e.g. GEMINI.md, skills) into the sandbox
before the agent starts.

ConfigurableGemini fills that gap: it accepts a sandbox_files mapping via
AgentConfig.kwargs and uploads each file into the container during setup().

Additionally, when the user has authenticated via ``gemini login`` (Google
account), ConfigurableGemini auto-detects ``~/.gemini/oauth_creds.json`` and
injects the credentials into the sandbox — allowing benchmarks to run on a
Google account instead of requiring a ``GEMINI_API_KEY``.  API key env vars
always take priority over OAuth.

Usage in harbor_config.json::

    {
      "agents": [{
        "import_path": "nasde_toolkit.agents.configurable_gemini:ConfigurableGemini",
        "model_name": "google/gemini-3-flash-preview",
        "kwargs": {
          "sandbox_files": {
            "/app/GEMINI.md": "path/to/GEMINI.md"
          }
        }
      }]
    }
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from harbor.agents.installed.base import ExecInput
from harbor.agents.installed.gemini_cli import GeminiCli
from harbor.environments.base import BaseEnvironment

logger = logging.getLogger(__name__)

_DNS_FIX_COMMAND = (
    "timeout 5 getent hosts generativelanguage.googleapis.com >/dev/null 2>&1"
    " || printf 'nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n' > /etc/resolv.conf"
)

_API_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")


def _read_gemini_oauth_creds() -> str | None:
    """Return serialised ``~/.gemini/oauth_creds.json`` when it holds OAuth tokens."""
    creds_path = Path.home() / ".gemini" / "oauth_creds.json"
    if not creds_path.exists():
        return None
    try:
        raw = json.loads(creds_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not raw:
        return None
    return json.dumps(raw)


def _inject_oauth_creds(commands: list[ExecInput], oauth_creds_json: str) -> list[ExecInput]:
    """Inject OAuth credentials into the sandbox environment."""
    result: list[ExecInput] = []
    for i, cmd in enumerate(commands):
        env = dict(cmd.env) if cmd.env else {}
        if i == 0:
            env["_GEMINI_OAUTH_CREDS_JSON"] = oauth_creds_json
            result.append(
                ExecInput(
                    command=_build_oauth_setup(cmd.command),
                    env=env,
                )
            )
        else:
            result.append(ExecInput(command=cmd.command, env=env))
    return result


def _build_oauth_setup(original_setup: str) -> str:
    """Build OAuth credential injection command, preserving original setup."""
    oauth_lines = (
        "mkdir -p /tmp/gemini-secrets\n"
        "printf '%s' \"$_GEMINI_OAUTH_CREDS_JSON\" > /tmp/gemini-secrets/oauth_creds.json\n"
        "mkdir -p ~/.gemini\n"
        "ln -sf /tmp/gemini-secrets/oauth_creds.json ~/.gemini/oauth_creds.json"
    )
    return oauth_lines + "\n" + original_setup


class ConfigurableGemini(GeminiCli):
    """GeminiCli with declarative file injection into the sandbox.

    Args:
        sandbox_files: Mapping of container paths to host-relative file paths.
            Each entry is uploaded into the sandbox during setup() before
            the agent starts. Paths are resolved relative to CWD.
    """

    def __init__(
        self,
        sandbox_files: dict[str, str] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._sandbox_files = sandbox_files or {}

    @staticmethod
    def name() -> str:
        return "configurable-gemini-cli"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Fix cloud DNS, upload files, then run base setup.

        Files must be uploaded BEFORE super().setup() because Harbor's
        GeminiCli.setup() writes MCP and skills configuration.  Our
        sandbox_files that target ~/.gemini/skills/ need to be in place
        before that happens.
        """
        await self._ensure_dns_resolution(environment)
        await self._upload_sandbox_files(environment)
        await super().setup(environment)

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Inject OAuth credentials when no API key is set.

        Priority:
        1. GEMINI_API_KEY / GOOGLE_API_KEY / GOOGLE_APPLICATION_CREDENTIALS → API key mode
        2. ~/.gemini/oauth_creds.json → OAuth mode (injected into sandbox)
        """
        commands: list[ExecInput] = super().create_run_agent_commands(instruction)

        has_api_key = any(os.environ.get(var) for var in _API_KEY_VARS)
        if has_api_key:
            return commands

        oauth_creds_json = _read_gemini_oauth_creds()
        if oauth_creds_json:
            logger.info("Using Gemini OAuth credentials from ~/.gemini/oauth_creds.json")
            return _inject_oauth_creds(commands, oauth_creds_json)

        return commands

    async def _ensure_dns_resolution(self, environment: BaseEnvironment) -> None:
        """Prepend public DNS resolvers if cloud sandbox cannot reach Google APIs."""
        result = await environment.exec(command=_DNS_FIX_COMMAND)
        if result.return_code == 0:
            logger.debug("DNS resolution fix applied")
        else:
            logger.warning("DNS resolution fix failed: %s", result.stderr)

    async def _upload_sandbox_files(self, environment: BaseEnvironment) -> None:
        for target_path, source_path in self._sandbox_files.items():
            resolved = Path(source_path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(
                    f"sandbox_files: source '{source_path}' (resolved to '{resolved}') does not exist"
                )
            upload_targets = _expand_skill_targets(target_path)
            for upload_path in upload_targets:
                parent_dir = str(Path(upload_path).parent)
                await environment.exec(command=f"mkdir -p {parent_dir}")
                await environment.upload_file(
                    source_path=resolved,
                    target_path=upload_path,
                )


def _expand_skill_targets(target_path: str) -> list[str]:
    """Expand a skill target path to include both /app/ and ~/.gemini/ locations.

    Gemini CLI discovers skills in both workspace (.gemini/skills/) and user
    (~/.gemini/skills/) directories.  This ensures skills are available in both.
    """
    app_skills_prefix = "/app/.gemini/skills/"
    if target_path.startswith(app_skills_prefix):
        relative = target_path[len(app_skills_prefix) :]
        home_path = f"/root/.gemini/skills/{relative}"
        return [target_path, home_path]
    return [target_path]
