# ADR-001: Thin integration layer over Harbor and Opik

**Status:** Accepted
**Date:** 2026-03-16

## Context

The eval pipeline requires three tools: Harbor (agent execution), Opik (observability), and a CLI-based LLM judge (`claude` or `codex` spawned as a subprocess). Originally orchestrated by a bash script (`run-benchmark.sh`) that called each tool via subprocess with `uv run` prefix. This forced users to either activate a venv or use `uv run` for every command — not viable for open-source distribution.

Three approaches were considered:

1. **Full abstraction** — rewrite everything behind our own API, hiding Harbor/Opik completely
2. **Fork and vendor** — copy Harbor/Opik source code into this project
3. **Thin integration layer** — use their Python APIs for core flow, pass through to their CLIs for utility commands

## Decision

**Thin integration layer** (option 3).

- **Core flow** (`run`, `eval`) uses Harbor and Opik Python APIs directly (`Job`, `JobConfig`, `track_harbor()`, `evaluate_trial()`)
- **Utility commands** (`harbor view`, `harbor jobs resume`, `opik configure`) pass through to the original CLIs unchanged
- All three libraries are core dependencies — `uv tool install .` gives full functionality with only `nasde` on PATH

## Consequences

- No subprocess calls or `uv run` prefix needed — Python imports guarantee package availability
- Harbor and Opik CLI updates are immediately available via pass-through (zero maintenance)
- We depend on their internal Python APIs (e.g. `Job`, `JobConfig`), which may change between versions — pin ranges in pyproject.toml
- Single `nasde` entry point replaces `run-benchmark.sh` + `uv run harbor` + `uv run opik` trifecta
