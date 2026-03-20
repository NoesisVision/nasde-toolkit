#!/bin/bash

# DDD Weather Discount Challenge - Evaluation Script
# This script verifies that the AI agent successfully implemented the weather-based discount feature

echo "=========================================="
echo "DDD Weather Discount - Evaluation"
echo "=========================================="
echo ""

# Navigate to project directory
cd /app

echo "Step 1: Verifying project compiles..."
echo "--------------------------------------"
if dotnet build MyCompany.ECommerce.sln --configuration Debug --no-restore; then
    echo "✓ SUCCESS: Project compiles without errors"
    echo ""
else
    echo "✗ FAILURE: Project does not compile"
    echo "The solution must compile successfully."
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
# Search for the Open-Meteo API URL in the codebase
# This confirms the agent actually integrated with the required external API
if grep -r "api.open-meteo.com" --include="*.cs" Sources/; then
    echo ""
    echo "✓ SUCCESS: Open-Meteo API URL found in codebase"
    echo ""
else
    echo "✗ FAILURE: Open-Meteo API URL not found in codebase"
    echo "Expected to find 'api.open-meteo.com' in the source code."
    echo "The implementation must use the specified weather API."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Checking for weather-related implementation..."
echo "--------------------------------------"
# Check if weather-related code exists (case-insensitive search)
# This is a soft check to see if the agent implemented something weather-related
if grep -ri "weather" --include="*.cs" Sources/Sales/ | grep -v "// " | head -5; then
    echo ""
    echo "✓ SUCCESS: Weather-related implementation found"
    echo ""
else
    echo "⚠ WARNING: No obvious weather-related code found"
    echo "This may indicate the implementation is incomplete, but continuing evaluation..."
    echo ""
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo ""
echo "Summary:"
echo "  • Project compiles successfully"
echo "  • All tests pass"
echo "  • Open-Meteo API integration verified"
echo "  • Weather-based discount feature implemented"
echo ""
echo "The AI agent successfully completed the challenge!"
echo ""

# Write success reward (1 = success in Harbor)
echo 1 > /logs/verifier/reward.txt

exit 0
