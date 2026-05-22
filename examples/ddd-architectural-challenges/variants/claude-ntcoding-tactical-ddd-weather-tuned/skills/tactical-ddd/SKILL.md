---
name: tactical-ddd
description: "Design, refactor, analyze, and review code by applying the principles and patterns of tactical domain-driven design. Triggers on: domain modeling, aggregate design, 'entity', 'value object', 'repository', 'bounded context', 'domain event', 'domain service', code touching domain/ directories, rich domain model discussions."
version: 1.0.0
---

<!-- Source: ntcoding/claude-skillz, snapshot 2026-03-20 -->
<!-- REPO-TUNED VARIANT (DDD-starter): C# examples reference this repo's own value objects
     (Money, PercentageDiscount, the Discount discriminated union, Sources/Sales/... paths).
     This is the deliberate "skill adapted to your repo" arm — NOT the pristine public skill.
     Recovered verbatim from the run artifacts that produced the weather-tuned = 90 result. -->
<!-- Examples rewritten from TypeScript to C# / .NET (idiomatic for DDD-starter-dotnet codebase) -->

# Tactical DDD

Design, refactor, analyze, and review code by applying the principles and patterns of tactical domain-driven design.

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
public class Delivery
{
    public async Task Dispatch()
    {
        _logger.LogInformation("Dispatching delivery {Id}", _id);   // Infrastructure!
        await _db.BeginTransactionAsync();                          // Infrastructure!
        if (_status != DeliveryStatus.Ready) throw new InvalidOperationException("Not ready");
        _status = DeliveryStatus.Dispatched;
        await _db.SaveAsync(this);                                  // Infrastructure!
        await _db.CommitAsync();                                    // Infrastructure!
        await _pushNotification.NotifyDriver();                     // Infrastructure!
    }
}

// ✅ RIGHT - isolated domain logic
public class Delivery
{
    public void Dispatch()
    {
        if (_status != DeliveryStatus.Ready)
            throw new DeliveryNotReadyError(_id);
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
public class ClaimHandler
{
    public ProcessingResult ProcessClaimData(ClaimDto claimData)
        => _claimProcessor.Handle(claimData);
}

// ✅ RIGHT - domain language
[DddDomainService]
public class ClaimAssessor
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
// UseCases/CalculateEta.cs
public async Task<Duration> CalculateEta(DeliveryId deliveryId)
{
    var delivery = await _deliveryRepository.Load(deliveryId);
    var driver = await _driverRepository.Load(delivery.DriverId);
    return _routeService.EstimateArrival(driver.Location, delivery.Destination);
}

// ✅ RIGHT - actual user goal (appears in menu)
// UseCases/CancelDelivery.cs
public async Task CancelDelivery(DeliveryId deliveryId, CancellationReason reason)
{
    var delivery = await _deliveryRepository.Load(deliveryId);
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
    var delivery = await _deliveryRepository.Load(deliveryId);

    // Business rules leaked into use case!
    if (delivery.Status != DeliveryStatus.InTransit)
        throw new InvalidOperationException("Delivery not in transit");
    if (photo is null && delivery.RequiresSignature)
        throw new InvalidOperationException("Proof of delivery required");

    delivery.Status = DeliveryStatus.Delivered;
    delivery.ProofPhoto = photo;
    delivery.DeliveredAt = DateTime.UtcNow;
    await _deliveryRepository.Save(delivery);
}

// ✅ RIGHT - use case orchestrates, domain decides
public async Task ConfirmDropoff(DeliveryId deliveryId, ProofPhoto photo)
{
    var delivery = await _deliveryRepository.Load(deliveryId);

    delivery.ConfirmDropoff(photo);  // Domain enforces the rules

    await _deliveryRepository.Save(delivery);
}
```

**Signs of anemic model:**
- Use cases full of if/else business logic
- Domain objects are just data with `{ get; set; }` properties
- Business rules duplicated across multiple use cases
- Validation logic outside the object being validated
- A domain object exposes `IsX()` + `DoX()` ("ask, don't tell") instead of a single decision method that both checks and acts

---

## 5. Separate generic concepts

**What:** Generic capabilities that aren't specific to your domain live separately from domain-specific logic.

**Why:** A retry mechanism, a caching layer, a validation framework—these aren't YOUR domain. Mixing them with domain logic obscures what's actually specific to your business.

**Test:** Would this code exist in a completely different business domain? If yes, it's generic. If it's specific to YOUR business rules, it's domain.

```csharp
// ❌ WRONG - generic retry logic mixed with domain
// Sales.DeepModel/Delivery/DriverLocator.cs
[DddDomainService]
public class DriverLocator
{
    // Generic retry logic does not belong in domain!
    private async Task<T> WithRetry<T>(Func<Task<T>> fn, int attempts)
    {
        for (var i = 0; i < attempts; i++)
        {
            try { return await fn(); }
            catch { if (i == attempts - 1) throw; }
        }
        throw new InvalidOperationException("Retry failed");
    }

    public Task<Driver> FindAvailableDriver(Zone zone)
        => WithRetry(() => SearchDriversInZone(zone), 3);

    private Task<Driver> SearchDriversInZone(Zone zone) { /* domain logic */ }
}

// ✅ RIGHT - same behavior, properly separated
// Sales.Adapters/Retry/Retry.cs (generic, reusable anywhere)
public static class Retry
{
    public static async Task<T> WithAttempts<T>(Func<Task<T>> fn, int attempts)
    {
        for (var i = 0; i < attempts; i++)
        {
            try { return await fn(); }
            catch { if (i == attempts - 1) throw; }
        }
        throw new InvalidOperationException("Retry failed");
    }
}

// Sales.DeepModel/Delivery/DriverLocator.cs (pure domain, no infra references)
[DddDomainService]
public class DriverLocator
{
    public Task<Driver> FindAvailableDriver(Zone zone) { /* domain logic */ }
}

// UseCases/DispatchDelivery.cs (orchestrates domain + infra)
public async Task DispatchDelivery(DeliveryId deliveryId)
{
    var delivery = await _deliveryRepository.Load(deliveryId);
    var driver = await Retry.WithAttempts(
        () => _driverLocator.FindAvailableDriver(delivery.Zone), attempts: 3);
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
public class Delivery
{
    public DeliveryStatus Status { get; private set; }
    public Driver? Driver { get; private set; }
    public DateTime? PickupTime { get; private set; }
    public DateTime? DropoffTime { get; private set; }
    public Photo? ProofOfDelivery { get; private set; }

    public void AssignDriver(Driver driver)
    {
        if (Status != DeliveryStatus.Confirmed) throw new InvalidOperationException("...");
        Driver = driver;
        Status = DeliveryStatus.Assigned;
    }

    public void RecordPickup()
    {
        if (Status != DeliveryStatus.Assigned) throw new InvalidOperationException("...");
        PickupTime = DateTime.UtcNow;
        Status = DeliveryStatus.InTransit;
    }

    public void RecordDropoff(Photo photo)
    {
        if (Status != DeliveryStatus.InTransit) throw new InvalidOperationException("...");
        ProofOfDelivery = photo;
        DropoffTime = DateTime.UtcNow;
        Status = DeliveryStatus.Delivered;
    }
}

// But the TYPES can describe the domain! Each state is a distinct concept.
// Reading the types alone tells you how deliveries work.

// Modelled as a discriminated union via readonly struct + Kind enum
// (the same pattern as Discount in this codebase: see Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs)
[DddValueObject]
public readonly struct Delivery : IEquatable<Delivery>
{
    private readonly DeliveryKind _kind;
    private readonly RequestedDelivery _requested;
    private readonly ConfirmedDelivery _confirmed;
    private readonly AssignedDelivery _assigned;
    private readonly InTransitDelivery _inTransit;
    private readonly DeliveredDelivery _delivered;

    public static Delivery Requested(Customer customer, Restaurant restaurant, IReadOnlyList<MenuItem> items) =>
        new(DeliveryKind.Requested, RequestedDelivery.Of(customer, restaurant, items),
            default, default, default, default);

    public Delivery Confirm(Duration estimatedPrepTime) => _kind switch
    {
        DeliveryKind.Requested => new(DeliveryKind.Confirmed, default,
            ConfirmedDelivery.From(_requested, estimatedPrepTime), default, default, default),
        _ => throw new DomainError($"Cannot confirm delivery in state {_kind}")
    };

    public Delivery AssignDriver(Driver driver) => _kind switch
    {
        DeliveryKind.Confirmed => new(DeliveryKind.Assigned, default, default,
            AssignedDelivery.From(_confirmed, driver), default, default),
        _ => throw new DomainError($"Cannot assign driver in state {_kind}")
    };

    // ... RecordPickup, RecordDropoff follow the same pattern

    private enum DeliveryKind { Requested, Confirmed, Assigned, InTransit, Delivered }
}

// Each state is a value object holding ONLY the fields guaranteed at that state:

[DddValueObject]
public readonly record struct RequestedDelivery(
    Customer Customer, Restaurant Restaurant, IReadOnlyList<MenuItem> Items)
{
    public static RequestedDelivery Of(Customer c, Restaurant r, IReadOnlyList<MenuItem> i) => new(c, r, i);
}

[DddValueObject]
public readonly record struct AssignedDelivery(
    Customer Customer, Restaurant Restaurant, IReadOnlyList<MenuItem> Items,
    Driver Driver,                  // Now guaranteed non-null
    DateTime EstimatedPickup)
{
    public static AssignedDelivery From(ConfirmedDelivery prev, Driver driver) => new(
        prev.Customer, prev.Restaurant, prev.Items, driver, DateTime.UtcNow.AddMinutes(15));
}

[DddValueObject]
public readonly record struct DeliveredDelivery(
    Customer Customer, Restaurant Restaurant, IReadOnlyList<MenuItem> Items,
    Driver Driver,
    DateTime PickupTime,
    DateTime DropoffTime,           // Now guaranteed non-null
    Photo ProofOfDelivery);         // Now guaranteed non-null
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
- Model states as distinct types (Delivery with `Status` enum → RequestedDelivery, ConfirmedDelivery, etc. via the readonly-struct discriminated-union pattern this codebase already uses for `Discount`)
- Make optional fields guaranteed at the right state (`Driver?` → `Driver` non-null in `AssignedDelivery`)
- Extract conditionals to named methods (complex `if` → `ExceedsDriverRange`)
- Rename variables to use domain language (`standardFee` → `defaultDeliveryFee`)

---

## 7. Design aggregates around invariants

**What:** An aggregate is a cluster of objects that must be consistent together. The aggregate root enforces the rules. External code cannot violate invariants.

**Why:** Without clear boundaries, inconsistent states creep in. One piece of code updates the delivery, another updates the route, and suddenly the ETA is wrong.

**Test:** What must be true at all times? What rules must never be broken? The objects involved in those rules form an aggregate.

```csharp
// ❌ WRONG - no aggregate boundary, invariants violated
public class Delivery
{
    public List<DeliveryStop> Stops { get; set; }       // Exposed!
    public Distance TotalDistance { get; set; }
}

// External code can break invariants
delivery.Stops.Add(new DeliveryStop(location));
// Oops - TotalDistance is now wrong!

// ✅ RIGHT - aggregate protects invariants
[DddAggregateRoot]
public class Delivery
{
    private readonly List<DeliveryStop> _stops = new();
    private Distance _totalDistance = Distance.Zero();
    public DeliveryStatus Status { get; private set; }

    public IReadOnlyList<DeliveryStop> Stops => _stops;
    public Distance TotalDistance => _totalDistance;

    public void AddStop(Location location)
    {
        if (Status != DeliveryStatus.Planning)
            throw new DeliveryNotModifiableError(_id);

        var previousStop = _stops[^1];
        var stop = new DeliveryStop(location);
        _stops.Add(stop);
        _totalDistance = _totalDistance.Add(
            previousStop.DistanceTo(location));            // Invariant maintained!
    }

    public void RemoveStop(StopId stopId)
    {
        if (_stops.Count <= 2)
            throw new MinimumStopsRequiredError(_id);

        _stops.RemoveAll(s => s.Id.Equals(stopId));
        _totalDistance = CalculateTotalDistance();         // Invariant maintained!
    }
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
public class Delivery
{
    public DeliveryId Id { get; }
    public decimal FeeAmount { get; private set; }
    public string FeeCurrency { get; private set; }
}

// Extract the value object
public class Delivery
{
    public DeliveryId Id { get; }
    public Money Fee { get; private set; }
}

// Idiomatic C# value object in this codebase:
// readonly struct, IEquatable<T>, static factory, validating ctor, override Equals/GetHashCode.
// (See Sources/Sales/Sales.Commons/Money.cs and PercentageDiscount.cs for the canonical shape.)
[DddValueObject]
public readonly struct Money : IEquatable<Money>
{
    public decimal Amount { get; }
    public Currency Currency { get; }

    public static Money Of(decimal amount, Currency currency) => new(amount, currency);

    private Money(decimal amount, Currency currency)
    {
        if (amount < 0) throw new DomainError("Money amount cannot be negative");
        Amount = amount;
        Currency = currency;
    }

    public Money Add(Money other)
    {
        if (Currency != other.Currency)
            throw new CurrencyMismatchError(Currency, other.Currency);
        return new Money(Amount + other.Amount, Currency);
    }

    public bool Equals(Money other) => Amount == other.Amount && Currency == other.Currency;
    public override bool Equals(object? obj) => obj is Money other && Equals(other);
    public override int GetHashCode() => HashCode.Combine(Amount, Currency);
    public override string ToString() => $"{Amount} {Currency}";
}
```

**Good candidates for value objects:**
- `Money`, `Currency`, `Percentage`
- `DateRange`, `TimeSlot`, `Duration`
- `Address`, `Coordinates`, `Distance`
- `EmailAddress`, `PhoneNumber`, `Url`
- `Quantity`, `Weight`, `Temperature`, `Precipitation`
- `PersonName`, `CompanyName`

---

## 9. Repositories are for loading and saving full aggregates

The job of a repository is to load and save entire aggregates - not partial aggregates or nested entities inside an aggregate. The `Load` method takes an ID and returns the full aggregate.

A repository should not exist for a domain object that is not an aggregate. An entity that is part of an aggregate → does not have a repository. It is loaded via the aggregate root's repository.

The `Hydrate` method is used ONLY for constructing an aggregate from its persisted state. It should not be abused for other use cases like creating new instances. Each creation flow should have a dedicated factory method, e.g. `Order.FromExisting()`, `Order.New()`, `Order.Draft()`.

The `Save` method of a repository should take the full aggregate.

If you just want to query information to display without modifying state and applying business rules, create a separate read model object and don't use a repository.

```csharp
// ✅ RIGHT - repository for an aggregate root, factory methods for each creation scenario
public interface IDeliveryRepository
{
    Task<Delivery> Load(DeliveryId id);
    Task Save(Delivery delivery);
}

public class Delivery
{
    // Hydration: reconstruct from persistence — DO NOT use for new instances
    public static Delivery Hydrate(DeliveryId id, DeliveryStatus status, IReadOnlyList<DeliveryStop> stops,
        Distance totalDistance) => new(id, status, stops, totalDistance);

    // Creation factories — one per use case:
    public static Delivery Draft(Customer customer) => new(DeliveryId.New(), DeliveryStatus.Draft,
        new List<DeliveryStop>(), Distance.Zero());

    public static Delivery FromQuote(Quote quote) => new(DeliveryId.New(), DeliveryStatus.Planning,
        quote.Stops, quote.TotalDistance);
}
```

---

## Mandatory Checklist

When designing, refactoring, analyzing, or reviewing code:

1. [ ] Verify domain is isolated from infrastructure (no DB/HTTP/logging in domain; generic utilities in infra; domain doesn't `using` infra)
2. [ ] Verify names are from YOUR domain, not generic developer jargon (`Manager`, `Handler`, `Data`, `Process`)
3. [ ] Verify use cases are intentions of users, human or automated (apply the menu test)
4. [ ] Verify business logic lives in domain objects, use cases only orchestrate. **No `IsApplicable()` + `Apply()` split** — give the domain object one decision method that both checks and acts
5. [ ] Verify states are modeled as distinct types where appropriate (readonly-struct discriminated unions; see `Discount` in this codebase)
6. [ ] Verify hidden domain concepts are extracted and named explicitly (a `decimal precipitation` should usually become a `Precipitation` value object)
7. [ ] Verify aggregates are designed around invariants, not naive mapping of domain nouns
8. [ ] Verify values are extracted into value objects expressing a domain concept (`readonly struct`, `IEquatable<T>`, static `Of(...)` factory, validating private ctor, override `Equals`/`GetHashCode`/`ToString`)
9. [ ] Verify no abuse of hydrate methods for creation scenarios. Each creation scenario must have a dedicated factory method (`Of`, `New`, `Draft`, `FromExisting`, ...)

Do not proceed until all checks pass.
