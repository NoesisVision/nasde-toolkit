#!/bin/bash

echo "=========================================="
echo "Expense Report Extract Hierarchy - Evaluation"
echo "=========================================="
echo ""

cd /app/expensereport-java

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

echo "Step 2: Running tests if present..."
echo "--------------------------------------"
mvn test -q 2>&1 && echo "✓ Tests pass" || echo "⚠ No tests or tests failed (non-blocking for this task)"
echo ""

echo "Step 3: Verifying expense type hierarchy exists..."
echo "--------------------------------------"
JAVA_SRC="src/main/java/com/nelkinda/training"
if find $JAVA_SRC -name "*.java" -exec grep -l "extends.*Expense\|implements.*Expense\|abstract.*class.*Expense\|sealed.*interface.*Expense\|sealed.*class.*Expense" {} + 2>/dev/null | grep -q .; then
    echo "✓ Expense type hierarchy found"
    echo ""
elif find $JAVA_SRC -name "*.java" -exec grep -l "class Dinner\|class Breakfast\|class CarRental\|class Lunch\|class Supper" {} + 2>/dev/null | grep -q .; then
    echo "✓ Expense type classes found"
    echo ""
else
    echo "✗ No expense type hierarchy found"
    echo "Expected classes extending/implementing an Expense base type, or concrete expense type classes"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying switch/case on expense type is eliminated..."
echo "--------------------------------------"
SWITCH_COUNT=$(grep -r "switch.*[Tt]ype\|case DINNER\|case BREAKFAST\|case CAR_RENTAL\|case LUNCH" --include="*.java" $JAVA_SRC 2>/dev/null | wc -l)
if [ "$SWITCH_COUNT" -le 1 ]; then
    echo "✓ Switch statements on expense type eliminated or minimal ($SWITCH_COUNT remaining)"
    echo ""
else
    echo "✗ Still $SWITCH_COUNT switch/case statements on expense type"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 5: Verifying output is configurable (not hardcoded System.out)..."
echo "--------------------------------------"
SYSOUT_IN_REPORT=$(grep -c "System.out" $JAVA_SRC/ExpenseReport.java 2>/dev/null || echo "0")
if [ "$SYSOUT_IN_REPORT" -le 1 ]; then
    echo "✓ System.out usage minimal in ExpenseReport ($SYSOUT_IN_REPORT references)"
    echo ""
else
    echo "✗ ExpenseReport still has $SYSOUT_IN_REPORT System.out references"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
