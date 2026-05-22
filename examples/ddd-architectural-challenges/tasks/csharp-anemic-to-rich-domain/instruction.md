# Task: Refactor Anemic Domain Model to Rich Domain Model

## Context
You are working in `/app`, a C# ASP.NET Core 2.2 application that manages companies, persons, and employees. The codebase follows a classic anemic domain model anti-pattern: domain classes (`Person`, `Company`, `Employee`) are plain data containers with only public getters and setters, while all business logic lives in application service classes (`PersonService`, `CompanyService`, `EmployeeService`).

The project structure:
```
DotNetConfPl.Refactoring/
  Domain/           # Anemic entities — just properties, no behavior
  Application/      # Services containing ALL business logic
  Controllers/      # HTTP controllers
  Infrastructure/   # EF Core configuration
```

## Requirement
Refactor the domain model from anemic to rich. Business rules currently in service classes must move into domain objects where they belong.

Specifically:
1. **Person**: The `ChangePersonNames` logic in `PersonService` (name validation, `FullName` computation) should be encapsulated inside the `Person` entity. A `Person` should never exist with invalid names, and `FullName` should always be consistent with `FirstName` and `LastName`.

2. **Company**: Business rules around company creation, importing, and contact employee assignment (currently in `CompanyService`) should move into the `Company` entity. The company should protect its own invariants.

3. **Employee**: The logic for creating an employee relationship between a person and a company (currently in `PersonService.SetPersonAsEmployee`) should be moved into the domain. The invariant "a person cannot be an active employee of the same company more than once" must be enforced by the domain, not the service.

4. **Value Objects**: Identify primitive types that represent domain concepts and extract them as value objects. Candidates: person name (first + last + full), email, phone.

## Scope
- Modify files in `Domain/` to add behavior and invariants
- Modify files in `Application/` to remove business logic (services become thin orchestrators)
- Do NOT change the public API (controllers, DTOs, HTTP endpoints)
- Do NOT modify `Infrastructure/` EF Core configurations unless necessary for domain changes

## Quality Expectations
- Domain objects enforce their own invariants — constructors and methods should reject invalid state
- Services contain only orchestration: load, call domain method, save
- Value objects are immutable with equality based on attributes
- Follow existing C# conventions in the project

## Success Criteria
1. The project compiles successfully
2. Domain entities contain behavior methods (not just getters/setters)
3. Service classes are thin orchestrators — no business logic in if/else blocks
4. At least one value object has been introduced
