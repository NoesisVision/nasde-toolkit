#!/bin/bash

# DDD Threshold Discount Challenge - Verifier
# Reward semantics: compile + functional tests pass. Design quality is graded
# separately by the LLM-as-judge against assessment_criteria.md.

echo "=========================================="
echo "DDD Threshold Discount - Verifier"
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

echo "=========================================="
echo "VERIFIER PASSED ✓"
echo "=========================================="
echo ""
echo "Note: this verifier only checks that the feature works."
echo "DDD design quality is evaluated separately by the LLM-as-judge."

echo 1 > /logs/verifier/reward.txt
exit 0
