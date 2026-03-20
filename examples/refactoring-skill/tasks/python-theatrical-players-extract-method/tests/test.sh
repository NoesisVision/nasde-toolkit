#!/bin/bash

echo "=========================================="
echo "Theatrical Players Extract Method - Evaluation"
echo "=========================================="
echo ""

cd /app/python

echo "Step 1: Running existing tests..."
echo "--------------------------------------"
if python -m pytest test_statement.py -v; then
    echo "✓ Existing tests pass"
    echo ""
else
    echo "✗ Existing tests failed — regression detected"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Verifying html_statement function exists..."
echo "--------------------------------------"
if python -c "from statement import html_statement; print('html_statement found')"; then
    echo "✓ html_statement function exists"
    echo ""
else
    echo "✗ html_statement function not found"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying html_statement produces valid HTML..."
echo "--------------------------------------"
if python -c "
from statement import html_statement

plays = {
    'hamlet': {'name': 'Hamlet', 'type': 'tragedy'},
    'as-like': {'name': 'As You Like It', 'type': 'comedy'},
    'othello': {'name': 'Othello', 'type': 'tragedy'},
}
invoice = {
    'customer': 'BigCo',
    'performances': [
        {'playID': 'hamlet', 'audience': 55},
        {'playID': 'as-like', 'audience': 35},
        {'playID': 'othello', 'audience': 40},
    ],
}

result = html_statement(invoice, plays)
assert '<html>' in result.lower() or '<table>' in result.lower() or '<h1>' in result.lower(), 'Output does not look like HTML'
assert 'Hamlet' in result, 'Missing play name Hamlet'
assert 'As You Like It' in result, 'Missing play name As You Like It'
assert 'BigCo' in result, 'Missing customer name'
print('HTML statement is valid')
"; then
    echo "✓ html_statement produces valid HTML with correct data"
    echo ""
else
    echo "✗ html_statement output is invalid"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying calculation logic is separated from rendering..."
echo "--------------------------------------"
if python -c "
import ast
with open('statement.py') as f:
    tree = ast.parse(f.read())

functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

total_defs = len(functions) + len(classes)
assert total_defs >= 4, f'Expected at least 4 functions/classes (calculation + 2 renderers + helpers), found {total_defs}: {functions + classes}'
print(f'Found {total_defs} definitions: {functions + classes}')
"; then
    echo "✓ Code has been decomposed into multiple functions/classes"
    echo ""
else
    echo "✗ Code not sufficiently decomposed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
