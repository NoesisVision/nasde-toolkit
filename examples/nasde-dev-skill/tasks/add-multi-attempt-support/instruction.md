# Task: Add Multi-Attempt Support to nasde CLI

## Context

You are working in `/app`, a Python toolkit called `nasde-toolkit` (Noesis Agentic Software Development Evals). The CLI entry point is `nasde`, built with Typer. The main command `nasde run` executes benchmark tasks via the Harbor evaluation framework.

Key files:
- `src/nasde_toolkit/cli.py` — Typer CLI definitions
- `src/nasde_toolkit/runner.py` — Harbor job execution and config merging
- `src/nasde_toolkit/agents/configurable_claude.py` — Custom Harbor agent with sandbox file injection

Read `CLAUDE.md` in the project root for architecture details.

## Requirement

Currently `nasde run` executes each task exactly once. Users need to run multiple independent attempts per task to measure variance in agent performance (e.g., `nasde run -n 3` runs 3 independent trials per task).

Implement:

1. **CLI flag**: Add `--attempts` / `-n` option to `nasde run` (integer, default 1)
2. **Runner propagation**: Pass the attempts count through `run_benchmark()` into the Harbor `JobConfig` as `n_attempts`
3. **Deterministic job naming**: Generate a predictable job directory name using the format `{YYYY-MM-DD__%H-%M-%S}__{variant_name}` so that multiple runs don't collide and are easy to identify
4. **Explicit job directory**: After the Harbor job completes, pass the specific job directory to post-hoc assessment evaluation instead of relying on the "find latest job" heuristic (which breaks when multiple jobs run close together)
5. **Cloud DNS fix**: Cloud sandbox providers (like Daytona) sometimes have DNS resolvers that cannot reach whitelisted domains. Add a DNS resolution fix to `ConfigurableClaude.setup()` that prepends public DNS resolvers (e.g., 8.8.8.8, 1.1.1.1) to `/etc/resolv.conf` if the default resolver fails to resolve `claude.ai`
6. **Display**: Update the CLI header panel to show the attempts count

## Scope

- Modify: `cli.py`, `runner.py`, `configurable_claude.py`
- Do NOT modify: `config.py`, `evaluator.py`, `docker.py`, test files
- Do NOT change existing CLI flags or their defaults

## Quality Expectations

- Follow the existing Typer option patterns in `cli.py` (see `--variant`, `--model`, etc.)
- Match the runner's function signature style (keyword arguments with defaults)
- The DNS fix should be conditional — only apply if default DNS fails
- Keep changes minimal and focused

## Success Criteria

1. `nasde run --help` shows `--attempts` / `-n` flag with help text
2. Running with `-n 2` would create a Harbor job with `n_attempts: 2` in the config
3. Job directory name follows `{timestamp}__{variant}` format
4. Assessment evaluation targets the specific job directory, not "latest"
5. `ConfigurableClaude` has DNS fix that runs before base setup
6. CLI header panel displays the attempts count
7. README.md CLI options table includes `--attempts` flag
