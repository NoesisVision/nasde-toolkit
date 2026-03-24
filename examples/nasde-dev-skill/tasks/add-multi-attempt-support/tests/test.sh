#!/bin/bash

echo "=========================================="
echo "Multi-Attempt Support - Evaluation"
echo "=========================================="
echo ""

cd /app

# Reinstall from source so agent edits are picked up
# TEMPORARY WORKAROUND: litellm quarantined on PyPI (March 2026 supply chain attack).
# Safe version installed from GitHub via uv override. Remove once PyPI restores litellm.
echo 'litellm @ https://github.com/BerriAI/litellm/archive/refs/tags/v1.82.3.tar.gz' > /tmp/litellm-override.txt
uv tool install . --force --override /tmp/litellm-override.txt 2>/dev/null

echo "Step 1: CLI flag exists with correct help text..."
echo "--------------------------------------"
HELP_OUTPUT=$(nasde run --help 2>&1)
if echo "$HELP_OUTPUT" | grep -q "\-\-attempts" && echo "$HELP_OUTPUT" | grep -q "\-n"; then
    echo "OK: --attempts and -n flags found in CLI help"
else
    echo "FAIL: --attempts/-n flag not found in nasde run --help"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if echo "$HELP_OUTPUT" | grep -qi "attempt\|independent.*per task\|number.*attempt"; then
    echo "OK: Help text is descriptive"
else
    echo "FAIL: Help text missing or not descriptive for --attempts"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 2: CLI flag actually parses..."
echo "--------------------------------------"
if nasde run --attempts 3 --help >/dev/null 2>&1; then
    echo "OK: --attempts 3 parses without error"
else
    echo "FAIL: --attempts flag does not parse correctly"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if nasde run -n 2 --help >/dev/null 2>&1; then
    echo "OK: -n 2 short alias parses without error"
else
    echo "FAIL: -n short alias does not parse correctly"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 3: Running Python tests..."
echo "--------------------------------------"
TEST_OUTPUT=$(uv run pytest -x -q 2>&1)
TEST_EXIT=$?
echo "$TEST_OUTPUT"
echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "OK: All tests pass"
else
    echo "FAIL: Unit tests failed (exit code $TEST_EXIT)"
    echo "Review test output above for details"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 4: run_benchmark accepts n_attempts parameter..."
echo "--------------------------------------"
if uv run python -c "
import inspect
from nasde_toolkit.runner import run_benchmark
sig = inspect.signature(run_benchmark)
assert 'n_attempts' in sig.parameters, f'n_attempts not in signature: {list(sig.parameters.keys())}'
param = sig.parameters['n_attempts']
assert param.default == 1, f'Default should be 1, got {param.default}'
print('run_benchmark(n_attempts=1) signature OK')
"; then
    echo "OK: run_benchmark accepts n_attempts with default=1"
else
    echo "FAIL: run_benchmark does not accept n_attempts parameter"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 5: ConfigurableClaude imports correctly..."
echo "--------------------------------------"
if uv run python -c "
from nasde_toolkit.agents.configurable_claude import ConfigurableClaude
print(f'ConfigurableClaude loaded: {ConfigurableClaude.name()}')
"; then
    echo "OK: ConfigurableClaude imports successfully"
else
    echo "FAIL: ConfigurableClaude import failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 6: README.md CLI options table updated..."
echo "--------------------------------------"
if grep -q "\-\-attempts" README.md 2>/dev/null; then
    echo "OK: README.md mentions --attempts flag"
else
    echo "FAIL: README.md CLI options table not updated with --attempts flag"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "=========================================="
echo "EVALUATION PASSED"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
