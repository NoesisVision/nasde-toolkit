# ADR-013: Layered pricing override (convention over config)

**Status:** Accepted
**Date:** 2026-06-22

## Context

Token-cost metrics (ADR-011) price every trial against a model-rate catalog,
`src/nasde_toolkit/pricing.toml`, bundled into the wheel. The loader
`pricing.load_pricing(path)` accepted an override path, but both real call sites —
`evaluator.py` (run → `assessment_summary.json`) and `results_exporter.py`
(export → `metrics.json`) — always called it with no argument, so the bundled
catalog was the *only* catalog.

After a PyPI / `uv tool install`, that catalog lives inside an isolated
environment. Correcting a stale rate or adding a model meant editing a file in
`site-packages` — an anti-pattern that is wiped on the next upgrade. Model prices
change far more often than `nasde` releases, and users have their own rates
(enterprise discounts, Azure/Bedrock, private contracts). The product goal —
evaluating the *cost* of migrating between agents — depends on locally-correct,
locally-controllable prices. The docs already flagged a per-project / per-user
override as planned.

## Decision

Pricing is overridable **by convention, not configuration**. A file literally
named `pricing.toml` placed at a known location is auto-detected and merged onto
the bundled catalog — there is **no `[pricing]` section in `nasde.toml`** and **no
configurable filename**. This mirrors `assessment_dimensions.json`, which is also
a fixed-name file discovered by convention.

A new public entry point `pricing.load_pricing_layered(project_dir)` merges three
layers, **higher wins, per-model whole-entry replacement**:

1. `<project_dir>/pricing.toml` — project layer (highest)
2. `~/.nasde/pricing.toml` — user layer
3. bundled `pricing.toml` — the floor (always present, the only required layer)

An override file lists **only the models it changes or adds**; every other model
falls through to the layer below. The merge is `dict.update` over whole
`ModelPrice` entries — **not** a per-field blend: a model entry in an override
replaces the lower layer's entry entirely, so a field the override omits takes the
`ModelPrice` default (`cached_input_per_1m=None`, `source=""`), it is *not*
inherited. This is the least-surprising rule and mirrors the whole-value override
semantics of `--model > variant.toml > default`. A missing project/user file is
silently skipped. When a layer file is found and applied, one dim console line is
printed (transparency), never for the skipped case.

**User layer is `~/.nasde/`, a HOME dotfolder — deliberately not `platformdirs`.**
Every agent CLI the user works with keeps its *user config* in a HOME dotfolder
(`~/.claude` + `~/.claude.json`, `~/.codex`, `~/.gemini`); `platformdirs.user_config_dir`
maps to `~/Library/Application Support` on macOS, which is where Electron app-state
(cookies, caches) lives, not a file a human edits. Config belongs in the dotfolder;
`platformdirs` stays for cache (`update_check.py::user_cache_dir`). One path on
every OS.

**Both write paths thread `project_dir`.** `token_metrics.build_trial_economics`
is the single extractor feeding both `assessment_summary.json` (run) and
`metrics.json` (export) — so the override has to reach both, or the same trial
would report two different costs. The run path already had `project_root` in hand
(`evaluate_job`); the export path gained a `project_dir` argument on
`export_results`, supplied from `config.project_dir` in the CLI. Calibration
(`calibration_publisher`) reuses `_build_metrics` and threads `project_root` too.
The merged catalog is **not** cached: it depends on `project_dir` and on on-disk
file contents that can change between runs, and a per-job re-read is cheap. The
bundled `_load_bundled_pricing` keeps its `lru_cache` (invariant), and
`load_pricing(path)` is unchanged.

## Consequences

- Users override model prices post-install without touching the wheel — drop a
  `pricing.toml` in the project root, or `~/.nasde/pricing.toml` machine-wide.
- The bundled catalog stays the auditable floor, each entry stamped with
  `as_of` / `source`; overrides layer on top per-model.
- A re-run or re-export picks up an edited `pricing.toml` immediately — no new
  agent runs needed to recost.
- Run and export agree on cost for the same trial, preserving the ADR-011
  invariant.
- Determinism and the "confirm rates before quoting figures" caveat from ADR-011
  carry over — a wrong override produces wrong (but deterministic) costs.
- The effective catalog is **inspectable**: `resolve_pricing_layers` /
  `effective_pricing_with_source` expose which layer supplied each rate, surfaced
  via `nasde pricing show [--show-source]`, a "Pricing used" table in the `nasde run`
  summary, and a `pricing_used.json` in `results-export`. This makes the
  transparency the convention promises actually verifiable — you can confirm a
  three-layer override composed as intended, and an exported report is a
  self-contained cost audit.

## References

- ADR-011 (token & cost metrics) — the single-extractor invariant this override
  must respect.
- `assessment_dimensions.json` — the fixed-name-by-convention precedent.
