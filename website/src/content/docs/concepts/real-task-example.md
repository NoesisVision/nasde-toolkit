---
title: A Real Task (DDD example)
description: One benchmark task shown end to end — instruction, assessment criteria, and the scores four agent configurations earned against it.
---

Everything in [How Scoring Works](/nasde-toolkit/concepts/scoring/) is easier to grasp on a concrete example. Here is one benchmark task from the repo — [`examples/ddd-architectural-challenges/tasks/ddd-weather-discount`](https://github.com/NoesisVision/nasde-toolkit/tree/main/examples/ddd-architectural-challenges/tasks/ddd-weather-discount) — shown end to end: the agent's instruction, the assessment criteria, and the resulting scores.

## `instruction.md` — what the coding agent is asked to do

> **Task — Implement a weather-based discount.**
>
> You are working on an e-commerce system built using **Domain-Driven Design** and **hexagonal architecture** (.NET 8, C#). Implement a discount that:
>
> - Checks current weather in Warsaw via the Open-Meteo API.
> - Applies a **10% discount** when `precipitation > 0`.
> - Must be **extensible**: more weather-based discounts (temperature, wind, UV, humidity) will follow and should plug in without rewrites.
>
> **Quality expectations:** fit into the existing DDD architecture · handle API failures gracefully (do not break order processing) · write unit and integration tests · follow codebase conventions.

## `assessment_criteria.md` — what the reviewer scores against (excerpt)

The criteria spell out what each score means for each dimension. Here is the full ladder for the *Domain Modeling* dimension — in this benchmark the author chose a 0–25 scale (the scale is entirely up to you: 0–5, 0–10, 0–100, named levels, pass/fail only, whatever fits):

| Score | Criteria |
|:---:|---|
| **0**  | No domain types for weather — raw HTTP responses or primitives used directly in domain logic. |
| **10** | Domain types exist for weather, but they leak infrastructure concerns (JSON annotations, HTTP status codes). |
| **15** | Clean domain types (precipitation as a value object), but discount logic is *not* modeled as a domain service or policy. |
| **20** | Good domain modeling and discount as a domain service, but error handling uses infrastructure exceptions instead of domain-appropriate patterns. |
| **25** | Weather modeled as value objects · discount encapsulated in a domain service/policy · failures handled via domain patterns (Result type, domain exceptions, safe defaults) · domain layer has **zero** infrastructure dependencies. |

**Key checks for the reviewer agent:**

- Is there a port / interface for weather data in the *domain* layer?
- Does that port use domain types (not `HttpResponseMessage`, `JsonElement`)?
- Is the discount rule inside a domain service / policy, or living in the HTTP adapter?
- Are failure modes (API down) handled with domain-appropriate defaults?

> The full assessment covers four more dimensions the benchmark author picked for this task (*Encapsulation* · *Architecture Compliance* · *Extensibility* · *Test Quality*), each with its own ladder and checks. Another author would have chosen different dimensions or different scales for the same task.

## Results — four agent configurations scored against the same criteria

| Variant | Pass | Domain (/25) | Encaps. (/20) | Arch. (/20) | Ext. (/15) | Tests (/20) | Total (/100) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `claude-vanilla` | 75% | 17.1 | 11.2 | 16.1 | 9.5 | 7.7 | **61.6** |
| `claude-guided` (with a DDD skill) | 75% | 17.4 | 12.4 | 16.6 | 10.0 | 8.7 | **65.1** |
| `codex-vanilla` | 89% | 18.8 | 13.8 | 16.8 | 11.4 | 8.7 | **69.4** |
| `codex-guided` (same skill) | 50% | 11.5 | 9.6 | 12.9 | 7.4 | 6.0 | **47.4** |

**The insight:** the same "DDD guidance" skill helps Claude a little (+3.5) and *badly* hurts Codex (-22). The per-dimension breakdown pinpoints *where* Codex regresses — domain modeling, encapsulation, extensibility — which would be invisible without this assessment. Skill optimization is agent-specific.

## Deep dive — does a public skill, and tuning it, actually help?

A separate study took a public DDD skill (the `tactical-ddd` skill from `ntcoding/claude-skillz`) and its repo-tuned version across four configurations on two deliberately different tasks — a feature on a clean DDD codebase and a legacy anemic→rich refactor. The headline: **a repo-tuned skill measurably beats the bare model on both tasks** (+0.12 on the clean feature, +0.05 on the legacy refactor — increment over vanilla, both clearing our significance bar), and it also beats hand-written DDD hints. But an **off-the-shelf public skill helps only on the greenfield feature** (+0.07) — on the legacy refactor it doesn't beat the bare model at all. Two lessons that generalize: judge *per dimension*, not one aggregate (a real architecture gain can hide inside a flat average); and a skill present on disk is not a skill used — verify it activated.

→ Full tables, per-dimension radars, and token/time charts in **[Benchmark Results](/nasde-toolkit/guides/benchmark-results/#deep-dive--tactical-ddd-skill-public-vs-repo-tuned-claude-code)**.

## More benchmarks in the repo

- **Refactoring katas (Java + Python)** — four classic refactorings scored on behavior preservation, clarity, technique, scope discipline. *Takeaway:* a candidate "refactoring skill" didn't move the score — shipping it would have been based on vibes.
- **Project-specific skill validation (NASDE's own repo)** — one task pulled from NASDE's git history; four skill combinations tested. *Takeaway:* the testing-discipline skill alone raised pass rate from 67% → 100%; the "full-stack, everything-on" variant scored *worse* than vanilla.

See **[Benchmark Results](/nasde-toolkit/guides/benchmark-results/)** for the full tables and methodology, and **[Use Cases](/nasde-toolkit/guides/use-cases/)** for the end-to-end walkthrough of building a benchmark like these yourself.
