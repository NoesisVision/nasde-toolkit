"""Configurable Claude Code agent for Harbor evaluations.

Harbor's built-in ClaudeCode agent handles MCP servers declared in the JSON
config and reads authentication credentials from the environment natively.
However, it has no mechanism to inject arbitrary files (e.g. CLAUDE.md) into
the sandbox before the agent starts.

ConfigurableClaude fills that single gap: it accepts a sandbox_files mapping
via AgentConfig.kwargs and uploads each file into the container during setup().
Everything else (auth, MCP servers, model selection) stays in the JSON config.

Usage in harbor_config.json::

    {
      "agents": [{
        "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
        "model_name": "claude-sonnet-4-6",
        "kwargs": {
          "sandbox_files": {
            "/app/CLAUDE.md": "path/to/CLAUDE.md"
          }
        }
      }]
    }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment

logger = logging.getLogger(__name__)

_DNS_FIX_COMMAND = (
    "timeout 5 getent hosts claude.ai >/dev/null 2>&1"
    " || printf 'nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n' > /etc/resolv.conf"
)


class ConfigurableClaude(ClaudeCode):
    """ClaudeCode with declarative file injection into the sandbox.

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
        return "configurable-claude-code"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Fix cloud DNS, upload files, then run base setup.

        Files must be uploaded BEFORE super().setup() because Harbor's
        ClaudeCode.setup() copies skills from ~/.claude/skills/ into
        the Claude config directory. Our sandbox_files that target
        ~/.claude/skills/ need to be in place before that copy happens.
        """
        await self._ensure_dns_resolution(environment)
        await self._upload_sandbox_files(environment)
        await super().setup(environment)

    async def _ensure_dns_resolution(self, environment: BaseEnvironment) -> None:
        """Prepend 1.1.1.1 to resolv.conf if missing.

        Daytona cloud sandboxes may land on runners whose DNS resolvers
        cannot reach whitelisted domains (e.g. claude.ai).  Prepending
        Cloudflare's public resolver fixes this without affecting local
        Docker environments (Docker regenerates resolv.conf on start).
        """
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
    """Expand a skill target path to include both /app/ and ~/.claude/ locations.

    Harbor's ClaudeCode.setup() copies skills from ~/.claude/skills/ into
    its internal config directory. Skills placed only under /app/.claude/
    won't be discovered. This ensures skills are available in both locations.
    """
    app_skills_prefix = "/app/.claude/skills/"
    if target_path.startswith(app_skills_prefix):
        relative = target_path[len(app_skills_prefix) :]
        home_path = f"/root/.claude/skills/{relative}"
        return [target_path, home_path]
    return [target_path]
