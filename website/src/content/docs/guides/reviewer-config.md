---
title: Configuring the Reviewer Agent
description: Customize the assessment evaluator — backend, model, skills, MCP servers, system prompt, and trajectory access — via the [evaluation] section.
---

The reviewer agent (assessment evaluator) is configurable via the `[evaluation]` section in `nasde.toml`. By default it uses `claude-opus-4-7` with read-only tools (`Read`, `Glob`, `Grep`).

## Evaluator backend

By default, nasde uses Claude Code CLI for assessment evaluation. You can switch to Codex:

```toml
[evaluation]
backend = "codex"      # "claude" (default) | "codex"
model = "gpt-5.3-codex"
```

Supported backends:
- `claude` (default) — requires `claude` CLI installed and authenticated
- `codex` — requires `codex` CLI installed and authenticated

Both backends use your existing CLI authentication (subscription OAuth or API key) — no additional setup required. The evaluator spawns the CLI as a subprocess, so you get the same billing treatment as interactive use.

See [`examples/nasde-dev-skill/nasde.codex.toml`](https://github.com/NoesisVision/nasde-toolkit/blob/main/examples/nasde-dev-skill/nasde.codex.toml) for a ready-to-use Codex configuration — swap it in with:

```bash
cp examples/nasde-dev-skill/nasde.codex.toml examples/nasde-dev-skill/nasde.toml
```

## Model

Use the best available model for review quality:

```toml
[evaluation]
model = "claude-opus-4-7"   # Default — recommended for review quality
```

## Skills

Give the reviewer agent skills (e.g. a code review methodology). Create a directory with `SKILL.md` files:

```
my-benchmark/
  evaluator_skills/
    code-review/
      SKILL.md              # Review methodology, scoring principles
```

```toml
[evaluation]
skills_dir = "./evaluator_skills"
```

Skills are copied into the evaluator's workspace and loaded via the CLI's native auto-discovery (`claude --add-dir <workspace>`). The evaluator's prompt automatically adjusts to reference artifact paths correctly.

## MCP servers

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

## System prompt

Append custom instructions to the evaluator's system prompt:

```toml
[evaluation]
append_system_prompt = "Pay special attention to SOLID principles when scoring."
```

## All options

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
