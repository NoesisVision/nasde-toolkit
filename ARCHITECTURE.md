# NASDE Toolkit Architecture

## Overview

NASDE evaluates AI coding agents (e.g. Claude Code) on programming tasks. It uses **Harbor** as the execution engine running agents in isolated sandbox environments and **Opik** as the observability platform for tracking results.

Key design: evaluation is **two-stage** — Harbor assesses functional correctness (tests pass/fail), then a separate reviewer agent (Claude Code SDK) assesses architectural quality of the generated code.

---

## End-to-end flow

```mermaid
flowchart TB
    subgraph LAUNCH ["1. Launch"]
        CLI["nasde run\n--variant vanilla --harbor-env daytona"]
        CLI --> MERGE["Merge configuration\n(variant config + task registry + CLI params)"]
        MERGE --> JOB{{"Harbor Job via Python API\n(JobConfig.model_validate)"}}
    end

    subgraph HARBOR ["2. Harbor — trial execution (isolated sandbox)"]
        JOB --> SANDBOX["Sandbox environment\n(Docker, Daytona, Modal, E2B, etc.)"]
        SANDBOX --> SETUP["ConfigurableClaude.setup()\n→ upload CLAUDE.md, .claude.json"]
        SETUP --> AGENT["Claude Code agent\nworks on the task"]
        AGENT --> TEST["test.sh — functional verification"]
        TEST --> REWARD["reward: 0.0 or 1.0"]
        REWARD --> ARTIFACTS["Artifacts copied to host\n→ jobs/ts/trial/artifacts/"]
    end

    subgraph OPIK_TRACE ["  Opik (tracing)"]
        JOB -.->|"track_harbor()\nautomatic tracing"| TRACE["Trace: agent_name/trial_name\n+ spans, tokens, duration"]
    end

    subgraph ASSESSMENT ["3. Assessment evaluation (host machine, always local)"]
        ARTIFACTS -->|"Harbor done,\nsandboxes torn down"| EVAL["evaluator.evaluate_job()"]
        EVAL --> SDK["Claude Code SDK\n(local subprocess, sonnet)\ntools: Read/Glob/Grep\ncwd = artifacts/workspace/"]
        SDK --> SCORE["Score across N dimensions\n0-25 pts each"]
        SCORE --> JSON_OUT["assessment_eval.json"]
        SCORE --> OPIK_FB["Opik feedback scores\narch_*, reward, duration"]
    end

    TRACE -.-> OPIK_FB

    style LAUNCH fill:#e8f4fd,stroke:#2196F3
    style HARBOR fill:#fff3e0,stroke:#FF9800
    style OPIK_TRACE fill:#f3e5f5,stroke:#9C27B0
    style ASSESSMENT fill:#e8f5e9,stroke:#4CAF50
```

---

## What happens inside Harbor

Harbor is a framework for evaluating AI agents. You provide an agent, a dataset, and run a job. NASDE adds minimal but important customizations on top.

### Trial lifecycle

```mermaid
sequenceDiagram
    participant H as Harbor
    participant S as Sandbox Environment
    participant A as ConfigurableClaude
    participant CC as Claude Code
    participant T as test.sh

    H->>S: Create sandbox (Docker/Daytona/Modal/...)
    H->>A: setup(environment)
    A->>A: super().setup() — standard init
    A->>S: upload CLAUDE.md → /app/CLAUDE.md
    A->>S: upload .claude.json → /logs/agent/sessions/
    H->>A: solve(task) with instruction.md
    A->>CC: Launch Claude Code in sandbox
    CC->>CC: Reads CLAUDE.md, configures MCP
    CC->>CC: Analyzes codebase, implements solution
    CC-->>A: Done (artifacts in /app/)
    H->>T: Run test.sh in sandbox
    T->>T: Execute functional tests
    T-->>H: exit code → reward 0.0 or 1.0
    H->>H: Save trajectory.json, result.json, artifacts
```

### Inside the sandbox

```mermaid
flowchart LR
    subgraph Sandbox["Sandbox Environment (Docker / Cloud)"]
        direction TB
        APP["/app/ — source code"]
        CLAUDE_MD["/app/CLAUDE.md\n(injected)"]
        CLAUDE_JSON["/logs/agent/sessions/.claude.json\n(MCP config, injected)"]
        AGENT["Claude Code\nworks on the task"]
        TESTS["test.sh → functional tests"]

        CLAUDE_MD --> AGENT
        CLAUDE_JSON -.->|"MCP servers"| AGENT
        APP --> AGENT
        AGENT -->|"modifies code"| APP
        APP --> TESTS
    end

    TESTS -->|"exit code"| REWARD{"reward:\n0.0 / 1.0"}
```

Harbor only measures **functional correctness** — tests pass or fail, yielding a binary reward. Whether the agent wrote the code *well* is not something Harbor measures. That's where assessment evaluation comes in.

---

## Cloud sandbox providers

Harbor supports multiple execution environments. The provider is set at the **job level** — all trials in a job use the same environment.

| Provider | `--harbor-env` value | Use case |
|----------|---------------------|----------|
| Docker | `docker` (default) | Local development, small runs |
| Daytona | `daytona` | Horizontal scaling, recommended for production |
| Modal | `modal` | Serverless execution |
| E2B | `e2b` | Sandboxed environments |
| Runloop | `runloop` | Runloop platform |
| GKE | `gke` | Google Kubernetes Engine |

### How it works

NASDE passes the environment choice to Harbor's `JobConfig`:

```python
# In runner.py _build_merged_config()
if harbor_env:
    merged["environment"] = {"type": harbor_env}
```

Harbor's `EnvironmentFactory` creates the appropriate environment class based on `EnvironmentConfig.type`. All environments implement the same `BaseEnvironment` interface (`start`, `stop`, `upload_file`, `download_file`, `exec`), so agent code works identically regardless of the provider.

### What runs where

| Component | Where it runs |
|-----------|--------------|
| Harbor trial (agent + test.sh) | Sandbox (Docker or cloud) |
| Assessment evaluation (reviewer agent) | Host machine (always local) |
| Opik tracing | Host machine (API calls to Opik cloud) |

The assessment evaluator reads artifacts that Harbor already copied from the sandbox to `jobs/<ts>/<trial>/artifacts/workspace/` on the host filesystem. It does not need access to the sandbox.

---

## Assessment evaluation — LLM-as-a-Judge

This is NASDE's key extension beyond default Harbor. It runs **entirely on the host machine**, outside of Harbor. After Harbor finishes all trials and sandboxes are torn down, NASDE invokes `evaluator.evaluate_job()` as a separate step.

```mermaid
flowchart TB
    subgraph Inputs["Inputs (per task)"]
        ARTIFACTS["artifacts/workspace/\n(agent-generated output)"]
        CRITERIA["assessment_criteria.md\n(scoring rubric)"]
        DIMS["assessment_dimensions.json\n(dimension definitions)"]
        INSTRUCTION["instruction.md\n(original task prompt)"]
    end

    subgraph Evaluator["Claude Code SDK as evaluator"]
        PROMPT["Composite prompt:\ninstruction + rubric +\ndimension constraints"]
        SDK_RUN["query() with tools:\nRead, Glob, Grep\ncwd = workspace\nmodel = sonnet\nmax_turns = 30"]
        PARSE["Parse JSON from\nlast json code block"]
    end

    subgraph Output["Output"]
        SCORE["N dimensions × 0-25 pts each"]
        FILE["assessment_eval.json"]
        OPIK["Opik feedback scores"]
    end

    ARTIFACTS --> SDK_RUN
    CRITERIA --> PROMPT
    DIMS --> PROMPT
    INSTRUCTION --> PROMPT
    PROMPT --> SDK_RUN
    SDK_RUN --> PARSE
    PARSE --> SCORE
    SCORE --> FILE
    SCORE --> OPIK
```

---

## ConfigurableClaude — the only custom agent class

```mermaid
classDiagram
    class ClaudeCode {
        <<Harbor built-in>>
        +setup(environment)
        +solve(task)
    }
    class ConfigurableClaude {
        -_sandbox_files: dict~str, str~
        +setup(environment)
        -_upload_sandbox_files(environment)
        +name() str
    }
    ClaudeCode <|-- ConfigurableClaude

    note for ConfigurableClaude "Only reason to exist: Harbor has no\nmechanism for injecting files into\nthe sandbox (e.g. CLAUDE.md, MCP config)"
```

Harbor natively handles auth, MCP servers, model selection, and timeout. `ConfigurableClaude` adds **one thing**: declarative file mapping from host to the sandbox via `sandbox_files` in `harbor_config.json`.

---

## Agent variants

Each benchmark defines its **own set of variants** — there are no globally shared variants. A variant represents a specific agent configuration to be compared against other variants on the same set of tasks.

Each variant is a directory under `variants/<variant-name>/` containing:
- `CLAUDE.md` — project instructions injected into `/app/CLAUDE.md` in the sandbox (required)
- `skills/` — skill snapshots, each `skills/<name>/SKILL.md` injected into `/app/.claude/skills/<name>/SKILL.md` (optional)
- `harbor_config.json` — agent import path + `sandbox_files` mapping (auto-generated if absent)
- `claude_config.json` — MCP server configuration (optional)

This mirrors a real Claude Code project where CLAUDE.md and `.claude/skills/` are separate concerns. Skills in variants are deterministic snapshots — copies of the skill at a specific point in time, not references to external sources.

Variants can differ along many axes: instruction specificity, skill combinations, tool access, constraints, prompting techniques.

---

## Opik integration

```mermaid
flowchart LR
    subgraph Harbor_Run["During Harbor job"]
        OPIK_WRAP["track_harbor()\n(monkey-patches Harbor)"]
        TRACE["Automatic trace\nname: agent/trial\n+ spans per step\n+ token usage"]
    end

    subgraph Assessment_Upload["After assessment eval"]
        EVAL["evaluator.evaluate_job()"]
        SEARCH["search_traces()\nby name agent/trial"]
        FB["log_traces_feedback_scores()"]
    end

    OPIK_WRAP --> TRACE
    TRACE -.->|"trace_id"| SEARCH
    EVAL --> SEARCH
    SEARCH --> FB

    FB --> SCORES["Feedback scores:\narch_<dimension>\narch_total\nreward\nduration_sec"]
```

Two integration points:
1. **`track_harbor()`** — Opik's monkey-patch over Harbor. Automatically creates traces with agent steps, token usage, and duration
2. **`evaluate_job() --with-opik`** — finds the existing trace by name `agent_name/trial_name`, attaches feedback scores

---

## Orchestration — `nasde run`

```mermaid
sequenceDiagram
    participant User
    participant CLI as cli.py
    participant Runner as runner.py
    participant Harbor as Harbor Job (Python API)
    participant Eval as evaluator.py

    User->>CLI: nasde run --variant vanilla --harbor-env daytona
    CLI->>CLI: Load project config (nasde.toml)
    CLI->>Runner: run_benchmark(config, harbor_env="daytona")
    Runner->>Runner: Merge variant config + registry + CLI params
    Runner->>Runner: Set environment = {"type": "daytona"}

    Runner->>Harbor: JobConfig.model_validate(merged) → Job.run()
    Harbor-->>Runner: Results in jobs/timestamp/

    Runner->>Runner: unset CLAUDECODE
    Runner->>Eval: evaluate_job(job_dir, with_opik)
    Eval->>Eval: For each trial in job_dir
    Eval-->>Runner: assessment_eval.json + Opik feedback
```

The runner builds a **merged config** by combining:
- `variants/<name>/harbor_config.json` — agent definition (import path, sandbox_files)
- Task registry — discovered from `tasks/` directory
- CLI parameters — model, timeout, harbor_env, task filter

---

## Trial result structure

```
jobs/2026-03-12__14-30-00/
└── sample-task__vanilla__0/
    ├── result.json              # reward, duration, task_id, source
    ├── config.json              # Agent config used for this trial
    ├── assessment_eval.json     # LLM-as-a-Judge evaluation result
    ├── agent/
    │   └── trajectory.json      # ATIF: agent steps, tool calls, tokens
    └── artifacts/
        └── workspace/           # Modified files from /app/
```

---

## Package structure

```
src/nasde_toolkit/
  cli.py                   # Typer CLI (init, run, eval + harbor/opik pass-through)
  config.py                # nasde.toml + task.json parsing into dataclasses
  runner.py                # Harbor Python API — variant resolution, config merging, Job execution
  evaluator.py             # Post-hoc assessment via Claude Code SDK
  docker.py                # Docker environment helpers
  scaffold/                # Project scaffolding templates
  agents/
    configurable_claude.py # Harbor-compatible agent with sandbox file injection
```
