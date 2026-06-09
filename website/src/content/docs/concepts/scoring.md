---
title: How Scoring Works
description: The two independent kinds of scoring in NASDE — deterministic rough tests and the multi-dimensional LLM-as-a-Judge reviewer.
---

This is the question that trips most people up, so it's worth being explicit. There are **two independent kinds of scoring** in NASDE, and they answer different questions:

## 1. Initial rough tests — deterministic pass/fail (reward 0 or 1)

This is the standard verifier pattern used by [Harbor](https://www.harborframework.com/) and other coding-agent benchmarks — every task has a `tests/test.sh` script. After the agent finishes, the script runs inside the container and either passes (reward = 1) or fails (reward = 0). There's nothing AI about this step — it's just a shell script. What "passing" means is entirely up to you:

- For a bug-fix task: *"the regression test that was failing now passes"*
- For a refactor: *"the existing test suite still passes — no behavior change"*
- For a feature: *"the new integration test I wrote passes"*

This gives you a hard yes/no on correctness. It says nothing about *how* the result got there or whether its structure is any good.

## 2. Multi-dimensional assessment — scored by a reviewer agent (LLM-as-a-Judge)

These rough tests only catch black-and-white failures. They don't tell you whether the produced workspace is well-structured, whether it respects your architecture, whether tests are meaningful (or just coverage padding), whether a generated document is clear, whether a migration is reversible. For that, NASDE runs a **second agent** (`claude` or `codex`) on the produced workspace.

The reviewer's reference point is **two files you write** when creating the benchmark:

| File | What goes in it | Who writes it |
|---|---|---|
| `assessment_dimensions.json` | The list of dimensions to score on (e.g. *Domain Modeling*, *Test Quality*, *Documentation Clarity*), plus a max score per dimension | You — once, shared across all tasks in the benchmark |
| `assessment_criteria.md` | Per-task criteria: for each dimension, what a low score looks like, what a high score looks like, what specific things to check | You — once per task, in plain prose |

The workspace also contains the agent's full trace — tool-call trajectory, token usage, wall-clock duration — so your criteria can cover those too, alongside the produced artifacts. One local `nasde run` handles all of it, no separate LLM-as-a-judge stack required.

You decide how strict the criteria are — spell out a ground-truth structure, enumerate exact checks, or leave room for judgment. Whatever gives you a signal you trust.

**The reviewer runs more than once.** An LLM judge is non-deterministic — score the same workspace twice and you can get 0.61 then 0.71. So by default NASDE evaluates each trial **3 times** (`eval_repetitions`, set in `nasde.toml [evaluation]` or with `--eval-repetitions`) and reports the **mean** rather than any single run. Each evaluation is kept as its own `assessment_eval_<N>.json`; a derived `assessment_summary.json` holds the per-dimension mean, standard deviation, and range. Means are computed only within a single judge model **and a single rubric** — a Claude review and a Codex review are different benchmarks, and so is a review run after you edited `assessment_dimensions.json` (the rubric is fingerprinted, so changing a dimension, its `max_score`, or even its description starts a fresh cluster rather than silently mixing incomparable scores). After editing the rubric, just re-run `nasde eval` — the new evaluations form their own cluster automatically.

**The reviewer is itself a coding agent** (`claude` or `codex` CLI). Instead of stuffing the whole workspace into a prompt, it navigates with real tools — `Read`, `Glob`, `Grep`, and optionally MCP analysis servers — reading only what each dimension actually needs. That's why reviews stay tractable on large workspaces.
