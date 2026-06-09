# ADR-011: Token & cost metrics

**Status:** Accepted
**Date:** 2026-06-08

## Context

`nasde` already captured agent token usage — Harbor writes a `final_metrics` block into each trial's `agent/trajectory.json` (`total_prompt_tokens`, `total_completion_tokens`, `total_cached_tokens`, and an `extra` map that, for Codex, carries `reasoning_output_tokens`). But that data was never promoted into the analytic files. Across 275 real exports, `metrics.json` had **zero** token fields and `assessment_summary.json` carried no cost. The recurring practical consequence: "do we even have tokens?" — and no way to answer "which agent/model delivers more quality per token, or per dollar?" without hand-parsing trajectories.

The product goal (private benchmarks for AI-cost optimization) needs the raw comparable axes
recorded per trial — **quality** (`normalized_score`), **tokens** (`total_tokens`), and **cost**
(`cost_usd`) — so an agent/model can be compared on quality *and* on what it spent to get there.

Computing cost raises a subtle methodological trap: **prompt caching**. The cached-token fraction of a run depends on session length, run order, and cache TTL — not on the agent's quality. Two runs of the same task can show wildly different `total_cached_tokens`. If cost rewarded cache hits, the metric would be non-deterministic and reward verbose, many-step sessions; if it ignored cache volume entirely it would understate real input work.

## Decision

**Cost is computed "as if every run were the first".** The full prompt-token volume (cache included) is billed at the full catalog input rate, with **no cache discount**:

```
input  = total_prompt_tokens                              (full, cache included)
output = total_completion_tokens + reasoning_output_tokens
cost   = input/1e6 * input_rate + output/1e6 * output_rate
```

Rationale: `total_prompt_tokens` is **fixed for a task** (the model must process that context regardless of how much was cache-served), while the cache hit rate is not. Billing the full volume at full rate makes cost **deterministic and independent of run order / cache TTL** — the property a benchmark needs.

Supporting decisions:
- **Reasoning tokens fold into output** (Codex `reasoning_output_tokens`), so Codex is treated fairly against Claude, whose thinking is already inside `completion_tokens`.
- **Pricing is an explicit, versioned catalog** — `pricing.toml` bundled in the wheel, each model stamped with `as_of` + `source`. `cached_input_per_1m` is recorded for reference but **not used** in the cost formula. An unpriced model yields `cost_usd = null` + a warning (never a crash, never silent zero); token metrics are still computed.
- **A single extractor** (`token_metrics.py`) feeds both write paths — `evaluator.py` (run → `assessment_summary.json`) and `results_exporter.py` (export → `metrics.json`) — so the two never diverge.
- **Economics live per-trial** (one agent run), on `AssessmentSummary`, **not** on `EvaluatorGroupSummary` (which averages repeated judge evaluations). `normalized_score` is the dominant cluster's mean.
- **`model_name` and `reasoning_effort` are recorded on `AssessmentSummary`** (model was already in `metrics.json`). Cross-model analysis groups by `(agent_name, model_name, reasoning_effort)`, because `agent_name` is the variant name and does not distinguish models — a single variant has historically run several models — and a different reasoning effort is a different configuration (see the reasoning-effort section below).

## Consequences

- **Backfilling existing results is cheap.** Re-running `nasde results-export` against source jobs refreshes `metrics.json` with economics (no new runs). For already-exported dirs whose source jobs are gone, a one-shot ad-hoc script reads the export's own flat `trajectory.json` — kept out of the CLI deliberately (one-time history migration, not a routine command).
- **`nasde run` prints a cost report** — a per-`(agent, model, effort)` table (trials, score, tokens, $cost) plus the job path and an export hint. Raw cost/token columns carry an inter-trial `±std` when the group has ≥2 trials (n=1 → bare value). Missing price/trajectory renders as `—`, never an error.
- **Cost figures are only as good as the catalog.** `pricing.toml` must be kept current; each entry's `as_of`/`source` makes the provenance auditable. Numbers used in public posts must be re-confirmed against the live rate cards.
- **Determinism over realism-of-discount.** Cost intentionally does not model the cache discount a real bill would show; it answers "what did this run cost at full rate", which is the comparable, order-independent quantity. A future variant could add a discounted view using the recorded `cached_input_per_1m` without changing the default.

## Statistical rigor in the summary (a mean is never reported bare)

A single mean hides whether a gap is real or noise. Following the project's benchmarking
methodology (repeat runs, repeat scoring, never trust a lone number), every reported mean is
shown with its spread, and the **two noise sources are kept separate**:

- **Agent noise** — variation between trials (the agent writes different code each run). The
  `nasde run` table shows `Score` as `mean ±std` over trials, where `std` is the sample
  standard deviation (n−1) across per-trial scores. A single trial reads `mean (n=1)` — an
  explicit single-run flag, not a fake `±0.00`. The `Trials` column is the sample size.
- **Evaluator noise** — variation between repeated judge evaluations of the *same* trial.
  This is per-trial, so it lives in `metrics.json`: `score`, `score_eval_std` (the dominant
  cluster's std over `eval_repetitions`), `score_eval_n`, and a `single_eval` flag (true when
  the trial was scored only once). A well-behaved judge keeps this in the ~0.01–0.03 band.

Detailed stats stay in `metrics.json`; the console table carries only the `±std` next to the
mean and points the reader to `metrics.json` for the rest. Bootstrap / Bayesian
significance testing (does a between-config gap cross zero?) is **out of scope here** — it
remains an offline analysis step; this ADR only surfaces the spread and sample size that
make a mean honest.

## Superseded: scalar `token_efficiency` / `cost_efficiency` removed

The original decision shipped two scalar ratios — `token_efficiency = normalized_score / (total_tokens / 1e6)`
and `cost_efficiency = normalized_score / cost_usd` — written onto `assessment_summary.json` and `metrics.json`,
and a `score/$` / `score/MTok` console table. **Both ratios are removed.**

**Why.** A `normalized_score`-over-denominator ratio has an **arbitrary zero**. Score 0 means an *empty rubric*
— an unreachable point on the scale, not a meaningful floor — so the location of the zero is a free parameter.
A ratio ranking is *not* invariant to a shift of that zero: re-baseline the score (subtract a constant, or pick a
different lowest-possible rubric) and the *same underlying data* re-orders which agent/model "wins". A model
comparison that flips with an arbitrary choice of origin is not a sound comparison.

**Replacement: a Pareto front.** Quality vs cost (and quality vs tokens) are compared as a 2D **Pareto front**,
which is invariant to where the score zero sits (it only uses the *ordering* of points, not a ratio against an
origin) and keeps the full two-axis picture instead of collapsing it into one number. The Pareto methodology lives
in the **`nasde-benchmark-runner` skill**, not the toolkit — the toolkit's job is to record honest raw signals;
choosing a winner from them is an analysis step. The raw signals **stay and are the source of truth**:
`token_usage`, `cost_usd`, `pricing_as_of`, and the per-trial `normalized_score`. Only the derived ratios are gone.

The token/cost **definitions above are unchanged** — `input`/`output`/`total` tokens and the
"as-if-first" cost formula all remain; this section removes only the two efficiency *ratios* built on top of them.

## Reasoning effort: controlled and stamped per trial

Reasoning effort is a first-class configuration axis. nasde previously never set it, inheriting Harbor's
per-family default — and those defaults are **unequal across families** (Codex `high` is its top of three levels;
Claude `high` is 3 of 5, with `xhigh`/`max` above), so "default vs default" silently compared different thinking budgets.

- **Control.** Optional `variant.toml` field `reasoning_effort = "..."`, overridable by `nasde run --effort TEXT`.
  Priority: `--effort` > `variant.toml reasoning_effort` > unset. Unset means the effort is **not passed**, leaving
  Harbor's family default in place. The value is threaded to Harbor via the agent's `reasoning_effort` kwarg, which
  Harbor turns into the right CLI flag per family (Claude `--effort`, Codex `-c model_reasoning_effort=`, Gemini ctor arg).
- **No local validation.** The value is passed straight to Harbor, which is the source of truth: Claude and Gemini
  reject an unknown level via their own CLI `choices`, and Codex takes a free-form string. An earlier hardcoded
  per-family allow-list was removed — effort scales differ per family and change often, so a stale list does more harm
  than good (it would wrongly block a newly-valid level, and for free-form Codex it was a guess in the first place).
  Typical levels for reference (NOT enforced): Claude `low`/`medium`/`high`/`xhigh`/`max`, Codex `low`/`medium`/`high`,
  Gemini `minimal`/`low`/`medium`/`high`.

- **Stamp.** The effort is stamped onto each trial's `assessment_summary.json` (run path) and `metrics.json`
  (export path) as a `reasoning_effort` string, read back from the per-trial Harbor `config.json`
  (`config.agent.kwargs.reasoning_effort`). When no override was set the stamp is the empty string `""` — we record
  **only explicit overrides** and do **not** fabricate Codex's implicit `high` default (there is no Claude equivalent
  to fabricate, and an unset effort is a valid "family default" state, not a missing value).
- **Grouping.** The economics grouping in the run summary becomes `(agent_name, model_name, reasoning_effort)`. A
  different effort is a different configuration and is never averaged together — mirroring how a changed
  `dimensions_fingerprint` is a different benchmark.

## References

- ADR-008 — independent per-dimension scales (source of `normalized_score`).
- Anthropic pricing — https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI pricing — https://developers.openai.com/api/docs/pricing
