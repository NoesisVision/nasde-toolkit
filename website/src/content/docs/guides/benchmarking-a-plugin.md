---
title: Benchmarking a Plugin
description: Ship a local Claude Code plugin into the sandbox with one task.toml declaration — skills and MCP server auto-registered.
---

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

The full `[nasde.plugin]` reference lives in [variant.toml & task.toml → Benchmarking a plugin](/nasde-toolkit/reference/config-formats/#benchmarking-a-claude-code-plugin-nasdeplugin).
