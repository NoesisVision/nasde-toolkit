# Task: Theatrical Players — Decompose Statement

## Context

You are working in `/app`, a Python project that generates billing statements for a theatrical company. The relevant code is in the `python/` directory:

```
python/
  statement.py          # Statement rendering logic
  test_statement.py     # Approval tests for statement output
```

The `statement()` function takes an invoice (list of performances) and a dictionary of plays, and produces a plain-text billing statement showing the charge per performance, total amount, and volume credits earned.

## Requirement

The `statement()` function in `statement.py` is a single long function that calculates charges, formats output, and accumulates credits all in one place. The calculation logic is tangled with string formatting, and different play types (tragedy, comedy) have their pricing rules embedded in a `switch`-style conditional block.

The company wants to also generate an **HTML version** of the statement. Adding HTML output to the current code would require duplicating all the calculation logic.

Your task:
1. Refactor `statement()` so that calculation logic is separated from formatting/rendering
2. After refactoring, add a `html_statement()` function that produces an HTML version of the same billing data
3. The plain-text `statement()` function must produce exactly the same output as before

## Scope

- Focus on: `python/statement.py`
- Do NOT modify: test files (they verify the plain-text output hasn't changed)
- Preserve: exact plain-text statement output (character-for-character)

## Quality Expectations

- Follow Python idioms
- Ensure existing tests pass unchanged
- The HTML statement should contain the same data (play names, amounts, credits, totals) in a reasonable HTML table structure

## Success Criteria

1. All existing tests in `python/test_statement.py` continue to pass
2. Calculation logic is separated from rendering logic
3. `html_statement()` function exists and produces valid HTML with the correct billing data
4. Plain-text `statement()` output is character-for-character identical to the original
