---
name: nasde-dev
description: |
  Internal skill for developing and maintaining nasde-toolkit itself. Use this skill when:
  - Making changes to nasde-toolkit source code (CLI, runner, evaluator, config, agents)
  - Refactoring or adding features to the toolkit
  - Fixing bugs in the evaluation pipeline
  - Updating dependencies or integration points (Harbor, Opik, `claude` / `codex` CLI subprocess backends)
  This skill defines the verification protocol that must be followed after any significant change.
---

# NASDE Toolkit Development

Internal guidelines for developing nasde-toolkit itself.

> **Important context:** `nasde-toolkit/` is the current production toolkit. The repository also contains `SDLC/evals/` which is the **legacy predecessor** — the original research/prototype that has been migrated into nasde-toolkit. Do NOT modify `SDLC/evals/` for new work. It will be removed once migration is confirmed complete.

## Post-change verification protocol

After any significant change to the toolkit (new features, refactors, dependency updates, renamed identifiers), run the full verification pipeline before considering the work complete.

### 1. Quality gates (must pass before any commit/PR)

These are the same checks that run on CI. **Always run locally before claiming code is ready:**

```bash
# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/nasde_toolkit/

# Unit tests
uv run pytest
```

All four must pass. If `ruff format` fails, run `uv run ruff format src/ tests/` to auto-fix.

After pushing, verify CI passes on the PR with `gh pr checks <PR_NUMBER>`.

### 1b. Static checks

```bash
# No stale references to old names or patterns
grep -r "sdlc.eval\|sdlc-eval\|sdlc_eval" src/ docs/ CLAUDE.md README.md .claude/skills/ pyproject.toml --include="*.py" --include="*.md" --include="*.toml" --include="*.json" | grep -v __pycache__

# Package installs cleanly
uv sync
```

### 1c. Documentation and skills consistency

After any change to the evaluation pipeline, CLI flags, configuration schema, agent support, or sandbox/environment handling, update **all** of these:

**Think DX-first:** For every new option or feature, ask "where will the user be when they need this?" and put the documentation there. A feature that exists only in CLAUDE.md is invisible to most users. Check every touchpoint:

**Documentation:**
- `CHANGELOG.md` — **add an entry under `## [Unreleased]`** (Added / Changed / Fixed) for any user-visible change: new CLI flag, config field, behavior change, dependency bump. Add the `[#NN]` PR link-reference at the bottom. Easy to forget — do it as part of the change, not at release time.
- `README.md` — user-facing documentation (CLI options table, nasde.toml config reference, explanatory text). This is where most users look first.
- `CLAUDE.md` — agent instructions (CLI reference, nasde.toml example, architecture decisions)
- `ARCHITECTURE.md` — system architecture with mermaid diagrams (end-to-end flow, trial lifecycle, cloud sandbox providers, assessment evaluation)

**Examples:**
- At least one example benchmark in `examples/` should demonstrate the new feature in a working configuration.

**Scaffold templates** (`src/nasde_toolkit/scaffold/__init__.py`):
- If the feature is a new config option, add a commented-out example to the `NASDE_TOML_TEMPLATE` so users discover it when running `nasde init`.

**Skills (update when relevant to the change):**
- `.claude/skills/nasde-benchmark-runner/SKILL.md` — running benchmarks, supported models/agents, auth, troubleshooting
- `.claude/skills/nasde-benchmark-creator/SKILL.md` — creating benchmarks, variant structure, task formats, agent conventions
- `.claude/skills/nasde-dev/SKILL.md` — this file, verification protocol

### 2. CLI smoke test

```bash
nasde --version
nasde --help
```

### 3. End-to-end benchmark run

**Auth — CHAIN the export scripts INTO the run command.** OAuth env vars do NOT
persist between separate shell invocations, so a lone `source ...` in one command
is lost by the next. Always `&&`-chain the needed `source` scripts with the `nasde`
call in a single command. Never ask the user to authenticate — do it yourself.

Which auth each task needs (check before running, don't ask):
- **Agent** claude → `scripts/export_oauth_token.sh` (`CLAUDE_CODE_OAUTH_TOKEN`);
  codex → `scripts/export_codex_oauth_token.sh`; gemini → `scripts/export_gemini_oauth_token.sh`.
- **Evaluator** (every run without `--without-eval`, and `nasde eval`) uses the
  `[evaluation] backend` from `nasde.toml` — **default `claude` → needs Claude OAuth
  even when the agent is codex/gemini.** So a codex-agent run with the default
  evaluator needs BOTH Codex OAuth (agent) and Claude OAuth (eval).
- `--with-opik` → Opik config (see step 4 / `.env`).

```bash
# codex agent + default (claude) evaluator → BOTH OAuth tokens, chained:
source scripts/export_codex_oauth_token.sh && source scripts/export_oauth_token.sh && \
  nasde run --variant codex-vanilla --tasks ddd-threshold-discount \
  -C examples/ddd-architectural-challenges --with-opik
```

Expected output:
- Harbor trial completes with reward 1.0
- Assessment evaluation produces scores for all configured dimensions
- Token & cost economics appear in the per-(agent, model) summary table and in
  `assessment_summary.json` (see ADR-011)
- Opik trace is created with feedback scores uploaded

### 4. Opik REST API verification

After any run with `--with-opik`, verify that all feedback scores arrived in Opik. Use Python `urllib.request` (never curl — it drops the `Comet-Workspace` header):

```bash
source .env
python3 -c "
import urllib.request, json

req = urllib.request.Request(
    'https://www.comet.com/opik/api/v1/private/traces?project_name=ddd-architectural-challenges&limit=1',
    headers={
        'authorization': '$OPIK_API_KEY',
        'Comet-Workspace': '$OPIK_WORKSPACE',
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
trace = resp['content'][0]
print(f'Trace: {trace[\"name\"]}')
print(f'ID:    {trace[\"id\"]}')
print()
scores = trace.get('feedback_scores', [])
print(f'Feedback scores ({len(scores)}):')
for s in sorted(scores, key=lambda x: x['name']):
    print(f'  {s[\"name\"]}: {s[\"value\"]}')
"
```

Expected feedback scores (7 total for the ddd benchmark):
- `arch_<dimension>` for each dimension in `assessment_dimensions.json` (normalized 0.0-1.0)
- `arch_total` — overall normalized score
- `reward` — Harbor functional test result (0.0 or 1.0)
- `duration_sec` — trial execution time

### 6. When to run this protocol

- **Step 1 (quality gates): ALWAYS before any commit or PR.** No exceptions.
- **Full protocol (steps 1-5):** After renaming, refactoring, dependency updates, or changes to runner/evaluator/config
- **Steps 1-2 only:** After documentation-only changes or minor code edits
- **Skip entirely:** Typo fixes, comment changes, .gitignore updates (but still run step 1 before committing)
