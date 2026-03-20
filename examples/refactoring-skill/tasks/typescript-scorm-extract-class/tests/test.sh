#!/bin/bash

echo "=========================================="
echo "SCORM Extract Class - Evaluation"
echo "=========================================="
echo ""

cd /app

echo "Step 1: Verifying build succeeds..."
echo "--------------------------------------"
if npm run build 2>&1; then
    echo "✓ Build succeeded"
    echo ""
else
    echo "✗ Build failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Running existing tests..."
echo "--------------------------------------"
if npm test 2>&1; then
    echo "✓ All tests pass"
    echo ""
else
    echo "✗ Tests failed — regression detected"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying Scorm2004API.ts is smaller..."
echo "--------------------------------------"
ORIGINAL_APPROX_LINES=1000
CURRENT_LINES=$(wc -l < src/Scorm2004API.ts 2>/dev/null || echo "0")
THRESHOLD=$((ORIGINAL_APPROX_LINES * 80 / 100))

if [ "$CURRENT_LINES" -lt "$THRESHOLD" ]; then
    echo "✓ Scorm2004API.ts reduced to $CURRENT_LINES lines (threshold: $THRESHOLD)"
    echo ""
else
    echo "✗ Scorm2004API.ts is $CURRENT_LINES lines (expected less than $THRESHOLD)"
    echo "The God Class has not been sufficiently decomposed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying sequencing logic was extracted..."
echo "--------------------------------------"
if find src -name "*.ts" -newer src/Scorm2004API.ts 2>/dev/null | grep -qi "sequenc\|navig" || \
   find src -name "*[Ss]equenc*" -o -name "*[Nn]avig*" 2>/dev/null | grep -v node_modules | grep -v "\.d\.ts" | grep -q ".ts"; then
    echo "✓ Sequencing/navigation module found"
    echo ""
else
    EXTRACTED=$(find src -name "*.ts" -not -name "*.d.ts" -not -path "*/node_modules/*" | xargs grep -l "sequenc\|navig\|adl\.nav" 2>/dev/null | grep -v "Scorm2004API.ts" | grep -v "__tests__" | head -5)
    if [ -n "$EXTRACTED" ]; then
        echo "✓ Sequencing logic found in extracted files:"
        echo "$EXTRACTED"
        echo ""
    else
        echo "✗ No extracted sequencing/navigation module found"
        echo 0 > /logs/verifier/reward.txt
        exit 1
    fi
fi

echo "Step 5: Verifying public API exports unchanged..."
echo "--------------------------------------"
if grep -q "class Scorm2004API" src/Scorm2004API.ts 2>/dev/null; then
    echo "✓ Scorm2004API class still exists in its original file"
    echo ""
else
    echo "✗ Scorm2004API class not found in expected location"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
