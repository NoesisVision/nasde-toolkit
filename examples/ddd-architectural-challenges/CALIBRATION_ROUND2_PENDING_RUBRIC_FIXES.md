# PENDING rubric v2.1 proposal — ddd-weather-discount (status 2026-07-07)

**Not applied.** Owner's decision: finish the Fable subset first, then corroborate the
check-level verdicts with cheaper judge models (Sonnet/Opus) BEFORE editing the rubric.
This file is the durable record of the proposal + the round's live state, in case the
working session's context is lost.

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
