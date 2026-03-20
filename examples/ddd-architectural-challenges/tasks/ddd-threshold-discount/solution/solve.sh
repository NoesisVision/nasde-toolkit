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
using MyCompany.ECommerce.TechnicalStuff.Money;

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

# Patch Discount.cs: add _thresholdDiscount field, factory method, and cases
# Uses Python for safe in-place patching.
python3 - << 'PYEOF'
import re

path = "Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs"
with open(path) as f:
    src = f.read()

# Add field after _valueDiscount field
src = src.replace(
    "    private readonly ValueDiscount _valueDiscount;",
    "    private readonly ValueDiscount _valueDiscount;\n    private readonly ThresholdDiscount _thresholdDiscount;"
)

# Add factory method after Value factory method
src = src.replace(
    "    public static Discount Value(Money value) =>",
    "    public static Discount Threshold(Money threshold, Percentage value) =>\n        new() { _thresholdDiscount = ThresholdDiscount.Of(threshold, value) };\n\n    public static Discount Value(Money value) =>"
)

# Add case in ApplyOn
src = src.replace(
    "        if (_valueDiscount != default) return _valueDiscount.ApplyOn(price);",
    "        if (_valueDiscount != default) return _valueDiscount.ApplyOn(price);\n        if (_thresholdDiscount != default) return _thresholdDiscount.ApplyOn(price);"
)

# Add case in ToString
src = src.replace(
    "        if (_valueDiscount != default) return _valueDiscount.ToString();",
    "        if (_valueDiscount != default) return _valueDiscount.ToString();\n        if (_thresholdDiscount != default) return _thresholdDiscount.ToString();"
)

with open(path, "w") as f:
    f.write(src)

print("✓ Discount.cs extended with threshold variant")
PYEOF

echo ""
echo "Reference solution applied successfully."
echo "Run 'dotnet build && dotnet test' to verify."
