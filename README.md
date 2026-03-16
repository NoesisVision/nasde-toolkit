# sdlc-eval-kit

CLI toolkit for evaluating AI coding agents. Wraps [Harbor](https://github.com/cased/harbor) (agent execution in sandboxed environments) and [Opik](https://github.com/comet-ml/opik) (observability) into a single `sdlc-eval` command with two-stage evaluation: functional tests + LLM-as-a-Judge architecture assessment.

## Installation

```bash
# As a global tool (recommended)
uv tool install .

# For development
git clone https://github.com/NoesisVision/sdlc-eval-kit.git
cd sdlc-eval-kit
uv sync
```

After installation, only `sdlc-eval` appears on PATH. Harbor, Opik, and Claude Code SDK are bundled as core dependencies — no separate installation needed.

## Quick start

```bash
# Set authentication (one of)
export ANTHROPIC_API_KEY=sk-ant-...
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...

# 1. Scaffold a new evaluation project
sdlc-eval init my-benchmark

# 2. Run benchmark (assessment evaluation runs by default)
sdlc-eval run --variant vanilla -C my-benchmark

# 3. Run specific tasks with Opik tracing
sdlc-eval run --variant vanilla --tasks my-task -C my-benchmark --with-opik

# 4. Skip assessment evaluation (Harbor only)
sdlc-eval run --variant vanilla -C my-benchmark --without-eval

# 5. Re-evaluate an existing job directory
sdlc-eval eval jobs/2026-03-13__14-30-00 --with-opik -C my-benchmark
```

## Two-stage evaluation pipeline

```
sdlc-eval run
    |
    v
  Stage 1: Harbor trial (sandboxed Docker environment)
    - Agent (Claude Code) solves a coding task
    - test.sh runs functional tests -> reward 0.0 or 1.0
    - Artifacts copied to host (jobs/<ts>/<trial>/artifacts/workspace/)
    |
    v
  Stage 2: Assessment evaluation (host, Claude Code SDK)
    - LLM-as-a-Judge analyzes artifacts against rubric
    - Scores N dimensions x 0-25 points each
    - Writes assessment_eval.json
    - Uploads feedback scores to Opik (if --with-opik)
```

Assessment evaluation runs by default because it's the core value of this tool. Use `--without-eval` to skip it when you only need functional test results.

## Commands

### Core

| Command | Description |
|---------|-------------|
| `sdlc-eval run` | Run benchmark: Harbor trial + assessment evaluation (default) |
| `sdlc-eval eval <JOB_DIR>` | Re-run assessment evaluation on an existing job |
| `sdlc-eval init [DIR]` | Scaffold a new evaluation project |

### Pass-through

| Command | Description |
|---------|-------------|
| `sdlc-eval harbor ...` | Full Harbor CLI (view, jobs resume, trials, datasets, etc.) |
| `sdlc-eval opik ...` | Opik CLI (configure, usage-report, export, etc.) |

### `sdlc-eval run` options

| Flag | Description |
|------|-------------|
| `--variant` | Variant to run (defaults to config default) |
| `--tasks` | Comma-separated task names to run |
| `--model` | Model override (e.g. `claude-sonnet-4-6`) |
| `--timeout` | Agent timeout in seconds |
| `--with-opik` | Enable Opik tracing |
| `--without-eval` | Skip assessment evaluation |
| `--project-dir`, `-C` | Path to evaluation project |

## Project structure

A scaffolded project has the following layout:

```
my-benchmark/
  sdlc-eval.toml              # Project configuration
  assessment_dimensions.json   # Scoring dimensions (shared across tasks)
  tasks/
    feature-a/
      task.json                # Task source + evaluation config
      instruction.md           # Agent prompt
      assessment_criteria.md   # Rubric for post-hoc evaluator
      tests/
        test.sh                # Harbor verification script
  variants/
    vanilla/
      CLAUDE.md                # Agent system prompt for this variant
    guided/
      CLAUDE.md
  jobs/                        # Trial output (gitignored)
```

### `sdlc-eval.toml`

```toml
[project]
name = "my-benchmark"
version = "1.0.0"

[defaults]
variant = "vanilla"
model = "claude-sonnet-4-6"
timeout_sec = 720

[docker]
base_image = "ubuntu:22.04"
build_commands = []

[evaluation]
model = "claude-sonnet-4-6"
dimensions_file = "assessment_dimensions.json"

[reporting]
platform = "opik"
project_name = "my-benchmark"
```

## Architecture

See [docs/adr/](docs/adr/) for architectural decision records.

Key design: `sdlc-eval` is a **thin integration layer** over Harbor and Opik, not a replacement. Core flow uses their Python APIs directly; utility commands pass through to their CLIs unchanged.

## Authentication

The tool checks for auth tokens in this order:
1. `ANTHROPIC_API_KEY` environment variable
2. `CLAUDE_CODE_OAUTH_TOKEN` environment variable

For Opik tracing, set credentials in `.env` (in project dir or parent):
```
OPIK_API_KEY=...
OPIK_WORKSPACE=...
OPIK_PROJECT_NAME=...
```

## Prerequisites

- **Python 3.12+**
- **Docker** — Harbor runs agents in Docker containers
- **uv** — Package manager
- **ANTHROPIC_API_KEY** or **CLAUDE_CODE_OAUTH_TOKEN** — Required for agent and evaluator execution

## Verifying Opik results

```python
import urllib.request, json

req = urllib.request.Request(
    "https://www.comet.com/opik/api/v1/private/traces?project_name=<PROJECT>&limit=1",
    headers={
        "authorization": "<OPIK_API_KEY>",
        "Comet-Workspace": "<WORKSPACE>",
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
scores = resp["content"][0].get("feedback_scores", [])
for s in sorted(scores, key=lambda x: x["name"]):
    print(f"  {s['name']}: {s['value']}")
```

Expected feedback scores after a full run with `--with-opik`:
- `arch_<dimension>` (e.g. `arch_domain_modeling`) — normalized 0.0-1.0
- `arch_total` — overall architecture score
- `reward` — Harbor functional test result (0.0 or 1.0)
- `duration_sec` — trial duration
