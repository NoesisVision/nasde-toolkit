# Calibration round 2 — ddd-weather-discount (2026-07-07)

Follow-up to [CALIBRATION_TRIAL_2026-06-05.md](CALIBRATION_TRIAL_2026-06-05.md) (round 1:
5 trials, loop proven, no rubric edits applied). Round 2 covers **all 13 published
trials** (sink PRs #9–#21 on `NoesisVision/nasde-calibration`), adds **60 inline
calibration comments** (2026-06-15, pullable via `nasde calibrate pull-comments`), a
**human-approved reference ranking**, and lands **rubric v2** for the task.

Companion reports (per-trial evidence, judge-score disagreements, comment index):
branch `nasde-calibrate` on the sink repo — `calibration-review-notes.md`,
`calibration-comments-index.md`.

## Why v1 failed (evidence)

- **Surface anchoring.** v1's domain_modeling text leads with a `Precipitation`-as-VO
  example; on PR #16 a gpt-5.5 run scored 10/25 with reasoning *only* about
  "precipitation as raw `decimal`, not a semantic value object", while opus runs gave
  20–23 for the same code. The criteria text drives the spread.
- **Instability.** domain_modeling std up to 5.03 within one judge (PR #21: runs 8–18);
  cross-model gap up to 8.7 pts (PR #16: gpt 13.3 vs opus 22.0).
- **Blindness to restraint.** The two trials that stripped the author's
  `[DddDomainService]` from six base files and rewrote `RiskManagementInMemoryCalls`
  from `NotImplementedException` to `Money.Of(decimal.MaxValue, PLN)` (silent unlimited
  credit) scored architecture_compliance 16–17/20 — above clean trials.
- **Inverted ranking.** v1's leader (#13, 0.94) is a reference bucket-C trial; both
  bucket-D trials (0.84, 0.80) outscore the only bucket-A trial (0.77).
- **Dead dimensions.** encapsulation/extensibility/architecture largely re-measured the
  same value-object signals as domain_modeling; test_quality reached 20/20 on suites
  with zero coverage of the riskiest behavior (composition with the existing chain).

## Reference ranking (human-approved, 2026-07-07)

Buckets: **A** exemplary · **B** good with flaws · **C** flawed modeling ·
**D** disqualified (out-of-feature damage; `precheck.sh` hard-fail → cap normalized
score at 0.45).

| PR | Trial | Agent | v1 | Bucket | One-liner (reviewer's terms) |
|----|-------|-------|----|:------:|------------------------------|
| #21 | FjYQ3XQ | codex-ntcoding | 0.77 | **A** | Only trial to add the discount to the aggregation ONLY when weather qualifies (rules filtered in the factory against the once-fetched state of the world); flaw: rewrote `AggregatedModifier(List→IEnumerable)` — the author's intent not respected. |
| #11 | 2yQqBnm | claude-vanilla | 0.80 | **B** | Closure in the factory exemplary, but the generic "spread discounts over quotes" hidden as a private nested class in the weather module instead of an `OfferLevelDiscount` in Discounts; empty modifier always aggregated. |
| #12 | 3vwBnrU | claude-ntcoding | 0.85 | **B** | Factory ✓, but weather types dumped into shared `Pricing/Discounts` instead of a separate weather module resembling `SpecialOffers`; wrapper decides inside `ApplyOn`. |
| #14 | qHCAtXV | claude-vanilla | 0.70 | **B** | Factory ✓, minimal touch ✓, faithful reuse of the `ClientLevelDiscounts` path; rules in `Pricing/Discounts` (module coupling), silent stacking. v1's lowest score despite solidity. |
| #16 | aGTFmDh | claude-vanilla | 0.72 | **B** | Factory ✓, `PercentageDiscount` reuse ✓; over-build: static policy registry for one rule, self-disabling 0%-guard modifier always in the chain. Main victim of v1 judge spread. |
| #17 | SnS5iHF | claude-ntcoding | 0.75 | **B** | Exemplary closure (parallel tuple-await) and module, but introduced `NoOfferModifier` — a NoDiscounts with no reason to exist (albeit placed in shared Pricing, not weather); `Percentage`-only contract cuts off `ValueDiscount`. |
| #9 | SuuU3yh | claude-ntcoding | 0.88 | **C** | State of the world closed once but NOT in the factory — second `.Apply()` path in `CalculatePrices`; its `WeatherDiscount` is de facto a WeatherPercentageDiscount duplicating the `ClientLevelDiscounts` path; failure encoded as `Clear()`. |
| #10 | Kc8Es5k | claude-ntcoding | 0.79 | **C** | Built a proper weather factory, then bypassed `OfferModifiers` anyway (applied via `CalculatePrices`); `Unavailable = new(0)`; scratch `decompile.csx` committed. |
| #13 | ZvSsnyg | claude-ntcoding-**tuned** | **0.94** | **C** | v1's leader: factory closure exemplary, but the discount is applied BEFORE special offers (feeds discounted quotes into `IndividualSalesConditions`' `min()`), `Unknown ≡ None` erases the failure state, and the failure-path test is vacuous. Score partly reflects the 569-line tuned skill, not the model. |
| #15 | Jyu9YsY | claude-ntcoding | 0.81 | **C** | Deepest factory bypass: `IEnumerable<WeatherDiscountRule>` injected into the `CalculatePrices` constructor (policy registry in the orchestrator); a test canonizes compounding (100→90→81) with no spec basis. |
| #19 | cE8V77t | codex-vanilla | 0.68 | **C** | Reviewer's manual round-1 case: `NoDiscount` with no reason to exist (and in the weather module, not Discounts), bespoke `PercentageWeatherDiscount`, and a clumsy discount factory whose rule engine broke domain invariants (phantom discounts in Quotes). |
| #18 | 4njch2w | codex-vanilla | 0.84 | **D** | Paradox: the only canonical `OfferWideDiscount` in `Pricing/Discounts` (best type reuse of all 13) — and `[DddDomainService]` stripped from six base files, `RiskManagementInMemoryCalls` rewritten to unlimited credit, `Program.cs` reworked. |
| #20 | URtZnzf | codex-ntcoding | 0.80 | **D** | Twin of #18 (same six files, same fabrication) plus raw Open-Meteo wire strings (`"temperature_2m"`) as deep-model vocabulary. |

## What round 2 lands

Round 2 has priority over prior toolkit conventions: where the loop needed toolkit
support, the toolkit was extended (per the project owner's direction), not worked
around.

**Toolkit changes (src/nasde_toolkit):**

- **Agent diff as universal judge input.** For every trial (every task, every
  benchmark), the evaluator materializes the agent's full diff (start state → final
  workspace, tracked + untracked, via the same `workspace_diff.capture_patch` used for
  `changes.patch`) into `<trial>/agent_changes.diff` and injects an "Agent diff"
  prompt section (diffstat inline + the file path for Read/Grep; the claude backend
  grants `--add-dir` on the trial dir). This gives the judge the same reference point
  a human reviewer gets — removals and out-of-feature edits become visible — without
  per-task processing and without handing the judge free-form git (which breeds
  variance: the codex judge always had shell access and demonstrably didn't use it).
- **Per-task dimensions.** `assessment_dimensions.json` placed next to a task's
  `assessment_criteria.md` now overrides the challenge-level file
  (`evaluator.resolve_dimensions_path`, used by both the evaluator and
  `calibrate publish`). Other tasks keep the shared 5-dimension file; a different
  dimensions file yields a different fingerprint, so v1/v2 evaluations are never mixed
  in one summary group.
- **Deterministic precheck hook (optional policy layer).** If a task ships
  `precheck.sh`, the evaluator runs it against the trial workspace, validates its
  JSON, injects it into the judge prompt as "Deterministic pre-check signals", records
  it in `assessment_eval_*.json`, and enforces an optional `normalized_score_cap`.
  With the agent diff as the universal input, precheck's role narrows to hard
  mechanical policy (the bucket-D disqualification cap) rather than being the judge's
  only window on changes. Any precheck failure degrades to "no precheck" with a
  warning.
- **Reviewer bundle.** `calibrate publish` now also ships
  `ground_truth_decisions.json` under `.calibration/`.

**Task changes (tasks/ddd-weather-discount):**

1. **Task-level `assessment_dimensions.json`** — three disjoint dimensions:
   `model_fit` (0–50), `restraint` (0–25), `test_quality` (0–25).
2. **`assessment_criteria.md` v2** — decidable checks (FULL/PARTIAL/NONE with
   evidence): model_fit M1–M7 (closure & purity, factory policy, canonical type reuse,
   no phantoms, explicit exclusivity, failure≠measurement, proportionate seam),
   restraint R1–R6 (touchpoints & no fabrication, annotations, signatures, artifacts,
   modularization mirror, domain language), test_quality T1–T5 (composition through
   `ChooseFor`, single-fetch guarantee, honest failure/boundary, adapter isolation,
   conventions). Anchors taken from the 13 real trials; "base-model intent" preamble
   (`[Pure]`, `[DddFactory]`, `ExchangeRate:PriceModifier ≠ policy`, explicit
   `Or`/`min()` idioms).
3. **`ground_truth_decisions.json`** — the seven reference decisions, auto-injected
   into the judge prompt.
4. **`precheck.sh`** — dual-mode (evaluator workspace / sink refs) restraint signals
   with advisory R1–R4 scores and `normalized_score_cap: 0.45` on hard fail
   (annotation stripping ≥2 files, or behavior fabrication). Smoke-tested against the
   sink: #21 → R-signals without cap; #18 → all R floored, cap 0.45.

## Acceptance criteria for the re-run (loop stop conditions)

Re-evaluate all 13 trials with v2 (2 judge models × 3 runs, as in v1). Accept v2 when
ALL hold; otherwise diagnose failing cases from judge reasoning, patch the specific
check's wording, and re-run.

1. **Repeatability:** per-dimension std within a judge model ≤ 8% of the dimension max
   (model_fit ≤ 4.0, restraint/test_quality ≤ 2.0). v1 worst: 20% (5.03/25).
2. **Judge-model agreement:** per-dimension mean gap between models ≤ 12% of the
   dimension max (model_fit ≤ 6.0, restraint/test_quality ≤ 3.0). v1 worst: 35%.
3. **Human agreement:** Spearman rank correlation (bucket ranks, ties within buckets)
   between the v2 total ordering and the reference ranking ≥ 0.8, AND strict bucket
   separation: every A total > every B > every C > every D.
4. **Dimension disjointness:** pairwise Pearson |r| between dimension scores across the
   13 trials ≤ 0.6 (v1: domain_modeling/encapsulation/architecture strongly coupled).
5. **Regression assertions (known v1 misfires):**
   - #21 model_fit ≥ 38/50 and std ≤ 4 (v1 domain_modeling: mean 12.67/25, std 5.03);
   - #16 model_fit cross-model gap ≤ 6/50 (v1: 8.7/25);
   - #13 no longer ranked #1 overall; #13 model_fit ≤ 36/50 (v1 domain_modeling 25/25);
   - #18 and #20: precheck cap holds (normalized ≤ 0.45) and restraint ≤ 8/25
     (v1 architecture_compliance 16.3/17.3 of 20);
   - no trial reaches test_quality ≥ 18/25 without a composition test through
     `OfferModifiers.ChooseFor` (in v1, two suites with zero composition coverage
     scored 20/20).

## Procedure (calibration orchestrator)

1. `nasde eval` the existing job dirs — the evaluator picks up the task-level
   dimensions, ground truth and precheck automatically (no agent re-runs needed).
2. Compute acceptance criteria 1–5 from the fresh `assessment_eval_*.json` /
   `assessment_summary.json`; report a pass/fail table.
3. On failure: pull the offending judge reasoning, map it to the specific M/R/T check,
   propose a wording diff (per the `nasde-benchmark-calibration` skill — **wait for
   approval before writing**), re-run.
4. On pass: republish with `nasde calibrate publish` for a confirmation human pass.
