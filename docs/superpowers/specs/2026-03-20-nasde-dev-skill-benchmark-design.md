# Design: nasde-dev-skill Benchmark

Self-testing benchmark for nasde-toolkit that measures whether the `nasde-dev` skill improves agent effectiveness when developing nasde-toolkit itself.

## Prerequisites

### 1. Refocus nasde-dev skill as domain-only (before creating benchmark)

nasde-dev must be purely domain-specific — no generic Python conventions. Generic Python quality is handled by external skills (python-testing, python-best-practices) composed in separate variants.

nasde-dev covers ONLY:
- **Pre-change analysis** — dependency chain mapping, test baseline, CLI alias collision check
- **Nasde-specific rules** — lazy imports for harbor/opik/sdk, `@dataclass` modification protocol, Rich console output
- **Monkeypatch awareness** — evaluator.py SDK patch, CLAUDECODE env var, opik patch
- **Verification protocol** — pytest, CLI help verification, documentation sync table, e2e benchmark run

This separation enables clean variant combinations that measure the value of each skill layer independently.

### 2. Fix source.git integration (before creating benchmark)

`docker.py:generate_dockerfile()` exists but is never called — `source.git` in task.json is dead metadata. Fix this so the benchmark can use `source.git: "../.."` without a custom Dockerfile.

Implementation:
1. In the runner pipeline (before Harbor job launch), check if `tasks/<name>/environment/Dockerfile` exists
2. If missing, call `docker.py:generate_dockerfile(source, docker)` and write to a generated location
3. For local paths (`source.git` not starting with `http`/`https`/`git`): resolve to absolute path, set Docker build context to the repo root, use `COPY . /app` + `git checkout {ref}` instead of `git clone`
4. Pass the generated Dockerfile path to Harbor

This unblocks the benchmark's main goal: demonstrating local-repo workflow without custom Dockerfile.

## Task

**Source commit:** `812b189` — "Add multi-attempt support (--attempts/-n) and cloud DNS fix"
**Before state:** `7e1a804` (parent commit)

The agent starts from the codebase at `7e1a804` and must implement multi-attempt support:

1. Add `--attempts` / `-n` CLI flag to `nasde run` (cli.py)
2. Propagate `n_attempts` parameter through `run_benchmark()` and `_build_merged_config()` (runner.py)
3. Generate a deterministic `job_name` with timestamp + variant name
4. Pass explicit `job_dir` to post-hoc assessment instead of relying on `_find_latest_job()`
5. Add DNS resolution fix for cloud sandboxes in `ConfigurableClaude` (configurable_claude.py)
6. Update CLI header display to show attempts count

## Project structure

```
examples/nasde-dev-skill/
  .gitignore                    # jobs/
  nasde.toml
  assessment_dimensions.json
  tasks/
    add-multi-attempt-support/
      task.json
      task.toml
      instruction.md
      assessment_criteria.md
      tests/test.sh
      solution/solve.sh
  variants/
    vanilla/
      CLAUDE.md
    nasde-dev-with-arch/                  # domain + code architecture
      CLAUDE.md
      skills/
        nasde-dev/SKILL.md                # domain knowledge (nasde-specific)
        python-best-practices/SKILL.md    # type-first, dataclasses, error handling, module structure
    nasde-dev-with-testing/               # domain + testing methodology
      CLAUDE.md
      skills/
        nasde-dev/SKILL.md
        python-testing/SKILL.md           # pytest, TDD, fixtures, mocking, async testing
    nasde-dev-full-stack/                 # domain + architecture + testing
      CLAUDE.md
      skills/
        nasde-dev/SKILL.md
        python-best-practices/SKILL.md
        python-testing/SKILL.md
```

This structure showcases nasde's variant system: same task, different skill combinations, measurable impact. Users see how to compose domain-specific + generic skills in their own benchmarks.

No `environment/Dockerfile` — uses auto-generated Dockerfile from `source.git: "../.."` (the source.git fix above).

## nasde.toml

```toml
[project]
name = "nasde-dev-skill"
version = "1.0.0"

[defaults]
variant = "vanilla"
model = "claude-sonnet-4-6"
timeout_sec = 1800

[docker]
base_image = "python:3.12-slim"
build_commands = [
  "pip install uv",
  "uv sync",
  "nasde --version",
]

[evaluation]
model = "claude-sonnet-4-6"
dimensions_file = "assessment_dimensions.json"

[reporting]
platform = "opik"
project_name = "nasde-dev-skill"
```

## assessment_dimensions.json

```json
{
  "dimensions": [
    {
      "name": "verification_discipline",
      "title": "Verification Discipline",
      "max_score": 25,
      "description": "Agent ran tests before and after changes, verified CLI help output, checked that flag parses correctly, did not leave regressions. Evidence of systematic verification in the workspace."
    },
    {
      "name": "code_conventions",
      "title": "Code Conventions",
      "max_score": 25,
      "description": "Lazy imports for heavy deps (harbor/opik/sdk inside functions), Typer option patterns match existing style (Optional with None default), Rich console output (no bare print), error handling follows project patterns."
    },
    {
      "name": "architecture_quality",
      "title": "Architecture Quality",
      "max_score": 25,
      "description": "Deterministic job naming with timestamp+variant, explicit job_dir passed to assessment eval instead of latest-job heuristic, DNS resolution fix conditional and before super().setup(), n_attempts propagated through full chain."
    },
    {
      "name": "documentation_completeness",
      "title": "Documentation Completeness",
      "max_score": 25,
      "description": "CLAUDE.md CLI reference updated with --attempts flag, README.md CLI options table updated, help text is clear and descriptive, header display shows attempts count, ARCHITECTURE.md updated if pipeline flow changed."
    }
  ]
}
```

Dimensions are designed to differentiate skill value:
- **verification_discipline** — nasde-dev mandates "run pytest before coding" and "verify --help output"; python-testing adds TDD methodology
- **code_conventions** — nasde-dev knows lazy import rule; python-best-practices knows type-first and dataclass patterns
- **architecture_quality** — nasde-dev knows the module dependency chain; python-best-practices knows module structure principles
- **documentation_completeness** — nasde-dev has the doc sync table with section-level specifics

## task.json

```json
{
  "name": "add-multi-attempt-support",
  "description": "Add --attempts/-n CLI flag for multiple independent trial attempts per task, with deterministic job naming and cloud DNS fix",
  "difficulty": "intermediate",
  "estimated_time_minutes": 30,
  "tags": ["python", "cli", "typer", "async", "harbor-integration"],
  "source": {
    "git": "../..",
    "ref": "7e1a804"
  },
  "instruction": "./instruction.md",
  "evaluation": {
    "type": "script",
    "script": "./tests/test.sh",
    "timeout_seconds": 300
  },
  "metadata": {
    "language": "Python",
    "framework": "Typer + Harbor",
    "source_commit": "812b189"
  }
}
```

No `environment` block — nasde auto-generates Dockerfile from `source.git` + `[docker]` config in nasde.toml.

## task.toml

```toml
version = "1.0"

[metadata]
name = "add-multi-attempt-support"
description = "Add --attempts/-n flag for multiple independent trial attempts per task"
difficulty = "intermediate"
language = "Python"
framework = "Typer + Harbor"

[agent]
timeout_sec = 1800

[verifier]
timeout_sec = 300
```

## instruction.md

```markdown
# Task: Add Multi-Attempt Support to nasde CLI

## Context

You are working in `/app`, a Python toolkit called `nasde-toolkit` (Noesis Agentic Software Development Evals). The CLI entry point is `nasde`, built with Typer. The main command `nasde run` executes benchmark tasks via the Harbor evaluation framework.

Key files:
- `src/nasde_toolkit/cli.py` — Typer CLI definitions
- `src/nasde_toolkit/runner.py` — Harbor job execution and config merging
- `src/nasde_toolkit/agents/configurable_claude.py` — Custom Harbor agent with sandbox file injection

Read `CLAUDE.md` in the project root for architecture details.

## Requirement

Currently `nasde run` executes each task exactly once. Users need to run multiple independent attempts per task to measure variance in agent performance (e.g., `nasde run -n 3` runs 3 independent trials per task).

Implement:

1. **CLI flag**: Add `--attempts` / `-n` option to `nasde run` (integer, default 1)
2. **Runner propagation**: Pass the attempts count through `run_benchmark()` into the Harbor `JobConfig` as `n_attempts`
3. **Deterministic job naming**: Generate a predictable job directory name using the format `{YYYY-MM-DD__%H-%M-%S}__{variant_name}` so that multiple runs don't collide and are easy to identify
4. **Explicit job directory**: After the Harbor job completes, pass the specific job directory to post-hoc assessment evaluation instead of relying on the "find latest job" heuristic (which breaks when multiple jobs run close together)
5. **Cloud DNS fix**: Cloud sandbox providers (like Daytona) sometimes have DNS resolvers that cannot reach whitelisted domains. Add a DNS resolution fix to `ConfigurableClaude.setup()` that prepends public DNS resolvers (e.g., 8.8.8.8, 1.1.1.1) to `/etc/resolv.conf` if the default resolver fails to resolve `claude.ai`
6. **Display**: Update the CLI header panel to show the attempts count

## Scope

- Modify: `cli.py`, `runner.py`, `configurable_claude.py`
- Do NOT modify: `config.py`, `evaluator.py`, `docker.py`, test files
- Do NOT change existing CLI flags or their defaults

## Quality Expectations

- Follow the existing Typer option patterns in `cli.py` (see `--variant`, `--model`, etc.)
- Match the runner's function signature style (keyword arguments with defaults)
- The DNS fix should be conditional — only apply if default DNS fails
- Keep changes minimal and focused

## Success Criteria

1. `nasde run --help` shows `--attempts` / `-n` flag with help text
2. Running with `-n 2` would create a Harbor job with `n_attempts: 2` in the config
3. Job directory name follows `{timestamp}__{variant}` format
4. Assessment evaluation targets the specific job directory, not "latest"
5. `ConfigurableClaude` has DNS fix that runs before base setup
6. CLI header panel displays the attempts count
```

## assessment_criteria.md

```markdown
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
```

## tests/test.sh

```bash
#!/bin/bash

echo "=========================================="
echo "Multi-Attempt Support - Evaluation"
echo "=========================================="
echo ""

cd /app

echo "Step 1: CLI flag exists with correct help text..."
echo "--------------------------------------"
HELP_OUTPUT=$(nasde run --help 2>&1)
if echo "$HELP_OUTPUT" | grep -q "\-\-attempts" && echo "$HELP_OUTPUT" | grep -q "\-n"; then
    echo "OK: --attempts and -n flags found in CLI help"
else
    echo "FAIL: --attempts/-n flag not found in nasde run --help"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if echo "$HELP_OUTPUT" | grep -qi "attempt\|independent.*per task\|number.*attempt"; then
    echo "OK: Help text is descriptive"
else
    echo "FAIL: Help text missing or not descriptive for --attempts"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 2: CLI flag actually parses..."
echo "--------------------------------------"
if nasde run --attempts 3 --help >/dev/null 2>&1; then
    echo "OK: --attempts 3 parses without error"
else
    echo "FAIL: --attempts flag does not parse correctly"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if nasde run -n 2 --help >/dev/null 2>&1; then
    echo "OK: -n 2 short alias parses without error"
else
    echo "FAIL: -n short alias does not parse correctly"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 3: Running Python tests..."
echo "--------------------------------------"
TEST_OUTPUT=$(uv run pytest -x -q 2>&1)
TEST_EXIT=$?
echo "$TEST_OUTPUT"
echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "OK: All tests pass"
else
    echo "FAIL: Unit tests failed (exit code $TEST_EXIT)"
    echo "Review test output above for details"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 4: run_benchmark accepts n_attempts parameter..."
echo "--------------------------------------"
if python -c "
import inspect
from nasde_toolkit.runner import run_benchmark
sig = inspect.signature(run_benchmark)
assert 'n_attempts' in sig.parameters, f'n_attempts not in signature: {list(sig.parameters.keys())}'
param = sig.parameters['n_attempts']
assert param.default == 1, f'Default should be 1, got {param.default}'
print('run_benchmark(n_attempts=1) signature OK')
"; then
    echo "OK: run_benchmark accepts n_attempts with default=1"
else
    echo "FAIL: run_benchmark does not accept n_attempts parameter"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 5: ConfigurableClaude imports correctly..."
echo "--------------------------------------"
if python -c "
from nasde_toolkit.agents.configurable_claude import ConfigurableClaude
print(f'ConfigurableClaude loaded: {ConfigurableClaude.name()}')
"; then
    echo "OK: ConfigurableClaude imports successfully"
else
    echo "FAIL: ConfigurableClaude import failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "Step 6: Documentation updated (CLAUDE.md and README.md)..."
echo "--------------------------------------"
if grep -q "\-\-attempts" CLAUDE.md 2>/dev/null; then
    echo "OK: CLAUDE.md mentions --attempts"
else
    echo "FAIL: CLAUDE.md does not mention --attempts flag"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if grep -q "\-\-attempts" README.md 2>/dev/null; then
    echo "OK: README.md mentions --attempts"
else
    echo "FAIL: README.md does not mention --attempts flag"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
echo ""

echo "=========================================="
echo "EVALUATION PASSED"
echo "=========================================="
echo 1 > /logs/verifier/reward.txt
exit 0
```

## solution/solve.sh

```bash
#!/bin/bash
cd /app
git cherry-pick 812b189 --no-commit
```

## Variants

All skill variants share the same CLAUDE.md (below). They differ only in which skills are injected.

### Shared CLAUDE.md (all non-vanilla variants)

```markdown
# Agent Instructions

## Approach

1. Before writing any code, explore the existing codebase to understand its architecture and conventions.
2. Follow existing architectural patterns exactly — match naming, namespaces, directory structure, and code style.
3. Read CLAUDE.md in the project root for full architecture documentation.
4. After making changes, verify documentation is consistent (CLAUDE.md, README.md, ARCHITECTURE.md).
```

### vanilla/CLAUDE.md

```markdown
# Agent Instructions

You are a coding assistant. Work in /app.

1. Follow existing patterns in the codebase.
2. Read CLAUDE.md for project context.
```

### Variant skill composition

| Variant | Skills | What it tests |
|---|---|---|
| `vanilla` | none | Baseline — raw agent capability |
| `nasde-dev-with-arch` | nasde-dev + python-best-practices | Domain knowledge + code architecture (type-first, dataclasses, error handling, module structure) |
| `nasde-dev-with-testing` | nasde-dev + python-testing | Domain knowledge + testing methodology (pytest, TDD, fixtures, mocking, async testing) |
| `nasde-dev-full-stack` | nasde-dev + python-best-practices + python-testing | All three — domain + architecture + testing |

### Hypotheses to measure

- **vanilla vs any** → baseline value of skills
- **nasde-dev-with-arch vs nasde-dev-with-testing** → architecture knowledge vs testing methodology — which matters more for this task?
- **nasde-dev-full-stack vs 2-skill variants** → does the third skill add value or cause diminishing returns / context noise?

### Skill sources

| Skill | Source | Installs | What it provides |
|---|---|---|---|
| `nasde-dev` | `.claude/skills/nasde-dev/SKILL.md` (this repo) | — | Domain-only: module dependency chain, dataclass protocol, lazy imports, monkeypatch awareness, verification protocol with doc sync table |
| `python-best-practices` | `0xbigboss/claude-code@python-best-practices` (skills.sh) | 802 | Type-first development, frozen dataclasses, discriminated unions, Protocol, module structure (<300 lines), error handling with `from err`, Config.from_env() |
| `python-testing` | `affaan-m/everything-claude-code@python-testing` (skills.sh) | 1.6K | TDD (red-green-refactor), pytest fixtures (scopes, conftest), parametrize, mocking (@patch, autospec), async testing (pytest-asyncio), 80%+ coverage target |

Skills are snapshots (frozen at benchmark creation time) to ensure deterministic evaluation across runs.

## Key design decisions

1. **First local-repo benchmark example:** This is the primary goal. Users need a working pattern for building benchmarks from local/private repositories — not just from public GitHub URLs. `source.git: "../.."` demonstrates this flow. All existing examples use public GitHub repos; this fills a critical documentation gap.

2. **No custom Dockerfile:** Uses auto-generated Dockerfile from `source.git: "../.."` + `[docker]` in nasde.toml. This requires the source.git integration fix (see Prerequisites). The benchmark is an integration test for that fix.

3. **No Harbor execution in tests:** test.sh validates structure and imports only. Running Harbor would require DinD which adds complexity without proportional value.

4. **DNS fix included in scope:** The commit includes a DNS fix in `configurable_claude.py`. This is harder to discover without the skill's structural knowledge of the agents/ directory.

5. **Deterministic job naming as architecture test:** Tests whether the agent understands why explicit naming matters (Opik tagging, assessment eval targeting the right job).

## End-to-end verification protocol

After implementation, run the full verification to confirm the benchmark works:

### 1. Single-task dry run (no eval, no Opik)

```bash
nasde run --variant vanilla --tasks add-multi-attempt-support --without-eval \
  -C examples/nasde-dev-skill
```

Verify:
- Docker image builds successfully from local repo (source.git integration works)
- Harbor trial completes
- `/logs/verifier/reward.txt` contains `1`

### 2. Full run with assessment evaluation

```bash
source scripts/export_oauth_token.sh
nasde run --variant vanilla --tasks add-multi-attempt-support \
  -C examples/nasde-dev-skill
```

Verify:
- Assessment evaluation produces scores for all 4 dimensions
- `assessment_eval.json` exists in the trial directory
- Scores are reasonable (reference solution should score near-max)

### 3. Full run with Opik tracing

```bash
nasde run --variant vanilla --tasks add-multi-attempt-support \
  --with-opik -C examples/nasde-dev-skill
```

Verify via Opik REST API:
```bash
source .env
python3 -c "
import urllib.request, json
req = urllib.request.Request(
    'https://www.comet.com/opik/api/v1/private/traces?project_name=nasde-dev-skill&limit=1',
    headers={
        'authorization': '$OPIK_API_KEY',
        'Comet-Workspace': '$OPIK_WORKSPACE',
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
trace = resp['content'][0]
scores = trace.get('feedback_scores', [])
print(f'Feedback scores ({len(scores)}):')
for s in sorted(scores, key=lambda x: x['name']):
    print(f'  {s[\"name\"]}: {s[\"value\"]}')
"
```

Expected: `arch_*` scores for each dimension, `arch_total`, `reward`, `duration_sec`.

### 4. All-variant comparison

Run all 4 variants:

```bash
source scripts/export_oauth_token.sh
for variant in vanilla nasde-dev-with-arch nasde-dev-with-testing nasde-dev-full-stack; do
  nasde run --variant $variant --tasks add-multi-attempt-support \
    --with-opik -C examples/nasde-dev-skill
done
```

Compare scores across dimensions in Opik:
- `verification_discipline` — expect nasde-dev-with-testing and full-stack to score highest (python-testing teaches TDD)
- `code_conventions` — expect nasde-dev-with-arch and full-stack to score highest (python-best-practices teaches type-first + module patterns)
- `documentation_completeness` — expect all nasde-dev variants to beat vanilla (nasde-dev has the doc sync table)
- `architecture_quality` — expect nasde-dev variants to beat vanilla (nasde-dev knows the module dependency chain)

### 5. Critical log analysis

After each run, inspect:
- **Harbor trial log** — errors, warnings, agent timeout
- **Docker build output** — source.git / local path handling (verify the fix works)
- **Assessment evaluator log** — dimension scoring rationale (verify the LLM judge differentiates variants)
- **Agent transcript** — did the agent actually use the skills? (look for evidence of running pytest, checking --help, updating docs)
- **test.sh output** — all 6 steps must pass; check for edge cases in CLI help parsing and doc grep

## Documentation updates (part of implementation)

This work includes updating nasde-toolkit documentation:

1. **CLAUDE.md** — Add `source.git` with local path to task.json format docs. Add note that `environment/Dockerfile` is optional when `source.git` + `[docker]` config are sufficient.
2. **README.md** — Add "Local repo benchmarks" example showing how to build a benchmark from a private/local repository.
3. **ARCHITECTURE.md** — Update Docker environment diagram if the source.git auto-generation flow changes the pipeline.
