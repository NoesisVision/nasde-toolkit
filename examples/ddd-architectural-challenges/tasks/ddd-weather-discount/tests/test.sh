#!/bin/bash

# DDD Weather Discount Challenge - Verifier
# Reward semantics: compile + functional tests pass + required API used.
# Design quality is graded separately by the LLM-as-judge against
# assessment_criteria.md.

echo "=========================================="
echo "DDD Weather Discount - Verifier"
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
    echo "All tests must pass. Please ensure your implementation includes tests and they all succeed."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying Open-Meteo API integration..."
echo "--------------------------------------"
if grep -r "api.open-meteo.com" --include="*.cs" Sources/; then
    echo ""
    echo "✓ SUCCESS: Open-Meteo API URL found in codebase"
    echo ""
else
    echo "✗ FAILURE: Open-Meteo API URL not found in codebase"
    echo "Task constraint: implementation must use api.open-meteo.com (Do NOT change the API URL or service)."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "VERIFIER PASSED ✓"
echo "=========================================="
echo ""
echo "Note: this verifier only checks that the feature works and uses the required API."
echo "DDD design quality is evaluated separately by the LLM-as-judge."

echo 1 > /logs/verifier/reward.txt
exit 0
