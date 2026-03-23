#!/bin/bash

# DDD Threshold Discount - Reference Solution
# This script applies the reference solution to the project.

set -e

cd /app

# -------------------------------------------------------------------
# 1. Create ThresholdDiscount value object
# -------------------------------------------------------------------

DISCOUNT_DIR="Sources/Sales/Sales.DeepModel/Pricing/Discounts"

cat > "$DISCOUNT_DIR/ThresholdDiscount.cs" << 'EOF'
using MyCompany.ECommerce.Sales.Commons;

namespace MyCompany.ECommerce.Sales.Pricing.Discounts;

public readonly struct ThresholdDiscount : PriceModifier, IEquatable<ThresholdDiscount>
{
    private readonly Money _threshold;
    private readonly PercentageDiscount _discount;

    private ThresholdDiscount(Money threshold, PercentageDiscount discount)
    {
        _threshold = threshold;
        _discount = discount;
    }

    public static ThresholdDiscount Of(Money threshold, Percentage discountValue) =>
        new(threshold, PercentageDiscount.Of(discountValue));

    public Money ApplyOn(Money price) =>
        price > _threshold ? _discount.ApplyOn(price) : price;

    public bool Equals(ThresholdDiscount other) =>
        _threshold.Equals(other._threshold) && _discount.Equals(other._discount);

    public override bool Equals(object? obj) =>
        obj is ThresholdDiscount other && Equals(other);

    public override int GetHashCode() =>
        HashCode.Combine(_threshold, _discount);

    public static bool operator ==(ThresholdDiscount left, ThresholdDiscount right) =>
        left.Equals(right);

    public static bool operator !=(ThresholdDiscount left, ThresholdDiscount right) =>
        !left.Equals(right);

    public override string ToString() =>
        $"{_discount} above {_threshold}";
}
EOF

echo "✓ ThresholdDiscount.cs created"

# -------------------------------------------------------------------
# 2. Extend Discount discriminated union
# -------------------------------------------------------------------

# The original Discount.cs uses a private constructor with all fields.
# We need to: add a field, extend the constructor, add a factory method,
# and update ApplyOn/Equals/GetHashCode/ToString.

DISCOUNT_FILE="Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs"

# Rewrite Discount.cs entirely — sed patches are fragile on readonly structs
cat > "$DISCOUNT_FILE" << 'EOF'
using MyCompany.ECommerce.Sales.Commons;
using NoesisVision.Annotations.Domain.DDD;

namespace MyCompany.ECommerce.Sales.Pricing.Discounts;

[DddValueObject]
public readonly struct Discount : PriceModifier, IEquatable<Discount>
{
    private readonly bool _isPercentage;
    private readonly bool _isThreshold;
    private readonly PercentageDiscount _percentageDiscount;
    private readonly ValueDiscount _valueDiscount;
    private readonly ThresholdDiscount _thresholdDiscount;

    public static Discount Percentage(Percentage value) =>
        new(isPercentage: true, isThreshold: false, PercentageDiscount.Of(value), default, default);

    public static Discount Value(Money value) =>
        new(isPercentage: false, isThreshold: false, default, ValueDiscount.Of(value), default);

    public static Discount Threshold(Money threshold, Percentage value) =>
        new(isPercentage: false, isThreshold: true, default, default, ThresholdDiscount.Of(threshold, value));

    private Discount(
        bool isPercentage,
        bool isThreshold,
        PercentageDiscount percentageDiscount,
        ValueDiscount valueDiscount,
        ThresholdDiscount thresholdDiscount)
    {
        _isPercentage = isPercentage;
        _isThreshold = isThreshold;
        _percentageDiscount = percentageDiscount;
        _valueDiscount = valueDiscount;
        _thresholdDiscount = thresholdDiscount;
    }

    public Money ApplyOn(Money price) => _isThreshold
        ? _thresholdDiscount.ApplyOn(price)
        : _isPercentage
            ? _percentageDiscount.ApplyOn(price)
            : _valueDiscount.ApplyOn(price);

    public bool Equals(Discount other) =>
        (_isPercentage, _isThreshold, _percentageDiscount, _valueDiscount, _thresholdDiscount)
            .Equals((other._isPercentage, other._isThreshold, other._percentageDiscount, other._valueDiscount, other._thresholdDiscount));

    public override bool Equals(object? obj) => obj is Discount other && Equals(other);
    public override int GetHashCode() =>
        (_isPercentage, _isThreshold, _percentageDiscount, _valueDiscount, _thresholdDiscount).GetHashCode();

    public override string ToString() => _isThreshold
        ? _thresholdDiscount.ToString()
        : _isPercentage
            ? _percentageDiscount.ToString()
            : _valueDiscount.ToString();
}
EOF

echo "✓ Discount.cs extended with threshold variant"

# -------------------------------------------------------------------
# 3. Create tests for ThresholdDiscount
# -------------------------------------------------------------------

TEST_DIR="Sources/Sales/Sales.DeepModel.Tests/Pricing/Discounts"
mkdir -p "$TEST_DIR"

cat > "$TEST_DIR/ThresholdDiscountTests.cs" << 'EOF'
using FluentAssertions;
using MyCompany.ECommerce.Sales.Commons;
using MyCompany.ECommerce.Sales.Pricing.Discounts;
using Xunit;

namespace MyCompany.ECommerce.Sales.Tests.Pricing.Discounts;

public class ThresholdDiscountTests
{
    [Fact]
    public void AppliesDiscountWhenPriceExceedsThreshold()
    {
        var threshold = ThresholdDiscount.Of(
            Money.Of(500, Currency.PLN),
            Percentage.Of(10));

        var result = threshold.ApplyOn(Money.Of(600, Currency.PLN));

        result.Should().Be(Money.Of(540, Currency.PLN));
    }

    [Fact]
    public void DoesNotApplyDiscountWhenPriceEqualsThreshold()
    {
        var threshold = ThresholdDiscount.Of(
            Money.Of(500, Currency.PLN),
            Percentage.Of(10));

        var result = threshold.ApplyOn(Money.Of(500, Currency.PLN));

        result.Should().Be(Money.Of(500, Currency.PLN));
    }

    [Fact]
    public void DoesNotApplyDiscountWhenPriceBelowThreshold()
    {
        var threshold = ThresholdDiscount.Of(
            Money.Of(500, Currency.PLN),
            Percentage.Of(10));

        var result = threshold.ApplyOn(Money.Of(300, Currency.PLN));

        result.Should().Be(Money.Of(300, Currency.PLN));
    }
}
EOF

echo "✓ ThresholdDiscountTests.cs created"

echo ""
echo "Reference solution applied successfully."
echo "Run 'dotnet build && dotnet test' to verify."
