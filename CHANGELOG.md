# Changelog

All notable changes to **nasde-toolkit** are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

See [docs/RELEASING.md](docs/RELEASING.md) for the release procedure.

## [Unreleased]

## [0.3.2] — 2026-05-07

### Added
- **PyPI publishing.** `nasde-toolkit` now ships to [PyPI](https://pypi.org/project/nasde-toolkit/);
  install with `uv tool install nasde-toolkit` (or `pipx`/`pip`). Tag pushes
  trigger an automated `publish.yml` workflow that builds, runs a fresh-install
  smoke test on TestPyPI, gates the production publish on the smoke test
  passing, then publishes to PyPI and creates a GitHub Release. ([#36], [#38])
- **In-CLI update notifier.** `nasde` checks PyPI for newer releases on
  startup and prints a one-line notice on stderr when one is available
  (severity-tinted: patch / minor / major). Notify-only — never auto-applies,
  never prompts. Skips on no-TTY, `NASDE_NO_UPDATE_CHECK=1`, `CI=true`, and
  dev/pre-release builds. Cached for 24h via `platformdirs`. ([#36])
- **Weekly TestPyPI canary.** Monday 09:00 UTC cron re-publishes a fresh dev
  build to TestPyPI and runs the smoke test against it — catches transitive
  dependency breakage (e.g. an upstream wheel going bad) in the window
  between releases. ([#38])

### Changed
- **Bump `harbor` to `>=0.6,<0.7`** (latest 0.6.4). Adapter additions,
  Modal/Windows support, gemini-cli v0.40+ session improvements, plus a
  field rename in `JobStats` (`n_trials` → `n_completed_trials`) that the
  runner now handles. No user-facing CLI or config changes. ([#38])
- **Refresh `opik` to 2.0.22** within the existing `>=2,<3` range. ([#38])
- Enriched `pyproject.toml` with project URLs, classifiers, and keywords
  for a proper PyPI project page. ([#36])

### Fixed
- Strip the local-version segment (`+gHASH`) from `hatch-vcs` output so dev
  builds are PyPI-acceptable as pre-releases (`0.3.2.devN` instead of
  `0.3.2.devN+gabcdef`). PEP 440 forbids local versions on the public index. ([#37])
- Pin `supabase>=2.29.0,<3` to skip broken upstream wheels. `supabase 2.28.3`
  and `3.0.0a1` ship wheels missing the `_async/` and `_sync/` subpackages,
  which made `nasde --version` crash at import in fresh installs. ([#38])
- Adapt `_print_job_summary` in the runner to harbor 0.6's `JobStats` field
  rename; previously crashed with `AttributeError` after a successful trial. ([#38])

### Docs
- Rewrote `docs/RELEASING.md` and `docs/ci-setup.md` for the automated
  publish flow. Includes a recovery table for failure modes encountered
  during pipeline verification. ([#38])

### Internal
- `publish.yml` workflow with PyPI Trusted Publishing (OIDC) — no long-lived
  tokens or secrets. Reuses `quality-gate.yml` via `workflow_call`. ([#36])
- `pyproject.toml`: explicit `packaging>=25,<26` dependency (used by the
  update notifier; was previously transitive). ([#36])
- TestPyPI uploads use `skip-existing: true` so re-runs of `workflow_dispatch`
  with the same `devN` filename are no-ops instead of `400 File already exists`. ([#38])

## [0.3.0] — 2026-05-05

### Changed
- **Breaking: per-task config consolidated into a single `task.toml`.** The
  previous split between `task.json` (nasde-only) and `task.toml` (Harbor) is
  gone — Harbor sections (`[task]`, `[agent]`, `[environment]`, `[verifier]`,
  `[metadata]`) and nasde-specific fields (`[nasde.source]`) now live side by
  side in one file. All bundled examples migrated. ([#29])
- **Breaking: `model` is now required in every `variant.toml`.** There is no
  project-level model default in `nasde.toml` anymore — different agent
  families need different models, so each variant declares its own. Missing
  model fails fast with a clear error. CLI `--model` still overrides. ([#29])

### Added
- **Independent per-dimension scoring scales (ADR-008).** Each dimension in
  `assessment_dimensions.json` declares its own `max_score` (any positive
  integer). `normalized_score` is computed from the actual sum of per-dimension
  maxima — pick the granularity that matches what you can distinguish, instead
  of forcing every benchmark into a fixed total. ([#34])

### Fixed
- Evaluator now prints a clear, actionable error when the underlying `claude`
  or `codex` CLI is missing, instead of failing with a confusing subprocess
  trace. ([#30])
- The "missing CLI" hint now prints `[evaluation]` correctly instead of
  hiding it as Rich markup.

### Security
- Pin `litellm>=1.83.7` to address [GHSA-xqmj-j6mv-4862][gh-litellm-2026-04]. ([#31])

### Docs
- README: clarified how NASDE is meant to be used end-to-end.
- README: Harbor links now point at `harborframework.com` instead of the GitHub
  repo, matching Harbor's primary site.

### Internal
- `CODEOWNERS` added so PRs auto-request review from the right people.

## [0.2.1] — 2026-04-22

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

### Added
- `CHANGELOG.md`, `SECURITY.md`, `docs/RELEASING.md`. ([#26])

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

[Unreleased]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.3.0...v0.3.2
[0.3.0]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/NoesisVision/nasde-toolkit/releases/tag/v0.1.0
[#22]: https://github.com/NoesisVision/nasde-toolkit/pull/22
[#23]: https://github.com/NoesisVision/nasde-toolkit/pull/23
[#24]: https://github.com/NoesisVision/nasde-toolkit/pull/24
[#25]: https://github.com/NoesisVision/nasde-toolkit/pull/25
[#26]: https://github.com/NoesisVision/nasde-toolkit/pull/26
[#29]: https://github.com/NoesisVision/nasde-toolkit/pull/29
[#30]: https://github.com/NoesisVision/nasde-toolkit/pull/30
[#31]: https://github.com/NoesisVision/nasde-toolkit/pull/31
[#34]: https://github.com/NoesisVision/nasde-toolkit/pull/34
[#36]: https://github.com/NoesisVision/nasde-toolkit/pull/36
[#37]: https://github.com/NoesisVision/nasde-toolkit/pull/37
[#38]: https://github.com/NoesisVision/nasde-toolkit/pull/38
[gh-litellm-2026-04]: https://github.com/BerriAI/litellm/security/advisories/GHSA-xqmj-j6mv-4862
