# Task: Refactor Anemic Domain Model to Rich Domain Model

## Context
You are working in `/app/Before`, an "Online Theater" C# movie-rental backend
(targeting **.NET 8**). It is a *Refactoring from Anemic Domain Model Towards a
Rich One* sample: customers purchase movies, accumulate spend, and can be promoted
to an Advanced status. The domain classes (`Customer`, `Movie`, `PurchasedMovie`)
are plain data containers — public getters and setters with no behavior — while
all business logic lives in application service classes (`CustomerService`,
`MovieService`). This is the classic anemic domain model anti-pattern. The codebase
originated on an older .NET version; bring the domain model up to modern standards
as you enrich it.

Persistence is handled by NHibernate / FluentNHibernate against SQL Server; you do
**not** need a running database to complete or build the task.

The project structure:
```
Before/src/
  Logic/
    Entities/      # Anemic entities — just properties, no behavior
    Services/      # Services containing ALL business logic
    Repositories/  # NHibernate-backed repositories
    Mappings/      # FluentNHibernate ClassMaps
  Api/
    Controllers/   # HTTP controllers
```

## Requirement
Refactor the domain model from anemic to rich. Business rules currently in the
service classes (`CustomerService`, `MovieService`) must move into the domain
objects where they belong, and each entity must protect its own invariants.

## Scope
- Modify files under `Before/src/Logic/Entities/` to add behavior and invariants
  (and add new value-object types under `Logic/` where appropriate).
- Modify files under `Before/src/Logic/Services/` to remove business logic
  (services become thin orchestrators, or disappear if all their logic moves into
  the domain).
- Update the FluentNHibernate mappings under `Before/src/Logic/Mappings/` only as
  needed to keep the model persistable.
- Do NOT change the public HTTP API (route shape, request/response JSON contract).
- Do NOT add a functional-extensions / `Result<T>` library (e.g.
  CSharpFunctionalExtensions); the starting code does not reference one. Enforce
  invariants with validating factories that throw a domain-specific exception, in
  plain modern C#.

## Quality Expectations
- Domain objects enforce their own invariants — constructors and methods reject
  invalid state; an entity cannot be left inconsistent from outside.
- Services contain only orchestration: load, call a domain method, save.
- Value objects are immutable with equality based on attributes.
- **Use modern C# / .NET idioms** appropriate to .NET 8 — `record` /
  `readonly record struct` for value objects, `required` / `init`-only properties,
  file-scoped namespaces, nullable reference types, pattern matching. Do not
  preserve the legacy NHibernate-era boilerplate. Note that NHibernate requires
  mapped *entity* members to be `virtual` with a (possibly protected) parameterless
  constructor — honor that on the entities while still modernizing the model.

## Success Criteria
1. The `Before` solution compiles successfully on .NET 8.
2. Domain entities contain behavior methods (not just getters/setters).
3. Service classes are thin orchestrators — no business logic in `if`/`switch`
   blocks (or removed entirely).
4. At least one value object has been introduced.
5. The code reads like a modern .NET 8 codebase, not a port of a legacy app.
