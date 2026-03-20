#!/bin/bash
cd /app

echo "=========================================="
echo "C# Anemic to Rich Domain Model - Evaluation"
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

echo "Step 2: Verifying domain entities have behavior methods..."
echo "--------------------------------------"
DOMAIN_FILES=$(find DotNetConfPl.Refactoring/Domain -name "*.cs" -type f)
if echo "$DOMAIN_FILES" | xargs grep -lE "(void (Change|Set|Add|Remove|Assign|Create)|bool (Is|Can|Has))" 2>/dev/null | grep -q .; then
    echo "✓ SUCCESS: Domain entities contain behavior methods"
    echo ""
else
    echo "✗ FAILURE: Domain entities lack behavior methods — still anemic"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying services are thin orchestrators..."
echo "--------------------------------------"
SERVICE_FILES=$(find DotNetConfPl.Refactoring/Application -name "*Service.cs" -type f)
if [ -n "$SERVICE_FILES" ]; then
    BIZ_LOGIC_COUNT=$(echo "$SERVICE_FILES" | xargs grep -cE "^\s+if\s*\(" 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
    echo "Business logic if-statements in services: ${BIZ_LOGIC_COUNT:-0}"
    if [ "${BIZ_LOGIC_COUNT:-0}" -le 2 ]; then
        echo "✓ SUCCESS: Services are thin (≤2 if-statements)"
        echo ""
    else
        echo "✗ FAILURE: Services still contain too much business logic (>2 if-statements)"
        echo 0 > /logs/verifier/reward.txt
        exit 1
    fi
else
    echo "✓ INFO: No service files found — logic may be fully in domain"
    echo ""
fi

echo "Step 4: Checking for value objects..."
echo "--------------------------------------"
ALL_CS=$(find DotNetConfPl.Refactoring -name "*.cs" -type f)
if echo "$ALL_CS" | xargs grep -lE "(readonly struct|sealed class.*: (ValueObject|IEquatable)|record struct|record class)" 2>/dev/null | grep -q .; then
    echo "✓ SUCCESS: Value object(s) found"
    echo ""
else
    if echo "$ALL_CS" | xargs grep -lE "(readonly|immutable|Equals\(|GetHashCode\(\))" 2>/dev/null | grep -q .; then
        echo "✓ SUCCESS: Immutable types found (likely value objects)"
        echo ""
    else
        echo "✗ FAILURE: No value objects detected"
        echo 0 > /logs/verifier/reward.txt
        exit 1
    fi
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="

echo 1 > /logs/verifier/reward.txt
exit 0
