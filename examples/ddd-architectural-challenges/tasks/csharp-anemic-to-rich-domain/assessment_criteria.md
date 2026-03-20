# Assessment Criteria: C# Anemic to Rich Domain Model

Evaluate the agent's solution across five dimensions.

## 1. Domain Modeling (0–25)

| Score | Criteria |
|-------|----------|
| 0     | No changes to domain entities — still pure data bags |
| 5     | Some methods added to entities but logic is superficial |
| 10    | Business rules moved from services to entities, basic invariant enforcement |
| 15    | Rich domain model with proper aggregate boundaries, entity behavior, and factory methods |
| 20    | Strong DDD: aggregates protect invariants, state transitions are explicit, ubiquitous language used |
| 25    | Exemplary DDD: aggregates protect invariants, state transitions are explicit, ubiquitous language used throughout, proper use of value objects and domain events where appropriate |

**Key checks:**
- Does `Person` enforce name validation and `FullName` computation internally?
- Does `Company` protect its invariants (contact employee, source)?
- Is the employee-company relationship modeled with proper invariant enforcement?
- Are constructors/factory methods used instead of public setters?

## 2. Encapsulation (0–20)

| Score | Criteria |
|-------|----------|
| 0     | All properties still have public setters — no encapsulation |
| 5     | Some setters made private but logic still in services |
| 10    | Most business logic in domain objects, services are mostly orchestration |
| 15    | Services are thin orchestrators: load → call domain method → save |
| 20    | Full encapsulation: no way to put domain objects in invalid state from outside |

**Key checks:**
- Are public setters removed or made private?
- Do services still contain if/else business logic?
- Can external code bypass domain invariants?

## 3. Architecture Compliance (0–20)

| Score | Criteria |
|-------|----------|
| 0     | No structural changes |
| 5     | Some refactoring but mixed concerns remain |
| 10    | Clear separation: domain has no infrastructure dependencies |
| 15    | Proper layer separation, domain objects don't reference EF Core or controllers |
| 20    | Clean architecture: domain is isolated, application orchestrates, infrastructure adapts, dependency direction is correct |

**Key checks:**
- Does the domain layer depend on EF Core or ASP.NET?
- Are DTOs and domain objects properly separated?
- Is the dependency direction correct (outer layers depend on inner)?

## 4. Extensibility (0–15)

| Score | Criteria |
|-------|----------|
| 0     | Refactoring makes future changes harder |
| 3     | No improvement to extensibility |
| 6     | Slightly easier to extend but business rules still scattered |
| 9     | Domain objects are cohesive; adding new business rules has a clear home |
| 12    | Good: aggregate boundaries are clear, new domain rules go in the right place naturally |
| 15    | Excellent: domain model is well-factored, new features require adding behavior to existing aggregates or creating new value objects, no shotgun surgery needed |

**Key checks:**
- Are aggregate boundaries clear?
- Would adding a new business rule (e.g., company name validation) be straightforward?
- Are value objects used where appropriate, making them reusable?

## 5. Test Quality (0–20)

| Score | Criteria |
|-------|----------|
| 0     | Tests broken or removed |
| 4     | Existing tests pass but no new tests for domain behavior |
| 8     | Some tests for new domain methods but poor coverage |
| 12    | Good coverage of domain behavior, invariant enforcement tested |
| 16    | Comprehensive: domain invariants, factory methods, state transitions all tested |
| 20    | Excellent: all domain behavior tested, invalid states tested and rejected, test names express domain concepts, follows project test conventions |

**Key checks:**
- Do existing tests still pass?
- Are domain invariants tested (e.g., invalid name, invalid company state)?
- Are factory methods / constructors tested with valid and invalid inputs?
- Do test names express domain concepts?
