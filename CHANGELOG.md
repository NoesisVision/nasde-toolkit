# Changelog

All notable changes to **nasde-toolkit** are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

See [docs/RELEASING.md](docs/RELEASING.md) for the release procedure.

## [Unreleased]

### Changed
- Modernized dependencies: `harbor` 0.1.45 → 0.4.0, `opik` 1.10.39 → 2.0.9.
  Brings upstream bugfixes and removes a long-standing Opik monkey-patch that
  is no longer needed. `ConfigurableCodex` simplified by ~80 LOC thanks to
  Harbor 0.4 adding first-class support for files-to-inject. ([#25])
- Default reviewer model bumped to `claude-opus-4-7` across README, ARCHITECTURE,
  bundled `nasde-benchmark-runner` skill, and example benchmarks
  (`ddd-architectural-challenges`, `refactoring-skill`). `nasde-dev-skill`
  stays on Sonnet 4.6 as documented in [benchmark results](docs/benchmark-results.md).

### Security
- Added `pip-audit` as a CI gate. Fixes 20 known CVEs across the transitive
  dependency tree, including 1 CRITICAL and 3 HIGH in `litellm` / `cbor2`.
  New vulnerabilities will now fail the quality gate instead of shipping
  silently. ([#25])

### Docs
- README: unified "what NASDE does" opener around four steps, mentioning the
  rough `test.sh` pass/fail gate that precedes LLM-as-a-judge scoring.
- README: scoring section now calls out that criteria can cover the agent's
  run-time signals — tool-call trajectory, token usage, wall-clock duration —
  alongside the produced artifacts.

## [0.2.0] — 2026-04-22

### Added
- **Subprocess evaluator backends.** The LLM-as-a-judge reviewer now runs as
  a subprocess against the installed `claude` or `codex` CLI instead of going
  through the Anthropic Agent SDK. Select with `[evaluation] backend` in
  `nasde.toml` (`"claude"` default, `"codex"` available). This unlocks
  subscription billing (Claude Max, ChatGPT Plus) for local evaluation, and
  picks up the user's existing OAuth/keychain auth without extra config. ([#24])
- **Bundled authoring skills.** `nasde install-skills` copies the
  `nasde-benchmark-*` skills into `~/.claude/skills/` so they're available in
  every Claude Code session. `--scope project` and `--force` flags supported.
- **Trajectory-aware evaluation.** Set `[evaluation] include_trajectory = true`
  to give the reviewer access to the agent's ATIF trajectory
  (`agent/trajectory.json`) alongside the final workspace — lets criteria
  reward *how* the agent arrived at the result, not just the result itself. ([#22])
- **MCP server configuration per variant.** Drop a `claude_config.json` into
  a variant directory to wire up MCP servers for that variant's agent runs.

### Changed
- README rewritten for a developer audience: problem-first framing, explicit
  "why NASDE" section, reference point for how the rubric concept maps to
  familiar engineering practice.
- `nasde eval` now forwards the full `[evaluation]` config from `nasde.toml`
  to the post-hoc evaluator (previously some keys were dropped). ([#23])

### Fixed
- Evaluator now captures a real stderr file descriptor, surfacing actual
  error output when the subprocess fails.
- Clearer diagnostics when the evaluator's Claude Code process exits non-zero.
- `scripts/export_*_oauth_token.sh` no longer use `set -e`, so sourcing them
  into a shell that hits an error no longer kills the terminal.

## [0.1.1] — 2026-03-26

### Added
- Noesis Vision, CI status, and License badges in the README header.
- Stable-vs-HEAD installation instructions: `@v0.1.1` for pinned installs,
  `@main` for bleeding edge.

### Changed
- Version is now derived from git tags via `hatch-vcs` — no more hand-edited
  `version = "…"` in `pyproject.toml`. `_version.py` is auto-generated and
  gitignored. See [ADR-007](docs/adr/).

### Fixed
- `_version.py` correctly excluded from ruff and mypy (no more noisy lint
  output on generated code).
- Removed auto-generated `harbor_config.json` from shipped examples — it was
  leaking per-machine absolute paths into the repo.

## [0.1.0] — 2026-03-26

Initial release under the **nasde-toolkit** name (rebrand from
`sdlc-eval-kit`). This is the first version intended for outside use.

### Added
- **`nasde` CLI** with `init`, `run`, `eval`, `install-skills`, plus
  pass-throughs for `nasde harbor …` and `nasde opik …`.
- **Harbor Python API integration.** The runner builds `JobConfig` directly
  and calls `await job.run()`, replacing the earlier subprocess dance. Trial
  lifecycle, variant resolution, and sandbox execution all go through
  Harbor.
- **Cloud sandbox providers.** `--harbor-env` selects `docker` (default),
  `daytona`, `modal`, `e2b`, `runloop`, or `gke` for where the agent trial
  runs. Same benchmark, any backend.
- **Assessment evaluation on by default** — LLM-as-a-judge reviewer runs
  after every trial unless `--without-eval` is passed. Results land in
  `assessment_eval.json` per trial and upload to Opik when `--with-opik`
  is set.
- **Three agent types:** Claude Code, Codex (OpenAI), and Gemini CLI. Each
  with its own sandbox file-injection path (`CLAUDE.md` / `AGENTS.md` /
  `GEMINI.md`) and OAuth support (ChatGPT subscription for Codex, Google
  account for Gemini).
- **Auto-generated Dockerfile.** When a task has no
  `environment/Dockerfile`, `nasde` generates one from `source.git` and
  `[docker]` config in `nasde.toml`. Local paths get a
  `docker-compose.yaml` override for the build context.
- **Skill snapshots per variant.** `variants/<name>/skills/`,
  `agents_skills/`, and `gemini_skills/` directories are injected into the
  agent's sandbox so benchmarks stay deterministic across runs.
- **Benchmark-authoring skills.** `nasde-benchmark-creator`,
  `nasde-benchmark-from-history`, `nasde-benchmark-from-public-repos`, and
  `nasde-benchmark-runner` for building and running benchmark suites from
  inside Claude Code.
- **Docs.** `ARCHITECTURE.md` (end-to-end flow with diagrams),
  `docs/use-cases.md` (worked examples), `docs/benchmark-results.md`
  (reference numbers), ADRs for key decisions, MIT license,
  Noesis-branded ASCII banner.
- **CI pipeline.** GitHub Actions for quality gate (lint, typecheck,
  tests), example validation, and dogfooding.
- **Parallel runs and retries.** `--all-variants` for Cartesian product
  runs, `--attempts/-n` for multi-attempt per task, per-trial streaming
  hooks for Opik.

### Notes
- `v0.1.0` represents the first public-oriented baseline; earlier commits
  on the `sdlc-eval-kit` history are not cataloged here.

[Unreleased]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/NoesisVision/nasde-toolkit/releases/tag/v0.1.0
[#22]: https://github.com/NoesisVision/nasde-toolkit/pull/22
[#23]: https://github.com/NoesisVision/nasde-toolkit/pull/23
[#24]: https://github.com/NoesisVision/nasde-toolkit/pull/24
[#25]: https://github.com/NoesisVision/nasde-toolkit/pull/25
