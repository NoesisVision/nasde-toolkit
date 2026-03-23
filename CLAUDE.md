# nasde-toolkit

AI coding agent evaluation toolkit. CLI entry point: `nasde`.

## Package structure

```
src/nasde_toolkit/
  __init__.py              # Package version
  cli.py                   # Typer CLI (init, run, eval + harbor/opik pass-through)
  config.py                # nasde.toml + task.json parsing into dataclasses
  runner.py                # Harbor Python API — variant resolution, config merging, Job execution
  evaluator.py             # Post-hoc assessment via Claude Code SDK
  docker.py                # Docker environment helpers
  scaffold/
    __init__.py            # Project scaffolding templates and file creation
  agents/
    __init__.py
    configurable_claude.py # Harbor-compatible Claude Code agent with sandbox file injection
    configurable_codex.py  # Harbor-compatible Codex agent with sandbox file injection
tests/
pyproject.toml
```

## How to run

```bash
uv tool install .
nasde --version
```

## Testing

```bash
uv run pytest
```

## Code style

1. PEP 8 with type hints on all public functions.
2. `@dataclass` for internal data models (see `config.py`, `evaluator.py`).
3. Rich console for all CLI output — no bare `print()`.
4. Do NOT use comments in method bodies. Use descriptive function and variable names instead.
5. Split large functions into a hierarchy of private helpers with descriptive names.
6. Structure functions: public first (alphabetical), then private helpers ordered by dependency (caller before callee).
7. Snake_case for file and directory names.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system architecture with diagrams (end-to-end flow, trial lifecycle, cloud sandbox providers, assessment evaluation). Keep it in sync with code changes.

## Architecture decisions

- **CLI framework**: Typer with Rich markup mode. The `app` object in `cli.py` is the entry point registered in `pyproject.toml` as `nasde`.
- **Configuration**: Two-layer config — `nasde.toml` for project-level settings, `task.json` per task. Both parsed into `@dataclass` models in `config.py`. Task discovery walks `tasks/` (or `.nasde/tasks/`) automatically.
- **Benchmark runner**: Uses Harbor Python API (`Job`, `JobConfig`) directly instead of subprocess. The runner merges variant config with task registry into a dict, passes it to `JobConfig.model_validate()`, then runs `await job.run()`. Opik tracking via `track_harbor()` (monkey-patches Harbor at runtime).
- **Evaluator**: Uses Claude Code SDK async API to run a Claude agent that reads trial artifacts and scores them against assessment criteria. Configurable via `[evaluation]` in `nasde.toml` — model, tools, MCP servers, skills, and system prompt can all be customized. Default model is `claude-opus-4-6` (best available for review quality). Monkeypatches SDK's `parse_message` to handle unknown message types (remove when SDK fixes this). Results written to `assessment_eval.json` per trial and optionally uploaded to Opik.
- **Variant system**: Each variant is a directory under `variants/` with a required `variant.toml` declaring the agent type (`agent = "claude"` or `agent = "codex"`). For Claude Code variants, `CLAUDE.md` is injected into `/app/CLAUDE.md`; for Codex variants, `AGENTS.md` is injected into `/app/AGENTS.md`. An optional `skills/` subdirectory contains Claude skill snapshots — each `skills/<name>/SKILL.md` is injected into `/app/.claude/skills/<name>/SKILL.md`. An optional `agents_skills/` subdirectory contains Codex skill snapshots — all files under `agents_skills/<name>/` are injected into `/app/.agents/skills/<name>/`. If no `harbor_config.json` exists, one is auto-generated from `variant.toml`.
- **All dependencies are core**: `harbor`, `opik`, `claude-code-sdk` are in `[project.dependencies]`. No optional extras — `uv tool install .` gives full functionality. Assessment evaluation is on by default (`--without-eval` to skip).
- **Auto-generated Dockerfile**: When a task has no `environment/Dockerfile`, nasde generates one from `source.git` + `[docker]`. For local paths, also generates `docker-compose.yaml` to override the build context. See `docker.py:ensure_task_environment()`.
- **Pass-through CLI**: `nasde harbor ...` delegates to Harbor's Typer app via `add_typer()`. `nasde opik ...` forwards args to Opik's Click CLI via `ctx.args`.
- See `docs/adr/` for detailed decision records.

## CLI reference

```
nasde run [OPTIONS]              # Run benchmark (Harbor trial + assessment eval)
  --variant TEXT                     # Variant name (default: from nasde.toml)
  --tasks TEXT                       # Comma-separated task names (default: all)
  --model TEXT                       # Model override
  --timeout INT                      # Agent timeout in seconds
  --with-opik                        # Enable Opik tracing
  --without-eval                     # Skip assessment evaluation
  --job-suffix TEXT                  # Custom suffix for job directory (default: random 6-char hex)
  --harbor-env TEXT                  # Harbor execution environment (docker, daytona, modal, e2b, runloop, gke)
  -C, --project-dir PATH             # Path to benchmark project

nasde eval JOB_DIR [OPTIONS]     # Re-run assessment on existing job
  --with-opik                        # Upload scores to Opik
  -C, --project-dir PATH

nasde init [PROJECT_DIR]         # Scaffold new benchmark project
  -n, --name TEXT

nasde harbor ...                 # Harbor CLI pass-through (view, jobs, trials, etc.)
nasde opik ...                   # Opik CLI pass-through (configure, usage-report, etc.)
```

## Benchmark project structure

A benchmark project managed by `nasde` has this layout:

```
my-benchmark/
  nasde.toml                # Project config (name, defaults, docker, evaluation, reporting)
  assessment_dimensions.json    # Scoring dimensions (benchmark-wide, 3-5 dimensions, sum to 100)
  tasks/
    <task-name>/
      task.json                 # Task metadata for nasde (name, source.git, source.ref, evaluation script)
      task.toml                 # Task metadata for Harbor (version, agent timeout, verifier timeout)
      instruction.md            # Agent-facing task description
      assessment_criteria.md    # Per-task rubric for LLM-as-a-Judge
      environment/Dockerfile    # Docker container setup
      tests/test.sh             # Harbor verifier (writes 0/1 to /logs/verifier/reward.txt)
      solution/solve.sh         # Optional reference solution
  variants/
    <variant-name>/
      variant.toml              # Required: agent type declaration (agent = "claude" or "codex")
      CLAUDE.md                 # Claude Code instructions (injected into /app/CLAUDE.md)
      AGENTS.md                 # Codex instructions (injected into /app/AGENTS.md)
      skills/                   # Optional: Claude skill snapshots (injected into /app/.claude/skills/)
        <skill-name>/
          SKILL.md              # Skill content (snapshot for deterministic testing)
      agents_skills/            # Optional: Codex skill snapshots (injected into /app/.agents/skills/)
        <skill-name>/
          SKILL.md              # Skill content with YAML frontmatter (name + description)
      harbor_config.json        # Optional: agent import path + sandbox_files mapping
      claude_config.json        # Optional: MCP server configuration
  evaluator_skills/             # Optional: skills for the evaluator agent
    <skill-name>/
      SKILL.md
  evaluator_mcp.json            # Optional: MCP server config for the evaluator agent
  jobs/                         # Trial output (gitignored)
```

## Key file formats

### nasde.toml

```toml
[project]
name = "my-benchmark"
version = "1.0.0"

[defaults]
variant = "vanilla"
model = "claude-sonnet-4-6"
timeout_sec = 720
# harbor_env = "daytona"  # Optional: cloud sandbox provider

[docker]
base_image = "ubuntu:22.04"
build_commands = []

[evaluation]
model = "claude-opus-4-6"
dimensions_file = "assessment_dimensions.json"
# max_turns = 30                              # Max evaluator conversation turns
# allowed_tools = ["Read", "Glob", "Grep"]    # Override default tool whitelist
# mcp_config = "./evaluator_mcp.json"         # MCP server config for evaluator
# skills_dir = "./evaluator_skills"           # Skills directory for evaluator
# append_system_prompt = ""                   # Extra system prompt for evaluator

[reporting]
platform = "opik"
project_name = "my-benchmark"
```

### assessment_dimensions.json

```json
{
  "dimensions": [
    {
      "name": "snake_case_name",
      "title": "Human-Readable Title",
      "max_score": 25,
      "description": "What this dimension measures"
    }
  ]
}
```

Dimensions are benchmark-specific. Total scores should sum to 100. Typically 3-5 dimensions.

### task.json

```json
{
  "name": "task-name",
  "source": {
    "git": "https://github.com/org/repo.git",
    "ref": "main"
  },
  "instruction": "./instruction.md",
  "evaluation": {
    "type": "script",
    "script": "./tests/test.sh",
    "timeout_seconds": 300
  }
}
```

**Auto-generated environment:** If `environment/Dockerfile` is absent, nasde auto-generates one from `source.git` + `[docker]` config in `nasde.toml`. For local repos (paths not starting with `http`/`https`/`git`/`file`), the generated Dockerfile uses `COPY . /app` instead of `git clone`, and a `docker-compose.yaml` is also generated to set the Docker build context to the repo root.

### task.toml (required by Harbor)

Harbor reads `task.toml`, not `task.json`. Every task directory MUST have both files.

```toml
version = "1.0"

[metadata]
name = "task-name"
description = "Brief description"
language = "Python"

[agent]
timeout_sec = 1800

[verifier]
timeout_sec = 300
```

### harbor_config.json (per variant)

Claude Code variant:
```json
{
  "agents": [
    {
      "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
      "name": "variant-name",
      "kwargs": {
        "sandbox_files": {
          "/app/CLAUDE.md": "/absolute/path/to/variants/variant-name/CLAUDE.md",
          "/app/.claude/skills/my-skill/SKILL.md": "/absolute/path/to/variants/variant-name/skills/my-skill/SKILL.md"
        }
      }
    }
  ]
}
```

Codex variant:
```json
{
  "agents": [
    {
      "import_path": "nasde_toolkit.agents.configurable_codex:ConfigurableCodex",
      "name": "variant-name",
      "model_name": "o3",
      "kwargs": {
        "sandbox_files": {
          "/app/AGENTS.md": "/absolute/path/to/variants/variant-name/AGENTS.md"
        },
        "reasoning_effort": "high"
      }
    }
  ]
}
```

Critical: `"name"` field is REQUIRED — without it, Opik tagging breaks.
If `harbor_config.json` is absent, `nasde` auto-generates one based on the instruction file present (`CLAUDE.md` → Claude, `AGENTS.md` → Codex).

### tests/test.sh (Harbor verifier)

Every failure path must `echo 0 > /logs/verifier/reward.txt && exit 1`.
Final success must `echo 1 > /logs/verifier/reward.txt && exit 0`.

## Known issues and workarounds

- **claude-code-sdk 0.0.25**: crashes on `rate_limit_event` — runtime monkeypatch in `evaluator.py`. Remove when SDK handles unknown message types.
- **opik 1.10.x**: token usage=None for Harbor spans — file patch in `patches/`. Re-apply after `uv sync`.
- **Nested Claude Code sessions**: SDK detects `CLAUDECODE` env var. Runner unsets it before assessment eval.
- **Opik REST API auth**: use `authorization: <OPIK_API_KEY>` header (not `Comet-Api-Key`), plus `Comet-Workspace` header.
- **Opik verification**: always use Python `urllib.request`, not curl (curl drops the `Comet-Workspace` header).
