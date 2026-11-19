"""Configurable Cursor CLI agent for Harbor evaluations.

Harbor's built-in CursorCli installs ``cursor-agent``, runs it headless, parses
its stream-json output into an ATIF trajectory, copies Harbor's native skills
(``config.agent.skills``) into ``~/.cursor/skills`` (ADR-012) and writes the
task's MCP servers to ``~/.cursor/mcp.json``. It lacks two things nasde needs:

1. Injecting arbitrary files (``AGENTS.md``) into the sandbox before the agent
   starts. ConfigurableCursor accepts a ``sandbox_files`` mapping via
   ``AgentConfig.kwargs`` and uploads each file during ``setup()``.
2. Approving the MCP servers it registers. A ``--print`` run cannot answer
   ``cursor-agent``'s approval prompt, so ``--approve-mcps`` is appended whenever
   the task declares MCP servers.

Authentication is ``CURSOR_API_KEY`` only (checked by the runner's
``_ensure_auth``; Harbor forwards it into the sandbox). Model names arrive
``cursor/``-qualified (the runner adds the prefix), the ``provider/model`` form
``CursorCli`` requires. See ADR-015.

Usage in harbor_config.json::

    {
      "agents": [{
        "import_path": "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor",
        "model_name": "cursor/composer-2.5",
        "kwargs": {
          "sandbox_files": {
            "/app/AGENTS.md": "path/to/AGENTS.md"
          }
        }
      }]
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

from harbor.agents.installed.cursor_cli import CursorCli, CursorCliOptions
from harbor.environments.base import BaseEnvironment
from pydantic import Field


class ConfigurableCursorOptions(CursorCliOptions):
    """CursorCliOptions plus nasde's ``sandbox_files`` kwarg.

    Harbor's preflight validates raw kwargs against ``options_model`` with
    ``extra="forbid"`` before the agent is constructed, so every nasde kwarg
    must be declared here. The field has no ``Cli``/``Env`` annotation and is
    therefore never rendered into the agent command or environment.
    """

    sandbox_files: dict[str, str] | None = Field(
        default=None,
        description="Container path -> host file path, uploaded into the sandbox during setup().",
    )


class ConfigurableCursor(CursorCli):
    """CursorCli with declarative file injection and MCP auto-approval.

    Args:
        sandbox_files: Mapping of container paths to host file paths. Each entry
            is uploaded into the sandbox during setup() before Harbor installs
            the CLI. Paths are resolved relative to CWD.
    """

    options_model = ConfigurableCursorOptions

    def __init__(
        self,
        sandbox_files: dict[str, str] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._sandbox_files = sandbox_files or {}

    @staticmethod
    @override
    def name() -> str:
        return "configurable-cursor-cli"

    def build_cli_flags(self) -> str:
        """Harbor's flags, plus ``--approve-mcps`` when the task declares MCP servers."""
        harbor_flags: str = super().build_cli_flags()
        if not self.mcp_servers:
            return harbor_flags
        return f"{harbor_flags} --approve-mcps".strip()

    async def setup(self, environment: BaseEnvironment) -> None:
        """Upload sandbox files (e.g. AGENTS.md), then run Harbor's install."""
        await self._upload_sandbox_files(environment)
        await super().setup(environment)

    async def _upload_sandbox_files(self, environment: BaseEnvironment) -> None:
        for target_path, source_path in self._sandbox_files.items():
            resolved = Path(source_path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(
                    f"sandbox_files: source '{source_path}' (resolved to '{resolved}') does not exist"
                )
            parent_dir = str(Path(target_path).parent)
            await environment.exec(command=f"mkdir -p {parent_dir}")
            await environment.upload_file(
                source_path=resolved,
                target_path=target_path,
            )
