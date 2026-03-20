# Assessment Criteria: Expense Report — Separate Concerns

Evaluate the agent's solution across the following dimensions.
This task is in Java — apply Java idioms and conventions.

## 1. Behavior Preservation (0–30)

| Score | Criteria |
|-------|----------|
| 0     | Code doesn't compile, or report output is completely different |
| 10    | Compiles but report format has noticeable differences (missing markers, wrong totals) |
| 20    | Report output is mostly correct but minor formatting differences (spacing, labels) |
| 30    | Report output is identical to the original for the same input data — same format, amounts, over-limit markers, totals |

**Key checks:**
- Does the project compile?
- Does the report show expense names, amounts, over-limit markers?
- Are meal expense totals calculated correctly?
- Are over-limit checks correct (Dinner > 5000, Breakfast > 1000)?
- Is the total calculated correctly?

## 2. Code Clarity (0–25)

| Score | Criteria |
|-------|----------|
| 0     | Code is equally or more confusing than the original |
| 5     | Some separation but responsibilities still mixed |
| 10    | Responsibilities separated but the class hierarchy is confusing or overly complex |
| 15    | Clean hierarchy, each expense type is self-documenting, report logic is readable |
| 20    | Well-structured — expense types encapsulate their own rules, report formatting is separate and clear |
| 25    | Excellent — each class has obvious purpose, naming is precise, data flow is clear, no god classes |

**Key checks:**
- Does each expense type know its own name, limit, and meal status?
- Is the report printing logic in its own class/method?
- Can you understand the report generation flow without jumping between files?

## 3. Refactoring Technique (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No meaningful refactoring — just moved code around |
| 5     | Extracted some methods but enum + switch structure remains |
| 10    | Partial hierarchy — some expense types are classes but switch statements remain |
| 15    | Full Replace Conditional with Polymorphism for expense types, but formatting still tangled with calculation |
| 20    | Good separation: expense type hierarchy + Extract Method for formatting, output is configurable |
| 25    | Complete refactoring: polymorphic expense types, separated calculation from formatting, configurable output, testable design |

**Key checks:**
- Was Replace Conditional with Polymorphism applied to expense types?
- Was Extract Method/Class applied to separate formatting from calculation?
- Is the output destination configurable (dependency injection of PrintStream)?
- Is the design testable (can inject a mock output stream)?

## 4. Scope Discipline (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Changes across many directories, new frameworks added, build system modified |
| 5     | Major unnecessary changes (new build plugins, configuration, unrelated files) |
| 10    | Changes in the right package but with unnecessary additions (logging, metrics, etc.) |
| 15    | Focused on the expense report code, new files only for extracted classes, but some over-polish |
| 20    | Minimal changes — only the expense report code refactored, new classes only as needed |

**Key checks:**
- Were changes limited to the `com.nelkinda.training` package?
- Were new files created only for extracted classes (not unnecessary utilities)?
- Was the build configuration left unchanged?
- Were there any gratuitous additions (logging, javadoc on unchanged code, etc.)?
