# Dependency Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `harbor` to 0.4.x and `opik` to 2.x, adapt the runtime monkey-patch to the Opik 2.x internal API, add a CVE gate to CI, and verify the Opik Harbor token-usage integration still emits `usage` data end-to-end.

**Architecture:** Single-PR dependency bump. The bug that necessitates the Opik monkey-patch (`Step.__init__` reading `self.metrics` before Harbor assigns it) is still present in opik 2.0.9, so the patch stays but its internal-API references are updated. Harbor 0.4's new async `Job.create` and flat `registry_path` keys are absorbed by `runner.py`.

**Tech Stack:** Python 3.12, `uv`, `harbor>=0.4,<0.5`, `opik>=2,<3`, pytest, GitHub Actions, `pip-audit`.

**Spec:** `docs/superpowers/specs/2026-04-22-dependency-modernization-design.md`

---

## Files changed by this plan

| File | Action |
| --- | --- |
| `pyproject.toml` | Modify `[project.dependencies]` |
| `src/nasde_toolkit/runner.py` | Modify `_build_merged_config`, `_patch_opik_deferred_metrics`, `_run_job` |
| `.github/workflows/quality-gate.yml` | Add `audit` job |
| `docs/adr/006-opik-deferred-metrics-patch.md` | Append 2.x status note |
| `CLAUDE.md` | Update "Known issues" version references |

No new files. No file deletions.

---

### Task 1: Bump dependency pins in `pyproject.toml`

**Files:**
- Modify: `pyproject.toml:12-18`

- [ ] **Step 1: Edit the dependencies block**

Change lines 12–18 of `pyproject.toml` from:

```toml
dependencies = [
    "typer>=0.15",
    "rich>=13.0",
    "platformdirs>=4.0",
    "harbor>=0.1.40,<0.2",
    "opik>=1.10,<2",
]
```

to:

```toml
dependencies = [
    "typer>=0.15",
    "rich>=14.1",
    "platformdirs>=4.0",
    "harbor>=0.4,<0.5",
    "opik>=2,<3",
]
```

- [ ] **Step 2: Resolve the new tree with `uv`**

Run: `uv sync --extra dev`

Expected: completes without resolution errors. `uv pip list | grep -E '^(harbor|opik|rich)'` should print `harbor 0.4.0`, `opik 2.0.9` (or newer 2.x), `rich >=14.1`.

- [ ] **Step 3: Confirm CVE-free tree**

Run:

```bash
uv export --no-dev --no-hashes --format requirements-txt > /tmp/reqs.txt
uvx --with pip pip-audit -r /tmp/reqs.txt --strict
```

Expected: `No known vulnerabilities found`, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): bump harbor to 0.4, opik to 2, rich to 14.1+

Fixes all currently-known CVEs in the transitive tree (OSV-verified).
Upgrade requires runner.py adaptations — follow-up commits in this PR."
```

---

### Task 2: Adapt `_build_merged_config` to Harbor 0.4 flat `registry_path`

**Files:**
- Modify: `src/nasde_toolkit/runner.py:400-412`

- [ ] **Step 1: Replace the nested `registry` key**

In `_build_merged_config`, change lines 400–412 from:

```python
    merged = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_attempts": n_attempts,
        "agents": variant["agents"],
        "datasets": [
            {
                "name": config.name,
                "registry": {"path": registry_path},
            }
        ],
        "artifacts": [{"source": "/app", "destination": "workspace"}],
    }
```

to:

```python
    merged = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_attempts": n_attempts,
        "agents": variant["agents"],
        "datasets": [
            {
                "name": config.name,
                "registry_path": registry_path,
            }
        ],
        "artifacts": [{"source": "/app", "destination": "workspace"}],
    }
```

- [ ] **Step 2: Confirm no other callers depend on the old key**

Run: `uv run python -c "import json, tempfile, os; from pathlib import Path; from nasde_toolkit.config import load_project_config; print('import OK')"`

Expected: prints `import OK` (the module imports cleanly with the new key).

- [ ] **Step 3: Run existing tests**

Run: `uv run pytest -v`

Expected: all tests pass. If any test fails complaining about `registry_path`, inspect the test and fix. No runner-specific test exists today, so this step mainly verifies we didn't regress evaluator/config/backend tests.

---

### Task 3: Switch `_run_job` to async `Job.create`

**Files:**
- Modify: `src/nasde_toolkit/runner.py:640-673`

- [ ] **Step 1: Replace `Job(job_config)` with `await Job.create(job_config)`**

In `_run_job`, change the body (approximately lines 665–670) from:

```python
    try:
        job_config = JobConfig.model_validate(config_dict)
        job = Job(job_config)
        if on_trial_ended:
            job.on_trial_ended(on_trial_ended)
        return await job.run()
```

to:

```python
    try:
        job_config = JobConfig.model_validate(config_dict)
        job = await Job.create(job_config)
        if on_trial_ended:
            job.on_trial_ended(on_trial_ended)
        return await job.run()
```

- [ ] **Step 2: Quick import / type sanity check**

Run:

```bash
uv run python -c "from nasde_toolkit.runner import _run_job; import inspect; print(inspect.iscoroutinefunction(_run_job))"
```

Expected: prints `True`.

- [ ] **Step 3: Run unit tests**

Run: `uv run pytest -v`

Expected: all pass.

- [ ] **Step 4: Commit Tasks 2 + 3 together**

```bash
git add src/nasde_toolkit/runner.py
git commit -m "refactor(runner): adapt to harbor 0.4 API

- Job(config) -> await Job.create(config) (direct construction is deprecated)
- datasets[].registry.path -> datasets[].registry_path (flat key)"
```

---

### Task 4: Adapt `_patch_opik_deferred_metrics` to Opik 2.x internal API

**Files:**
- Modify: `src/nasde_toolkit/runner.py:455-588`

- [ ] **Step 1: Update the imports inside the patch function**

Open `runner.py`. In `_patch_opik_deferred_metrics`, the current imports (around lines 468–472) are:

```python
    from typing import Any

    from harbor.models.trajectories.step import Step
    from opik import datetime_helpers, id_helpers, opik_context
    from opik.api_objects import opik_client
```

Replace them with:

```python
    from typing import Any

    import opik
    from harbor.models.trajectories.step import Step
    from opik import datetime_helpers, id_helpers, opik_context
```

(The `from opik.api_objects import opik_client` line is removed; `opik` is imported directly.)

- [ ] **Step 2: Update the client getter inside `_create_span_for_step`**

Find the line that reads `client = opik_client.get_client_cached()` (around line 505). Replace it with:

```python
            client = opik.get_global_client()
```

- [ ] **Step 3: Update the span-emission call**

In the same `_create_span_for_step` function, find the block starting with `client.span(` (around line 536) and rename the method to `__internal_api__span__` — the full call becomes:

```python
            client.__internal_api__span__(
                id=id_helpers.generate_id(),
                trace_id=trace_data.id,
                parent_span_id=parent_span_id,
                name=f"step_{step.step_id}",
                type=_source_to_span_type(step.source),
                start_time=datetime_helpers.parse_iso_timestamp(step.timestamp),
                input=input_dict if input_dict else None,
                output=output_dict,
                metadata=metadata,
                usage=usage,
                total_cost=total_cost,
                model=step.model_name if step.source == "agent" else None,
                tags=["harbor", step.source],
                project_name=span_project_name,
                provider="anthropic" if step.source == "agent" else None,
            )
```

All other arguments stay identical.

- [ ] **Step 4: Remove the obsolete re-import of `SpanType`**

Inside `_patch_opik_deferred_metrics`, there is a second import line `from opik.types import SpanType` (around line 494) used only inside `_source_to_span_type`. That still exists in opik 2.x — leave it in place. No change needed in this step. (Included as an explicit check so the engineer doesn't assume it needs changing.)

- [ ] **Step 5: Verify the module still imports**

Run: `uv run python -c "from nasde_toolkit.runner import _patch_opik_deferred_metrics; print('import OK')"`

Expected: prints `import OK`.

- [ ] **Step 6: Run unit tests**

Run: `uv run pytest -v`

Expected: all pass. (The monkey-patch isn't exercised directly by the unit tests, but import-time failures would surface here.)

- [ ] **Step 7: Commit**

```bash
git add src/nasde_toolkit/runner.py
git commit -m "fix(runner): adapt opik monkey-patch to opik 2.x internal API

opik 2.0.9 still ships the Harbor Step metrics race condition
(__init__ reads self.metrics before Harbor assigns it), so the
runtime re-patch in runner.py is still required. This commit only
updates the internal-API references:
  opik_client.get_client_cached() -> opik.get_global_client()
  client.span(...)                -> client.__internal_api__span__(...)

Everything else in the patch is unchanged."
```

---

### Task 5: Add `pip-audit` job to GitHub Actions

**Files:**
- Modify: `.github/workflows/quality-gate.yml`

- [ ] **Step 1: Append the new job**

At the end of `.github/workflows/quality-gate.yml`, append (keeping existing indentation convention — top-level jobs are two-space indented under `jobs:`):

```yaml
  audit:
    name: CVE audit (pip-audit)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Export lockfile as requirements
        run: uv export --no-dev --no-hashes --format requirements-txt > requirements.txt

      - name: Run pip-audit
        run: uvx --with pip pip-audit -r requirements.txt --strict
```

- [ ] **Step 2: Lint-check the YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/quality-gate.yml'))"`

Expected: no output (clean parse, exit 0).

- [ ] **Step 3: Dry-run pip-audit locally**

Run:

```bash
uv export --no-dev --no-hashes --format requirements-txt > /tmp/reqs.txt
uvx --with pip pip-audit -r /tmp/reqs.txt --strict
```

Expected: exits 0 with "No known vulnerabilities found" (or equivalent clean message). If it reports vulnerabilities, STOP — the earlier dep bump didn't land correctly; re-run Task 1 Step 2.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/quality-gate.yml
git commit -m "ci: add pip-audit CVE gate to quality workflow

Fails any PR (and push to main) whose resolved dep tree contains a
known vulnerability. Use pip-audit --ignore-vuln GHSA-... to waive
specific advisories if ever needed."
```

---

### Task 6: Update ADR-006 and CLAUDE.md

**Files:**
- Modify: `docs/adr/006-opik-deferred-metrics-patch.md`
- Modify: `CLAUDE.md:303`

- [ ] **Step 1: Append a status note to ADR-006**

At the bottom of `docs/adr/006-opik-deferred-metrics-patch.md`, append:

```markdown

## 2026-04-22 update: still required under opik 2.x

Opik 2.0.9 was inspected and still contains the same race condition in
`opik.integrations.harbor.opik_tracker._patch_step_class.patched_init` —
`self.metrics` is read synchronously during `Step.__init__`, before Harbor
assigns it. The only 2.x-relevant change is the internal API rename:
`opik_client.get_client_cached()` → `opik.get_global_client()`, and
`client.span(...)` → `client.__internal_api__span__(...)`. The runtime
monkey-patch in `runner.py` was adapted accordingly; semantics unchanged.

The `__internal_api__span__` double-underscore naming is a deliberate
"internal, may change" signal from Opik maintainers. Re-verify this patch
at every opik minor bump.
```

- [ ] **Step 2: Update CLAUDE.md "Known issues" version reference**

In `CLAUDE.md`, find the line:

```markdown
- **opik 1.10.x**: token usage=None for Harbor spans — runtime monkeypatch in `runner.py` (`_patch_opik_deferred_metrics`). Defers Step span creation to `__setattr__` because Harbor assigns metrics after `Step.__init__`. See ADR-006. Remove when opik fixes upstream.
```

Replace it with:

```markdown
- **opik 2.x (and 1.10.x)**: token usage=None for Harbor spans — runtime monkeypatch in `runner.py` (`_patch_opik_deferred_metrics`). Defers Step span creation to `__setattr__` because Harbor assigns metrics after `Step.__init__`. See ADR-006. Remove when opik fixes upstream.
```

- [ ] **Step 3: Commit**

```bash
git add docs/adr/006-opik-deferred-metrics-patch.md CLAUDE.md
git commit -m "docs: record that opik 2.x still needs the monkey-patch"
```

---

### Task 7: Smoke test the Opik Harbor integration end-to-end

**Files:** none modified — behavior verification only.

- [ ] **Step 1: Ensure Opik credentials are exported**

Run:

```bash
echo "OPIK_API_KEY set: ${OPIK_API_KEY:+yes}${OPIK_API_KEY:-no}"
echo "OPIK_WORKSPACE set: ${OPIK_WORKSPACE:+yes}${OPIK_WORKSPACE:-no}"
```

Expected: both print `set: yes`. If either says `no`, source a `.env` file that has them, or `export OPIK_API_KEY=... OPIK_WORKSPACE=...` before continuing.

- [ ] **Step 2: Ensure Claude OAuth token is exported**

Per `feedback_auth_method.md` memory — prefer OAuth over API key for local work:

```bash
source scripts/export_oauth_token.sh
```

Expected: `CLAUDE_CODE_OAUTH_TOKEN` is now set.

- [ ] **Step 3: Run the smallest benchmark**

Run:

```bash
uv run nasde run \
  --variant claude-vanilla \
  --tasks ddd-threshold-discount \
  --with-opik \
  -C examples/ddd-architectural-challenges
```

Expected: benchmark completes (success or failure is OK — what matters is that the trial ran and Opik received spans). Note the job directory printed at the end (e.g., `examples/ddd-architectural-challenges/jobs/2026-04-22__HH-MM-SS__claude-vanilla__XXXXXX`).

- [ ] **Step 4: Verify token usage reached Opik**

Using Python (`urllib.request` only per CLAUDE.md; no curl):

```bash
uv run python << 'EOF'
import json, os, urllib.request
from pathlib import Path

project = "ddd-architectural-challenges"
api_key = os.environ["OPIK_API_KEY"]
workspace = os.environ["OPIK_WORKSPACE"]
url = f"https://www.comet.com/opik/api/v1/private/traces?project_name={project}&size=5"
req = urllib.request.Request(url, headers={
    "authorization": api_key,
    "Comet-Workspace": workspace,
})
with urllib.request.urlopen(req, timeout=30) as r:
    traces = json.load(r)["content"]

most_recent = traces[0]
print(f"Trace: {most_recent['name']}  total_tokens={most_recent.get('usage', {}).get('total_tokens')}")
assert most_recent.get("usage", {}).get("total_tokens", 0) > 0, \
    f"FAIL: trace usage is empty: {most_recent.get('usage')}"
print("OK: trace has non-zero total_tokens")
EOF
```

Expected: prints a line with `total_tokens=<non-zero integer>` and then `OK: trace has non-zero total_tokens`. If `total_tokens` is 0 or missing, the monkey-patch is broken — inspect runner.py and re-check Task 4.

- [ ] **Step 5: No commit — verification only**

Skip commit; this task produces no source changes.

---

### Task 8: Push and verify CI

**Files:** none.

- [ ] **Step 1: Confirm clean local state**

Run: `git status`

Expected: working tree clean, branch `worktree-lively-shimmying-quiche` ahead of origin by several commits.

- [ ] **Step 2: Push the branch**

Run: `git push -u origin HEAD`

Expected: push succeeds.

- [ ] **Step 3: Open a PR**

Run:

```bash
gh pr create --title "chore(deps): modernize harbor to 0.4 and opik to 2.x" --body "$(cat <<'EOF'
## Summary
- Bumps `harbor>=0.4,<0.5`, `opik>=2,<3`, `rich>=14.1`. Fixes all 20 currently-known CVEs in the transitive tree (1 CRITICAL + 3 HIGH were in litellm/cbor2).
- Adapts `runner.py` to Harbor 0.4 (`await Job.create(...)`, `registry_path`) and Opik 2.x internals (`opik.get_global_client`, `client.__internal_api__span__`). ADR-006 updated — the root bug still ships in opik 2.0.9.
- Adds a `pip-audit` gate in `quality-gate.yml` so we can't silently regress into CVEs.

## Test plan
- [x] `uv run pytest` passes locally
- [x] `uvx --with pip pip-audit -r <exported-reqs> --strict` shows zero findings
- [x] Smoke-tested `nasde run --variant claude-vanilla --tasks ddd-threshold-discount --with-opik` on `examples/ddd-architectural-challenges` — trace in Opik has non-zero `total_tokens`
- [ ] CI green (lint, typecheck, test, audit)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: prints a PR URL.

- [ ] **Step 4: Wait for CI and verify green**

Run: `gh pr checks --watch`

Expected: all four jobs (`lint`, `typecheck`, `test`, `audit`) finish with ✓ green. If any fails, investigate and fix; do NOT merge red.

---

## Self-review checklist (for the plan author)

1. Spec coverage: all seven in-scope items map to tasks — pyproject (Task 1), runner.py (Tasks 2–4), CI audit (Task 5), docs (Task 6), smoke test (Task 7), PR (Task 8).
2. Placeholders: none. All code blocks contain the real content.
3. Types / names: `_build_merged_config`, `_run_job`, `_patch_opik_deferred_metrics`, `_create_span_for_step` referenced consistently; `registry_path` (not `registryPath` or `registry_url`) used everywhere; `Job.create` (not `Job.from_config`) used everywhere; `__internal_api__span__` (double underscores both sides) used everywhere.
