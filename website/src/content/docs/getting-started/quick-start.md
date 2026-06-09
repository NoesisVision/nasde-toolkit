---
title: Quick Start
description: The fastest path from zero to a working benchmark built from your own git history — three steps.
---

The fastest path from zero to a working benchmark built from **your own git history**:

## 1. Install the CLI

```bash
uv tool install nasde-toolkit --python 3.13
nasde --version
```

This installs the latest stable release from [PyPI](https://pypi.org/project/nasde-toolkit/).

:::note[Python version]
We recommend `--python 3.13` (latest stable, broadest wheel availability). `--python 3.12` is also supported and tested if your environment standardizes on it. Python **3.14 is not currently supported** — a transitive dependency (`pyiceberg` via `supabase`) hasn't yet released wheels for cp314. The cap will be lifted once upstream wheels land.
:::

See the [Installation reference](/nasde-toolkit/getting-started/installation/) for pipx, pip, and from-source alternatives.

## 2. Install the authoring skills for Claude Code

```bash
nasde install-skills
```

This copies the bundled `nasde-benchmark-*` skills into `~/.claude/skills/` so they're available in every Claude Code session. Use `--scope project` to install into the current project's `.claude/skills/` instead, or `--force` to overwrite after a `nasde` upgrade.

:::note
The authoring helpers are Claude Code skills. Codex and Gemini users can still run NASDE from the CLI — the skills just speed up *creating* benchmarks; they are not required to *run* them.
:::

## 3. From inside your own repo, ask the agent to build a benchmark from git history

Open your own project in Claude Code and say something like:

> *"Create a NASDE benchmark with a single task, based on a recent piece of work from this repo — a commit, a range of commits, or a merged PR."*

Start with **one task**. Point the skill at whatever unit of work feels self-contained in your workflow — a single commit, a range, a merged MR/PR, or an issue that was closed by a set of commits. The `nasde-benchmark-from-history` skill proposes a good candidate, and generates one task directory with `instruction.md`, a Dockerfile, `test.sh`, and a starter `assessment_criteria.md`. You review each file before it's written.

Then run it:

```bash
nasde run --all-variants -C path/to/generated-benchmark
```

`--all-variants` runs every variant the skill scaffolded, so you don't need to know their names yet. If you'd rather burn fewer tokens on the first run, pick just one with `--variant NAME` — you can run the others later.

## Good to know

- **Start small.** One task is enough to validate the loop end to end. Scale up once it works — more tasks only pay off after you've seen what a task looks like in practice.
- **Your subscription covers it.** Runs use your existing `claude` / `codex` / `gemini` CLI auth, so a Claude Max or ChatGPT Plus subscription is enough to get going. API keys are supported too when you have them — see [Authentication](/nasde-toolkit/reference/authentication/) for the full picture.
- **More docs.** See [Use Cases](/nasde-toolkit/guides/use-cases/) for the end-to-end walkthrough and [Benchmark Results](/nasde-toolkit/guides/benchmark-results/) for reference numbers.
