---
name: nasde-dev
description: |
  Internal skill for developing and maintaining nasde-toolkit itself. Use this skill when:
  - Making changes to nasde-toolkit source code (CLI, runner, evaluator, config, agents)
  - Refactoring or adding features to the toolkit
  - Fixing bugs in the evaluation pipeline
  - Updating dependencies or integration points (Harbor, Opik, Claude Code SDK)
  This skill defines the verification protocol that must be followed after any significant change.
---

# NASDE Toolkit Development

Internal guidelines for developing nasde-toolkit itself.

## Post-change verification protocol

After any significant change to the toolkit (new features, refactors, dependency updates, renamed identifiers), run the full verification pipeline before considering the work complete.

### 1. Static checks

```bash
# No stale references to old names or patterns
grep -r "sdlc.eval\|sdlc-eval\|sdlc_eval" src/ docs/ CLAUDE.md README.md .claude/skills/ pyproject.toml --include="*.py" --include="*.md" --include="*.toml" --include="*.json" | grep -v __pycache__

# Package installs cleanly
uv sync
```

### 2. CLI smoke test

```bash
nasde --version
nasde --help
```

### 3. End-to-end benchmark run

Run a single task from the existing benchmark with full eval and Opik tracing:

```bash
source scripts/export_oauth_token.sh
nasde run --variant baseline --tasks ddd-threshold-discount \
  -C benchmarks/ddd-architectural-challenges --with-opik
```

Expected output:
- Harbor trial completes with reward 1.0
- Assessment evaluation produces scores for all configured dimensions
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

### 5. When to run this protocol

- **Full protocol (steps 1-4):** After renaming, refactoring, dependency updates, or changes to runner/evaluator/config
- **Steps 1-2 only:** After documentation-only changes or minor code edits
- **Skip:** Typo fixes, comment changes, .gitignore updates
