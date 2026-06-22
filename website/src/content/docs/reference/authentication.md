---
title: Authentication & Opik
description: How Nasde auto-detects credentials per agent — Claude Code, OpenAI Codex, Gemini CLI — plus Opik tracing setup and how to verify results landed.
---

Nasde auto-detects the required credentials based on the variant's agent type.

:::note[Programmatic use]
Nasde drives the agents **non-interactively** (`claude -p`, `codex exec`, and the Gemini CLI equivalent), so it counts as *programmatic* use of those tools. For Claude specifically, Anthropic has announced that **from June 15, 2026, paid plans include a dedicated monthly credit for programmatic usage** — covering `claude -p`, the Claude Agent SDK, and Claude Code GitHub Actions. Running Nasde on a paid Claude subscription is therefore supported; check [Anthropic's current terms](https://www.anthropic.com/) for the credit and limits on your plan.
:::

## Claude Code

The tool checks for auth tokens in this order:
1. `ANTHROPIC_API_KEY` environment variable
2. `CLAUDE_CODE_OAUTH_TOKEN` environment variable

On macOS, you can extract the OAuth token from your Claude Code keychain entry (created when you log in via `claude` CLI):

```bash
source scripts/export_oauth_token.sh
# ✓ CLAUDE_CODE_OAUTH_TOKEN exported (sk-ant-oat01-...)
```

This lets you use your Claude Pro/Max subscription instead of an API key.

## OpenAI Codex

Codex variants support two authentication methods:

**Option 1: ChatGPT subscription (OAuth)** — uses your ChatGPT Plus/Pro/Business plan credits, not API billing.

```bash
codex login                                # authenticate via ChatGPT (one-time)
source scripts/export_codex_oauth_token.sh # validate tokens are present
uv run nasde run --variant codex-vanilla -C my-benchmark
```

When no API key is set, Nasde auto-detects the presence of `~/.codex/auth.json` (created by `codex login`) and opts into uploading it to the sandbox (it sets `CODEX_FORCE_AUTH_JSON=true`; Harbor does the actual upload). No env vars needed.

**Option 2: API key** — billed per-token through your OpenAI Platform account.

```bash
export CODEX_API_KEY=sk-...  # preferred
# or: export OPENAI_API_KEY=sk-...
```

API key always takes priority over OAuth when both are present.

## Gemini CLI

Gemini CLI variants support three authentication methods:

**Option 1: API key (Google AI Studio)** — billed per-token through your Google AI Studio account.

```bash
export GEMINI_API_KEY=your-key
```

**Option 2: Google Cloud / Vertex AI** — uses your Google Cloud project billing. Set either an API key or a service-account credentials file:

```bash
export GOOGLE_API_KEY=your-key
# or, for a service account:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

These are the env vars Nasde checks for the API-key path (alongside `GEMINI_API_KEY`).

**Option 3: OAuth (Google account)** — uses your Gemini subscription credits.

```bash
gemini login                                  # authenticate via Google account (one-time)
source scripts/export_gemini_oauth_token.sh   # validate tokens are present
uv run nasde run --variant gemini-baseline -C my-benchmark
```

Nasde auto-detects `~/.gemini/oauth_creds.json` and injects the credentials into the sandbox. No env vars needed.

API key env vars (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`) always take priority over OAuth when present.

## Opik tracing

For Opik tracing, set credentials in `.env` (in project dir or parent):

```
OPIK_API_KEY=...
OPIK_WORKSPACE=...
```

The Opik project name is automatically set to the benchmark name (from `nasde.toml [project] name`).

## Verifying Opik results

After a `--with-opik` run, confirm the feedback scores landed:

```python
import urllib.request, json

req = urllib.request.Request(
    "https://www.comet.com/opik/api/v1/private/traces?project_name=<PROJECT>&limit=1",
    headers={
        "authorization": "<OPIK_API_KEY>",
        "Comet-Workspace": "<WORKSPACE>",
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
scores = resp["content"][0].get("feedback_scores", [])
for s in sorted(scores, key=lambda x: x["name"]):
    print(f"  {s['name']}: {s['value']}")
```

Expected feedback scores after a full run with `--with-opik`:

- `arch_<dimension>` (e.g. `arch_domain_modeling`) — normalized 0.0-1.0, plus `arch_<dimension>_std`
- `arch_total` — overall architecture score, plus `arch_total_std`
- `eval_n` — how many judge evaluations the mean is over
- `reward` — Harbor rough-test result (0.0 or 1.0)
- `duration_sec` — trial duration
