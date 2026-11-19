# ADR-015: Cursor CLI as agent and judge

**Status:** Accepted
**Date:** 2026-11-19

## Context

nasde benchmarks Claude Code, Codex and Gemini CLI and judges with `claude` or
`codex`. Harbor 0.24 ships a `CursorCli` agent (install, headless run,
stream-json → ATIF trajectory, native skills into `~/.cursor/skills`, MCP into
`~/.cursor/mcp.json`). Cursor differs from the other harnesses in three ways that
matter to nasde:

1. **Model slugs embed effort** (`claude-opus-5-5-high`,
   `claude-fable-5-thinking-xhigh`); no bare `claude-opus-5-5` slug exists.
2. **The same model costs differently per harness.** Cursor bills third-party
   models at API list price. On 2026-11-19 its OpenAI rates match nasde's vendor
   entries exactly, but it bills Claude cache writes at the 5-minute rate (1.25x
   input), while nasde's Claude entries use the 1-hour rate Claude Code uses (2x).
3. **Auth.** Harbor's agent requires `CURSOR_API_KEY`; a Cursor user API key
   bills against the Cursor plan, so there is no subscription-vs-API split.

## Decision

- **Thin wrapper.** `ConfigurableCursor(CursorCli)` adds only `sandbox_files`
  (for `AGENTS.md`) and `--approve-mcps` when MCP servers are declared. Variants
  reuse the Codex layout: `AGENTS.md` and `agents_skills/` through the native
  skill channel (ADR-012).
- **Provider-qualified model names.** A Cursor agent's `model_name` is recorded as
  `cursor/<slug>`; the runner adds the prefix to a bare slug. This is the form
  Harbor's `CursorCli` requires and it scopes price keys to the harness.
- **Layered price-key lookup.** `pricing.resolve_catalog_key` tries the recorded
  name, its effort-normalized form, the name without its provider prefix, and
  that normalized. The bundled catalog carries `cursor/` entries for Composer and
  for every Claude model with a cache-write rate (they carry Cursor's 1.25x
  cache-write rate). OpenAI models fall through to vendor entries. `auto` is deliberately unpriced (no per-token
  rate). Effort normalization is not a validation gate: an unknown suffix
  degrades to "unpriced".
- **Audit, not truth.** The harness-reported cost (`final_metrics.total_cost_usd`
  + `extra.cost_source`) is recorded as `agent_reported_cost_*`; `cost_usd` from
  the catalog remains the source of truth (ADR-011/014).
- **Judge.** `CursorSubprocessBackend` runs `cursor-agent -p --output-format json
  --mode ask` (read-only; Cursor has no per-tool allow-list) from a throwaway
  `--workspace` holding `.cursor/skills` and `.cursor/mcp.json`, with the trial
  workspace attached via `--add-dir`, so nothing the CLI writes reaches the
  agent's diff. Host auth is `CURSOR_API_KEY` or `cursor-agent login`. The default
  judge model for this backend is `claude-opus-5-5-high`.
- **Sandbox auth is API-key only.** No login-token injection.

## Consequences

- Cursor trials and Claude Code trials of the same model are priced at the rate
  each harness actually bills.
- `google/gemini-*` names now fall through to an unprefixed catalog entry if one
  is added.
- A slug whose real price differs from its effort-stripped base (none known
  today) needs an exact entry; exact entries always win.
- Team/Enterprise "Cursor Token Rate" ($0.25/1M on third-party models) is not
  modelled.
- `max_turns` and `allowed_tools` have no Cursor equivalent; the judge warns on
  `allowed_tools` and ignores `max_turns`.
- Harbor drops `env` for stdio MCP servers in `~/.cursor/mcp.json`; nasde's
  `[nasde.plugin]` servers are unaffected (env-wrapped), hand-declared ones are.
