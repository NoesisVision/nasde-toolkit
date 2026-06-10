---
title: Running & Configuring Runs
description: The operational side of a run — building from a local repo, scaling on cloud sandboxes, configuring both the agent under test and the reviewer, and exporting results.
---

This guide covers the operational lifecycle of a run, in the order you typically hit it: point it at your code, scale it out, configure the two agents (the one under test and the reviewer), and keep the results.

:::tip[Two agents, configured the same way]
A NASDE run involves **two** coding agents: the **agent under test** (the one whose configuration you're measuring) and the **reviewer agent** (the LLM-as-a-Judge that scores the result). Both are configurable along the same axes — instructions, skills, MCP servers, model, reasoning effort. The two sections below mirror each other deliberately.
:::

## Running on a local repo

You can build benchmarks from local (private) repositories by setting `source.git` to a relative path:

```json
{
  "source": {
    "git": "../..",
    "ref": "abc1234"
  }
}
```

NASDE auto-generates the Docker environment — no custom `Dockerfile` needed. See [`examples/nasde-dev-skill/`](https://github.com/NoesisVision/nasde-toolkit/tree/main/examples/nasde-dev-skill) for a complete example that tests nasde-toolkit itself. The full `[nasde.source]` reference is in [Configuration](/nasde-toolkit/reference/configuration/#local-repo-source-nasdesource).

## Cloud sandbox providers

By default, Harbor runs agents in **local Docker containers**. For horizontal scaling, you can use a cloud sandbox provider — this shifts command execution to the cloud, making trials I/O bounded rather than compute bounded. You can typically parallelize far above your local CPU count.

Supported providers (via Harbor):

| Provider | Flag value | API key env var |
|----------|-----------|-----------------|
| Docker (default) | `docker` | — |
| [Daytona](https://www.daytona.io/) | `daytona` | `DAYTONA_API_KEY` |
| [Modal](https://modal.com/) | `modal` | `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` |
| [E2B](https://e2b.dev/) | `e2b` | `E2B_API_KEY` |
| [Runloop](https://www.runloop.ai/) | `runloop` | `RUNLOOP_API_KEY` |
| [GKE](https://cloud.google.com/kubernetes-engine) | `gke` | GCP credentials |

We recommend **Daytona** for its flexibility and scaling capabilities.

```bash
# Run with Daytona cloud sandbox
export DAYTONA_API_KEY=...
nasde run --variant vanilla --harbor-env daytona -C my-benchmark

# Or use the Harbor pass-through for full control
nasde harbor run --dataset my-benchmark@1.0 --agent claude-code --model claude-sonnet-4-6 --env daytona -n 32
```

The cloud sandbox provider affects **only the Harbor trial execution** (Stage 1). The assessment evaluation (Stage 2) always runs locally on the host machine. You can set a default provider in `nasde.toml`:

```toml
[defaults]
harbor_env = "daytona"
```

See the [Harbor documentation](https://harborframework.com/docs/cloud) for detailed provider configuration.

## Configuring the agent under test

The agent under test is the one whose configuration you're measuring — and **that configuration is the whole point of a benchmark**. A variant bundles everything that defines one agent setup. (For the exact file format, see [Configuration → variant.toml](/nasde-toolkit/reference/configuration/#varianttoml).)

### Instructions (CLAUDE.md / AGENTS.md / GEMINI.md)

The single most important knob: the system instructions you inject into the agent. Each family reads its own file, dropped into the variant directory and injected into the sandbox:

- Claude Code → `CLAUDE.md` → `/app/CLAUDE.md`
- Codex → `AGENTS.md` → `/app/AGENTS.md`
- Gemini CLI → `GEMINI.md` → `/app/GEMINI.md`

This is how you test "baseline vs. with my custom prompt" — two variants, same task, different instruction file.

### Skills

Give the agent Claude Code skills two ways: drop them under `variants/<v>/skills/<name>/` (copied in whole, including `references/`), or reference a skill from its source path with a `[[skill]]` entry in `variant.toml` (no copy — staged from the source at an optional git `ref`). Codex and Gemini skills live under `agents_skills/` and `gemini_skills/`. See [Plugins & Skills](/nasde-toolkit/guides/plugins-and-skills/) for the full workflow.

### MCP servers

Wire MCP servers the agent can call during the task. The cleanest path is a `[nasde.plugin]` declaration in `task.toml`, which ships a plugin's skills **and** its MCP server into the sandbox in one line — see [Benchmarking a plugin](/nasde-toolkit/guides/plugins-and-skills/#benchmarking-a-plugin-nasdeplugin).

### Reasoning effort

Set how hard the agent thinks with `reasoning_effort` in `variant.toml`, or override per run with `nasde run --effort`. Family defaults are *not* comparable, so set it deliberately when comparing agents — see [Configuration → Reasoning effort](/nasde-toolkit/reference/configuration/#reasoning-effort).

### Variant scoping

Restrict a variant to specific tasks with `tasks = [...]` in `variant.toml` — useful when a skill is tuned to one repo's conventions and would mislead elsewhere. See [Scoping a variant](/nasde-toolkit/guides/plugins-and-skills/#scoping-a-variant-to-specific-tasks-tasks).

## Configuring the reviewer agent

The reviewer agent (assessment evaluator) is the mirror image of the agent under test: same axes (model, skills, MCP, system prompt), configured via the `[evaluation]` section in `nasde.toml`. By default it uses `claude-opus-4-7` with read-only tools (`Read`, `Glob`, `Grep`).

### Backend and model

By default, nasde uses the Claude Code CLI for assessment evaluation. You can switch to Codex:

```toml
[evaluation]
backend = "codex"      # "claude" (default) | "codex"
model = "gpt-5.3-codex"
```

Both backends use your existing CLI authentication (subscription OAuth or API key) — no additional setup. The evaluator spawns the CLI as a subprocess, so you get the same billing treatment as interactive use. See [`examples/nasde-dev-skill/nasde.codex.toml`](https://github.com/NoesisVision/nasde-toolkit/blob/main/examples/nasde-dev-skill/nasde.codex.toml) for a ready-to-use Codex configuration.

### Skills

Give the reviewer agent skills (e.g. a code review methodology) by creating a directory with `SKILL.md` files and pointing at it:

```toml
[evaluation]
skills_dir = "./evaluator_skills"
```

Skills are copied into the evaluator's workspace and loaded via the CLI's native auto-discovery (`claude --add-dir <workspace>`).

### MCP servers

Add external analysis tools (linters, complexity analyzers) as MCP servers:

```json
// evaluator_mcp.json
{
  "mcpServers": {
    "code-analysis": {
      "type": "stdio",
      "command": "npx",
      "args": ["@some-org/code-analysis-mcp"]
    }
  }
}
```

```toml
[evaluation]
mcp_config = "./evaluator_mcp.json"
allowed_tools = ["Read", "Glob", "Grep", "mcp__code-analysis__analyze"]
```

MCP tool names follow the `mcp__<server>__<tool>` convention. If you override `allowed_tools`, you must include the MCP tools explicitly.

### All options

| Setting | Default | Purpose |
|---------|---------|---------|
| `backend` | `claude` | Subprocess backend: `claude` or `codex` |
| `model` | `claude-opus-4-7` | Evaluator model |
| `dimensions_file` | `assessment_dimensions.json` | Scoring dimensions file |
| `max_turns` | `60` | Max evaluator conversation turns (raise for DDD-rich workspaces with many small files) |
| `allowed_tools` | `["Read", "Glob", "Grep"]` | Tool whitelist |
| `mcp_config` | — | Path to MCP server config JSON |
| `skills_dir` | — | Path to evaluator skills directory |
| `append_system_prompt` | — | Extra system prompt text |
| `include_trajectory` | `false` | Include ATIF trajectory in evaluation |

When `include_trajectory` is enabled, the evaluator can read the agent's full execution trajectory (`agent/trajectory.json`) — tool calls, timestamps, token usage, errors. This enables assessment dimensions that evaluate the agent's *process* (efficiency, verification discipline, decision-making) alongside the final output. See [`examples/nasde-dev-skill`](https://github.com/NoesisVision/nasde-toolkit/tree/main/examples/nasde-dev-skill) for a working example with trajectory-aware dimensions.

## Exporting results

:::caution[Experimental / beta]
This command is new; the layout may still change. Feedback welcome.
:::

By default a run's output lives only in the local, gitignored `jobs/` directory — and most of its weight is build junk (compiled binaries, `.git` checkouts) that's useless for analysis. If you clear `jobs/`, the results are gone. `nasde results-export` copies just the **essence** of each trial into a plain destination directory so your results survive and travel:

```bash
nasde results-export jobs/2026-03-13__14-30-00 --to ~/Dropbox/nasde-results -C my-benchmark
```

The destination is any path you like — an iCloud or Dropbox folder, an external drive, or a git repo you commit yourself. NASDE just writes files there; it never talks to a cloud provider, so there's nothing to authenticate. Each trial becomes one flat folder `<job>__<trial>/` containing:

- `metrics.json` — self-contained summary: timing, model, variant, task, reward, reasoning effort, **token usage + USD cost** (see [Token & Cost](/nasde-toolkit/concepts/token-cost/))
- `assessment_eval_*.json` — the reviewer's per-dimension scores and reasoning (one file per repetition)
- `assessment_summary.json` — per-dimension mean/std/range across repetitions (the representative result)
- `trajectory.json` — the agent's full tool-call trace, for post-hoc cost/process analysis
- `changes.patch` — exactly what the agent changed (a code diff, not the multi-GB workspace)
- `verifier_stdout.txt`, `reward.txt` — the rough-test output

You can pass several paths at once, mixing whole jobs and individual trials — NASDE figures out which is which. Re-running is safe: it merges (copying any evaluations added since the last export) and never re-touches the immutable trajectory or patch.
