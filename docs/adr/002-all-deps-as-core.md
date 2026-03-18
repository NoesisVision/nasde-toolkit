# ADR-002: All dependencies as core (no optional extras)

**Status:** Accepted
**Date:** 2026-03-16

## Context

Harbor, Opik, and Claude Code SDK are heavy dependencies (~160 transitive packages). A common pattern is to make them optional extras (`pip install nasde-toolkit[harbor,opik]`). However, the tool's entire purpose is the integrated pipeline — there is no useful subset without all three.

## Decision

All three are core dependencies in `[project.dependencies]`. No `[project.optional-dependencies]` section.

```toml
dependencies = [
    "harbor>=0.1.40,<0.2",
    "opik>=1.10,<2",
    "claude-code-sdk>=0.0.25,<1",
    ...
]
```

## Consequences

- `uv tool install nasde-toolkit` gives complete functionality — no "did you install the extras?" support issues
- Larger install footprint (~160 packages), but this is a developer tool, not a production dependency
- Version pins (`<0.2`, `<2`, `<1`) protect against breaking API changes in Harbor/Opik/SDK
- Only `nasde` appears on PATH (verified empirically with `uv tool install`) — Harbor and Opik CLIs are accessible only through pass-through commands, preventing confusion
