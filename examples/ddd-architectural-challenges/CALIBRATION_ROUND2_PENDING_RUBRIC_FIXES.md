# HANDOVER SNAPSHOT (2026-07-08 evening — rubric v2.3 verified, supple-v3 probe run)

**TL;DR of the day:** v2.2 verified live on 4 trials (every prediction exact, no
inflation, no amnesty); owner rulings turned M5 direction-neutral and added the MAX
verdict → rubric v2.3, verified live same day (BAzkEPJ 0.85, prediction exact, MAX
correctly withheld); `claude-supple` instruction rewritten v1→v3 (universal text,
supple-design elements explained, anti-abstraction restraint, tests-as-documentation);
supple-v3 coding run landed in the ExchangeRate trap (modified `CalculatePrices.cs`,
never touched `OfferModifiers.cs`) — eval result below. Everything committed and
pushed; Max 20x active; Fable (coder+judge) available until 2026-07-12.

## Score table (judge = claude-fable-5, grouped by fingerprint — groups never mix)

| Trial | v2.1 `42d6a9e593cf` | v2.2 `25e9d07f8b31` | v2.3 `37ffc5f460d2` |
|---|---|---|---|
| BAzkEPJ (Fable, deeper instruction) | 0.70 | 0.79 | **0.85** (pred. 0.85 ✓) |
| ayg7ckA (Fable, vanilla) | 0.66 | 0.70 | **0.75** (42/22/11) |
| 3WwZrNY (Fable, claude-supple v3) | — | — | **0.69** (39/19/11) |
| #21 FjYQ3XQ (bucket A) | 0.66 | 0.68 | not run |
| #13 ZvSsnyg (bucket C, neg control) | 0.55 | 0.59 | **0.59** (30/23/6 — identical to v2.2; M5 NONE held: before-chain) |
| 7sJ9JK3 (Fable, claude-deeper-hint) | — | — | Fable: **0.78/0.80**; Opus: **0.78/0.78** (judge pilot) |
| Ss2F6dR (Fable, vanilla #2) | — | — | Fable: **0.72/0.74**; Opus: **0.67/0.67** — M4 NONE (NoDiscount null-object!), no base-bug fix |
| b5jkaWo (Fable, deeper-hint #2) | — | — | Fable: **0.74/0.74**; Opus: **0.73/0.73** — M4 PARTIAL, T1 PARTIAL (identity-chain composition test), no bug fix |

## Today's experiments, in order

1. **v2.2 verification (4 evals):** BAzkEPJ 0.79 (restraint 25/25 — R1 bug-fix
   exemption and R4 harness exclusion cited verbatim by the judge), ayg7ckA 0.70,
   #21 0.68 (facts-vs-verdicts discriminates: sanctioned constructor change recovers
   R3 while the List→IEnumerable author-intent rewrite stays penalized; R4 correctly
   generalized to codex's AGENTS.md), #13 0.59 (model_fit/test_quality identical to
   v2.0/v2.1 to the point — zero inflation; restraint uplift fully attributable).
2. **Publication:** PR #22 (ayg7ckA) and PR #23 (BAzkEPJ) on
   NoesisVision/nasde-calibration + 13 inline comments mapping v2.2 verdicts to code
   (7 on #22, 6 on #23); M5 comments carry "superseded by v2.3" replies.
3. **M5 base-code audit** (triggered by owner's challenge): the base has NO Pricing
   tests at all; every implemented interaction idiom chooses (ClientLevelDiscounts
   override, IndividualSalesConditions min(), SpecialOffer.Or fallback with
   unimplemented bodies); unused `AggregatedModifier` is a base-provided
   sequential-composition idiom. Conclusion: the base prescribes VISIBILITY of the
   interaction decision, not a direction.
4. **Rubric v2.3** (commits `82fa12c`, `2dd14e1`, `2f15d6f`, `7fb6a9f`): M5
   direction-neutral (tested accumulation == tested exclusivity == FULL 6/7);
   verdict **MAX (7)** — the only above-FULL verdict — for reifying
   exclusive-vs-accumulate as a configurable composition decision, gated by a
   two-part evidence bar: (a) selection point (file+line), (b) executable proof of
   the second policy; prose is not movement. Ground truth `explicit-exclusivity` →
   `explicit-interaction`. Fingerprint `fdb83b1535a6` (never ran) → `37ffc5f460d2`.
5. **v2.3 first live eval:** BAzkEPJ 0.85 (40/25/20) — M5 FULL 6 citing
   `RainDiscountIsAppliedOnTopOfProductDiscounts`; MAX not awarded (correct — its
   policy seam extends the discount LIST, not the interaction choice); M4 PARTIAL 3
   and T2 NONE held. Third rubric version in a row with exact verdict-level
   predictions. Watch item: the judge withheld MAX silently — verify future MAX
   denials cite the missing selection point.
6. **claude-supple instruction v1→v2→v3** (commits `5bf43d9`, `6a50420`): universal
   study-the-model text ("as if the original author had extended it"); dropped
   "maintaining extension points for the future" (the phrase that biased BAzkEPJ
   toward always-in-chain structure); v3 adds a compact explanation of supple design
   + its six Evans elements framed as "inspiration, not a checklist", the
   anti-abstraction clause ("avoid interfaces nothing needs yet... small and concrete
   wherever the domain is concrete"), and proof discipline (edge cases; tests as the
   model's documentation — every claimed property, including extension points,
   demonstrated by an executable test, not a comment).
   **Owner's universality rule (binding):** proof-discipline and attention-direction
   hints are fine in an always-injected CLAUDE.md; naming the mechanism under test
   (where decisions live, how to treat unspecified interactions) is telegraphing —
   it converts understanding into obedience and is forbidden.
7. **supple-v3 coding run:** job `2026-07-08__17-57-38__claude-supple__fable5-supple3`,
   trial `3WwZrNY`, 15 min, harbor reward 1.0. Restrained structure as instructed
   (`Pricing/Discounts/Weather/` with 3 types, `Weather/` with 2 types — fewer
   abstractions than BAzkEPJ) **but composed in the wrong place: modified
   `CalculatePrices.cs`, never touched `OfferModifiers.cs`** — the exact
   ExchangeRate-precedent trap the rubric's base-intent note warns judges about
   (denomination ≠ policy). **Eval (v2.3, Fable): 0.69 = 39/19/11.** The measured
   diagnosis PARTIALLY refutes the first hypothesis ("restraint overpowered
   composition"): the composition MECHANICS were right — M4 FULL (eager factory-time
   filtering in its own [DddFactory], no null-object) and, first time in 16 trials,
   **M3 FULL** (zero bespoke spreading: delegates to pre-existing
   `Offer.Apply<TPriceModifier>` with canonical `PercentageDiscount`) — the
   anti-abstraction clause demonstrably worked. What failed is the ENTRY POINT and
   the PROOF: M2 PARTIAL (proper weather factory, but applied via a second
   `.Apply(weatherDiscount)` in `CalculatePrices.cs:41` instead of the
   OfferModifiers chain → also R1 PARTIAL off-touchpoint), M5 PARTIAL (silent
   stacking re existing chain), and **T1 NONE — the composition test that made
   BAzkEPJ shine is gone** (weather module tested in isolation only; test_quality
   11 vs deeper's 20). Net vs siblings: v3 instruction fixed M3+M4 (+7 over deeper's
   verdicts) but lost M2+T1+M5 (−13). Instruction v4 question for tomorrow: anchor
   the entry point and composition-testing WITHOUT telegraphing — candidates:
   strengthen "study how the pieces compose into a whole" and extend proof
   discipline to "properties of the change's integration with the existing model",
   both still mechanism-free. Also note: proof discipline delivered module-level
   tests (T3/T4/T5 FULL) but not integration-level ones — the wording says
   "properties your design claims" and the model read "design" as "my new module".

### 2026-07-09 addendum — deeper-hint probe + judge pilot (autonomous task)

Article matrix settled: TWO Fable arms only (vanilla, claude-deeper-hint = minimal
'think deeper' CLAUDE.md hint, instruction untouched), n=3 each; Opus/Sonnet ± skill
arms in a later session; judge-cost and orchestration-cost threads CUT from the
article (owner). claude-supple-hint instruction-override feature REVERTED (benchmark
invariant: instruction belongs to the benchmark, never to a variant); claude-supple
(rich v3) parked as internal exploration.

Probe trial `7sJ9JK3` (job 2026-07-09__14-33-46, reward 1.0, hint mount smoke-checked):
found+fixed the SAME latent base bug as BAzkEPJ (Discount.Value isPercentage) plus a
ValueDiscount GetHashCode null-safety fix, both covered by DiscountTests — two
independent 'think deeper' runs found the bug; vanilla and supple2 did not.
Fable evals: 0.78 (44/25/9) and 0.80 (44/25/11) — model_fit 44 = RECORD (M4 FULL,
M5 FULL via AggregatedModifier idiom, M3 PARTIAL hidden GrantedDiscounts); weakness
is tests again: T1/T2 NONE, T4 PARTIAL (NeverDisruptsPricingWhenObservingRealWeather
hits the real API during dotnet test). vs the instruction-swap probe 0.85: better
model mechanics, all of the gap is test_quality (10 vs 20 — no composition test).
Opus 4.8 evals (judge pilot): 0.78 (41/25/12) and 0.78 (44/19/15) — headline
agreement with Fable excellent (0.78 vs 0.79 mean); dimension level one genuine
gray-zone split (Opus#2 read the extra ValueDiscount null-safety edit as R1
PARTIAL/'avoidable modification' where Fable and Opus#1 folded it into the bug-fix
exemption). Opus cites rubric checks by name, applies harness-mount exclusion
correctly — reads the rubric's language well. Rubric v2.4 candidate: define whether
a SECOND, adjacent fix in the same shared file stays inside the bug-fix exemption.

## Next actions (in order)

1. Analyze the 3WwZrNY eval against the hypothesis above; decide instruction v4
   (universality rule applies — no mechanism naming).
   v2.4 CANDIDATE (do NOT apply while the v2.3 table is filling — fingerprint bump
   would orphan the group): sharpen the M5 FULL/PARTIAL boundary — the judge read
   "modeled as an explicit idiom" as covering composition via the base
   AggregatedModifier in ChooseFor (ayg7ckA M5 FULL 6 without any composition test),
   while the PARTIAL example calls untested stack-after "silent". Decide whether
   idiom-without-test is FULL (current judge reading; the test gap is already priced
   in T1) or PARTIAL, and say it explicitly. PR naming convention (owner): #22 =
   vanilla, #23 = supple, #24 = supple2.
2. Complete the v2.3 table: remaining #21, #16, #14 — one password each.
   Done under v2.3: BAzkEPJ 0.85, ayg7ckA 0.75, 3WwZrNY 0.69, #13 0.59 (control clean).
   PR #24 carries 7 inline comments mapping the v2.3 verdicts to code.
3. Opus 4.8 back-to-back on `jobs/calibration-round2/` (13 trials assembled):
   originally v2.0 (`git restore --source 22d6dde -- tasks/ddd-weather-discount/`)
   vs v2.2; now a v2.3 pass is the more interesting endpoint — owner to choose the
   version pair. `--eval-model claude-opus-4-8`, per-eval gating.
4. Exports to nasde-results: fable5-coder / fable5-deeper / fable5-supple3 jobs and
   refreshed calibration-round2 (new v2.2/v2.3 assessment files) — commit+push
   (precedent established; last push 4d1ff59 contains only the v2.1 state).
5. Optional: #18 under current rubric (live cap demo — the cap has never fired).

**Budget reality:** plan upgraded to **Max 20x** on 2026-07-08 — one Fable eval
(7–21 min) now ≈ 5–10% of a 5h window; a coding run ≈ 15 min. Fable disappears after
**2026-07-12** — Fable-judge and Fable-coder work has priority until then. Per-eval
gating by the owner stays in force regardless of headroom. Auth: claude CLI keychain
works for evals; sandbox coding runs need CLAUDE_CODE_OAUTH_TOKEN (extracted from
keychain at runtime by the scratch launchers — never print it).

**Where everything lives:** toolkit PR #75 (branch `calibration/ddd-weather-discount-v2`);
sink PRs #9–#21 with 60 inline comments + PR #22 (ayg7ckA) and PR #23 (BAzkEPJ) with
13 v2.2-verdict comments (NoesisVision/nasde-calibration, GitHub is canonical);
durable results in NoesisVision/nasde-results (main); review reports on sink branch
`nasde-calibrate`.

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
