<div align="center">
  <a href="https://noesis.vision/nasde/"><img src="nasde-toolkit-logo.png" alt="NASDE Toolkit" width="400"></a>

  <h3>Noesis Agentic Software Development Evals Toolkit</h3>

  <p>Run an AI coding agent on a task you already know the answer to. Score the result. Compare configurations.</p>

  <a href="https://noesis.vision/nasde/"><img src="https://img.shields.io/badge/Product%20Page-Noesis%20Vision-0B6623?style=for-the-badge&logoColor=white" alt="Product Page"></a>
  <a href="https://discord.gg/QF5PMX4Dqg"><img src="https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join our Discord"></a>
  <br>
  <a href="https://github.com/NoesisVision/nasde-toolkit/actions/workflows/quality-gate.yml"><img src="https://img.shields.io/github/actions/workflow/status/NoesisVision/nasde-toolkit/quality-gate.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
</div>

---

## What NASDE does — in four steps

One `nasde run` command executes the whole chain.

1. **You describe a task you already understand.** An instruction, a repo snapshot, and the assessment criteria describing what a good solution looks like. The output can be anything the agent writes into its workspace — code, a migration plan, an ADR, a SQL script, updated docs.
2. **The agent solves it in a sandbox.** The agent works in a safe, isolated environment — it can't touch your machine or your real code. Every run starts from the same clean state, so different configurations get a fair comparison. When it's done, a quick `test.sh` check gives a rough pass/fail signal. Powered by [Harbor](https://www.harborframework.com/), runs locally on Docker or in the cloud.
3. **A reviewer agent assesses the result against your criteria.** After initial rough tests pass or fail, a second coding agent (`claude` or `codex`) navigates the workspace and scores your chosen dimensions (e.g. *domain modeling*, *test quality*) on whatever scale you picked. The review stays token-efficient even on large codebases.
4. **Results land in a dashboard (optional).** Browse scores, compare variants, and track how your agent setup evolves over time — optionally via [Opik](https://www.comet.com/site/products/opik/).

You're the one defining "what good looks like." NASDE just automates running the experiment and assessing it the same way every time.

## 📖 Documentation

**Full documentation lives at → [noesisvision.github.io/nasde-toolkit](https://noesisvision.github.io/nasde-toolkit/)**

Concepts (how the scoring works, the evaluation pipeline, token & cost, rubric calibration), the complete CLI reference, every configuration-file format, authentication, and step-by-step guides — all there, searchable.

- [Quick Start](https://noesisvision.github.io/nasde-toolkit/getting-started/quick-start/) — zero to a working benchmark from your own git history
- [How scoring works](https://noesisvision.github.io/nasde-toolkit/concepts/scoring/) — the two independent kinds of scoring
- [A real task, end to end](https://noesisvision.github.io/nasde-toolkit/concepts/real-task-example/) — instruction, criteria, and scores
- [CLI commands](https://noesisvision.github.io/nasde-toolkit/reference/commands/) — the full command reference
- [Use Cases](https://noesisvision.github.io/nasde-toolkit/guides/use-cases/) · [Benchmark Results](https://noesisvision.github.io/nasde-toolkit/guides/benchmark-results/) — worked examples with numbers

## What do I use it for?

Anyone working with AI coding agents eventually hits the same wall: *"I changed my skill / `CLAUDE.md` / MCP setup — is the agent actually better now, or does it just feel that way?"* NASDE turns that gut feeling into a repeatable measurement which is **easy to do even on a personal machine, with a Claude Code or Codex subscription**.

Typical things you'd do with it:

- **Run an agent safely on a realistic task** — a sandboxed container means the agent can `rm -rf`, install random packages, or run your tests in loops without wrecking your laptop.
- **Compare two configurations of the same agent** — baseline vs. "with my new skill"; see whether the skill moves the score up or down, and on which dimensions.
- **Compare different agents on the same task** — Claude Code vs. Codex vs. Gemini CLI against *your* workspace and *your* criteria.
- **Build a regression suite for your AI setup** — once a task set exists, re-run it every time someone tweaks the prompt/skills/MCP and spot regressions before they ship.

## Quick start

The fastest path from zero to a working benchmark built from **your own git history**:

```bash
# 1. Install the CLI
uv tool install nasde-toolkit --python 3.13
nasde --version

# 2. Install the authoring skills for Claude Code
nasde install-skills
```

> **Python version**: we recommend `--python 3.13` (`3.12` is also supported). Python **3.14 is not yet supported** — a transitive dependency hasn't released cp314 wheels.

Then, from inside your own repo, ask Claude Code:

> *"Create a NASDE benchmark with a single task, based on a recent piece of work from this repo — a commit, a range of commits, or a merged PR."*

The `nasde-benchmark-from-history` skill proposes a good candidate and scaffolds the task files for you to review. Then run it:

```bash
nasde run --all-variants -C path/to/generated-benchmark
```

**Start small** — one task is enough to validate the loop end to end. Your existing `claude` / `codex` / `gemini` CLI auth covers it (a Claude Max or ChatGPT Plus subscription is enough). API keys work too.

→ Full walkthrough: **[Quick Start](https://noesisvision.github.io/nasde-toolkit/getting-started/quick-start/)** · **[Installation reference](https://noesisvision.github.io/nasde-toolkit/getting-started/installation/)** · **[Authentication](https://noesisvision.github.io/nasde-toolkit/reference/authentication/)**

## Authoring helpers (Claude Code skills)

Writing `assessment_criteria.md`, picking tasks from git history, and scaffolding Dockerfiles is the tedious part of building a benchmark. NASDE ships [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) that take care of most of it — install them with `nasde install-skills`:

| Skill | What it does |
|-------|-------------|
| **nasde-benchmark-creator** | Interactive end-to-end scaffolding: project layout, tasks, Dockerfiles, test scripts, assessment criteria. |
| **nasde-benchmark-from-history** | Point it at a commit range, a merged PR, or a closed issue from your own repo — it proposes tasks based on work your team already finished, and writes the task files for you to review. |
| **nasde-benchmark-from-public-repos** | Describe a skill you want to test broadly; it builds a diversity matrix of public repos (languages, sizes, styles) and scaffolds one task per cell. |
| **nasde-benchmark-runner** | Guides running benchmarks, re-running the reviewer on existing results, verifying the experiment tracker, and troubleshooting failed runs. |
| **nasde-benchmark-calibration** | Publishes trial diffs + scores as PRs/MRs, pulls your review comments back, and proposes concrete rubric edits — the human-in-the-loop calibration loop. |

You don't *have* to use these — everything they do is just writing files you could write by hand — but they save a lot of typing.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system architecture with diagrams, and [docs/adr/](docs/adr/) for architectural decision records. Release notes live in [CHANGELOG.md](CHANGELOG.md).

Key design: `nasde` is a **thin integration layer** over Harbor and Opik, not a replacement. Core flow uses their Python APIs directly; utility commands pass through to their CLIs unchanged.

## Community

Have questions, want to share your benchmarks, or discuss AI agent evaluation strategies? Join our Discord community — we'd love to hear from you!

[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/QF5PMX4Dqg)

## Security

Found a security issue? Please report it privately — see [SECURITY.md](SECURITY.md) for the reporting channels, response timeline, and what's in scope.
