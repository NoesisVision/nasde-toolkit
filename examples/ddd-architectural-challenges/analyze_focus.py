#!/usr/bin/env python3
"""
analyze_focus.py — aggregates results from the tactical-ddd focus benchmark
into a single Markdown report (_focus_report.md).

Scans `jobs/` for job dirs whose name contains "focus-vanilla" or "focus-skill",
groups by variant + task, computes:
  - pass-rate (Harbor reward 0/1)
  - normalized score (LLM-as-judge)
  - tokens, duration, dollar cost
  - per-dimension breakdown (vanilla vs skill, per task)

Usage:  python3 analyze_focus.py  (run from the benchmark project root)
"""
from __future__ import annotations
import glob, json, statistics, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

JOBS_GLOB = "jobs/*focus*"
TASKS = ["ddd-threshold-discount", "ddd-weather-discount"]
VARIANTS = {"focus-vanilla": "claude-vanilla", "focus-skill": "claude-ntcoding-tactical-ddd"}

# Pricing per 1M tokens (USD). Cache-read = 10% of input.
PRICING = {"claude-sonnet-4-6": dict(inp=3.0, out=15.0, cache=0.30)}


def iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", ""))


def cost(model: str, n_in: int, n_cache: int, n_out: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    uncached = max(0, (n_in or 0) - (n_cache or 0))
    return (uncached * p["inp"] + (n_cache or 0) * p["cache"] + (n_out or 0) * p["out"]) / 1_000_000


def fmt_dur(s: float) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m}m{sec:02d}s" if m else f"{sec}s"


def collect_trials():
    rows = []
    for job_dir in sorted(glob.glob(JOBS_GLOB)):
        name = Path(job_dir).name
        variant = next((v for tag, v in VARIANTS.items() if tag in name), None)
        if not variant:
            continue
        for rj in glob.glob(f"{job_dir}/*/result.json"):
            try:
                r = json.load(open(rj))
            except Exception:
                continue
            ar = r.get("agent_result") or {}
            if ar.get("n_input_tokens") is None:
                continue
            vr = (r.get("verifier_result") or {}).get("rewards", {}) or {}
            ae = r.get("agent_execution") or {}
            model = (r["config"]["agent"] or {}).get("model_name")
            dur = (iso(ae["finished_at"]) - iso(ae["started_at"])).total_seconds() if ae.get("started_at") else 0
            row = dict(
                variant=variant, task=r["task_name"], model=model,
                in_t=ar["n_input_tokens"], cache=ar.get("n_cache_tokens") or 0,
                out_t=ar["n_output_tokens"], reward=vr.get("reward"), dur=dur,
                cost=cost(model, ar["n_input_tokens"], ar.get("n_cache_tokens"), ar["n_output_tokens"]),
                norm=None, dims={},
            )
            ev_path = rj.replace("result.json", "assessment_eval.json")
            try:
                ev = json.load(open(ev_path))
                row["norm"] = ev.get("normalized_score")
                for d in ev.get("dimensions", []):
                    row["dims"][d["name"]] = (d.get("score"), d.get("max_score"))
            except Exception:
                pass
            rows.append(row)
    return rows


def mean_safe(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def aggregate_table(rows) -> str:
    lines = ["## Aggregate (all tasks)\n",
             "| variant | trials | pass-rate | norm-score | avg in tok | avg out tok | avg duration | $/trial |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for variant in sorted({r["variant"] for r in rows}):
        vrows = [r for r in rows if r["variant"] == variant]
        n = len(vrows)
        pr = mean_safe([r["reward"] for r in vrows])
        ns = mean_safe([r["norm"] for r in vrows])
        ai = mean_safe([r["in_t"] for r in vrows])
        ao = mean_safe([r["out_t"] for r in vrows])
        ad = mean_safe([r["dur"] for r in vrows])
        ac = mean_safe([r["cost"] for r in vrows])
        lines.append(
            f"| {variant} | {n} | {pr:.0%} | {ns:.2f} | "
            f"{ai:,.0f} | {ao:,.0f} | {fmt_dur(ad)} | ${ac:.2f} |"
        )
    return "\n".join(lines) + "\n"


def per_task_table(rows) -> str:
    out = ["\n## Per-task breakdown\n"]
    for task in TASKS:
        trows = [r for r in rows if r["task"] == task]
        if not trows:
            continue
        out.append(f"\n### `{task}`\n")
        out.append("| variant | trials | pass | norm | avg in tok | avg out tok | avg dur | $/trial |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for variant in sorted({r["variant"] for r in trows}):
            vrows = [r for r in trows if r["variant"] == variant]
            n = len(vrows)
            pr = mean_safe([r["reward"] for r in vrows])
            ns = mean_safe([r["norm"] for r in vrows])
            ai = mean_safe([r["in_t"] for r in vrows])
            ao = mean_safe([r["out_t"] for r in vrows])
            ad = mean_safe([r["dur"] for r in vrows])
            ac = mean_safe([r["cost"] for r in vrows])
            out.append(
                f"| {variant} | {n} | {pr:.0%} | {ns:.2f} | "
                f"{ai:,.0f} | {ao:,.0f} | {fmt_dur(ad)} | ${ac:.2f} |"
            )
    return "\n".join(out) + "\n"


def dimension_table(rows) -> str:
    out = ["\n## Dimension breakdown (LLM-as-judge, mean per dimension)\n"]
    for task in TASKS:
        trows = [r for r in rows if r["task"] == task and r["dims"]]
        if not trows:
            continue
        out.append(f"\n### `{task}`\n")
        out.append("| dimension | vanilla | skill | Δ |")
        out.append("|---|---:|---:|---:|")
        all_dims = sorted({d for r in trows for d in r["dims"]})
        for dim in all_dims:
            vanilla_rows = [r for r in trows if r["variant"] == "claude-vanilla" and dim in r["dims"]]
            skill_rows = [r for r in trows if r["variant"] == "claude-ntcoding-tactical-ddd" and dim in r["dims"]]
            if not vanilla_rows or not skill_rows:
                continue
            max_score = vanilla_rows[0]["dims"][dim][1] or skill_rows[0]["dims"][dim][1]
            mv = mean_safe([r["dims"][dim][0] for r in vanilla_rows])
            ms = mean_safe([r["dims"][dim][0] for r in skill_rows])
            if mv is None or ms is None:
                continue
            nv, ns = mv / max_score, ms / max_score
            delta = ns - nv
            arrow = "▲" if delta > 0.02 else ("▼" if delta < -0.02 else "≈")
            out.append(
                f"| {dim} | {mv:.1f}/{max_score} ({nv:.0%}) | {ms:.1f}/{max_score} ({ns:.0%}) | {arrow} {delta:+.2f} |"
            )
    return "\n".join(out) + "\n"


def main() -> None:
    rows = collect_trials()
    if not rows:
        print("No focus trials found under jobs/. Run `nasde run ...` first.", file=sys.stderr)
        sys.exit(1)
    report = "# Tactical-DDD focus benchmark report\n\n"
    report += f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n\n"
    report += f"Total trials: **{len(rows)}** across {len({r['task'] for r in rows})} tasks "
    report += f"and {len({r['variant'] for r in rows})} variants.\n\n"
    report += aggregate_table(rows)
    report += per_task_table(rows)
    report += dimension_table(rows)
    Path("_focus_report.md").write_text(report)
    print("Wrote _focus_report.md")


if __name__ == "__main__":
    main()
