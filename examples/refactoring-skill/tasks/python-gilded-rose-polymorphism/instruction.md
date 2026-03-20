# Task: Gilded Rose — Untangle Update Logic

## Context

You are working in `/app`, a Python project containing the classic Gilded Rose inventory management system. The relevant code is in the `python/` directory:

```
python/
  gilded_rose.py        # Core update logic
  test_gilded_rose.py   # Test suite (TextTest-based approval tests)
```

The `GildedRose` class has a single `update_quality()` method that updates the `sell_in` and `quality` properties of every item in inventory. Different item categories have different update rules, but all of this logic lives in one deeply nested conditional block.

## Requirement

The `update_quality()` method in `gilded_rose.py` is a single monolithic function with deeply nested `if/elif/else` branches that determine behavior based on item name strings. Each item category (normal items, Aged Brie, Sulfuras, Backstage passes) has different rules buried inside interleaved conditions that are difficult to follow, extend, or test in isolation.

The shop owner also wants to start selling **"Conjured" items**, which degrade in quality **twice as fast** as normal items. Adding this feature to the current code structure would make the already tangled conditionals even worse.

Your task:
1. Refactor the `update_quality()` method so that each item category's update logic is cleanly separated and easy to understand
2. Add support for "Conjured" items (items whose name starts with "Conjured") that degrade in quality twice as fast as normal items

## Scope

- Focus on: `python/gilded_rose.py`
- Do NOT modify: the `Item` class (the goblin in the corner gets angry)
- Preserve: all existing behavior for Aged Brie, Sulfuras, Backstage passes, and normal items

## Quality Expectations

- Follow Python idioms and the project's existing style
- Ensure all existing tests continue to pass
- Keep the refactoring focused — separate concerns without over-engineering

## Success Criteria

1. All existing tests in `python/test_gilded_rose.py` continue to pass
2. The deeply nested conditional in `update_quality()` has been replaced with a cleaner structure
3. "Conjured" items are supported and degrade in quality twice as fast as normal items
4. The `Item` class is unchanged
