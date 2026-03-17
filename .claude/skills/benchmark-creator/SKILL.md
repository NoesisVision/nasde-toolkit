---
name: benchmark-creator
description: |
  Create coding agent benchmarks for evaluation with sdlc-eval. Use this skill when the user wants to:
  - Create a new benchmark project (set of tasks for evaluating coding agents)
  - Add tasks to an existing benchmark
  - Create or modify agent variants (configurations that control agent behavior)
  - Set up assessment dimensions and scoring criteria
  - Verify that a new benchmark's Docker environment and tests work
  Even if the user doesn't say "benchmark" — if they're talking about creating coding challenges for AI agents or setting up evaluation criteria, this skill applies.
---

# Benchmark Creator

Create and configure coding agent benchmarks for evaluation with `sdlc-eval`. A benchmark is a set of coding tasks that AI agents solve inside isolated Docker containers, scored both by functional tests (pass/fail) and by an LLM-as-a-Judge architecture assessment.

## Step 1: Understand what to evaluate

Before creating files, clarify with the user:

- What programming language/framework? (determines Dockerfile base image)
- What kind of coding challenges? (feature implementation, refactoring, bug fixing, etc.)
- What source repository should the agent work on? (git URL cloned in Dockerfile)
- What quality dimensions should be assessed? (these are benchmark-specific, not hardcoded)

## Step 2: Scaffold or create the project

For a new benchmark, run:

```bash
sdlc-eval init my-benchmark --name my-benchmark
```

This creates the base structure. Then customize the generated files.

For adding tasks to an existing benchmark, skip to Step 4.

## Step 3: Define assessment dimensions

Edit `assessment_dimensions.json`. Each benchmark has its OWN dimensions — design them for what matters in this benchmark's domain.

Examples by domain:
- **Refactoring**: `code_clarity`, `test_preservation`, `api_compatibility`, `performance_impact`
- **API integration**: `error_handling`, `api_usage_correctness`, `test_coverage`, `documentation`
- **Security**: `vulnerability_detection`, `fix_correctness`, `regression_safety`, `explanation_quality`
- **DDD**: `domain_modeling`, `architecture_compliance`, `extensibility`, `test_quality`

Rules:
- 3-5 dimensions, scores summing to 100
- Names in snake_case
- Each dimension has: `name`, `title`, `max_score`, `description`

## Step 4: Create task files

Each task lives in `tasks/<task-name>/` and needs these files:

### task.json (required)

```json
{
  "name": "<task-name>",
  "description": "Brief description",
  "difficulty": "intermediate",
  "estimated_time_minutes": 30,
  "tags": ["relevant", "tags"],
  "source": {
    "git": "https://github.com/org/repo.git",
    "ref": "main"
  },
  "environment": {
    "type": "docker",
    "dockerfile": "./environment/Dockerfile"
  },
  "instruction": "./instruction.md",
  "evaluation": {
    "type": "script",
    "script": "./tests/test.sh",
    "timeout_seconds": 300
  },
  "metadata": {
    "language": "C#",
    "framework": ".NET 8",
    "domain": "E-Commerce"
  }
}
```

### instruction.md (required)

Agent-facing task description. Structure it as:

```markdown
# Task: <Name>

## Context
Working environment, codebase location (/app), technology stack.

## Requirement
What the agent must implement/fix/change. Concrete examples with inputs and expected outputs.

## Scope
What's in scope, what's not.

## Quality Expectations
Architecture and code quality expectations.

## Success Criteria
Numbered list matching what test.sh verifies.

## Constraints
What the agent must NOT do (e.g., don't modify existing tests).
```

### environment/Dockerfile (required)

```dockerfile
FROM <base-image>

RUN apt-get update && apt-get install -y git curl wget ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone <repository-url> .

# Pre-install dependencies so the agent doesn't waste time
RUN <dependency-install-command>

# Verify the environment works
RUN <build-or-compile-command>

CMD ["/bin/bash"]
```

The Dockerfile MUST be self-contained — the agent starts working immediately.

### tests/test.sh (required — Harbor verifier)

```bash
#!/bin/bash
cd /app

echo "Step 1: Verifying build..."
if <build-command>; then
    echo "✓ Build succeeded"
else
    echo "✗ Build failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 2: Running tests..."
if <test-command>; then
    echo "✓ Tests pass"
else
    echo "✗ Tests failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "EVALUATION PASSED ✓"
echo 1 > /logs/verifier/reward.txt
exit 0
```

Rules:
- Every failure: `echo 0 > /logs/verifier/reward.txt` + `exit 1`
- Final success: `echo 1 > /logs/verifier/reward.txt` + `exit 0`
- Order steps from fundamental (build) to specific (implementation checks)

### assessment_criteria.md (required for LLM-as-a-Judge evaluation)

Per-task rubric. Structure:

```markdown
# Assessment Criteria: <Task Name>

Evaluate across N dimensions. Each dimension is scored 0–<max_score> points.

## 1. <Dimension Name> (0–<max_score>)

| Score | Criteria |
|-------|----------|
| 0     | <worst case> |
| 12    | <middle case> |
| 25    | <best case> |

**Key checks:**
- Specific things to look for
```

Scores should have at least 5 levels for granularity.

### solution/solve.sh (optional)

Reference solution for verifying test.sh works. Not executed by Harbor.

## Step 5: Create variants

Each variant is a directory under `variants/<variant-name>/`. At minimum it contains `CLAUDE.md` — the instructions injected into the agent's sandbox.

If no `harbor_config.json` exists, `sdlc-eval` auto-generates one. To customize (e.g., add MCP servers), create it explicitly:

```json
{
  "agents": [
    {
      "import_path": "sdlc_eval_kit.agents.configurable_claude:ConfigurableClaude",
      "name": "<variant-name>",
      "kwargs": {
        "sandbox_files": {
          "/app/CLAUDE.md": "/absolute/path/to/variants/<variant>/CLAUDE.md",
          "/logs/agent/sessions/.claude.json": "/absolute/path/to/variants/<variant>/claude_config.json"
        }
      }
    }
  ]
}
```

Critical: `"name"` field is REQUIRED — without it, Opik tagging breaks.

### Variant design patterns

Design variants to test specific hypotheses:
- **Minimal** (baseline) — bare instructions, no extra guidance
- **Guided** — detailed domain-specific guidance, patterns to follow
- **Tool-augmented** — MCP server access (e.g., codebase search)
- **Constrained** — specific restrictions or requirements

Every benchmark needs at least one variant (typically `vanilla` or `baseline`).

## Step 6: Verify the benchmark works

Before running with a real agent:

1. **Build the Docker image:**
   ```bash
   docker build -t benchmark-test -f tasks/<task>/environment/Dockerfile .
   ```

2. **Test the verifier** with reference solution (if available):
   ```bash
   docker run --rm -it benchmark-test bash
   # Inside container:
   bash /path/to/solution/solve.sh
   bash /path/to/tests/test.sh
   cat /logs/verifier/reward.txt  # Should be 1
   ```

3. **Dry run** on a single task:
   ```bash
   sdlc-eval run --variant vanilla --tasks <task-name> --without-eval -C .
   ```
