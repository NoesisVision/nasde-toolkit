---
title: Troubleshooting & FAQ
description: Common failures on your first runs — Docker, auth, out-of-memory, flaky evaluations — plus what to expect on time, cost, and how many trials you need.
---

Most first-run problems fall into a handful of buckets. Here's how to recognize and fix them, followed by the operational questions everyone asks.

## Common problems

### "Cannot connect to the Docker daemon"
The sandbox needs Docker running. Start Docker Desktop (or your daemon) and re-run. If you'd rather not run containers locally, use a [cloud sandbox provider](/nasde-toolkit/guides/running-benchmarks/#cloud-sandbox-providers) with `--harbor-env daytona`.

### Authentication errors / empty API key
Nasde uses whatever you're already logged into. If a run fails with an auth or empty-key error:
- **Claude**: `ANTHROPIC_API_KEY`, or `CLAUDE_CODE_OAUTH_TOKEN` from `claude` login.
- **Codex**: `CODEX_API_KEY`, or `codex login` for the ChatGPT subscription (an API key always wins over OAuth when both are set).
- **Gemini**: `GEMINI_API_KEY` / `GOOGLE_API_KEY`, or `gemini login`.

See [Authentication & Opik](/nasde-toolkit/reference/authentication/) for the full per-agent setup.

### The agent container exits with code 137 (out of memory)
Exit 137 is the OOM killer, not an agent error — the container hit its memory ceiling. It shows up most under parallelism (several heavy agents at once). Fixes: raise the task's `[environment] memory_mb` (Claude Code wants 4096+), run fewer variants in parallel, or move to a cloud sandbox. **An OOM is a retry, not a result** — re-run that trial.

### The reviewer (evaluation) fails with an empty error
The `claude -p` evaluator is occasionally flaky (a non-zero exit with empty stderr). It almost always passes on a retry — re-run just the assessment without re-executing the agent:

```bash
nasde eval jobs/<job-dir> -C my-benchmark
```

### Rate limits (HTTP 429) on long local runs
Harbor reinstalls the agent CLI per trial, which can trip provider rate limits after a stretch of back-to-back trials locally. Space runs out, or scale on a cloud provider. Transient API overload (HTTP 529) is the provider, not your setup — retry.

## What to expect

### How long does a run take?
A single trial (one agent solving one task) is typically a few minutes to ~30 minutes, dominated by how long the agent takes on the task (set by the task's `[agent] timeout_sec`, default 1800s) plus the reviewer pass. Total wall-clock multiplies by **variants × tasks × attempts** (`--attempts` / `-n`, the independent agent runs per task) — and each trial is then reviewed `--eval-repetitions` times. So start with one task and one variant.

### How much does it cost?
Each trial spends real tokens on the agent; each trial is then reviewed several times (`--eval-repetitions`, default 3), so the reviewer cost multiplies too. Nasde records the exact token and USD cost per trial — see [Token & Cost](/nasde-toolkit/concepts/token-cost/). On a Claude Max or ChatGPT Plus subscription, casual benchmarking is covered by your plan; heavy parallel runs may hit subscription windows.

### How many attempts do I need?
Two different knobs, two different noise sources:
- **`--attempts` (agent runs per task)** — the agent writes different code each run. More attempts shrink the **`mean ±std`** spread you see *between trials* in the run summary. One attempt gives a point estimate with no spread; **3+** lets you compare configurations honestly.
- **`--eval-repetitions` (reviewer passes per trial, default 3)** — the judge scores the same code slightly differently each pass. This is *judge* noise, reported per trial.

If two configs differ by less than their combined spread, run more attempts before believing the gap. See [Reading Your Results](/nasde-toolkit/getting-started/reading-results/).

## FAQ

**Do I need an API key, or is a subscription enough?**
A subscription is enough to get going — runs reuse your `claude` / `codex` / `gemini` CLI login. API keys work too when you have them.

**Does Nasde run the agents interactively?**
No — it drives them **non-interactively** (`claude -p`, `codex exec`, the Gemini CLI equivalent), scripting them rather than chatting. An interactive mode is **planned** but not available yet.

**Does running it programmatically affect my Claude plan?**
Nasde's non-interactive use counts as *programmatic* use of Claude. Anthropic has announced that **from June 15, 2026, paid Claude plans include a dedicated monthly credit for programmatic usage** (covering `claude -p`, the Agent SDK, and Claude Code GitHub Actions), so running Nasde on a paid plan is supported. Check [Anthropic's current terms](https://www.anthropic.com/) for the credit and limits on your plan.

**Can I run this without Docker?**
Yes — point `--harbor-env` at a [cloud sandbox provider](/nasde-toolkit/guides/running-benchmarks/#cloud-sandbox-providers). The reviewer (Stage 2) always runs locally on the host regardless.

**Does it phone home / upload my code?**
No. Trials run in a local (or your-cloud) sandbox; results stay in `jobs/`. Only `--with-opik` sends scores to your Opik workspace, and `results-export` only writes to a local path you choose.

**Can the agent and the reviewer be different models?**
Yes — that's the norm. The agent under test is set per variant; the reviewer is set under `[evaluation]`. See [Running & Configuring Runs](/nasde-toolkit/guides/running-benchmarks/).

**I edited my rubric — do old and new scores mix?**
No. Nasde fingerprints the rubric, so changing a dimension, its `max_score`, or its description starts a fresh scoring cluster. Just re-run `nasde eval`.
