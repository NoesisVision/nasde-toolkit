# Cursor CLI Support

**Date:** 2026-11-19
**Status:** Approved (design review)

## Problem

nasde benchmarks three agent families (Claude Code, Codex, Gemini CLI) and judges
with two evaluator backends (`claude`, `codex`). Cursor's `cursor-agent` CLI is
neither a benchmarkable agent nor a judge option, so Cursor-hosted models
(Composer, `auto`) and Cursor's agent harness cannot be compared against the
other families.

Harbor 0.24 (already a nasde dependency) ships a working `CursorCli` agent
(`harbor/agents/installed/cursor_cli.py`): it installs `cursor-agent`, runs it with
`--yolo --print --output-format=stream-json`, parses the stream into an ATIF
trajectory, supports `reasoning_effort` (`low|medium|high|xhigh|max`, rendered as
`model[effort=X]`), native skills (`config.agent.skills` → `~/.cursor/skills`), and
MCP servers (`~/.cursor/mcp.json`). What is missing is the nasde layer around it.

## Scope

Both halves, in one design:

1. **Cursor as a benchmarked agent** — variant `agent = "cursor"`.
2. **Cursor as an evaluator backend** — `[evaluation] backend = "cursor"`.

Plus the token/cost economics needed so Cursor trials get a non-null `cost_usd`.

Out of scope: injecting the host `cursor-agent login` token into the sandbox
(API key only), `.cursor/rules/` support, long-context price premiums, an Opik
`provider` attribution fix.

## Decisions

| Question | Decision |
|---|---|
| Sandbox auth | `CURSOR_API_KEY` only (env or `.env`); clear error if missing. Cursor user API keys bill against the Cursor plan, so there is no subscription-vs-API split to work around. |
| Instruction file | `AGENTS.md` → `/app/AGENTS.md` (same as Codex; `cursor-agent` reads it from repo root). |
| Skill snapshots | Reuse `agents_skills/` (a Codex variant becomes a Cursor variant by changing one line). |
| Cost source of truth | nasde's catalog; Harbor's reported cost recorded alongside for audit. |
| Approach | Thin wrappers on Harbor's `CursorCli` + a slug normalizer in the price lookup + a third subprocess judge backend. |

Fallback: if the live smoke test shows Harbor's install-time skill registration
is not discovered by `cursor-agent` (the ADR-012 timing risk), replace the wrapper
with a nasde-owned agent on `BaseInstalledAgent` that registers skills inside `run()`.

## Design

### 1. Benchmarked agent

**New `src/nasde_toolkit/agents/configurable_cursor.py`**, modelled on
`configurable_gemini.py`:

- `ConfigurableCursorOptions(CursorCliOptions)` declares `sandbox_files`
  (Harbor's preflight validates kwargs against `options_model` with
  `extra="forbid"`).
- `ConfigurableCursor(CursorCli)`:
  - `setup()` uploads `sandbox_files` then calls `super().setup()`.
  - `name()` → `"configurable-cursor-cli"`.
  - Overrides `_model_arg()` to accept a bare slug: `composer-2.5` is treated as
    `cursor/composer-2.5` for Harbor's parsing. Effort still renders as
    `composer-2.5[effort=high]`; a slug already containing `/` passes through.
    `model_name` stays bare everywhere else (harbor config, `config.json`,
    trajectory, pricing, summaries), so cost lookup and run-summary grouping
    work without translation.
  - Overrides `build_cli_flags()` to append `--approve-mcps` when
    `self.mcp_servers` is non-empty — Harbor writes `~/.cursor/mcp.json` but
    never approves the servers, and a `--print` run cannot answer the prompt.

**Runner wiring (`runner.py`):**

- `_VALID_AGENT_TYPES` gains `"cursor"`.
- `_agent_import_path("cursor")` →
  `nasde_toolkit.agents.configurable_cursor:ConfigurableCursor`.
- New `_is_cursor_agent()`; `_agent_type_from_import_path` returns `"cursor"`.
- `_AGENT_SKILLS_SUBDIR["cursor"] = "agents_skills"` — snapshot skills,
  `[[skill]]` references and `[nasde.plugin]` skills all flow through the
  existing native `config.agent.skills` path (ADR-012), unchanged.
- `AGENTS.md` → `/app/AGENTS.md` already works via `_collect_sandbox_files`.
- `_ensure_auth`: a Cursor agent requires `CURSOR_API_KEY`; otherwise print
  `ERROR: Set CURSOR_API_KEY (create a User API key in the Cursor dashboard)`
  and `SystemExit(1)`.
- Run-summary agent-name prefix stripping gains `"cursor-"`.

**Effort.** Variants use a slug exactly as `cursor-agent --list-models` prints it
(e.g. `claude-opus-5-5-high`, which embeds effort). The optional
`reasoning_effort` is still threaded through unchanged and Harbor renders it as
`[effort=X]`; docs say to use one or the other. No local validation (consistent
with `_resolve_effort`'s policy). When effort lives in the slug, the
`reasoning_effort` stamp is `""` — grouping still separates configurations
because the `model_name` differs.

**Variant example:**

```toml
agent = "cursor"
model = "composer-2.5"
```

**Known limitation.** Harbor's `~/.cursor/mcp.json` writer drops `env` for stdio
servers. `[nasde.plugin]` servers are unaffected (nasde env-wraps them into a
script); a hand-declared stdio server relying on `env` loses it. Documented, not
worked around.

### 2. Token and cost economics

All changes sit in the single extractor / single price lookup, so the run path
(`assessment_summary.json`) and export path (`metrics.json`) stay in agreement
(ADR-011).

**Cache-write extraction (`token_metrics.extract_token_usage`).** Read
`final_metrics.extra.total_cache_creation_input_tokens`; if absent, fall back to
`final_metrics.extra.usage_totals.cacheWriteTokens` (Cursor's location). The other
fields already match nasde's definitions: Harbor's Cursor `total_prompt_tokens` =
fresh + cache reads + cache writes (= nasde `input`), `total_cached_tokens` =
cache reads, output = completion tokens (no separate reasoning count).

**Slug normalization (`pricing.resolve_price(model, pricing)`).** Used by
`compute_cost_usd`, `pricing_as_of`, the run-summary "Pricing used" table, and
`pricing_used.json`:

1. Exact key match first — a catalog or project-override entry for the full slug
   always wins.
2. Otherwise strip bracket params (`[effort=high]`, `[context=1m,...]`), then a
   trailing effort suffix from a closed set
   (`-none|-minimal|-low|-medium|-high|-xhigh|-max`), optionally preceded by
   `-thinking`, or a bare trailing `-thinking`; retry the lookup once.
   - `claude-opus-5-5-high` → `claude-opus-5-5`
   - `claude-fable-5-thinking-high` → `claude-fable-5`
   - `gpt-5.3-codex-xhigh` → `gpt-5.3-codex`
3. Still no match → unpriced: `cost_usd = null` + the existing warning, extended
   with a hint to add a `pricing.toml` override.

It is not a validation gate: a new Cursor suffix degrades to "unpriced", never
blocks a run. It applies to every agent (harmless — exact match runs first).
Wherever the effective catalog is shown, a normalized match is labelled, e.g.
`claude-opus-5-5-high (priced as claude-opus-5-5)`; `pricing_used.json` records
both the trial's slug and the catalog key it resolved to.

**Bundled catalog entries.** Add `composer-2.5`, `composer-2`, `composer-2-fast`,
and `auto` to `src/nasde_toolkit/pricing.toml` with `as_of` and
`source = "https://cursor.com/docs/models-and-pricing"`. Rates are re-verified
against that page at implementation time (Harbor's copy, not authoritative:
Composer 2.5 = $0.50 in / $2.50 out / $0.20 cache read / $0.50 cache write per 1M).
Third-party models run through Cursor resolve to their existing vendor entries via
normalization; `gemini-4-*` and `muse-*` stay unpriced as today.

**Audit fields.** The per-trial economics block gains
`agent_reported_cost_usd` (from `final_metrics.total_cost_usd`) and
`agent_reported_cost_source` (from `final_metrics.extra.cost_source`, e.g.
`cursor_cli`, `cursor_pricing`, `litellm`; `null` when absent). Generic across
agents. Recorded only — `cost_usd` (catalog) remains the source of truth and the
run-summary table is unchanged.

**Known limitation.** "1M" context slugs may carry long-context premiums a flat
catalog rate does not model. Documented.

### 3. Evaluator backend (`evaluator_backends/cursor_subprocess.py`)

`CursorSubprocessBackend` implements the existing `EvaluatorBackend` protocol and
is selected by `[evaluation] backend = "cursor"`.

**Command:**

```
cursor-agent -p --output-format json --mode ask --trust \
  --model <model> --workspace <tmp> --add-dir <trial workspace> \
  [--add-dir <trial dir>] [--approve-mcps]
```

- **Read-only via `--mode ask`.** Cursor has no `--allowedTools` equivalent; if
  `allowed_tools` is set, print a yellow warning that it is ignored on this
  backend.
- **Always a temporary `--workspace`.** Unlike the Claude backend (temp dir only
  when skills are configured), Cursor may write `.cursor/` state into its
  workspace; anything written into the trial workspace would leak into
  `changes.patch` and calibration PRs. The temp dir holds `.cursor/skills/`
  (copied from `skills_dir`) and `.cursor/mcp.json` (copied from `mcp_config`;
  same `mcpServers` shape as Claude's). Removed in `finally`.
- **Trial dir** via `--add-dir` under the same rule as Claude: when
  `include_trajectory` is on or `agent_changes.diff` exists.
- **`append_system_prompt`** has no flag → prepended to the prompt as a preamble.
- **`max_turns`** has no equivalent → documented as unsupported on this backend.
- **Result** from the JSON output's `result` field; `is_error: true` or a
  non-zero exit code raises `RuntimeError` with the stderr/stdout tails (same
  shape as the other backends).

**Auth (host).** `CURSOR_API_KEY` if set; otherwise the host `cursor-agent` login,
checked by `cursor-agent status`. Neither → error pointing at `cursor-agent login`.
`validate_cli_installed` checks `shutil.which("cursor-agent")` with an install hint
and the "set a different backend or pass `--without-eval`" escape hatch.

**Default model.** When `backend = "cursor"` and `[evaluation] model` is unset, the
default is `claude-opus-5-5-high` (the Claude backend's `claude-opus-5-5` is not a
valid Cursor slug). "Unset" means the `model` key is absent from the
`[evaluation]` table: the backend-aware default is chosen in `config.py` while
parsing, so an explicit `model = "claude-opus-5-5"` is passed through untouched
(and rejected by `cursor-agent` itself, consistent with the no-local-validation
policy). Its evaluations cluster separately because `evaluator_model` differs —
correct by the existing clustering contract.

**Wiring.** `create_backend()` gains the `cursor` branch; the "Supported:" error
lists `'claude', 'codex', 'cursor'`.

**Verify during implementation:** whether `-p` reads the prompt from stdin (else
pass it positionally — judge prompts are tens of KB, well under macOS `ARG_MAX`);
that `--workspace` picks up `.cursor/skills` and `.cursor/mcp.json`; that
`--mode ask` permits Read/Grep/Glob across `--add-dir` roots.

## Testing

Unit tests (fakes only, no live calls):

- `tests/test_configurable_cursor.py` (new): options model accepts
  `sandbox_files`; `_model_arg()` for bare slug, bare slug + effort, and
  `provider/slug`; `--approve-mcps` only with MCP servers; `setup()` uploads
  `sandbox_files` before Harbor's setup.
- `tests/test_configurable_agents_options.py`: Cursor passes Harbor's preflight.
- `tests/test_runner.py`, `tests/test_runner_skills.py`: `agent = "cursor"`
  accepted; import path; `AGENTS.md` mapped; `agents_skills/`, `[[skill]]`, and
  plugin skills land in `config.agent.skills`; `_ensure_auth` with/without
  `CURSOR_API_KEY`.
- `tests/test_token_metrics.py`: Cursor-shaped trajectory yields
  `cache_write_tokens` from `usage_totals`; `agent_reported_cost_*` populated.
- `tests/test_pricing.py`: exact-first (incl. full-slug project override);
  table-driven suffix/bracket stripping; unknown suffix → `None`; Composer
  entries load.
- `tests/test_evaluator_backends.py`: command contains `--mode ask` and a temp
  `--workspace`; `--add-dir` rules; `--approve-mcps` with `mcp_config`; temp dir
  cleaned up on success and failure; `allowed_tools` warning; preamble
  prepending; `result` extraction; `is_error` raises; factory branch.
- `tests/test_config.py`: cursor backend default model.

Live smoke (each LLM run individually authorized by the owner):

1. New `cursor-vanilla` variant in `examples/ddd-architectural-challenges`
   (`composer-2.5`) with a canary skill in `agents_skills/`; one `nasde run` at
   `--eval-repetitions 1`. Pass: reward written, `trajectory.json` present,
   `cost_usd` non-null, `cache_write_tokens > 0`, canary skill natively invoked
   in the trajectory. A skill failure triggers the approach-B fallback.
2. `nasde eval` with `backend = "cursor"` against that job.

Quality gates per `nasde-dev`: `ruff check`, `ruff format --check`, `mypy`, `pytest`.

## Documentation

- `CHANGELOG.md` `[Unreleased]` — Added: Cursor agent, Cursor judge backend,
  Composer pricing, `agent_reported_cost_*` audit fields. Fixed: Cursor cache
  writes counted in cost.
- `docs/adr/015-cursor-cli-agent-and-judge.md` — thin wrapper, bare slug, price
  lookup normalization, `--mode ask` + temp workspace judge, key-only sandbox auth.
- `README.md`, `CLAUDE.md`, `ARCHITECTURE.md` — agent lists, auth, backend lists,
  package structure.
- Skills: `nasde-benchmark-runner` (`CURSOR_API_KEY`, `--list-models`),
  `nasde-benchmark-creator` (Cursor variant example), `nasde-dev` (Cursor auth in
  the e2e step).
- Scaffold: `NASDE_TOML_TEMPLATE` backend comment → `"claude" | "codex" | "cursor"`.
- Example: `cursor-vanilla` variant.

## Rollout

Three PRs:

1. **Economics** — `resolve_price` normalizer, Composer/`auto` entries,
   cache-write fallback, audit fields. Independent and useful on its own.
2. **Cursor agent** — `ConfigurableCursor` + runner wiring + example variant.
   Depends on PR 1 for non-null cost.
3. **Cursor judge** — `CursorSubprocessBackend`. Independent of 1 and 2.

Each PR carries its own CHANGELOG entry and doc updates.
