---
name: tactical-ddd
description: "Design, refactor, analyze, and review code by applying the principles and patterns of tactical domain-driven design. Triggers on: domain modeling, aggregate design, 'entity', 'value object', 'repository', 'bounded context', 'domain event', 'domain service', code touching domain/ directories, rich domain model discussions."
version: 1.0.0
---

<!-- Source: ntcoding/claude-skillz, snapshot 2026-03-20 -->
<!-- REPO-TUNED VARIANT: the conventions section + value-object example are adapted to THIS codebase
     (a movie-rental backend on .NET 8, NHibernate). This is the "skill adapted to your repo" arm of
     the experiment — NOT the pristine public skill. The repo originated on an old .NET version and is
     being modernized: write idiomatic .NET 8, do not preserve the legacy style. -->

# Tactical DDD

Design, refactor, analyze, and review code by applying the principles and patterns of tactical domain-driven design.

## This codebase's conventions

This codebase is a movie-rental backend targeting **.NET 8**, persisted with NHibernate. It originated
on an old .NET version and is being modernized as it is enriched — write idiomatic modern C#, do not
copy the legacy style:

- **File-scoped namespaces** (`namespace Logic.Entities;`), not bracketed blocks.
- **Value objects as `record` / `readonly record struct`** — you get value equality, `ToString`, and
  immutability for free, so do NOT hand-roll `Equals`/`GetHashCode`. Use `init`-only / `required`
  members and a static factory (or a validating primary constructor) so an instance cannot exist in
  an invalid state.
- **Do NOT introduce a functional-extensions / `Result<T>` library** (e.g. CSharpFunctionalExtensions).
  It is not referenced by the code you start from. Enforce invariants with a validating factory that
  throws a domain-specific exception. Keep the dependency set as-is — adding a value-object base-class
  library is exactly the kind of detour that breaks the build; stay with plain modern C#.
- **Nullable reference types enabled**; use them to make "must exist" vs "may be absent" explicit
  rather than relying on runtime null checks.
- **NHibernate constraints**: entities are mapped by NHibernate, which needs `virtual` members and a
  (protected/private) parameterless constructor to materialize them — add **only** those. NHibernate
  does **not** require the legacy MVC/serialization attributes that the starting code carries; do not
  treat them as something to be "preserved". Extract cohesive concepts into immutable `record` value
  objects around the entities.
- **Strip web/serialization/validation attributes off the domain entities**: the starting `Customer` /
  `Movie` / `PurchasedMovie` carry `[Required]`, `[RegularExpression]`, `[MaxLength]`,
  `[JsonConverter]`, `[JsonIgnore]`, `Newtonsoft.Json`, and `System.ComponentModel.DataAnnotations` —
  these are presentation/validation leaks, not domain concerns. Move validation **into** the domain
  (a factory or value object that throws a domain exception); JSON shaping belongs in the API/DTO
  layer, not on the entity. The domain layer must import **no** web or serialization namespace.
- **Layout**: `Logic/Entities` (domain entities), `Logic/Services` (services that orchestrate),
  `Logic/Repositories` + `Logic/Mappings` (NHibernate persistence), `Api/Controllers` (HTTP + DTOs).
  Keep domain logic out of services and out of the persistence/API layers.
- Keep the public API (controllers, DTOs, endpoints) unchanged when refactoring internals.

## Principles

1. **Isolate domain logic**
2. **Use rich domain language**
3. **Orchestrate with use cases**
4. **Avoid anemic domain model**
5. **Separate generic concepts**
6. **Make the implicit explicit... like your life depends on it**
7. **Design aggregates around invariants**
8. **Extract immutable value objects liberally**
9. **Repositories are for loading and saving full aggregates**

---

## 1. Isolate domain logic

**What:** Domain logic is not mixed with technical code like HTTP and database transactions.

**Why:** Easier to understand the most important part of the code, easier to validate with domain experts, easier to test and evolve, easier to plan and implement new features.

**Test:** Could a domain expert read the code? Can the code be unit tested without mocks or spinning up databases?

```csharp
// ❌ WRONG - domain polluted with infrastructure
class Delivery
{
    public async Task Dispatch()
    {
        _logger.LogInformation("Dispatching delivery {Id}", Id); // Infrastructure!
        await _db.BeginTransactionAsync();                       // Infrastructure!
        if (_status != "ready") throw new Exception("Not ready");
        _status = "dispatched";
        await _db.SaveAsync(this);                               // Infrastructure!
        await _db.CommitAsync();                                 // Infrastructure!
        await _pushNotification.NotifyDriverAsync();             // Infrastructure!
    }
}

// ✅ RIGHT - isolated domain logic
class Delivery
{
    public void Dispatch()
    {
        if (_status != DeliveryStatus.Ready)
            throw new DeliveryNotReadyError(Id);
        _status = DeliveryStatus.Dispatched;
        _dispatchedAt = DateTime.UtcNow;
    }
}
```

---

## 2. Use rich domain language

**What:** Names in code match exactly what domain experts say. No programmer jargon. No generic names.

**Why:** Translation between code-speak and business-speak causes bugs. When a domain expert says "assess a claim" and the code says "ProcessEntity", someone will misunderstand something.

**Test:** Would a domain expert recognize this name? If you'd need to translate it for them, it's wrong.

**Common generic terms to watch for:**
- `Manager`, `Handler`, `Processor`, `Helper`, `Util`
- `Data`, `Info`, `Item` (when domain terms exist)
- `Process`, `Handle`, `Execute` (what does it actually DO?)

```csharp
// ❌ WRONG - programmer jargon
class ClaimHandler
{
    public ProcessingResult ProcessClaimData(ClaimDto claimData)
    {
        return _claimProcessor.Handle(claimData);
    }
}

// ✅ RIGHT - domain language
class ClaimAssessor
{
    public AssessmentDecision AssessClaim(InsuranceClaim claim)
    {
        if (claim.ExceedsCoverageLimit())
            return AssessmentDecision.Deny(DenialReason.ExceedsCoverage);
        return AssessmentDecision.Approve();
    }
}
```

---

## 3. Orchestrate with use cases

**What:** A use case is a user goal—something a user would recognize as an action they can perform in your application.

**Why:** Use cases define the entry points to your domain. They answer "what can a user do?" If something isn't a user goal, it's supporting machinery that belongs elsewhere.

**Test (the menu test):** If you described your application's features to a user like a menu, would this be on it?

```
DELIVERY APP MENU:
├── Request Delivery     ← Use case: user goal
├── Track Delivery       ← Use case: user goal
├── Cancel Delivery      ← Use case: user goal
├── Calculate ETA        ← NOT a use case: internal machinery
└── Check Delivery Radius ← NOT a use case: domain rule
```

```csharp
// ❌ WRONG - not a user goal, this is internal machinery
// UseCases/CalculateEtaUseCase.cs
public async Task<Eta> CalculateEta(DeliveryId deliveryId)
{
    var delivery = await _deliveryRepository.Find(deliveryId);
    var driver = await _driverRepository.Find(delivery.DriverId);
    return _routeService.EstimateArrival(driver.Location, delivery.Destination);
}

// ✅ RIGHT - actual user goal (appears in menu)
// UseCases/CancelDeliveryUseCase.cs
public async Task CancelDelivery(DeliveryId deliveryId, CancellationReason reason)
{
    var delivery = await _deliveryRepository.Find(deliveryId);
    delivery.Cancel(reason);
    await _deliveryRepository.Save(delivery);
}
```

---

## 4. Avoid anemic domain model

**What:** Domain logic lives in domain objects, not in use cases. Use cases orchestrate; domain objects decide.

**Why:** When business rules leak into use cases, they scatter across the codebase, duplicate, and diverge. The domain becomes a dumb data carrier.

**Test:** Is your use case making business decisions, or just coordinating? If the use case contains if/else business logic, you likely have an anemic model.

```csharp
// ❌ WRONG - business logic in use case (anemic domain)
public async Task ConfirmDropoff(DeliveryId deliveryId, ProofPhoto photo)
{
    var delivery = await _deliveryRepository.Find(deliveryId);

    // Business rules leaked into use case!
    if (delivery.Status != "in_transit")
        throw new Exception("Delivery not in transit");
    if (photo == null && delivery.RequiresSignature)
        throw new Exception("Proof of delivery required");

    delivery.Status = "delivered";
    delivery.ProofPhoto = photo;
    delivery.DeliveredAt = DateTime.UtcNow;
    await _deliveryRepository.Save(delivery);
}

// ✅ RIGHT - use case orchestrates, domain decides
public async Task ConfirmDropoff(DeliveryId deliveryId, ProofPhoto photo)
{
    var delivery = await _deliveryRepository.Find(deliveryId);

    delivery.ConfirmDropoff(photo); // Domain enforces the rules

    await _deliveryRepository.Save(delivery);
}
```

**Signs of anemic model:**
- Use cases full of if/else business logic
- Domain objects are just data with getters/setters
- Business rules duplicated across multiple use cases
- Validation logic outside the object being validated

---

## 5. Separate generic concepts

**What:** Generic capabilities that aren't specific to your domain live separately from domain-specific logic.

**Why:** A retry mechanism, a caching layer, a validation framework—these aren't YOUR domain. Mixing them with domain logic obscures what's actually specific to your business.

**Test:** Would this code exist in a completely different business domain? If yes, it's generic. If it's specific to YOUR business rules, it's domain.

```csharp
// ❌ WRONG - generic retry logic mixed with domain
// Domain/DriverLocator.cs
class DriverLocator
{
    // Generic retry logic does not belong in domain!
    private async Task<T> WithRetry<T>(Func<Task<T>> fn, int attempts)
    {
        for (var i = 0; i < attempts; i++)
        {
            try { return await fn(); }
            catch { if (i == attempts - 1) throw; }
        }
        throw new Exception("Retry failed");
    }

    public Task<Driver> FindAvailableDriver(Zone zone)
        => WithRetry(() => SearchDriversInZone(zone), 3);

    private Task<Driver> SearchDriversInZone(Zone zone)
    {
        // domain logic to find nearest available driver
    }
}

// ✅ RIGHT - same behavior, properly separated
// Infrastructure/Retry.cs (generic, reusable in any project)
public static class Retry
{
    public static async Task<T> WithRetry<T>(Func<Task<T>> fn, int attempts)
    {
        for (var i = 0; i < attempts; i++)
        {
            try { return await fn(); }
            catch { if (i == attempts - 1) throw; }
        }
        throw new Exception("Retry failed");
    }
}

// Domain/DriverLocator.cs (pure domain, no infra imports)
class DriverLocator
{
    public Task<Driver> FindAvailableDriver(Zone zone)
    {
        // domain logic to find nearest available driver
    }
}

// UseCases/DispatchDeliveryUseCase.cs (orchestrates domain + infra)
public async Task DispatchDelivery(DeliveryId deliveryId)
{
    var delivery = await _deliveryRepository.Find(deliveryId);
    var driver = await Retry.WithRetry(
        () => _driverLocator.FindAvailableDriver(delivery.Zone), 3);
    delivery.AssignDriver(driver);
    await _deliveryRepository.Save(delivery);
}
```

---

## 6. Make the implicit explicit... like your life depends on it

**What:** Strive for maximum expressiveness. Go as far as possible to identify and name domain concepts in code. Don't settle for "good enough"—push until the code speaks the domain fluently.

**Why:** Maximum alignment optimizes communication between engineers and domain experts. Easier to discuss nuances and avoid misconceptions. Easier to plan and implement features and detect when the design of code is causing unnecessary friction.

**Test:** Could you discuss this code with a domain expert without translation? Are there concepts they use that don't exist in your code?

```csharp
// This code looks fine - isolated, uses domain terms
class Delivery
{
    public DeliveryStatus Status { get; private set; }
    public Driver? Driver { get; private set; }
    public DateTime? PickupTime { get; private set; }
    public DateTime? DropoffTime { get; private set; }
    public Photo? ProofOfDelivery { get; private set; }

    public void AssignDriver(Driver driver)
    {
        if (Status != DeliveryStatus.Confirmed) throw new Exception("...");
        Driver = driver;
        Status = DeliveryStatus.Assigned;
    }

    public void RecordPickup()
    {
        if (Status != DeliveryStatus.Assigned) throw new Exception("...");
        PickupTime = DateTime.UtcNow;
        Status = DeliveryStatus.InTransit;
    }

    public void RecordDropoff(Photo photo)
    {
        if (Status != DeliveryStatus.InTransit) throw new Exception("...");
        ProofOfDelivery = photo;
        DropoffTime = DateTime.UtcNow;
        Status = DeliveryStatus.Delivered;
    }
}

// But the TYPES can describe the domain! Each state is a distinct concept.
// Reading the types alone tells you how deliveries work.

abstract record Delivery;

record RequestedDelivery(           // Customer placed request
    Customer Customer,
    Restaurant Restaurant,
    IReadOnlyList<MenuItem> Items) : Delivery;

record ConfirmedDelivery(           // Restaurant accepted
    Customer Customer,
    Restaurant Restaurant,
    IReadOnlyList<MenuItem> Items,
    Duration EstimatedPrepTime) : Delivery;

record AssignedDelivery(            // Driver assigned, heading to restaurant
    Customer Customer,
    Restaurant Restaurant,
    IReadOnlyList<MenuItem> Items,
    Driver Driver,                  // Now guaranteed to exist
    Time EstimatedPickup) : Delivery;

record InTransitDelivery(           // Driver picked up, heading to customer
    Customer Customer,
    Restaurant Restaurant,
    IReadOnlyList<MenuItem> Items,
    Driver Driver,
    Time PickupTime,                // Now guaranteed to exist
    Time EstimatedDropoff) : Delivery;

record DeliveredDelivery(           // Complete with proof
    Customer Customer,
    Restaurant Restaurant,
    IReadOnlyList<MenuItem> Items,
    Driver Driver,
    Time PickupTime,
    Time DropoffTime,               // Now guaranteed to exist
    Photo ProofOfDelivery) : Delivery;

// State transitions are explicit functions
ConfirmedDelivery ConfirmDelivery(RequestedDelivery d, Duration prepTime);
AssignedDelivery AssignDriver(ConfirmedDelivery d, Driver driver);
InTransitDelivery RecordPickup(AssignedDelivery d);
DeliveredDelivery RecordDropoff(InTransitDelivery d, Photo photo);
```

**Smaller improvements matter too:**

```csharp
// Extract an if statement to a named method
if (distance.Kilometers > 10 && !driver.HasLongRangeVehicle) { ... }
if (delivery.ExceedsDriverRange(driver)) { ... }

// Name a boolean expression
var canAssign = driver.IsAvailable && driver.IsInZone(delivery.Zone) && !driver.AtCapacity;
var canAssign = driver.CanAccept(delivery);

// Rename to use domain language
var fee = customFee ?? standardFee;
var fee = customFee ?? defaultDeliveryFee;
```

**Ways to increase expressiveness:**
- Model states as distinct types (Delivery with status → RequestedDelivery, ConfirmedDelivery, etc.)
- Make optional fields guaranteed at the right state (`Driver? Driver` → `Driver Driver`)
- Extract conditionals to named methods (complex if → ExceedsDriverRange)
- Rename variables to use domain language (standardFee → defaultDeliveryFee)

---

## 7. Design aggregates around invariants

**What:** An aggregate is a cluster of objects that must be consistent together. The aggregate root enforces the rules. External code cannot violate invariants.

**Why:** Without clear boundaries, inconsistent states creep in. One piece of code updates the delivery, another updates the route, and suddenly the ETA is wrong.

**Test:** What must be true at all times? What rules must never be broken? The objects involved in those rules form an aggregate.

```csharp
// ❌ WRONG - no aggregate boundary, invariants violated
class Delivery
{
    public List<DeliveryStop> Stops; // Exposed!
    public Distance TotalDistance;
}

// External code can break invariants
delivery.Stops.Add(new DeliveryStop(location));
// Oops - TotalDistance is now wrong!

// ✅ RIGHT - aggregate protects invariants
class Delivery
{
    private readonly List<DeliveryStop> _stops = new();
    private Distance _totalDistance = Distance.Zero();

    public void AddStop(Location location)
    {
        if (_status != DeliveryStatus.Planning)
            throw new DeliveryNotModifiableError(Id);

        var previousStop = _stops[^1];
        var stop = new DeliveryStop(location);
        _stops.Add(stop);
        _totalDistance = _totalDistance.Add(
            previousStop.DistanceTo(location)); // Invariant maintained!
    }

    public void RemoveStop(StopId stopId)
    {
        if (_stops.Count <= 2)
            throw new MinimumStopsRequiredError(Id);

        // Recalculate total distance after removal
        _stops.RemoveAll(s => s.Id.Equals(stopId));
        _totalDistance = CalculateTotalDistance(); // Invariant maintained!
    }

    public Distance TotalDistance => _totalDistance;
}
```

**Aggregate rules:**
- One root entity per aggregate
- External code accesses only through the root
- The root enforces all invariants
- Reference other aggregates by ID, not object
- Methods should operate on the same state—if they don't, split the aggregate

---

## 8. Extract immutable value objects liberally

**What:** When something is defined by its attributes (not identity), make it an immutable value object. Do this liberally—more value objects is usually better.

**Why:** Value objects are simple. They can't change unexpectedly. They're easy to test. They make domain concepts explicit. They're also a good way to extract logic from aggregates and entities that can easily get large—keep entities focused by pulling cohesive concepts into value objects.

**Test:** Does this need a unique ID to track it over time? No? It's probably a value object.

```csharp
// Entity with primitives that should be a value object
class Delivery
{
    public DeliveryId Id;
    public decimal FeeAmount;
    public string FeeCurrency;
}

// Extract the value object
class Delivery
{
    public DeliveryId Id;
    public Money Fee;
}

// Value object in modern .NET 8 idiom: a readonly record struct — value equality,
// ToString and immutability for free (no hand-rolled Equals/GetHashCode), with a
// validating factory so an invalid instance cannot exist. File-scoped namespace.
namespace DotNetConfPl.Refactoring.Domain;

public readonly record struct Money
{
    public decimal Amount { get; }
    public Currency Currency { get; }

    private Money(decimal amount, Currency currency)
    {
        Amount = amount;
        Currency = currency;
    }

    public static Money Of(decimal amount, Currency currency) =>
        amount < 0
            ? throw new DomainException("Money amount cannot be negative")
            : new Money(amount, currency);

    public Money Add(Money other) =>
        Currency != other.Currency
            ? throw new DomainException("Cannot add money in different currencies")
            : new Money(Amount + other.Amount, Currency);
}
```

> EF Core maps a `readonly record struct` value object via an owned type or a value
> converter — keep the model expressible to EF, but don't regress to a mutable,
> ctor-less data bag just to satisfy the mapper.

**Good candidates for value objects:**
- Money, Currency, Percentage
- DateRange, TimeSlot, Duration
- Address, Coordinates, Distance
- EmailAddress, PhoneNumber, URL
- Quantity, Weight, Temperature
- PersonName, CompanyName

---

## 9. Repositories are for loading and saving full aggregates

The job of a repository is to load and save entire aggregates - not partial aggregates or nested entities inside an aggregate. The `load` method takes an ID and returns the full aggregate.

A repository should not exist for a domain object that is not an aggregate. Entity that is part of an aggreate -> does not have a repository. It is loaded via the aggregate root's repository.

The `hydrate` method is used ONLY for constructing an aggregate from it's persisted state. It should not be abused for other use cases like creating new instances. Each creation flow should have a dedicated factory method, e.g. `Order.FromExisting()`, `Order.New()`, `Order.Draft()`.

The `save` method of a repository should take the full aggregate.

If you just want to query information to display without modifying state and applying business rules, create a separate read model object and don't use a repository.

---

## Mandatory Checklist

When designing, refactoring, analyzing, or reviewing code:

1. [ ] Verify domain is isolated from infrastructure (no DB/HTTP/logging in domain; generic utilities in infra; domain doesn't import infra)
2. [ ] Verify names are from YOUR domain, not generic developer jargon
3. [ ] Verify use cases are intentions of users, human or automated (apply the menu test)
4. [ ] Verify business logic lives in domain objects, use cases only orchestrate
5. [ ] Verify states are modeled as distinct types where appropriate
6. [ ] Verify hidden domain concepts are extracted and named explicitly
7. [ ] Verify aggregates are designed around invariants, not naive mapping of domain nouns
8. [ ] Verify values are extracted into value objects expressing a domain concept
9. [ ] Veirfy no abuse of hydrate methods for creation scenarios. Each creation scenario must have dedicated factory method

Do not proceed until all checks pass.
