# sdlc-eval-kit

AI coding agent evaluation toolkit. Provides a CLI (`sdlc-eval`) for scaffolding benchmark projects, running AI agents against coding tasks via [Harbor](https://github.com/cased/harbor), and scoring their output with a Claude-based post-hoc evaluator.

## Installation

```bash
# From GitHub
uv tool install git+https://github.com/<org>/sdlc-eval-kit.git

# For development
git clone https://github.com/<org>/sdlc-eval-kit.git
cd sdlc-eval-kit
uv tool install -e ".[all]"

# As a project dependency
uv add git+https://github.com/<org>/sdlc-eval-kit.git
```

After installation the `sdlc-eval` command is available globally.

## Quick Start

```bash
# 1. Scaffold a new evaluation project
sdlc-eval init my-benchmark

# 2. Configure tasks — edit tasks/*/task.json (set source.git + source.ref)
#    Write instruction.md, assessment_criteria.md, and tests/test.sh per task
#    Create variant prompt files in variants/*/CLAUDE.md

# 3. Run a benchmark
sdlc-eval run --variant vanilla --tasks my-task

# 4. Run with Opik tracing and post-hoc evaluation
sdlc-eval run --with-opik --with-eval

# 5. Evaluate an existing job directory
sdlc-eval eval jobs/2026-03-13__14-30-00 --with-opik
```

## Project Structure

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
    feature-b/
      ...
  variants/
    vanilla/
      CLAUDE.md                # Agent system prompt for this variant
    guided/
      CLAUDE.md
  jobs/                        # Trial output (gitignored)
    2026-03-13__14-30-00/
      trial-001/
        result.json
        config.json
        artifacts/workspace/
        assessment_eval.json
```

### `sdlc-eval.toml`

Top-level configuration file. Defines project name, default variant, model, timeout, Docker base image, evaluation model, and reporting settings (Opik project name).

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

## Task Configuration

Each task lives in `tasks/<task-name>/` and must contain a `task.json`:

```json
{
  "name": "feature-a",
  "source": {
    "git": "https://github.com/org/repo.git",
    "ref": "abc1234"
  },
  "instruction": "./instruction.md",
  "evaluation": {
    "type": "script",
    "script": "./tests/test.sh",
    "timeout_seconds": 300
  }
}
```

- **`source.git`** -- Git repository URL for the codebase the agent works on.
- **`source.ref`** -- A specific commit, tag, or branch. Always pin to a concrete ref for reproducibility.
- **`instruction`** -- Path to the Markdown file describing the task for the agent.
- **`evaluation.script`** -- Harbor verification script. Must write a reward value (0 or 1) to `/logs/verifier/reward.txt`.

Each task should also include:
- `assessment_criteria.md` -- Rubric used by the post-hoc Claude evaluator.
- Optionally `ground_truth_decisions.json` -- Reference data for evaluator accuracy checks.

## Variant Matrix

Variants let you test different agent prompts and configurations against the same tasks.

Each variant lives in `variants/<variant-name>/` and contains at minimum a `CLAUDE.md` file. This file is injected into the agent's sandbox as `/app/CLAUDE.md` at runtime, giving the agent variant-specific instructions.

Additional files in the variant directory can be injected via `sandbox_files` in `harbor_config.json`. If no `harbor_config.json` exists, one is generated automatically from the `CLAUDE.md`.

Run a specific variant:

```bash
sdlc-eval run --variant guided
```

## CLI Reference

### `sdlc-eval init [PROJECT_DIR]`

Scaffold a new evaluation project with example task, variant, and configuration files.

| Flag | Description |
|------|-------------|
| `--name`, `-n` | Project name (defaults to directory name) |

### `sdlc-eval run`

Run benchmark tasks via Harbor.

| Flag | Description |
|------|-------------|
| `--variant` | Variant to run (defaults to config default) |
| `--tasks` | Comma-separated task names to run |
| `--model` | Model override (e.g. `claude-sonnet-4-6`) |
| `--timeout` | Agent timeout in seconds |
| `--with-opik` | Enable Opik tracing |
| `--with-eval` | Run post-hoc assessment after benchmark |
| `--project-dir`, `-C` | Path to evaluation project |

### `sdlc-eval eval <JOB_DIR>`

Run post-hoc assessment evaluation on existing trial artifacts.

| Flag | Description |
|------|-------------|
| `--with-opik` | Upload scores to Opik |
| `--project-dir`, `-C` | Path to evaluation project |

### `sdlc-eval --version`

Print version and exit.

## Prerequisites

- **Python 3.11+**
- **Docker** -- Harbor runs agents in Docker containers
- **uv** -- Package manager
- **harbor-ai** -- Agent runner (`pip install harbor-ai` or install with `.[harbor]`)

Optional, depending on features used:

- **opik** -- Tracing and score reporting (`.[opik]`)
- **claude-code-sdk** -- Post-hoc evaluator (`.[eval]`)
- **ANTHROPIC_API_KEY** or **CLAUDE_CODE_OAUTH_TOKEN** -- Required for agent and evaluator execution

Install all optional dependencies at once:

```bash
uv tool install -e ".[all]"
```
