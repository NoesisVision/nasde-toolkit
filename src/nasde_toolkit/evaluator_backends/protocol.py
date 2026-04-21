"""Evaluator backend protocol — defines the interface for CLI-based evaluators."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from nasde_toolkit.config import EvaluationConfig


@runtime_checkable
class EvaluatorBackend(Protocol):
    """Interface for subprocess-based evaluator backends.

    Each backend spawns a CLI agent (claude, codex, etc.) as a subprocess,
    passes the evaluation prompt, and returns the agent's text response.
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str: ...

    def validate_auth(self) -> None: ...
