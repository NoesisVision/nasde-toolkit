---
title: Running & Configuring Runs
description: The operational side of a run — building from a local repo, scaling on cloud sandboxes, configuring the reviewer agent, and exporting results.
---

This guide covers the operational lifecycle of a run, in the order you typically hit it: point it at your code, scale it out, tune the reviewer, and keep the results.

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

## Configuring the reviewer agent

The reviewer agent (assessment evaluator) is configurable via the `[evaluation]` section in `nasde.toml`. By default it uses `claude-opus-4-7` with read-only tools (`Read`, `Glob`, `Grep`).

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
