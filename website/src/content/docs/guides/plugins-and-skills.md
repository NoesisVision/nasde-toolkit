---
title: Plugins & Skills
description: Advanced variant mechanisms — ship a whole Claude Code plugin into the sandbox, reference a single skill by path, and scope a variant to specific tasks.
---

Three mechanisms control *what* you load into a trial and *where* it runs: a whole plugin, a single skill by reference, and task scoping. All three are declared in config files — see [Configuration](/nasde-toolkit/reference/configuration/) for the bare format; this page shows how to use them.

## Benchmarking a plugin (`[nasde.plugin]`)

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

## Referencing a skill (`[[skill]]`)

If a variant just needs to test one skill, point at its source path instead of copying it into `variants/<v>/skills/`. Add a `[[skill]]` array to the variant's `variant.toml`:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

[[skill]]
path = "../../../src/plugins/my-plugin/skills/my-skill"
ref  = "abc1234"   # optional, same semantics as [nasde.source]
```

The **whole** skill directory (including `references/`) is staged into the sandbox — no copy under `variants/`. The legacy `variants/<v>/skills/<name>/` copy path still works unchanged (and now also carries `references/`, which it previously dropped).

## How skills reach each agent

Each agent family auto-discovers skills from a different place, so Nasde delivers them where the CLI actually looks (you don't manage this — but it's worth knowing where your skill files end up):

- **Claude Code** discovers from the project, so its skills land in `/app/.claude/skills/`.
- **Codex** and **Gemini** auto-discover skills only from a HOME-scoped directory — `$HOME/.agents/skills/` for Codex, `~/.gemini/skills/` for Gemini. Nasde routes Codex/Gemini skills there through the agent's native skill-injection (not into the project directory, where the CLI would never scan them). See [ADR-012](https://github.com/NoesisVision/nasde-toolkit/blob/main/docs/adr/012-native-codex-gemini-skill-injection.md).

This applies to all three skill sources for Codex/Gemini: a variant's `agents_skills/` / `gemini_skills/` snapshot, a `[[skill]]` reference, and a `[nasde.plugin]`'s own skills.

:::caution[Codex/Gemini skills must start with `---` frontmatter]
Codex's loader is strict: a `SKILL.md` that does **not start** with a `---` YAML frontmatter line is silently rejected and the skill is never registered. A common trap is a leading comment (e.g. `<!-- Source: ... -->`) *above* the frontmatter — move it below the closing `---`. Nasde warns at run time when a skill's `SKILL.md` doesn't open with `---`, so the gotcha surfaces instead of the skill mysteriously doing nothing. (Claude is more lenient, but starting every `SKILL.md` with frontmatter is the safe habit.)
:::

## Scoping a variant to specific tasks (`tasks`)

Some variants only make sense for one task — for example, a skill whose code examples are *tuned to a particular repo's conventions*. Running such a variant against a different codebase produces misleading results. Declare a `tasks` scope in the variant's `variant.toml`:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

# This variant's skill references this repo's value objects, so it should only
# run against that task.
tasks = ["csharp-anemic-to-rich-domain"]
```

The scope is enforced either way you run: with `--all-variants` a scoped variant runs **only** against its declared tasks (others show as `SKIPPED`); with a single `--variant`, asking for a task outside its scope aborts with a clear error rather than running against the wrong repo. Omit `tasks` (the default) for a general-purpose variant that runs everywhere.
