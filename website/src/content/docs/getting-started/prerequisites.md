---
title: Prerequisites
description: What you need installed and authenticated before running a NASDE benchmark.
---

- **Python 3.12+**
- **Docker** (default) or a cloud sandbox provider — Harbor runs agents in isolated environments
- **uv** — Package manager
- **npm** — Required for Gemini CLI (`@google/gemini-cli` is installed automatically by Harbor)
- **Agent credentials** (at least one):
  - Claude Code: `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`
  - OpenAI Codex: `CODEX_API_KEY` (API key) or `codex login` (ChatGPT subscription OAuth)
  - Gemini CLI: `GEMINI_API_KEY` (API key), `GOOGLE_API_KEY` (Vertex AI), or `gemini login` (Google account OAuth)
- **Evaluator CLI** — the assessment evaluator spawns the `claude` CLI by default (or `codex` if `[evaluation] backend = "codex"`). That CLI must be installed and authenticated (OAuth subscription or API key — whichever you already use interactively)

See [Authentication](/nasde-toolkit/reference/authentication/) for how to set up each agent's credentials.
