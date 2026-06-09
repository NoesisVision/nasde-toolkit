---
title: variant.toml & task.toml
description: The per-variant and per-task configuration file formats — agent type, model, reasoning effort, skill-by-reference, plugins, and task scoping.
---

## `variant.toml`

Every variant directory must contain a `variant.toml` declaring the agent type **and** the model:

```toml
agent = "claude"                   # "claude" | "codex" | "gemini"
model = "claude-sonnet-4-6"        # model appropriate for the agent family
reasoning_effort = "high"          # optional — see Reasoning effort below
```

For Claude Code variants, `CLAUDE.md` is injected into `/app/CLAUDE.md`; for Codex variants `AGENTS.md` → `/app/AGENTS.md`; for Gemini CLI variants `GEMINI.md` → `/app/GEMINI.md`. If no `harbor_config.json` exists, one is auto-generated from the agent type.

### Reasoning effort

How hard the model thinks is a configuration you should set deliberately — each agent family ships a *different* default level, and those defaults are not comparable. Set it with the optional `reasoning_effort` field, or override it for a single run with `nasde run --effort`. Priority is **`--effort` > `variant.toml reasoning_effort` > Harbor's family default**. See [Reasoning effort](/nasde-toolkit/reference/project-structure/#reasoning-effort) for the full explanation and per-family level scales.

### Referencing a skill instead of copying it (`[[skill]]`)

If a variant just needs to test one skill, point at its source path instead of copying it into `variants/<v>/skills/`. Add a `[[skill]]` array to the variant's `variant.toml`:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

[[skill]]
path = "../../../src/plugins/my-plugin/skills/my-skill"
ref  = "abc1234"   # optional, same semantics as [nasde.source]
```

The **whole** skill directory (including `references/`) is staged into the sandbox — no copy under `variants/`. The legacy `variants/<v>/skills/<name>/` copy path still works unchanged (and now also carries `references/`, which it previously dropped).

### Scoping a variant to specific tasks (`tasks`)

Some variants only make sense for one task — for example, a skill whose code examples are *tuned to a particular repo's conventions*. Running such a variant against a different codebase produces misleading results. Declare a `tasks` scope:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

# This variant's skill references this repo's value objects, so it should only
# run against that task.
tasks = ["csharp-anemic-to-rich-domain"]
```

The scope is enforced either way you run: with `--all-variants` a scoped variant runs **only** against its declared tasks (others show as `SKIPPED`); with a single `--variant`, asking for a task outside its scope aborts with a clear error rather than running against the wrong repo. Omit `tasks` (the default) for a general-purpose variant that runs everywhere.

## `task.toml`

A single task config file, shared with Harbor — it reads its standard sections (`[task]`, `[agent]`, `[environment]`, `[verifier]`, `[metadata]`) directly. NASDE-specific fields live under `[nasde.*]` and are ignored by Harbor.

### Local repo benchmarks (`[nasde.source]`)

You can build benchmarks from local (private) repositories by setting `source.git` to a relative path:

```json
{
  "source": {
    "git": "../..",
    "ref": "abc1234"
  }
}
```

NASDE auto-generates the Docker environment — no custom `Dockerfile` needed. See [`examples/nasde-dev-skill/`](https://github.com/NoesisVision/nasde-toolkit/tree/main/examples/nasde-dev-skill) for a complete example that tests nasde-toolkit itself.

### Benchmarking a Claude Code plugin (`[nasde.plugin]`)

If your task exercises a **local Claude Code plugin** (a directory with `.claude-plugin/plugin.json`, `skills/`, and an MCP server in `.mcp.json`), declare it once in `task.toml` — no vendored snapshot, no hand-wired Dockerfile `COPY`, no hand-written `[environment.mcp_servers]`, no copying the plugin's skills into a variant:

```toml
[nasde.plugin]
path = "../../../src/plugins/my-plugin"   # dir containing .claude-plugin/plugin.json
ref = "abc1234"                           # optional git ref, same semantics as [nasde.source]
install_root = "/opt/my-plugin"           # optional, default /opt/<plugin-name>
build = "bun install --frozen-lockfile"   # optional, run at image-build time

[nasde.plugin.env]                        # optional, exported in the MCP server wrapper
CLAUDE_PLUGIN_DATA = "/opt/my-plugin-data"
```

One declaration ships the whole plugin into the sandbox image (at `ref`, via a temporary git worktree, for reproducibility), registers the plugin's own skills for the agent (whole skill dir, including `references/`), and wires its MCP server into the task automatically. Works with or without `[nasde.source]` and with or without a hand-written `environment/Dockerfile`. This **removes the frozen-snapshot workaround** entirely. See [ADR-009](https://github.com/NoesisVision/nasde-toolkit/blob/main/docs/adr/009-plugin-and-skill-by-reference.md).
