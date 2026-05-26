# Assessment Criteria: Movie-Rental Anemic to Rich Domain Model

Evaluate the agent's solution across five dimensions. The codebase is an
"Online Theater" movie-rental backend (`Customer`, `Movie`,
`PurchasedMovie`, `CustomerService`, `MovieService`), persisted with
NHibernate / FluentNHibernate.

**Modern .NET expectation (applies throughout):** the project targets .NET 8. A
strong solution reads like a modern .NET 8 codebase, not a port of a legacy
.NET Framework / NHibernate app. Reward idiomatic modern C# where it improves the
domain model — `record` / `readonly record struct` for value objects (free value
equality), `required` / `init`-only properties, file-scoped namespaces, nullable
reference types, pattern matching. Penalize value objects hand-rolled with manual
`Equals`/`GetHashCode` boilerplate and dated style when a `record` would express
the concept more clearly. Note the legitimate persistence constraint: NHibernate
needs mapped members `virtual` and a parameterless (possibly `protected`)
constructor — keeping `virtual` members and a parameterless ctor on **entities**
(`Customer`, `Movie`, `PurchasedMovie`) is required for mapping and is correct, not
a defect. That constraint does **not** apply to value objects: `Email`,
`Dollars`/money, expiration date, and `CustomerName` should still be immutable
`record` / `readonly record struct` types.

**No functional-extensions / `Result<T>` library:** this task forbids introducing a
functional-extensions library (e.g. CSharpFunctionalExtensions) or any `Result<T>` /
`Maybe<T>` monad abstraction. Invariants must be enforced with validating factory
methods that throw a domain-specific exception in plain modern C#. Do **not** award
extra credit for pulling in such a library, and treat adding one as a regression
against the task constraints — it is not a substitute for, nor an improvement over,
factory validation plus a domain exception.

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
- Does `Customer` own `PurchaseMovie` (rejecting a duplicate active purchase and
  keeping `MoneySpent` consistent) and the promotion rules (≥2 active movies in
  30 days **and** ≥$100 in the last year), rather than the service/controller?
- Does `Movie` own its expiration-date and price-by-licensing-model logic
  (previously `MovieService.GetExpirationDate` + `CustomerService.CalculatePrice`)?
- Is `PurchasedMovie` created through the domain (e.g. `Customer.PurchaseMovie`)
  instead of being assembled field-by-field by a service? Are its
  active-vs-expired semantics modeled explicitly on the entity (e.g. an
  `ExpirationDate` value object plus an `IsExpired`/`IsActive` query, or an
  `Expire()` transition) rather than re-derived ad hoc in a service?
- Are invariants enforced by validating factory methods / constructors that throw a
  **domain-specific exception** in plain modern C#? (See the global note: introducing
  a functional-extensions / `Result<T>` library is forbidden and must not raise the
  score — it is neither required nor a better answer than a validating factory plus a
  domain exception.)
- Are constructors / factory methods used instead of public setters? Is the
  `Customer` ↔ `PurchasedMovie` collection encapsulated (no public `IList` to
  mutate from outside)?
- **Modern idioms**: are the value-object candidates (`Email`, money/`Dollars`,
  `ExpirationDate`, `CustomerName`) expressed as `record` / `readonly record struct`
  (value equality for free) rather than classes with hand-written
  `Equals`/`GetHashCode`? Are file-scoped namespaces, `init`/`required`, and nullable
  reference types used? Code that achieves rich DDD but in dated NHibernate-era style
  (hand-rolled value-object equality, `netcoreapp`-era boilerplate) caps this
  dimension at 20 (not exemplary). Note that pulling in a `Result<T>` /
  functional-extensions library does **not** count as a "modern idiom" here and must
  not lift the score — see the global note above.

## 2. Encapsulation (0–20)

| Score | Criteria |
|-------|----------|
| 0     | All properties still have public setters — no encapsulation |
| 5     | Some setters made private but logic still in services |
| 10    | Most business logic in domain objects, services are mostly orchestration |
| 15    | Services are thin orchestrators: load → call domain method → save |
| 20    | Full encapsulation: no way to put domain objects in invalid state from outside |

**Key checks:**
- Are public setters removed or made private/protected on the **entities**
  (`Customer`, `Movie`, `PurchasedMovie`) — within NHibernate's `virtual` +
  parameterless-ctor constraint, which is acceptable and should not be penalized?
- Are the **value objects** (`Email`, `Dollars`/money, `ExpirationDate`,
  `CustomerName`) genuinely immutable (`record` with `init`-only members, no public
  setters) so they cannot be mutated after construction?
- Is the `PurchasedMovies` collection exposed read-only, with mutation only via a
  domain method (e.g. `Customer.PurchaseMovie`)?
- Is `Customer.MoneySpent` kept consistent internally (recomputed/incremented by the
  domain on purchase) rather than settable from outside?
- Do `CustomerService` / `MovieService` still contain `if`/`switch` business
  logic, or has it moved into the domain (services possibly removed)?
- Can external code (the controller) bypass domain invariants — e.g. set
  `Status`, `MoneySpent`, or add a `PurchasedMovie` directly?
- Are invariants guarded inside the domain via factory validation throwing a
  domain-specific exception — **not** by threading a `Result<T>` /
  functional-extensions type through the model (which is forbidden and earns no
  credit)?

## 3. Architecture Compliance (0–20)

| Score | Criteria |
|-------|----------|
| 0     | No structural changes |
| 5     | Some refactoring but mixed concerns remain |
| 10    | Clear separation: domain has no infrastructure dependencies |
| 15    | Proper layer separation, domain objects don't reference NHibernate or controllers |
| 20    | Clean architecture: domain is isolated, application orchestrates, infrastructure adapts, dependency direction is correct |

**Key checks:**
- Does the domain layer leak persistence concerns (NHibernate attributes/usings)
  or web concerns into the entities?
- Are the FluentNHibernate mappings kept in the mapping layer (not pushed into the
  entities) and updated correctly for new value objects / private setters?
- Is the HTTP contract of `CustomersController` preserved while the controller
  becomes a thin delegate to domain methods?
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
- Are aggregate boundaries clear (Customer as the aggregate root over its
  PurchasedMovies)?
- Would adding a new licensing model or a new pricing/promotion rule be a localized
  change rather than edits across services, controllers, and entities?
- Are value objects (email, money, expiration date) reusable and the obvious home
  for related validation?

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
- Note: the repository ships with no test project. Reward the agent for adding one
  (e.g. an xUnit/NUnit project referencing `Logic`) and not breaking the build.
- Are domain invariants tested (duplicate active purchase rejected, invalid `Email`
  rejected, negative `Dollars`/money rejected, the promotion rule of ≥2 active
  movies in 30 days **and** ≥$100 in the last year, price-by-licensing-model,
  expired-vs-active `PurchasedMovie`)?
- Are value-object factory methods (`Email`, `Dollars`, `ExpirationDate`,
  `CustomerName`) tested with valid and invalid inputs, asserting that invalid input
  throws the domain-specific exception (not a `Result`-style failure object)?
- Do test names express domain concepts (e.g.
  `Cannot_purchase_the_same_active_movie_twice`)?
