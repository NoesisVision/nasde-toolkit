---
title: The Evaluation Pipeline, End to End
description: How a task flows from instruction through sandboxed execution, rough tests, and the reviewer agent to logged results.
---

```mermaid
flowchart LR
    A["Task:<br/>instruction.md<br/>+ test.sh<br/>+ assessment_criteria.md"] --> B["Coding agent solves task<br/>in an isolated container<br/>(Docker or cloud sandbox)"]
    B --> C["test.sh:<br/>initial rough tests"]
    C --> D["Binary reward<br/>0 or 1"]
    D --> E["Reviewer agent<br/>reads the produced<br/>workspace + trajectory"]
    E --> F["Per-dimension scores<br/>vs. your criteria"]
    F --> G["Results logged<br/>(locally + optional<br/>experiment tracker)"]

    style E fill:#c0392b,color:#fff
```

Stage 1 (the agent does the work in a sandbox) comes from [Harbor](https://www.harborframework.com/). The optional experiment-tracking stage at the end uses [Opik](https://github.com/comet-ml/opik). NASDE is the glue that connects them and adds the reviewer stage in between — plus the CLI, the benchmark project layout, and the [authoring skills](/nasde-toolkit/getting-started/quick-start/).
