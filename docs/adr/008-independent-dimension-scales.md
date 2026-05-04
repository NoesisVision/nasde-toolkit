# ADR-008: Independent per-dimension scoring scales

**Status:** Accepted
**Date:** 2026-05-04

## Context

Earlier versions of `nasde` baked a specific scoring shape into the assessment evaluator: every dimension was assumed to be on a 0–25 scale, totals were assumed to sum to 100, and authoring guidance recommended "3–5 dimensions". This assumption leaked into multiple layers:

- `evaluator.py` defaulted `DimensionScore.max_score` to `25`, clamped every score with `min(25, ...)`, and computed `normalized_score = total / 100.0`.
- The evaluator prompt told the LLM "Each dimension is 0–25 points" and showed a JSON output template with hardcoded `"max_score": 25`.
- Console output printed `Score: X/100` regardless of actual totals.
- The `nasde init` scaffold generated an `assessment_dimensions.json` with four dimensions, each `max_score: 25`, totaling 100.
- The `nasde-benchmark-creator` skill instructed authors to use "3-5 dimensions, scores summing to 100".
- `CLAUDE.md` documented the same constraint.

This was wrong on two counts.

**Methodologically**: nothing about LLM-as-a-Judge requires uniform scales. The dominant pattern in modern eval frameworks (G-Eval, MT-Bench, RAGAS, DeepEval, OpenAI Evals, Inspect AI) is **independent per-dimension scales** — each dimension picks the granularity that matches what it measures. A coarse "did the agent follow instructions?" check is naturally pass/fail or 1–3; a fine-grained "code quality" rubric may want 1–10 or 0–100. Forcing both onto a 0–25 scale destroys resolution. The "scores sum to 100" convention comes from academic grading rubrics and HR scorecards — useful in those contexts, but not load-bearing for evals.

**Practically**: benchmark authors found themselves either stretching weak dimensions to fit a 25-point scale, or compressing rich rubrics that wanted finer gradation. The fixed 3–5 count discouraged comprehensive rubrics. The clamp at 25 silently truncated any score the LLM produced above 25 — so an author who *did* write a 0–50 dimension would see correct-looking results that were quietly broken.

## Decision

Each dimension declares its own `max_score` independently. There is no constraint on:

- the value of any individual `max_score` (any positive integer),
- the sum of `max_score` across dimensions (does not need to be 100),
- the number of dimensions (no recommended minimum or maximum).

`max_score` is **required** in every dimension entry — there is no default. A missing `max_score` is an authoring error and produces a clear validation failure rather than silently picking 25.

Implementation:

- `DimensionScore.max_score` becomes a required field (no default).
- Score clamping is per-dimension: `min(dimension.max_score, score)` instead of `min(25, score)`.
- `normalized_score = total / sum(d.max_score for d in dimensions)`. Backwards compatible: a setup with four dimensions × 25 still normalizes to `100 / 100 = 1.0`.
- The evaluator prompt is constructed dynamically — it lists each dimension with its own range (`<name>: 0-<max_score>`) rather than telling the LLM "0–25 points".
- Console output reads `Score: <total>/<sum_of_max_scores>` — the denominator reflects the actual rubric, not a hardcoded 100.

## Consequences

- **Backwards compatible.** Existing benchmarks with the old 4×25=100 shape continue to work unchanged. Their `normalized_score` stays identical.
- **Higher resolution where it matters.** Authors can give a finicky dimension a 0–100 scale and a coarse one a 0–3 scale in the same rubric.
- **No silent truncation.** Scores above a dimension's `max_score` are clamped *to that dimension's* max, not to 25.
- **Stricter validation.** A dimension entry without `max_score` is now rejected at load time. (Previously it would silently default to 25.) This is a one-time correction for any rubric that relied on the implicit default.
- **Documentation simpler to teach.** The guidance becomes "pick the scale that matches the granularity you can actually distinguish" rather than "carve 100 points across 3–5 dimensions" — closer to how mature eval frameworks describe rubric design.

## References

- G-Eval (Liu et al., 2023) — uses 1–5 per criterion, criteria scored independently.
- MT-Bench (Zheng et al., 2023) — 1–10 per turn.
- RAGAS, DeepEval — per-metric independent scales, no aggregation constraint.
