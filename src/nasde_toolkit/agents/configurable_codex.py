"""Configurable Codex agent for Harbor evaluations.

Harbor's built-in Codex agent handles CLI installation, command construction,
token/trajectory parsing, and — since harbor 0.4 — ChatGPT OAuth auth.json
injection natively (via ``~/.codex/auth.json`` or ``CODEX_AUTH_JSON_PATH``).

``ConfigurableCodex`` fills two remaining gaps:

1. A ``sandbox_files`` mapping (via ``AgentConfig.kwargs``) that uploads
   arbitrary files (e.g. ``AGENTS.md``) into the container during ``setup()``.
2. A DNS-resolver fallback for cloud sandboxes whose default resolver cannot
   reach ``api.openai.com``.

Everything else (auth, model selection, reasoning effort) stays in Harbor.

Usage in harbor_config.json::

    {
      "agents": [{
        "import_path": "nasde_toolkit.agents.configurable_codex:ConfigurableCodex",
        "model_name": "o3",
        "kwargs": {
          "sandbox_files": {
            "/app/AGENTS.md": "path/to/AGENTS.md"
          }
        }
      }]
    }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment

logger = logging.getLogger(__name__)

_DNS_FIX_COMMAND = (
    "timeout 5 getent hosts api.openai.com >/dev/null 2>&1"
    " || printf 'nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n' > /etc/resolv.conf"
)


class ConfigurableCodex(Codex):
    """Codex with declarative file injection into the sandbox.

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
        return "configurable-codex"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Fix cloud DNS, run base setup, then upload configured files."""
        await self._ensure_dns_resolution(environment)
        await super().setup(environment)
        await self._upload_sandbox_files(environment)

    async def _ensure_dns_resolution(self, environment: BaseEnvironment) -> None:
        """Prepend public DNS resolvers if cloud sandbox cannot reach OpenAI.

        Cloud sandboxes (Daytona, Modal, etc.) may land on runners whose DNS
        resolvers cannot reach whitelisted domains.  Prepending Google/Cloudflare
        public resolvers fixes this without affecting local Docker environments.
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
            parent_dir = str(Path(target_path).parent)
            await environment.exec(command=f"mkdir -p {parent_dir}")
            await environment.upload_file(
                source_path=resolved,
                target_path=target_path,
            )
