"""Grid strip plot v2 (trial shades + pair links) and judge test-retest plot."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

JOBS = Path("/Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/examples/ddd-architectural-challenges/jobs")
FP = "37ffc5f460d2"

ARMS: dict[tuple[str, str], list[str]] = {
    ("Fable 5", "vanilla"): ["ayg7ckA", "Ss2F6dR", "CKEcWHg", "8ks7yf5"],
    ("Fable 5", "hint"): ["7sJ9JK3", "b5jkaWo", "PuuJKHt", "E2soRnZ"],
    ("Fable 5", "skill"): ["MNP2RGe", "qpCRH3A", "NZmadqg", "h3a65Ke"],
    ("Opus 4.8", "vanilla"): ["GoWvUz6", "cyQyXFc", "JTgey8p", "Lozfurr"],
    ("Opus 4.8", "hint"): ["YgcbZjf", "VoktgLb", "sSUYQp4", "a6okSgZ"],
    ("Opus 4.8", "skill"): ["ZMX6Xbq", "TsjcHWY", "Bkwiqom", "F5vYATs"],
}
JUDGES = {"claude-fable-5": "Judge: Fable 5", "claude-opus-4-8": "Judge: Opus 4.8"}
CODER_COLOR = {"Fable 5": "#2a78d6", "Opus 4.8": "#1baf7a"}
INK = "#1a1a19"


def blend_to_white(hex_color: str, factor: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    mix = tuple(round(c + (255 - c) * factor) for c in (r, g, b))
    return "#%02x%02x%02x" % mix


TRIAL_SHADE = [0.0, 0.22, 0.42, 0.58]


def collect() -> dict[tuple[str, str, str], list[list[float]]]:
    out: dict[tuple[str, str, str], list[list[float]]] = {}
    for (coder, config), trials in ARMS.items():
        for trial in trials:
            per_judge: dict[str, list[float]] = {j: [] for j in JUDGES}
            for f in sorted(JOBS.glob(f"*/ddd-weather-discount__{trial}/assessment_eval_*.json")):
                d = json.loads(f.read_text())
                if d.get("dimensions_fingerprint") != FP:
                    continue
                if d.get("evaluator_model") in per_judge:
                    per_judge[d["evaluator_model"]].append(d["normalized_score"])
            for judge, scores in per_judge.items():
                out.setdefault((judge, coder, config), []).append(scores)
    return out


def grid_plot(data: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharey=True)
    fig.suptitle(
        "All v2.3 measurements — shade = trial, connector = the judge's score pair, "
        "larger dot = two identical scores",
        fontsize=11.5, color=INK, y=0.98,
    )
    configs = ["vanilla", "hint", "skill"]
    coders = ["Fable 5", "Opus 4.8"]
    xpos = {("Fable 5", c): i for i, c in enumerate(configs)}
    xpos.update({("Opus 4.8", c): 3.7 + i for i, c in enumerate(configs)})
    trial_off = [-0.21, -0.07, 0.07, 0.21]

    for ax, judge_id in zip(axes, JUDGES):
        ax.set_title(JUDGES[judge_id], fontsize=11, color=INK)
        ax.grid(axis="y", color="#e4e3dc", linewidth=0.8, zorder=0)
        for coder in coders:
            for config in configs:
                x0 = xpos[(coder, config)]
                trials = data.get((judge_id, coder, config), [])
                all_scores = [s for t in trials for s in t]
                for ti, scores in enumerate(trials):
                    x = x0 + trial_off[ti]
                    col = blend_to_white(CODER_COLOR[coder], TRIAL_SHADE[ti])
                    tie = len(scores) == 2 and abs(scores[0] - scores[1]) < 1e-9
                    if len(scores) == 2 and not tie:
                        ax.plot([x, x], scores, color=col, linewidth=2.2, zorder=2, solid_capstyle="round")
                    for s in set(scores) if tie else scores:
                        ax.scatter(
                            x, s, s=150 if tie else 68, zorder=3, color=col,
                            edgecolors="white", linewidths=1.2,
                        )
                if all_scores:
                    mean = sum(all_scores) / len(all_scores)
                    ax.hlines(mean, x0 - 0.3, x0 + 0.3, color=INK, linewidth=1.6, zorder=4)
                    ax.annotate(f"{mean:.3f}", (x0, mean), textcoords="offset points",
                                xytext=(0, 8), ha="center", fontsize=8.5, color=INK,
                                fontweight="bold", zorder=5)
        ax.set_xticks([xpos[(c, k)] for c in coders for k in configs])
        ax.set_xticklabels(configs * 2, fontsize=9.5, color="#444")
        for coder, center in (("Fable 5", 1.0), ("Opus 4.8", 4.7)):
            ax.annotate(coder, (center, -0.115), xycoords=("data", "axes fraction"),
                        ha="center", fontsize=10.5, color=CODER_COLOR[coder], fontweight="bold")
        ax.set_xlim(-0.6, 6.3)
        ax.tick_params(axis="y", labelsize=9, colors="#444")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color("#c3c2b7")
    axes[0].set_ylabel("normalized score (v2.3)", fontsize=10, color="#444")
    axes[0].set_ylim(0.5, 1.0)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    out = Path(__file__).with_name("raw_scores_grid_en.png")
    fig.savefig(out, dpi=160, facecolor="white")
    print("saved:", out)


def retest_plot(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    fig.suptitle("Judge repeatability: score #1 vs score #2 on the same trial", fontsize=11.5, color=INK)
    ax.plot([0.5, 1.0], [0.5, 1.0], color="#c3c2b7", linewidth=1.2, zorder=1)
    stats: dict[str, list[float]] = {j: [] for j in JUDGES}
    ties = {j: 0 for j in JUDGES}
    n_pairs = {j: 0 for j in JUDGES}
    judge_color = {"claude-fable-5": "#2a78d6", "claude-opus-4-8": "#1baf7a"}
    for (judge, _c, _k), trials in data.items():
        for scores in trials:
            if len(scores) != 2:
                continue
            a, b = sorted(scores)
            n_pairs[judge] += 1
            stats[judge].append(abs(a - b))
            if abs(a - b) < 1e-9:
                ties[judge] += 1
            ax.scatter(a, b, s=64, color=judge_color[judge], edgecolors="white",
                       linewidths=1.2, zorder=3, alpha=0.9)
    ax.set_xlabel("lower score of the pair", fontsize=10, color="#444")
    ax.set_ylabel("higher score of the pair", fontsize=10, color="#444")
    ax.set_xlim(0.5, 1.0)
    ax.set_ylim(0.5, 1.0)
    ax.set_aspect("equal")
    ax.grid(color="#efeee8", linewidth=0.8, zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    handles = []
    for judge, label in JUDGES.items():
        mad = sum(stats[judge]) / len(stats[judge])
        handles.append(plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                                  markerfacecolor=judge_color[judge], markeredgecolor="white",
                                  label=f"{label}  (mean |Δ|={mad:.3f}, identical: {ties[judge]}/{n_pairs[judge]})"))
        print(f"{label}: pairs={n_pairs[judge]} mean|d|={mad:.4f} ties={ties[judge]} max|d|={max(stats[judge]):.3f}")
    ax.legend(handles=handles, loc="upper left", fontsize=8.6, frameon=False)
    ax.annotate("a point on the diagonal = the judge scored identically twice",
                (0.98, 0.515), ha="right", fontsize=8.5, color="#777")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = Path(__file__).with_name("judge_retest_en.png")
    fig.savefig(out, dpi=160, facecolor="white")
    print("saved:", out)


if __name__ == "__main__":
    d = collect()
    grid_plot(d)
    retest_plot(d)
