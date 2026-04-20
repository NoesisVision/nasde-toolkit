from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends import EvaluatorBackend, create_backend


def test_create_backend_returns_claude_by_default() -> None:
    config = EvaluationConfig()
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_returns_codex_when_configured() -> None:
    config = EvaluationConfig(backend="codex")
    backend = create_backend(config)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_raises_on_unknown() -> None:
    config = EvaluationConfig(backend="unknown-agent")
    with pytest.raises(ValueError, match="Unknown evaluator backend"):
        create_backend(config)
