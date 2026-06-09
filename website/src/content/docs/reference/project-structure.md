---
title: Project Structure & nasde.toml
description: The layout of a scaffolded benchmark project, the variant.toml essentials, reasoning effort, and the nasde.toml config block.
---

A scaffolded project has the following layout:

```
my-benchmark/
  nasde.toml                  # Project configuration
  assessment_dimensions.json   # Scoring dimensions (shared across tasks)
  tasks/
    feature-a/
      task.toml                # Task config (Harbor sections + [nasde.source] / [nasde.plugin])
      instruction.md           # Agent prompt
      assessment_criteria.md   # Per-task criteria for post-hoc evaluator
      environment/             # Optional: custom Dockerfile (else auto-generated from [nasde.source] / [nasde.plugin])
      tests/
        test.sh                # Harbor verification script
  variants/
    vanilla/                   # Claude Code variant
      variant.toml             # agent = "claude", model = "claude-sonnet-4-6"
      CLAUDE.md                # Agent system prompt (injected to /app/CLAUDE.md)
    guided/                    # Claude Code variant with skills
      variant.toml             # may also list [[skill]] entries (skill-by-reference)
      CLAUDE.md
      skills/                  # Claude skills (injected to /app/.claude/skills/, incl. references/)
        my-skill/
          SKILL.md
    codex-baseline/            # Codex variant
      variant.toml             # agent = "codex", model = "gpt-5.3-codex"
      AGENTS.md                # Codex instructions (injected to /app/AGENTS.md)
    codex-with-skills/         # Codex variant with skills
      variant.toml
      AGENTS.md
      agents_skills/           # Codex skills (injected to /app/.agents/skills/)
        my-skill/
          SKILL.md             # Requires YAML frontmatter (name + description)
    gemini-baseline/           # Gemini CLI variant
      variant.toml             # agent = "gemini", model = "google/gemini-3-flash-preview"
      GEMINI.md                # Gemini instructions (injected to /app/GEMINI.md)
    gemini-with-skills/        # Gemini CLI variant with skills
      variant.toml
      GEMINI.md
      gemini_skills/           # Gemini skills (injected to /app/.gemini/skills/)
        my-skill/
          SKILL.md
  evaluator_skills/            # Optional: skills for the evaluator agent
    code-review/
      SKILL.md
  evaluator_mcp.json           # Optional: MCP server config for evaluator
  jobs/                        # Trial output (gitignored)
```

Each variant must have a `variant.toml` declaring the agent type **and** the model:

```toml
agent = "claude"                   # "claude" | "codex" | "gemini"
model = "claude-sonnet-4-6"        # model appropriate for the agent family
reasoning_effort = "high"          # optional — see "Reasoning effort" below
```

See [variant.toml & task.toml](/nasde-toolkit/reference/config-formats/) for the full configuration-file reference.

## Reasoning effort

How hard the model thinks is a configuration you should set deliberately, not leave to chance. Each agent family ships a *different* default level, and those defaults are not comparable — Codex's `high` is the top of its three levels, while Claude's `high` is only the middle of five (`xhigh` and `max` sit above it). Comparing two agents on their respective defaults silently compares different thinking budgets.

Set the effort explicitly with the optional `reasoning_effort` field in `variant.toml`, or override it for a single run with `nasde run --effort`. Priority is **`--effort` > `variant.toml reasoning_effort` > Harbor's family default** (left unset means NASDE passes nothing and the family default applies). Typical levels (for reference — the exact set differs per model and changes over time): Claude `low`/`medium`/`high`/`xhigh`/`max`, Codex `none`/`minimal`/`low`/`medium`/`high`/`xhigh`, Gemini `minimal`/`low`/`medium`/`high`. NASDE does **not** police the value — it passes whatever you set straight to the agent, which is the source of truth and rejects an unknown level itself; this avoids a stale built-in list wrongly blocking a newly-valid level.

The effort you set is stamped onto each trial (`reasoning_effort` in `assessment_summary.json` and `metrics.json`), and the `nasde run` cost table groups by `(agent, model, effort)` — a different effort is treated as a different configuration and never averaged in with another.

## `nasde.toml`

```toml
[project]
name = "my-benchmark"
version = "1.0.0"

[defaults]
variant = "vanilla"
# harbor_env = "daytona"  # Optional: cloud sandbox provider (default: docker)

[docker]
base_image = "ubuntu:22.04"
build_commands = []

[evaluation]
backend = "claude"                            # "claude" (default) | "codex"
model = "claude-opus-4-7"
dimensions_file = "assessment_dimensions.json"
# max_turns = 60                              # Max evaluator conversation turns (default 60)
# allowed_tools = ["Read", "Glob", "Grep"]    # Override default tool whitelist
# mcp_config = "./evaluator_mcp.json"         # MCP server config for evaluator
# skills_dir = "./evaluator_skills"           # Skills directory for evaluator
# append_system_prompt = ""                   # Extra system prompt for evaluator
# include_trajectory = false                   # Include ATIF trajectory in evaluation

[reporting]
platform = "opik"
```
