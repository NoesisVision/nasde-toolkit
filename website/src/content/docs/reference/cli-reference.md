---
title: CLI Reference
description: The nasde commands you'll use day to day, the full command list, the Harbor/Opik pass-throughs, and every nasde run option.
---

Most users only need `nasde run` — everything else is occasional. The everyday commands come first; the full reference follows.

## Everyday commands

```bash
# Scaffold a new benchmark project from scratch
nasde init my-benchmark

# Run the default variant
nasde run --variant vanilla -C my-benchmark

# Codex variant (model name is OpenAI-side)
nasde run --variant codex-baseline --model gpt-5.3-codex -C my-benchmark

# Gemini CLI variant
nasde run --variant gemini-baseline --model google/gemini-3-flash-preview -C my-benchmark

# Run a single task with experiment tracking
nasde run --variant vanilla --tasks my-task -C my-benchmark --with-opik

# Skip the reviewer (rough tests only, faster)
nasde run --variant vanilla -C my-benchmark --without-eval

# Re-run the reviewer on an existing trial (no re-execution)
nasde eval jobs/2026-03-13__14-30-00 --with-opik -C my-benchmark

# [Experimental] Back up the results essence so they don't only live in jobs/
nasde results-export jobs/2026-03-13__14-30-00 --to ~/Dropbox/nasde-results -C my-benchmark

# Publish a trial as a PR for human rubric calibration, then pull comments back
nasde calibrate publish jobs/2026-03-13__14-30-00/movie__abc -C my-benchmark
nasde calibrate pull-comments jobs/2026-03-13__14-30-00/movie__abc -C my-benchmark --json
```

Authentication is covered in [Authentication & Opik](/nasde-toolkit/reference/authentication/) — in short, export an API key (`ANTHROPIC_API_KEY` / `CODEX_API_KEY` / `GEMINI_API_KEY`) **or** just use whatever OAuth subscription you're already logged into via `claude` / `codex` / `gemini login`.

## All commands

| Command | Description |
|---------|-------------|
| `nasde run` | Run benchmark: Harbor trial + assessment evaluation (default) |
| `nasde eval <JOB_DIR>` | Re-run assessment evaluation on an existing job |
| `nasde results-export <PATHS> --to <DIR>` | Copy trial artifact essence (scores, metrics, patch, trajectory) to a plain dir |
| `nasde calibrate publish <PATHS>` | Publish trial diffs + assessments as PRs/MRs for human rubric review |
| `nasde calibrate pull-comments <PATHS>` | Pull review comments back from the PRs/MRs (use `--json` for the orchestrator) |
| `nasde init [DIR]` | Scaffold a new evaluation project |
| `nasde install-skills` | Install bundled Claude Code authoring skills into `~/.claude/skills/` (or `./.claude/skills/` with `--scope project`) |

## Pass-through

| Command | Description |
|---------|-------------|
| `nasde harbor ...` | Full Harbor CLI (view, jobs resume, trials, datasets, etc.) |
| `nasde opik ...` | Opik CLI (configure, usage-report, export, etc.) |

## `nasde run` options

| Flag | Description |
|------|-------------|
| `--variant` | Variant to run (defaults to config default) |
| `--all-variants` | Run every available variant (Cartesian product with tasks) |
| `--tasks` | Comma-separated task names to run |
| `--model` | Model override (e.g. `claude-sonnet-4-6`, `o3`, `google/gemini-3-flash-preview`) |
| `--effort` | Reasoning-effort override (overrides `variant.toml reasoning_effort`; see [Configuration → Reasoning effort](/nasde-toolkit/reference/configuration/#reasoning-effort)) |
| `--attempts`, `-n` | Independent agent attempts per task (Harbor `n_attempts`) — the sample size behind the `mean ±std` |
| `--timeout` | Agent timeout in seconds |
| `--with-opik` | Enable Opik tracing |
| `--without-eval` | Skip assessment evaluation |
| `--eval-repetitions` | Judge evaluations per trial (default: from `nasde.toml [evaluation]`, fallback 3) |
| `--max-concurrent-eval` | Max concurrent assessment evaluations (default: 10) |
| `--harbor-env` | Harbor execution environment (`docker`, `daytona`, `modal`, `e2b`, `runloop`, `gke`) |
| `--job-suffix` | Custom suffix for the job directory name (default: random 6-char hex) |
| `--project-dir`, `-C` | Path to evaluation project |
