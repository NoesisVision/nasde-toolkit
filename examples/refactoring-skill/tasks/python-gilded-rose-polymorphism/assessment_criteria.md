# Assessment Criteria: Gilded Rose — Untangle Update Logic

Evaluate the agent's solution across the following dimensions.
This task is in Python — apply Pythonic standards and idioms.

## 1. Behavior Preservation (0–30)

| Score | Criteria |
|-------|----------|
| 0     | Existing tests fail, or observable behavior changed for one or more item categories |
| 10    | Most tests pass but one item category (Aged Brie, Backstage passes, Sulfuras, or normal) has subtle regressions |
| 20    | All existing tests pass, but edge cases (quality bounds, sell_in transitions) have minor issues |
| 30    | All existing tests pass, all edge cases preserved — quality never negative, never above 50 (except Sulfuras at 80), sell_in boundary behavior identical |

**Key checks:**
- Do all existing `test_gilded_rose.py` tests pass?
- Is Sulfuras still immutable (quality=80, sell_in unchanged)?
- Does Aged Brie still increase in quality?
- Do Backstage passes drop to 0 after concert?
- Is quality capped at 50 (except Sulfuras)?
- Is the `Item` class completely unchanged?

## 2. Code Clarity (0–25)

| Score | Criteria |
|-------|----------|
| 0     | Code is equally or more tangled than the original |
| 5     | Some restructuring but still hard to follow, mixed responsibilities |
| 10    | Logic separated but using long if/elif chains with string comparisons |
| 15    | Clear separation of item categories, each category's logic readable in isolation |
| 20    | Well-structured with descriptive names, each update strategy is self-contained and easy to understand |
| 25    | Excellent clarity — each item category's rules are immediately obvious, new developer could understand and modify any category in isolation |

**Key checks:**
- Can you understand each item category's rules without reading other categories?
- Are method/class names descriptive (not generic like `process` or `handle`)?
- Is the dispatch mechanism (how the right strategy is selected) clear?
- Is there appropriate use of Python idioms (not Java-style over-engineering)?

## 3. Refactoring Technique (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No meaningful refactoring — just added Conjured logic to existing conditionals |
| 5     | Extracted some methods but core nested conditional structure remains |
| 10    | Used Extract Method to separate categories, but still string-matching in a big if/elif |
| 15    | Applied Replace Conditional with Polymorphism or Strategy pattern, but implementation has issues (e.g. broken dispatch, unnecessary complexity) |
| 20    | Clean polymorphism or strategy pattern, proper dispatch, Conjured items integrate naturally into the new structure |
| 25    | Textbook refactoring — polymorphism/strategy cleanly replaces conditionals, adding a new item category would require only adding a new class/function with no changes to existing code |

**Key checks:**
- Was Replace Conditional with Polymorphism (or equivalent) applied?
- Does the Conjured item implementation demonstrate the benefit of the refactoring (easy to add)?
- Is the pattern appropriate for Python (not over-engineered Java-style AbstractStrategyFactoryBean)?
- Could a new item category be added without modifying existing update logic?

## 4. Scope Discipline (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Wholesale rewrite of unrelated code, new dependencies added, test files modified |
| 5     | Major changes outside `gilded_rose.py`, or `Item` class modified |
| 10    | Changes mostly in `gilded_rose.py` but with unnecessary additions (new files, extra abstractions, type hints on unrelated code) |
| 15    | Focused on `gilded_rose.py`, minimal new files if any, but some unnecessary polish (docstrings, comments, reformatting unchanged code) |
| 20    | Surgically precise — only `gilded_rose.py` modified (plus any new module for strategies), no unnecessary changes, no feature creep beyond Conjured items |

**Key checks:**
- Was only `gilded_rose.py` modified (and optionally a new module for strategy classes)?
- Were test files left unchanged?
- Was the `Item` class left completely alone?
- Were there any gratuitous changes (reformatting, adding type hints to unrelated code, renaming existing things)?
