---
title: Key Terms
description: A glossary of the Nasde vocabulary — variant, trial, job, rubric, dimension, reviewer, trajectory, and the tools it builds on.
---

Nasde has its own vocabulary. If a word in the docs is unfamiliar, it's probably here.

## The benchmark you author

**Benchmark (project)**
: A directory holding everything you define: tasks, variants, assessment dimensions, and config. One `nasde init` scaffolds it. See [Anatomy of a Benchmark](/nasde-toolkit/creating-benchmarks/anatomy/).

**Task**
: One problem the agent must solve — an `instruction.md`, a starting codebase (`environment/`), a `test.sh` verifier, and per-task `assessment_criteria.md`. The thing you already know the answer to.

**Variant**
: One configuration of the agent under test — its family (`claude` / `codex` / `gemini`), model, instructions (`CLAUDE.md` etc.), skills, MCP servers, and reasoning effort. Comparing variants is the point of a benchmark. See [Configuration](/nasde-toolkit/reference/configuration/#varianttoml).

**Dimension**
: One axis the reviewer scores on — e.g. *Domain Modeling*, *Test Quality* — each with its own max score. Defined once per benchmark in `assessment_dimensions.json`. See [Assessment Criteria & Dimensions](/nasde-toolkit/creating-benchmarks/assessment-criteria/).

**Rubric**
: The pair of files the reviewer scores against: the benchmark-wide `assessment_dimensions.json` and the per-task `assessment_criteria.md`.

## The two kinds of scoring

**Rough tests**
: The deterministic `test.sh` verifier that runs after the agent and emits a pass/fail. No AI involved.

**Reward**
: The binary result of the rough tests — `1` (pass) or `0` (fail).

**Reviewer (judge / evaluator)**
: The *second* coding agent that reads the produced workspace and scores it on your dimensions — the LLM-as-a-Judge. Configured under `[evaluation]` in `nasde.toml`. See [How It Works](/nasde-toolkit/concepts/how-it-works/).

**Agent under test**
: The agent whose configuration you're measuring — the one that actually solves the task. Distinct from the reviewer.

## What a run produces

**Trial**
: One execution of one variant against one task — the agent solving it, the rough tests, and the reviewer scoring. A run can produce many trials.

**Job**
: The output directory for a whole `nasde run` (one timestamped folder under `jobs/`), containing all its trials. See [Reading Your Results](/nasde-toolkit/getting-started/reading-results/).

**Trajectory**
: The agent's full trace of a trial — every tool call, token count, and timestamp. The reviewer can read it to judge the agent's *process*, not just its output.

**Sandbox**
: The isolated container the agent works in. It can't touch your machine, and every trial starts from the same clean state.

## The tools Nasde builds on

**Harbor**
: The framework that runs the agent in a sandbox (Stage 1). Nasde uses its Python API directly. [harborframework.com](https://www.harborframework.com/)

**Opik**
: The optional experiment tracker scores flow to with `--with-opik`. [Opik by Comet](https://github.com/comet-ml/opik)

**Authoring skills**
: The bundled Claude Code skills (`nasde-benchmark-*`) that scaffold benchmarks, mine git history, run them, and calibrate rubrics. Installed with `nasde install-skills`.
