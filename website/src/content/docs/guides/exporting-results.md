---
title: Exporting Results
description: Copy the analytic essence of trial artifacts out of the gitignored jobs/ tree into a plain destination directory.
---

:::caution[Experimental / beta]
This command is new; the layout may still change. Feedback welcome.
:::

By default a run's output lives only in the local, gitignored `jobs/` directory — and most of its weight is build junk (compiled binaries, `.git` checkouts) that's useless for analysis. If you clear `jobs/`, the results are gone. `nasde results-export` copies just the **essence** of each trial into a plain destination directory so your results survive and travel:

```bash
nasde results-export jobs/2026-03-13__14-30-00 --to ~/Dropbox/nasde-results -C my-benchmark
```

The destination is any path you like — an iCloud or Dropbox folder, an external drive, or a git repo you commit yourself. NASDE just writes files there; it never talks to a cloud provider, so there's nothing to authenticate. Each trial becomes one flat folder `<job>__<trial>/` containing:

- `metrics.json` — self-contained summary: timing, model, variant, task, reward, reasoning effort, **token usage + USD cost** (see [Token & cost](/nasde-toolkit/concepts/token-cost/))
- `assessment_eval_*.json` — the reviewer's per-dimension scores and reasoning (one file per repetition)
- `assessment_summary.json` — per-dimension mean/std/range across repetitions (the representative result)
- `trajectory.json` — the agent's full tool-call trace, for post-hoc cost/process analysis
- `changes.patch` — exactly what the agent changed (a code diff, not the multi-GB workspace)
- `verifier_stdout.txt`, `reward.txt` — the rough-test output

You can pass several paths at once, mixing whole jobs and individual trials — NASDE figures out which is which. Re-running is safe: it merges (copying any evaluations added since the last export) and never re-touches the immutable trajectory or patch.
