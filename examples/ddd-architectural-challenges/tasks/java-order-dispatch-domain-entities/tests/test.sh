#!/bin/bash

echo "=========================================="
echo "Java Order Dispatch Domain Entities - Evaluation"
echo "=========================================="
echo ""

cd /app/java

echo "Step 1: Verifying project compiles..."
echo "--------------------------------------"
if mvn compile -q -B 2>/dev/null || gradle build --no-daemon -q 2>/dev/null; then
    echo "✓ SUCCESS: Project compiles"
    echo ""
else
    echo "✗ FAILURE: Project does not compile"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Running tests..."
echo "--------------------------------------"
if mvn test -q -B 2>/dev/null || gradle test --no-daemon -q 2>/dev/null; then
    echo "✓ SUCCESS: All tests pass"
    echo ""
else
    echo "✗ FAILURE: Tests failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying domain entities have behavior methods..."
echo "--------------------------------------"
ENTITY_FILES=$(find src/main -name "*.java" -type f)
if echo "$ENTITY_FILES" | xargs grep -lE "(boolean (is|can|should)|void (dispatch|accept|validate|process))" 2>/dev/null | grep -q .; then
    echo "✓ SUCCESS: Domain entities contain behavior methods"
    echo ""
else
    echo "✗ FAILURE: Domain entities lack behavior methods"
    echo "Expected behavior methods like isDispatchable(), canReceive(), etc. on domain entities"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying dispatch service delegates to entities..."
echo "--------------------------------------"
SERVICE_FILES=$(find src/main -name "*.java" -type f | xargs grep -l -i "dispatch\|service" 2>/dev/null)
if [ -n "$SERVICE_FILES" ]; then
    GETTER_COUNT=$(echo "$SERVICE_FILES" | xargs grep -c "\.get[A-Z]" 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
    BEHAVIOR_COUNT=$(echo "$SERVICE_FILES" | xargs grep -cE "\.(is|can|should|dispatch|accept|validate)" 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
    echo "Getter calls in service: $GETTER_COUNT"
    echo "Behavior method calls in service: $BEHAVIOR_COUNT"
    if [ "${BEHAVIOR_COUNT:-0}" -gt 0 ]; then
        echo "✓ SUCCESS: Service calls behavior methods on entities"
        echo ""
    else
        echo "✗ FAILURE: Service does not delegate to entity behavior methods"
        echo 0 > /logs/verifier/reward.txt
        exit 1
    fi
else
    echo "✓ INFO: No separate service file found — logic may be fully in entities"
    echo ""
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="

echo 1 > /logs/verifier/reward.txt
exit 0
