"""Claude Code CLI subprocess evaluator backend."""

from __future__ import annotations

from pathlib import Path

from nasde_toolkit.config import EvaluationConfig


class ClaudeSubprocessBackend:
    """Evaluator backend that spawns `claude -p` as a subprocess."""

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
