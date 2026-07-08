# Assessment Criteria: Weather-Based Discount (v2.3, calibrated 2026-07)

v2.1 recalibrated three model_fit checks (M1, M4, M5) from the measured Fable subset
(see CALIBRATION_ROUND2_PENDING_RUBRIC_FIXES.md): style is no longer priced as an
invariant (M1), the factory-filtered empty-aggregate shape earns full credit (M4),
and stacking-after is separated from applying-before-the-chain (M5). v2.2 adds the
findings of the live verification: a justified, tested bug fix in pre-existing code
is restraint-neutral (R1), harness-injected files are not agent artifacts (R4), and
construction-time qualification resolution is codified as factory-time (M4). v2.3
makes M5 direction-neutral: the spec is silent on discount interaction and the agent
cannot ask, so a TESTED assumption (accumulation or exclusivity alike) scores as an
explicit decision — only invisible or model-breaking interaction is penalized.

This task uses its own dimension set (task-level `assessment_dimensions.json`):
**model_fit (0–50)**, **restraint (0–25)**, **test_quality (0–25)**. The rubric is a
**checklist of decidable questions**, not a quality scale. For every check: find
concrete evidence (file + line), assign a verdict — **FULL** (full points), **PARTIAL**
(half, rounded down), **NONE** (zero) — quote the evidence in your reasoning, and sum
the check points to get the dimension score.

Hard rules:

- Each failure mode is scored in **exactly one** check of **exactly one** dimension.
  Never deduct twice for the same evidence.
- Do not reward or punish anything this rubric does not ask about. In particular, do
  NOT score based on whether a `Precipitation` value object exists — value-object
  liberality is not a check in this rubric.
- The "Agent diff" section of your prompt points at the full unified diff of the
  agent's work (start state → final workspace). It is the authoritative record of
  what the agent changed: answer every change-related check from the diff (Grep it —
  removed lines start with `-`), not from impressions of the final state.
- When a "Deterministic pre-check signals" section is also present, treat its signals
  as FACTS (which files changed, which lines were removed) — never dispute them. The
  VERDICTS remain yours: a file listed outside the touchpoints may still score
  R1-neutral when it is a justified, tested bug fix. `suggested_scores` are advisory
  anchors, not decisions.
- Verify against the code, not against the agent's comments or naming.

## Base-model intent (read this before scoring)

The start state (`itlibrium/DDD-starter-dotnet @ 7950712`) encodes the author's design
intent. Facts you must know to score correctly:

- `Sources/Sales/Sales.DeepModel/Pricing/OfferModifier.cs`: `OfferModifier.ApplyOn(Offer)`
  is marked `[Pure]`. `AggregatedModifier(List<OfferModifier>)` aggregates modifiers.
- `Sources/Sales/Sales.DeepModel/Pricing/CalculatePrices.cs` (domain service) awaits ALL
  async I/O upfront in parallel (price lists, `OfferModifiers.ChooseFor(offerRequest)`,
  exchange rates), then applies pure modifiers to the immutable `Offer`/`Quote` tree.
  It contains **no conditional logic** — it is a straight pipeline.
- `Sources/Sales/Sales.DeepModel/Pricing/OfferModifiers.cs` is a `[DddFactory]` — the
  codebase's **single decision point for pricing policy**: all repository/world-state
  access for policy choice happens there; it returns a composed pure modifier chain
  `ThreeForTwo.Or(EverySecondBoxForHalfPrice.Or(fallback))`.
- `ExchangeRate` is a `struct : PriceModifier` — **denomination, not policy**. That FX
  is fetched in `CalculatePrices` is NOT a precedent for fetching weather there: a
  weather discount is an `OfferModifier` (policy) and belongs to the factory.
- Discount interaction is decided **explicitly** wherever the base model implements it:
  `ClientLevelDiscounts` overrides (product-specific ELSE base), `IndividualSalesConditions`
  takes per-quote `min()` of client vs product paths, `SpecialOffer.Or(...)` names an
  exclusive fallback (bodies unimplemented — intent visible in shape only). The base
  also ships `AggregatedModifier`, an unused sequential-composition idiom — so the model
  points at BOTH choosing and composing; it prescribes visibility, not a direction.
  Note: the base has no Pricing tests at all — interaction idioms exist in code shape
  only, and the agent has no test precedent to imitate.
- The canonical shape of an offer-wide percentage discount already exists:
  `ClientLevelDiscounts`' base-discount path applies a `PercentageDiscount` to every
  quote (unless a product-specific discount overrides it). Value objects `Discount`
  (percentage|value union), `PercentageDiscount`, `ValueDiscount`, `ProductDiscount`
  live in `Sources/Sales/Sales.DeepModel/Pricing/Discounts/`.
- The modifier-application path is hot: `QuoteModifier.ApplyOn` runs once per quote per
  modifier (and `IndividualSalesConditions` evaluates two sub-modifiers per quote).
  Anything impure there multiplies.

## 1. Model & Composition Fit (0–50) — `model_fit`

**M1 (0–10) — World-state closure and purity (hard invariant).** Weather is fetched
exactly **once per price calculation**, awaited before modifier application, and the
returned modifier closes over the resolved **value** — no provider reference escapes
past the factory boundary. `ApplyOn` stays `[Pure]`: no I/O, no async, no
sync-over-async anywhere in the application path. Needing memoization/caching to avoid
repeated calls is itself evidence the state was closed in the wrong place.
- FULL: single upfront fetch, value-closed modifier, pure application. Sequential
  instead of parallel awaiting is a style note — mention it, do NOT deduct for it:
  this invariant is about closure and purity, not await shape.
- PARTIAL: no fetch is reachable from the application path, but the closure captures
  a provider (or other unresolved dependency) it no longer needs.
- NONE: any fetch reachable from `ApplyOn` (lazy, per-quote, `.Result`/`.Wait()`).

**M2 (0–9) — Policy is assembled in the factory.** The weather discount is composed
inside `OfferModifiers.ChooseFor` (directly, or via a weather factory called from it),
NOT bolted onto `CalculatePrices` as an extra awaited dependency and a second
`.Apply(...)` step.
- FULL: `CalculatePrices` unchanged; weather policy enters the offer exclusively
  through the `OfferModifiers` chain.
- PARTIAL: weather resolved via a proper `[DddFactory]` but applied through a second
  path in `CalculatePrices`.
- NONE: weather provider (or a rule collection) injected into `CalculatePrices` itself
  — a policy registry inside the orchestrator.

**M3 (0–9) — Canonical discount type reuse.** The weather discount is an offer-level
percentage discount. Canonical modeling: a **generic** `OfferLevelDiscount` (any name;
generality is what counts) in `Pricing/Discounts` that spreads a `PercentageDiscount`
over the quotes of all products exactly the way `ClientLevelDiscounts`' base-discount
path does — or direct reuse of `ClientLevelDiscounts` with an empty product list.
- FULL: generic offer-level discount type in the shared Discounts module, reusing the
  `Discount`/`PercentageDiscount` value objects.
- PARTIAL: reuses `PercentageDiscount`/`Discount` values, but the generic "apply to all
  quotes" behavior is weather-specific or hidden (private nested class, weather-named
  base class) instead of living as a reusable type in `Pricing/Discounts`.
- NONE: a bespoke `WeatherPercentageDiscount`-style type whose only feature is applying
  a percentage to quotes — duplication, not consistent with the model.

**M4 (0–7) — No phantom modifiers, no null-objects.** The factory adds the weather
modifier to the aggregation ONLY when the weather qualifies. A `NoDiscount` /
`NoOfferModifier` null-object class **has no reason to exist** — it comes from
over-engineering. Quotes must never pass through dead modifiers: `Quotes` may later be
used to explain which discounts were applied.
- FULL: conditional composition in the factory — rules/discounts filtered against the
  once-fetched conditions BEFORE aggregation; no null-object class anywhere. An
  always-present but possibly-empty SHARED aggregate (e.g. an empty
  `AggregatedModifier`) does not spoil FULL: the qualification decision already
  happened in the factory and quotes never traverse a phantom modifier. Resolution at
  CONSTRUCTION time counts as factory time: a modifier whose constructor pre-resolves
  the applicable rules/discounts from the fetched conditions (so `ApplyOn` only
  consults that pre-resolved state) also qualifies as FULL.
- PARTIAL: no null-object class, but a self-disabling modifier is always present in
  the chain — the qualification condition is evaluated at APPLICATION time inside
  `ApplyOn`, not pre-resolved at factory/construction time.
- NONE: a named null-object class is introduced and unconditionally aggregated.

**M5 (0–7) — Explicit interaction with existing discounts.** The specification does
NOT define how the weather discount interacts with existing discounts, and the agent
has no channel to ask — so the DIRECTION of the choice is free: accumulation on top of
the offer, exclusivity, or a min/max competition are all acceptable readings (the base
model itself points both ways: `.Or`/`min()` choose, `AggregatedModifier` composes).
What this check scores is the VISIBILITY of the decision, not its direction. A test
that pins the chosen semantics is the strongest form of visibility — including a test
that introduces a hypothetical second weather rule to demonstrate how multiple weather
discounts combine; do NOT deduct such a test for "lacking spec basis". With a silent
spec and no way to interact, a tested assumption is the correct engineering move.
The EXEMPLARY ceiling goes one step further: since the business has not decided, the
strongest model treats exclusive-vs-accumulate as a CONFIGURATION decision — both
policies expressible through composition idioms (the way `.Or` and `AggregatedModifier`
already embody the two directions), selectable without touching the discount logic.
Any genuine movement in this direction earns the top of the range.
Application order remains a hard constraint: applying weather BEFORE special offers
feeds discounted quotes into `IndividualSalesConditions`' `min()` comparisons and
breaks the semantics of the model's existing decisions.
- FULL: the interaction semantics — whatever direction — are visible and consistent:
  pinned by a test that exercises the composition with existing discounts, or modeled
  as an explicit idiom. A tested accumulation assumption and a tested exclusivity
  decision score identically: 6 of 7. Award the full 7 ONLY when the choice itself is
  modeled: both policies expressible and selectable at composition/configuration time
  (an explicit combinator choice, a policy seam demonstrated both ways in tests) —
  reward any genuine movement in this direction.
- PARTIAL: the interaction with EXISTING discounts is only implicit — e.g. the weather
  modifier stacks after the chain silently (even if intra-weather semantics are
  tested), or the decision is stated in a comment/assumptions note but never tested.
- NONE: weather applied BEFORE the existing chain (feeding discounted quotes into
  `IndividualSalesConditions`' `min()` comparisons), or self-contradictory semantics
  (code and tests disagree about the interaction).

**M6 (0–4) — Failure is not a measurement.** API failure must be distinguishable from
a measured zero. Encoding failure as `Clear()`, `Unknown => new(0)`, or
`Unavailable ≡ With(0)` makes the domain assert weather it never observed — and breaks
the announced future rules (a temperature rule `< 0°C` would fire exactly when the API
is down).
- FULL: explicit unknown/unavailable state (or the factory simply omits the modifier on
  failure, so no fake reading enters the model); ordering never breaks on API failure.
- PARTIAL: failure degrades gracefully to "no discount" but is representable only as a
  fake zero reading.
- NONE: failure state is value-equal to a real measurement and flows into rules.

**M7 (0–4) — Proportionate, future-ready seam.** Adding the announced future discounts
(temperature, wind, cloud, humidity, UV) is a one-class change; the extension contract
accepts the `Discount` union (percentage AND value), not a hardcoded `Percentage`. The
seam is as small as the problem: registries for n=1, static rule tables,
fetch-plan/parameter-negotiation machinery, or options patterns are speculative
generality; latent runtime traps for future rules (e.g., an adapter switch throwing
`ArgumentOutOfRangeException` for unmapped parameters) cap this at PARTIAL.

## 2. Boundaries & Restraint (0–25) — `restraint`

This dimension scores respect for the author's pre-existing code. The allowed
touchpoints for this feature are: `Sources/Sales/Sales.DeepModel/Pricing/OfferModifiers.cs`
(new dependency + composition), `Sources/Monolith.Startup/DI/Modules/Sales.cs`
(registration), and `.csproj` files (package references). Everything else pre-existing
should be byte-identical. **Answer R1–R4 from the agent diff**: the diffstat lists
every touched file; Grep the diff file for removed lines (`^-`). Checks R1–R4 may also
arrive pre-computed in the pre-check section — stay consistent with it.

**R1 (0–8) — Pre-existing files untouched beyond the touchpoints; no fabrication.**
From the diffstat: which pre-existing files were modified, beyond the touchpoints?
Confirm suspicious ones by Reading (e.g. `Sales.Adapters/Integrations/RiskManagementInMemoryCalls.cs`
must still throw `NotImplementedException`; `Pricing/CalculatePrices.cs` must keep the
three-way tuple await with no weather dependency).
- FULL: only touchpoints modified (additive package refs OK).
- PARTIAL: 1–2 avoidable modifications (e.g., `CalculatePrices` gained a weather
  dependency; an extra class added to a shared pre-existing file).
- NONE: 3+ pre-existing files modified, or ANY behavior fabrication (e.g.,
  `NotImplementedException` replaced by `Money.Of(decimal.MaxValue, ...)` — silently
  granting unlimited credit in an unrelated integration).
- **Justified bug fix is R1-neutral.** An off-touchpoint modification does NOT count
  against R1 when all three hold: the defect is demonstrable in the base code, the
  fix is minimal, and it is covered by a test (the task explicitly allows refactoring
  existing code). Example: base `Discount.Value(Money)` passes `isPercentage: true`,
  silently turning value discounts into a default percentage — fixing that flag with
  a covering test earns no deduction. Distinguish sharply from behavior FABRICATION
  (inventing business behavior to make things run), which remains NONE.

**R2 (0–5) — Author's annotations preserved.** Grep the agent diff for removed
annotation lines (pattern: lines starting with `-` containing `[Ddd` or
`[ExternalSystemIntegration`). Stripping the author's annotations (e.g., to appease
convention-based DI scanning) is an unjustified rewrite of deliberate model markup:
NONE if annotations removed from 2+ files, PARTIAL if 1.

**R3 (0–4) — No signature rewrites of pre-existing types.** E.g.,
`AggregatedModifier(List<OfferModifier>)` changed to `IEnumerable<OfferModifier>`: the
author may have used `List` for a reason; catching author intent is a trait of good
domain modeling. PARTIAL for one cosmetic change, NONE for more or for semantic
changes.

**R4 (0–2) — No agent artifacts committed.** Scratch scripts (`*.csx`), notes, debug
dumps and other agent-created junk. IGNORE files injected by the evaluation harness
itself: root `CLAUDE.md` / `AGENTS.md` and the `.claude/` / `.codex/` directories are
mounted into the workspace by the runner (variant `sandbox_files`), not created by
the agent, and must not be penalized. FULL: no agent-created artifacts; PARTIAL: one;
NONE: multiple.

**R5 (0–4) — Modularization mirrors the surrounding design.** A separate weather
module that **exposes offer modifiers analogously to `SpecialOffers`**, wired through
the factory — the "resemble the existing code" rule. The hexagonal split mirrors the
Forex precedent: port interface in the deep model (`[ExternalSystemIntegration]`),
adapter in `Sales.Adapters/Integrations/Weather/`, typed HttpClient in the DI module.
- FULL: dedicated weather module exposing modifiers + clean port/adapter mirror.
- PARTIAL: port/adapter correct but weather types dumped into shared
  `Pricing/Discounts` (coupling it to weather), or the module hides its modifiers.
- NONE: no module boundary, or domain references HTTP types directly.

**R6 (0–2) — The domain speaks domain language.** No wire vocabulary inside the deep
model: Open-Meteo query-parameter strings (`"precipitation"`, `"temperature_2m"`) as
value-object contents, HTTP/JSON types, or status codes in `Sales.DeepModel` score
NONE. Resilience (try/catch of transport errors) belongs at the adapter boundary — a
bare `catch` inside a deep-model factory is a PARTIAL-level leak.

## 3. Test Quality (0–25) — `test_quality`

**T1 (0–9) — Composition is tested through `OfferModifiers.ChooseFor`.** At least one
test exercises the factory end-to-end and verifies how the weather discount interacts
with the existing chain (a non-identity base modifier: special offer active or client/
product discounts present). A test suite that only exercises the weather module in
isolation scores NONE here — the riskiest behavior is the interaction.

**T2 (0–5) — The single-fetch guarantee is asserted.** A test proves the weather
provider is called at most once per price calculation (e.g., counting stub).

**T3 (0–5) — Failure and boundary are tested honestly.** API-failure path asserted in
a way that can actually fail (beware vacuous assertions: if `Unknown` is value-equal to
a zero reading, `result.Should().Be(Unknown)` passes even when parsing succeeded), and
`precipitation == 0` is covered as a case distinct from "data unavailable".

**T4 (0–4) — Adapter isolation.** HttpClient mocked/stubbed (no real API calls), URL
pinned, malformed payload and non-success status covered.

**T5 (0–2) — House conventions.** Tests follow the repo's BDD style
(`Bdd.Scenario`), unit vs integration split matches the existing projects.
