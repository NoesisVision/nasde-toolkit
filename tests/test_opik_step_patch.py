"""ADR-006 Opik Step patch: exactly one span per Harbor Step, carrying token usage.

``track_harbor()`` wraps ``Step.__init__`` to emit a span eagerly (before Harbor
assigns ``metrics``). nasde's deferred patch runs after it and must replace that
behaviour, not stack on top of it — otherwise every step is emitted twice and
Opik's trace token totals double-count when metrics arrive in the constructor.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import opik
import pytest
from harbor.models.trajectories.metrics import Metrics
from harbor.models.trajectories.step import Step
from opik import opik_context
from opik.integrations.harbor import opik_tracker

from nasde_toolkit import runner

TIMESTAMP = "2026-10-15T00:00:00Z"


class _RecordingClient:
    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    def __internal_api__span__(self, **kwargs: Any) -> None:
        self.spans.append(kwargs)


@pytest.fixture
def recording_client() -> Iterator[_RecordingClient]:
    original_init = Step.__init__
    original_setattr = Step.__setattr__
    client = _RecordingClient()
    fake_trace = type("FakeTrace", (), {"id": "trace-1", "project_name": "proj"})()
    with (
        patch.object(opik, "get_global_client", return_value=client),
        patch.object(opik_context, "get_current_trace_data", return_value=fake_trace),
        patch.object(opik_context, "get_current_span_data", return_value=None),
    ):
        opik_tracker._patch_step_class()
        runner._patch_opik_deferred_metrics()
        yield client
    Step.__init__ = original_init  # type: ignore[method-assign]
    Step.__setattr__ = original_setattr  # type: ignore[method-assign]
    for patch_fn, flag in (
        (opik_tracker._patch_step_class, "_patched"),
        (runner._patch_opik_deferred_metrics, "_applied"),
    ):
        if hasattr(patch_fn, flag):
            delattr(patch_fn, flag)


def _metrics() -> Metrics:
    return Metrics(prompt_tokens=100, completion_tokens=10)


def test_step_with_metrics_in_constructor_emits_one_span(recording_client: _RecordingClient) -> None:
    Step(step_id=1, source="agent", message="m", timestamp=TIMESTAMP, model_name="gpt-6-luna", metrics=_metrics())

    assert [span["name"] for span in recording_client.spans] == ["step_1"]
    assert recording_client.spans[0]["usage"]["total_tokens"] == 110


def test_step_with_metrics_assigned_later_emits_one_span_with_usage(recording_client: _RecordingClient) -> None:
    step = Step(step_id=2, source="agent", message="m", timestamp=TIMESTAMP, model_name="claude-sonnet-5-5")
    step.metrics = _metrics()

    assert [span["name"] for span in recording_client.spans] == ["step_2"]
    assert recording_client.spans[0]["usage"]["total_tokens"] == 110


def test_non_agent_step_emits_one_span(recording_client: _RecordingClient) -> None:
    Step(step_id=3, source="user", message="task", timestamp=TIMESTAMP)

    assert [span["name"] for span in recording_client.spans] == ["step_3"]
