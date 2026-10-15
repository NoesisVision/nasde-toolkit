"""Harbor >=0.20 validates raw agent kwargs in a class-level preflight.

The preflight runs before any agent is constructed, against the agent's
``options_model`` (``extra="forbid"``). nasde-specific kwargs such as
``sandbox_files`` must therefore be declared on the options model, not only
consumed in ``__init__``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit.agents.configurable_claude import ConfigurableClaude
from nasde_toolkit.agents.configurable_codex import ConfigurableCodex
from nasde_toolkit.agents.configurable_gemini import ConfigurableGemini

AGENT_CASES = [
    (ConfigurableClaude, "claude-sonnet-5-5", "/app/CLAUDE.md"),
    (ConfigurableCodex, "gpt-6.1-sol", "/app/AGENTS.md"),
    (ConfigurableGemini, "google/gemini-3-flash-preview", "/app/GEMINI.md"),
]


@pytest.mark.parametrize(("agent_class", "model_name", "sandbox_path"), AGENT_CASES)
def test_preflight_accepts_nasde_kwargs(agent_class: type, model_name: str, sandbox_path: str) -> None:
    kwargs = {"sandbox_files": {sandbox_path: "/tmp/instructions.md"}, "reasoning_effort": "high"}
    agent_class.preflight(kwargs=kwargs, env={})


@pytest.mark.parametrize(("agent_class", "model_name", "sandbox_path"), AGENT_CASES)
def test_preflight_still_rejects_unknown_kwargs(agent_class: type, model_name: str, sandbox_path: str) -> None:
    with pytest.raises(ValueError, match="Unknown option 'not_a_real_option'"):
        agent_class.preflight(kwargs={"not_a_real_option": 1}, env={})


@pytest.mark.parametrize(("agent_class", "model_name", "sandbox_path"), AGENT_CASES)
def test_sandbox_files_never_rendered_as_cli_flag_or_env(agent_class: type, model_name: str, sandbox_path: str) -> None:
    agent = agent_class(
        sandbox_files={sandbox_path: "/tmp/instructions.md"},
        logs_dir=Path("/tmp/logs"),
        model_name=model_name,
    )
    assert agent._sandbox_files == {sandbox_path: "/tmp/instructions.md"}
    assert "instructions.md" not in agent.compile_cli_flags()
    assert not any("instructions.md" in value for value in agent.compile_env_vars().values())
