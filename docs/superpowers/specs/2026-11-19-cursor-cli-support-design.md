# Cursor CLI Support

**Date:** 2026-11-19
**Status:** Approved (design review)

## Problem

nasde benchmarks three agent families (Claude Code, Codex, Gemini CLI) and judges
with two evaluator backends (`claude`, `codex`). Cursor's `cursor-agent` CLI is
neither a benchmarkable agent nor a judge option, so Cursor-hosted models
(Composer) and Cursor's agent harness cannot be compared against the
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
| Model name | Provider-qualified `cursor/<slug>` end-to-end (the runner adds the prefix, so a variant may write a bare slug). |
| Price lookup | `cursor/<slug>` → `cursor/<base>` → `<base>`; bundled `cursor/` entries only where Cursor's rate differs from the vendor's. |
| Approach | Thin wrappers on Harbor's `CursorCli` + a layered slug lookup in pricing + a third subprocess judge backend. |

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
  - Overrides `build_cli_flags()` to append `--approve-mcps` when
    `self.mcp_servers` is non-empty — Harbor writes `~/.cursor/mcp.json` but
    never approves the servers, and a `--print` run cannot answer the prompt.

**Runner wiring (`runner.py`):**

- `_VALID_AGENT_TYPES` gains `"cursor"`.
- `_agent_import_path("cursor")` →
  `nasde_toolkit.agents.configurable_cursor:ConfigurableCursor`.
- New `_is_cursor_agent()`; `_agent_type_from_import_path` returns `"cursor"`.
- `_build_merged_config` qualifies a Cursor agent's `model_name`: a bare slug
  (`composer-2.5`, from `variant.toml` or `--model`) becomes `cursor/composer-2.5`,
  which is the `provider/model` form Harbor's `CursorCli._model_arg()` requires.
  An already-qualified name passes through. The qualified name is what lands in
  `config.json`, the trajectory, `assessment_summary.json` and `metrics.json`;
  the run-summary table strips `cursor/` for display, as it already strips `google/`.
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

**Why a Cursor namespace.** Cursor bills third-party models at "API list price",
and on 2026-11-19 its OpenAI rates match nasde's vendor entries exactly. Its
Claude rates do not: Cursor bills cache writes at the 5-minute rate (1.25x input,
e.g. Opus 5.5 = $5/1M) while nasde's Claude entries use the 1-hour rate Claude
Code uses (2x, $8/1M). Pricing Claude-through-Cursor against the vendor entries
would overstate the cache-write component by ~60%. The same model can therefore
cost differently per harness, so Cursor-specific rates live under a `cursor/`
key prefix.

**Layered key lookup (`pricing.resolve_catalog_key(model, catalog)`).** Used by
`compute_cost_usd`, `pricing_as_of`, the run-summary "Pricing used" table, and
`pricing_used.json`. Candidates, first hit wins:

1. the model name as recorded (`cursor/claude-opus-5-5-high`)
2. its effort-normalized form (`cursor/claude-opus-5-5`)
3. the name without its provider prefix (`claude-opus-5-5-high`)
4. that, effort-normalized (`claude-opus-5-5`)

Effort normalization (`pricing.normalize_model_slug`) strips bracket params
(`[effort=high]`, `[context=1m,...]`), then one trailing effort suffix from a
closed set (`-none|-minimal|-low|-medium|-high|-xhigh|-max`), optionally preceded
by `-thinking`, or a bare trailing `-thinking`:
`claude-fable-5-thinking-high` → `claude-fable-5`, `gpt-5.3-codex-xhigh` →
`gpt-5.3-codex`. `-fast` is deliberately not stripped (fast modes cost more).

No match → unpriced: `cost_usd = null` + the existing warning. It is not a
validation gate: a new Cursor suffix degrades to "unpriced", never blocks a run.
It applies to every agent; a bare `claude-opus-5-5` from Claude Code resolves on
the first candidate and never reaches a `cursor/` entry. As a side effect,
`google/gemini-*` names now fall through to an unprefixed entry if one is added.

Wherever the effective catalog is shown, a non-exact match is labelled, e.g.
`cursor/claude-opus-5-5-high (priced as cursor/claude-opus-5-5)`;
`pricing_used.json` gains a `catalog_key` field per model.

**Bundled `cursor/` entries** (`as_of = "2026-11-19"`,
`source = "https://cursor.com/docs/models-and-pricing"`), per 1M tokens:

| Key | Input | Cache write | Cache read | Output |
|---|---|---|---|---|
| `cursor/composer-2.5` | 0.5 | (omitted → input rate) | 0.2 | 2.5 |
| `cursor/claude-opus-5-5` | 4.0 | 5.0 | 0.2 | 20.0 |
| `cursor/claude-sonnet-5-5` | 2.0 | 2.5 | 0.1 | 10.0 |
| `cursor/claude-fable-5` | 10.0 | 12.5 | 1.0 | 50.0 |
| `cursor/claude-fable-5-1` | 10.0 | 12.5 | 0.25 | 50.0 |

OpenAI models through Cursor fall through to the existing vendor entries.
`auto` stays unpriced: Cursor bills it as whatever model serves the request, so
there is no per-token rate. Grok, Composer Fast, Gemini 4 and Muse are not added
(not offered to the reference account / no vendor entry); users add them via a
`pricing.toml` override.

**Audit fields.** The per-trial economics block gains
`agent_reported_cost_usd` (from `final_metrics.total_cost_usd`) and
`agent_reported_cost_source` (from `final_metrics.extra.cost_source`, e.g.
`cursor_cli`, `cursor_pricing`, `litellm`; `null` when absent). Generic across
agents. Recorded only — `cost_usd` (catalog) remains the source of truth and the
run-summary table is unchanged.

**Known limitations.** Team and Enterprise plans add a $0.25/1M "Cursor Token
Rate" on eligible third-party models; individual plans do not pay it and it is not
modelled. Models with long-context surcharges (GPT-5.x above 272K input) are
understated on long requests, the same limitation as the Codex entries.

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

**Prompt** is passed as the final positional argument after `--` (as Harbor's
`CursorCli` does); judge prompts are tens of KB, well under macOS `ARG_MAX`.

**Host auth check:** `cursor-agent status` exits 0 whether or not a user is
logged in, so the check parses its output (`Logged in as ...` vs `Not logged in`).

**Verify during the live smoke run:** that `--workspace` picks up
`.cursor/skills` and `.cursor/mcp.json`, and that `--mode ask` permits reading
files across the `--add-dir` roots.

## Testing

Unit tests (fakes only, no live calls):

- `tests/test_configurable_cursor.py` (new): options model accepts
  `sandbox_files`; `--approve-mcps` only with MCP servers; `setup()` uploads
  `sandbox_files` before Harbor's setup.
- `tests/test_configurable_agents_options.py`: Cursor passes Harbor's preflight.
- `tests/test_runner.py`, `tests/test_runner_skills.py`: `agent = "cursor"`
  accepted; import path; `AGENTS.md` mapped; `agents_skills/`, `[[skill]]`, and
  plugin skills land in `config.agent.skills`; `_ensure_auth` with/without
  `CURSOR_API_KEY`; a bare Cursor model becomes `cursor/<slug>` in the merged
  config while other agents' models are untouched.
- `tests/test_token_metrics.py`: Cursor-shaped trajectory yields
  `cache_write_tokens` from `usage_totals`; `agent_reported_cost_*` populated.
- `tests/test_pricing.py`: the four-candidate lookup order; exact match wins
  (incl. full-slug project override); table-driven suffix/bracket stripping;
  unknown suffix → `None`; `cursor/claude-opus-5-5` bills cache writes at 1.25x
  while bare `claude-opus-5-5` keeps 2x.
- `tests/test_evaluator_backends.py`: command contains `--mode ask` and a temp
  `--workspace`; `--add-dir` rules; `--approve-mcps` with `mcp_config`; temp dir
  cleaned up on success and failure; `allowed_tools` warning; preamble
  prepending; `result` extraction; `is_error` raises; factory branch.
- `tests/test_config.py`: cursor backend default model.

Live smoke (each LLM run individually authorized by the owner):

1. A throwaway `cursor-skill-canary` variant (not committed; the shipped example
   is a plain `cursor-vanilla`) on `composer-2.5` with a canary skill in
   `agents_skills/`; one `nasde run` at `--eval-repetitions 1`. Pass: reward
   written, `trajectory.json` present, `cost_usd` non-null,
   `cache_write_tokens > 0`, canary skill natively invoked. A skill failure
   triggers the approach-B fallback.
2. `nasde eval` with `backend = "cursor"` against that job.

Quality gates per `nasde-dev`: `ruff check`, `ruff format --check`, `mypy`, `pytest`.

## Documentation

- `CHANGELOG.md` `[Unreleased]` — Added: Cursor agent, Cursor judge backend,
  `cursor/` pricing entries, `agent_reported_cost_*` audit fields. Changed:
  price lookup falls back through effort suffixes and provider prefixes. Fixed:
  Cursor cache writes counted in cost.
- `docs/adr/015-cursor-cli-agent-and-judge.md` — thin wrapper, `cursor/`-qualified
  model names, harness-scoped price keys + layered lookup, `--mode ask` + temp
  workspace judge, key-only sandbox auth.
- `README.md`, `CLAUDE.md`, `ARCHITECTURE.md` — agent lists, auth, backend lists,
  package structure.
- Skills: `nasde-benchmark-runner` (`CURSOR_API_KEY`, `--list-models`),
  `nasde-benchmark-creator` (Cursor variant example), `nasde-dev` (Cursor auth in
  the e2e step).
- Scaffold: `NASDE_TOML_TEMPLATE` gains a commented
  `# backend = "claude"  # "claude" | "codex" | "cursor"` line in `[evaluation]`.
- Example: `cursor-vanilla` variant.

## Rollout

Three PRs:

1. **Economics** — `resolve_catalog_key` layered lookup, `cursor/` entries,
   cache-write fallback, audit fields. Independent and useful on its own.
2. **Cursor agent** — `ConfigurableCursor` + runner wiring + example variant.
   Depends on PR 1 for non-null cost.
3. **Cursor judge** — `CursorSubprocessBackend`. Independent of 1 and 2.

Each PR carries its own CHANGELOG entry and doc updates.
