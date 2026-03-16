# Task: Threshold Discount

## Context

You are working on an e-commerce system built using **Domain-Driven Design (DDD)** and **Hexagonal Architecture**. The codebase is located at `/app` (**.NET 8**, **C#**).

The sales system supports multiple types of discounts applied to product prices. Currently the system handles:
- **Percentage discounts** (e.g. 20% off) — `PercentageDiscount`
- **Fixed-value discounts** (e.g. 10 PLN off) — `ValueDiscount`

Both are exposed through a `Discount` discriminated union in:
```
Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs
```

## Requirement

Sales representatives need to be able to grant customers a **percentage discount that only activates when a product's price exceeds a defined threshold**.

Examples:
- Product costs **600 PLN**, 10% discount with a **500 PLN threshold** → final price: **540 PLN** (discount applies)
- Product costs **500 PLN**, 10% discount with a **500 PLN threshold** → final price: **500 PLN** (threshold not exceeded, no discount)
- Product costs **300 PLN**, 10% discount with a **500 PLN threshold** → final price: **300 PLN** (price unchanged)

## Scope

Implement the new discount type so that it can be used everywhere the existing discount types are already used.

## Quality Expectations

- Fit into the existing DDD architecture — follow the patterns established by `PercentageDiscount` and `ValueDiscount`
- Write tests following the conventions in the existing test suite
- Follow codebase conventions (naming, file placement, code style)

## Success Criteria

1. `dotnet build` succeeds
2. `dotnet test` passes (including new tests for `ThresholdDiscount`)
3. `ThresholdDiscount` value object exists in the correct location
4. `Discount` discriminated union has a third variant for the threshold discount

## Constraints

- Do NOT modify existing discount types (`PercentageDiscount`, `ValueDiscount`)
- Do NOT skip tests
