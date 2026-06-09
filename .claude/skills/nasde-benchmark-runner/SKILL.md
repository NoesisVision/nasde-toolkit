---
name: nasde-benchmark-runner
description: |
  Run coding agent benchmarks and verify results with nasde. Use this skill when the user wants to:
  - Run a benchmark (all tasks, single task, specific variant)
  - Re-run assessment evaluation on existing trial results
  - Check or verify results in Opik (traces, feedback scores, experiments)
  - Troubleshoot a failed benchmark run
  - View or compare trial results
  Even if the user doesn't say "benchmark" — if they're talking about running evaluations, checking scores, or analyzing agent performance, this skill applies.
  After every run that uses --with-opik, ALWAYS verify results via Opik REST API — don't wait for the user to ask.
---

# NASDE Benchmark Runner

Run coding agent benchmarks with `nasde` and verify results. The two-stage pipeline: Harbor runs agents in Docker containers (functional test → reward 0/1), then an LLM-as-a-Judge scores architecture quality across multiple dimensions.

## Authentication setup

Before running any benchmark, set up authentication tokens for the agents you plan to run. Both OS and auth method matter — pick the right command per row.

### Step 1 — Ask the user which auth they prefer

**Always ask the user before running, never assume.** Two questions:

1. **Which agents will you run?** (Claude / Codex / Gemini, any combination)
2. **For each agent, OAuth (subscription) or API key (per-token billing)?** Default recommendation: OAuth where available — no per-token cost, no env vars to manage.

Then detect their OS and pick the matching script row from the table below. On Windows, also ask whether they're in **PowerShell** or **WSL** (cmd.exe is not directly supported — see "Windows: cmd.exe" below).

### Where the auth scripts live

The OAuth scripts ship inside this skill. After `nasde install-skills` they are at:

- **User scope** (default): `~/.claude/skills/nasde-benchmark-runner/scripts/` (macOS/Linux/WSL) or `%USERPROFILE%\.claude\skills\nasde-benchmark-runner\scripts\` (Windows PowerShell)
- **Project scope**: `<project>/.claude/skills/nasde-benchmark-runner/scripts/` (if installed with `nasde install-skills --scope project`)
- **Editable nasde checkout** (devs only): `<repo>/scripts/` — same files, mirrored from the skill bundle

Below, `<SKILL_SCRIPTS>` is shorthand for whichever absolute path applies. Resolve it once, then substitute it in every command. Verify the path with `ls <SKILL_SCRIPTS>` before telling the user to source anything — if the directory is missing, they need to run `nasde install-skills` first.

### Step 2 — Run the right script per agent × OS

Priority order: **Claude → Codex → Gemini.** Claude is required even for non-Claude variants when `[evaluation] backend = "claude"` (default), because the assessment evaluator spawns `claude` CLI as a subprocess.

#### Claude Code

| OS / shell | OAuth (subscription) | API key |
|---|---|---|
| macOS | `source <SKILL_SCRIPTS>/export_oauth_token.sh` (reads Keychain entry "Claude Code-credentials") | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Linux | `source <SKILL_SCRIPTS>/export_oauth_token.sh` (reads `~/.claude/.credentials.json`) | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Windows PowerShell | `. <SKILL_SCRIPTS>\export_oauth_token.ps1` (reads `%USERPROFILE%\.claude\.credentials.json`) | `$env:ANTHROPIC_API_KEY = 'sk-ant-...'` |
| Windows WSL (Ubuntu) | `source <SKILL_SCRIPTS>/export_oauth_token.sh` (Linux path; resolve `<SKILL_SCRIPTS>` from your WSL home, not the Windows host's) | `export ANTHROPIC_API_KEY=sk-ant-...` |

Prerequisite for OAuth: `claude` CLI installed and `claude` ran once to log in.

The script exports `CLAUDE_CODE_OAUTH_TOKEN`. This is required for both Claude variant runs AND assessment evaluation (when `[evaluation] backend = "claude"` — the default).

#### Codex

| OS / shell | OAuth (ChatGPT subscription) | API key |
|---|---|---|
| macOS | `codex login` once, then `source <SKILL_SCRIPTS>/export_codex_oauth_token.sh` | `export CODEX_API_KEY=sk-proj-...` (or `OPENAI_API_KEY`) |
| Linux | `codex login` once, then `source <SKILL_SCRIPTS>/export_codex_oauth_token.sh` | `export CODEX_API_KEY=sk-proj-...` |
| Windows PowerShell | `codex login` once, then `. <SKILL_SCRIPTS>\export_codex_oauth_token.ps1` | `$env:CODEX_API_KEY = 'sk-proj-...'` |
| Windows WSL (Ubuntu) | `codex login` once, then `source <SKILL_SCRIPTS>/export_codex_oauth_token.sh` | `export CODEX_API_KEY=sk-proj-...` |

The OAuth scripts only **validate** `~/.codex/auth.json` (or `%USERPROFILE%\.codex\auth.json`) — `nasde` then opts Harbor into uploading it into the sandbox (it sets `CODEX_FORCE_AUTH_JSON=true` when no API key is present but the file exists; harbor 0.13's Codex agent otherwise defaults to `OPENAI_API_KEY` and would write an empty key). API key always takes priority over OAuth when both are present.

#### Gemini CLI

| OS / shell | OAuth (Google account) | API key |
|---|---|---|
| macOS | `gemini login` once, then `source <SKILL_SCRIPTS>/export_gemini_oauth_token.sh` | `export GEMINI_API_KEY=...` |
| Linux | `gemini login` once, then `source <SKILL_SCRIPTS>/export_gemini_oauth_token.sh` | `export GEMINI_API_KEY=...` |
| Windows PowerShell | `gemini login` once, then `. <SKILL_SCRIPTS>\export_gemini_oauth_token.ps1` | `$env:GEMINI_API_KEY = '...'` |
| Windows WSL (Ubuntu) | `gemini login` once, then `source <SKILL_SCRIPTS>/export_gemini_oauth_token.sh` | `export GEMINI_API_KEY=...` |

The OAuth scripts export `GEMINI_OAUTH_CREDS` (the raw JSON) — `ConfigurableGemini` reads that env var and injects credentials into the sandbox. API key always takes priority over OAuth.

### Combined setup for cross-agent runs

Resolve `<SKILL_SCRIPTS>` first, then run all three.

**macOS / Linux / Windows WSL:**
```bash
SKILL_SCRIPTS=~/.claude/skills/nasde-benchmark-runner/scripts   # adjust if --scope project
source $SKILL_SCRIPTS/export_oauth_token.sh         # Claude (subscription)
source $SKILL_SCRIPTS/export_codex_oauth_token.sh   # Codex (subscription) — or: export CODEX_API_KEY=...
source $SKILL_SCRIPTS/export_gemini_oauth_token.sh  # Gemini (Google account) — or: export GEMINI_API_KEY=...
```

**Windows PowerShell:**
```powershell
$SkillScripts = "$env:USERPROFILE\.claude\skills\nasde-benchmark-runner\scripts"
. "$SkillScripts\export_oauth_token.ps1"
. "$SkillScripts\export_codex_oauth_token.ps1"
. "$SkillScripts\export_gemini_oauth_token.ps1"
```

### Windows: cmd.exe

cmd.exe is **not supported directly** — `.ps1` requires PowerShell, `.sh` requires bash. Two workarounds:

1. **Open PowerShell** (`powershell.exe`) and dot-source the `.ps1` script. This is the simplest path on a vanilla Windows install.
2. **Use WSL** (`wsl -d Ubuntu`) and source the `.sh` script. This is the recommended path if you also want Docker Desktop with the WSL2 backend, which is the most common dev setup.

If a user is in cmd.exe, point them to one of these two — don't try to extract the token manually.

### Important: chain auth into the run command

Exported env vars (`CLAUDE_CODE_OAUTH_TOKEN`, etc.) **do not persist across separate
shell invocations** — every command in an automated runner (and every separate terminal
call) is a fresh shell, so a lone `source ...` in one step is gone by the next. When
running non-interactively, **chain the `source` script(s) and the `nasde` call in a single
command** with `&&`:

```bash
# bash/zsh — both tokens chained into one invocation
source $SKILL_SCRIPTS/export_codex_oauth_token.sh && source $SKILL_SCRIPTS/export_oauth_token.sh && \
  nasde run --variant codex-vanilla --tasks my-task -C path/to/benchmark
```

Chain exactly the scripts the run needs: the agent's token (claude/codex/gemini) **and**
the evaluator's token — the evaluator uses `[evaluation] backend` from `nasde.toml`, which
defaults to `claude`, so a codex/gemini run with the default evaluator still needs
`export_oauth_token.sh` too. In an interactive terminal session a one-time `source` in the
same session is fine; the chaining rule matters for scripts, CI, and tool-driven runs.

## Running benchmarks

All commands assume `-C` points to the benchmark project directory.

### Basic run (all tasks, default variant)

```bash
nasde run -C path/to/benchmark
```

Assessment evaluation runs by default. This is the standard workflow.

### Specific variant and tasks

```bash
# Single task, specific variant
nasde run --variant guided --tasks my-task -C path/to/benchmark

# Multiple tasks
nasde run --variant baseline --tasks task-a,task-b -C path/to/benchmark
```

### With Opik tracing

```bash
nasde run --variant baseline --tasks my-task -C path/to/benchmark --with-opik
```

After this completes, ALWAYS verify Opik results (see Opik verification below).

### Harbor only (skip assessment)

```bash
nasde run --variant baseline -C path/to/benchmark --without-eval
```

### Parallel runs (multiple variants)

**Do not use `--all-variants` when you want parallelism.** `--all-variants` runs variants **sequentially** in a single process (one variant after another). To run two or more variants in parallel, launch separate `nasde run` processes with `&` and `wait` — each job directory gets a unique random suffix, so concurrent runs are collision-safe:

```bash
nasde run --variant vanilla --tasks my-task -C path/to/benchmark &
nasde run --variant guided --tasks my-task -C path/to/benchmark &
wait
```

Use `--all-variants` only when you want one variant after another (e.g. to limit total resource use, or when running Claude variants where parallel runs risk Docker OOM — see warning below).

For deterministic job names, use `--job-suffix`:

```bash
nasde run --variant vanilla --job-suffix run1 -C path/to/benchmark
```

### Running Codex variants

Codex variants use `AGENTS.md` (instead of `CLAUDE.md`) and require either `codex login` (ChatGPT subscription) or `CODEX_API_KEY`/`OPENAI_API_KEY` (API billing).

**CRITICAL: Codex model must be set explicitly.** The `nasde.toml` default model (e.g. `claude-sonnet-4-6`) is designed for Claude and will be passed to Codex if not overridden. Codex CLI will silently accept invalid model names but produce garbage results (0% pass rate). Always set the model via `--model` flag or in `variant.toml`.

```bash
# Option A: ChatGPT subscription (no env vars needed after codex login)
nasde run --variant codex-vanilla --model gpt-5.3-codex -C path/to/benchmark

# Option B: API key
export $(grep CODEX_API_KEY .env)
nasde run --variant codex-vanilla --model gpt-5.3-codex -C path/to/benchmark
```

**Codex models** (recommended first, as of 2026-03):
- `gpt-5.4` — flagship frontier model, best overall for professional work
- `gpt-5.4-mini` — fast, efficient mini model for responsive coding and subagents
- `gpt-5.3-codex` — industry-leading coding model for complex software engineering
- `gpt-5.3-codex-spark` — near-instant real-time coding iteration (ChatGPT Pro only)

Older alternatives: `gpt-5.2-codex`, `gpt-5.1-codex`, `gpt-5-codex`, `gpt-5-codex-mini`

Codex supports any model compatible with the Responses API. Chat Completions API support is deprecated.

**Setting model in variant.toml** (preferred over --model flag):
```toml
agent = "codex"
model = "gpt-5.4"
```
This avoids accidentally inheriting the Claude model from `nasde.toml`.

### Running Gemini CLI variants

Gemini variants use `GEMINI.md` (instead of `CLAUDE.md`) and require either `gemini login` (Google account) or `GEMINI_API_KEY`/`GOOGLE_API_KEY` (API billing).

**CRITICAL: Gemini model must use `google/` prefix.** Harbor requires model names in `provider/model_name` format. Always set via `--model` flag or in `variant.toml`.

```bash
# Option A: Google account OAuth (no env vars needed after gemini login)
nasde run --variant gemini-vanilla --model google/gemini-3-flash-preview -C path/to/benchmark

# Option B: API key
export GEMINI_API_KEY=your-key
nasde run --variant gemini-vanilla --model google/gemini-3-flash-preview -C path/to/benchmark
```

**Gemini models** (recommended first, as of 2026-03):
- `google/gemini-3.1-pro-preview` — advanced thinking model, deep reasoning
- `google/gemini-3-flash-preview` — best quality/speed ratio, daily coding
- `google/gemini-3.1-flash-lite-preview` — fastest, simple tasks

**Setting model in variant.toml** (preferred over --model flag):
```toml
agent = "gemini"
model = "google/gemini-3-flash-preview"
```

### Cross-agent comparison (Claude vs Codex vs Gemini)

Set up all auth tokens first (see Authentication setup above), then run:

```bash
source scripts/export_oauth_token.sh && export $(grep CODEX_API_KEY .env) && source scripts/export_gemini_oauth_token.sh

# Run Claude, Codex, and Gemini variants — non-Claude MUST have --model override
nasde run --variant claude-vanilla -C path/to/benchmark --with-opik &
nasde run --variant codex-vanilla --model gpt-5.3-codex -C path/to/benchmark --with-opik &
nasde run --variant gemini-vanilla --model google/gemini-3-flash-preview -C path/to/benchmark --with-opik &
wait
```

**WARNING**: Running Claude variants in parallel can cause OOM (exit code 137) in Docker. Claude Code containers are memory-heavy (~2-4 GB each). Run Claude variants sequentially, or increase Docker Desktop memory to 16+ GB.

### Custom model and timeout

```bash
nasde run --variant baseline --model claude-opus-4-7 --timeout 1200 -C path/to/benchmark
```

**Timeout priority**: `--timeout` flag overrides everything. Without it, Harbor uses `task.toml [agent] timeout_sec` per task. Timeouts are per-task only — there is no project-wide default in nasde.toml.

### Re-evaluate existing results

```bash
nasde eval path/to/benchmark/jobs/2026-03-16__14-05-58 --with-opik -C path/to/benchmark
```

## Token cost heuristic

**Claude Code variants:**
When using `CLAUDE_CODE_OAUTH_TOKEN` (Claude subscription — no per-token cost):
- **Run freely**: total estimated time under 30 minutes (sum of tasks × variants)
- **Ask first**: over 30 minutes, OR when using `ANTHROPIC_API_KEY` (API billing)

**Codex variants:**
- **ChatGPT OAuth** (`codex login`): uses subscription credits, no per-token cost. Same heuristic as Claude subscription — run freely under 30 minutes.
- **API key** (`CODEX_API_KEY`): billed per-token. Always ask before running. Codex uses significantly more input tokens than Claude Code (~1M vs ~250K per task).

**Gemini CLI variants:**
- **Google account OAuth** (`gemini login`): free tier via Gemini Code Assist license (1M token context). Run freely.
- **API key** (`GEMINI_API_KEY`): billed per-token through Google AI Studio. Ask before running.
- **Vertex AI** (`GOOGLE_API_KEY`): billed through Google Cloud. Ask before running.

Task estimated times are derived from `task.toml [agent] timeout_sec` (timeout_sec / 60 is a rough upper bound; agents typically finish faster). When `--tasks` filters are used, count only selected tasks.

## Viewing results

After a run, results are in `jobs/<timestamp>/`:

```bash
# Job summary
cat jobs/<timestamp>/result.json | python3 -m json.tool

# Per-trial results
cat jobs/<timestamp>/<trial-id>/result.json | python3 -m json.tool

# Verifier output (what test.sh printed)
cat jobs/<timestamp>/<trial-id>/verifier/test-stdout.txt

# Assessment scores
cat jobs/<timestamp>/<trial-id>/assessment_eval.json | python3 -m json.tool
```

### Using Harbor CLI for viewing

```bash
nasde harbor view path/to/benchmark/jobs/<timestamp>
```

## Comparing models — quality vs cost / tokens (PRIMARY method)

When the user asks "which model/agent is best?" or "which is most efficient?", the answer is a **two-axis scatter (quality vs cost, quality vs tokens)**, not a single ranked number. Show the data honestly and let the reader judge — the convention here follows charts like Artificial Analysis's intelligence-vs-tokens plots: **raw points with full names, a shaded "most attractive" region, an arrow pointing toward "better", and no verdict painted on individual points.** Two reasons this is the primary method:

1. **Quality and cost are two axes, and you keep both.** Collapsing them into one number throws away information. *Pareto dominance* is the concept you reason **with** (point A is dominated if some B is no-worse on both axes and strictly better on one), but it is **not** a tag stamped on the chart — at small n a hard "dominated / never pick" label on a point with no variance over-claims. State dominance in prose when it is clear from the data; let the chart stay raw.
2. **Position is invariant to where you put the score zero.** That is exactly why nasde deliberately does **not** compute a scalar "token efficiency" or "cost efficiency" (`score / denominator`). See "Why no scalar efficiency" below.

### Two panels — report BOTH

Always draw and report both panels:

- **Quality × cost ($)** — *price-dependent*. Uses `cost_usd`, which moves with the price catalog (`pricing.toml`).
- **Quality × tokens** — *price-independent*. Uses `token_usage` (output tokens by default on a log axis, the Artificial Analysis convention; total tokens optional). Pure model behaviour, stable across price changes.

When both panels tell the same story, the conclusion is stronger. When they disagree (e.g. a model is token-light but expensive due to a high per-token price), say so explicitly — that disagreement is itself the finding.

### Hard scoping rules — do NOT violate

Compare points **only** within:

- **ONE task.** Never aggregate across tasks of different difficulty into a single number. This is the **paired-difference principle**: report per-task deltas against a shared baseline, never a cross-task mean. An easy task and a hard task averaged together is a meaningless number.
- **The same `dimensions_fingerprint`.** A changed rubric (added/removed dimension, changed `max_score`, changed `description`) is a different benchmark and its scores are not comparable.
- **The same `reasoning_effort`.** Effort is part of the comparison axis. The toolkit groups economics by `(agent_name, model_name, reasoning_effort)`. A trial's artifacts carry a `reasoning_effort` stamp (a string; empty `""` means "not overridden — the Harbor family default"). `gpt-5.3-codex` at `high` and at `low` are two different points, not one.

If the points you are about to plot span more than one task, fingerprint, or effort, **split them into separate charts** — one Pareto chart per `(task, fingerprint, effort)` cell.

### Sample size — n=1 is a signal, not a conclusion

- **n=1** (a single trial) has **no variance** — it is a *preliminary signal*, never a conclusion. Label it as such.
- **n≥2** gives the inter-trial std that the toolkit now reports (per model group). You need n≥2 before claiming a model "beats" another; a 0.02 score gap with no std is noise.

### Source of truth

The raw numbers come straight from `nasde results-export` (see below). For each trial:

- `score` — `normalized_score_mean` in `assessment_summary.json` (or `normalized_score` / `score`).
- `token_usage.output_tokens` / `token_usage.total_tokens` — in `metrics.json` (and mirrored on the summary). Output tokens is the default token axis; total is available via `--token-axis total`.
- `cost_usd` — in `metrics.json`. `null` for an unpriced/legacy-trajectory model — such a point is dropped from the cost panel but still appears on the token panel.
- `reasoning_effort`, `model_name`, `agent_name`, `task_name` — stamped on the artifacts; the first three define the group, `task_name` enforces the one-task scope.

Export first, then compare — **the export step is required, not optional**: it is the single place that computes per-trial cost and token economics (from `agent/trajectory.json` + the price catalog; ADR-011) and flattens the nested `jobs/<job>/<trial>/` tree into one dir per trial. A raw `jobs/` dir has no `metrics.json` and is two levels deep, so the generator reads only exported dirs (or explicit `--point`s) — never raw `jobs/`.

```bash
nasde results-export path/to/benchmark/jobs/<timestamp> --to /tmp/myexport -C path/to/benchmark
```

### Generating the chart

The skill ships a reference generator at `<SKILL_SCRIPTS>/pareto.py` (matplotlib + stdlib only — install matplotlib into whatever Python you run it with, e.g. `uv run --with matplotlib python <SKILL_SCRIPTS>/pareto.py ...`). It reads an export dir directly, or accepts explicit data points, and draws both panels in the raw-points style (a green shaded region marks the most attractive corner — high quality, low cost/tokens — no front line, no dominated tags). Visual encoding for the skill×model matrix: **color = provider**, **marker shape = skill** (circle = vanilla, a distinct shape per skill — assigned stably, so the same skill keeps its shape across providers and both panels), and a **thin line links the variants of one model**, so the quality/cost shift from adding a skill to a given model is visible at a glance. The model name is labelled once per model — at its **lowest point** (the variant with the lowest score) — so a model with several variants is not labelled repeatedly; the connecting line and marker shape identify the other variants. A single shared **encoding legend** sits to the right of both panels (provider colors + a shape-per-skill list with the real skill names). The shape palette holds ~10 skills; beyond that shapes repeat and the generator prints a warning (read the labels/legend to disambiguate) — it never collides shapes silently.

```bash
# From an export dir (one subdir per trial). --task scopes a multi-task export to one task.
# Title MUST state the scope (task, fingerprint, effort).
uv run --with matplotlib python <SKILL_SCRIPTS>/pareto.py \
  --export-dir /path/to/nasde-results \
  --task ddd-weather-discount \
  --title "weather-discount — fp=abc123def456 — effort=default" \
  --out /tmp/quality_chart.png

# Or explicit points: name,effort,score,cost_usd,output_tokens (cost may be empty for unpriced).
uv run --with matplotlib python <SKILL_SCRIPTS>/pareto.py \
  --point "claude-opus-4-8,,0.92,26.30,69055" \
  --point "claude-sonnet-4-6,,0.80,8.55,33430" \
  --out /tmp/quality_chart.png
```

`--token-axis {output,total}` picks the token panel's x-axis (default `output`, log scale). Trials are grouped by `(agent_name, model_name, reasoning_effort)` — the same key the toolkit uses for run-summary economics — so two variants of the *same* model (e.g. `claude-vanilla` vs `claude-ntcoding-tactical-ddd`, both on `claude-sonnet-4-6`) stay separate points, not one averaged blob. Each group's per-axis std is printed to stdout (n≥2), with an `[n=1 preliminary signal]` flag otherwise. (With `--point` you have no separate agent field, so the point name doubles as the variant.)

### Chart rule — full model version strings, always

- **Never** use bare family names ("sonnet", "opus", "gpt") in labels or legends. **Always** the full version string: `claude-sonnet-4-6`, `claude-opus-4-8`, `gpt-5.3-codex`, `google/gemini-3-flash-preview`.
- **The reasoning effort must be visible** on the chart/legend too (the generator prints `effort=<value>` per point; `default` when the stamp is empty).

### Why no scalar "efficiency"

It is tempting to collapse the picture into one number — `efficiency = score / cost` or `score / tokens` — and rank by it. nasde deliberately does **not**, for two reasons:

1. **It is lossy.** It crushes a 2D trade-off (quality vs cost) into one scalar, hiding *which* axis a model wins on. A buyer choosing between "cheap and decent" and "expensive and excellent" needs both numbers, not their ratio.
2. **It has an arbitrary zero.** `score` is a normalized rubric score whose zero is "empty rubric" — an unreachable, arbitrary reference point. Because the ratio divides by a denominator from that arbitrary zero, the *ranking is not invariant to a baseline shift*: the same trials can produce a different "winner" depending only on where you place the score zero. A Pareto front does not move when you shift the score axis, so it is the honest comparison. (This is a locked design decision — do not reintroduce a scalar efficiency.)

### Optional secondary helper — baseline-relative Δscore

For a *single task*, it is fine to report each variant's **Δscore against the vanilla baseline on that same task** (`score_variant − score_vanilla`). That is a paired difference against a shared reference and is legitimate. What is **not** legitimate is a scalar `score/$` measured from zero — that is the arbitrary-zero ratio above. Keep Δscore as a supporting view; the Pareto front stays primary.

## Opik verification

After every run with `--with-opik`, verify results via REST API. This is mandatory — Opik has known issues with long-running trials where data may not arrive completely.

### Verification script

Use Python `urllib.request` (never curl — it drops the `Comet-Workspace` header):

```python
python3 -c "
import urllib.request, json

req = urllib.request.Request(
    'https://www.comet.com/opik/api/v1/private/traces?project_name=<PROJECT_NAME>&limit=1',
    headers={
        'authorization': '<OPIK_API_KEY>',
        'Comet-Workspace': '<OPIK_WORKSPACE>',
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
trace = resp['content'][0]
print(f'Trace: {trace[\"name\"]}')
print(f'ID:    {trace[\"id\"]}')
print()
for s in sorted(trace.get('feedback_scores', []), key=lambda x: x['name']):
    print(f'  {s[\"name\"]}: {s[\"value\"]}')
"
```

Credentials are in the benchmark's `.env` file (or parent directory).

### What to check

For each trace, verify:

1. **Feedback scores present** — should include:
   - `reward` (from Harbor verifier: 0.0 or 1.0)
   - `duration_sec` (trial execution time)
   - `arch_<dimension>` for each assessment dimension (normalized 0.0-1.0)
   - `arch_total` (overall normalized score)
2. **Trace name format**: `<agent-name>/<trial-name>` (e.g. `baseline/ddd-threshold-discount__4tTaKwg`)
3. **Tags**: should include `harbor` and the variant name

### Finding trace IDs

The trace ID is printed during the run:
```
OPIK: Started logging traces to ... ?trace_id=<TRACE_ID>&...
```

Or search by project:
```python
import opik
client = opik.Opik()
traces = client.search_traces(
    project_name='<benchmark-name>',
    filter_string='name = "<agent-name>/<trial-name>"',
    max_results=1,
    wait_for_at_least=1,
    wait_for_timeout=10,
)
```

## Troubleshooting

### "No module named 'evals'" or import errors

Harbor resolves `import_path` from `harbor_config.json` via `importlib`. If using the built-in agent (`nasde_toolkit.agents.configurable_claude:ConfigurableClaude`), this works when nasde-toolkit is installed. For custom agents, ensure the module is on `sys.path`.

### Docker build fails

Test the Dockerfile independently:
```bash
docker build -t test-env -f tasks/<task>/environment/Dockerfile .
docker run --rm -it test-env bash
```

### Assessment eval fails with "No artifacts/workspace/"

Harbor didn't copy artifacts. Check:
- The `artifacts` config in the merged Harbor config (source path must match container layout)
- The trial log: `jobs/<ts>/<trial>/trial.log`

### Opik scores missing after --with-opik

1. Check trace exists: use the REST API verification script above
2. If trace exists but no `arch_*` scores: assessment eval didn't run or failed. Check the CLI output for errors.
3. If no trace at all: Opik tracking wasn't enabled. Verify `.env` has `OPIK_API_KEY` and `OPIK_WORKSPACE`.

### Codex trial fails immediately (reward 0, 0/100)

Check the agent log for errors:
```bash
head -20 jobs/<ts>/<trial>/agent/codex.txt
```

Common causes:
- **`Incorrect API key provided: ''`** — no auth configured. Either run `codex login` (ChatGPT subscription) or set `CODEX_API_KEY`: `export $(grep CODEX_API_KEY .env)`
- **`model 'X' does not exist`** — wrong model name. Use `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, or `gpt-5.3-codex-spark`
- **0% pass rate, low scores, but trials completed** — likely inherited Claude model name (e.g. `claude-sonnet-4-6`) instead of OpenAI model. Check `config.json` in the job dir for `model_name`. Fix by adding `model = "gpt-5.3-codex"` to `variant.toml` or using `--model gpt-5.3-codex`
- **`Tool 'web_search_preview' is not supported`** — model doesn't support Codex tools
- **`Model metadata for 'X' not found`** — warning only, usually followed by the real error

### Gemini trial fails immediately (reward 0, 0/100)

Check the agent log for errors:
```bash
head -20 jobs/<ts>/<trial>/agent/gemini-cli.txt
```

Common causes:
- **`GEMINI_API_KEY is not set`** — no auth configured. Either run `gemini login` or set `GEMINI_API_KEY`
- **`Model name must be in the format provider/model_name`** — model must include `google/` prefix (e.g. `google/gemini-3-flash-preview`)
- **Node.js errors** — Gemini CLI requires Node.js 22+. Check the Docker image includes nvm setup
- **DNS resolution failures** — cloud sandboxes may not resolve `generativelanguage.googleapis.com`. ConfigurableGemini auto-fixes this, but custom configs may not

### Trial reward is 0 but code looks correct

Read the verifier output:
```bash
cat jobs/<ts>/<trial>/verifier/test-stdout.txt
```

This shows exactly which step in `test.sh` failed.
