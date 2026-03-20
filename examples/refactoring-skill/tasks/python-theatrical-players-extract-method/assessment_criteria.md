# Assessment Criteria: Theatrical Players — Decompose Statement

Evaluate the agent's solution across the following dimensions.
This task is in Python — apply Pythonic standards and idioms.

## 1. Behavior Preservation (0–30)

| Score | Criteria |
|-------|----------|
| 0     | Existing tests fail, plain-text statement output changed |
| 10    | Tests pass but plain-text output has minor formatting differences (whitespace, number format) |
| 20    | Plain-text output is identical, tests pass, but edge cases in calculation have subtle issues |
| 30    | All tests pass, plain-text output is character-for-character identical, all calculation logic preserved exactly |

**Key checks:**
- Do all existing `test_statement.py` tests pass?
- Is the plain-text output byte-for-byte identical to the original?
- Are amounts calculated correctly for both tragedy and comedy?
- Are volume credits calculated correctly (including comedy bonus)?

## 2. Code Clarity (0–25)

| Score | Criteria |
|-------|----------|
| 0     | Code is equally or more tangled — calculation still mixed with formatting |
| 5     | Some extraction but calculation and formatting still interleaved |
| 10    | Calculation separated but the structure is confusing (too many indirections, unclear data flow) |
| 15    | Clean separation: calculate data → render to text or HTML. Easy to follow |
| 20    | Well-structured with an intermediate data representation between calculation and rendering |
| 25    | Excellent — clear pipeline (calculate → intermediate result → render), each piece has a single responsibility, naming is descriptive |

**Key checks:**
- Is there a clear boundary between "compute billing data" and "format output"?
- Is there an intermediate data structure (dict, dataclass, namedtuple) holding the computed results?
- Can you trace the data flow without jumping back and forth?

## 3. Refactoring Technique (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No meaningful refactoring — just duplicated the function for HTML |
| 5     | Extracted a few helper functions but core structure unchanged |
| 10    | Applied Extract Method — calculation helpers exist but formatting not fully separated |
| 15    | Good decomposition with Extract Method, calculation fully separated, both renderers share calculation code |
| 20    | Clean Split Phase (calculate then render), possibly with Replace Conditional for play type pricing |
| 25    | Textbook Fowler Chapter 1 refactoring — Split Phase with intermediate data, Replace Conditional with Polymorphism for play types, both renderers are thin formatting layers over shared calculation |

**Key checks:**
- Was Extract Method applied to pull out calculation helpers?
- Was Split Phase applied to separate calculation from rendering?
- Do `statement()` and `html_statement()` share calculation logic (not duplicate it)?
- Was Replace Conditional with Polymorphism considered for play type pricing?

## 4. Scope Discipline (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Wholesale changes across many files, test files modified, new dependencies added |
| 5     | Major unnecessary restructuring (new packages, configuration files, etc.) |
| 10    | Changes mostly in `statement.py` but with unnecessary additions (extra files, frameworks) |
| 15    | Focused on `statement.py`, added `html_statement` cleanly, but some unnecessary polish |
| 20    | Surgically precise — `statement.py` refactored, `html_statement` added, no other changes |

**Key checks:**
- Were test files left unchanged?
- Were changes limited to `statement.py` (and optionally a new module)?
- Was there any unnecessary restructuring?
- Did the agent add only what was asked for (refactoring + HTML statement)?
