"""Cost x quality plane for the 24-trial Fable/Opus grid (PL + EN publication PNGs).

X = cache-aware run cost (ADR-014): fresh input at the full rate, cache writes at
the 1h-cache write rate, cache reads at the cached rate, output at the output rate
— what the API would bill for the run. Rates are read live from
src/nasde_toolkit/pricing.toml so a rate update reprices the chart on next render.
Y = trial quality: mean of the 4 rubric-v2.3 evaluations (2x Fable + 2x Opus judge).
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs"
PRICING = HERE.parents[1] / "src" / "nasde_toolkit" / "pricing.toml"
FP = "37ffc5f460d2"

ARMS: dict[tuple[str, str], list[str]] = {
    ("Fable 5", "vanilla"): ["ayg7ckA", "Ss2F6dR", "CKEcWHg", "8ks7yf5"],
    ("Fable 5", "hint"): ["7sJ9JK3", "b5jkaWo", "PuuJKHt", "E2soRnZ"],
    ("Fable 5", "skill"): ["MNP2RGe", "qpCRH3A", "NZmadqg", "h3a65Ke"],
    ("Opus 4.8", "vanilla"): ["GoWvUz6", "cyQyXFc", "JTgey8p", "Lozfurr"],
    ("Opus 4.8", "hint"): ["YgcbZjf", "VoktgLb", "sSUYQp4", "a6okSgZ"],
    ("Opus 4.8", "skill"): ["ZMX6Xbq", "TsjcHWY", "Bkwiqom", "F5vYATs"],
}
MODEL_ID = {"Fable 5": "claude-fable-5", "Opus 4.8": "claude-opus-4-8"}
CODER_COLOR = {"Fable 5": "#2a78d6", "Opus 4.8": "#1baf7a"}
CONFIG_MARKER = {"vanilla": "o", "hint": "^", "skill": "s"}
INK = "#1a1a19"

TEXT = {
    "pl": {
        "title": "Koszt runu a jakość modelu domenowego — ddd-weather-discount, 24 runy kodujące",
        "xlabel": "koszt runu w USD — stawki API z rozliczeniem prompt cache",
        "ylabel": "jakość (średnia 4 ewaluacji, rubryka v2.3)",
        "coder": "model kodujący",
        "mean": "duży znacznik = średnia ramienia (n=4)",
        "outlier": "pojedynczy run za ${cost:.0f}",
        # \$ keeps matplotlib from treating $...$ pairs as mathtext
        "footnote": (
            "koszt = świeże wejście × stawka + zapisy cache × stawka zapisu (2×) "
            "+ odczyty cache × stawka odczytu (0.1×) + wyjście × stawka wyjścia\n"
            "stawki API z {as_of}: Fable 5 \\${fi:.0f} / \\${fo:.0f}, "
            "Opus 4.8 \\${oi:.0f} / \\${oo:.0f} za mln tokenów"
        ),
        "out": "cost_quality_plane.png",
    },
    "en": {
        "title": "Run cost vs domain-model quality — ddd-weather-discount, 24 coding runs",
        "xlabel": "run cost in USD — API rates with prompt caching",
        "ylabel": "quality (mean of 4 evaluations, rubric v2.3)",
        "coder": "coding model",
        "mean": "large marker = arm mean (n=4)",
        "outlier": "a single ${cost:.0f} run",
        "footnote": (
            "cost = fresh input × input rate + cache writes × write rate (2×) "
            "+ cache reads × read rate (0.1×) + output × output rate\n"
            "API rates as of {as_of}: Fable 5 \\${fi:.0f} / \\${fo:.0f}, "
            "Opus 4.8 \\${oi:.0f} / \\${oo:.0f} per MTok"
        ),
        "out": "cost_quality_plane_en.png",
    },
}

# offset-points placement of each arm-mean label, tuned against the rendered layout
LABEL_OFFSET = {
    ("Fable 5", "vanilla"): (14, -4, "left"),
    ("Fable 5", "hint"): (-14, 2, "right"),
    ("Fable 5", "skill"): (0, 12, "center"),
    ("Opus 4.8", "vanilla"): (-14, -4, "right"),
    ("Opus 4.8", "hint"): (14, -4, "left"),
    ("Opus 4.8", "skill"): (14, -4, "left"),
}


def load_rates() -> dict:
    raw = tomllib.loads(PRICING.read_text())["models"]
    return {
        "fi": raw["claude-fable-5"]["input_per_1m"],
        "fo": raw["claude-fable-5"]["output_per_1m"],
        "oi": raw["claude-opus-4-8"]["input_per_1m"],
        "oo": raw["claude-opus-4-8"]["output_per_1m"],
        "as_of": raw["claude-fable-5"]["as_of"],
        "by_model": {
            m: (
                raw[m]["input_per_1m"],
                raw[m]["output_per_1m"],
                raw[m]["cached_input_per_1m"],
                raw[m]["cache_write_per_1m"],
            )
            for m in ("claude-fable-5", "claude-opus-4-8")
        },
    }


def collect(rates: dict) -> list[dict]:
    rows = []
    for (coder, config), trials in ARMS.items():
        for trial in trials:
            (trial_dir,) = JOBS.glob(f"*/ddd-weather-discount__{trial}")
            fm = json.loads((trial_dir / "agent" / "trajectory.json").read_text()).get("final_metrics") or {}
            extra = fm.get("extra") or {}
            inp = fm["total_prompt_tokens"]
            out = (fm.get("total_completion_tokens") or 0) + (extra.get("reasoning_output_tokens") or 0)
            reads = extra.get("total_cache_read_input_tokens") or fm.get("total_cached_tokens") or 0
            writes = extra.get("total_cache_creation_input_tokens") or 0
            in_rate, out_rate, read_rate, write_rate = rates["by_model"][MODEL_ID[coder]]
            scores = []
            for f in sorted(trial_dir.glob("assessment_eval_*.json")):
                d = json.loads(f.read_text())
                if d.get("dimensions_fingerprint") == FP and d.get("evaluator_model") in MODEL_ID.values():
                    scores.append(d["normalized_score"])
            if len(scores) != 4:
                print(f"WARN: {trial} has {len(scores)} v2.3 evals (expected 4)")
            rows.append({
                "trial": trial, "coder": coder, "config": config,
                "cost": (
                    (inp - reads - writes) / 1e6 * in_rate
                    + writes / 1e6 * write_rate
                    + reads / 1e6 * read_rate
                    + out / 1e6 * out_rate
                ),
                "q": sum(scores) / len(scores),
            })
    return rows


def plane_plot(rows: list[dict], rates: dict, lang: str) -> None:
    t = TEXT[lang]
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    fig.suptitle(t["title"], fontsize=12.5, color=INK, y=0.975)

    ax.grid(color="#e4e3dc", linewidth=0.8, zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c3c2b7")

    for (coder, config), _trials in ARMS.items():
        sub = [r for r in rows if r["coder"] == coder and r["config"] == config]
        col, mark = CODER_COLOR[coder], CONFIG_MARKER[config]
        for r in sub:
            ax.scatter(r["cost"], r["q"], s=58, marker=mark, color=col, alpha=0.55,
                       edgecolors="white", linewidths=1.1, zorder=3)
        mc = sum(r["cost"] for r in sub) / len(sub)
        mq = sum(r["q"] for r in sub) / len(sub)
        ax.scatter(mc, mq, s=230, marker=mark, color=col, edgecolors=INK,
                   linewidths=1.4, zorder=5)
        dx, dy, ha = LABEL_OFFSET[(coder, config)]
        ax.annotate(config, (mc, mq), textcoords="offset points", xytext=(dx, dy),
                    ha=ha, fontsize=9.5, color=col, fontweight="bold", zorder=6)

    # per-coder trajectory through the arm means, in config order
    for coder in CODER_COLOR:
        pts = []
        for config in ("vanilla", "hint", "skill"):
            sub = [r for r in rows if r["coder"] == coder and r["config"] == config]
            pts.append((sum(r["cost"] for r in sub) / len(sub), sum(r["q"] for r in sub) / len(sub)))
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=CODER_COLOR[coder],
                linewidth=1.1, linestyle=(0, (4, 3)), alpha=0.65, zorder=2)

    top = max(rows, key=lambda r: r["cost"])
    ax.annotate(t["outlier"].format(cost=top["cost"]), (top["cost"], top["q"]),
                textcoords="offset points", xytext=(-13, -3), ha="right",
                fontsize=8.8, color="#666", zorder=6)

    ax.set_xlim(0, 26)
    ax.set_ylim(0.55, 0.92)
    ax.set_xlabel(t["xlabel"], fontsize=10, color="#444")
    ax.set_ylabel(t["ylabel"], fontsize=10, color="#444")
    ax.tick_params(labelsize=9, colors="#444")
    ax.xaxis.set_major_formatter(lambda v, _p: f"${v:.0f}")

    handles = [
        plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                   markerfacecolor=CODER_COLOR[c], markeredgecolor="white",
                   label=f"{t['coder']}: {c}")
        for c in CODER_COLOR
    ]
    handles += [
        plt.Line2D([], [], marker=CONFIG_MARKER[k], linestyle="", markersize=7,
                   markerfacecolor="#9b9a90", markeredgecolor="white", label=k)
        for k in CONFIG_MARKER
    ]
    handles.append(plt.Line2D([], [], marker="o", linestyle="", markersize=11,
                              markerfacecolor="#d8d7cd", markeredgecolor=INK, label=t["mean"]))
    ax.legend(handles=handles, loc="lower right", fontsize=8.6, frameon=False)

    fig.text(0.5, 0.012, t["footnote"].format(**rates), ha="center", fontsize=7.8,
             color="#777", linespacing=1.5)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    out = HERE / "assets" / t["out"]
    fig.savefig(out, dpi=160, facecolor="white")
    print("saved:", out)


if __name__ == "__main__":
    rates = load_rates()
    rows = collect(rates)
    for (coder, config), _ in ARMS.items():
        sub = [r for r in rows if r["coder"] == coder and r["config"] == config]
        mc = sum(r["cost"] for r in sub) / len(sub)
        mq = sum(r["q"] for r in sub) / len(sub)
        print(f"{coder:9s} {config:8s} cost ${mc:6.2f}  quality {mq:.3f}")
    for lang in ("pl", "en"):
        plane_plot(rows, rates, lang)
