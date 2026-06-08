---
name: nasde-benchmark-calibration
description: |
  Calibrate assessment rubrics by reviewing agent work in GitHub/GitLab PRs and feeding human comments back into the rubric. Use this skill when the user wants to:
  - Calibrate, tune, or sanity-check assessment criteria / dimensions of a benchmark
  - Review trial diffs alongside the LLM-as-a-Judge scores in a PR/MR
  - Investigate why judge scores feel off, too harsh, too lenient, or misaligned with how a human would grade the code
  - Pull review comments back from PRs/MRs and turn them into concrete rubric edits
  Even if the user doesn't say "calibrate" — if they're worried the LLM judge's scores diverge from human judgment, or want to align scores with a real developer's opinion before freezing a benchmark, this skill applies.
---

# NASDE Benchmark Calibration

Close the loop between the LLM-as-a-Judge and a human reviewer. The judge scores trials against
`assessment_criteria.md` (per task) and `assessment_dimensions.json` (benchmark-wide) — but an LLM
judge is an imperfect grader, and how it reads the rubric may diverge from how a human grades the code.
This skill publishes trial diffs + scores as Pull/Merge Requests for human review, pulls the comments
back, and proposes concrete rubric edits.

This is the third skill in the benchmark lifecycle: `nasde-benchmark-creator` writes the rubric,
`nasde-benchmark-runner` runs trials and scores them, and **this skill calibrates the rubric** against
human judgment before the benchmark is frozen.

## Prerequisites

- A sink repository that already exists (creation is out of scope). Configure it in `nasde.toml`:
  ```toml
  [calibration]
  repo = "https://github.com/Org/nasde-calibration"   # full URL or owner/repo slug
  # platform = "gitlab"        # only needed for a bare slug or a self-hosted host
  # base_branch = "main"
  # throttle_sec = 2.0
  ```
- The platform CLI for that repo's host: `gh` (GitHub) or `glab` (GitLab), installed and logged in
  (`gh auth login` / `glab auth login`). The platform is auto-detected from the repo URL host. nasde
  never handles tokens — the CLI's keyring does. See ADR-010.
- `git` on PATH.

## Workflow

### 1. Decide which trials to calibrate

Calibration is about the **criteria**, not individual runs. Discuss with the user which trials to
publish: a representative trial per (task, variant) is usually enough; publishing every repetition
floods the sink with PRs. Selecting trials is the agent's judgment here — there is no `--select` flag
yet (that logic may move into the CLI once the workflow settles).

You can pass job directories (all their trials) or individual trial directories — mixed is fine.

### 2. Publish

```bash
nasde calibrate publish jobs/<job>/<trial>__<id> -C <project_dir>
# or a whole job:
nasde calibrate publish jobs/<job> -C <project_dir>
```

Each trial becomes one PR/MR:
- An **orphan base branch** `base/<repo>-<sha>` holds the agent's start-state codebase (seeded once
  per (repo, commit); git deduplicates shared blobs across bases).
- The **feature branch** `calib/<repo>-<sha>/<trial>` carries the agent's diff applied as a real
  commit, so the PR diff is *exactly* the agent's work — clean to review.
- The **description** renders the dominant evaluator cluster's per-dimension `mean ± std`, the
  normalized score, and a "How to calibrate" note.
- A **`.calibration/` directory** ships the review context: the task's `instruction.md` (what the
  agent was asked to do), the `assessment_criteria.md` + `assessment_dimensions.json` the judge scored
  against, every `assessment_eval_<N>.json` (full per-dimension reasoning), and `metrics.json`. This
  lets the reviewer judge whether a score is fair without leaving the PR.

Re-running is idempotent — a trial whose **open** PR/MR already exists is skipped. Closing a
calibration round lets the same trials be re-published into a fresh round. Give the user the PR/MR
URLs and ask them to review the diffs and comment inline where a score disagrees with their judgment.
If a second person should review, the user adds them as a collaborator on the sink repo.

### 3. Pull the comments back

After the user has reviewed:

```bash
nasde calibrate pull-comments jobs/<job>/<trial>__<id> -C <project_dir> --json
```

`--json` emits a machine-readable structure (issue-level + inline comments, each with `path`/`line`
when inline) — consume it directly. Without `--json` it prints a summary table.

### 4. Diagnose the divergence per dimension

For each comment, line it up against the judge's score for that trial (read
`assessment_summary.json` for the per-dimension `mean ± std`, and `assessment_eval_*.json` for the
per-dimension `reasoning`). Inline comments carry a `path`/`line` — map that back to which
dimension's rubric is implicated.

Classify each divergence:
- **Judge too harsh** — human says the code is fine, judge scored low → the rubric's threshold for
  that dimension is too strict, or its description rewards the wrong thing.
- **Judge too lenient** — human flags a problem the judge missed → the rubric doesn't describe the
  failure mode, or its scale lacks resolution there.
- **Aligned** — no action; record it as a positive signal.

A human "I think this score should be X" comment is a free-text gold label — interpret it; do not
expect a rigid format.

### 5. Propose the rubric edit (for approval)

The rubric to edit lives at `evals/<source>/tasks/<task>/assessment_criteria.md` (per task) or
`evals/<source>/assessment_dimensions.json` (benchmark-wide, when the divergence is about a
dimension's scale/description, not one task's thresholds). The `<source>` and `<task>` come from the
trial's `result.json` (`source`, `task_name`).

Show the user a concrete **diff of the rubric** — the specific threshold/description change that would
have moved the judge toward the human's score — and **wait for approval before writing**. Never edit
the rubric silently.

After the edit, the loop repeats: re-run the trial through `nasde-benchmark-runner` (or re-eval an
existing job with `nasde eval`) and re-publish to confirm the judge now aligns. This iterative
measure → diagnose → fix → re-measure loop is the point of calibration.

## Notes

- Trajectories are intentionally NOT published to the PR (they may contain secrets and clutter the
  diff). The PR carries the diff, the assessment files, and metrics only.
- One trial = one PR. All of that trial's repeated evaluations are summarized in the description and
  shipped as `.calibration/assessment_eval_<N>.json`.
- The platform is inferred from the repo URL — GitHub and GitLab both work with no code change, only
  the right CLI installed.
