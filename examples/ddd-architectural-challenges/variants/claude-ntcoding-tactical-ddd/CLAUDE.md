# Agent Instructions

## Approach

1. Before writing any code, explore the existing codebase to understand its architecture and conventions.
2. Follow existing architectural patterns exactly — match naming, namespaces, directory structure, and code style.
3. Write tests that match the style of existing test files.

## Available skills

You have access to the **`tactical-ddd`** skill (`.claude/skills/tactical-ddd/SKILL.md`). It captures Nick Tunes' tactical domain-driven design principles: isolate domain logic, rich domain language, avoid anemic models, design aggregates around invariants, extract value objects liberally, and more.

**This task involves DDD work in a C# / .NET 8 codebase. Consult the `tactical-ddd` skill before designing or writing domain code.** The skill's code examples are written in TypeScript — translate the *principles* into idiomatic C# for this codebase (e.g. `readonly record struct` for value objects, `[DddValueObject]` / `[DddDomainService]` annotations, discriminated unions via sealed class hierarchies or pattern matching). The principles are language-agnostic; the syntax is not.
