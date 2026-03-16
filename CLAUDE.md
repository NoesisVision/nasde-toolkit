# sdlc-eval-kit

AI coding agent evaluation toolkit. CLI entry point: `sdlc-eval`.

## Project Structure

```
src/sdlc_eval_kit/
  __init__.py              # Package version
  cli.py                   # Typer CLI (init, run, eval commands)
  config.py                # sdlc-eval.toml + task.json parsing into dataclasses
  runner.py                # Harbor wrapper — variant resolution, config merging, subprocess
  evaluator.py             # Post-hoc assessment via Claude Code SDK
  docker.py                # Docker environment helpers
  scaffold/
    __init__.py            # Project scaffolding templates and file creation
  agents/
    __init__.py
    configurable_claude.py # Harbor-compatible agent class
tests/
pyproject.toml
```

## How to Run

```bash
uv tool install -e ".[all]"
sdlc-eval --version
```

## Testing

```bash
uv run pytest
```

## Code Style

1. PEP 8 with type hints on all public functions.
2. `@dataclass` for internal data models (see `config.py`, `evaluator.py`).
3. Rich console for all CLI output — no bare `print()`.
4. Do NOT use comments in method bodies. Use descriptive function and variable names instead.
5. Split large functions into a hierarchy of private helpers with descriptive names.
6. Structure functions: public first (alphabetical), then private helpers ordered by dependency (caller before callee).
7. Snake_case for file and directory names.

## Architecture Decisions

- **CLI framework**: Typer with Rich markup mode. The `app` object in `cli.py` is the entry point registered in `pyproject.toml` as `sdlc-eval`.
- **Configuration**: Two-layer config — `sdlc-eval.toml` for project-level settings, `task.json` per task. Both parsed into `@dataclass` models in `config.py`. Task discovery walks `tasks/` (or `.sdlc-eval/tasks/`) automatically.
- **Benchmark runner**: Harbor is invoked via subprocess (`python -m harbor run` or `python -m opik harbor run`). The runner merges variant config with task registry into a temporary JSON config file, then cleans up after execution.
- **Evaluator**: Uses Claude Code SDK async API to run a Claude agent that reads trial artifacts and scores them against assessment criteria. Monkeypatches SDK's `parse_message` to handle unknown message types (remove when SDK fixes this). Results written to `assessment_eval.json` per trial and optionally uploaded to Opik.
- **Variant system**: Each variant is a directory under `variants/`. The `CLAUDE.md` inside is injected into the Harbor sandbox. If no `harbor_config.json` exists, one is auto-generated.
- **Optional dependencies**: `harbor-ai`, `opik`, `claude-code-sdk` are extras in `pyproject.toml`. Core CLI works without them; features degrade gracefully with import guards.
