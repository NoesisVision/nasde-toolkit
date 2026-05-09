---
name: nasde-benchmark-from-public-repos
description: |
  Build diverse benchmark task suites from public GitHub repositories for testing universal skills. Use this skill when the user wants to:
  - Create a benchmark that spans multiple public repositories and languages
  - Test a universal skill (refactoring, test writing, code review, etc.) across diverse codebases
  - Curate a representative set of repos and tasks for cross-codebase validation
  - Build an evaluation suite for a skill that should work in any repository
  Even if the user doesn't say "benchmark" — if they're building a skill meant to work everywhere and want to validate it across many different projects, this skill applies.
---

# NASDE Benchmark from Public Repos

Build a diverse NASDE benchmark by curating tasks from multiple public GitHub repositories. Designed for validating universal skills — skills that should work across different languages, frameworks, project sizes, and architectural styles.

## Prerequisites

- An existing NASDE benchmark project (run `nasde init` first, or use the `nasde-benchmark-creator` skill)
- A clear description of the skill being evaluated (what it does, what kinds of tasks it helps with)
- Internet access (to browse and clone public repositories)

## Critical: line endings on Windows (read this first)

When generating `tests/test.sh`, `solution/solve.sh`, or `environment/Dockerfile` on a Windows host, write them with **LF** line endings or every trial fails with `bash: required file not found` (the kernel reads `#!/bin/bash\r` as the shebang). See the full explanation and `.gitattributes` template in the `nasde-benchmark-creator` skill.

Quick rules:
- The benchmark project MUST have a `.gitattributes` enforcing `*.sh text eol=lf` and `Dockerfile text eol=lf`. `nasde init` creates this. If the existing project lacks it, **create `.gitattributes` before generating any task files**.
- When writing files programmatically, use `path.write_text(content, encoding="utf-8", newline="")` — never the bare default which translates `\n`→`\r\n` on Windows.
- Sanity-check after generation: `find tasks/<new-task> -name '*.sh' -o -name 'Dockerfile' | xargs file | grep CRLF` should print nothing.

## Step 1: Understand the skill under test

Ask the user:

- **What does the skill do?** (e.g., "helps agents refactor code", "guides test writing", "enforces DDD patterns")
- **What languages/frameworks should it support?** (e.g., "Python, TypeScript, and Go" or "any language")
- **What task types exercise the skill?** (e.g., "extract method, rename module, split class" for a refactoring skill)
- **Are there known weak spots?** (e.g., "seems to struggle with large files" or "not sure about Rust")

## Step 2: Design the diversity matrix

Based on the skill description, define axes of variation that the benchmark should cover. Present these to the user as a table:

### Example for a refactoring skill

| Axis | Values to cover | Why it matters |
|------|----------------|---------------|
| **Language** | Python, TypeScript, Go, Rust, C# | Refactoring idioms differ per language |
| **Project size** | Small (<5K LOC), Medium (5-50K), Large (>50K) | Large codebases stress navigation and context |
| **Test coverage** | Extensive tests, Minimal tests, No tests | Refactoring with no safety net is harder |
| **Architecture** | Monolith, Microservice, Library | Different refactoring patterns apply |
| **Difficulty** | Extract function, Split module, Restructure package | Increasing complexity |

Not every cell in the matrix needs a task. Aim for **8–15 tasks** that provide meaningful coverage across the axes. Ask the user which axes matter most — they may want to emphasize language diversity over project size, or vice versa.

## Step 3: Find candidate repositories

For each cell in the matrix that needs coverage, search for public repositories that fit.

**Good source repositories have:**
- A clear, active codebase (not abandoned, not a tutorial/toy project)
- A working build system and some test infrastructure
- A well-understood structure (README, organized directories)
- A permissive license (MIT, Apache 2.0, BSD — avoid GPL if the benchmark may be shared)
- Enough complexity to be a meaningful test (not a single-file script)

**Search strategies:**
1. **GitHub search** — search by language, stars, topic tags
2. **Known ecosystem repos** — well-known open source projects in each language (e.g., FastAPI for Python, Express for Node, Gin for Go)
3. **GitHub Trending** — find actively maintained repos with good structure
4. **User suggestions** — the user may know repos that represent their target audience

For each candidate repo, present:

```
[1] github.com/user/repo — "Description from GitHub"
    Language: Python | Size: ~15K LOC | Stars: 2.3K | License: MIT
    Tests: pytest suite, good coverage
    Why: Medium Python project, clean architecture, good refactoring target
    Proposed task: "Extract the database access layer into a repository pattern"

[2] github.com/user/repo2 — "Description from GitHub"
    Language: TypeScript | Size: ~40K LOC | Stars: 890 | License: Apache 2.0
    Tests: Jest, moderate coverage
    Why: Large TS project, component-heavy, tests UI refactoring
    Proposed task: "Split the UserDashboard component into focused sub-components"
```

Ask the user to select which repos and tasks to include.

## Step 4: Create tasks for each selected repo

For each approved repo+task pair, generate the full task directory. Work through each file with the user.

### 4a: Determine the "before" state

Unlike `nasde-benchmark-from-history` (which uses a specific commit), here you choose a state of the repo that presents the problem to solve:

- **Option A: Current main branch** — the repo as-is has the problem (e.g., a God class that should be split). Set `source.ref` to a specific commit hash on main for reproducibility.
- **Option B: A tagged release** — use a specific version. More stable for long-lived benchmarks.
- **Option C: Create a setup branch** — if the task requires introducing a specific problem into a clean codebase, create a branch that sets up the scenario. Push it to a fork or document the setup in the Dockerfile.

Always pin to a specific commit hash, not a branch name — branches move, hashes don't.

### 4b: task.toml (single task config, shared with Harbor)

```toml
version = "1.0"

[task]
name = "<benchmark-name>/<language>-<repo-slug>-<task-slug>"   # Harbor requires org/name format
description = "<What the agent must do>"

[metadata]
difficulty = "<easy|intermediate|hard>"
language = "<language>"
framework = "<framework>"
source_repo = "https://github.com/<owner>/<repo>"
diversity_axes = ["<axis:value>", "<axis:value>"]

[agent]
timeout_sec = 1800          # Rule of thumb: estimated_time_minutes × 60

[environment]
memory_mb = 4096            # Claude Code needs 4096+, default 2048 is too low.

[verifier]
timeout_sec = 300

[nasde.source]              # Only needed when task has no environment/Dockerfile (auto-generation).
git = "https://github.com/<owner>/<repo>.git"
ref = "<pinned-commit-hash>"
```

The `[metadata] diversity_axes` helps track coverage across the matrix. Always pin `[nasde.source] ref` to a specific commit hash, not a branch name.

### 4c: instruction.md

Write a task instruction that:
- Describes the codebase context (what the project does, relevant directory structure)
- States the problem clearly (what needs to change and why)
- Defines success criteria the agent can verify
- Does NOT prescribe the implementation approach

```markdown
# Task: <Descriptive name>

## Context
You are working in `/app`, a <language> <framework> project that <brief description>.
The project structure relevant to this task:
<tree of relevant directories/files>

## Requirement
<What needs to change. Describe the problem, not the solution.
Example: "The UserService class handles authentication, authorization, profile management,
and notification dispatch. It's 800 lines and growing. Separate these concerns into
focused services.">

## Scope
- Focus on: <specific files/directories>
- Do NOT modify: <test files, configuration, unrelated modules>
- Preserve: <all existing public APIs, test behavior>

## Quality Expectations
- Follow <language> idioms and the project's existing style
- Maintain or improve test coverage
- Keep changes minimal — change what needs changing, nothing more

## Success Criteria
1. <Specific, testable criterion>
2. <Specific, testable criterion>
3. All existing tests continue to pass
```

**Important for universal skill benchmarks:** Write the instruction as if the agent has no special skill. The skill configuration is injected via the variant's `CLAUDE.md` — the instruction describes the raw problem.

### 4d: environment/Dockerfile

Each repo needs its own Dockerfile. Detect the stack and generate:

```dockerfile
FROM <base-image>

RUN apt-get update && apt-get install -y git curl wget ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/<owner>/<repo>.git . && git checkout <pinned-hash>

# Install dependencies
RUN <dependency-install-command>

# Verify build works at the "before" state
RUN <build-or-compile-command>

CMD ["/bin/bash"]
```

**Test the Dockerfile** before moving on:
```bash
docker build -t benchmark-test-<task-name> -f tasks/<task-name>/environment/Dockerfile .
```

### 4e: tests/test.sh

For public repos, the verifier typically:
1. Verifies the project still builds
2. Runs the existing test suite (all tests must still pass)
3. Checks for task-specific outcomes (new files exist, specific patterns in code, etc.)

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

echo "Step 2: Running existing tests..."
if <test-command>; then
    echo "✓ Existing tests pass"
else
    echo "✗ Existing tests failed — regression detected"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "Step 3: Checking task-specific criteria..."
# Example: verify a specific file was created or a class was split
if <task-specific-check>; then
    echo "✓ Task criteria met"
else
    echo "✗ Task criteria not met"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

echo "EVALUATION PASSED ✓"
echo 1 > /logs/verifier/reward.txt
exit 0
```

Task-specific checks depend on the task type:
- **Refactoring:** check that target files exist, original God class is smaller or removed
- **Test writing:** check that new test files exist and pass
- **Bug fix:** check that a specific test case now passes

### 4f: assessment_criteria.md

Use the benchmark project's `assessment_dimensions.json` and adapt each dimension to this specific task and language:

```markdown
# Assessment Criteria: <Task Name>

Evaluate the agent's solution across the following dimensions.
This task is in <language> using <framework> — apply language-specific standards.

## 1. <Dimension> (0–<max_score>)

| Score | Criteria |
|-------|----------|
| 0     | <worst — specific to this language and task> |
| ...   | ... |
| <max> | <best — specific to this language and task> |

**Key checks:**
- <Language-specific things to look for>
```

**Important:** Assessment criteria should reflect language idioms. "Good refactoring" looks different in Rust (ownership, lifetimes) vs Python (duck typing, protocols) vs Go (interfaces, embedding).

## Step 5: Review coverage

After all tasks are created, present the filled diversity matrix to the user:

```
Coverage matrix for "refactoring" skill benchmark:

| Language   | Small | Medium | Large |
|------------|-------|--------|-------|
| Python     |       | ✓ fastapi-extract | |
| TypeScript |       | | ✓ dashboard-split |
| Go         | ✓ cli-service-layer | | |
| Rust       | ✓ error-handling | | |
| C#         |       | ✓ ddd-aggregate | |

Gaps: No large Python project, no small TypeScript project.
```

Ask the user if they want to fill gaps or if current coverage is sufficient.

## Step 6: Verify the benchmark

1. **Build all Docker images** — every task must build successfully
2. **Run existing test suites** in each container — they must pass at the "before" state
3. **Dry run** on one or two tasks:
   ```bash
   nasde run --variant <skill-variant> --tasks <task-name> --without-eval -C <benchmark-dir>
   ```

## Tips

- **Pin commit hashes, not branches.** Branches move. A benchmark task that worked yesterday might break tomorrow if main advanced. Always use the full 40-char hash.
- **Diverse doesn't mean random.** Each task should test a different aspect of the skill. If three tasks all test "extract method in Python," replace two with different languages or problem types.
- **Test the Dockerfiles early.** The most common failure is a Dockerfile that doesn't build because a dependency changed or a repo restructured. Build images as you create tasks, not all at the end.
- **Keep instructions skill-agnostic.** The task instruction describes the problem. The skill is injected via the variant's `CLAUDE.md`. This separation lets you test the same tasks with and without the skill.
- **Start with 5–8 tasks.** You can always add more. A smaller, well-curated benchmark is better than a large, noisy one.
- **Combine with nasde-benchmark-creator.** This skill generates tasks from public repos; `nasde-benchmark-creator` handles project scaffold, dimensions, and variants. Use them together.
