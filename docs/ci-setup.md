# CI Setup Guide

## GitHub Actions Workflows

nasde-toolkit uses four GitHub Actions workflows:

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| Quality Gate | `quality-gate.yml` | PR + push to main, `workflow_call` | Lint, mypy, pytest, pip-audit. Reused by `publish.yml` as a release prerequisite. |
| Example Validation | `example-validation.yml` | PR + push to main (paths: `examples/**`, `src/**`) | Validates example benchmarks build and pass smoke checks. |
| Dogfooding | `dogfooding.yml` | Manual (`workflow_dispatch`) | Runs `nasde run` against an example task. |
| Publish | `publish.yml` | Tag push (`v*`), manual dispatch, weekly cron (Mon 09:00 UTC) | Builds wheel + sdist, publishes to TestPyPI then PyPI, runs fresh-install smoke tests. See [RELEASING.md](RELEASING.md). |

## Required Secrets

Most workflows need no secrets — `publish.yml` uses PyPI Trusted Publishing (OIDC), no long-lived tokens.

`dogfooding.yml` requires an Anthropic auth secret in repo Settings → Secrets and variables → Actions:

| Secret | Description | Required |
|--------|-------------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | One of these two |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth token (alternative auth) | One of these two |

Opik integration in CI is deferred until a dedicated CI workspace/project strategy is established.

## Running Dogfooding Manually

1. Go to Actions tab in GitHub
2. Select "Dogfooding" workflow
3. Click "Run workflow"
4. Optionally override task, variant, or model
5. The workflow runs the benchmark and verifies exit code 0

## Running Publish Manually (TestPyPI dry-run)

For verifying release readiness without cutting a tag:

```bash
gh workflow run publish.yml --ref <branch>
```

Default behavior: builds the head of `<branch>`, publishes to TestPyPI only, runs smoke test against TestPyPI install. PyPI publish is **skipped**. See [RELEASING.md](RELEASING.md) for the full release flow including disaster recovery via `--field publish_to_prod=true`.
