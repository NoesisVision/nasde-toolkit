# Assessment Criteria: Threshold Discount

Evaluate the AI-generated code across five dimensions.

## 1. Domain Modeling (0–25)

Evaluate how well the ThresholdDiscount follows DDD building blocks established by PercentageDiscount and ValueDiscount.

| Score | Criteria |
|-------|----------|
| 0     | No ThresholdDiscount type exists, or it is a plain class with mutable state |
| 5     | ThresholdDiscount exists but is a class (not a value object), or misses key DDD traits |
| 10    | ThresholdDiscount is a `readonly struct` but lacks proper equality (no `IEquatable<T>`) or factory method |
| 15    | ThresholdDiscount is a `readonly struct` with `IEquatable<T>`, but missing factory method or validation |
| 20    | ThresholdDiscount is a `readonly struct`, implements `IEquatable<T>`, has factory method, validates inputs (percentage 0–100, threshold > 0), but minor issues (e.g. missing `GetHashCode` override, inconsistent naming) |
| 25    | ThresholdDiscount is a `readonly struct`, implements `IEquatable<T>`, has static factory method (`Create` or `Of`), validates all inputs, overrides `Equals`/`GetHashCode`/`==`/`!=`, is fully immutable — matches quality of existing value objects |

**Key checks:**
- Is it a `readonly struct`?
- Does it implement `IEquatable<ThresholdDiscount>`?
- Does it have a static factory method (not just public constructor)?
- Are fields `readonly` / init-only?
- Does it validate percentage (0–100) and threshold (> 0)?
- Is it properly integrated into the Discount discriminated union (`Apply`/`Match` methods)?

## 2. Encapsulation (0–20)

Evaluate whether business rules are contained within domain objects.

| Score | Criteria |
|-------|----------|
| 0     | Discount logic spread across services or controllers |
| 5     | ThresholdDiscount exists but threshold/percentage logic partially external |
| 10    | ThresholdDiscount contains core logic but invariant validation done externally |
| 15    | All validation and calculation logic inside ThresholdDiscount; factory method enforces valid construction |
| 20    | Perfect encapsulation: ThresholdDiscount is impossible to construct in an invalid state, all business rules (percentage bounds, threshold positivity, conditional application) are internal |

**Key checks:**
- Can invalid ThresholdDiscount instances be created?
- Is the "apply only when price > threshold" rule inside the domain object?
- Are validation rules enforced at construction time?

## 3. Architecture Compliance (0–20)

Evaluate whether the new code respects existing project structure, conventions, and API contracts.

| Score | Criteria |
|-------|----------|
| 0     | Files in wrong location, wrong namespace, completely different style |
| 5     | Correct directory but wrong namespace, or significant style deviations |
| 10    | Correct location and namespace, but naming inconsistencies or missing XML documentation |
| 15    | Good location, namespace, naming, XML docs present but minor style differences |
| 20    | Perfect convention adherence: namespace, directory, file naming, XML doc style, `using` order, bracket style all match existing code. No breaking changes to the public API |

**Key checks:**
- File placed in `Sources/Sales/Sales.DeepModel/Pricing/Discounts/`?
- Namespace is `Sales.DeepModel.Pricing.Discounts`?
- Naming follows existing pattern (PascalCase, consistent with PercentageDiscount/ValueDiscount)?
- XML documentation present and follows existing style?
- Do existing PercentageDiscount and ValueDiscount cases still work unchanged?

## 4. Extensibility (0–15)

Evaluate how well the discriminated union design supports adding future discount variants.

| Score | Criteria |
|-------|----------|
| 0     | Discount union not modified, or ThresholdDiscount used standalone |
| 3     | Discount union modified but existing variants broken |
| 6     | Third variant added to Discount but `Apply`/`Match` methods missing or incomplete |
| 9     | Third variant added, `Apply` works, but `Match`/pattern matching not updated |
| 12    | Full integration: third variant, `Apply` correct, `Match` updated, but minor issues |
| 15    | Seamless integration: third variant in Discount, `Apply` method correct, `Match`/`Switch` patterns updated, all existing callers compile. Adding a 4th variant would follow the same clear pattern |

**Key checks:**
- Does `Discount` have a third case/variant for ThresholdDiscount?
- Does `Apply(Money price)` return correct result (apply only when price > threshold)?
- Are pattern matching methods (`Match`, `Switch`, or C# pattern match) updated?
- Would adding a 4th discount variant be straightforward following the same pattern?

## 5. Test Quality (0–20)

Evaluate the quality and coverage of tests for ThresholdDiscount.

| Score | Criteria |
|-------|----------|
| 0     | No tests written |
| 4     | One or two basic tests, no edge cases |
| 8     | Tests exist for basic apply logic but miss edge cases (at-threshold, zero price, boundary) |
| 12    | Good coverage of apply logic including threshold boundary, but missing equality tests or factory validation tests |
| 16    | Comprehensive: apply above/below/at threshold, factory validation, equality checks, but minor issues |
| 20    | Excellent: tests cover apply (above, below, at threshold, zero), factory validation (invalid percentage, negative threshold), equality/inequality, follows existing test class structure and naming conventions exactly |

**Key checks:**
- Tests for: price above threshold (discount applies), price below threshold (no discount), price exactly at threshold?
- Tests for factory validation (invalid percentage, zero/negative threshold)?
- Tests for value object equality?
- Test file location mirrors source structure?
- Test naming convention matches existing tests?
