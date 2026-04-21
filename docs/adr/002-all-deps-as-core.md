# ADR-002: All dependencies as core (no optional extras)

**Status:** Accepted (updated 2026-04-21 — SDK replaced by CLI subprocess; see ADR-008)
**Date:** 2026-03-16

## Context

Harbor and Opik are heavy dependencies (~160 transitive packages). A common pattern is to make them optional extras (`pip install nasde-toolkit[harbor,opik]`). However, the tool's entire purpose is the integrated pipeline — there is no useful subset without them.

## Decision

Both are core dependencies in `[project.dependencies]`. No `[project.optional-dependencies]` section.

```toml
dependencies = [
    "harbor>=0.1.40,<0.2",
    "opik>=1.10,<2",
    ...
]
```

> **Note (2026-04-21):** The original ADR also listed `claude-code-sdk>=0.0.25,<1` as a core dep for the assessment evaluator. That SDK was removed when the evaluator was refactored to spawn the `claude` / `codex` CLI binaries as subprocesses — see `src/nasde_toolkit/evaluator_backends/`. The CLI binaries themselves are a runtime prerequisite, not a Python dependency.

## Consequences

- `uv tool install nasde-toolkit` gives complete functionality — no "did you install the extras?" support issues
- Larger install footprint (~160 packages), but this is a developer tool, not a production dependency
- Version pins (`<0.2`, `<2`) protect against breaking API changes in Harbor/Opik
- Only `nasde` appears on PATH (verified empirically with `uv tool install`) — Harbor and Opik CLIs are accessible only through pass-through commands, preventing confusion
- Assessment evaluation requires the user to have `claude` or `codex` CLI installed and authenticated on the host (documented in README "Prerequisites")
