# ADR-014: Cache-aware cost is THE cost

**Status:** Accepted
**Date:** 2026-07-15
**Supersedes:** the cost formula of ADR-011 (everything else in ADR-011 stands)

## Context

ADR-011 priced every trial "as if every run were the first": the full prompt-token
volume billed at the full catalog input rate, no cache discount. The stated rationale
was determinism — the cache hit rate was assumed to be noisy (dependent on run order,
session length, TTL) while `total_prompt_tokens` is fixed for a task.

Measurement on the 2026-07 Fable 5 / Opus 4.8 grid (24 trials, `ddd-weather-discount`)
falsified both halves of that assumption:

1. **The cache ratio is not noisy.** Cache reads were 92.6–97.7% of prompt tokens on
   every one of 24 trials, across two models and three instruction configurations.
   Prompt caching in agentic sessions is a stable, structural property of the
   harness (each step extends the same prompt prefix), not run-order luck. Cache
   hits are effectively intra-session: across sessions only the short static prefix
   can match, and only within the cache TTL.
2. **The full-rate number is far from a real bill.** The as-if formula priced the
   grid at $958; the cache-aware price is $220 (4.4x lower). Harbor's own per-step
   cost accounting confirms the cache-aware figure (agreement to the cent on 20 of
   24 trials; Harbor slightly higher on 4). A cost metric meant to drive real
   model-choice decisions cannot be 4x away from the invoice it predicts.

## Decision

**`cost_usd` is cache-aware, and it is the only stored cost.**

```
fresh_input = total_prompt_tokens - cache_reads - cache_writes
cost = fresh_input * input_rate
     + cache_writes * cache_write_rate      (Anthropic 1h-cache: 2x input rate)
     + cache_reads  * cached_input_rate     (0.1x input rate)
     + output       * output_rate
```

- `TokenUsage` records `cache_write_tokens` (from Harbor's
  `extra.total_cache_creation_input_tokens`) next to the existing `cached_tokens`
  (reads). All raw volumes remain in `token_usage`.
- `pricing.toml` gains `cache_write_per_1m` per model. A missing cache rate falls
  back to the full input rate — conservative, never a silent discount. Codex
  trajectories carry no cache-creation counter, and OpenAI bills no write premium,
  so gpt entries simply omit the field.
- **No second cost field.** The old full-rate ceiling is NOT stored. Storing a
  derived view next to the primary one re-creates the confusion ADR-011 itself
  removed with the efficiency ratios: raw signals stay, derived numbers are an
  analysis step. Anyone needing the ceiling computes
  `input * input_rate + output * output_rate` from `token_usage`.

## Consequences

- Historical `metrics.json` exports carry full-rate `cost_usd` values until
  re-exported; `pricing_as_of` plus this ADR's date separate the two eras. Re-export
  refreshes economics without re-running anything.
- Cross-model comparisons barely move (both models cache at the same ~95% ratio;
  rate ratios dominate), but absolute dollars drop ~4.4x and now approximate a real
  API bill. Published figures must state "with prompt caching, at API rates".
- The determinism ADR-011 wanted survives in practice: the inputs to the formula
  are the recorded per-trial volumes, so a recomputation is always reproducible;
  what changed is that the recorded reality now includes the cache split.
