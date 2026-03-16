# Agent Instructions

## Approach

1. Before writing any code, explore the existing codebase to understand its architecture and conventions.
2. Follow existing architectural patterns exactly — match naming, namespaces, directory structure, and code style.
3. Write tests that match the style of existing test files.

## Architecture guidelines

- Model domain concepts as Value Objects (immutable, with equality and factory methods) following existing examples in the codebase.
- Respect layer boundaries and separation of concerns — place code where similar code already lives.
- Design for extensibility: integrate new concepts into existing discriminated unions or pattern-matching structures so that adding further variants follows the same pattern.
- Cover edge cases and boundary conditions in tests, including validation of invalid inputs.