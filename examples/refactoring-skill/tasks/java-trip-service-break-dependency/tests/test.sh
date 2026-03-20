#!/bin/bash

echo "=========================================="
echo "Trip Service Break Dependency - Evaluation"
echo "=========================================="
echo ""

cd /app/java

echo "Step 1: Verifying project compiles..."
echo "--------------------------------------"
if mvn compile -q; then
    echo "✓ Project compiles"
    echo ""
else
    echo "✗ Project does not compile"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Running tests..."
echo "--------------------------------------"
if mvn test -q; then
    echo "✓ All tests pass"
    echo ""
else
    echo "✗ Tests failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying static dependencies are broken..."
echo "--------------------------------------"
TRIP_SERVICE="src/main/java/org/craftedsw/tripservicekata/trip/TripService.java"
STATIC_CALLS=$(grep -c "UserSession.getInstance\|TripDAO.findTripsByUser" "$TRIP_SERVICE" 2>/dev/null || echo "0")
if [ "$STATIC_CALLS" -eq 0 ]; then
    echo "✓ No direct static calls to UserSession or TripDAO in TripService"
    echo ""
else
    echo "✗ TripService still has $STATIC_CALLS direct static dependency calls"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying test coverage exists for key scenarios..."
echo "--------------------------------------"
TEST_FILE=$(find src/test -name "TripServiceTest.java" 2>/dev/null | head -1)
if [ -z "$TEST_FILE" ]; then
    echo "✗ TripServiceTest.java not found"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

TEST_COUNT=$(grep -c "@Test" "$TEST_FILE" 2>/dev/null || echo "0")
if [ "$TEST_COUNT" -ge 3 ]; then
    echo "✓ Found $TEST_COUNT test methods in TripServiceTest"
    echo ""
else
    echo "✗ Only $TEST_COUNT test methods found (expected at least 3)"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 5: Verifying dependency injection is used..."
echo "--------------------------------------"
if grep -q "interface\|@Inject\|constructor\|Constructor" "$TRIP_SERVICE" 2>/dev/null || find src/main -name "*.java" -exec grep -l "interface.*Session\|interface.*TripRepository\|interface.*TripProvider" {} + 2>/dev/null | grep -q .; then
    echo "✓ Dependency injection pattern detected"
    echo ""
else
    echo "✗ No dependency injection pattern found"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
