# Task: Trip Service — Break Static Dependencies

## Context

You are working in `/app`, a Java project (the `java/` directory) that models a social trip-sharing service. The relevant code is:

```
java/
  src/main/java/org/craftedsw/tripservicekata/
    trip/TripService.java       # Service under refactoring
    trip/TripDAO.java           # Static data access (hardcoded DB dependency)
    user/User.java              # User domain model
    user/UserSession.java       # Static session management (singleton)
    exception/...               # Custom exceptions
  src/test/java/org/craftedsw/tripservicekata/
    trip/TripServiceTest.java   # Existing test skeleton
```

`TripService.getTripsByUser(User)` retrieves trips for a given user, but only if the logged-in user is a friend of that user. The method calls `UserSession.getInstance().getLoggedUser()` (a static singleton) and `TripDAO.findTripsByUser(user)` (a static data access call).

## Requirement

The `TripService` class has two problems that make it untestable and rigid:

1. **Static singleton dependency**: It calls `UserSession.getInstance().getLoggedUser()` directly — you cannot test the service without a real HTTP session
2. **Static DAO dependency**: It calls `TripDAO.findTripsByUser()` directly — you cannot test without a real database connection

The method also has a deeply nested conditional structure that mixes authorization checks with trip retrieval logic.

Your task:
1. Make `TripService` testable by breaking its static dependencies — the service should receive its dependencies rather than reaching out to static singletons
2. Refactor the `getTripsByUser()` method to separate authorization from trip retrieval
3. Write comprehensive tests for `TripService` that cover: logged-in user is a friend (returns trips), logged-in user is not a friend (returns empty), no logged-in user (throws exception)

## Scope

- Focus on: `TripService.java` and `TripServiceTest.java`
- You may create interfaces or wrapper classes for `UserSession` and `TripDAO`
- Do NOT modify: `User.java` (unless adding a helper method like `isFriendOf`)
- Preserve: the business logic (friends see trips, non-friends get empty list, no session throws)

## Quality Expectations

- Follow Java conventions
- Tests should not depend on static state — use dependency injection and mocks/stubs
- The refactored code should be easy to understand and extend

## Success Criteria

1. The project compiles with `mvn compile`
2. All tests pass with `mvn test`
3. `TripService` no longer calls static methods on `UserSession` or `TripDAO` directly
4. Tests exist covering the three scenarios (friend, non-friend, no session)
