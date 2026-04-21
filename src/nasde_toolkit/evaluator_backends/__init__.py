"""Pluggable evaluator backends for nasde assessment evaluation."""

from __future__ import annotations

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends.protocol import EvaluatorBackend

__all__ = ["EvaluatorBackend", "create_backend"]


def create_backend(eval_config: EvaluationConfig) -> EvaluatorBackend:
    if eval_config.backend == "claude":
        from nasde_toolkit.evaluator_backends.claude_subprocess import ClaudeSubprocessBackend

        return ClaudeSubprocessBackend()
    elif eval_config.backend == "codex":
        from nasde_toolkit.evaluator_backends.codex_subprocess import CodexSubprocessBackend

        return CodexSubprocessBackend()
    else:
        raise ValueError(f"Unknown evaluator backend: '{eval_config.backend}'. Supported: 'claude', 'codex'")
