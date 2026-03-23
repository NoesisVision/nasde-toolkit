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

Running multiple variants simultaneously is safe — each job directory includes a unique random suffix to prevent collisions:

```bash
nasde run --variant vanilla --tasks my-task -C path/to/benchmark &
nasde run --variant guided --tasks my-task -C path/to/benchmark &
wait
```

For deterministic job names, use `--job-suffix`:

```bash
nasde run --variant vanilla --job-suffix run1 -C path/to/benchmark
```

### Running Codex variants

Codex variants use `AGENTS.md` (instead of `CLAUDE.md`) and require `CODEX_API_KEY` (standard OpenAI API key from platform.openai.com):

```bash
# Set Codex API key
export CODEX_API_KEY=sk-...

# Run a Codex variant — must specify a Codex-compatible model
nasde run --variant codex-vanilla --model gpt-5-codex -C path/to/benchmark
```

**Supported Codex models** (via API key): `gpt-5-codex`, `gpt-5.3-codex`, `gpt-5.4`, `gpt-5.4-mini`. Models like `codex-mini-latest` or `o3-mini` do NOT work with API keys.

### Cross-agent comparison (Claude vs Codex)

Run all variants (both Claude and Codex) on the same tasks:

```bash
export CODEX_API_KEY=sk-...           # For Codex variants
export CLAUDE_CODE_OAUTH_TOKEN=...     # For Claude variants

nasde run --all-variants -C path/to/benchmark --with-opik
```

Or run specific variants in parallel:

```bash
nasde run --variant vanilla --tasks my-task -C path/to/benchmark --with-opik &
nasde run --variant codex-vanilla --model gpt-5-codex --tasks my-task -C path/to/benchmark --with-opik &
wait
```

### Custom model and timeout

```bash
nasde run --variant baseline --model claude-opus-4-6 --timeout 1200 -C path/to/benchmark
```

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
Always billed per-token via `CODEX_API_KEY`. Always ask before running. Codex uses significantly more input tokens than Claude Code (~1M vs ~250K per task).

Task estimated times are in `task.json` → `estimated_time_minutes`. When `--tasks` filters are used, count only selected tasks.

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
- **`Incorrect API key provided: ''`** — `CODEX_API_KEY` not set or not exported
- **`model 'X' does not exist`** — wrong model name. Use `gpt-5-codex`, `gpt-5.3-codex`, `gpt-5.4`, or `gpt-5.4-mini`
- **`Tool 'web_search_preview' is not supported`** — model doesn't support Codex tools (e.g. `o3-mini`)
- **`Model metadata for 'X' not found`** — warning only, usually followed by the real error

### Trial reward is 0 but code looks correct

Read the verifier output:
```bash
cat jobs/<ts>/<trial>/verifier/test-stdout.txt
```

This shows exactly which step in `test.sh` failed.
