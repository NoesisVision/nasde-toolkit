# Calibration feedback-loop trial — ddd-weather-discount (2026-06-05)

First real human-in-the-loop test of `nasde calibrate` (the PR/MR rubric-calibration
feature, [ADR-010](../../docs/adr/010-git-platform-integration.md), PR
[#59](https://github.com/NoesisVision/nasde-toolkit/pull/59)). **Conclusion: the
feedback loop works end-to-end.** No rubric edits were applied — this run is a
proof-of-concept and a record of the divergences found, to return to later.

## What was published

5 trials of `ddd-weather-discount`, all sharing one start-state base
(`itlibrium/DDD-starter-dotnet @ 7950712`, n=3 evals each, judge
`claude-opus-4-7`), published as PRs (GitHub) and MRs (GitLab) to the private sink
`NoesisVision/nasde-calibration` / `noesisvision/nasde-calibration`.

| Variant | norm score (n=3) | source job | trial dir | GitHub | GitLab |
|---|---|---|---|---|---|
| tactical-ddd **tuned** | **0.94** ±0.006 | `jobs/2026-05-25__14-37-18__claude-ntcoding-tactical-ddd-weather-tuned__weather-tuned-iter3` | `ddd-weather-discount__ZvSsnyg` | PR #13 | MR !13 |
| tactical-ddd (public) | 0.88 ±0.029 | `jobs/2026-05-25__13-22-50__claude-ntcoding-tactical-ddd__weather-public-forced-1` | `ddd-weather-discount__SuuU3yh` | PR #9 | MR !9 |
| tactical-ddd (public) | 0.85 ±0.015 | `jobs/2026-05-25__14-37-15__claude-ntcoding-tactical-ddd__weather-public-iter3` | `ddd-weather-discount__3vwBnrU` | PR #12 | MR !12 |
| **vanilla** | 0.80 ±0.015 | `jobs/2026-05-25__14-37-13__claude-vanilla__weather-vanilla-iter3` | `ddd-weather-discount__2yQqBnm` | PR #11 | MR !11 |
| tactical-ddd (public) | 0.79 ±0.012 | `jobs/2026-05-25__13-22-52__claude-ntcoding-tactical-ddd__weather-public-forced-2` | `ddd-weather-discount__Kc8Es5k` | PR #10 | MR !10 |

> Note on "n=5" in the blog: that means 5 **trials** per variant (each ~1–3 evals),
> with significance computed across trials — not 5 evals on one trial. These 5 were
> picked because they each have **3 evals** (strongest per-dimension mean±std), at the
> cost of uneven variant coverage (3× public, 1× vanilla, 1× tuned, 0× guided).

Each PR/MR carried, under `.calibration/`: the task `instruction.md`,
`assessment_criteria.md`, `assessment_dimensions.json`, the three
`assessment_eval_<N>.json` (judge reasoning), `assessment_summary.json`,
`metrics.json` — plus the agent's clean diff.

## Human comments (pulled via `nasde calibrate pull-comments`)

7 inline comments across PR #11 (vanilla) and PR #13 (tuned). Verbatim summary:

**PR #11 — vanilla (0.80):**
- `OfferModifiers.cs:24` — all existing discounts are mutually exclusive; adding an
  *additive* weather discount is unjustified. Could hint in the task; but
  domain_modeling should also penalize the stacking design.
- `WeatherBasedDiscount.cs:7` — agrees a "discount" should be a value object; this
  design is odd and rightly lost points.
- `WeatherBasedDiscount.cs:28` — the weather OfferModifier is hidden here; should be
  modeled at a higher level; rightly lost points.
- `.calibration/assessment_eval_2.json:24` — architecture_compliance should credit
  how the agent fits the *existing modularization*. This agent fit **well** (added
  `Sales.DeepModel/Pricing/Weather` next to `SpecialOffers`, producing
  `OfferModifiers` — architecturally correct); it does **worse** on modeling and
  should lose points there, not on architecture.

**PR #13 — tuned (0.94):**
- `PrecipitationDiscount.cs:8` — not convinced about placing this class in
  `Pricing/Discounts`; that module is for high-abstraction classes that react to
  *offer configuration*. This discount has no link to the offer — modeling is OK but
  it belongs in a `Weather` module (like `SpecialOffer` is a modifier in
  `SpecialOffers`).
- `PrecipitationDiscount.cs:10` — an extensible model should hold a generic
  `Discount`, not a hardcoded concrete one. The 10% decision belongs to the factory in
  `OfferModifiers`. Penalize in domain_modeling.
- `OfferModifiers.cs:18` — same as vanilla: modeling-unjustified aggregation of
  discounts instead of mutual exclusion.

## Divergences diagnosed (judge vs human)

**1. domain_modeling does not penalize additive-vs-exclusive discounts.**
Judge scored domain_modeling purely on value objects (vanilla 20/25 for anemic
`WeatherData`; tuned **25/25** for proper VOs). The stacking-vs-exclusive concern
never appears in the reasoning. Rubric is too tactical-patterns-centric; it lacks a
"fidelity to existing domain rules/invariants" criterion.

**2. architecture_compliance ignores semantic module fit.**
Judge scored it mechanically (layer boundaries, port-in-domain, adapter isolation,
DI, `HttpClient.Timeout`). It does not assess whether a class landed in the module it
*semantically* belongs to. Per the human, vanilla placed it well and tuned placed it
poorly — so crediting module fit would **partly invert** the current ranking (raise
vanilla, lower tuned).

**3. extensibility/domain_modeling miss hardcoded 10%.**
Judge gave tuned extensibility 15/15 + domain_modeling 25/25, praising "new condition
= new OfferModifier class". It did not flag that the discount *value* is hardcoded in
the class rather than parameterized. Judge and human look at different extensibility
axes (new condition types vs value-as-data).

**4. Task under-specification (not a rubric issue).**
`instruction.md` never states whether the weather discount should stack with or
exclude other discounts — the root of comment #1. This is an `instruction.md` fix,
not a rubric fix.

## Headline finding

The rubric rewards **tactical-DDD pattern presence** (VOs, ports, strategies) more
than **business-modeling correctness** and **architectural placement**. That is why
the purely-tactical `tuned` scored 0.94 despite real modeling/placement flaws the
human flagged. After applying edits #1–#3, the judge's ranking would compress or
partly invert relative to the human's — a real change to benchmark output. **This is
exactly the miscalibration `nasde calibrate` is meant to surface, and it did.**

## Proposed edits (NOT applied — for later)

- **assessment_dimensions.json → domain_modeling**: add that a model contradicting
  established invariants (e.g. an additive discount where all existing discounts are
  mutually exclusive) loses points even with clean tactical patterns.
- **assessment_dimensions.json → architecture_compliance**: add semantic module fit —
  a class in a module whose domain purpose it does not share loses points even when
  layer boundaries are respected.
- **domain_modeling / extensibility**: distinguish structural extensibility (new
  classes) from parameterization (hardcoded values as code vs data).
- **instruction.md**: specify whether the weather discount stacks or excludes.

Re-measure step (re-eval on the edited rubric → new fingerprint cluster → confirm the
ranking moves toward the human's judgment) was deferred.
