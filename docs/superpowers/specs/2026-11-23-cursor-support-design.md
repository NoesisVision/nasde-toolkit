# Cursor support — design

**Date:** 2026-11-23
**Status:** Approved (design), pending spec review
**ADR:** [ADR-015](../../adr/015-cursor-agent-and-judge.md)

## Goal

Add Cursor (`cursor-agent` CLI) as a fourth agent family and a third judge
backend, with behavior and decisions as close as possible to Claude support.
Scope: agent, judge backend, pricing, Opik cost, auth helper script, examples,
docs, tests.

## Context (verified 2026-11-23)

- Harbor 0.24 ships `harbor.agents.installed.cursor_cli.CursorCli`: installs
  `cursor-agent`, runs `cursor-agent --yolo --print --output-format=stream-json`,
  converts stream-json to an ATIF trajectory (`final_metrics` only — no per-step
  `metrics`), writes task MCP servers to `~/.cursor/mcp.json`, copies native
  skills (`config.agent.skills`) into `~/.cursor/skills` in `install()`, and
  folds `reasoning_effort` (`low|medium|high|xhigh|max`) into the model arg as
  `model[effort=X]`. Requires `CURSOR_API_KEY` and a `provider/model` name.
- Harbor uploads injected skills before `agent.setup()`, so Cursor's
  `install()`-time skill copy has correct timing.
- `--yolo` implies MCP auto-approval in `cursor-agent` (`force || approveMcps`).
- `cursor-agent` loads `AGENTS.md` from cwd unconditionally; `CLAUDE.md` only
  behind a third-party setting.
- `cursor-agent`'s stream-json `result.usage` carries tokens only
  (`inputTokens`, `outputTokens`, `cacheReadTokens`, `cacheWriteTokens`,
  `reasoningTokens`) — **no dollar cost**. It also emits per-model-call
  `{"type":"usage","subtype":"model_call","model_call_id":...}` events, which
  Harbor currently drops.
- Hidden flags `--allowed-tools` ("internal only") and `--system-prompt`
  ("Anysphere/OpenAI team only") exist; not used.

## Decisions

### 1. Agent — `agents/configurable_cursor.py`

`ConfigurableCursor(CursorCli)`, mirroring `ConfigurableGemini`:

- `ConfigurableCursorOptions(CursorCliOptions)` adds `sandbox_files`.
- `setup()`: DNS fix (probe `api2.cursor.sh`), upload `sandbox_files`, then
  `super().setup()`.
- Per-step metrics for Opik (see §5).
- `name()` → `"configurable-cursor-cli"`.

Variant contract:

| Item | Cursor variant |
|---|---|
| `variant.toml` | `agent = "cursor"`, `model = "cursor/<base-slug>"` (e.g. `cursor/composer-2.5`) |
| Instructions | `AGENTS.md` → `/app/AGENTS.md` (existing collection, no new code). No rules support — Claude has none either. |
| Skills | `cursor_skills/<name>/` → Harbor-native `config.agent.skills` → `~/.cursor/skills` (ADR-012 machinery). `[[skill]]` and `[nasde.plugin]` skills follow automatically. |
| Effort | `reasoning_effort` / `--effort`, passed straight through; Harbor validates. Use base slugs (`cursor/claude-opus-5-5`), not Cursor's effort-suffixed slugs (`-high`), so `config.json` `model_name` and the `reasoning_effort` stamp stay separate — same as Claude/Codex/Gemini. |
| MCP | Task-level `mcp_servers` work via Harbor (`~/.cursor/mcp.json` + `--yolo`). No Cursor equivalent of `claude_config.json` (unused in examples). |

### 2. Runner / CLI wiring

Add `cursor` to: `_VALID_AGENT_TYPES`, `_agent_import_path`, new
`_is_cursor_agent`, `_agent_type_from_import_path`, `_AGENT_SKILLS_SUBDIR`
(`"cursor": "cursor_skills"`), job-summary short-name prefix strip, `--effort`
help text, agent label map in `cli.py`, `--eval-backend` validation.

`_ensure_auth`: Cursor agent requires `CURSOR_API_KEY`; otherwise SystemExit
with a hint to `source scripts/export_cursor_api_key.sh`.

### 3. Judge — `evaluator_backends/cursor_subprocess.py`

`CursorSubprocessBackend`, selected by `[evaluation] backend = "cursor"`.

Command: `cursor-agent -p --output-format json --trust --mode ask --model <m>`
with the prompt on stdin; `<m>` is `eval_config.model` with a leading
`cursor/` stripped. Result text parsed from the JSON `result` field.

| Claude judge option | Cursor judge |
|---|---|
| `allowed_tools` (default Read/Glob/Grep) | Always `--mode ask` (read-only). If `allowed_tools` is set: yellow warning, ignored. |
| `max_turns` | Ignored silently (always set via default 60); documented. |
| `skills_dir` | Temp cwd `.cursor/skills/` + `--add-dir <workspace>` (same as Claude's temp-dir trick). |
| `mcp_config` | Copied to temp cwd `.cursor/mcp.json` + `--approve-mcps` + `--add-dir <workspace>`. |
| `append_system_prompt` | Always-apply rule `.cursor/rules/nasde-judge.mdc` in temp cwd. |
| trial dir (`include_trajectory` / diff) | `--add-dir <trial_dir>` |
| `--no-session-persistence` | No equivalent; Cursor keeps the chat locally. Accepted. |
| Auth | Non-fatal like Claude: dim note when `CURSOR_API_KEY` unset (relies on `cursor-agent login`). |

The temp cwd is created only when `skills_dir`, `mcp_config` or
`append_system_prompt` is set; otherwise cwd = workspace, as for Claude. The
trial workspace is never written to.

### 4. Pricing

- Bundle 3 entries in `pricing.toml` at Cursor's published list rates
  (no Teams/Enterprise Cursor Token Rate; documented as a project /
  `~/.nasde` override), `as_of = "2026-11-23"`,
  `source = "https://cursor.com/docs/models-and-pricing"`:

  | Key | input | cache write | cache read | output |
  |---|---|---|---|---|
  | `cursor/composer-2.5` | 0.5 | — (falls back to input) | 0.2 | 2.5 |
  | `cursor/claude-opus-5-5` | 4.0 | 5.0 | 0.20 | 20.0 |
  | `cursor/claude-sonnet-5-5` | 2.0 | 2.5 | 0.10 | 10.0 |

- **One rate source:** for Cursor agents the runner resolves the model in the
  layered catalog (`load_pricing_layered`) and passes the rates into Harbor's
  existing `CursorCli` `pricing` kwarg (per-1M `input`/`output`/`cache_read`/
  `cache_write`) in `_build_merged_config`. Harbor's `total_cost_usd`, the
  per-step Opik costs and nasde's `cost_usd` then agree.
- **Fallback (Cursor agents only):** model not in the catalog → no `pricing`
  kwarg → Harbor prices it (built-in table, then LiteLLM) → nasde's `cost_usd`
  uses trajectory `final_metrics.total_cost_usd`. Claude/Codex/Gemini behavior
  unchanged.
- **Provenance:** economics gain `cost_source`: `"pricing.toml"`,
  `"harbor:<extra.cost_source>"` (e.g. `harbor:cursor_pricing`,
  `harbor:litellm`), or `null`. Yellow warning on fallback.
- **Token fix:** `extract_token_usage` reads cache writes from
  `extra.total_cache_creation_input_tokens`, falling back to
  `extra.usage_totals.cacheWriteTokens` (Cursor).

### 5. Opik cost for Cursor agents

`ConfigurableCursor` overrides trajectory conversion: collect
`usage/model_call` events by `model_call_id`, and after Harbor builds the
steps, assign `step.metrics = Metrics(prompt_tokens=input+cacheRead+cacheWrite,
completion_tokens=output, cached_tokens=cacheRead, cost_usd=<rates>)` to the
step mapped to that `model_call_id`. Rates = the resolved `pricing` kwarg (or
Harbor's built-in/LiteLLM resolution). Assigning `metrics` after construction
triggers nasde's deferred-span patch (ADR-006), so Cursor agent steps appear
in Opik with tokens and cost and roll up into the trace total — same path as
Claude.

### 6. Auth helper

`scripts/export_cursor_api_key.sh` (+ `.ps1`), mirroring
`export_oauth_token.sh`: keep an existing `CURSOR_API_KEY`; else read the
macOS keychain entry `cursor-api-key`; export `CURSOR_API_KEY`. Verified with
user approval during implementation.

### 7. Examples, docs

- `cursor-vanilla` variant in all three examples (`agent = "cursor"`,
  `model = "cursor/composer-2.5"`, `AGENTS.md` copied from the matching codex
  variant or a neutral one where none exists).
- `CHANGELOG.md` (Unreleased → Added), `README.md`, `CLAUDE.md`,
  `ARCHITECTURE.md`, skills (`nasde-benchmark-runner`,
  `nasde-benchmark-creator`, `nasde-dev`), scaffold template comment,
  ADR-015.

## Testing

Unit tests (no LLM calls), mirroring existing Gemini/Codex tests:

- `ConfigurableCursor`: options accept `sandbox_files`; upload + DNS; per-step
  metrics attached from usage events; cost from rates.
- Runner: variant validation, import path, auth error, `cursor_skills`
  native routing, `pricing` kwarg injection (priced and unpriced model).
- Judge: command building per option, temp-cwd contents, warning on
  `allowed_tools`, model prefix strip, result parsing.
- Token metrics: Cursor cache-write fallback; `cost_source` and Harbor
  fallback.

Quality gates: `ruff check`, `ruff format --check`, `mypy`, `pytest`.

E2E (each run individually authorized — spends tokens):

1. `cursor-vanilla` on one small task with the default Claude judge,
   `--with-opik`; check reward, economics, `cost_source`, Opik spans/cost.
2. `nasde eval <job> --eval-backend cursor`.
3. Verify `cursor-agent` accepts a bare base slug (`claude-opus-5-5` with and
   without `[effort=...]`); if not, revisit pricing keys with the user.

## Out of scope

Rules support (`.claude/rules`, `.cursor/rules`) for any agent; Cursor OAuth
token injection; Cursor equivalent of `claude_config.json`; Teams surcharge in
bundled prices; Cost fallback for non-Cursor agents.
