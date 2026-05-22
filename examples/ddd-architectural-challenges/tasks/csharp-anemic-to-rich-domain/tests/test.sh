#!/bin/bash

# C# Anemic → Rich Domain Model - Verifier
# Reward semantics: compiles on modern .NET (net8.0) + tests pass (if any).
# Design quality (rich model, modern idioms) is graded by the LLM-as-judge
# against assessment_criteria.md.

cd /app

echo "=========================================="
echo "C# Anemic to Rich Domain Model - Verifier"
echo "=========================================="
echo ""

echo "Step 1: Verifying project compiles..."
echo "--------------------------------------"
if dotnet build DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj --no-restore -c Release -v q 2>&1; then
    echo "✓ SUCCESS: Project compiles"
    echo ""
else
    echo "✗ FAILURE: Project does not compile"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Verifying the project targets modern .NET (net8.0)..."
echo "--------------------------------------"
if grep -qE "<TargetFramework>net8\.0</TargetFramework>" DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj; then
    echo "✓ SUCCESS: Targets net8.0"
    echo ""
else
    echo "✗ FAILURE: Project does not target net8.0 — the solution must run on modern .NET"
    echo "  Found:"
    grep -E "<TargetFramework" DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj || echo "  (no TargetFramework element)"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "VERIFIER PASSED ✓"
echo "=========================================="
echo ""
echo "Note: this verifier only checks that the feature compiles on modern .NET."
echo "DDD design quality and idiom modernity are evaluated by the LLM-as-judge."

echo 1 > /logs/verifier/reward.txt
exit 0
