# ADR-015: Cursor agent and judge backend

**Status:** Accepted
**Date:** 2026-11-23

## Context

nasde supports Claude Code, Codex and Gemini CLI as agents, and Claude/Codex
as judges. Cursor's `cursor-agent` CLI is the fourth family users want to
benchmark. Harbor 0.24 already ships a `CursorCli` installed agent (install,
stream-json → ATIF trajectory, MCP via `~/.cursor/mcp.json`, native skills via
`~/.cursor/skills`, `reasoning_effort` folded into `model[effort=X]`).

The guiding requirement: Cursor behavior and decisions stay as close as
possible to Claude support. Where the Cursor CLI has no public equivalent of a
Claude mechanism, nasde says so explicitly instead of relying on internal
flags.

## Decision

1. **Agent.** `ConfigurableCursor` subclasses Harbor's `CursorCli`, adding
   `sandbox_files` and the cloud DNS fix (same role as `ConfigurableClaude` /
   `ConfigurableGemini`). Variants declare `agent = "cursor"` and a
   Harbor-style prefixed model (`cursor/composer-2.5`).
2. **Instructions.** `AGENTS.md` → `/app/AGENTS.md`, Cursor's always-loaded
   project file. Like Claude (`CLAUDE.md` only), no rules directory support.
3. **Skills.** `cursor_skills/<name>/` routes through Harbor-native
   `config.agent.skills` → `~/.cursor/skills` (ADR-012), so `[[skill]]` and
   `[nasde.plugin]` skills reuse the Codex/Gemini channel. Harbor uploads
   injected skills before `agent.setup()`, and `CursorCli.install()` copies
   them, so timing is correct.
4. **Effort.** Base model slug + `reasoning_effort`, as for every other
   family. Cursor's effort-suffixed slugs (`claude-opus-5-5-high`) are not the
   documented convention: they would hide effort inside the model name and
   break per-`(agent, model, effort)` grouping and exact-match pricing.
5. **Auth.** `CURSOR_API_KEY` (Harbor's only mechanism), required by
   `_ensure_auth`; `scripts/export_cursor_api_key.sh` mirrors the Claude
   token export script.
6. **Judge.** `backend = "cursor"` runs `cursor-agent -p --output-format json
   --trust --mode ask`. `--mode ask` is the public read-only mode and stands in
   for Claude's `--allowedTools Read,Glob,Grep`; a custom `allowed_tools` is
   warned about and ignored. `max_turns` has no equivalent and is ignored.
   `skills_dir`, `mcp_config` (`.cursor/mcp.json` + `--approve-mcps`) and
   `append_system_prompt` (always-apply `.cursor/rules/nasde-judge.mdc`) share
   one temp cwd with `--add-dir <workspace>` — the pattern Claude already uses
   for `skills_dir` — so the trial workspace is never written to. Hidden
   internal flags (`--allowed-tools`, `--system-prompt`) are not used.
7. **Pricing.** Bundled `cursor/*` entries at Cursor's published list rates
   (no Teams/Enterprise Cursor Token Rate — a plan property, documented as an
   ADR-013 override). For Cursor agents the runner passes the resolved catalog
   rates into `CursorCli`'s `pricing` kwarg, so Harbor's trajectory cost, the
   Opik per-step costs and nasde's `cost_usd` use one rate source. When a
   `cursor/*` model is not in the catalog, nasde falls back to the trajectory's
   `final_metrics.total_cost_usd` (Harbor's built-in table or LiteLLM) and
   records `cost_source` so the figure is traceable. The fallback applies to
   Cursor agents only.
8. **Opik.** Harbor's Cursor trajectory has no per-step `metrics`, so nasde's
   deferred-span patch (ADR-006) never emitted Cursor agent spans.
   `ConfigurableCursor` attaches per-step `metrics` (tokens + cost) from
   `cursor-agent`'s per-call `usage` events, giving Cursor the same per-step
   Opik spans and trace cost roll-up Claude has.

## Consequences

- Cursor trials get tokens, cost, Opik spans and native skills on par with
  Claude.
- Judge differences from Claude are explicit: fixed read-only tool set, no
  turn cap, system prompt delivered as a rule file, chats persisted locally.
- `cost_source` is a new economics field (all agents; `"pricing.toml"` for
  catalog-priced trials).
- Cursor's prices change often; the three bundled entries need re-verification
  like every other catalog entry. Unbundled or effort-suffixed slugs fall back
  to Harbor's estimate, flagged by `cost_source`.
