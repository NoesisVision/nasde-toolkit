# ADR-006: Runtime monkey-patch for Opik Harbor token usage

**Status:** Accepted
**Date:** 2026-03-26

## Context

Opik's Harbor integration (`opik.integrations.harbor.opik_tracker._patch_step_class`) patches `Step.__init__` to read `self.metrics` and create Opik spans with `usage` data (token counts). However, Harbor's `ClaudeCode._convert_event_to_step()` creates `Step(...)` without `metrics`, then assigns `step.metrics = metrics` after construction. This means the Opik patch always sees `self.metrics = None`, all spans have `usage=None`, and the Opik backend has nothing to aggregate into the trace's "Total tokens" column.

This bug was originally fixed in the SDLC repo (commit `66c2c11`, 2026-03-09) via a vendor `.patch` file applied to the installed opik package (`evals/eval-platforms/patches/opik_harbor_deferred_metrics.patch`). When the evaluation infrastructure was extracted into nasde-toolkit (SDLC commit `74bfb06`, 2026-03-20), the patch was not ported.

As of opik 1.10.50 (latest), this bug remains unfixed upstream.

## Decision

Apply the fix as a **runtime monkey-patch** in `runner.py` instead of a vendor `.patch` file. The patch is applied immediately after `track_harbor()` and re-patches `Step.__init__` + adds `Step.__setattr__`:

- `__init__`: stashes Opik trace context on the Step instance; emits spans immediately for non-agent steps (which never receive metrics).
- `__setattr__`: when `metrics` is assigned, creates the Opik span with token usage data at that point.

## Rationale

- **Survives `uv sync`**: vendor `.patch` files must be re-applied after every dependency install. Runtime patches are applied each run automatically.
- **No external scripts**: the SDLC approach required `apply_opik_patches.sh` — easy to forget after `uv sync`.
- **Same fix, different delivery**: the logic is identical to the SDLC `.patch` file; only the application mechanism differs.
- **Follows existing pattern**: `evaluator.py` already uses a runtime monkey-patch for the claude-code-sdk `parse_message` bug.

## Consequences

- The patch must be maintained alongside opik upgrades. If opik changes `_patch_step_class` internals, our re-patch may need adjustment.
- Remove when: opik upstream fixes the timing issue (check changelog for "harbor" + "metrics" or "deferred" mentions).
