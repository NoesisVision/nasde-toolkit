# HANDOVER SNAPSHOT (2026-07-08, end of working session)

**Rubric lineage:** v2.0 `22d6dde` (fp `8e0d00bfd8df`) → v2.1 `feec7b9` (fp
`42d6a9e593cf`, verified live) → v2.2 `5c49d8e` (fp `25e9d07f8b31`, verified live
2026-07-08: BAzkEPJ 0.79 / ayg7ckA 0.70 / #21 0.68 / #13 0.59 neg-control clean;
facts-vs-verdicts rule discriminates — sanctioned constructor change recovers R3,
#21's List→IEnumerable rewrite stays penalized) → **v2.3 (fp `37ffc5f460d2`,
CURRENT)** — M5 direction-neutral: spec is silent on discount interaction and the
agent cannot ask, so a TESTED assumption (accumulation or exclusivity alike) is an
explicit decision, not a deduction (FULL, 6/7); the 7th point is the verdict **MAX** —
the only above-FULL verdict in the rubric — reserved for reifying the choice itself:
exclusive-vs-accumulate as a configurable composition decision, both policies
expressible (the way `.Or` vs `AggregatedModifier` embody the two directions),
demonstrated both ways in tests. Base-intent note corrected after code
audit (base has NO Pricing tests; all implemented interaction idioms choose —
ClientLevelDiscounts override, min(), .Or fallback — but unused AggregatedModifier
is a base-provided sequential-composition idiom, and special-offer bodies are
unimplemented). Ground truth `explicit-exclusivity` renamed → `explicit-interaction`.
(Lineage note: v2.3 was amended same-day pre-first-run, fp `fdb83b1535a6` →
`37ffc5f460d2`; the earlier fp never ran, so no evaluations are affected.)
v2.3 has NO live evaluations yet. Expected v2.3 re-scores: BAzkEPJ M5 0→6 (composition
tested through ChooseFor, single direction) ≈ 0.85; ayg7ckA M5 0→~4 (intra-weather
tested, chain interaction still silent) ≈ 0.74; #13 unchanged (before-chain stays
NONE). No trial so far models the configurable-policy ceiling.

**Live results so far** (all judge=claude-fable-5): v2.1 anchors #21 0.66 / #16 0.64 /
#14 0.63 / #13 0.55 (neg. control exact) / #18 not run (cap-by-construction); Fable
as coder: vanilla `ayg7ckA` 0.66, deeper-instruction probe `BAzkEPJ` 0.70 (record;
first composition test in 15 trials; found+fixed base `Discount.Value` bug). v2.2:
BAzkEPJ 0.79 (restraint 25/25 — R1 bug-fix exemption + R4 harness exclusion fired
verbatim), ayg7ckA 0.70, #21 0.68 (no amnesty for the author-intent rewrite), #13
0.59 (model_fit/test identical to v2.0/v2.1 — zero inflation). Trials published for
review: PR #22 (ayg7ckA), PR #23 (BAzkEPJ) on NoesisVision/nasde-calibration, with
13 inline comments mapping v2.2 verdicts to code.

**Next actions (in order):**
1. Opus 4.8 back-to-back: v2.0 (`git restore --source 22d6dde -- tasks/ddd-weather-discount/`)
   vs **v2.2** (branch head; v2.1 was transitional). Same 13-trial job dir
   `jobs/calibration-round2/`, `--eval-model claude-opus-4-8`, n=2 if budget allows;
   per-eval gating via `calibration_round2_eval_one.sh` (edit MODEL inside or copy).
2. Optional: #18 under current rubric (live cap-application demo), Fable eval of
   `BAzkEPJ`/`ayg7ckA` under v2.2, `variants/claude-supple` coding run (ready, unrun).
3. `calibration_round2_check.py` computes acceptance per fingerprint group from the
   working tree's dimensions file; export results via `nasde results-export` to the
   nasde-results repo (commit+push — precedent established).

**Budget reality:** one Fable eval = 12–21 min ≈ 20–40% of a Max-5x 5h window; runs
are gated per-eval by the owner. Auth: claude CLI keychain works for evals; sandbox
coding runs need CLAUDE_CODE_OAUTH_TOKEN (extracted from keychain at runtime by the
scratch launchers — never print it).

**Where everything lives:** toolkit PR #75 (branch `calibration/ddd-weather-discount-v2`);
sink PRs #9–#21 with 60 inline comments (NoesisVision/nasde-calibration, GitHub is
canonical); durable results in NoesisVision/nasde-results (main); review reports on
sink branch `nasde-calibrate`.

---

# Rubric v2.1 — ddd-weather-discount (APPLIED 2026-07-07, verification pending)

**Status update:** after the Fable subset completed (10/10, formal check: 5 PASS /
2 FAIL, both FAILs = the defects below), the owner approved applying the M1/M4/M5
edits immediately — as separate commits — to enable a retroactive **Opus 4.8
before/after comparison**. Sonnet corroboration was dropped (Opus instead, later).

- **BEFORE (rubric v2.0):** commit `22d6dde` — dimensions fingerprint `8e0d00bfd8df`
- **AFTER (rubric v2.1):** commit `feec7b9` — dimensions fingerprint `42d6a9e593cf`

## Opus back-to-back procedure (planned for 2026-07-08)

1. "Before" pass: materialize the v2.0 task files, e.g.
   `git restore --source 22d6dde -- tasks/ddd-weather-discount/`
   then `uv run nasde eval jobs/calibration-round2 -C . --eval-model claude-opus-4-8
   --eval-backend claude --eval-repetitions 2` (or per-trial via
   `calibration_round2_eval_one.sh` under budget gating). Evals land in fingerprint
   group `8e0d00bfd8df`.
2. "After" pass: `git restore --source feec7b9 -- tasks/ddd-weather-discount/` (or
   branch head) and repeat — evals land in `42d6a9e593cf`. Groups never mix; the
   check script derives the fingerprint from the working tree, so run it once per
   state.
3. Compare per-group summaries (same trials, same judge, only the rubric differs) —
   this isolates the rubric edit as the sole variable.

**No verification runs executed yet** (Fable window exhausted ~2026-07-07 evening;
planned after reset). Fable v2.1 verification = re-run the 5-trial subset
(`calibration_round2_fable_subset.sh`, now fingerprint-dynamic) and re-check
acceptance: expected order 0.66/0.64/0.58/0.55/0.445, Spearman 1.0.

---

## Live v2.1 verification + Fable-coder experiments (2026-07-08)

All predictions from the simulation were confirmed by live single evals
(judge claude-fable-5, fingerprint `42d6a9e593cf`); reference order restored:

| Trial | Bucket | v2.0 mean | v2.1 live | Wording validated |
|---|:---:|:---:|:---:|---|
| FjYQ3XQ #21 | A | 0.600 | **0.66** | M4 FULL (judge cites "the v2.1-approved empty AggregatedModifier"); M5 NONE→PARTIAL |
| aGTFmDh #16 | B | 0.600 | **0.64** | M1 FULL despite sequential await (was PARTIAL) |
| qHCAtXV #14 | B | 0.500 | **0.63** | M1+M5 lifts; NOTE: judge also read constructor-side rule filtering as factory-time → M4 FULL (+4 beyond simulation; defensible, ordering unharmed) |
| ZvSsnyg #13 | C | 0.550 | **0.55** | negative control EXACT (30-19-6); M4 stays PARTIAL ("self-disables inside ApplyOn"), M5 stays NONE (before-the-chain clause) — v2.1 not inflationary |
| 4njch2w #18 | D | 0.445 | not run | cap-by-construction; optional demo pending |

**Fable 5 as coding agent** (claude-vanilla, xhigh, --without-eval, then judged):

- `ayg7ckA` (standard instruction): **0.66** (36/19/11) — tied with #21; avoided every
  hard trap (parallel factory closure, factory-filtered rules M4 FULL, genuine Unknown
  M6 FULL); sins: compounding canonized in a test (M5 NONE), weather types in shared
  Pricing/Discounts (R5), Percentage-hardcoded contract (M7).
- `BAzkEPJ` ("deeper" instruction experiment): **0.70 — highest score ever recorded**
  (32/18/20). The Quality-Expectations bullet "Fit into the existing DDD architecture"
  was temporarily replaced with: *"VERY IMPORTANT - before the actual implementation
  understand the deeper idea behind the implemented Domain Driven Design model - try
  to fit in the existing model in the most conceptually sensible way - making only
  necessary changes while maintaining extension points for the future ("supple
  design" from Eric Evans). The quality of the changes in the resulting model is very
  important"*. Instruction restored afterwards; the sentence now lives in the
  **`variants/claude-supple`** variant CLAUDE.md instead (task stays canonical — an
  instruction change would invalidate cross-trial comparability). CAVEAT: BAzkEPJ ran
  on the modified instruction, so it is a coaching-effect probe, not a same-task data
  point.
- Coaching effect, check-level: **first composition test in 15 trials** (T1 FULL:
  `OfferModifiersTests` drives `ChooseFor` with a product discount active and asserts
  the interaction + unavailable path) → test_quality 11→20; dedicated
  `Pricing/WeatherDiscounts` module beside SpecialOffers (R5 FULL); **and it found and
  fixed a real latent bug in the base model**: `Discount.Value(Money)` passes
  `isPercentage: true`, so value discounts silently apply a default percentage —
  no other trial noticed this. The mechanical precheck priced that fix as an
  off-touchpoint modification (R1 PARTIAL) — open rubric question for round 3:
  should a *justified, tested bug fix* in a pre-existing file cost restraint points?
  Counter-effects: model_fit dropped 36→32 (M4 back to PARTIAL — per-quote gating in
  ApplyOn instead of vanilla's factory filtering; M5 NONE again — compounding test;
  M7 registry). Net: the supple-design nudge moved modularization, testing depth and
  model comprehension, but not the interaction-decision discipline.

Original proposal record (now applied) below.

## Live state of the Fable subset (model claude-fable-5, dimensions fingerprint 8e0d00bfd8df)

5 stratified trials × 2 reps planned; evals append to trial dirs under
`jobs/calibration-round2/` (11 symlinks + 2 sink-restores; `jobs/` is gitignored).
One eval ≈ 12–21 min, ≈ 40% of a Max-5x 5h window → manual per-eval gating
(`scratchpad/fable-one.sh <suffix>`), NO loops without the owner's go.

| Trial | PR | Bucket | rep 1 | rep 2 | mean | per-dim means (mf/re/tq) |
|---|---|:---:|:---:|:---:|:---:|---|
| FjYQ3XQ | #21 | A | 0.59 | 0.61 | 0.600 | 34.0 / 16 / 10 |
| aGTFmDh | #16 | B | 0.59 | 0.61 | 0.600 | 27.0 / 22 / 11 |
| qHCAtXV | #14 | B | 0.49 | 0.51 | 0.500 | 24.0 / 20 / 6 |
| ZvSsnyg | #13 | C | 0.55 | 0.55 | 0.550 | 30.0 / 19 / 6 (identical reps) |
| 4njch2w | #18 | D | 0.45 | 0.44 | 0.445 | 29.5 / 5 / 10, precheck cap standby |

**SUBSET COMPLETE (10/10). Formal check verdict (calibration_round2_check.py):**

```
[PASS] repeatability      worst std 1.41/50 = 2.8% of scale (v1 worst: 20%)
[PASS] judge-model gap    n/a with one judge (passes trivially)
[FAIL] human agreement    spearman 0.763 < 0.8; separation violated:
                          #21 == #16 == 0.600 (A/B tie), #13 0.550 > #14 0.500 (C>B)
[PASS] disjointness       worst |r| = 0.372 (mf~tq); mf~re -0.34, re~tq -0.30 (n=5!)
[FAIL] #21 model_fit>=38  mean 34.0 (v2.1 simulation lifts it to 41)
[PASS] #13 dethroned      rank 3, model_fit 30 <= 36
[PASS] #18 cap+floor      normalized 0.445 <= 0.45, restraint 5 <= 8
[  OK] anti-gaming guard  silent (max test_quality 11 < 18)
```

Both FAILs are exactly the two v2.0 defects the pending M1/M4/M5 edits address; the
v2.1 simulation (below) restores strict reference order. Next per owner's decision:
corroborate verdict patterns with a cheaper judge before applying any edit.

Repeatability so far: all |Δ| within limits (worst: model_fit Δ2 on #14 — M7 verdict
wobble). v1 comparison: same five scored 0.77/0.72/0.70/0.94/0.84 (order inverted in
two places); v2.0 fixes the poles but shows two ordering defects (below).

## Two measured ordering defects of rubric v2.0

1. **Top tie**: #21 (A) == #16 (B) == 0.59 at n=1. #21 wins model_fit (33 vs 26), loses
   restraint (16 vs 22 — its List→IEnumerable rewrite + OfferModifier.cs off-touchpoint
   + AGENTS.md).
2. **B/C inversion (confirmed on n=2 means)**: #13 (C) 0.550 > #14 (B) 0.500.

## Check-level cause matrix (from Fable's reasoning, verdicts stable across reps)

| Check | #21 (A) | #16 (B) | #14 (B) | #13 (C) |
|---|:---:|:---:|:---:|:---:|
| M1 closure & purity | FULL | PARTIAL (seq. await) | PARTIAL (seq. await) | FULL |
| M2 policy in factory | FULL | FULL | FULL | FULL |
| M3 canonical type | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| M4 no phantoms | PARTIAL (empty aggregate) | PARTIAL (0%-guard in ApplyOn) | PARTIAL | PARTIAL |
| M5 explicit interaction | NONE (silent, after) | PARTIAL (after, stated in comment) | NONE (silent, after) | NONE (**before** the chain) |
| M6 failure ≠ measurement | **FULL** (Unavailable state) | NONE | NONE | NONE |
| M7 proportionate seam | PARTIAL | PARTIAL | PARTIAL↔FULL (wobble) | FULL |

## Proposed v2.1 edits (three, surgical — NOT applied)

1. **M1**: sequential-instead-of-parallel awaiting stops degrading to PARTIAL (style
   note at FULL); PARTIAL reserved for closures capturing more than resolved values.
   Rationale: the hard invariant (once, value-closed, pure) is fully met — half the
   heaviest check for a style nuance is disproportionate. Effect: +5 for #14 and #16.
2. **M5**: introduce a middle tier — PARTIAL for stacking applied AFTER the existing
   chain (silent or stated); NONE reserved for application BEFORE the chain (feeding
   discounted quotes into IndividualSalesConditions' min()) or tests canonizing
   compounding. Rationale: v2.0's floor equates two qualitatively different sins; the
   owner's review ranked before-the-chain as the worst variant. Effect: +3 for #21 and
   #14; #13 stays 0; #16 unchanged (already PARTIAL via stated comment).
3. **M4**: rules filtered in the factory against once-fetched conditions with an
   always-present (possibly empty) SHARED aggregate upgrades to FULL; PARTIAL reserved
   for self-disabling modifiers (condition inside ApplyOn); NONE for named null-object
   classes. Rationale: the owner called #21's shape "the only implementation of the
   recipe: add to the aggregation ONLY when the weather qualifies". Effect: +4 for #21.

## Simulation on the already-collected verdicts (no new evals needed)

```
        v2.0 measured      v2.1 simulated     reference bucket
#21     0.59               0.66               A   (1st)
#16     0.59  <- tie       0.64               B
#14     0.500 <- below C   0.58               B
#13     0.550              0.55               C
#18     0.445 (cap)        0.445 (cap)        D   (last)
```

Order under v2.1 = exactly the human reference, with sane gaps. Caveats:
(a) #16/#21 rows rest on n=1 until their second reps land; (b) simulation reuses
v2.0 verdicts — a live v2.1 confirmation run is still required before acceptance.

## Application protocol (when approved)

1. Corroborate the M1/M5/M4 verdict patterns with a cheaper judge (Sonnet full 13×2
   pass planned; Opus 4.8 and codex subset later - judge-matrix in
   CALIBRATION_ROUND2_2026-07-07.md).
2. Edit `tasks/ddd-weather-discount/assessment_criteria.md` (checks M1, M4, M5 only).
3. **Bump the version marker inside `assessment_dimensions.json`** (e.g. suffix in a
   description) — criteria edits do NOT change the fingerprint by themselves, and
   without a bump v2.1 evals would silently mix into v2.0 summary groups (same
   confound class the owner vetoed for max_turns; note: evaluator params like
   max_turns are not fingerprinted at all — recording them in eval JSONs is a separate
   TODO on PR #75).
4. Re-run the acceptance assertions (`calibration_round2_check.py`) on the v2.1 group.

## Other fixed decisions of this round (owner-approved)

- max_turns stays 60 — comparability with existing evals; no criteria "reading
  economy" edits either.
- Judge cost reality: ~40% of a 5h Max-5x window per Fable eval → full plans only
  after Max 20x; cheap-model statistics first.
- Reference buckets: A={FjYQ3XQ}, B={2yQqBnm,3vwBnrU,qHCAtXV,aGTFmDh,SnS5iHF},
  C={SuuU3yh,Kc8Es5k,ZvSsnyg,Jyu9YsY,cE8V77t}, D={4njch2w,URtZnzf}.
