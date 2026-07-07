"""Acceptance assertions for calibration round 2 (ddd-weather-discount, rubric v2).

Computes the five loop stop-conditions from CALIBRATION_ROUND2_2026-07-07.md
mechanically, from assessment_eval_*.json files — no human in the loop for the
check itself. Every assertion is a falsifiable prediction derived from a
diagnosed v1 misfire, with a direction and a margin.

Usage:
    uv run python calibration_round2_check.py <job-dir> [--project-dir .]

Exit code 0 = all criteria pass (v2 accepted), 1 = at least one FAIL.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from nasde_toolkit.evaluator import _dimensions_fingerprint

# Human-approved reference ranking (2026-07-07). Buckets: A exemplary,
# B good-with-flaws, C flawed modeling, D disqualified.
REFERENCE_BUCKETS: dict[str, str] = {
    "SuuU3yh": "C",
    "Kc8Es5k": "C",
    "2yQqBnm": "B",
    "3vwBnrU": "B",
    "ZvSsnyg": "C",
    "qHCAtXV": "B",
    "Jyu9YsY": "C",
    "aGTFmDh": "B",
    "SnS5iHF": "B",
    "4njch2w": "D",
    "cE8V77t": "C",
    "URtZnzf": "D",
    "FjYQ3XQ": "A",
}
BUCKET_RANK = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}

# Margins (fractions of a dimension's max score). Chosen from the v1 empirical
# distribution: v1's worst within-judge std was 20% of scale and its worst
# cross-judge gap 35%, while FULL/PARTIAL/NONE check quantization implies a
# natural noise floor of roughly one check's half-step (~4-8%).
STD_LIMIT_FRACTION = 0.08
GAP_LIMIT_FRACTION = 0.12
SPEARMAN_MIN = 0.8
DISJOINTNESS_MAX_ABS_R = 0.6


@dataclass
class TrialEvals:
    suffix: str
    # evaluator_model -> list of eval dicts (v2 fingerprint only)
    by_model: dict[str, list[dict]] = field(default_factory=dict)


@dataclass
class CheckResult:
    criterion: str
    passed: bool
    detail: str


def _std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def _ranks_with_ties(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks_with_ties(xs), _ranks_with_ties(ys))


def collect(job_dir: Path, fingerprint: str) -> list[TrialEvals]:
    if not job_dir.is_dir():
        return []
    trials: list[TrialEvals] = []
    for trial_dir in sorted(job_dir.iterdir()):
        if not (trial_dir / "result.json").exists():
            continue
        suffix = trial_dir.name.rsplit("__", 1)[-1]
        if suffix not in REFERENCE_BUCKETS:
            continue
        trial = TrialEvals(suffix=suffix)
        for eval_path in sorted(trial_dir.glob("assessment_eval_*.json")):
            data = json.loads(eval_path.read_text(encoding="utf-8"))
            if data.get("dimensions_fingerprint") != fingerprint:
                continue
            trial.by_model.setdefault(data["evaluator_model"], []).append(data)
        trials.append(trial)
    return trials


def _dim_scores(evals: list[dict], name: str) -> list[float]:
    return [float(d["score"]) for e in evals for d in e["dimensions"] if d["name"] == name]


def _dim_max(trials: list[TrialEvals], name: str) -> float:
    for trial in trials:
        for evals in trial.by_model.values():
            for e in evals:
                for d in e["dimensions"]:
                    if d["name"] == name:
                        return float(d["max_score"])
    raise ValueError(f"dimension '{name}' not found in any evaluation")


def _dimension_names(trials: list[TrialEvals]) -> list[str]:
    for trial in trials:
        for evals in trial.by_model.values():
            for e in evals:
                return [d["name"] for d in e["dimensions"]]
    return []


def _normalized_mean(trial: TrialEvals, model: str) -> float:
    return statistics.fmean(float(e["normalized_score"]) for e in trial.by_model[model])


def check_repeatability(trials: list[TrialEvals], dims: list[str]) -> CheckResult:
    worst = ("", 0.0, 0.0)
    for trial in trials:
        for model, evals in trial.by_model.items():
            for dim in dims:
                limit = STD_LIMIT_FRACTION * _dim_max(trials, dim)
                std = _std(_dim_scores(evals, dim))
                if std - limit > worst[1] - worst[2]:
                    worst = (f"{trial.suffix}/{model}/{dim} std={std:.2f} (limit {limit:.2f})", std, limit)
    passed = worst[1] <= worst[2]
    return CheckResult("1. repeatability (std <= 8% of scale)", passed, worst[0] or "all within limit")


def check_cross_model_gap(trials: list[TrialEvals], dims: list[str]) -> CheckResult:
    worst = ("", 0.0, 0.0)
    for trial in trials:
        models = list(trial.by_model)
        for m1, m2 in combinations(models, 2):
            for dim in dims:
                limit = GAP_LIMIT_FRACTION * _dim_max(trials, dim)
                gap = abs(
                    statistics.fmean(_dim_scores(trial.by_model[m1], dim))
                    - statistics.fmean(_dim_scores(trial.by_model[m2], dim))
                )
                if gap - limit > worst[1] - worst[2]:
                    worst = (f"{trial.suffix}/{dim} {m1} vs {m2} gap={gap:.2f} (limit {limit:.2f})", gap, limit)
    passed = worst[1] <= worst[2]
    return CheckResult("2. judge-model agreement (gap <= 12% of scale)", passed, worst[0] or "all within limit")


def check_human_agreement(trials: list[TrialEvals]) -> list[CheckResult]:
    results = []
    models = sorted({m for t in trials for m in t.by_model})
    for model in models:
        scored = [t for t in trials if model in t.by_model]
        totals = [_normalized_mean(t, model) for t in scored]
        reference = [BUCKET_RANK[REFERENCE_BUCKETS[t.suffix]] for t in scored]
        rho = _spearman(totals, reference)
        by_bucket: dict[str, list[float]] = {}
        for t, score in zip(scored, totals, strict=True):
            by_bucket.setdefault(REFERENCE_BUCKETS[t.suffix], []).append(score)
        separation_ok = all(
            min(by_bucket.get(hi, [1.0])) > max(by_bucket.get(lo, [0.0]))
            for hi, lo in [("A", "B"), ("B", "C"), ("C", "D")]
            if hi in by_bucket and lo in by_bucket
        )
        passed = rho >= SPEARMAN_MIN and separation_ok
        results.append(
            CheckResult(
                f"3. human agreement [{model}]",
                passed,
                f"spearman={rho:.3f} (min {SPEARMAN_MIN}), bucket separation={'OK' if separation_ok else 'VIOLATED'}",
            )
        )
    return results


def check_disjointness(trials: list[TrialEvals], dims: list[str]) -> list[CheckResult]:
    results = []
    models = sorted({m for t in trials for m in t.by_model})
    for model in models:
        scored = [t for t in trials if model in t.by_model]
        vectors = {dim: [statistics.fmean(_dim_scores(t.by_model[model], dim)) for t in scored] for dim in dims}
        worst = ("", 0.0)
        for d1, d2 in combinations(dims, 2):
            r = abs(_pearson(vectors[d1], vectors[d2]))
            if r > worst[1]:
                worst = (f"{d1}~{d2} |r|={r:.3f}", r)
        passed = worst[1] <= DISJOINTNESS_MAX_ABS_R
        results.append(
            CheckResult(f"4. dimension disjointness [{model}]", passed, f"{worst[0]} (max {DISJOINTNESS_MAX_ABS_R})")
        )
    return results


def check_regressions(trials: list[TrialEvals]) -> list[CheckResult]:
    by_suffix = {t.suffix: t for t in trials}
    results: list[CheckResult] = []

    def add(name: str, passed: bool, detail: str) -> None:
        results.append(CheckResult(f"5. regression: {name}", passed, detail))

    for model in sorted({m for t in trials for m in t.by_model}):
        fj = by_suffix.get("FjYQ3XQ")
        if fj and model in fj.by_model:
            scores = _dim_scores(fj.by_model[model], "model_fit")
            mean, std = statistics.fmean(scores), _std(scores)
            add(f"#21 model_fit >= 38 & std <= 4 [{model}]", mean >= 38 and std <= 4, f"mean={mean:.1f} std={std:.2f}")

        zv = by_suffix.get("ZvSsnyg")
        if zv and model in zv.by_model:
            ranked = sorted(
                (t for t in trials if model in t.by_model), key=lambda t: _normalized_mean(t, model), reverse=True
            )
            not_first = ranked[0].suffix != "ZvSsnyg"
            mf = statistics.fmean(_dim_scores(zv.by_model[model], "model_fit"))
            add(
                f"#13 dethroned & model_fit <= 36 [{model}]",
                not_first and mf <= 36,
                f"rank1={ranked[0].suffix} model_fit={mf:.1f}",
            )

        for suffix, pr in (("4njch2w", 18), ("URtZnzf", 20)):
            trial = by_suffix.get(suffix)
            if trial and model in trial.by_model:
                norm = _normalized_mean(trial, model)
                restraint = statistics.fmean(_dim_scores(trial.by_model[model], "restraint"))
                add(
                    f"#{pr} capped & restraint floored [{model}]",
                    norm <= 0.45 and restraint <= 8,
                    f"normalized={norm:.2f} restraint={restraint:.1f}",
                )

        # Anti-gaming guard: high test_quality demands manual confirmation of a
        # composition test through OfferModifiers.ChooseFor — reported as WARN,
        # since test presence is not mechanically decidable here.
        for trial in trials:
            if model in trial.by_model:
                tq = statistics.fmean(_dim_scores(trial.by_model[model], "test_quality"))
                if tq >= 18:
                    add(
                        f"WARN {trial.suffix} test_quality={tq:.1f} [{model}]",
                        True,
                        "verify composition test exists before trusting this score",
                    )

    aG = by_suffix.get("aGTFmDh")
    if aG and len(aG.by_model) >= 2:
        means = [statistics.fmean(_dim_scores(evals, "model_fit")) for evals in aG.by_model.values()]
        gap = max(means) - min(means)
        add("#16 model_fit cross-model gap <= 6", gap <= 6, f"gap={gap:.1f}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path, help="Job dir containing the 13 reference trial dirs (symlinks OK).")
    parser.add_argument("--project-dir", "-C", type=Path, default=Path("."), help="Evaluation project dir.")
    args = parser.parse_args()

    dimensions_path = args.project_dir / "tasks" / "ddd-weather-discount" / "assessment_dimensions.json"
    fingerprint = _dimensions_fingerprint(dimensions_path)
    if not fingerprint:
        print(f"ERROR: no dimensions file at {dimensions_path}")
        return 1

    trials = collect(args.job_dir, fingerprint)
    evaluated = [t for t in trials if t.by_model]
    if len(evaluated) < len(REFERENCE_BUCKETS):
        missing = sorted(set(REFERENCE_BUCKETS) - {t.suffix for t in evaluated})
        print(f"WARNING: {len(evaluated)}/{len(REFERENCE_BUCKETS)} reference trials have v2 evals; missing: {missing}")
    trials = evaluated
    if not trials:
        print("ERROR: no v2 evaluations found — run `nasde eval` first.")
        return 1

    dims = _dimension_names(trials)
    checks: list[CheckResult] = [
        check_repeatability(trials, dims),
        check_cross_model_gap(trials, dims),
        *check_human_agreement(trials),
        *check_disjointness(trials, dims),
        *check_regressions(trials),
    ]

    width = max(len(c.criterion) for c in checks)
    failures = 0
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        if not c.passed:
            failures += 1
        print(f"[{status}] {c.criterion.ljust(width)}  {c.detail}")
    if failures == 0:
        print("\nACCEPTED: rubric v2 meets all stop conditions")
    else:
        print(f"\nREJECTED: {failures} criteria failed - diagnose, patch the specific check wording, re-run")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
