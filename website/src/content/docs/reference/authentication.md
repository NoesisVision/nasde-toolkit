---
title: Authentication
description: How NASDE auto-detects credentials per agent — Claude Code, OpenAI Codex, Gemini CLI — plus Opik tracing setup.
---

NASDE auto-detects the required credentials based on the variant's agent type.

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

NASDE auto-detects `~/.codex/auth.json` with `auth_mode: "chatgpt"` and injects the full OAuth token structure into the sandbox. No env vars needed.

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

**Option 2: Google Cloud / Vertex AI** — uses your Google Cloud project billing.

```bash
export GOOGLE_API_KEY=your-key
export GOOGLE_CLOUD_PROJECT=your-project
```

**Option 3: OAuth (Google account)** — uses your Gemini subscription credits.

```bash
gemini login                                  # authenticate via Google account (one-time)
source scripts/export_gemini_oauth_token.sh   # validate tokens are present
uv run nasde run --variant gemini-baseline -C my-benchmark
```

NASDE auto-detects `~/.gemini/oauth_creds.json` and injects the credentials into the sandbox. No env vars needed.

API key env vars (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`) always take priority over OAuth when present.

## Opik tracing

For Opik tracing, set credentials in `.env` (in project dir or parent):

```
OPIK_API_KEY=...
OPIK_WORKSPACE=...
```

The Opik project name is automatically set to the benchmark name (from `nasde.toml [project] name`).
