# Assessment Criteria: Trip Service — Break Static Dependencies

Evaluate the agent's solution across the following dimensions.
This task is in Java — apply Java idioms and conventions.

## 1. Behavior Preservation (0–30)

| Score | Criteria |
|-------|----------|
| 0     | Code doesn't compile, or business logic changed (friends/non-friends behavior different) |
| 10    | Compiles but some scenarios broken (e.g., no-session exception missing, or non-friend case wrong) |
| 20    | All three scenarios work correctly, but edge cases have issues (null user, empty friend list) |
| 30    | All business logic preserved exactly — friend sees trips, non-friend gets empty list, no session throws UserNotLoggedInException |

**Key checks:**
- Does it compile?
- When logged-in user is a friend: returns that user's trips?
- When logged-in user is not a friend: returns empty list?
- When no user logged in: throws `UserNotLoggedInException`?
- Is `User.java` mostly unchanged?

## 2. Code Clarity (0–25)

| Score | Criteria |
|-------|----------|
| 0     | Code is harder to understand than the original |
| 5     | Dependencies injected but method structure still confusing |
| 10    | Dependencies injected, method somewhat cleaner, but authorization and retrieval still interleaved |
| 15    | Clean separation — authorization check, then trip retrieval, clear dependency interfaces |
| 20    | Well-structured: named interfaces, clear method flow, self-documenting code |
| 25    | Excellent — dependencies are clearly named interfaces, method reads like prose, each piece obvious |

**Key checks:**
- Are injected dependencies behind clear interfaces?
- Is the authorization check clearly separated from trip retrieval?
- Are interface/class names descriptive (not `IService`, `Helper`, etc.)?

## 3. Refactoring Technique (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No meaningful refactoring — just mocked the statics with PowerMock |
| 5     | Used Extract and Override (subclass for testing) — works but fragile |
| 10    | Introduced interfaces but injected them via setter or method parameter (not constructor) |
| 15    | Proper constructor injection with interfaces, tests use stubs or mocks |
| 20    | Clean DI: interfaces for both session and DAO, constructor injection, tests with proper test doubles |
| 25    | Textbook legacy code refactoring: Extract Interface, Inject Dependency, comprehensive tests with clear arrange-act-assert, possibly extracted authorization as a separate concern |

**Key checks:**
- Were interfaces extracted for `UserSession` and `TripDAO`?
- Is constructor injection used (not setter injection or service locator)?
- Do tests use test doubles (stubs/mocks) rather than real implementations?
- Is the authorization check a clear, named step?

## 4. Scope Discipline (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Rewrote the entire project, changed build system, added frameworks |
| 5     | Added heavy dependencies (Spring, Guice) for a simple DI task |
| 10    | Changes mostly scoped to trip service, but added unnecessary abstractions or utilities |
| 15    | Focused on TripService + new interfaces + tests, but some extra polish |
| 20    | Minimal changes: TripService refactored, interfaces created, tests written, nothing else touched |

**Key checks:**
- Were changes limited to the trip service area?
- Were new dependencies avoided (no Spring/Guice for this)?
- Were new files only created for extracted interfaces?
- Was `User.java` left mostly unchanged?
