---
title: CLI Cheatsheet
description: The handful of nasde commands you'll actually use day to day, with copy-paste examples.
---

Most users only need `nasde run` — everything else is occasional. See [Commands](/nasde-toolkit/reference/commands/) for the full reference.

```bash
# Scaffold a new benchmark project from scratch
nasde init my-benchmark

# Run the default variant
nasde run --variant vanilla -C my-benchmark

# Codex variant (model name is OpenAI-side)
nasde run --variant codex-baseline --model gpt-5.3-codex -C my-benchmark

# Gemini CLI variant
nasde run --variant gemini-baseline --model google/gemini-3-flash-preview -C my-benchmark

# Run a single task with experiment tracking
nasde run --variant vanilla --tasks my-task -C my-benchmark --with-opik

# Skip the reviewer (rough tests only, faster)
nasde run --variant vanilla -C my-benchmark --without-eval

# Re-run the reviewer on an existing trial (no re-execution)
nasde eval jobs/2026-03-13__14-30-00 --with-opik -C my-benchmark

# [Experimental] Back up the results essence so they don't only live in jobs/
nasde results-export jobs/2026-03-13__14-30-00 --to ~/Dropbox/nasde-results -C my-benchmark

# Publish a trial as a PR for human rubric calibration, then pull comments back
nasde calibrate publish jobs/2026-03-13__14-30-00/movie__abc -C my-benchmark
nasde calibrate pull-comments jobs/2026-03-13__14-30-00/movie__abc -C my-benchmark --json
```

Authentication is covered in detail in the [Authentication](/nasde-toolkit/reference/authentication/) section — in short, export an API key (`ANTHROPIC_API_KEY` / `CODEX_API_KEY` / `GEMINI_API_KEY`) **or** just use whatever OAuth subscription you're already logged into via `claude` / `codex` / `gemini login`.
