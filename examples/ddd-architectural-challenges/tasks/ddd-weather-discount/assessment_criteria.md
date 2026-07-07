# Assessment Criteria: Weather-Based Discount (v2, calibrated 2026-07)

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
- When a "Deterministic pre-check signals" section is present in your prompt, its
  facts override your own impression for the overlapping checks (R1–R4): stay
  consistent with the signals and use Read only to collect the evidence quotes.
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

## 1. Model & Composition Fit (0–50) — `model_fit`

**M1 (0–10) — World-state closure and purity (hard invariant).** Weather is fetched
exactly **once per price calculation**, awaited before modifier application, and the
returned modifier closes over the resolved **value** — no provider reference escapes
past the factory boundary. `ApplyOn` stays `[Pure]`: no I/O, no async, no
sync-over-async anywhere in the application path. Needing memoization/caching to avoid
repeated calls is itself evidence the state was closed in the wrong place.
- FULL: single upfront fetch (ideally parallel with other I/O, matching the house
  tuple-await style), value-closed modifier, pure application.
- PARTIAL: single fetch per calculation but awaited sequentially where the house style
  is parallel, or the closure captures a provider it no longer needs.
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
- FULL: conditional composition in the factory (e.g., rules filtered against the
  once-fetched conditions before aggregation); no null-object class anywhere.
- PARTIAL: no null-object class, but a self-disabling modifier is always present in the
  chain (condition checked inside `ApplyOn`, or an always-included empty aggregate).
- NONE: a named null-object class is introduced and unconditionally aggregated.

**M5 (0–7) — Explicit interaction with existing discounts.** The model must NOT
silently assume the weather discount stacks on top of the whole offer. The decision
(stack / exclusive / min) must be visible somewhere: modeled as a composition idiom
(like `.Or` / `min()`), tested, or at minimum stated in code or an assumptions note.
Application order matters: applying weather BEFORE special offers feeds discounted
quotes into `IndividualSalesConditions`' `min()` comparisons — score NONE for that.
- FULL: interaction decision explicit and consistent with the model's idioms.
- PARTIAL: stacking assumed but at least stated (comment/test names the assumption).
- NONE: silent stacking, or weather applied before the existing chain.

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
should be byte-identical. Checks R1–R4 are also computed mechanically — when the
pre-check section is present, stay consistent with it.

**R1 (0–8) — Pre-existing files untouched beyond the touchpoints; no fabrication.**
Verify by Reading: `Pricing/CalculatePrices.cs` (three-way tuple await, no weather
dependency), `Pricing/OfferModifier.cs` (no extra classes unless justified),
`Sales.Adapters/Integrations/RiskManagementInMemoryCalls.cs` (still throws
`NotImplementedException`), `Monolith.Startup/Program.cs`.
- FULL: only touchpoints modified (additive package refs OK).
- PARTIAL: 1–2 avoidable modifications (e.g., `CalculatePrices` gained a weather
  dependency; an extra class added to a shared pre-existing file).
- NONE: 3+ pre-existing files modified, or ANY behavior fabrication (e.g.,
  `NotImplementedException` replaced by `Money.Of(decimal.MaxValue, ...)` — silently
  granting unlimited credit in an unrelated integration).

**R2 (0–5) — Author's annotations preserved.** Read these pre-existing files and
confirm they still carry `[DddDomainService]`: `Pricing/Discounts/ClientLevelDiscounts.cs`,
`Pricing/Discounts/ProductLevelDiscounts.cs`, `Pricing/IndividualSalesConditions.cs`,
`Pricing/SpecialOffers/SpecialOffer.cs`, `ThreeForTwo.cs`, `EverySecondBoxForHalfPrice.cs`.
Stripping the author's annotations (e.g., to appease convention-based DI scanning) is
an unjustified rewrite of deliberate model markup: NONE if 2+ files stripped, PARTIAL
if 1.

**R3 (0–4) — No signature rewrites of pre-existing types.** E.g.,
`AggregatedModifier(List<OfferModifier>)` changed to `IEnumerable<OfferModifier>`: the
author may have used `List` for a reason; catching author intent is a trait of good
domain modeling. PARTIAL for one cosmetic change, NONE for more or for semantic
changes.

**R4 (0–2) — No agent artifacts committed.** `CLAUDE.md`, `AGENTS.md`, `.claude/`
skill files, scratch scripts (`*.csx`), etc. FULL: none; PARTIAL: one; NONE: multiple.

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
