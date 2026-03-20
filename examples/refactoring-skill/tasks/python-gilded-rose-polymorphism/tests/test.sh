#!/bin/bash

echo "=========================================="
echo "Gilded Rose Polymorphism - Evaluation"
echo "=========================================="
echo ""

cd /app/python

echo "Step 1: Running existing tests..."
echo "--------------------------------------"
if python -m pytest tests/test_gilded_rose.py -v; then
    echo "✓ Existing tests pass"
    echo ""
else
    echo "✗ Existing tests failed — regression detected"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Verifying Item class is unchanged..."
echo "--------------------------------------"
if python -c "
from gilded_rose import Item
i = Item('foo', 10, 20)
assert hasattr(i, 'name') and hasattr(i, 'sell_in') and hasattr(i, 'quality')
assert i.name == 'foo' and i.sell_in == 10 and i.quality == 20
print('Item class unchanged')
"; then
    echo "✓ Item class preserved"
    echo ""
else
    echo "✗ Item class was modified"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Verifying Conjured items degrade twice as fast..."
echo "--------------------------------------"
if python -c "
from gilded_rose import Item, GildedRose
# Normal item: quality decreases by 1 per day
normal = Item('Normal Item', 10, 20)
GildedRose([normal]).update_quality()
assert normal.quality == 19, f'Normal item expected quality 19, got {normal.quality}'

# Conjured item: quality decreases by 2 per day
conjured = Item('Conjured Mana Cake', 10, 20)
GildedRose([conjured]).update_quality()
assert conjured.quality == 18, f'Conjured item expected quality 18, got {conjured.quality}'

# Conjured item past sell date: quality decreases by 4 per day
conjured2 = Item('Conjured Mana Cake', 0, 20)
GildedRose([conjured2]).update_quality()
assert conjured2.quality == 16, f'Conjured item past sell date expected quality 16, got {conjured2.quality}'

# Quality never goes below 0
conjured3 = Item('Conjured Mana Cake', 10, 1)
GildedRose([conjured3]).update_quality()
assert conjured3.quality == 0, f'Conjured item expected quality 0, got {conjured3.quality}'

print('Conjured items work correctly')
"; then
    echo "✓ Conjured items degrade twice as fast"
    echo ""
else
    echo "✗ Conjured items not working correctly"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 4: Verifying nested conditionals were refactored..."
echo "--------------------------------------"
NESTING_DEPTH=$(python -c "
import ast, sys
with open('gilded_rose.py') as f:
    tree = ast.parse(f.read())
max_depth = 0
def walk(node, depth=0):
    global max_depth
    if isinstance(node, ast.If):
        depth += 1
        max_depth = max(max_depth, depth)
    for child in ast.iter_child_nodes(node):
        walk(child, depth)
walk(tree)
print(max_depth)
")
if [ "$NESTING_DEPTH" -le 3 ]; then
    echo "✓ Nesting depth reduced to $NESTING_DEPTH (max 3 allowed)"
    echo ""
else
    echo "✗ Nesting depth is $NESTING_DEPTH — conditionals not sufficiently refactored"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "=========================================="
echo "EVALUATION PASSED ✓"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
