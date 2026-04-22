# Dependency modernization for public release

**Date:** 2026-04-22
**Status:** Approved

## Goal

Upgrade `nasde-toolkit` to the latest `harbor` and `opik` majors, eliminate all
known CVEs in the transitive dependency tree, and add a CI gate that prevents
regression to vulnerable versions. Result: the repo is safe to publish
publicly.

## Context

The `nasde-toolkit` currently pins `harbor>=0.1.40,<0.2` and `opik>=1.10,<2`.
An OSV batch audit of the locked tree surfaced 8 packages with 20 vulnerabilities,
including 1 CRITICAL and 3 HIGH:

| Package | Current | Severity | Fixed in |
| --- | --- | --- | --- |
| litellm | 1.82.2 | CRITICAL (OIDC auth bypass), HIGH (priv-esc), HIGH (password hash exposure) | 1.83.0 |
| cbor2 | 5.8.0 | HIGH (DoS via recursion) | 5.9.0 |
| aiohttp | 3.13.3 | MODERATE×3, LOW×7 | 3.13.4 |
| cryptography | 46.0.5 | MODERATE (buffer overflow), LOW | 46.0.7 |
| python-multipart | 0.0.22 | MODERATE (DoS) | 0.0.26 |
| pytest | 9.0.2 | MODERATE (tmpdir) | 9.0.3 |
| pygments | 2.19.2 | LOW (ReDoS) | 2.20.0 |
| requests | 2.32.5 | MODERATE (temp file) | 2.33.0 |

A dry-run `uv lock` with `harbor>=0.4,<0.5` + `opik>=2,<3` resolves to versions
that fix every CVE (re-verified against OSV after the upgrade: zero
vulnerabilities). `cbor2` drops out of the tree entirely as a transitive.

The Opik Harbor integration bug (ADR-006) still ships in opik 2.0.9 — the
`_patch_step_class.patched_init` still reads `self.metrics` synchronously in
`Step.__init__` before Harbor assigns metrics. The runtime monkey-patch in
`runner.py` is still required, but its internal-API calls need adaptation:
`opik_client.get_client_cached()` → `opik.get_global_client()`, and
`client.span(...)` → `client.__internal_api__span__(...)`.

Harbor 0.4 introduces two API changes that affect nasde:

1. `Job(config)` raises `ValueError` — construction is now async via
   `await Job.create(config)`.
2. `DatasetConfig.registry` nested key is deprecated; flat `registry_path` /
   `registry_url` fields are the new API (migration still works, but emits a
   `DeprecationWarning`).

The `ClaudeCode` base class signature is compatible; `ConfigurableClaude` and
siblings need no changes. The evaluator subprocess backends are untouched by
this upgrade.

## Scope

In scope:

1. Bump `harbor>=0.4,<0.5`, `opik>=2,<3`, `rich>=14.1`.
2. Adapt `runner.py` to Harbor 0.4 (`Job.create`, `registry_path`) and Opik 2.x
   (monkey-patch internal-API rename).
3. Add `pip-audit` as a GitHub Actions step that fails on any CVE in the
   locked dependency tree.
4. Update `ADR-006` (bug still present in opik 2.x; patch adapted to 2.x
   internals) and `CLAUDE.md` "Known issues" version references.
5. Smoke test on the smallest benchmark (`ddd-threshold-discount` with the
   `claude-vanilla` variant) with `--with-opik`, verifying that token `usage`
   reaches Opik.

Out of scope (deferred to follow-up work):

- Upstream PRs to opik/harbor removing the need for the monkey-patch.
- Dependabot / Renovate automation.
- `SECURITY.md` with vulnerability reporting procedure.
- Committing `uv.lock` to the repo (already covered by `pyproject.toml`
  version constraints for now).
- Rewriting the tracker without any monkey-patch (would require either a
  Harbor upstream fix to `_convert_event_to_step`, an Opik upstream fix
  adding `__setattr__` patching, or a from-scratch tracker reading
  `trajectory.json` post-trial — all too large for this change).

## Architecture

### `pyproject.toml`

```toml
dependencies = [
    "typer>=0.15",
    "rich>=14.1",
    "platformdirs>=4.0",
    "harbor>=0.4,<0.5",
    "opik>=2,<3",
]
```

The `rich>=14.1` floor matches what harbor 0.4 requires
(`Requires-Dist: rich>=14.1.0`).

### `src/nasde_toolkit/runner.py`

Three edits:

**a) `_run_job` — async job construction.**

```python
# before
job = Job(job_config)
# after
job = await Job.create(job_config)
```

**b) `_build_merged_config` — flat registry key.**

```python
"datasets": [{
    "name": config.name,
    "registry_path": registry_path,  # was: "registry": {"path": registry_path}
}]
```

**c) `_patch_opik_deferred_metrics` — Opik 2.x internal API.**

Replace the two internal-API references inside `_create_span_for_step`:

```python
# before
from opik.api_objects import opik_client
client = opik_client.get_client_cached()
client.span(id=..., trace_id=..., ...)

# after
import opik
client = opik.get_global_client()
client.__internal_api__span__(id=..., trace_id=..., ...)
```

The re-patch strategy (replacing `Step.__init__` + installing
`Step.__setattr__` so that span creation is deferred until `metrics` is
assigned) stays identical — the race condition and its fix are unchanged.

### `.github/workflows/quality-gate.yml`

Add a new `audit` job alongside `lint`, `typecheck`, `test`:

```yaml
audit:
  name: CVE audit (pip-audit)
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Export lockfile
      run: uv export --no-dev --no-hashes --format requirements-txt > requirements.txt
    - name: Run pip-audit
      run: uvx --with pip pip-audit -r requirements.txt --strict
```

`--strict` fails the job if any advisory lacks a clear resolution. A PR
wishing to merge past a known but accepted CVE can use
`--ignore-vuln GHSA-...` on a per-advisory basis (we don't add this now).

### Documentation

- `docs/adr/006-opik-deferred-metrics-patch.md`: append a short note that
  opik 2.0.9 still ships the bug, and that the patch now targets the 2.x
  internal API.
- `CLAUDE.md` "Known issues": bump version references from 1.10.x to 2.x.

### Out-of-the-way files

No changes needed in `agents/configurable_*.py` (Harbor 0.4 `ClaudeCode`
signature is compatible), `evaluator.py`, `evaluator_backends/`, `config.py`,
`cli.py`, `docker.py`, `scaffold/`.

## Data flow (Opik integration, unchanged end-state)

The monkey-patch intent is unchanged: every Harbor `Step` construction should
produce one Opik span with token usage. The only thing that moves is *which
Opik symbol we reach for*.

```
Harbor creates Step(...)    ──►    patched __init__
                                   ├─ stashes trace/parent span ids
                                   └─ if source!="agent" OR metrics already set
                                          └─► emit span via opik.get_global_client()
                                                             .__internal_api__span__(...)

Harbor assigns step.metrics ──►    patched __setattr__
                                   └─ if name=="metrics" and not yet emitted
                                          └─► emit span (same path)
```

## Testing

### Unit tests

`uv run pytest` must pass. The evaluator backend tests don't touch Opik or
Harbor internals, so they're unaffected. The runner doesn't have dedicated
tests, which means this bump rides entirely on the smoke test for behavior
validation.

### Smoke test

On the smallest available benchmark (`examples/ddd-architectural-challenges`,
task `ddd-threshold-discount`, variant `claude-vanilla`):

```bash
uv run nasde run \
  --variant claude-vanilla \
  --tasks ddd-threshold-discount \
  --with-opik \
  -C examples/ddd-architectural-challenges
```

Verification (via Opik REST API, not curl):

- Trial trace exists under project `ddd-architectural-challenges`.
- At least one span has non-null `usage.prompt_tokens` and
  `usage.completion_tokens`.
- Trace `total_tokens` in the UI/API is > 0.

### CVE audit

`uvx --with pip pip-audit -r <exported-reqs> --strict` returns exit 0 with
zero findings both locally and in CI.

## Rollout

Single PR onto `main`. No phased rollout, no feature flag — dependency bumps
are all-or-nothing.

## Risk & rollback

- **Risk:** Opik's `__internal_api__span__` symbol is deliberately marked
  internal (double-underscore prefix+suffix). A patch-version bump that
  renames or removes it would break our tracker silently (the patch catches
  all exceptions for robustness). Mitigation: CI test catches it on next
  upgrade attempt; ADR-006 documents the coupling and calls for revisit at
  each opik bump.
- **Risk:** Harbor 0.4 may have subtle semantic changes in `Job.create` that
  the smoke test doesn't cover (e.g., task caching behavior). Mitigation:
  acceptable — we'll see these in the dogfooding runs after merge, and the
  benchmark suite is the full integration test.
- **Rollback:** `git revert` the merge commit. `pyproject.toml` constraints
  force a consistent rollback of the resolved tree.

## Open questions

None.

## References

- ADR-006: `docs/adr/006-opik-deferred-metrics-patch.md`
- Harbor 0.4 JobConfig: `harbor/models/job/config.py`
- Opik 2.0.9 Harbor tracker: `opik/integrations/harbor/opik_tracker.py`
- OSV batch audit query: https://api.osv.dev/v1/querybatch
