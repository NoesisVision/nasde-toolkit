# Assessment Criteria: Add Multi-Attempt Support

Evaluate the agent's solution across the following dimensions.

## 1. Verification Discipline (0-25)

| Score | Criteria |
|-------|----------|
| 0     | No evidence of testing or verification |
| 8     | Tests pass but no evidence agent ran them proactively |
| 15    | Agent ran pytest, code works, no regressions |
| 20    | Agent verified CLI help output, tested flag parsing, ran pytest before and after |
| 25    | Systematic verification: test baseline before coding, CLI help check, flag parse test, regression check, all passing |

**Key checks:**
- Evidence in workspace that agent ran `uv run pytest` (look for test output in agent logs)
- Evidence agent checked `nasde run --help` after adding flag
- No pre-existing tests broken by the change
- Agent wrote new tests for the feature (bonus, not required for pass)

## 2. Code Conventions (0-25)

| Score | Criteria |
|-------|----------|
| 0     | Code doesn't follow project patterns at all |
| 8     | Basic implementation works but ignores project conventions |
| 15    | Follows some conventions — Typer option exists, reasonable style |
| 20    | Clean adherence: lazy imports for heavy deps, Typer Optional+None pattern, Rich console, keyword args with defaults |
| 25    | Perfect: indistinguishable from existing code style, including import ordering, parameter naming, error message formatting |

**Key checks:**
- Harbor/Opik/SDK imports are inside functions, not at module level
- Typer option uses `Optional[int]` with `None` default or `int` with `1` default (matches existing flag patterns)
- No bare `print()` — all output via `console.print()` with Rich markup
- `run_benchmark()` and `_build_merged_config()` parameter style matches existing functions

## 3. Architecture Quality (0-25)

| Score | Criteria |
|-------|----------|
| 0     | Only basic flag added, no architectural consideration |
| 8     | n_attempts propagated but no job naming or job_dir improvements |
| 13    | Deterministic job naming OR explicit job_dir (one of two) |
| 18    | Both job naming and explicit job_dir present |
| 25    | Job naming + job_dir + DNS fix in ConfigurableClaude (conditional, before super().setup()) |

**Key checks:**
- `job_name` uses `{datetime}__{variant}` or similar deterministic format
- `_run_post_hoc_assessment()` accepts and uses explicit `job_dir` (not latest-job heuristic)
- DNS fix checks resolution before applying (conditional, not always overwriting)
- DNS fix runs before `super().setup()` (order matters for cloud environments)
- n_attempts flows: CLI → run_benchmark() → _build_merged_config() → Harbor dict

## 4. Documentation Completeness (0-25)

| Score | Criteria |
|-------|----------|
| 0     | No documentation changes |
| 8     | CLI header display updated with attempts count |
| 13    | Header updated + CLAUDE.md CLI reference mentions --attempts/-n |
| 18    | Header + CLAUDE.md + README.md CLI options table updated |
| 22    | All three docs + help text is descriptive and consistent with other flags |
| 25    | All docs updated (CLAUDE.md, README.md, header, help text), ARCHITECTURE.md updated if pipeline flow changed |

**Key checks:**
- `_print_run_header()` displays attempts count in the Rich Panel
- `CLAUDE.md` "CLI reference" section includes `--attempts` / `-n` with description
- `README.md` CLI options table includes `--attempts` / `-n`
- Help text for the flag is descriptive (sentence case, matches style of --variant, --model)
- ARCHITECTURE.md updated if the job naming or assessment eval targeting changed the pipeline flow
