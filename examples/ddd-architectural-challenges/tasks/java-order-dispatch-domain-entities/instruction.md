# Task: Move Order Dispatch Logic into Domain Entities

## Context

You are working in `/app`, a Java project structured as a refactoring kata. The codebase models an order dispatch system where orders are dispatched to customers based on various rules.

The relevant project structure:
```
src/
  main/java/
    ...              — Order, Customer, and dispatch logic
  test/java/
    ...              — Test suite
```

## Requirement

The dispatch logic currently lives in a service or procedural function that reaches into Order and Customer objects to read their state and make dispatch decisions. The domain entities are data holders with getters — the classic anemic domain model.

Refactor the codebase so that domain entities own the dispatch decision logic:

- **Order** should know whether it is dispatchable based on its own state (status, items, validity).
- **Customer** should know whether it can receive dispatches based on its own state (active, valid address, etc.).
- The dispatch decision should emerge from collaboration between entities, not from an external service interrogating their internal state.
- Reduce or eliminate getters that only exist to let external code make decisions that the entity itself should make.

## Scope

- Focus on: domain entity classes and the dispatch service/function
- Do NOT modify: test assertions (tests should still pass with same semantics)
- Preserve: all existing test behavior

## Quality Expectations

- Follow Java idioms used in the existing codebase
- All existing tests must continue to pass
- Keep changes focused — move logic into entities without changing the external behavior

## Success Criteria

1. `mvn compile` (or `gradle build`) succeeds
2. All existing tests pass
3. Domain entities have behavior methods for dispatch-related decisions
4. The dispatch service/function is thinner — it delegates to entities instead of inspecting their state
