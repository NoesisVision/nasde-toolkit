# Trajectory-Aware Evaluator

**Date:** 2026-04-16
**Status:** Approved

## Problem

The nasde evaluator (Claude Code SDK) currently only assesses final artifacts in `artifacts/workspace/`. It has no visibility into the agent's execution trajectory — tool calls, reasoning steps, token usage, errors, retries. This means evaluation dimensions can only measure "what was produced", not "how the agent worked".

Meanwhile, Harbor already captures full ATIF trajectory data in `agent/trajectory.json` for every trial. This data is unused by the evaluator.

Platforms like Braintrust and Opik offer trace-level evaluation, but require separate configuration. By giving our Claude Code evaluator access to trajectory data, we unify artifact + process evaluation in a single system using `assessment_dimensions.json` — no external evaluator configuration needed.

## Design

### Principle: simplicity over preprocessing

No ATIF parsing, no metric extraction, no intermediate summary files. The evaluator gets told where the trajectory file is and reads it itself using the Read tool — the same way it already explores workspace code.

### Configuration

New optional field in `nasde.toml`:

```toml
[evaluation]
include_trajectory = false   # default: false (opt-in)
```

Maps to `EvaluationConfig.include_trajectory: bool = False` in `config.py`.

Default is `false` — existing benchmarks are unaffected. Benchmark authors opt in when their assessment dimensions require evaluating the agent's process.

### Evaluator file access

When `include_trajectory = true`:

- The trial directory is added to `add_dirs` in `ClaudeCodeOptions`, giving the evaluator Read access to files outside workspace (specifically `agent/trajectory.json`).
- The evaluator's `cwd` remains `artifacts/workspace/` — code inspection is still the primary context.

### Prompt addition

When `include_trajectory = true` and `agent/trajectory.json` exists in the trial directory, the evaluator prompt includes a short section (~50 tokens):

```
## Agent trajectory

The agent's full ATIF execution trajectory is available at `../../agent/trajectory.json`.
It contains the complete step-by-step record of the agent's work: messages, tool calls
with arguments and results, token usage per step, timestamps, and errors.

Use the Read tool to examine it when your assessment criteria require evaluating
the agent's process, efficiency, or decision-making — not just the final output.
```

### Graceful degradation

If `include_trajectory = true` but `trajectory.json` does not exist (e.g., trial crashed before agent ran), the trajectory section is omitted and evaluation proceeds normally on artifacts only.

## What does NOT change

- **`assessment_dimensions.json` format** — no schema changes. Benchmark authors define dimensions that may evaluate code, trajectory, or both. The system is agnostic.
- **`EvaluationResult` / `DimensionScore`** — output model unchanged.
- **Opik integration** — scoring and upload logic unchanged.
- **Default behavior** — `include_trajectory = false` means zero impact on existing benchmarks.

## Files to modify

1. **`config.py`** — add `include_trajectory: bool = False` to `EvaluationConfig`, parse from `nasde.toml`
2. **`evaluator.py`** — two changes:
   - `_build_claude_code_options()`: when `include_trajectory=true`, add trial dir to `add_dirs`
   - `_build_evaluator_prompt()`: when trajectory is available, append the trajectory info section
3. **`CLAUDE.md`** — document the new `[evaluation]` option
4. **`ARCHITECTURE.md`** — update evaluator description

## Estimated size

~30-40 lines of production code + tests.
