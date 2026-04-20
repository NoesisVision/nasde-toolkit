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
