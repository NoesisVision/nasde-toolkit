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
   them, so timing is correct. Cursor support costs one
   `_AGENT_SKILLS_SUBDIR` entry, and Harbor owns the copy command.

   Alternatives considered (the Claude-style route, `sandbox_files` into a
   cwd skills dir). `cursor-agent` 2026.11.22 always loads the project
   roots `.cursor/skills` and `.agents/skills`; it loads `.claude/skills` and
   `.codex/skills` only when its third-party extensibility setting is on.
   - `cursor_skills/` → `sandbox_files` → `/app/.cursor/skills/`: workable,
     but needs a Cursor target in `stage_skill_dir` (hard-wired to
     `/app/.claude/skills`), a second `[[skill]]`/plugin staging pass and a
     third skill-routing style. Rejected: more code than one dict entry.
   - Reuse Claude's `skills/` → `/app/.claude/skills/`: no new code, but
     discovery depends on Cursor's third-party setting. Rejected.
4. **Effort.** Base model slug + `reasoning_effort`, as for every other
   family. Cursor's effort-suffixed slugs (`claude-opus-5-5-high`) are not the
   documented convention: they would hide effort inside the model name and
   break per-`(agent, model, effort)` grouping and exact-match pricing.
5. **Auth.** `CURSOR_API_KEY` (Harbor's only mechanism), required by
   `_ensure_auth`. Before that check nasde reads one `.env`: the project dir's
   if it exists, else its parent's (never both; shell values win). A key in
   the parent `.env` is therefore ignored when the project dir has its own
   `.env`. The key can come from the shell, from that `.env`, or from
   `scripts/export_cursor_api_key.sh`, which mirrors the Claude token
   export script. The `_ensure_auth` error and the script's error name both
   routes. A Cursor agent run with the default Claude judge needs the Cursor
   key as well as Claude auth: `_ensure_auth` checks only the agent's family.
6. **Judge.** `backend = "cursor"` runs `cursor-agent -p --output-format json
   --trust --mode ask`. `--mode ask` is the public read-only mode and stands in
   for Claude's `--allowedTools Read,Glob,Grep`; a custom `allowed_tools` is
   warned about and ignored. `max_turns` has no equivalent and is ignored.
   `skills_dir`, `mcp_config` (`.cursor/mcp.json` + `--approve-mcps`) and
   `append_system_prompt` (always-apply `.cursor/rules/nasde-judge.mdc`) share
   one temp cwd with `--add-dir <workspace>` — the pattern Claude already uses
   for `skills_dir` — so the trial workspace is never written to. Hidden
   internal flags (`--allowed-tools`, `--system-prompt`) are not used.

   `append_system_prompt` uses a rule because rules are the documented CLI
   mechanism ("The CLI agent supports the same rules system as the editor",
   cursor.com/docs/cli/using). PENDING: an e2e marker check that headless
   `-p --mode ask` loads an always-apply rule from the temp cwd has not been
   run. The real-CLI flag check (`--trust`, `--mode ask`, `--add-dir`,
   `--approve-mcps`) and native `~/.cursor/skills` discovery have not been run
   against a real cursor-agent either; they gate release, not merge. A
   prompt-prefix fallback (a user-turn instruction rather than a system-level
   one) is not implemented.

   Alternative considered: a `sessionStart` hook returning
   `additional_context`, which the docs describe as added to the initial
   system context. Rejected:
   - The hook is fire-and-forget (the agent loop does not wait for it), so in
     a one-shot `-p` run the context may arrive after the first model call.
   - It still needs the temp cwd (`.cursor/hooks.json`). The only other
     location, `~/.cursor/hooks.json`, is the user's global config and would
     collide across concurrent evaluations.
   - It adds a script that must print JSON on every OS, and a failing hook is
     silent in headless mode.
   - Hook responses from all sources are merged, and only `user_message` /
     `agent_message` are concatenated, so a user's own `sessionStart` hook
     may replace nasde's text.
   - The docs do not say `sessionStart` fires in the CLI.

   Known limitation, accepted: with no context options the judge runs in the
   trial workspace, which holds the variant's injected `/app/AGENTS.md`.
   `cursor-agent` 2026.11.22 loads `AGENTS.md` and `.cursor/rules` as rules
   from cwd and every parent up to `/` (plus nested `**/AGENTS.md`;
   `CLAUDE.md` too behind the third-party setting), so the agent's
   instructions reach the judge. The existing judges share this: the Codex
   judge always runs in the workspace and loads its `AGENTS.md`; the Claude
   judge does the same for `CLAUDE.md` (and parent folders) unless
   `skills_dir` is set. The Cursor judge matches them; isolating all judges
   from variant instruction files is out of scope for this ADR. Whether
   `--add-dir` roots also load rules is not verified, so the temp cwd is not
   claimed to avoid this.
7. **Pricing.** Bundled `cursor/*` entries at Cursor's published list rates
   (no Teams/Enterprise Cursor Token Rate — a plan property, documented as an
   ADR-013 override). As for Claude, nasde computes `cost_usd` from the catalog
   and passes no rates into Harbor. Harbor's trajectory cost and the Opik
   per-step costs come from Harbor's own resolution (its built-in Cursor
   table, then LiteLLM). With the bundled entries both sides use the same
   rates today. They differ only when a project or `~/.nasde` override changes
   a rate, or when one table drifts — the same as for Claude, Codex and
   Gemini. When a `cursor/*` model is not in the catalog, nasde falls back to
   the trajectory's `final_metrics.total_cost_usd` and records `cost_source`
   so the figure is traceable. The fallback applies to Cursor agents only.
   The `nasde run` summary marks such a figure with `*` and a footnote, so a
   Harbor estimate is never mistaken for a catalog price (Codex and Gemini
   never show a cost that is not from the catalog, so they need no marker).

   Alternative considered: pass the resolved catalog rates into `CursorCli`'s
   `pricing` kwarg, so Harbor, Opik and nasde share one rate source. Rejected:
   - With the bundled catalog it changes no number.
   - Cursor would be the only family whose Harbor-side cost nasde sets.
   - It ties the runner to Harbor's `pricing` schema, which Harbor validates
     strictly when it constructs the agent, so a schema change would fail the
     run.
   - Harbor's figure would no longer be an independent check on stale
     catalog entries.

   If Opik should show nasde's cost, that belongs in one place for all agents.
8. **Opik.** Harbor's Cursor trajectory has no per-step `metrics`, so nasde's
   deferred-span patch (ADR-006) never emitted Cursor agent spans.
   `ConfigurableCursor` attaches per-step `metrics` (tokens + cost) from
   `cursor-agent`'s per-call `usage` events, giving Cursor the same per-step
   Opik spans and trace cost roll-up Claude has.
9. **Deliberately unchanged (reviewed, not done).**
   - *Model-name normalization.* `cursor/<slug>` is validated by Harbor only
     as `provider/model`. A bare slug (`composer-2.5`) fails in every trial,
     after the image build, with Harbor's `ValueError`; nasde adds no
     preflight and does not rewrite the model. This matches Gemini, whose
     agent has the same `provider/model` rule and no nasde check, and keeps one
     rule per family instead of a Cursor-only exception. Considered: reject
     unless `cursor/`, prepend `cursor/` to bare slugs, always normalize to
     `cursor/<slug>`, an override of Harbor's `_model_arg`, and a per-family
     normalizer (which would also change Codex and Gemini). The cost of
     leaving it: a late failure for a bare slug, and a null `cost_usd` (not an
     error) for a wrong provider such as `anthropic/claude-opus-5-5`, because
     pricing and the Harbor fallback key on `cursor/`. Revisit with the
     per-family normalizer if it bites.
   - *Judge-model stamp.* The judge's `evaluator_model` stamp is the raw
     `[evaluation] model`, so a Cursor judge serving `claude-opus-5-5` is
     stamped like the Claude judge and their evaluations can share a cluster
     in `assessment_summary.json`. A `cursor/` stamp or a backend-aware
     grouping key was considered and rejected: judge execution is moving to
     Harbor, which will own judge identity and model naming, so a nasde-side
     fix would be thrown away. Until then, do not mix judge backends within one
     job when comparing scores.

## Consequences

- Cursor trials get tokens, cost, Opik spans and native skills on par with
  Claude.
- Judge differences from Claude are explicit: fixed read-only tool set, no
  turn cap, system prompt delivered as a rule file (unverified until the pending
  e2e marker check is run; no prompt-prefix fallback), chats persisted locally.
- Opik and the trajectory show Harbor's cost; nasde's summaries show the
  catalog cost. A `pricing.toml` override (e.g. the Teams Cursor Token Rate)
  changes only nasde's figure — the same as for every other agent.
- A Cursor model without the `cursor/` prefix fails per trial (as for Gemini);
  a wrong provider silently loses the catalog price. See Decision 9.
- Mixing judge backends that serve the same model name in one job averages
  them together. See Decision 9.
- `cost_source` is a new economics field (all agents; `"pricing.toml"` for
  catalog-priced trials).
- `[[skill]]`/`[nasde.plugin]` skills also reach every agent's
  `/app/.claude/skills/` through `sandbox_files` (ADR-009). Codex and Gemini
  never read that dir; Cursor does when third-party extensibility is on. It
  de-duplicates by real file path, not skill name, so such a skill can be
  listed twice (no error, slightly more context). Not filtered; revisit if
  observed.
- Cursor's prices change often; the three bundled entries need re-verification
  like every other catalog entry. Unbundled or effort-suffixed slugs fall back
  to Harbor's estimate, flagged by `cost_source`.
