# Cursor Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Cursor (`cursor-agent`) as a fourth agent family and a third judge backend, as close as possible to Claude support.

**Architecture:** A thin `ConfigurableCursor` subclass of Harbor's `CursorCli` (sandbox files, DNS fix, per-step metrics for Opik), runner wiring that mirrors the Gemini/Codex families, a `cursor` judge backend mirroring `claude_subprocess.py`, and Cursor-aware pricing (bundled list prices, rates fed into Harbor's `pricing` kwarg, Harbor-cost fallback with `cost_source` provenance).

**Tech Stack:** Python 3.12+, Harbor 0.24 (`harbor.agents.installed.cursor_cli`), Typer/Rich, pytest, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-11-23-cursor-support-design.md` · **ADR:** `docs/adr/015-cursor-agent-and-judge.md`

## Global Constraints

- Code style (CLAUDE.md): type hints on public functions; **no comments in method bodies**; public functions first (alphabetical), then private helpers caller-before-callee; Rich console output only, no `print()`.
- Agent type string: `"cursor"`. Variant model format: `cursor/<base-slug>` (e.g. `cursor/composer-2.5`). Effort via `reasoning_effort`, never via effort-suffixed slugs.
- Skills subdir: `cursor_skills/`. Instructions file: `AGENTS.md` → `/app/AGENTS.md`.
- Auth env var: `CURSOR_API_KEY`.
- Judge base command: `cursor-agent -p --output-format json --trust --mode ask --model <model-without-cursor/-prefix>`.
- Bundled prices: `as_of = "2026-11-23"`, `source = "https://cursor.com/docs/models-and-pricing"`, no Teams surcharge.
- `cost_source` values: `"pricing.toml"`, `"harbor:<extra.cost_source>"`, or `null`.
- Harbor-cost fallback applies only to models starting with `cursor/`.
- No LLM calls in unit tests. Every e2e run requires explicit user authorization.
- Quality gates before every commit: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/nasde_toolkit/ && uv run pytest -q`.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/nasde_toolkit/token_metrics.py` | Modify | Cursor cache-write fallback; `cost_source`; Harbor-cost fallback for `cursor/*` |
| `src/nasde_toolkit/evaluator.py` | Modify | `AssessmentSummary.cost_source` |
| `src/nasde_toolkit/results_exporter.py` | Modify | `metrics.json` `cost_source` |
| `src/nasde_toolkit/pricing.toml` | Modify | 3 `cursor/*` entries + header note |
| `src/nasde_toolkit/agents/configurable_cursor.py` | Create | Harbor `CursorCli` subclass |
| `src/nasde_toolkit/runner.py` | Modify | `cursor` agent family wiring, auth, `pricing` kwarg injection |
| `src/nasde_toolkit/cli.py` | Modify | Agent label, `--effort` help, `--eval-backend cursor` |
| `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py` | Create | `cursor-agent -p` judge |
| `src/nasde_toolkit/evaluator_backends/__init__.py` | Modify | Register `cursor` backend |
| `scripts/export_cursor_api_key.sh`, `.ps1` | Create | Export `CURSOR_API_KEY` |
| `examples/*/variants/cursor-vanilla/` | Create | Example variants |
| Docs + skills + scaffold | Modify | User-facing documentation |
| `tests/test_token_metrics.py`, `tests/test_configurable_cursor.py`, `tests/test_configurable_agents_options.py`, `tests/test_runner.py`, `tests/test_evaluator_backends.py`, `tests/test_pricing.py` | Modify/Create | Tests |

---

### Task 1: Economics — Cursor cache writes, `cost_source`, Harbor-cost fallback

**Files:**
- Modify: `src/nasde_toolkit/token_metrics.py`
- Modify: `src/nasde_toolkit/evaluator.py:103-125` (dataclass) and `:894-901` (`_enrich_with_economics`)
- Modify: `src/nasde_toolkit/results_exporter.py:184-208` (`_build_metrics`)
- Test: `tests/test_token_metrics.py`

**Interfaces:**
- Produces: `token_metrics.CURSOR_MODEL_PREFIX = "cursor/"`; `build_trial_economics(...)` dict gains key `"cost_source": str | None`; `AssessmentSummary.cost_source: str | None = None`; `metrics.json` key `cost_source`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_token_metrics.py`:

```python
from nasde_toolkit.pricing import ModelPrice

CURSOR_TRAJ = {
    "final_metrics": {
        "total_prompt_tokens": 1_000_000,
        "total_completion_tokens": 20_000,
        "total_cached_tokens": 900_000,
        "total_cost_usd": 0.42,
        "extra": {
            "usage_totals": {
                "inputTokens": 60_000,
                "outputTokens": 20_000,
                "cacheReadTokens": 900_000,
                "cacheWriteTokens": 40_000,
            },
            "cost_source": "litellm",
        },
    }
}

COMPOSER_PRICE = ModelPrice(input_per_1m=0.5, output_per_1m=2.5, cached_input_per_1m=0.2, as_of="2026-11-23")


def _write_traj(trial_dir: Path, traj: dict) -> None:
    (trial_dir / "agent").mkdir()
    (trial_dir / "agent" / "trajectory.json").write_text(json.dumps(traj))


def test_extract_cursor_reads_cache_writes_from_usage_totals() -> None:
    usage = extract_token_usage(CURSOR_TRAJ)
    assert usage is not None
    assert usage.cache_write_tokens == 40_000
    assert usage.cached_tokens == 900_000


def test_build_trial_economics_catalog_priced_has_pricing_toml_source(tmp_path: Path) -> None:
    _write_traj(tmp_path, CODEX_TRAJ)
    econ = build_trial_economics(tmp_path, "gpt-6.1-sol", load_pricing())
    assert econ["cost_source"] == "pricing.toml"


def test_build_trial_economics_cursor_catalog_price_wins_over_harbor(tmp_path: Path) -> None:
    _write_traj(tmp_path, CURSOR_TRAJ)
    econ = build_trial_economics(tmp_path, "cursor/composer-2.5", {"cursor/composer-2.5": COMPOSER_PRICE})
    fresh = 1_000_000 - 900_000 - 40_000
    expected = fresh / 1e6 * 0.5 + 40_000 / 1e6 * 0.5 + 900_000 / 1e6 * 0.2 + 20_000 / 1e6 * 2.5
    assert econ["cost_usd"] == pytest.approx(expected)
    assert econ["cost_source"] == "pricing.toml"
    assert econ["pricing_as_of"] == "2026-11-23"


def test_build_trial_economics_unpriced_cursor_falls_back_to_harbor(tmp_path: Path) -> None:
    _write_traj(tmp_path, CURSOR_TRAJ)
    econ = build_trial_economics(tmp_path, "cursor/some-new-model", {})
    assert econ["cost_usd"] == pytest.approx(0.42)
    assert econ["cost_source"] == "harbor:litellm"
    assert econ["pricing_as_of"] is None
    assert econ["token_usage"]["cache_write_tokens"] == 40_000


def test_build_trial_economics_unpriced_cursor_without_harbor_cost_is_none(tmp_path: Path) -> None:
    traj = json.loads(json.dumps(CURSOR_TRAJ))
    del traj["final_metrics"]["total_cost_usd"]
    _write_traj(tmp_path, traj)
    econ = build_trial_economics(tmp_path, "cursor/some-new-model", {})
    assert econ["cost_usd"] is None
    assert econ["cost_source"] is None


def test_build_trial_economics_unpriced_non_cursor_ignores_harbor_cost(tmp_path: Path) -> None:
    _write_traj(tmp_path, CURSOR_TRAJ)
    econ = build_trial_economics(tmp_path, "claude-haiku-5-5", {})
    assert econ["cost_usd"] is None
    assert econ["cost_source"] is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_token_metrics.py -q`
Expected: FAIL — `KeyError: 'cost_source'` and cache-write assertion `0 == 40000`.

- [ ] **Step 3: Implement in `src/nasde_toolkit/token_metrics.py`**

Update the module docstring line for cache writes to:
```
  cache_write = extra.total_cache_creation_input_tokens  (Claude)
                or extra.usage_totals.cacheWriteTokens   (Cursor)
```
and append to the docstring: `Cursor models (``cursor/*``) missing from the catalog fall back to Harbor's own trajectory cost (``final_metrics.total_cost_usd``); ``cost_source`` records where every figure came from (ADR-015).`

Add imports and constants below the existing imports:

```python
from rich.console import Console

console = Console()

CURSOR_MODEL_PREFIX = "cursor/"
```

Replace the `cache_write_tokens` line in `extract_token_usage`:

```python
    cache_write_tokens = _cache_write_tokens(extra)
```

Replace `build_trial_economics` and `_empty_economics`, and add helpers (order: `build_trial_economics` stays in the public block; helpers after `read_trajectory`… keep private helpers at the bottom, caller before callee):

```python
def build_trial_economics(
    trial_dir: Path,
    model: str,
    pricing: dict[str, ModelPrice],
) -> dict:
    """Assemble the economics block for one trial (used by run and export paths).

    Only raw, baseline-invariant signals are recorded — token volumes, USD cost,
    the price catalog date and the cost's source. Quality-vs-cost comparison is a
    Pareto front over these raw axes (in the nasde-benchmark-runner skill), not a
    scalar score/cost ratio whose zero point is arbitrary. See ADR-011. A Cursor
    model absent from the catalog uses Harbor's trajectory cost (ADR-015).
    """
    trajectory = read_trajectory(trial_dir)
    usage = extract_token_usage(trajectory) if trajectory is not None else None
    if trajectory is None or usage is None:
        return _empty_economics(model)
    if model not in pricing and model.startswith(CURSOR_MODEL_PREFIX):
        return _harbor_estimated_economics(model, usage, trajectory)
    cost_usd = compute_cost_usd(
        usage.input_tokens,
        usage.output_tokens,
        model,
        pricing,
        cache_read_tokens=usage.cached_tokens,
        cache_write_tokens=usage.cache_write_tokens,
    )
    return {
        "model_name": model,
        "token_usage": asdict(usage),
        "cost_usd": cost_usd,
        "pricing_as_of": pricing_as_of(model, pricing) if cost_usd is not None else None,
        "cost_source": "pricing.toml" if cost_usd is not None else None,
    }
```

```python
def _cache_write_tokens(extra: dict) -> int:
    claude_writes = extra.get("total_cache_creation_input_tokens")
    if claude_writes:
        return int(claude_writes)
    usage_totals = extra.get("usage_totals") or {}
    return int(usage_totals.get("cacheWriteTokens", 0) or 0)


def _harbor_estimated_economics(model: str, usage: TokenUsage, trajectory: dict) -> dict:
    final_metrics = trajectory.get("final_metrics") or {}
    cost_usd = final_metrics.get("total_cost_usd")
    harbor_source = (final_metrics.get("extra") or {}).get("cost_source", "unknown")
    cost_source = f"harbor:{harbor_source}" if cost_usd is not None else None
    console.print(
        f"  [yellow]No pricing for model {model!r} in pricing.toml — "
        f"{'using Harbor estimate (' + cost_source + ')' if cost_source else 'cost left unset'}. "
        f"Add it to pricing.toml for catalog-priced cost.[/yellow]"
    )
    return {
        "model_name": model,
        "token_usage": asdict(usage),
        "cost_usd": cost_usd,
        "pricing_as_of": None,
        "cost_source": cost_source,
    }


def _empty_economics(model: str) -> dict:
    return {
        "model_name": model,
        "token_usage": None,
        "cost_usd": None,
        "pricing_as_of": None,
        "cost_source": None,
    }
```

- [ ] **Step 4: Thread `cost_source` into both write paths**

`src/nasde_toolkit/evaluator.py` — add to `AssessmentSummary` after `pricing_as_of`:
```python
    cost_source: str | None = None
```
and to `_enrich_with_economics` after the `pricing_as_of` line:
```python
    summary.cost_source = economics["cost_source"]
```

`src/nasde_toolkit/results_exporter.py` — in `_build_metrics`, after `"pricing_as_of": economics["pricing_as_of"],` add:
```python
        "cost_source": economics["cost_source"],
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_token_metrics.py tests/test_evaluator.py tests/test_results_exporter.py tests/test_runner_economics.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/nasde_toolkit/token_metrics.py src/nasde_toolkit/evaluator.py src/nasde_toolkit/results_exporter.py tests/test_token_metrics.py
git commit -m "feat(economics): cost_source provenance, Cursor cache writes, Harbor-cost fallback for cursor/* models"
```

---

### Task 2: Bundled Cursor prices

**Files:**
- Modify: `src/nasde_toolkit/pricing.toml` (header comment + 3 entries at end)
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: catalog keys `cursor/composer-2.5`, `cursor/claude-opus-5-5`, `cursor/claude-sonnet-5-5`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_pricing.py`:

```python
def test_bundled_cursor_entries_use_cursor_list_rates() -> None:
    pricing = load_pricing()
    composer = pricing["cursor/composer-2.5"]
    assert (composer.input_per_1m, composer.cached_input_per_1m, composer.output_per_1m) == (0.5, 0.2, 2.5)
    assert composer.cache_write_per_1m is None
    opus = pricing["cursor/claude-opus-5-5"]
    assert (opus.input_per_1m, opus.cache_write_per_1m, opus.cached_input_per_1m, opus.output_per_1m) == (
        4.0,
        5.0,
        0.20,
        20.0,
    )
    sonnet = pricing["cursor/claude-sonnet-5-5"]
    assert (sonnet.input_per_1m, sonnet.cache_write_per_1m, sonnet.cached_input_per_1m, sonnet.output_per_1m) == (
        2.0,
        2.5,
        0.10,
        10.0,
    )
    assert {p.as_of for p in (composer, opus, sonnet)} == {"2026-11-23"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_pricing.py::test_bundled_cursor_entries_use_cursor_list_rates -q`
Expected: FAIL with `KeyError: 'cursor/composer-2.5'`

- [ ] **Step 3: Add entries** — append to the header comment block of `src/nasde_toolkit/pricing.toml` (before the first `[models.…]`):

```toml
#
# Cursor (cursor/*) entries are Cursor's published list rates for models run
# through cursor-agent (ADR-015). Cursor-owned models (Composer) draw from the
# plan's weekly pool first; these are the rates beyond it. Third-party models
# via Cursor bill at Cursor's listed API rates, whose cache write is 1.25x
# input — NOT the 2x 1-hour rate of the direct claude-* entries above. Teams /
# Enterprise plans add a "Cursor Token Rate" of +$0.25/M on input, output and
# cached tokens for third-party models; it is plan-specific and NOT included —
# add it via a project or ~/.nasde pricing.toml override (ADR-013). Keys use the
# base slug; set effort with reasoning_effort, not Cursor's -low/-high slugs.
# A cursor/* model missing here falls back to Harbor's own estimate
# (cost_source = "harbor:...").
```

Append at the end of the file:

```toml

[models."cursor/composer-2.5"]
input_per_1m = 0.5
output_per_1m = 2.5
cached_input_per_1m = 0.2
as_of = "2026-11-23"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-opus-5-5"]
input_per_1m = 4.0
output_per_1m = 20.0
cached_input_per_1m = 0.20
cache_write_per_1m = 5.0
as_of = "2026-11-23"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-sonnet-5-5"]
input_per_1m = 2.0
output_per_1m = 10.0
cached_input_per_1m = 0.10
cache_write_per_1m = 2.5
as_of = "2026-11-23"
source = "https://cursor.com/docs/models-and-pricing"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_pricing.py tests/test_pricing_report.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/pricing.toml tests/test_pricing.py
git commit -m "feat(pricing): bundle Cursor list prices for composer-2.5 and Claude 5.5 via Cursor"
```

---

### Task 3: `ConfigurableCursor` agent

**Files:**
- Create: `src/nasde_toolkit/agents/configurable_cursor.py`
- Create: `tests/test_configurable_cursor.py`
- Modify: `tests/test_configurable_agents_options.py:15-22`

**Interfaces:**
- Consumes: Harbor `CursorCli` (`_build_agent_step`, `_apply_tool_call_event`, `_convert_events_to_trajectory`, `_resolve_pricing_rates`, `_cost_from_token_rates`).
- Produces: `nasde_toolkit.agents.configurable_cursor:ConfigurableCursor`, `name() == "configurable-cursor-cli"`, kwargs `sandbox_files`, `pricing`, `reasoning_effort`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_configurable_cursor.py`:

```python
"""Tests for ConfigurableCursor agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nasde_toolkit.agents.configurable_cursor import ConfigurableCursor

MODEL = "cursor/composer-2.5"

EVENTS = [
    {"type": "system", "subtype": "init", "apiKeySource": "env", "cwd": "/app", "session_id": "s1",
     "model": "composer-2.5", "permissionMode": "default"},
    {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "do it"}]}, "session_id": "s1"},
    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
     "session_id": "s1", "model_call_id": "m1", "timestamp_ms": 1_700_000_000_000},
    {"type": "usage", "subtype": "model_call", "model_call_id": "m1", "session_id": "s1",
     "usage": {"inputTokens": 100, "outputTokens": 50, "cacheReadTokens": 1_000, "cacheWriteTokens": 200}},
    {"type": "tool_call", "subtype": "completed", "call_id": "c1", "tool_call": {"readToolCall": {"args": {}}},
     "session_id": "s1", "model_call_id": "m2", "timestamp_ms": 1_700_000_001_000},
    {"type": "usage", "subtype": "model_call", "model_call_id": "m2", "session_id": "s1",
     "usage": {"inputTokens": 10, "outputTokens": 5, "cacheReadTokens": 2_000, "cacheWriteTokens": 0}},
    {"type": "result", "subtype": "success", "duration_ms": 10, "duration_api_ms": 10, "is_error": False,
     "result": "done", "session_id": "s1",
     "usage": {"inputTokens": 110, "outputTokens": 55, "cacheReadTokens": 3_000, "cacheWriteTokens": 200}},
]


def _agent(**kwargs: object) -> ConfigurableCursor:
    return ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL, **kwargs)


def test_name_returns_configurable_cursor_cli() -> None:
    assert ConfigurableCursor.name() == "configurable-cursor-cli"


def test_constructor_stores_sandbox_files() -> None:
    files = {"/app/AGENTS.md": "/tmp/AGENTS.md"}
    assert _agent(sandbox_files=files)._sandbox_files == files


def test_constructor_defaults_to_empty_sandbox_files() -> None:
    assert _agent()._sandbox_files == {}


def test_setup_calls_dns_fix_then_upload_then_parent() -> None:
    agent = _agent(sandbox_files={"/app/AGENTS.md": __file__})
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with patch.object(ConfigurableCursor.__bases__[0], "setup", new_callable=AsyncMock) as mock_parent_setup:
        asyncio.run(agent.setup(env))

    dns_call = env.exec.call_args_list[0]
    cmd = dns_call.kwargs.get("command", dns_call.args[0] if dns_call.args else "")
    assert "api2.cursor.sh" in cmd
    mock_parent_setup.assert_awaited_once_with(env)
    assert env.upload_file.await_count == 1


def test_upload_raises_on_missing_source() -> None:
    agent = _agent(sandbox_files={"/app/AGENTS.md": "/nonexistent/path.md"})
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")
    with (
        patch.object(ConfigurableCursor.__bases__[0], "setup", new_callable=AsyncMock),
        pytest.raises(FileNotFoundError, match="does not exist"),
    ):
        asyncio.run(agent.setup(env))


def test_trajectory_steps_get_per_call_metrics_and_cost() -> None:
    agent = _agent(pricing={"input": 0.5, "output": 2.5, "cache_read": 0.2})
    trajectory = agent._convert_events_to_trajectory(EVENTS)
    agent_steps = [s for s in trajectory.steps if s.source == "agent"]
    assert len(agent_steps) == 2

    first = agent_steps[0].metrics
    assert first is not None
    assert first.prompt_tokens == 100 + 1_000 + 200
    assert first.completion_tokens == 50
    assert first.cached_tokens == 1_000
    assert first.cost_usd == pytest.approx((100 * 0.5 + 200 * 0.5 + 1_000 * 0.2 + 50 * 2.5) / 1e6)

    second = agent_steps[1].metrics
    assert second is not None
    assert second.prompt_tokens == 10 + 2_000
    assert second.cost_usd == pytest.approx((10 * 0.5 + 2_000 * 0.2 + 5 * 2.5) / 1e6)


def test_trajectory_steps_without_rates_have_tokens_but_no_cost() -> None:
    agent = _agent()
    with patch.object(ConfigurableCursor, "_resolve_pricing_rates", return_value=None):
        trajectory = agent._convert_events_to_trajectory(EVENTS)
    first = next(s for s in trajectory.steps if s.source == "agent").metrics
    assert first is not None
    assert first.prompt_tokens == 1_300
    assert first.cost_usd is None


def test_user_steps_get_no_metrics() -> None:
    trajectory = _agent()._convert_events_to_trajectory(EVENTS)
    assert all(s.metrics is None for s in trajectory.steps if s.source == "user")
```

Add Cursor to `AGENT_CASES` in `tests/test_configurable_agents_options.py`:

```python
from nasde_toolkit.agents.configurable_cursor import ConfigurableCursor
...
    (ConfigurableCursor, "cursor/composer-2.5", "/app/AGENTS.md"),
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_configurable_cursor.py tests/test_configurable_agents_options.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'nasde_toolkit.agents.configurable_cursor'`

- [ ] **Step 3: Implement** — create `src/nasde_toolkit/agents/configurable_cursor.py`:

```python
"""Configurable Cursor CLI agent for Harbor evaluations.

Harbor's built-in CursorCli handles installing ``cursor-agent``, command
construction (``--yolo`` also auto-approves MCP servers), stream-json →
trajectory conversion, MCP registration (``~/.cursor/mcp.json``), native skill
injection (``config.agent.skills`` → ``~/.cursor/skills``), reasoning effort
(``model[effort=X]``) and cost estimation (its ``pricing`` kwarg, then a built-in
table, then LiteLLM). What CursorCli lacks:

1. A mechanism to inject arbitrary files (e.g. AGENTS.md) into the sandbox
   before the agent starts — ``sandbox_files``, as for ConfigurableClaude.
2. Per-step token/cost ``metrics``. CursorCli fills only ``final_metrics``, so
   nasde's deferred Opik span patch (ADR-006) never emitted Cursor agent spans.
   ``cursor-agent`` reports usage per model call (``type: usage``,
   ``subtype: model_call``); this class attaches it to the matching step so
   Opik gets per-step tokens and cost, as it does for Claude (ADR-015).

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

import logging
from pathlib import Path
from typing import Any

from harbor.agents.installed.cursor_cli import (
    CursorAssistantMessage,
    CursorCli,
    CursorCliOptions,
    CursorThinkingBlock,
    CursorToolCall,
)
from harbor.environments.base import BaseEnvironment
from harbor.models.trajectories import Metrics, Step, Trajectory
from pydantic import Field

logger = logging.getLogger(__name__)

_DNS_FIX_COMMAND = (
    "timeout 5 getent hosts api2.cursor.sh >/dev/null 2>&1"
    " || printf 'nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n' > /etc/resolv.conf"
)

_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens")


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
    """CursorCli with declarative file injection and per-step metrics.

    Args:
        sandbox_files: Mapping of container paths to host-relative file paths.
            Each entry is uploaded into the sandbox during setup() before
            the agent starts. Paths are resolved relative to CWD.
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
        self._model_call_step_ids: dict[str, int] = {}

    @staticmethod
    def name() -> str:
        return "configurable-cursor-cli"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Fix cloud DNS, upload files, then run base setup (installs cursor-agent)."""
        await self._ensure_dns_resolution(environment)
        await self._upload_sandbox_files(environment)
        await super().setup(environment)

    def _build_agent_step(
        self,
        event: CursorAssistantMessage,
        step_id: int,
        thinking: list[CursorThinkingBlock],
    ) -> Step:
        if event.model_call_id is not None:
            self._model_call_step_ids.setdefault(event.model_call_id, step_id)
        return super()._build_agent_step(event, step_id, thinking)

    def _apply_tool_call_event(self, event: CursorToolCall, step: Step) -> None:  # type: ignore[override]
        self._model_call_step_ids.setdefault(event.model_call_id, step.step_id)
        CursorCli._apply_tool_call_event(event, step)

    def _convert_events_to_trajectory(self, events: list[dict[str, Any]]) -> Trajectory:
        self._model_call_step_ids = {}
        trajectory = super()._convert_events_to_trajectory(events)
        self._attach_step_metrics(trajectory, events)
        return trajectory

    def _attach_step_metrics(self, trajectory: Trajectory, events: list[dict[str, Any]]) -> None:
        usage_by_step = _sum_model_call_usage_by_step(events, self._model_call_step_ids)
        resolved = self._resolve_pricing_rates()
        for step in trajectory.steps:
            usage = usage_by_step.get(step.step_id)
            if usage is None:
                continue
            step.metrics = Metrics(
                prompt_tokens=usage["inputTokens"] + usage["cacheReadTokens"] + usage["cacheWriteTokens"],
                completion_tokens=usage["outputTokens"],
                cached_tokens=usage["cacheReadTokens"],
                cost_usd=self._cost_from_token_rates(usage, resolved[0]) if resolved else None,
            )

    async def _ensure_dns_resolution(self, environment: BaseEnvironment) -> None:
        """Prepend public DNS resolvers if the cloud sandbox cannot reach Cursor's API."""
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
            await environment.upload_file(source_path=resolved, target_path=target_path)


def _sum_model_call_usage_by_step(
    events: list[dict[str, Any]],
    model_call_step_ids: dict[str, int],
) -> dict[int, dict[str, int]]:
    totals: dict[int, dict[str, int]] = {}
    for event in events:
        if event.get("type") != "usage" or event.get("subtype") != "model_call":
            continue
        step_id = model_call_step_ids.get(str(event.get("model_call_id", "")))
        usage = event.get("usage")
        if step_id is None or not isinstance(usage, dict):
            continue
        bucket = totals.setdefault(step_id, dict.fromkeys(_USAGE_KEYS, 0))
        for key in _USAGE_KEYS:
            bucket[key] += int(usage.get(key) or 0)
    return totals
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_configurable_cursor.py tests/test_configurable_agents_options.py tests/test_opik_step_patch.py -q`
Expected: PASS. If mypy later flags the `_apply_tool_call_event` override differently, keep the targeted `# type: ignore[override]` only.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/agents/configurable_cursor.py tests/test_configurable_cursor.py tests/test_configurable_agents_options.py
git commit -m "feat(agents): ConfigurableCursor with sandbox_files and per-step Opik metrics"
```

---

### Task 4: Runner + CLI wiring for the `cursor` agent family

**Files:**
- Modify: `src/nasde_toolkit/runner.py` — `_ensure_auth` (:253), `_collect_native_skill_dirs` docstring (:383), `_warn_if_skill_frontmatter_malformed` message (:440), `_AGENT_SKILLS_SUBDIR` (:380), `_VALID_AGENT_TYPES` (:448), `load_variant_config` docstring (:455), `_agent_import_path` (:524), new `_is_cursor_agent` (after :537), `_agent_type_from_import_path` (:749), `_build_merged_config` (:834-839), new `_inject_cursor_pricing` + `_cursor_pricing_rates` (after `_build_merged_config`), `_short_label` (:1285)
- Modify: `src/nasde_toolkit/cli.py:198-202` (`--effort` help), `:770` (agent labels)
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `pricing.effective_pricing_with_source(project_dir) -> dict[str, tuple[ModelPrice, str]]`; `ConfigurableCursor` import path.
- Produces: `runner._is_cursor_agent(import_path: str | None) -> bool`; agent kwargs `pricing: {"input", "output", "cache_read"?, "cache_write"?}` in the merged Harbor config for Cursor agents with a catalog price.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_runner.py` (add `_is_cursor_agent` to the `from nasde_toolkit.runner import (...)` list):

```python
# ---------------------------------------------------------------------------
# cursor agent family
# ---------------------------------------------------------------------------

CURSOR_PATH = "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor"


def test_load_variant_agent_type_cursor(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "cursor"\nmodel = "cursor/composer-2.5"')
    assert load_variant_agent_type(tmp_path) == "cursor"


def test_is_cursor_agent() -> None:
    assert _is_cursor_agent(CURSOR_PATH)
    assert _is_cursor_agent("harbor.agents.installed.cursor_cli:CursorCli")
    assert not _is_cursor_agent("nasde_toolkit.agents.configurable_claude:ConfigurableClaude")
    assert not _is_cursor_agent(None)


def test_generate_harbor_config_cursor_variant_with_skills(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "cursor-skilled"
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# Cursor")
    (variant_dir / "variant.toml").write_text('agent = "cursor"')
    skill_dir = variant_dir / "cursor_skills" / "tactical-ddd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: tactical-ddd\ndescription: x\n---\n")

    _generate_harbor_config(variant_dir, "cursor-skilled")

    agent = json.loads((variant_dir / "harbor_config.json").read_text())["agents"][0]
    assert agent["import_path"] == CURSOR_PATH
    assert "/app/AGENTS.md" in agent["kwargs"]["sandbox_files"]
    assert not any(".cursor/skills" in k for k in agent["kwargs"]["sandbox_files"])
    assert agent["skills"] == [str(skill_dir.resolve())]


def test_ensure_auth_cursor_with_api_key() -> None:
    with patch.dict("os.environ", {"CURSOR_API_KEY": "key_test"}, clear=True):
        _ensure_auth(CURSOR_PATH)


def test_ensure_auth_cursor_missing_raises(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.dict("os.environ", {}, clear=True), pytest.raises(SystemExit):
        _ensure_auth(CURSOR_PATH)
    assert "CURSOR_API_KEY" in capsys.readouterr().out


def _cursor_project(tmp_project: ProjectConfig) -> Path:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    config = json.loads(variant_config_path.read_text())
    config["agents"][0]["import_path"] = CURSOR_PATH
    variant_config_path.write_text(json.dumps(config))
    return variant_config_path


def test_build_merged_config_injects_catalog_pricing_for_cursor(tmp_project: ProjectConfig) -> None:
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=_cursor_project(tmp_project),
        variant_name="vanilla",
        model="cursor/composer-2.5",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert result["agents"][0]["kwargs"]["pricing"] == {"input": 0.5, "output": 2.5, "cache_read": 0.2}


def test_build_merged_config_no_pricing_for_unpriced_cursor_model(tmp_project: ProjectConfig) -> None:
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=_cursor_project(tmp_project),
        variant_name="vanilla",
        model="cursor/some-new-model",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert "pricing" not in result["agents"][0]["kwargs"]


def test_build_merged_config_no_pricing_kwarg_for_claude(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-5-5",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert "pricing" not in result["agents"][0]["kwargs"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_runner.py -q -k cursor`
Expected: FAIL — `ImportError: cannot import name '_is_cursor_agent'`.

- [ ] **Step 3: Implement runner changes**

`_ensure_auth` — insert after the Gemini block, before the Claude check:

```python
    if _is_cursor_agent(agent_import_path):
        if os.environ.get("CURSOR_API_KEY"):
            return
        console.print(
            "[red]ERROR: Set CURSOR_API_KEY (or run 'source scripts/export_cursor_api_key.sh')[/red]"
        )
        raise SystemExit(1)
```

Constants:

```python
_AGENT_SKILLS_SUBDIR = {"codex": "agents_skills", "gemini": "gemini_skills", "cursor": "cursor_skills"}
...
_VALID_AGENT_TYPES = {"claude", "codex", "gemini", "cursor"}
```

`_agent_import_path` — add before the Claude fallback:

```python
    if agent_type == "cursor":
        return "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor"
```

New predicate after `_is_gemini_agent`:

```python
def _is_cursor_agent(agent_import_path: str | None) -> bool:
    return bool(agent_import_path and "cursor" in agent_import_path.lower())
```

`_agent_type_from_import_path` — add after the Gemini branch:

```python
    if _is_cursor_agent(import_path):
        return "cursor"
```

`_build_merged_config` — inside the `for agent in variant.get("agents", []):` loop, after the `reasoning_effort` block:

```python
        _inject_cursor_pricing(agent, config.project_dir)
```

New helpers right after `_build_merged_config`:

```python
def _inject_cursor_pricing(agent: dict, project_dir: Path) -> None:
    """Feed nasde's catalog rate into Harbor's CursorCli ``pricing`` kwarg.

    One rate source for Harbor's trajectory cost, the per-step Opik costs and
    nasde's ``cost_usd`` (ADR-015). A hand-written ``pricing`` kwarg is kept; an
    unpriced model gets none, so Harbor falls back to its own estimate.
    """
    if not _is_cursor_agent(agent.get("import_path")):
        return
    kwargs = agent.setdefault("kwargs", {})
    if "pricing" in kwargs:
        return
    from nasde_toolkit.pricing import effective_pricing_with_source

    entry = effective_pricing_with_source(project_dir).get(str(agent.get("model_name", "")))
    if entry is None:
        return
    kwargs["pricing"] = _cursor_pricing_rates(entry[0])


def _cursor_pricing_rates(price: ModelPrice) -> dict[str, float]:
    rates = {"input": price.input_per_1m, "output": price.output_per_1m}
    if price.cached_input_per_1m is not None:
        rates["cache_read"] = price.cached_input_per_1m
    if price.cache_write_per_1m is not None:
        rates["cache_write"] = price.cache_write_per_1m
    return rates
```

Add `from nasde_toolkit.pricing import ModelPrice` inside the existing `if TYPE_CHECKING:` block (`runner.py:39`).

Docstring/message updates (text only):
- `load_variant_config`: `an ``agent`` field set to ``"claude"``, ``"codex"``, ``"gemini"`` or ``"cursor"``.`
- `_collect_native_skill_dirs`: mention `~/.cursor/skills` for Cursor alongside Codex/Gemini.
- `_warn_if_skill_frontmatter_malformed`: `Codex/Gemini/Cursor may refuse to register the skill`.

`_short_label`:

```python
    short_agent = (
        agent.removeprefix("claude-").removeprefix("codex-").removeprefix("gemini-").removeprefix("cursor-")
    )
    short_agent = short_agent.replace("ntcoding-tactical-ddd-", "").replace("ntcoding-tactical-ddd", "tactical-ddd")
    short_model = model.removeprefix("claude-").removeprefix("google/").removeprefix("cursor/")
```

- [ ] **Step 4: CLI changes** in `src/nasde_toolkit/cli.py`

`--effort` help string:

```python
        help="Reasoning-effort override, passed straight to the agent (the agent validates it). "
        "Typical levels — claude: low/medium/high/xhigh/max; codex: none/minimal/low/medium/high/xhigh; "
        "gemini: minimal/low/medium/high; cursor: low/medium/high/xhigh/max. "
        "Default: variant.toml reasoning_effort, else Harbor family default.",
```

Agent labels:

```python
    agent_labels = {"codex": "Codex (OpenAI)", "gemini": "Gemini CLI (Google)", "cursor": "Cursor CLI"}
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_runner.py tests/test_runner_skills.py tests/test_runner_economics.py tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/nasde_toolkit/runner.py src/nasde_toolkit/cli.py tests/test_runner.py
git commit -m "feat(runner): cursor agent family — auth, native skills, catalog pricing into Harbor"
```

---

### Task 5: `cursor` judge backend

**Files:**
- Create: `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py`
- Modify: `src/nasde_toolkit/evaluator_backends/__init__.py`
- Modify: `src/nasde_toolkit/cli.py:85-93` (`_override_eval_judge`) and the `--eval-backend` option help text (search `eval-backend`)
- Test: `tests/test_evaluator_backends.py`

**Interfaces:**
- Consumes: `EvaluationConfig`, `AGENT_DIFF_FILENAME`, `claude_subprocess._extract_result_text`, `claude_subprocess._resolve_path`.
- Produces: `CursorSubprocessBackend` (satisfies `EvaluatorBackend` protocol), `create_backend(EvaluationConfig(backend="cursor"))`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_evaluator_backends.py`:

```python
from nasde_toolkit.evaluator_backends.cursor_subprocess import CursorSubprocessBackend


def test_create_backend_returns_cursor_when_configured() -> None:
    backend = create_backend(EvaluationConfig(backend="cursor"))
    assert isinstance(backend, CursorSubprocessBackend)
    assert isinstance(backend, EvaluatorBackend)


def test_cursor_backend_validate_cli_installed_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("nasde_toolkit.evaluator_backends.cursor_subprocess.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        CursorSubprocessBackend().validate_cli_installed()
    out = capsys.readouterr().out
    assert "cursor-agent" in out
    assert "--without-eval" in out


def test_cursor_backend_validate_auth_tolerates_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    CursorSubprocessBackend().validate_auth()


def test_cursor_backend_builds_read_only_command(tmp_path: Path) -> None:
    cmd = CursorSubprocessBackend()._build_command(
        eval_config=EvaluationConfig(backend="cursor", model="cursor/claude-opus-5-5"),
        trial_dir=None,
    )
    assert cmd[:2] == ["cursor-agent", "-p"]
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--mode") + 1] == "ask"
    assert "--trust" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    assert "--max-turns" not in cmd
    assert "--add-dir" not in cmd


def test_cursor_backend_command_includes_add_dir_for_agent_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    (trial_dir / "agent_changes.diff").write_text("diff --git a/x b/x\n", encoding="utf-8")
    cmd = CursorSubprocessBackend()._build_command(eval_config=EvaluationConfig(), trial_dir=trial_dir)
    assert cmd[cmd.index("--add-dir") + 1] == str(trial_dir)


def test_cursor_backend_no_context_options_runs_in_workspace(tmp_path: Path) -> None:
    cmd, temp_dir = CursorSubprocessBackend()._build_command_with_context(
        workspace_path=tmp_path, eval_config=EvaluationConfig(), project_root=tmp_path, trial_dir=None
    )
    assert temp_dir is None
    assert "--add-dir" not in cmd


def test_cursor_backend_context_dir_carries_skills_mcp_and_rule(tmp_path: Path) -> None:
    skill = tmp_path / "evaluator_skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Skill")
    mcp = tmp_path / "evaluator_mcp.json"
    mcp.write_text('{"mcpServers": {}}')
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    eval_config = EvaluationConfig(
        skills_dir="evaluator_skills", mcp_config="evaluator_mcp.json", append_system_prompt="Be strict."
    )

    cmd, temp_dir = CursorSubprocessBackend()._build_command_with_context(
        workspace_path=workspace, eval_config=eval_config, project_root=tmp_path, trial_dir=None
    )

    assert temp_dir is not None
    assert (temp_dir / ".cursor" / "skills" / "my-skill" / "SKILL.md").exists()
    assert (temp_dir / ".cursor" / "mcp.json").read_text() == '{"mcpServers": {}}'
    rule = (temp_dir / ".cursor" / "rules" / "nasde-judge.mdc").read_text()
    assert "alwaysApply: true" in rule
    assert "Be strict." in rule
    assert "--approve-mcps" in cmd
    assert cmd[cmd.index("--add-dir") + 1] == str(workspace)
    assert not (workspace / ".cursor").exists()

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_cursor_backend_warns_on_allowed_tools(capsys: pytest.CaptureFixture[str]) -> None:
    CursorSubprocessBackend()._warn_unsupported_options(EvaluationConfig(allowed_tools=["Read", "Bash"]))
    out = capsys.readouterr().out
    assert "allowed_tools" in out
    assert "--mode ask" in out


def test_cursor_backend_silent_without_allowed_tools(capsys: pytest.CaptureFixture[str]) -> None:
    CursorSubprocessBackend()._warn_unsupported_options(EvaluationConfig(max_turns=5))
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_evaluator_backends.py -q -k cursor`
Expected: FAIL with `ModuleNotFoundError: ... cursor_subprocess`

- [ ] **Step 3: Implement** — create `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py`:

```python
"""Cursor CLI (`cursor-agent -p`) subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends.claude_subprocess import _extract_result_text, _resolve_path
from nasde_toolkit.evaluator_backends.protocol import AGENT_DIFF_FILENAME

console = Console()

_CURSOR_MODEL_PREFIX = "cursor/"

_JUDGE_RULE_TEMPLATE = """---
description: nasde judge instructions
alwaysApply: true
---

{prompt}
"""


class CursorSubprocessBackend:
    """Evaluator backend that spawns `cursor-agent -p` as a subprocess.

    Mirrors the Claude backend as closely as the public `cursor-agent` CLI
    allows (ADR-015): `--mode ask` is the read-only mode standing in for
    Claude's `--allowedTools Read,Glob,Grep`; `skills_dir`, `mcp_config` and
    `append_system_prompt` are delivered through a temp working dir
    (`.cursor/skills`, `.cursor/mcp.json`, an always-apply
    `.cursor/rules/nasde-judge.mdc`) with the trial workspace added via
    `--add-dir`, so the workspace is never written to. `max_turns` has no
    equivalent and is ignored; a custom `allowed_tools` is warned about and
    ignored. Authenticates via CURSOR_API_KEY or the `cursor-agent login`
    session.
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_cli_installed()
        self.validate_auth()
        self._warn_unsupported_options(eval_config)
        cmd, temp_dir = self._build_command_with_context(workspace_path, eval_config, project_root, trial_dir)
        cwd = temp_dir if temp_dir else workspace_path
        try:
            return await self._run_subprocess([*cmd, "--", prompt], cwd, dict(os.environ))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def validate_auth(self) -> None:
        if os.environ.get("CURSOR_API_KEY"):
            return
        console.print("[dim]No CURSOR_API_KEY in the environment — relying on the cursor-agent login session.[/dim]")

    def validate_cli_installed(self) -> None:
        if shutil.which("cursor-agent") is not None:
            return
        console.print(
            "[red]ERROR: `cursor-agent` CLI not found on PATH.[/red]\n"
            "[yellow]Assessment evaluation with the Cursor backend requires the Cursor CLI.[/yellow]\n"
            "Install it with `curl https://cursor.com/install -fsS | bash`, then re-run. "
            'To use a different backend, set \\[evaluation] backend = "claude" in nasde.toml, '
            "or pass --without-eval to skip assessment evaluation."
        )
        raise SystemExit(1)

    def _warn_unsupported_options(self, eval_config: EvaluationConfig) -> None:
        if not eval_config.allowed_tools:
            return
        console.print(
            f"[yellow]WARNING: \\[evaluation] allowed_tools = {eval_config.allowed_tools} is ignored by the "
            "cursor backend — the judge always runs read-only (--mode ask).[/yellow]"
        )

    def _build_command_with_context(
        self,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None,
    ) -> tuple[list[str], Path | None]:
        cmd = self._build_command(eval_config, trial_dir)
        if not (eval_config.skills_dir or eval_config.mcp_config or eval_config.append_system_prompt):
            return cmd, None
        temp_dir = Path(tempfile.mkdtemp(prefix="nasde_eval_"))
        cursor_dir = temp_dir / ".cursor"
        cursor_dir.mkdir()
        _stage_skills(eval_config, project_root, cursor_dir)
        if _stage_mcp_config(eval_config, project_root, cursor_dir):
            cmd.append("--approve-mcps")
        _stage_system_prompt_rule(eval_config, cursor_dir)
        cmd.extend(["--add-dir", str(workspace_path)])
        return cmd, temp_dir

    def _build_command(self, eval_config: EvaluationConfig, trial_dir: Path | None) -> list[str]:
        cmd = [
            "cursor-agent",
            "-p",
            "--output-format",
            "json",
            "--trust",
            "--mode",
            "ask",
            "--model",
            eval_config.model.removeprefix(_CURSOR_MODEL_PREFIX),
        ]
        needs_trial_dir = trial_dir is not None and (
            eval_config.include_trajectory or (trial_dir / AGENT_DIFF_FILENAME).exists()
        )
        if needs_trial_dir:
            cmd.extend(["--add-dir", str(trial_dir)])
        return cmd

    async def _run_subprocess(self, cmd: list[str], cwd: Path, env: dict[str, str]) -> str:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=env,
        )
        stdout_bytes, stderr_bytes = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            last_lines = "\n".join(stderr_text.splitlines()[-10:]) if stderr_text else ""
            model = cmd[cmd.index("--model") + 1]
            raise RuntimeError(
                f"cursor-agent process failed (exit code {process.returncode}). "
                f"Model: {model}, cwd: {cwd}. "
                f"stderr (last 10 lines):\n{last_lines}"
            )

        return _extract_result_text(stdout_bytes.decode())


def _stage_skills(eval_config: EvaluationConfig, project_root: Path, cursor_dir: Path) -> None:
    if not eval_config.skills_dir:
        return
    skills_source = _resolve_path(eval_config.skills_dir, project_root)
    if skills_source.is_dir():
        shutil.copytree(skills_source, cursor_dir / "skills")


def _stage_mcp_config(eval_config: EvaluationConfig, project_root: Path, cursor_dir: Path) -> bool:
    if not eval_config.mcp_config:
        return False
    shutil.copyfile(_resolve_path(eval_config.mcp_config, project_root), cursor_dir / "mcp.json")
    return True


def _stage_system_prompt_rule(eval_config: EvaluationConfig, cursor_dir: Path) -> None:
    if not eval_config.append_system_prompt:
        return
    rules_dir = cursor_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "nasde-judge.mdc").write_text(_JUDGE_RULE_TEMPLATE.format(prompt=eval_config.append_system_prompt))
```

`src/nasde_toolkit/evaluator_backends/__init__.py` — add before `else:` and update the error:

```python
    elif eval_config.backend == "cursor":
        from nasde_toolkit.evaluator_backends.cursor_subprocess import CursorSubprocessBackend

        return CursorSubprocessBackend()
    else:
        raise ValueError(
            f"Unknown evaluator backend: '{eval_config.backend}'. Supported: 'claude', 'codex', 'cursor'"
        )
```

`src/nasde_toolkit/cli.py` `_override_eval_judge`:

```python
        if backend not in ("claude", "codex", "cursor"):
            console.print(
                f"[red]ERROR: --eval-backend must be 'claude', 'codex' or 'cursor', got '{backend}'.[/red]"
            )
            raise typer.Exit(1)
```

Also update the `--eval-backend` option `help=` text (find with `rg -n 'eval-backend' src/nasde_toolkit/cli.py`) to list `claude|codex|cursor`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_evaluator_backends.py tests/test_cli.py tests/test_evaluator.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/ src/nasde_toolkit/cli.py tests/test_evaluator_backends.py
git commit -m "feat(evaluator): cursor judge backend (cursor-agent -p --mode ask)"
```

---

### Task 6: Auth helper scripts

**Files:**
- Create: `scripts/export_cursor_api_key.sh`
- Create: `scripts/export_cursor_api_key.ps1`

- [ ] **Step 1: Create `scripts/export_cursor_api_key.sh`**

```bash
#!/bin/bash

# Export a Cursor API key as CURSOR_API_KEY for nasde's Cursor agent.
#
# Harbor's Cursor agent authenticates only via CURSOR_API_KEY. Source this
# script before running nasde:
#
#   source scripts/export_cursor_api_key.sh
#   nasde run --variant cursor-vanilla -C my-benchmark
#
# Resolution order:
#   1. An already-exported CURSOR_API_KEY is kept.
#   2. macOS: Keychain entry "cursor-api-key" (stored by the cursor-agent CLI).
# Otherwise create a key in the Cursor dashboard (Integrations → API keys) and
# export it yourself. Windows users: see scripts/export_cursor_api_key.ps1.

# NOTE: Do NOT use `set -e` here -- this script is sourced into the user's
# shell, so errexit would persist and kill the terminal on any later non-zero
# exit code.

if [ -n "$CURSOR_API_KEY" ]; then
    echo "✓ CURSOR_API_KEY already set (${CURSOR_API_KEY:0:8}...)"
    return 0 2>/dev/null || exit 0
fi

_cursor_key=""
if command -v security >/dev/null 2>&1; then
    _cursor_key="$(security find-generic-password -s "cursor-api-key" -w 2>/dev/null)"
fi

if [ -z "$_cursor_key" ]; then
    echo "ERROR: Could not find a Cursor API key." >&2
    echo "  - macOS: keychain entry 'cursor-api-key' missing" >&2
    echo "Create one in the Cursor dashboard (Integrations → API keys) and run:" >&2
    echo "  export CURSOR_API_KEY=<your-key>" >&2
    unset _cursor_key
    return 1 2>/dev/null || exit 1
fi

export CURSOR_API_KEY="$_cursor_key"
unset _cursor_key

echo "✓ CURSOR_API_KEY exported (${CURSOR_API_KEY:0:8}...)"
```

Run: `chmod +x scripts/export_cursor_api_key.sh`

- [ ] **Step 2: Create `scripts/export_cursor_api_key.ps1`**

```powershell
# Check that $env:CURSOR_API_KEY is set for nasde's Cursor agent.
#
# Windows-equivalent of scripts/export_cursor_api_key.sh. Harbor's Cursor agent
# authenticates only via CURSOR_API_KEY. There is no known local store to read
# the key from on Windows, so this script verifies the variable and explains
# how to set it.
#
#     . .\scripts\export_cursor_api_key.ps1
#     nasde run --variant cursor-vanilla -C my-benchmark

if (-not [string]::IsNullOrEmpty($env:CURSOR_API_KEY)) {
    $preview = $env:CURSOR_API_KEY.Substring(0, [Math]::Min(8, $env:CURSOR_API_KEY.Length))
    Write-Host "OK CURSOR_API_KEY already set ($preview...)" -ForegroundColor Green
    return
}

Write-Error "CURSOR_API_KEY is not set. Create a key in the Cursor dashboard (Integrations -> API keys), then run: `$env:CURSOR_API_KEY = '<your-key>'"
```

- [ ] **Step 3: Verify (requires user approval — reads keychain)**

Ask the user first. Then run in a subshell, printing only success/failure (never the key):
`bash -c 'unset CURSOR_API_KEY; source scripts/export_cursor_api_key.sh >/dev/null && cursor-agent status --api-key "$CURSOR_API_KEY" 2>&1 | head -1'`
Expected: `✓ Logged in as ...`. If it fails, report to the user and adjust the script (the keychain entry may not hold a usable API key).

- [ ] **Step 4: Commit**

```bash
git add scripts/export_cursor_api_key.sh scripts/export_cursor_api_key.ps1
git commit -m "feat(scripts): export_cursor_api_key helper"
```

---

### Task 7: Example `cursor-vanilla` variants

**Files:**
- Create: `examples/ddd-architectural-challenges/variants/cursor-vanilla/{variant.toml,AGENTS.md}`
- Create: `examples/refactoring-skill/variants/cursor-vanilla/{variant.toml,AGENTS.md}`
- Create: `examples/nasde-dev-skill/variants/cursor-vanilla/{variant.toml,AGENTS.md}`

- [ ] **Step 1: Create files**

Each `variant.toml`:

```toml
agent = "cursor"
model = "cursor/composer-2.5"
```

`examples/ddd-architectural-challenges/variants/cursor-vanilla/AGENTS.md`:

```markdown
You are a coding assistant. Work in /app.
```

`examples/refactoring-skill/variants/cursor-vanilla/AGENTS.md`:

```markdown
# Agent Instructions

You are a coding assistant. Work in /app.

1. Follow existing patterns in the codebase.
2. Write tests that match the style of existing test files.
```

`examples/nasde-dev-skill/variants/cursor-vanilla/AGENTS.md`:

```markdown
# Agent Instructions

You are a coding assistant. Work in /app.

1. Follow existing patterns in the codebase.
```

- [ ] **Step 2: Verify variants load**

Run: `uv run python -c "from pathlib import Path; from nasde_toolkit.runner import load_variant_agent_type as t; print([t(p) for p in Path('examples').glob('*/variants/cursor-vanilla')])"`
Expected: `['cursor', 'cursor', 'cursor']`

- [ ] **Step 3: Commit**

```bash
git add examples/*/variants/cursor-vanilla
git commit -m "feat(examples): cursor-vanilla variants"
```

---

### Task 8: Documentation, skills, scaffold, CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`
- Modify: `.claude/skills/nasde-benchmark-runner/SKILL.md`, `.claude/skills/nasde-benchmark-creator/SKILL.md`, `.claude/skills/nasde-dev/SKILL.md`
- Modify: `src/nasde_toolkit/scaffold/__init__.py`

- [ ] **Step 1: CHANGELOG** — under `## [Unreleased]`, add an `### Added` section (create it above `### Changed` if absent):

```markdown
### Added
- **Cursor support (agent + judge).** Variants can run Cursor's
  `cursor-agent` CLI with `agent = "cursor"` and a prefixed model
  (`model = "cursor/composer-2.5"`); instructions come from `AGENTS.md`,
  skills from `cursor_skills/` (native `~/.cursor/skills`), effort from
  `reasoning_effort`. Auth is `CURSOR_API_KEY`
  (`source scripts/export_cursor_api_key.sh`). `[evaluation] backend =
  "cursor"` (or `--eval-backend cursor`) runs the judge read-only via
  `cursor-agent -p --mode ask`. Cursor agent steps now reach Opik with
  per-step tokens and cost. Bundled prices for `cursor/composer-2.5`,
  `cursor/claude-opus-5-5` and `cursor/claude-sonnet-5-5` (list rates, no
  Teams surcharge); other `cursor/*` models fall back to Harbor's estimate.
  Every trial's economics gain `cost_source`. See ADR-015. ([#NN])
```

Add `[#NN]: https://github.com/NoesisVision/nasde-toolkit/pull/NN` to the link references at the bottom (replace `NN` with the PR number once the PR exists).

- [ ] **Step 2: Find every agent-family enumeration**

Run: `rg -n -i 'gemini' README.md CLAUDE.md ARCHITECTURE.md .claude/skills/nasde-benchmark-runner/SKILL.md .claude/skills/nasde-benchmark-creator/SKILL.md .claude/skills/nasde-dev/SKILL.md src/nasde_toolkit/scaffold/__init__.py`

At every location that enumerates agent families (agent types, variant files, skills subdirs, auth, effort levels, harbor_config examples, judge backends), add the Cursor equivalent using this mapping:

| Topic | Cursor value |
|---|---|
| `variant.toml` agent | `agent = "cursor"`, `model = "cursor/composer-2.5"` |
| Instructions file | `AGENTS.md` → `/app/AGENTS.md` |
| Skills | `cursor_skills/<name>/SKILL.md` → native `~/.cursor/skills` (needs `---` YAML frontmatter) |
| Import path | `nasde_toolkit.agents.configurable_cursor:ConfigurableCursor` |
| Auth | `CURSOR_API_KEY`; `source scripts/export_cursor_api_key.sh` |
| Effort levels (not enforced) | `low`/`medium`/`high`/`xhigh`/`max`; Harbor renders `model[effort=X]` |
| Judge | `backend = "cursor"`: read-only `--mode ask`; `allowed_tools` warned + ignored; `max_turns` ignored; `skills_dir`/`mcp_config`/`append_system_prompt` via temp cwd `.cursor/` |
| Pricing | 3 bundled `cursor/*` entries; Teams surcharge via override; fallback `cost_source = "harbor:..."` |

- [ ] **Step 3: CLAUDE.md specifics**

- Package structure: add `configurable_cursor.py # Harbor-compatible Cursor CLI agent with sandbox file injection + per-step metrics` and `cursor_subprocess.py # \`cursor-agent -p\` subprocess backend`.
- Architecture decisions: add a bullet **"Cursor (ADR-015)"** summarizing the Decision section of `docs/adr/015-cursor-agent-and-judge.md` in 5–8 lines.
- Token & cost bullet: append `cost_source` (`"pricing.toml"` / `"harbor:<source>"` / null) and the Cursor fallback.
- `CLI reference`: `--eval-backend` values include `cursor` where listed.
- Benchmark project structure: add `cursor_skills/` under `variants/<variant-name>/` next to `gemini_skills/`.
- Add a "Cursor CLI variant" `harbor_config.json` example next to the Gemini one.

- [ ] **Step 4: README pricing note** — in the pricing-override section, add an example override for Teams users:

```toml
# ~/.nasde/pricing.toml — Cursor Teams/Enterprise: list + $0.25/M Cursor Token Rate
[models."cursor/claude-opus-5-5"]
input_per_1m = 4.25
output_per_1m = 20.25
cached_input_per_1m = 0.45
cache_write_per_1m = 5.25
as_of = "2026-11-23"
source = "https://cursor.com/docs/models-and-pricing (+ Teams Cursor Token Rate)"
```

- [ ] **Step 5: nasde-dev skill** — in "3. End-to-end benchmark run" auth list add `cursor → CURSOR_API_KEY (scripts/export_cursor_api_key.sh)`, and add a `cursor` evaluator note (needs `cursor-agent` CLI + login/key).

- [ ] **Step 6: Scaffold** — in `NASDE_TOML_TEMPLATE` `[evaluation]` comments, change the backend comment to `# "claude" (default) | "codex" | "cursor"` if a backend comment exists; otherwise add `# backend = "claude"  # "claude" (default) | "codex" | "cursor"`.

- [ ] **Step 7: Run tests (scaffold tests)**

Run: `uv run pytest tests/test_scaffold.py tests/test_skills_installer.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add CHANGELOG.md README.md CLAUDE.md ARCHITECTURE.md .claude/skills src/nasde_toolkit/scaffold/__init__.py
git commit -m "docs: Cursor agent + judge support"
```

---

### Task 9: Verification

- [ ] **Step 1: Quality gates**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/nasde_toolkit/ && uv run pytest -q`
Expected: all pass. Fix and amend the relevant task commit if not.

- [ ] **Step 2: CLI smoke**

Run: `uv run nasde --version && uv run nasde run --help | rg -i cursor && uv run nasde pricing show | rg cursor/`
Expected: version prints; `--effort` help mentions cursor; three `cursor/*` rows.

- [ ] **Step 3: E2E agent run — ASK USER FIRST (spends tokens)**

```bash
source scripts/export_oauth_token.sh && \
  uv run nasde run --variant cursor-vanilla --tasks <smallest-task> \
  -C examples/refactoring-skill --with-opik --eval-repetitions 1
```

Check: trial completes; `agent/trajectory.json` has per-step `metrics` with `cost_usd`; `assessment_summary.json` has `token_usage` (non-zero `cache_write_tokens` if any), `cost_usd`, `cost_source == "pricing.toml"`; Opik trace shows agent spans with tokens and cost (verify via the nasde-dev skill's Opik REST snippet).

- [ ] **Step 4: E2E judge run — ASK USER FIRST**

`uv run nasde eval <job_dir> --eval-backend cursor --eval-model cursor/claude-opus-5-5 --eval-repetitions 1 -C examples/refactoring-skill`.
Check: `assessment_eval_<N>.json` written with scores; trial workspace has no `.cursor/` dir added.

- [ ] **Step 5: Bare-slug check — ASK USER FIRST**

In the e2e run with `cursor/claude-opus-5-5` (via `--model cursor/claude-opus-5-5 --effort high`), confirm `cursor-agent` accepts `claude-opus-5-5[effort=high]`. If rejected, stop and ask the user how to key pricing.
