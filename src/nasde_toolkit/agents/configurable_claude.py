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

from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment


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
        """Run base setup then upload configured files into the sandbox."""
        await super().setup(environment)
        await self._upload_sandbox_files(environment)

    async def _upload_sandbox_files(self, environment: BaseEnvironment) -> None:
        for target_path, source_path in self._sandbox_files.items():
            resolved = Path(source_path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(
                    f"sandbox_files: source '{source_path}' "
                    f"(resolved to '{resolved}') does not exist"
                )
            parent_dir = str(Path(target_path).parent)
            await environment.exec(command=f"mkdir -p {parent_dir}")
            await environment.upload_file(
                source_path=resolved,
                target_path=target_path,
            )
