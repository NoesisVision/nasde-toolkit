---
title: Quick Start
description: Everything to go from zero to a working benchmark — prerequisites, installation, and your first run built from your own git history.
---

This page takes you from nothing installed to a scored benchmark built from **your own git history**.

## Prerequisites

- **Python 3.12+**
- **Docker** (default) or a cloud sandbox provider — Harbor runs agents in isolated environments
- **uv** — Package manager
- **npm** — Required for Gemini CLI (`@google/gemini-cli` is installed automatically by Harbor)
- **Agent credentials** (at least one):
  - Claude Code: `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`
  - OpenAI Codex: `CODEX_API_KEY` (API key) or `codex login` (ChatGPT subscription OAuth)
  - Gemini CLI: `GEMINI_API_KEY` (API key), `GOOGLE_API_KEY` (Vertex AI), or `gemini login` (Google account OAuth)
- **Evaluator CLI** — the assessment evaluator spawns the `claude` CLI by default (or `codex` if `[evaluation] backend = "codex"`). That CLI must be installed and authenticated (OAuth subscription or API key — whichever you already use interactively)

See [Authentication & Opik](/nasde-toolkit/reference/authentication/) for how to set up each agent's credentials.

## Install the CLI

```bash
uv tool install nasde-toolkit --python 3.13
nasde --version
```

This installs the latest stable release from [PyPI](https://pypi.org/project/nasde-toolkit/).

:::note[Python version]
We recommend `--python 3.13` (latest stable, broadest wheel availability). `--python 3.12` is also supported and tested if your environment standardizes on it. Python **3.14 is not currently supported** — a transitive dependency (`pyiceberg` via `supabase`) hasn't yet released wheels for cp314. The cap will be lifted once upstream wheels land.
:::

Prefer pipx, pip, or a from-source install? See the alternatives below.

### Installation alternatives

```bash
# pipx — analogous isolation, popular in Python community
pipx install nasde-toolkit --python 3.13

# Inside an existing virtual environment (3.12 or 3.13)
pip install nasde-toolkit

# Latest unreleased changes from main (for testing PRs and dev builds)
uv tool install git+https://github.com/NoesisVision/nasde-toolkit.git --python 3.13

# Local clone (for developing NASDE itself)
git clone git@github.com:NoesisVision/nasde-toolkit.git
cd nasde-toolkit
uv sync
```

Upgrading to the newest release:

```bash
uv tool upgrade nasde-toolkit       # if installed via uv tool
pipx upgrade nasde-toolkit          # if installed via pipx
pip install --upgrade nasde-toolkit # if installed via pip
```

`nasde` checks PyPI for newer releases on startup and prints a one-line notice on stderr when an upgrade is available (severity-tinted: patch / minor / major). Disable with `NASDE_NO_UPDATE_CHECK=1` or `CI=true`.

After installation, only `nasde` appears on PATH. Harbor and Opik are bundled as core dependencies. The reviewer agent spawns your already-installed `claude` or `codex` CLI as a subprocess (not bundled), so it reuses whatever authentication you've set up interactively. Check the installed version with `nasde --version`.

## Install the authoring skills

```bash
nasde install-skills
```

This copies the bundled `nasde-benchmark-*` skills into `~/.claude/skills/` so they're available in every Claude Code session. Use `--scope project` to install into the current project's `.claude/skills/` instead, or `--force` to overwrite after a `nasde` upgrade.

:::note
The authoring helpers are Claude Code skills. Codex and Gemini users can still run NASDE from the CLI — the skills just speed up *creating* benchmarks; they are not required to *run* them.
:::

## Build your first benchmark from git history

Open your own project in Claude Code and say something like:

> *"Create a NASDE benchmark with a single task, based on a recent piece of work from this repo — a commit, a range of commits, or a merged PR."*

Start with **one task**. Point the skill at whatever unit of work feels self-contained in your workflow — a single commit, a range, a merged MR/PR, or an issue that was closed by a set of commits. The `nasde-benchmark-from-history` skill proposes a good candidate, and generates one task directory with `instruction.md`, a Dockerfile, `test.sh`, and a starter `assessment_criteria.md`. You review each file before it's written.

## Run it

```bash
nasde run --all-variants -C path/to/generated-benchmark
```

`--all-variants` runs every variant the skill scaffolded, so you don't need to know their names yet. If you'd rather burn fewer tokens on the first run, pick just one with `--variant NAME` — you can run the others later.

## Good to know

- **Start small.** One task is enough to validate the loop end to end. Scale up once it works — more tasks only pay off after you've seen what a task looks like in practice.
- **Your subscription covers it.** Runs use your existing `claude` / `codex` / `gemini` CLI auth, so a Claude Max or ChatGPT Plus subscription is enough to get going. API keys are supported too when you have them — see [Authentication & Opik](/nasde-toolkit/reference/authentication/) for the full picture.
- **More docs.** See [Use Cases](/nasde-toolkit/guides/use-cases/) for the end-to-end walkthrough and [Benchmark Results](/nasde-toolkit/guides/benchmark-results/) for reference numbers.
