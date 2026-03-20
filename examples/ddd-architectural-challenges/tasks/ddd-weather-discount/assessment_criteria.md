# Assessment Criteria: Weather-Based Discount

Evaluate the AI-generated code across five dimensions.

## 1. Domain Modeling (0–25)

Evaluate how well weather-related concepts are modeled using DDD building blocks.

| Score | Criteria |
|-------|----------|
| 0     | No domain types for weather data — raw HTTP responses or primitive types used in domain logic |
| 5     | Some domain types exist but weather data modeled as DTOs or anemic data holders, not proper value objects |
| 10    | Weather data has domain types but they leak infrastructure concerns (JSON annotations, HTTP status codes) |
| 15    | Clean domain types for weather data (e.g. precipitation as value object), but discount logic not modeled as a domain service or policy |
| 20    | Good domain modeling: weather data as value objects, discount logic as domain service/policy, but error handling uses infrastructure exceptions instead of domain-appropriate patterns |
| 25    | Excellent: weather conditions modeled as proper value objects, discount logic encapsulated in domain service/policy, failures handled through domain patterns (Result types, domain exceptions, or safe defaults), domain layer has zero infrastructure dependencies |

**Key checks:**
- Does a port/interface exist in the domain layer for weather data?
- Does the port use domain types (not `HttpResponseMessage`, `JsonElement`, etc.)?
- Is discount calculation logic in a domain service or policy (not in the adapter)?
- Are weather conditions modeled as value objects with proper semantics?

## 2. Encapsulation (0–20)

Evaluate whether business rules are contained within domain objects.

| Score | Criteria |
|-------|----------|
| 0     | Weather discount logic scattered across adapter and controller layers |
| 5     | Some logic in domain objects but precipitation thresholds hardcoded in infrastructure |
| 10    | Discount calculation in domain but weather data interpretation still external |
| 15    | Domain service/policy owns all business rules; adapter only translates HTTP to domain types |
| 20    | Perfect encapsulation: domain objects own all rules, weather interpretation, and discount logic. Infrastructure only handles transport. Domain objects cannot be misused by callers |

**Key checks:**
- Is the "precipitation > X means discount" rule inside the domain layer?
- Can callers bypass domain rules by constructing objects directly?
- Are failure modes (API down) handled with domain-appropriate defaults?

## 3. Architecture Compliance (0–20)

Evaluate separation of concerns, layer isolation, and adherence to project conventions.

| Score | Criteria |
|-------|----------|
| 0     | HttpClient used directly in domain logic, no separation |
| 5     | Some separation attempted but domain still references `System.Net.Http` or concrete HTTP types |
| 10    | Interface/port exists for weather data, but domain logic still depends on HTTP concepts |
| 15    | Clean port interface in domain, adapter in infrastructure, proper DI registration, but minor issues (e.g. no timeout, port in wrong namespace) |
| 20    | Excellent: domain port in domain layer returning domain value types, infrastructure adapter in separate project/namespace, timeout configured, all failure modes handled gracefully, proper DI registration, domain has zero reference to infrastructure |

**Key checks:**
- Is the HTTP adapter in an infrastructure/adapter layer?
- Does the domain project have any reference to `System.Net.Http`?
- Is the adapter registered in DI container?
- Is HttpClient timeout configured?
- Does API failure result in "no discount" (not an exception propagating up)?

## 4. Extensibility (0–15)

Evaluate how easy it is to add future weather-based discounts (temperature, wind, UV, etc.).

| Score | Criteria |
|-------|----------|
| 0     | Hardcoded precipitation logic, no extensibility consideration |
| 3     | Single weather discount class with if/else for different conditions |
| 6     | Some abstraction exists but adding a new weather discount requires changes in multiple places |
| 9     | Strategy/Policy pattern used — new weather discounts can be added as new classes, but weather provider interface only supports precipitation |
| 12    | Good design: Strategy pattern, weather provider can return multiple parameters, but minor issues |
| 15    | Excellent: Strategy/Policy pattern, weather provider returns flexible data, new weather discounts are just new classes implementing a common interface, Open-Closed Principle fully respected |

**Key checks:**
- Is there an abstraction for weather-based discount rules?
- Can a new weather discount be added by only creating a new class?
- Does the weather provider support fetching multiple parameters?
- Would adding UV index discount require changing existing classes?

## 5. Test Quality (0–20)

Evaluate test coverage and proper isolation from external services.

| Score | Criteria |
|-------|----------|
| 0     | No tests, or tests that call the real API |
| 4     | Basic tests exist but call real HTTP endpoints |
| 8     | Mock/stub for HTTP client exists, but only tests happy path |
| 12    | Good mock isolation, tests happy path and API failure, but missing edge cases |
| 16    | Comprehensive: mocked HTTP client, tests for precipitation > 0 (discount), precipitation = 0 (no discount), API failure (no discount), but minor gaps |
| 20    | Excellent: HTTP client properly mocked, unit tests for domain logic, integration tests for adapter, tests cover: happy path, no precipitation, API failure, malformed response, follows project test conventions |

**Key checks:**
- Is HttpClient mocked?
- Tests for: precipitation present (discount applies), no precipitation (no discount)?
- Tests for: API failure returns no discount?
- Are unit tests separated from integration tests?
- Is there a test for domain logic independent of infrastructure?
