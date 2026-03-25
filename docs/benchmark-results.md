# Example Benchmark Results

Results from the three example benchmarks included in `examples/`. All scores are means across independent trials, assessed by Claude Opus 4.6 (Sonnet 4.6 for nasde-dev-skill) against structured per-task rubrics.

**Agents tested:** Claude Code (claude-sonnet-4-6) and OpenAI Codex (gpt-5.3-codex).

## UC2: Universal Skill Validation — Refactoring

4 tasks: Java + Python refactoring katas (Extract Hierarchy, Break Dependency, Polymorphism, Extract Method).

| Variant | Trials | Pass Rate | Behavior (30) | Clarity (25) | Technique (25) | Scope (20) | Total (100) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| claude-vanilla | 12 | 58% | 24.6 | 20.2 | 18.5 | 17.9 | **81.2** |
| claude-refactoring-skill | 12 | 50% | 22.9 | 19.3 | 17.8 | 17.5 | **77.6** |
| codex-vanilla | 8 | 62% | 25.0 | 20.5 | 19.6 | 16.5 | **81.6** |
| codex-refactoring-skill | 8 | 50% | 24.4 | 21.5 | 19.4 | 17.8 | **83.0** |

**Takeaway:** Both agents perform comparably on refactoring tasks (81-83 range). The refactoring skill does not provide measurable improvement — these tasks may be well within both agents' baseline capabilities.

## UC2: Universal Skill Validation — DDD Architectural Challenges

4 tasks: Java + C# domain modeling (Order Dispatch, Anemic-to-Rich, Threshold Discount, Weather Discount).

| Variant | Trials | Pass Rate | Domain (25) | Encaps. (20) | Arch. (20) | Extens. (15) | Tests (20) | Total (100) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| claude-vanilla | 12 | 75% | 17.1 | 11.2 | 16.1 | 9.5 | 7.7 | **61.6** |
| claude-guided | 12 | 75% | 17.4 | 12.4 | 16.6 | 10.0 | 8.7 | **65.1** |
| codex-vanilla | 9 | 89% | 18.8 | 13.8 | 16.8 | 11.4 | 8.7 | **69.4** |
| codex-guided | 8 | 50% | 11.5 | 9.6 | 12.9 | 7.4 | 6.0 | **47.4** |

**Takeaway:** Architectural guidance helps Claude (+3.5) but dramatically hurts Codex (-22.0). The same skill applied to different agents can have opposite effects — this is exactly the kind of insight NASDE is designed to surface.

## UC1: Project-Specific Setup — NASDE Dev Skill

1 task: Add multi-attempt support to the nasde-toolkit itself. Claude only (project-specific skill, cross-agent comparison not applicable).

| Variant | Trials | Pass Rate | Verification (25) | Conventions (25) | Architecture (25) | Documentation (25) | Total (100) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| claude-vanilla | 3 | 67% | 0.0 | 21.7 | 25.0 | 18.0 | **64.7** |
| claude-nasde-dev-with-testing | 3 | 100% | 8.0 | 21.7 | 25.0 | 14.7 | **69.3** |
| claude-nasde-dev-with-arch | 3 | 33% | 0.0 | 20.0 | 25.0 | 18.0 | **63.0** |
| claude-nasde-dev-full-stack | 3 | 33% | 2.7 | 18.3 | 24.0 | 12.0 | **57.0** |

> Evaluator: Claude Sonnet 4.6 (not Opus).

**Takeaway:** The testing-focused skill is the only variant that improves both pass rate (67% -> 100%) and adds verification discipline. Combining too many skills (full-stack) actually hurts performance — less is more.

## Evaluator Consistency

The LLM-as-a-Judge evaluator shows high scoring consistency:

- **Objective dimensions** (behavior preservation, architecture compliance): σ < 2.5 across repeated trials
- **Subjective dimensions** (refactoring technique, test quality): σ = 5-7
- **Identical agent output produces identical scores**: `claude-nasde-dev-with-arch` scored 63/63/63 across 3 independent trials (σ=0.0)

Observed variance is dominated by agent output differences and task difficulty, not evaluator noise.

## Methodology

- Claude variants: 3 independent trials per task. Codex variants: 2 trials per task.
- Each trial runs the agent in an isolated Docker container with fresh source code.
- Pass rate = percentage of trials where functional tests passed (Harbor verifier reward = 1.0).
- Assessment scores are means across all trials for a variant, including failed trials (scored as 0).
- Container memory: 4096 MB. Agent timeout: per task.toml (1200-1800s).
