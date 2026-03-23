# CI Setup Guide

## GitHub Actions Workflows

nasde-toolkit uses three GitHub Actions workflow layers:

| Workflow | File | Trigger | Secrets needed |
|----------|------|---------|----------------|
| Quality Gate | `quality-gate.yml` | PR + push to main | None |
| Example Validation | `example-validation.yml` | PR + push to main | None |
| Dogfooding | `dogfooding.yml` | Manual (`workflow_dispatch`) | See below |

## Required Secrets (Dogfooding only)

Configure these in GitHub repo Settings > Secrets and variables > Actions:

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
