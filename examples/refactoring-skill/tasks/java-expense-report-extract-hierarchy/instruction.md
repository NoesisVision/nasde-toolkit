# Task: Expense Report — Separate Concerns

## Context

You are working in `/app`, a multi-language repository containing expense report implementations. The Java version is in `expensereport-java/`:

```
expensereport-java/
  src/main/java/com/nelkinda/training/ExpenseReport.java
```

The `ExpenseReport` class contains all the logic: an `Expense` inner type with a type enum, and a `printReport()` method that iterates over expenses, calculates totals, determines if expenses are over limit, and prints everything to `System.out`.

## Requirement

The `ExpenseReport.java` file has several code smells:

1. **Primitive Obsession**: Expense types are an enum, and all type-specific behavior (name, limit, whether it's a meal) is determined by switch statements scattered through the code
2. **Mixed Responsibilities**: `printReport()` handles calculation (totals, meal expenses, over-limit checks) and output formatting in a single method
3. **Hardcoded output**: Printing goes directly to `System.out`, making the code untestable

Your task:
1. Replace the expense type enum with a class hierarchy where each expense type knows its own name, limit, and whether it counts as a meal
2. Separate the calculation of report data from the formatting/printing of the report
3. Make the output destination configurable (accept a `PrintStream` or similar) so the report can be tested without capturing `System.out`

## Scope

- Focus on: `expensereport-java/src/main/java/com/nelkinda/training/ExpenseReport.java`
- You may create new files in the same package for extracted classes
- Preserve: the overall report output format (expense names, amounts, markers, totals)

## Quality Expectations

- Follow Java idioms and conventions
- The refactored code should be testable
- Each class should have a single responsibility

## Success Criteria

1. The project compiles with `mvn compile` or `gradle build`
2. Expense types are represented as a class hierarchy (not an enum with switch statements)
3. Report calculation is separated from report formatting
4. The output destination is configurable (not hardcoded to `System.out`)
