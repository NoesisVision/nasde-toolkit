# Assessment Criteria: Weather-Based Discount (v2, calibrated 2026-07)

Evaluate the AI-generated code across five dimensions. This rubric is a **checklist of
decidable questions**, not a quality scale. For every check: find concrete evidence
(file + line), assign a verdict — **FULL** (full points), **PARTIAL** (half, rounded
down), **NONE** (zero) — and quote the evidence in your reasoning. Sum the check points
to get the dimension score.

Hard rules:

- Each failure mode is scored in **exactly one** check of **exactly one** dimension.
  Never deduct twice for the same evidence in two dimensions.
- Do not reward or punish anything this rubric does not ask about. In particular, do
  NOT score based on whether a `Precipitation` value object exists — value-object
  liberality is not a check in this rubric.
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
- Discount interaction is always **explicit** in this model: `SpecialOffer.Or(...)` is
  an exclusive fallback; `IndividualSalesConditions` takes per-quote `min()` of client
  vs product discounts. Nothing stacks silently.
- The canonical shape of an offer-wide percentage discount already exists:
  `ClientLevelDiscounts`' base-discount path applies a `PercentageDiscount` to every
  quote (unless a product-specific discount overrides it). Value objects `Discount`
  (percentage|value union), `PercentageDiscount`, `ValueDiscount`, `ProductDiscount`
  live in `Sources/Sales/Sales.DeepModel/Pricing/Discounts/`.
- The modifier-application path is hot: `QuoteModifier.ApplyOn` runs once per quote per
  modifier (and `IndividualSalesConditions` evaluates two sub-modifiers per quote).
  Anything impure there multiplies.

## 1. Domain Modeling (0–25) — `domain_modeling`

**DM1 (0–7) — Policy is assembled in the factory.** The weather discount is composed
inside `OfferModifiers.ChooseFor` (directly, or via a weather factory called from it),
NOT bolted onto `CalculatePrices` as an extra awaited dependency and a second
`.Apply(...)` step.
- FULL: `CalculatePrices` unchanged; weather policy enters the offer exclusively through
  the `OfferModifiers` chain.
- PARTIAL: weather resolved via a proper `[DddFactory]` but applied through a second
  path in `CalculatePrices`.
- NONE: weather provider (or a rule collection) injected into `CalculatePrices` itself.
- Anti-pattern anchor: injecting `IEnumerable<WeatherDiscountRule>` into the
  `CalculatePrices` constructor — a policy registry inside the orchestrator.

**DM2 (0–7) — Canonical discount type reuse.** The weather discount is an offer-level
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

**DM3 (0–6) — No phantom modifiers, no null-objects.** The factory adds the weather
modifier to the aggregation ONLY when the weather qualifies. A `NoDiscount` /
`NoOfferModifier` null-object class **has no reason to exist** — it comes from
over-engineering. Quotes must never pass through dead modifiers: `Quotes` may later be
used to explain which discounts were applied.
- FULL: conditional composition in the factory (e.g., rules filtered against the
  once-fetched conditions before aggregation); no null-object class anywhere.
- PARTIAL: no null-object class, but a self-disabling modifier is always present in the
  chain (condition checked inside `ApplyOn`, or an always-included empty aggregate).
- NONE: a named null-object class is introduced and unconditionally aggregated.

**DM4 (0–5) — Explicit interaction with existing discounts.** The model must NOT
silently assume the weather discount stacks on top of the whole offer. The decision
(stack / exclusive / min) must be visible somewhere: modeled as a composition idiom
(like `.Or` / `min()`), tested, or at minimum stated in code or an assumptions note.
Application order matters: applying weather BEFORE special offers feeds discounted
quotes into `IndividualSalesConditions`' `min()` comparisons — score NONE for that.
- FULL: interaction decision explicit and consistent with the model's idioms.
- PARTIAL: stacking assumed but at least stated (comment/test names the assumption).
- NONE: silent stacking, or weather applied before the existing chain.

## 2. Encapsulation (0–20) — `encapsulation`

**EN1 (0–10) — World-state closure and purity (hard invariant).** Weather is fetched
exactly **once per price calculation**, awaited before modifier application, and the
returned modifier closes over the resolved **value** — no provider reference escapes
past the factory boundary. `ApplyOn` stays `[Pure]`: no I/O, no async, no
sync-over-async anywhere in the application path. Needing memoization/caching to avoid
repeated calls is itself evidence the state was closed in the wrong place.
- FULL: single upfront fetch (ideally parallel with other I/O, matching the house
  tuple-await style), value-closed modifier, pure application.
- PARTIAL: single fetch per calculation but awaited sequentially where the house style
  is parallel, or the closure captures more than the resolved values.
- NONE: any fetch reachable from `ApplyOn` (lazy, per-quote, `.Result`/`.Wait()`).

**EN2 (0–5) — Failure is not a measurement.** API failure must be distinguishable from
a measured zero. Encoding failure as `Clear()`, `Unknown => new(0)`, or
`Unavailable ≡ With(0)` makes the domain assert weather it never observed — and breaks
the announced future rules (a temperature rule `< 0°C` would fire exactly when the API
is down).
- FULL: explicit unknown/unavailable state (or the factory simply omits the modifier on
  failure, so no fake reading enters the model); ordering never breaks on API failure.
- PARTIAL: failure degrades gracefully to "no discount" but is representable only as a
  fake zero reading.
- NONE: failure state is value-equal to a real measurement and flows into rules.

**EN3 (0–5) — The domain speaks domain language.** No wire vocabulary inside the deep
model: Open-Meteo query-parameter strings (`"precipitation"`, `"temperature_2m"`) as
value-object contents, HTTP/JSON types, or status codes in `Sales.DeepModel` score
NONE. Resilience (try/catch of transport errors) belongs at the adapter boundary — a
bare `catch` inside a deep-model factory is a PARTIAL-level leak.

## 3. Architecture Compliance (0–20) — `architecture_compliance`

This dimension scores **restraint**: respect for the author's pre-existing code. The
allowed touchpoints for this feature are: `Sources/Sales/Sales.DeepModel/Pricing/OfferModifiers.cs`
(new dependency + composition), `Sources/Monolith.Startup/DI/Modules/Sales.cs`
(registration), and `.csproj` files (package references). Everything else pre-existing
should be byte-identical. Since you have no `git`, verify by Reading the specific files
listed below.

**AC1 (0–8) — Pre-existing files untouched beyond the touchpoints.** Check that the
following files still exist in their original form and carry no weather-related or
unrelated edits: `Pricing/CalculatePrices.cs` (three-way tuple await, no weather
dependency), `Pricing/OfferModifier.cs` (`AggregatedModifier(List<OfferModifier>)`,
no extra classes unless justified), `Sales.Adapters/Integrations/RiskManagementInMemoryCalls.cs`
(still throws `NotImplementedException`), `Monolith.Startup/Program.cs`.
- FULL: only touchpoints modified (additive package refs OK).
- PARTIAL: 1–2 avoidable modifications (e.g., `CalculatePrices` gained a weather
  dependency; an extra class added to a shared pre-existing file).
- NONE: 3+ pre-existing files modified, or any behavior fabrication (e.g.,
  `NotImplementedException` replaced by `Money.Of(decimal.MaxValue, ...)` — silently
  granting unlimited credit in an unrelated integration).

**AC2 (0–5) — Author's annotations preserved.** Read these pre-existing files and
confirm they still carry their DDD markup: `Pricing/Discounts/ClientLevelDiscounts.cs`,
`Pricing/Discounts/ProductLevelDiscounts.cs`, `Pricing/IndividualSalesConditions.cs`,
`Pricing/SpecialOffers/SpecialOffer.cs`, `ThreeForTwo.cs`, `EverySecondBoxForHalfPrice.cs`
— each must still have `[DddDomainService]`. Stripping the author's annotations (e.g.,
to appease convention-based DI scanning) is an unjustified rewrite of deliberate model
markup: NONE if 2+ files stripped, PARTIAL if 1.

**AC3 (0–4) — No signature rewrites of pre-existing types.** E.g.,
`AggregatedModifier(List<OfferModifier>)` changed to `IEnumerable<OfferModifier>`: the
author may have used `List` for a reason; catching author intent is a trait of good
domain modeling. Any changed public/internal signature of a pre-existing type: PARTIAL
for one cosmetic change, NONE for more or for semantic changes.

**AC4 (0–3) — No agent artifacts committed.** `CLAUDE.md`, `AGENTS.md`, `.claude/`
skill files, scratch scripts (`*.csx`), etc. FULL: none; PARTIAL: one; NONE: multiple.

## 4. Extensibility (0–15) — `extensibility`

**EX1 (0–8) — Modularization mirrors the surrounding design.** A separate weather
module that **exposes offer modifiers analogously to `SpecialOffers`**, wired through
the factory — the "resemble the existing code" rule. The hexagonal split mirrors the
Forex precedent: port interface in the deep model (`[ExternalSystemIntegration]`),
adapter in `Sales.Adapters/Integrations/Weather/`, typed HttpClient in the DI module.
- FULL: dedicated weather module exposing modifiers + clean port/adapter mirror.
- PARTIAL: port/adapter correct but weather types dumped into shared
  `Pricing/Discounts` (coupling it to weather), or the module hides its modifiers.
- NONE: no module boundary, or domain references HTTP types directly.

**EX2 (0–4) — Adding the announced future discounts is a one-class change.** The
extension contract must accept the `Discount` union (percentage AND value), not
hardcode `Percentage`; the provider/conditions type must be able to carry new
measurements without breaking existing rules. Latent runtime traps for future rules
(e.g., an adapter switch that throws `ArgumentOutOfRangeException` for unmapped
parameters) cap this at PARTIAL.

**EX3 (0–3) — Proportionate machinery.** The seam should be as small as the problem:
a rule/policy interface is justified by the announced future discounts; registries for
n=1, static rule tables, fetch-plan/parameter-negotiation machinery, or options
patterns are speculative generality. FULL: proportionate; PARTIAL: mild over-build;
NONE: a rule engine that strains or violates the existing design.

## 5. Test Quality (0–20) — `test_quality`

**TQ1 (0–7) — Composition is tested through `OfferModifiers.ChooseFor`.** At least one
test exercises the factory end-to-end and verifies how the weather discount interacts
with the existing chain (a non-identity base modifier: special offer active or client/
product discounts present). A test suite that only exercises the weather module in
isolation scores NONE here — the riskiest behavior is the interaction.

**TQ2 (0–4) — The single-fetch guarantee is asserted.** A test proves the weather
provider is called at most once per price calculation (e.g., counting stub).

**TQ3 (0–4) — Failure and boundary are tested honestly.** API-failure path asserted in
a way that can actually fail (beware vacuous assertions: if `Unknown` is value-equal to
a zero reading, `result.Should().Be(Unknown)` passes even when parsing succeeded), and
`precipitation == 0` is covered as a case distinct from "data unavailable".

**TQ4 (0–3) — Adapter isolation.** HttpClient mocked/stubbed (no real API calls), URL
pinned, malformed payload and non-success status covered.

**TQ5 (0–2) — House conventions.** Tests follow the repo's BDD style
(`Bdd.Scenario`), unit vs integration split matches the existing projects.
