---
title: Commands
description: Full reference for nasde core commands, the Harbor/Opik pass-throughs, and nasde run options.
---

## Core

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
| `--tasks` | Comma-separated task names to run |
| `--model` | Model override (e.g. `claude-sonnet-4-6`, `o3`, `google/gemini-3-flash-preview`) |
| `--effort` | Reasoning-effort override (overrides `variant.toml reasoning_effort`; see [Reasoning effort](/nasde-toolkit/reference/config-formats/#reasoning-effort)) |
| `--timeout` | Agent timeout in seconds |
| `--with-opik` | Enable Opik tracing |
| `--without-eval` | Skip assessment evaluation |
| `--harbor-env` | Harbor execution environment (`docker`, `daytona`, `modal`, `e2b`, `runloop`, `gke`) |
| `--project-dir`, `-C` | Path to evaluation project |
