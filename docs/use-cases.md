# NASDE Use Cases

---

## UC1: Evaluating Skills Against Your Own Codebase

### Persona

**Tech lead or senior developer** at a company that has invested in AI coding agent configuration — custom skills, `CLAUDE.md` files, prompting strategies, MCP servers. Works in one or a few company repositories (often a monorepo). Has access to git history of real problems the team has already solved.

### Problem

You've tuned how Claude Code operates in your codebase, but you have no way to measure whether the configuration actually helps. Skill changes are a leap of faith — maybe the new prompt improves refactoring but breaks the agent's ability to write tests. Without structured evaluation, you can't tell what's improving and what's regressing.

### What NASDE enables

You turn real problems from your team's history into repeatable benchmark tasks, then run different skill configurations against them. Results are multi-dimensional scores — not just "did it work?" but "how well did it work across code quality, architecture, testing, and whatever else matters to you." Once the task set is established, it becomes a regression suite: re-run it every time the skill configuration changes.

### Workflow

#### Phase 1: Build the benchmark (one-time setup)

**Step 1 — Identify source tasks from git history**

The **`nasde-benchmark-from-history`** skill automates this step. Tell it a commit range or set of PR numbers — e.g., *"create benchmark tasks from the last 20 commits on main"* — and it scans diffs, filters for good candidates, and presents them for your approval. See the [full skill description](#skill-nasde-benchmark-from-history) below.

You can also do this manually. Browse your team's closed PRs, resolved issues, or notable commits. Look for changes that:
- Are self-contained (clear before/after state)
- Have existing tests or a well-defined "done" criteria
- Represent the kind of work your agents handle (bug fixes, features, refactors)

Good candidates: 5–10 problems where you know what a good solution looks like — because your team already produced one.

**Step 2 — Create the benchmark project**

```bash
nasde init company-skills-eval
cd company-skills-eval
```

**Step 3 — Define assessment dimensions**

Choose 3–5 scoring dimensions that reflect what your team values. Examples for a DDD-oriented .NET team:

| Dimension | Max score | What it measures |
|-----------|-----------|-----------------|
| `domain_modeling` | 30 | Correct use of aggregates, value objects, domain events |
| `architecture_compliance` | 25 | Follows team patterns (mediator, CQRS, repository) |
| `test_quality` | 25 | Meaningful tests, not just coverage |
| `code_clarity` | 20 | Readable, idiomatic, well-structured |

Write these to `assessment_dimensions.json`.

**Step 4 — Create tasks from your history**

For each selected problem, create a task directory under `tasks/`. Each task needs:

| File | Purpose |
|------|---------|
| `task.json` | Git source (your repo at the commit *before* the fix), evaluation config |
| `instruction.md` | What the agent should do — derived from the original issue/PR description |
| `environment/Dockerfile` | Clones your repo at the right commit, installs dependencies |
| `tests/test.sh` | Verifies the solution works — often adapted from your existing tests |
| `assessment_criteria.md` | Rubric for the reviewer agent — what "good" looks like for this specific task |

The `nasde-benchmark-creator` skill walks you through this interactively. If you used `nasde-benchmark-from-history` in Step 1, task files are generated automatically — you review and edit each one before it's written.

**Step 5 — Define variants**

Create directories under `variants/` for each configuration you want to compare:

| Variant | What it represents |
|---------|--------------------|
| `vanilla` | No custom skills — baseline Claude Code |
| `current` | Your current production `CLAUDE.md` + skills |
| `proposed-v2` | The change you're considering |

Each variant contains at minimum a `CLAUDE.md` file that gets injected into the agent's sandbox.

#### Phase 2: Run and compare

```bash
# Run baseline
nasde run --variant vanilla --with-opik

# Run current configuration
nasde run --variant current --with-opik

# Run proposed change
nasde run --variant proposed-v2 --with-opik
```

Results land in Opik. Compare variants across dimensions — see which configuration scores highest on domain modeling, which is best at test quality, whether the proposed change helps or hurts.

#### Phase 3: Regression testing (ongoing)

The task set in `tasks/` is now your regression suite. When someone proposes a skill change:

1. Create a new variant directory with the proposed configuration
2. Run the benchmark: `nasde run --variant proposed-change --with-opik`
3. Compare scores against the `current` variant baseline
4. If scores drop on any dimension, investigate before shipping

The task files are committed to the benchmark project repo — they're stable, versioned, and shared across the team.

### What varies, what stays fixed

| Fixed | Varies |
|-------|--------|
| Source repository (your company repos) | Skill configurations (`CLAUDE.md`, MCP servers) |
| Task set (frozen after Phase 1) | Agent models (Sonnet vs Opus) |
| Assessment dimensions and criteria | Agent frameworks (via Harbor multi-agent support) |

### Current constraints

- NASDE supports local git repos and public remote repos. Private remote repos require local clones (not a practical limitation — you already have them).
- Task creation from git history is manual when using `nasde-benchmark-creator` alone. The **`nasde-benchmark-from-history`** skill automates this — see below.

### Skill: `nasde-benchmark-from-history` {#skill-nasde-benchmark-from-history}

NASDE includes a dedicated skill that accelerates Phase 1 by mining git history for benchmark candidates. Instead of manually browsing PRs and writing task files from scratch, you point the skill at a commit range and it does the heavy lifting.

**How to use it:** Open your repository in Claude Code and describe what you want — e.g., *"create benchmark tasks from the last 20 commits on main"* or *"turn PRs #45, #52, and #61 into evaluation tasks."* The skill activates automatically.

**What it does:**
1. Scans the specified commits, reads diffs, and filters for good candidates (self-contained changes with clear before/after states)
2. Presents a numbered list of candidates with metadata — files changed, difficulty estimate, whether tests exist
3. For each candidate you approve, generates the full task directory: `task.json`, `instruction.md`, `Dockerfile`, `test.sh`, `assessment_criteria.md`
4. You review and edit each generated file before it's written — the skill proposes, you decide

**What it won't do:** It doesn't generate instructions that leak the actual solution. The instruction describes the *problem to solve* (derived from the commit message and PR description), not the *implementation* (the diff). The agent must arrive at a solution independently.

**Relationship to other skills:** `nasde-benchmark-from-history` is an alternative entry point into the benchmark creation workflow. Where `nasde-benchmark-creator` starts from scratch ("what do you want to evaluate?"), `nasde-benchmark-from-history` starts from evidence ("here's what your team already solved"). Both produce the same NASDE task structure.

See the full skill reference: [`.claude/skills/nasde-benchmark-from-history/SKILL.md`](../.claude/skills/nasde-benchmark-from-history/SKILL.md)

---

## UC2: Building and Validating a Universal Skill

### Persona

**AI tooling developer or prompt engineer** building a skill (or `CLAUDE.md` configuration) intended to work across many different codebases, languages, and team conventions. Not tied to one repository — the skill should generalize.

### Problem

You've tested your skill on a handful of repos and it works. But you have no structured way to validate that it generalizes. Does it handle Python as well as TypeScript? Large monorepos as well as small libraries? Projects with extensive tests as well as those with none? Without a diverse, repeatable test suite, you're shipping based on anecdotes.

### What NASDE enables

A benchmark that spans multiple repositories, languages, and problem types. Define the test suite once, re-run it whenever the skill changes. Each run gives you per-task, per-dimension scores — so you can see exactly where the skill shines and where it struggles.

### Workflow

#### Phase 1: Curate the benchmark

**Step 1 — Select diverse source repositories**

The **`nasde-benchmark-from-public-repos`** skill automates this step. Describe the skill you're building — e.g., *"I'm building a refactoring skill that should work across Python, TypeScript, Go, and Rust"* — and it builds a diversity matrix, suggests repos, and generates task scaffolding. See the [full skill description](#skill-nasde-benchmark-from-public-repos) below.

You can also curate manually. Pick public repos that test different axes of your skill's capabilities. For a refactoring skill:

| Repo type | What it tests |
|-----------|--------------|
| Small Express.js API | Simple extraction, JS idioms |
| Large Django monolith | Complex refactoring in a big codebase |
| Rust CLI tool | Language-specific patterns, ownership model |
| React component library | Frontend patterns, component composition |
| Go microservice | Interface-driven design, Go conventions |

The key is **diversity** — each repo should stress a different aspect of the skill.

**Step 2 — Create tasks per repo**

For each source repo, define 1–3 tasks that exercise your skill. Each task should be realistic and self-contained:

- Django project → *"Extract the database layer into a repository pattern"*
- React project → *"Split the God component into focused components"*
- Rust project → *"Replace manual error handling with a Result type chain"*
- Go project → *"Extract the HTTP handler logic into a testable service layer"*

**Step 3 — Define common assessment dimensions**

Since the skill is universal, dimensions should be too:

| Dimension | Max score | What it measures |
|-----------|-----------|-----------------|
| `correctness` | 30 | Does the refactoring preserve behavior? |
| `idiom_adherence` | 25 | Does it follow language-specific conventions? |
| `code_clarity` | 25 | Is the result cleaner than the input? |
| `scope_discipline` | 20 | Did it change only what was needed? |

Per-task `assessment_criteria.md` files adapt these dimensions to the specific repo and language context.

**Step 4 — Scaffold and verify**

```bash
nasde init universal-refactoring-skill
# Add tasks, build Docker images, test verifiers
nasde run --variant current-skill --tasks django-repo-extract --without-eval  # dry run
```

#### Phase 2: Evaluate and iterate

```bash
# Run full benchmark with current skill version
nasde run --variant v1 --with-opik

# Make changes to the skill, run again
nasde run --variant v2 --with-opik
```

Compare in Opik: did v2 improve Rust scores? Did it regress on Python? The per-task breakdown shows exactly which repos and problem types benefit from the change.

#### Phase 3: Expand coverage

As you discover edge cases (the skill fails on monorepos, or struggles with codebases that have no tests), add new tasks to the benchmark. The suite grows over time, becoming a comprehensive validation of your skill's capabilities.

### What varies, what stays fixed

| Fixed | Varies |
|-------|--------|
| Task set (grows over time, but existing tasks don't change) | Skill versions (different `CLAUDE.md` / skill configurations) |
| Assessment dimensions | Agent models (Sonnet vs Opus) |
| Source repos (diverse, public) | — |

### Key difference from UC1

| | UC1: Company skill eval | UC2: Universal skill dev |
|---|---|---|
| **Source repos** | Your company repos (local/private) | Public repos (diverse) |
| **Task origin** | Derived from team's real history | Crafted for cross-cutting diversity |
| **Core question** | "Do our skills help *us*?" | "Does this skill help *everyone*?" |
| **Benchmark shape** | Narrow, deep — your real problems | Broad, varied — many languages and styles |
| **What varies** | Multiple skill configs + agents | Versions of one skill under development |

### Current constraints

- Curating tasks from diverse public repos is time-consuming — finding the right repos, understanding their structure, writing meaningful tasks.
- Each repo needs its own Dockerfile with potentially different base images, dependencies, and build steps.
- The **`nasde-benchmark-from-public-repos`** skill addresses both of these — see below.

### Skill: `nasde-benchmark-from-public-repos` {#skill-nasde-benchmark-from-public-repos}

NASDE includes a dedicated skill for curating diverse benchmark suites from public repositories. Instead of manually searching GitHub and scaffolding Dockerfiles for each language, you describe your skill and the tool guides the curation process.

**How to use it:** Open your benchmark project in Claude Code and describe the skill you're building — e.g., *"I'm building a refactoring skill that should work across Python, TypeScript, Go, and Rust."* The skill activates automatically.

**What it does:**
1. Builds a **diversity matrix** based on your skill description — axes like language, project size, test coverage, architecture style — and presents it for your approval
2. For each cell in the matrix, searches for and proposes public repositories with concrete task ideas
3. For each repo+task pair you approve, generates the full task directory: `task.json` (with pinned commit hash), `instruction.md`, language-appropriate `Dockerfile`, `test.sh`, `assessment_criteria.md`
4. After all tasks are created, shows a coverage summary highlighting which matrix cells are filled and where gaps remain

**Key design principle:** Task instructions are written to be **skill-agnostic**. The instruction describes the raw problem; the skill being tested is injected via the variant's `CLAUDE.md`. This means the same benchmark can test "with skill" vs "without skill" by simply switching variants.

**Relationship to other skills:** Like `nasde-benchmark-from-history`, this is an alternative entry point into the benchmark creation workflow — optimized for the "many repos, one skill" pattern (UC2) rather than the "one repo, many skills" pattern (UC1).

See the full skill reference: [`.claude/skills/nasde-benchmark-from-public-repos/SKILL.md`](../.claude/skills/nasde-benchmark-from-public-repos/SKILL.md)
