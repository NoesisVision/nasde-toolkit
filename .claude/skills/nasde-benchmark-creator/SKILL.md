---
name: nasde-benchmark-creator
description: |
  Create coding agent benchmarks for evaluation with nasde. Use this skill when the user wants to:
  - Create a new benchmark project (set of tasks for evaluating coding agents)
  - Add tasks to an existing benchmark
  - Create or modify agent variants (configurations that control agent behavior)
  - Set up assessment dimensions and scoring criteria
  - Verify that a new benchmark's Docker environment and tests work
  Even if the user doesn't say "benchmark" — if they're talking about creating coding challenges for AI agents or setting up evaluation criteria, this skill applies.
---

# NASDE Benchmark Creator

Create and configure coding agent benchmarks for evaluation with `nasde`. A benchmark is a set of coding tasks that AI agents solve inside isolated Docker containers, scored both by functional tests (pass/fail) and by an LLM-as-a-Judge architecture assessment.

## Critical: line endings on Windows (read this first)

Benchmark scripts execute inside **Linux** sandboxes (Docker, Daytona). If `tests/test.sh`, `solution/solve.sh`, or `environment/Dockerfile` are checked out with **CRLF** line endings (the Windows git default when `core.autocrlf=true` and there is no `.gitattributes`), every trial fails immediately with:

```
bash: line 1: /tests/test.sh: cannot execute: required file not found
```

…because the kernel reads the shebang as `#!/bin/bash\r` and tries to execute a non-existent `/bin/bash\r`. The agent finishes its work, but the verifier never runs and Harbor reports `RewardFileNotFoundError`.

**Mitigation (always do this for a new benchmark — `nasde init` does it for you, but verify):**

1. The benchmark repo MUST have a `.gitattributes` file enforcing LF for shell scripts and Dockerfiles. The minimum content:
   ```gitattributes
   * text=auto eol=lf
   *.sh        text eol=lf
   *.bash      text eol=lf
   Dockerfile  text eol=lf
   *.dockerfile text eol=lf
   docker-compose.yaml text eol=lf
   docker-compose.yml  text eol=lf

   *.ps1       text eol=crlf
   *.bat       text eol=crlf
   *.cmd       text eol=crlf
   ```
   `nasde init` writes this automatically. If you are adding a benchmark to an existing repo without `.gitattributes`, create one before adding any task.

2. When **writing** `.sh` or `Dockerfile` content programmatically on Windows, write with explicit LF — not `path.write_text(content)` (which translates `\n`→`\r\n` on Windows), but `path.write_text(content, encoding="utf-8", newline="")` or open the file in binary mode.

3. After committing on Windows for the first time, run:
   ```bash
   git add --renormalize .
   git commit -m "normalize line endings"
   ```
   to fix any files that landed before `.gitattributes` was in place.

4. Sanity check before pushing a new task:
   ```bash
   file tasks/<task>/tests/test.sh
   # MUST say "with LF line terminators" or omit line-terminator info entirely.
   # If it says "with CRLF line terminators" — fix it (`sed -i 's/\r$//' file`).
   ```

This applies equally when you're **adding tasks to a benchmark someone else created** — if their repo has no `.gitattributes` and you're on Windows, your contribution will silently break for them on Linux CI and vice versa.

## Step 1: Understand what to evaluate

Before creating files, clarify with the user:

- What programming language/framework? (determines Dockerfile base image)
- What kind of coding challenges? (feature implementation, refactoring, bug fixing, etc.)
- What source repository should the agent work on? (git URL cloned in Dockerfile)
- What quality dimensions should be assessed? (these are benchmark-specific, not hardcoded)

## Step 2: Scaffold or create the project

For a new benchmark, run:

```bash
nasde init my-benchmark --name my-benchmark
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
- Pick whatever number of dimensions actually captures the quality you care about — there is no required minimum or maximum.
- Each dimension declares its own `max_score` (any positive integer). Scales are independent — a coarse pass/fail-ish dimension can be 0–3 while a richly graded one can be 0–50 in the same rubric. There is no requirement for the total to sum to 100. `normalized_score` is computed automatically from the actual sum of `max_score` values. See ADR-008.
- Names in snake_case
- Each dimension has: `name`, `title`, `max_score`, `description`

## Step 4: Create task files

Each task lives in `tasks/<task-name>/` and needs these files:

### task.toml (required — single task config)

Single config file per task, shared with Harbor. nasde-specific fields live under `[nasde.*]`.

```toml
version = "1.0"

[task]
name = "<benchmark-name>/<task-name>"   # Harbor requires org/name format
description = "Brief description"

[metadata]
difficulty = "intermediate"
language = "C#"
framework = ".NET 8"
domain = "E-Commerce"

[agent]
timeout_sec = 1800          # Primary agent timeout. Rule of thumb: estimated_time_minutes × 60.

[environment]
memory_mb = 4096            # Container memory limit. Claude Code needs 4096+, default 2048 is too low.

[verifier]
timeout_sec = 300           # Timeout for tests/test.sh.

[nasde.source]              # Only needed when task has no environment/Dockerfile (nasde auto-generates one).
git = "https://github.com/org/repo.git"
ref = "main"
```

**Timeout priority**: `--timeout` CLI flag > task.toml `[agent] timeout_sec` > Harbor default. Timeouts are per-task — there is no project-wide default in nasde.toml.

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

> **Reminder for Windows authors:** the Dockerfile and any helper scripts it `COPY`s in must have LF line endings — Docker tolerates CRLF in some commands but not in `RUN` shell snippets, and any shell script copied with CRLF will hit the same shebang failure as `test.sh`.

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

> **Reminder for Windows authors:** this file MUST be saved with LF line endings. See "Critical: line endings on Windows" at the top of this skill. CRLF here = `bash: required file not found` and a wasted trial.

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

Evaluate across N dimensions. Each dimension uses its own scale (0–`max_score`),
defined in `assessment_dimensions.json`. The ladder below shows what each score
means for one specific dimension — repeat for each dimension.

## 1. <Dimension Name> (0–<max_score>)

| Score | Criteria |
|-------|----------|
| 0           | <worst case> |
| <middle>    | <middle case> |
| <max_score> | <best case> |

**Key checks:**
- Specific things to look for
```

Pick a `max_score` that matches the granularity you can actually distinguish.
A coarse pass/fail-ish dimension might be 0–3; a richly graded one might be 0–50.
Choose the resolution per dimension, independently.

### solution/solve.sh (optional)

Reference solution for verifying test.sh works. Not executed by Harbor.

## Step 5: Create variants

Each variant is a directory under `variants/<variant-name>/` with a required `variant.toml` declaring the agent type.

### variant.toml (required)

```toml
agent = "claude"   # or "codex" or "gemini"
```

For Codex variants, **always** set the model explicitly to avoid inheriting the Claude model from `nasde.toml`:

```toml
agent = "codex"
model = "gpt-5.3-codex"   # Required for Codex — use an OpenAI model ID
```

**Codex models** (recommended first, as of 2026-03):
- `gpt-5.4` — flagship frontier model, best overall for professional work
- `gpt-5.4-mini` — fast, efficient mini model for responsive coding and subagents
- `gpt-5.3-codex` — industry-leading coding model for complex software engineering
- `gpt-5.3-codex-spark` — near-instant real-time coding iteration (ChatGPT Pro only)
- Older: `gpt-5.2-codex`, `gpt-5.1-codex`, `gpt-5-codex`, `gpt-5-codex-mini`

Without `model` in variant.toml, Codex inherits `nasde.toml`'s default (e.g. `claude-sonnet-4-6`), which silently produces garbage results.

For Gemini CLI variants, **always** set the model with the `google/` prefix:

```toml
agent = "gemini"
model = "google/gemini-3-flash-preview"   # Required format: google/<model-name>
```

**Gemini models** (recommended first, as of 2026-03):
- `google/gemini-3.1-pro-preview` — advanced thinking model, best for deep reasoning
- `google/gemini-3-flash-preview` — best quality/speed ratio, daily coding tasks
- `google/gemini-3.1-flash-lite-preview` — fastest, simple and repetitive tasks

### Claude Code variant

```
variants/vanilla/
  variant.toml       # agent = "claude"
  CLAUDE.md          # Instructions (injected to /app/CLAUDE.md)
  skills/            # Optional: skill snapshots (injected to /app/.claude/skills/)
```

### Codex variant

```
variants/codex-baseline/
  variant.toml       # agent = "codex"
  AGENTS.md          # Instructions (injected to /app/AGENTS.md)
  agents_skills/     # Optional: skill snapshots (injected to /app/.agents/skills/)
```

### Gemini CLI variant

```
variants/gemini-baseline/
  variant.toml       # agent = "gemini"
  GEMINI.md          # Instructions (injected to /app/GEMINI.md)
  gemini_skills/     # Optional: skill snapshots (injected to /app/.gemini/skills/)
```

If no `harbor_config.json` exists, `nasde` auto-generates one from `variant.toml`. To customize (e.g., add MCP servers), create it explicitly:

```json
{
  "agents": [
    {
      "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
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
- **Skill-augmented** — skills injected for domain expertise (e.g., tactical DDD)
- **Tool-augmented** — MCP server access (e.g., codebase search)
- **Cross-agent** — same instructions for Claude, Codex, and Gemini to compare agent performance

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
   nasde run --variant vanilla --tasks <task-name> --without-eval -C .
   ```

4. **Final pre-flight on Windows authors** — verify no CRLF leaked in:
   ```bash
   find tasks -name '*.sh' -exec sh -c 'file "$1" | grep -q CRLF && echo "BAD: $1"' _ {} \;
   find tasks -name 'Dockerfile' -exec sh -c 'file "$1" | grep -q CRLF && echo "BAD: $1"' _ {} \;
   # Both should print nothing.
   ```
   If anything prints, fix with `sed -i 's/\r$//' <file>` and re-commit.
