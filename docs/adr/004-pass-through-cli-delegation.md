# ADR-004: Pass-through CLI delegation (Typer add_typer + Click ctx.args)

**Status:** Accepted
**Date:** 2026-03-16

## Context

Harbor and Opik have rich CLIs with utility commands (`harbor view`, `harbor jobs resume`, `opik configure`, `opik usage-report`). We need these accessible through `sdlc-eval` without reimplementing them.

**Complication:** Harbor uses Typer, Opik uses Click. Typer wraps Click, but the integration patterns differ.

## Decision

Two delegation mechanisms:

### Harbor (Typer to Typer)
```python
from harbor.cli.main import app as harbor_app
app.add_typer(harbor_app, name="harbor")
```
Full sub-app integration. `sdlc-eval harbor run` maps to Harbor's `run` command. All subcommands, options, and help text preserved.

### Opik (Click to Typer via ctx.args)
```python
@app.command(
    name="opik",
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
def opik_passthrough(ctx: typer.Context) -> None:
    from opik.cli.main import cli as opik_cli
    opik_cli(ctx.args, standalone_mode=False)
```
Args forwarded as a list to Click's `cli()`. Works for subcommands (`sdlc-eval opik configure`) but Typer intercepts some flags before forwarding (e.g., `--version`).

## Consequences

- Harbor pass-through: full fidelity, including help text and nested subcommands
- Opik pass-through: functional for all subcommands; `sdlc-eval opik --help` shows Typer's help (not Opik's full command list), but `sdlc-eval opik configure --help` shows Opik's help correctly
- No namespace collision: `sdlc-eval run` (ours) vs `sdlc-eval harbor run` (Harbor's) are distinct
- Module-level import of `harbor.cli.main` — acceptable because Harbor is a core dependency
