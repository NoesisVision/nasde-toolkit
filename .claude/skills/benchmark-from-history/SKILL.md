---
name: benchmark-from-history
description: |
  Generate benchmark tasks from git history of the current or specified repository. Use this skill when the user wants to:
  - Create benchmark tasks based on real problems their team already solved (closed PRs, past commits, resolved issues)
  - Mine git history for good evaluation candidates
  - Turn a commit range or set of PRs into a NASDE benchmark
  - Build a regression test suite from their team's actual work
  Even if the user doesn't say "benchmark" — if they're talking about turning past work into evaluation tasks, or want to test AI agents against problems they've already solved, this skill applies.
---

# Benchmark from Git History

Generate NASDE benchmark tasks by mining git history. You analyze commits, diffs, and PR descriptions to identify self-contained changes that make good evaluation candidates, then generate task files with user approval.

## Prerequisites

- A git repository with meaningful commit history (the repo you're currently in, or a path to another local repo)
- An existing NASDE benchmark project (run `nasde init` first, or use the `benchmark-creator` skill)
- If the benchmark project doesn't exist yet, create it first — this skill generates tasks, not the project scaffold

## Step 1: Identify the source repository and commit range

Ask the user:

- **Which repository?** Default: the current working directory. Can also be a path to another local repo.
- **What commit range?** Options:
  - A branch name (analyze all commits on that branch)
  - A commit range (`abc123..def456`)
  - Last N commits (`HEAD~20..HEAD`)
  - Specific PR numbers (if the repo has a GitHub remote, use `gh pr view`)
  - "Just show me good candidates" — scan the last 50 commits and filter

If the user says "just find good candidates," proceed to Step 2 with the last 50 commits.

## Step 2: Scan commits and identify candidates

For each commit in the range, read the diff and evaluate whether it's a good benchmark candidate.

**Good candidates have:**
- A self-contained change (clear before/after state — one commit or a squashed PR)
- A well-defined problem statement (readable from commit message, PR title, or linked issue)
- Existing tests that can serve as a verifier, OR a change that's testable by inspection
- Reasonable scope — not too trivial (typo fix) and not too large (multi-week refactor)
- A clean "before" state — the parent commit should build and run successfully

**Bad candidates (skip these):**
- Merge commits with no meaningful diff
- Dependency updates, lockfile changes, CI config tweaks
- Changes that span too many unrelated files (shotgun surgery)
- Changes that require external systems not reproducible in Docker (third-party API keys, specific databases with production data)

For each candidate, extract:
- `before_ref`: the parent commit hash (the state the agent will start from)
- `after_ref`: the commit hash (the reference solution)
- `description`: what the change does (from commit message / PR description)
- `files_changed`: list of modified files
- `has_tests`: whether the commit includes test changes
- `estimated_difficulty`: easy / intermediate / hard (based on diff size and complexity)

## Step 3: Present candidates to the user

Present a numbered list of candidates. For each one, show:

```
[1] abc1234 — "Add discount calculation for threshold-based pricing"
    Files: src/Pricing/ThresholdDiscount.cs, tests/Pricing/ThresholdDiscountTests.cs
    Difficulty: intermediate | Has tests: yes
    Before: abc1233 (parent commit)

[2] def5678 — "Fix race condition in order processing pipeline"
    Files: src/Orders/OrderProcessor.cs, src/Orders/OrderLock.cs
    Difficulty: hard | Has tests: yes
    Before: def5677 (parent commit)

[3] ...
```

Ask the user to select which candidates to turn into tasks (comma-separated numbers, or "all").

For each selected candidate, proceed to Step 4.

## Step 4: Generate task files for each selected candidate

For each approved candidate, generate the full task directory structure. Work through each file with the user — present it, get approval or edits, then write it.

### 4a: task.json

Generate from the commit metadata:

```json
{
  "name": "<slugified-commit-description>",
  "description": "<commit message, cleaned up>",
  "difficulty": "<estimated_difficulty>",
  "estimated_time_minutes": 30,
  "tags": ["<language>", "<domain-tags-from-files>"],
  "source": {
    "git": "<repo-url-or-local-path>",
    "ref": "<before_ref>"
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
    "language": "<detected-language>",
    "framework": "<detected-framework>",
    "source_commit": "<after_ref>"
  }
}
```

For `source.git`:
- If the repo has a public remote: use the HTTPS clone URL
- If the repo is local-only (no public remote): use the absolute local path
- Ask the user if unsure

### 4b: instruction.md

Generate from the commit message, PR description (if available via `gh`), and the diff:

```markdown
# Task: <Human-readable task name>

## Context
You are working in a <language/framework> codebase located at `/app`.
<Brief description of the project and the area of code being modified.>

## Requirement
<What the agent must implement/fix/change. Derived from the commit message and diff.
Be specific — describe the expected behavior, not the implementation approach.
Include concrete examples where possible.>

## Scope
- Files likely to be modified: <list based on the actual commit diff>
- Do NOT modify: <files outside the commit's scope, especially tests if they exist>

## Quality Expectations
<Inferred from the codebase style — mention patterns visible in surrounding code.>

## Success Criteria
<Numbered list derived from what the commit actually changed and what tests verify.>
```

**Important:** The instruction must describe the *problem to solve*, not the *solution*. Don't leak implementation details from the actual commit diff into the instruction. The agent should arrive at a solution independently.

Present the generated instruction to the user for review. They may want to:
- Remove implementation hints that leak from the diff
- Add context only they know (business rules, team conventions)
- Adjust scope (widen or narrow what the agent should touch)

### 4c: environment/Dockerfile

Generate based on the repo's tech stack (detected from files like `package.json`, `*.csproj`, `Cargo.toml`, `requirements.txt`, `go.mod`):

```dockerfile
FROM <base-image-for-detected-stack>

RUN apt-get update && apt-get install -y git curl wget ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Clone at the "before" state — the commit BEFORE the fix
RUN git clone <repo-url> . && git checkout <before_ref>

# Install dependencies
RUN <dependency-install-command>

# Verify the environment builds
RUN <build-command>

CMD ["/bin/bash"]
```

Base image selection:
- `.csproj` / `.sln` → `mcr.microsoft.com/dotnet/sdk:8.0`
- `package.json` → `node:20`
- `requirements.txt` / `pyproject.toml` → `python:3.12`
- `Cargo.toml` → `rust:1.78`
- `go.mod` → `golang:1.22`
- Other → ask the user

### 4d: tests/test.sh

If the commit includes test files, generate a verifier that runs those tests:

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
if <test-command-targeting-relevant-tests>; then
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

If the commit does NOT include tests, inform the user and offer options:
1. Write a test script that checks for the expected changes (file existence, specific patterns in code, API behavior)
2. Skip the verifier and rely only on assessment evaluation (not recommended)
3. Write the tests together with the user

### 4e: assessment_criteria.md

Generate a per-task rubric using the benchmark project's `assessment_dimensions.json`. For each dimension, create scoring criteria specific to this task:

```markdown
# Assessment Criteria: <Task Name>

Evaluate the agent's solution across the following dimensions.

## 1. <Dimension from assessment_dimensions.json> (0–<max_score>)

| Score | Criteria |
|-------|----------|
| 0     | <worst case — specific to this task> |
| ...   | <intermediate levels> |
| <max> | <best case — specific to this task> |

**Key checks:**
- <What to look for in the code, specific to this task and dimension>
```

Present to the user for review — they know the codebase best and can add nuance.

### 4f: solution/solve.sh (optional)

Offer to generate a reference solution script that applies the actual commit diff:

```bash
#!/bin/bash
cd /app
git cherry-pick <after_ref> --no-commit
```

Or, if cherry-pick won't apply cleanly, generate a patch-based approach:

```bash
#!/bin/bash
cd /app
git diff <before_ref> <after_ref> | git apply
```

This is useful for verifying that `test.sh` passes on a known-good solution.

## Step 5: Verify generated tasks

After all selected tasks are generated:

1. **Confirm the benchmark project has assessment dimensions** — if `assessment_dimensions.json` is missing or empty, prompt the user to define dimensions (delegate to `benchmark-creator` Step 3).

2. **Build and test each Docker image:**
   ```bash
   docker build -t benchmark-test-<task-name> -f tasks/<task-name>/environment/Dockerfile .
   ```

3. **If solution/solve.sh exists, validate the verifier:**
   ```bash
   docker run --rm -v $(pwd)/tasks/<task-name>/solution:/solution \
     -v $(pwd)/tasks/<task-name>/tests:/tests \
     benchmark-test-<task-name> bash -c "
       bash /solution/solve.sh && mkdir -p /logs/verifier && bash /tests/test.sh
     "
   ```
   Expected: exit 0 and `reward.txt` contains 1.

4. **Dry run** on a single task:
   ```bash
   nasde run --variant <any-variant> --tasks <task-name> --without-eval -C <benchmark-dir>
   ```

## Tips

- **Start small.** Pick 3–5 candidates for the first pass. You can always add more later.
- **Prefer commits with tests.** Tasks with existing tests are much faster to set up — the verifier almost writes itself.
- **Don't leak the solution.** The biggest risk in generating instructions from diffs is accidentally describing HOW the problem was solved. Describe the WHAT and WHY, not the HOW.
- **Local repos work fine.** NASDE supports local git paths in `source.git`. No need to push to a public remote for company repos.
- **Combine with benchmark-creator.** This skill generates tasks; `benchmark-creator` handles the project scaffold, dimensions, and variants. Use them together.
