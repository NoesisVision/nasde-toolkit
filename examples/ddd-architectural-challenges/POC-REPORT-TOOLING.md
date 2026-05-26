# POC: benchmark report tooling (not for release)

This branch parks two **work-in-progress** report/analysis scripts that are NOT
ready for the public release and were deliberately removed from the main
experiment branch:

- `build_experiment_log.py` — scans `jobs/` and emits a per-attempt Markdown
  journal (variant, hash, skill activation, reward, #evals, per-dimension mean/σ,
  time, tokens). General-ish but driven by a hardcoded `ARMS` list.
- `assets/make_charts.py` — generates the radar / increment / token / time charts
  from hardcoded final numbers.
- `analyze_focus.py` — the original throwaway aggregator: hardcoded to the
  `focus-vanilla` / `focus-skill` prefixes and **estimates dollar cost from a
  hardcoded price table** (we decided NOT to estimate cost). Superseded by
  `build_experiment_log.py`.
- `EXPERIMENT_LOG.md` — OUTPUT of `build_experiment_log.py` (per-attempt journal).
- `EXPERIMENT_STATUS.md` — paired human verdict that accompanies that log.

The EXPERIMENT_* files live here (not on the experiment/release branch) because they
are script artifacts, not part of the shipped example. The release example keeps only
the rendered chart PNGs as worked-example results.

## Why parked, not shipped
These were built ad-hoc during the tactical-ddd experiment. To belong in the
release they need to become a real, integrated feature, not loose scripts:

1. **Integrate into the toolkit**, not a sidecar script — e.g. a `nasde report`
   command (read `jobs/`, emit Markdown/CSV + charts), so users discover it.
2. **Update the `nasde-benchmark-runner` skill** to mention/use it — right now the
   skill doesn't know it exists.
3. **Test it.** Ideally dogfood: add a NASDE benchmark (next to `nasde-dev`) that
   exercises the reporting path, so we eval our own tool with our own tool.
4. Drop cost estimation, or make it opt-in with a real price source (not hardcoded).
5. Generalize away from hardcoded `ARMS` / `focus-*` prefixes — derive
   variants/tasks from the job dirs or config.

## What SHIPS on the experiment branch instead
The experiment branch keeps the *outputs* (charts PNGs + EXPERIMENT_LOG.md /
EXPERIMENT_STATUS.md as example results) — those have value as a worked example.
It does NOT ship these generator/analysis scripts.

Owner: pick up as a standalone feature branch off this POC.
