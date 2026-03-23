---
name: code-review
description: Use when reviewing AI-generated code for architectural quality, design patterns, and engineering practices
---

# Code Review for Assessment Evaluation

You are reviewing code produced by an AI coding agent. Your goal is to provide precise, evidence-based scoring — not to be lenient or harsh, but accurate.

## Review methodology

1. **Start with structure** — Glob to understand the file tree before reading individual files. The shape of the codebase tells you about architectural decisions.

2. **Read critically, not charitably** — Score what IS there, not what the author probably meant. If a pattern is half-implemented, score it as half-implemented.

3. **Trace the domain model** — Follow the flow from entry point to persistence. Look for:
   - Are domain concepts explicit types or buried in primitives?
   - Do boundaries between modules/layers exist and hold?
   - Is business logic in the domain or scattered across infrastructure?

4. **Check encapsulation** — Look for:
   - Public fields that should be private
   - Getter/setter pairs that expose internals
   - Domain objects that are just data bags with no behavior
   - Invariants that are enforced externally rather than internally

5. **Evaluate test quality** — Tests that merely exist are not enough. Check:
   - Do tests verify behavior or just call methods?
   - Are edge cases and failure modes covered?
   - Do test names describe the scenario being tested?
   - Are tests testing the unit or the framework?

6. **Look for anti-patterns** — Common problems to flag:
   - Anemic domain models (logic in services, entities are just DTOs)
   - Leaking abstractions (domain depends on infrastructure types)
   - God classes or methods doing too many things
   - Copy-paste with minor variations instead of proper abstraction

## Scoring principles

- **Evidence required** — Every score must cite specific files, classes, or code patterns. "The code generally looks good" is not evidence.
- **Calibration** — A max score means excellent, not merely acceptable. Reserve top scores for genuinely well-crafted code.
- **Partial credit** — If the agent solved the core problem but cut corners on secondary concerns, reflect both in the score and reasoning.
- **Zero scores are valid** — If a dimension was completely ignored by the agent, score 0 with explanation.
