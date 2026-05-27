#!/usr/bin/env python3
"""Generate the tactical-ddd experiment log (Markdown) from nasde job artifacts.

Per attempt (one agent run) reports: trial hash, skill activation, reward,
#evals, normalized mean(σ), per-dimension mean(σ), agent wall-time, tokens, cost.
Attempts group by variant (benchmark/task/variant/skill-state) with pooled means.

Two attempt-identification modes, because the two benchmarks are stored differently:
  - "suffix": one job-suffix == one attempt; evals are assessment_eval_{1,2,3}.json
    in the single trial dir (movie — clean, recent).
  - "hash": one trial hash == one attempt; its eval copies are SCATTERED across the
    original job dir + dddstarter-reeval* folders (weather — archaeological).

Lives next to jobs/ so any agent discovers what jobs/ holds without archaeology.
Run from this directory:
  python3 build_experiment_log.py > EXPERIMENT_LOG.md
Deliberately NOT Opik. Re-run to refresh. Add new attempts to ARMS below.
"""
import json
import glob
import os
import re
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime

DIMS = [("domain_modeling", 25), ("encapsulation", 20),
        ("architecture_compliance", 20), ("extensibility", 15), ("test_quality", 20)]

# (benchmark, task, variant, skill_state, mode, [attempt ids])
#   mode "suffix": ids are job-suffix substrings
#   mode "hash":   ids are trial-dir hashes (after the final __)
ARMS = [
    ("movie-rental", "csharp-movie-rental-anemic", "vanilla", "none", "suffix",
     ["movie-vanilla-smoke", "movie-vanilla-iter2", "movie-vanilla-iter3", "movie-vanilla-n5a"]),
    ("movie-rental", "csharp-movie-rental-anemic", "guided", "none", "suffix",
     ["movie-guided-2", "movie-guided-iter2", "movie-guided-iter3", "movie-guided-n5a"]),
    ("movie-rental", "csharp-movie-rental-anemic", "public-skill", "forced-on", "suffix",
     ["movie-public-1", "movie-public-iter2", "movie-public-iter3", "movie-public-n5a"]),
    ("movie-rental", "csharp-movie-rental-anemic", "repo-tuned (iter1-fix)", "forced-on", "suffix",
     ["movie-tuned-2", "movie-tuned-iter2", "movie-tuned-iter3", "movie-tuned-n5a"]),

    # WEATHER — consolidated to n=5 per variant (2026-05-27 significance run).
    # auto-on counted as forced (inv=1 in both); each entry = one clean attempt.
    ("weather", "ddd-weather-discount", "vanilla (n=5)", "none", "mixed",
     [("hash", "a2G4Zsy"), ("hash", "je53EFf"), ("suffix", "weather-vanilla-iter3"),
      ("suffix", "weather-vanilla-n5b")]),
    ("weather", "ddd-weather-discount", "guided (n=5)", "none", "mixed",
     [("hash", "KgfH97s"), ("hash", "nB8vCiA"), ("hash", "tENrXFW"),
      ("suffix", "weather-guided-n5a")]),
    ("weather", "ddd-weather-discount", "public-skill (n=5)", "forced-on", "mixed",
     [("suffix", "weather-public-forced-1"), ("suffix", "weather-public-forced-2"),
      ("suffix", "weather-public-iter3"), ("suffix", "weather-public-n5a")]),
    ("weather", "ddd-weather-discount", "repo-tuned (n=5)", "forced/auto-on", "mixed",
     [("hash", "z9Dgfep"), ("hash", "Rmq7iby"), ("suffix", "weather-tuned-iter3"),
      ("suffix", "weather-tuned-n5a")]),
]


def attempt_dirs_suffix(jobs_dir, suffix):
    """All trial dirs under a job-suffix (a --attempts N job holds N attempts)."""
    jobs = [d for d in glob.glob(os.path.join(jobs_dir, "*" + suffix + "*")) if os.path.isdir(d) and "reeval" not in d]
    tds = []
    for job in jobs:
        tds += [d for d in glob.glob(os.path.join(job, "*")) if os.path.isdir(d) and glob.glob(os.path.join(d, "assessment_eval*.json"))]
    return tds  # list of attempt dirs (each its own attempt)


def attempt_dirs_hash(jobs_dir, h):
    """All trial dirs matching a hash (original + reeval copies = repeated evals)."""
    tds = [d for d in glob.glob(os.path.join(jobs_dir, "**", "*__" + h), recursive=True) if os.path.isdir(d)]
    orig = [d for d in tds if "reeval" not in d]
    return (orig[0] if orig else (tds[0] if tds else None)), tds


def collect_evals(trial_dirs):
    """Pool every assessment_eval(_N).json across the given dirs."""
    scores, perdim = [], defaultdict(list)
    for td in trial_dirs:
        files = sorted(glob.glob(os.path.join(td, "assessment_eval_[0-9].json")))
        if not files and os.path.exists(os.path.join(td, "assessment_eval.json")):
            files = [os.path.join(td, "assessment_eval.json")]
        for f in files:
            j = json.load(open(f))
            scores.append(j["normalized_score"])
            for d in j["dimensions"]:
                perdim[d["name"]].append(d["score"])
    return scores, perdim


def read_meta(td):
    rj = os.path.join(td, "result.json") if td else None
    if not rj or not os.path.exists(rj):
        return {}
    d = json.load(open(rj))
    ae = d.get("agent_execution") or {}
    dur = None
    if ae.get("started_at") and ae.get("finished_at"):
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        try:
            dur = (datetime.strptime(ae["finished_at"], fmt) - datetime.strptime(ae["started_at"], fmt)).total_seconds()
        except ValueError:
            dur = None
    s = json.dumps(d)
    def grab(k):
        m = re.search(r'"' + k + r'"\s*:\s*([0-9.]+)', s)
        return float(m.group(1)) if m else None
    reward = (d.get("verifier_result") or {}).get("rewards", {}).get("reward")
    return {"dur": dur, "in": grab("n_input_tokens"), "out": grab("n_output_tokens"),
            "cache": grab("n_cache_tokens"), "cost": grab("cost_usd"), "reward": reward}


def skill_inv(td):
    if not td:
        return None
    sess = [s for s in glob.glob(os.path.join(td, "agent", "sessions", "projects", "*", "*.jsonl")) if "subagents" not in s]
    if not sess:
        return None
    return open(sess[0]).read().count('"name":"Skill"')


def f(x, n=2):
    return "—" if x is None else f"{x:.{n}f}"


def main(jobs_dir):
    o = []
    o.append("# Tactical-DDD Experiment Log")
    o.append("")
    o.append("Auto-generated by `build_experiment_log.py` from on-disk nasde job artifacts "
             "(trial dirs, **not** Opik). Re-run to refresh. Wide tables — scroll right for time/tokens/cost.")
    o.append("")
    o.append("**One row = one attempt** (single agent run). `hash` locates the trial dir under `jobs/`. "
             "`inv` = Skill-tool invocations (**0 = skill never activated → row reflects ~vanilla, not the skill**). "
             "`rew` = Harbor functional pass (1/0). `#ev` = independent judge evals on this attempt; "
             "the row's `norm`/per-dim = **mean(σ)** across those evals (within-attempt judge spread). "
             "**POOLED = mean of attempt-means** (each attempt counts once, regardless of how many evals it "
             "got — judge evals are repeated measurements of the same code, not independent samples), and its "
             "σ is the **between-attempt** stdev (the agent's run-to-run spread). This is the number to compare "
             "across variants; significance uses a Welch t-test on these attempt-means, not the flat eval pool.")
    o.append("")
    o.append("_Movie raised to n=5 attempts/variant (2026-05-27). Two tuned-movie attempts were "
             "discarded as environment/API failures (one Docker OOM during agent install under 8× "
             "parallelism; one Anthropic 529-overload retry-storm that hit the 1800s agent timeout) — "
             "neither produced a solution to score, so tuned-movie stands at n=4 healthy attempts._")
    o.append("")

    cur_bench = None
    for bench, task, variant, state, mode, ids in ARMS:
        if bench != cur_bench:
            o.append(f"# {bench.upper()}  (`{task}`)")
            o.append("")
            cur_bench = bench
        o.append(f"## {variant} — _{state}_")
        o.append("")
        head = ("| attempt id | hash | inv | rew | #ev | norm mean(σ) | "
                + " | ".join(f"{n}/{m}" for n, m in DIMS)
                + " | time | in/out/cache (k tok) | $ |")
        o.append(head)
        o.append("|" + "---|" * (6 + len(DIMS) + 3))
        arm_scores, arm_perdim = [], defaultdict(list)
        n_evals_total = 0
        attempts = []  # (display_id, rep_td, ev_dirs) — one per actual attempt
        for raw_id in ids:
            kind, aid = raw_id if mode == "mixed" else (mode, raw_id)
            if kind == "suffix":
                for td in attempt_dirs_suffix(jobs_dir, aid):
                    attempts.append((os.path.basename(td).split("__")[-1], td, [td]))
            else:
                rep_td, ev_dirs = attempt_dirs_hash(jobs_dir, aid)
                attempts.append((aid, rep_td, ev_dirs))
        for aid, rep_td, ev_dirs in attempts:
            disp_hash = aid
            if not ev_dirs:
                o.append(f"| {aid} | — | RUNNING/MISSING |" + " |" * (4 + len(DIMS) + 3))
                continue
            scores, perdim = collect_evals(ev_dirs)
            meta = read_meta(rep_td)
            inv = skill_inv(rep_td)
            arm_scores.append(st.mean(scores))
            for k, v in perdim.items():
                arm_perdim[k].append(st.mean(v))
            n_evals_total += len(scores)
            normc = f"{f(st.mean(scores))}({f(st.pstdev(scores),3)})" if scores else "—"
            dimc = [f"{f(st.mean(perdim[n]),1)}({f(st.pstdev(perdim[n]),1)})" if perdim.get(n) else "—" for n, m in DIMS]
            tok = f"{int(meta['in']/1000)}/{int(meta['out']/1000)}/{int(meta['cache']/1000)}" if meta.get("in") else "—"
            tstr = f"{int(meta['dur']//60)}m{int(meta['dur']%60):02d}s" if meta.get("dur") else "—"
            evflag = f"**{len(scores)}**" if len(scores) >= 3 else f"{len(scores)}⚠️"
            o.append(f"| {aid} | `{disp_hash}` | {inv} | {f(meta.get('reward'),0)} | {evflag} | {normc} | "
                     + " | ".join(dimc) + f" | {tstr} | {tok} | {f(meta.get('cost'))} |")
        if arm_scores:
            sd = st.stdev(arm_scores) if len(arm_scores) > 1 else 0.0
            normc = f"**{f(st.mean(arm_scores))}({f(sd,3)})**"
            dimc = [f"**{f(st.mean(arm_perdim[n]),1)}**" if arm_perdim.get(n) else "—" for n, m in DIMS]
            o.append(f"| **POOLED: {len(arm_scores)} attempts (mean of attempt-means; {n_evals_total} evals)** "
                     f"|  |  |  | **{len(arm_scores)}** | {normc} | "
                     + " | ".join(dimc) + " |  |  |  |")
        o.append("")
    print("\n".join(o))


if __name__ == "__main__":
    default_jobs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
    main(sys.argv[1] if len(sys.argv) > 1 else default_jobs)
