#!/bin/bash

# DDD Threshold Discount Challenge - Test Script
# Verifies that the AI agent correctly extended the Discount discriminated union
# with a new ThresholdDiscount value object.

echo "=========================================="
echo "DDD Threshold Discount - Evaluation"
echo "=========================================="
echo ""

cd /app

echo "Step 1: Verifying project compiles..."
echo "--------------------------------------"
if dotnet build MyCompany.ECommerce.sln --configuration Debug --no-restore; then
    echo "✓ SUCCESS: Project compiles without errors"
    echo ""
else
    echo "✗ FAILURE: Project does not compile"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Running tests..."
echo "--------------------------------------"
if dotnet test MyCompany.ECommerce.sln --configuration Debug --no-build --verbosity normal --filter "FullyQualifiedName!~OrderSqlRepositoryTests"; then
    echo "✓ SUCCESS: All tests pass"
    echo ""
else
    echo "✗ FAILURE: Tests failed"
    echo "All tests must pass. Ensure your implementation includes tests and they all succeed."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying ThresholdDiscount value object exists..."
echo "--------------------------------------"
if find Sources/Sales -name "ThresholdDiscount.cs" | grep -q .; then
    echo "✓ SUCCESS: ThresholdDiscount.cs found"
    find Sources/Sales -name "ThresholdDiscount.cs"
    echo ""
else
    echo "✗ FAILURE: ThresholdDiscount.cs not found under Sources/Sales"
    echo "Expected a new value object file implementing the threshold discount logic."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying ThresholdDiscount implements PriceModifier..."
echo "--------------------------------------"
if grep -r "PriceModifier" --include="ThresholdDiscount.cs" Sources/Sales/ | grep -q .; then
    echo "✓ SUCCESS: ThresholdDiscount implements PriceModifier"
    echo ""
else
    echo "✗ FAILURE: ThresholdDiscount does not implement PriceModifier"
    echo "The value object must implement the PriceModifier interface, as PercentageDiscount and ValueDiscount do."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 5: Verifying Discount union has a threshold variant..."
echo "--------------------------------------"
DISCOUNT_FILE="Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs"
if [ -f "$DISCOUNT_FILE" ] && grep -qi "threshold" "$DISCOUNT_FILE"; then
    echo "✓ SUCCESS: Discount union references threshold variant"
    echo ""
else
    echo "✗ FAILURE: Discount.cs does not contain a threshold variant"
    echo "The Discount discriminated union must be extended with a third variant for ThresholdDiscount."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 6: Verifying tests for ThresholdDiscount exist..."
echo "--------------------------------------"
if find Sources/Sales -type d -name "*Tests*" -exec grep -r -l -i "threshold" --include="*.cs" {} + 2>/dev/null | grep -q .; then
    echo "✓ SUCCESS: Test file(s) for ThresholdDiscount found"
    find Sources/Sales -type d -name "*Tests*" -exec grep -r -l -i "threshold" --include="*.cs" {} + 2>/dev/null
    echo ""
else
    echo "✗ FAILURE: No test file found containing ThresholdDiscount tests"
    echo "Tests for the new discount type are required."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo ""
echo "Summary:"
echo "  • Project compiles successfully"
echo "  • All tests pass"
echo "  • ThresholdDiscount value object implemented"
echo "  • Discount union extended with threshold variant"
echo "  • Tests for ThresholdDiscount present"
echo ""
echo "The AI agent successfully completed the challenge!"
echo ""

echo 1 > /logs/verifier/reward.txt
exit 0
