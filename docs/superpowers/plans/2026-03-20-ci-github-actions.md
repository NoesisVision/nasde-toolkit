# CI Pipeline (GitHub Actions) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a three-layer GitHub Actions CI pipeline: quality gate (lint/type/test), example validation (Docker builds + verifier tests), and dogfooding (nasde run on Gilded Rose, exit code verification).

**Architecture:** Three independent workflow files in `.github/workflows/`. Layer 1 (quality) and Layer 2 (examples) run on every PR and push to main. Layer 3 (dogfooding) runs only on manual trigger (`workflow_dispatch`), verifies exit code 0. Authentication via `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` GitHub secrets. Opik integration in CI deferred until dedicated workspace strategy is established.

**Tech Stack:** GitHub Actions, uv, ruff, mypy, pytest, Docker, nasde CLI

---

### Task 1: Add ruff and mypy configuration to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ruff and mypy to dev dependencies and configure ruff**

Add a `[project.optional-dependencies]` section for dev tools and ruff config:

```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.9",
    "mypy>=1.14",
    "pytest>=8.0",
]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Verify ruff passes on existing code**

Run: `cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles && uv run --extra dev ruff check src/ tests/`
Expected: PASS (fix any issues if found)

- [ ] **Step 3: Verify mypy passes on existing code**

Run: `cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles && uv run --extra dev mypy src/nasde_toolkit/`
Expected: PASS (fix any issues or add targeted `# type: ignore` comments if needed for third-party libs)

- [ ] **Step 4: Verify pytest still passes**

Run: `cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles && uv run --extra dev pytest tests/ -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add ruff, mypy, pytest config to pyproject.toml"
```

---

### Task 2: Create Layer 1 workflow — quality gate

**Files:**
- Create: `.github/workflows/quality-gate.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Quality Gate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: quality-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run ruff check
        run: uv run ruff check src/ tests/

      - name: Run ruff format check
        run: uv run ruff format --check src/ tests/

  typecheck:
    name: Type check (mypy)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run mypy
        run: uv run mypy src/nasde_toolkit/

  test:
    name: Unit tests (pytest)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run tests
        run: uv run pytest tests/ -v --tb=short
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/quality-gate.yml
git commit -m "ci: add quality gate workflow (ruff, mypy, pytest)"
```

---

### Task 3: Create Layer 2 workflow — example validation

This workflow builds Docker images from example benchmarks and runs the verifier (`test.sh`) with any available reference solution (`solve.sh`). It validates that the benchmark infrastructure works without requiring API keys.

**Files:**
- Create: `.github/workflows/example-validation.yml`
- Create: `scripts/validate_example_task.sh`

- [ ] **Step 1: Create the task validation helper script**

This script builds the Docker image for a single task, optionally runs `solve.sh`, then runs `test.sh`:

```bash
#!/bin/bash
set -euo pipefail

TASK_DIR="$1"
TASK_NAME="$(basename "$TASK_DIR")"

echo "=== Validating task: $TASK_NAME ==="

DOCKERFILE="$TASK_DIR/environment/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    echo "SKIP: No Dockerfile found at $DOCKERFILE"
    exit 0
fi

IMAGE_TAG="nasde-ci-${TASK_NAME}"

echo "Building Docker image..."
docker build -t "$IMAGE_TAG" -f "$DOCKERFILE" "$TASK_DIR/environment/"

echo "Starting container..."
CONTAINER_ID=$(docker run -d "$IMAGE_TAG" sleep infinity)
docker exec "$CONTAINER_ID" mkdir -p /logs/verifier

SOLVE_SCRIPT="$TASK_DIR/solution/solve.sh"
if [ -f "$SOLVE_SCRIPT" ]; then
    echo "Running reference solution..."
    docker cp "$SOLVE_SCRIPT" "$CONTAINER_ID:/tmp/solve.sh"
    docker exec "$CONTAINER_ID" chmod +x /tmp/solve.sh
    docker exec "$CONTAINER_ID" /tmp/solve.sh
else
    echo "No solution/solve.sh found — verifying Docker build only"
    echo "PASS: $TASK_NAME (Docker build OK, no solution to verify)"
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
    exit 0
fi

echo "Running verifier (test.sh)..."
TEST_SCRIPT="$TASK_DIR/tests/test.sh"
docker cp "$TEST_SCRIPT" "$CONTAINER_ID:/tmp/test.sh"
docker exec "$CONTAINER_ID" chmod +x /tmp/test.sh

if docker exec "$CONTAINER_ID" /tmp/test.sh; then
    REWARD=$(docker exec "$CONTAINER_ID" cat /logs/verifier/reward.txt 2>/dev/null || echo "missing")
    if [ "$REWARD" = "1" ]; then
        echo "PASS: $TASK_NAME (reward=1)"
    else
        echo "FAIL: $TASK_NAME (reward=$REWARD, expected 1)"
        docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
        exit 1
    fi
else
    echo "FAIL: $TASK_NAME (test.sh exited non-zero)"
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
    exit 1
fi

docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
echo "=== Done: $TASK_NAME ==="
```

- [ ] **Step 2: Make the script executable**

Run: `chmod +x scripts/validate_example_task.sh`

- [ ] **Step 3: Create the workflow file**

```yaml
name: Example Validation

on:
  push:
    branches: [main]
    paths:
      - "examples/**"
      - "src/**"
      - "scripts/validate_example_task.sh"
  pull_request:
    branches: [main]

concurrency:
  group: examples-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate-configs:
    name: Validate benchmark configs
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install nasde-toolkit
        run: uv sync

      - name: Validate refactoring-skill config
        run: |
          uv run python -c "
          from pathlib import Path
          from nasde_toolkit.config import load_project_config
          config = load_project_config(Path('examples/refactoring-skill'))
          assert len(config.tasks) > 0, 'No tasks discovered'
          print(f'OK: {config.name} — {len(config.tasks)} tasks')
          "
        env:
          PYTHONPATH: src

      - name: Validate ddd-architectural-challenges config
        run: |
          uv run python -c "
          from pathlib import Path
          from nasde_toolkit.config import load_project_config
          config = load_project_config(Path('examples/ddd-architectural-challenges'))
          assert len(config.tasks) > 0, 'No tasks discovered'
          print(f'OK: {config.name} — {len(config.tasks)} tasks')
          "
        env:
          PYTHONPATH: src

  validate-docker-tasks:
    name: "Docker: ${{ matrix.task }}"
    runs-on: ubuntu-latest
    needs: validate-configs
    strategy:
      fail-fast: false
      matrix:
        include:
          - example: refactoring-skill
            task: python-gilded-rose-polymorphism
          - example: ddd-architectural-challenges
            task: ddd-threshold-discount
          - example: ddd-architectural-challenges
            task: ddd-weather-discount
    steps:
      - uses: actions/checkout@v4

      - name: Build and validate task
        run: |
          bash scripts/validate_example_task.sh \
            "examples/${{ matrix.example }}/tasks/${{ matrix.task }}"
```

Note: The validation script runs the full verify cycle (solve.sh + test.sh) only for tasks with a `solution/solve.sh`. Tasks without solutions (like Gilded Rose) only verify that the Docker image builds successfully, then exit early.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/example-validation.yml scripts/validate_example_task.sh
git commit -m "ci: add example validation workflow (Docker build + verifier)"
```

---

### Task 4: Create Layer 3 workflow — dogfooding

This workflow runs `nasde run` on the Gilded Rose task from the refactoring-skill example. Triggered only manually via `workflow_dispatch`. Opik integration is deferred until a dedicated CI workspace/project strategy is established (to avoid polluting production experiment data).

**Files:**
- Create: `.github/workflows/dogfooding.yml`

- [ ] **Step 1: Create the dogfooding workflow file**

```yaml
name: Dogfooding

on:
  workflow_dispatch:
    inputs:
      task:
        description: "Task to run (default: python-gilded-rose-polymorphism)"
        required: false
        default: "python-gilded-rose-polymorphism"
      variant:
        description: "Variant to use"
        required: false
        default: "vanilla"
      model:
        description: "Model override"
        required: false
        default: "claude-sonnet-4-6"

jobs:
  dogfood:
    name: "Dogfood: nasde run"
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install nasde-toolkit
        run: uv tool install .

      - name: Run benchmark
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: |
          nasde run \
            --variant "${{ inputs.variant }}" \
            --tasks "${{ inputs.task }}" \
            --model "${{ inputs.model }}" \
            --without-eval \
            -C examples/refactoring-skill

      - name: Upload job artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: dogfood-results-${{ github.run_number }}
          path: examples/refactoring-skill/jobs/
          retention-days: 30
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/dogfooding.yml
git commit -m "ci: add dogfooding workflow (nasde run via workflow_dispatch)"
```

---

### Task 5: Add required GitHub secrets documentation

**Files:**
- Create: `docs/ci-setup.md`

- [ ] **Step 1: Write the CI setup guide**

```markdown
# CI Setup Guide

## GitHub Actions Workflows

nasde-toolkit uses three GitHub Actions workflow layers:

| Workflow | File | Trigger | Secrets needed |
|----------|------|---------|----------------|
| Quality Gate | `quality-gate.yml` | PR + push to main | None |
| Example Validation | `example-validation.yml` | PR + push to main | None |
| Dogfooding | `dogfooding.yml` | Manual (`workflow_dispatch`) | See below |

## Required Secrets (Dogfooding only)

Configure these in GitHub repo Settings > Secrets and variables > Actions:

| Secret | Description | Required |
|--------|-------------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | One of these two |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth token (alternative auth) | One of these two |

Opik integration in CI is deferred until a dedicated CI workspace/project strategy is established.

## Running Dogfooding Manually

1. Go to Actions tab in GitHub
2. Select "Dogfooding" workflow
3. Click "Run workflow"
4. Optionally override task, variant, or model
5. The workflow runs the benchmark and verifies exit code 0
```

- [ ] **Step 2: Commit**

```bash
git add docs/ci-setup.md
git commit -m "docs: add CI setup guide with secrets documentation"
```

---

### Task 6: Fix ruff/mypy issues in existing code (if any)

This task handles any linting or type-checking issues discovered in Task 1.

**Files:**
- Modify: any source files with issues (determined at runtime)

- [ ] **Step 1: Run ruff and fix auto-fixable issues**

Run: `cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles && uv run --extra dev ruff check --fix src/ tests/`

- [ ] **Step 2: Run ruff format**

Run: `cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles && uv run --extra dev ruff format src/ tests/`

- [ ] **Step 3: Fix remaining mypy issues manually**

Review mypy output and fix type annotation issues. Use `# type: ignore[<code>]` only for third-party library issues that cannot be resolved (harbor, opik, claude-code-sdk).

- [ ] **Step 4: Run full test suite to verify nothing broke**

Run: `uv run --extra dev pytest tests/ -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit if any changes were made**

```bash
git add -A
git commit -m "chore: fix ruff/mypy issues in existing code"
```

---

### Task 7: End-to-end local verification

Verify the complete CI setup works locally before pushing.

- [ ] **Step 1: Run quality gate locally**

```bash
cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/.claude/worktrees/gracious-wiles
uv run --extra dev ruff check src/ tests/
uv run --extra dev ruff format --check src/ tests/
uv run --extra dev mypy src/nasde_toolkit/
uv run --extra dev pytest tests/ -v
```
Expected: All pass

- [ ] **Step 2: Run config validation locally**

```bash
uv run python -c "
from pathlib import Path
from nasde_toolkit.config import load_project_config
for example in ['refactoring-skill', 'ddd-architectural-challenges']:
    config = load_project_config(Path(f'examples/{example}'))
    print(f'OK: {config.name} — {len(config.tasks)} tasks')
"
```
Expected: Both examples load successfully

- [ ] **Step 3: Verify Docker validation script syntax**

```bash
bash -n scripts/validate_example_task.sh
```
Expected: No syntax errors

- [ ] **Step 4: Final commit — all CI files**

```bash
git status
```
Expected: Clean working tree (all changes committed in previous tasks)
