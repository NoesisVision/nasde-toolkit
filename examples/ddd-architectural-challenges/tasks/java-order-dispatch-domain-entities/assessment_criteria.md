# Assessment Criteria: Java Order Dispatch Domain Entities

Evaluate the agent's solution across five dimensions.
This task is in Java (refactoring kata) — apply Java-specific standards.

## 1. Domain Modeling (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No changes to entities, or changes break tests |
| 5     | Minor method additions but core dispatch logic still external |
| 10    | Some dispatch-related methods on entities but incomplete encapsulation |
| 15    | Entities have meaningful dispatch behavior; most decision logic moved in; but some rules still external |
| 20    | Entities fully own dispatch decisions; service only coordinates; proper method signatures |
| 25    | Exemplary: entities have intention-revealing methods (isDispatchable, canReceive), clean collaboration between entities, no external state interrogation needed |

**Key checks:**
- Do Order/Customer entities have methods that express dispatch-related decisions?
- Is the dispatch decision made by entities rather than by external inspection?
- Are entity methods well-named and express domain concepts?

## 2. Encapsulation (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Entities still fully exposed via getters; no behavior moved |
| 4     | Some logic moved but getters still used externally for decisions |
| 8     | Behavior methods exist but unnecessary getters remain |
| 12    | Most decision logic inside entities; some getters removed; service is thinner |
| 16    | Getters for decision-making eliminated; entities expose behavior, not state |
| 20    | Perfect: Tell, Don't Ask principle applied; entities expose only behavior methods; no feature envy in service |

**Key checks:**
- Have getters used only for external decision-making been removed?
- Does the service call entity methods instead of reading state?
- Is the Tell, Don't Ask principle followed?

## 3. Architecture Compliance (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Project structure broken, files moved incorrectly |
| 4     | Structure preserved but naming inconsistencies introduced |
| 8     | Good structure but some logic placed in wrong layer |
| 12    | Proper placement: behavior in entities, coordination in service; minor style deviations |
| 16    | Follows all existing conventions; entities and service in correct packages |
| 20    | Perfect: respects existing package structure, consistent naming, no unnecessary new classes or packages |

**Key checks:**
- Are entity behavior methods in the entity classes (not in new helper classes)?
- Is the service still in its original location?
- Does the solution avoid introducing unnecessary infrastructure?

## 4. Extensibility (0–15)

| Score | Criteria |
|-------|----------|
| 0     | Refactoring makes future changes harder |
| 3     | No improvement to extensibility |
| 6     | Slightly easier to add new dispatch rules but still requires modifying entities |
| 9     | New dispatch rules can be added with minimal entity changes |
| 12    | Entity methods are composable; new dispatch criteria can be combined with existing ones |
| 15    | Excellent: entity behavior methods follow SRP, new dispatch rules require only adding new methods or combining existing ones, no modification of existing logic needed |

**Key checks:**
- Are entity methods focused (single responsibility)?
- Can new dispatch criteria be added without modifying existing methods?
- Is the service thin enough to easily extend with new workflows?

## 5. Test Quality (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Tests broken or removed |
| 4     | Existing tests still pass but no new tests for entity behavior |
| 8     | Some tests for new entity methods but poor coverage |
| 12    | Good coverage of new entity behavior; existing tests still pass |
| 16    | Comprehensive entity behavior tests; edge cases covered; follows kata test style |
| 20    | Excellent: all new entity methods tested, edge cases covered, test names express domain concepts, existing tests untouched and passing, follows kata test conventions exactly |

**Key checks:**
- Do existing tests still pass?
- Are new entity behavior methods tested?
- Do test names express domain concepts?
- Are edge cases covered?
