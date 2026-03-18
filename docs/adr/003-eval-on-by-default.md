# ADR-003: Assessment evaluation enabled by default

**Status:** Accepted
**Date:** 2026-03-16

## Context

The tool has two stages: Harbor trial (functional tests) and assessment evaluation (LLM-as-a-Judge architecture scoring). Initially, evaluation was opt-in (`--with-eval`). This was wrong — the entire value proposition of `nasde` over raw `harbor run` is the two-stage pipeline with architecture assessment.

## Decision

Assessment evaluation is **on by default**. The flag is `--without-eval` to skip it, not `--with-eval` to enable it.

```bash
# Full pipeline (default)
nasde run baseline -C benchmarks/ddd-architectural-challenges

# Harbor-only (explicit opt-out)
nasde run baseline -C benchmarks/ddd-architectural-challenges --without-eval
```

## Consequences

- Users get full value immediately without needing to know about the `--with-eval` flag
- Running without eval is still possible for quick iteration (skips ~2 min of Claude Code SDK calls per trial)
- Opik tracing remains opt-in (`--with-opik`) because it requires external credentials and is not universally needed
