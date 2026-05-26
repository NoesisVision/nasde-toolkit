#!/usr/bin/env python3
"""Generate blog charts for the tactical-ddd post from the FINAL experiment numbers.

Data hard-coded here = the n=3x3 medians from EXPERIMENT_STATUS.md / EXPERIMENT_LOG.md
(source of truth in nasde-toolkit). Self-contained so the asset is stable.

All on-chart text is ENGLISH (these go straight into the post). Titles are short so
they don't collide with the legend; explanatory captions belong in the post body,
not on the image.

Run:  uv run --with matplotlib python make_charts.py
Outputs: radar_weather.png, radar_movie.png, loop_before_after.png, contrast_weather_movie.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# --- FINAL DATA (n=3 attempts x 3 evals, medians, normalized 0-1) ---
# 5 axes (full pentagon). Test quality INCLUDED on purpose: on movie it collapses to
# the centre for EVERY variant -> visually shows the skill does not touch that axis.
DIMS = ["Domain\nmodeling", "Encapsulation", "Architecture", "Extensibility", "Test\nquality"]
WEATHER = {
    "vanilla":      [0.80, 0.72, 0.81, 0.73, 0.78],
    "guided":       [0.85, 0.80, 0.83, 0.74, 0.80],
    "public skill": [0.94, 0.85, 0.82, 0.84, 0.74],
    "repo-tuned":   [0.99, 0.94, 0.89, 0.84, 0.88],
}
MOVIE = {
    "vanilla":      [0.64, 0.67, 0.74, 0.67, 0.12],
    "guided":       [0.63, 0.68, 0.81, 0.70, 0.08],
    "public skill": [0.66, 0.62, 0.75, 0.69, 0.15],
    "repo-tuned":   [0.66, 0.71, 0.86, 0.72, 0.09],
}
OVERALL = {
    "vanilla":      {"weather": 0.79, "movie": 0.56},
    "guided":       {"weather": 0.84, "movie": 0.58},
    "public skill": {"weather": 0.85, "movie": 0.60},
    "repo-tuned":   {"weather": 0.92, "movie": 0.62},
}
COLORS = {"vanilla": "#9aa0a6", "guided": "#f4b400", "public skill": "#4285f4", "repo-tuned": "#0f9d58"}

# --- OPERATIONAL metrics: AVERAGED over all 3 agent runs/variant. Cost OMITTED. ---
# (time_s, total_tokens_k) = mean agent wall-clock seconds, mean total (input+output) tokens.
OPS = {
    "weather": {
        #              time_s  total_k
        "vanilla":      (798,  1999),
        "guided":       (576,  5605),
        "public skill": (934,  4210),
        "repo-tuned":   (951,  3399),
    },
    "movie": {
        "vanilla":      (762,  1368),
        "guided":       (588,  1411),
        "public skill": (1323,  918),
        "repo-tuned":   (1312, 1553),
    },
}
VARIANTS = ["vanilla", "guided", "public skill", "repo-tuned"]


def radar(data, title, fname):
    N = len(DIMS)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7, 7.6), subplot_kw=dict(polar=True))
    for name, vals in data.items():
        v = vals + vals[:1]
        ax.plot(angles, v, color=COLORS[name], linewidth=2.2, label=name)
        ax.fill(angles, v, color=COLORS[name], alpha=0.08)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIMS, fontsize=11)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8, color="#999")
    ax.set_rlabel_position(90)  # radial labels along a clear spoke, away from data
    # short title ABOVE the plot, centered; legend BELOW -> no collision
    ax.set_title(title, fontsize=14, pad=30, fontweight="bold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=4,
              fontsize=10, frameon=False, columnspacing=1.4, handletextpad=0.5)
    ax.grid(color="#ddd")
    fig.subplots_adjust(top=0.84, bottom=0.12)
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def loop_before_after(fname):
    dims = ["Overall", "Architecture"]
    before = [0.50, 0.63]
    after = [0.62, 0.86]
    x = np.arange(len(dims))
    w = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - w / 2, before, w, label="before skill fix", color="#db4437")
    ax.bar(x + w / 2, after, w, label="after fix (one skill edit)", color="#0f9d58")
    for i, (b, a) in enumerate(zip(before, after)):
        ax.text(i - w / 2, b + 0.01, f"{b:.2f}", ha="center", fontsize=9)
        ax.text(i + w / 2, a + 0.01, f"{a:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(dims, fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("normalized score 0-1")
    ax.set_title("Measure -> diagnose -> fix loop (repo-tuned, movie)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def contrast(fname):
    variants = ["vanilla", "guided", "public skill", "repo-tuned"]
    weather = [OVERALL[v]["weather"] for v in variants]
    movie = [OVERALL[v]["movie"] for v in variants]
    x = np.arange(len(variants))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w / 2, weather, w, label="WEATHER (feature, clean DDD)", color="#4285f4")
    ax.bar(x + w / 2, movie, w, label="MOVIE (legacy refactor)", color="#db4437")
    for i, (we, mo) in enumerate(zip(weather, movie)):
        ax.text(i - w / 2, we + 0.01, f"{we:.2f}", ha="center", fontsize=8)
        ax.text(i + w / 2, mo + 0.01, f"{mo:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(variants, fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("median, normalized 0-1")
    ax.set_title("Same skill, two tasks: tuning wins on weather, ties on movie",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def ops_tokens(task, fname):
    """Vertical bars: total tokens (input+output) per variant (k). Portrait.
    One bar per variant, colored to match the radar/time charts."""
    d = OPS[task]
    total = [d[v][1] for v in VARIANTS]
    x = np.arange(len(VARIANTS))
    fig, ax = plt.subplots(figsize=(6, 7.2))  # portrait
    bars = ax.bar(x, total, 0.6, color=[COLORS[v] for v in VARIANTS])
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(total) * 0.01,
                f"{int(b.get_height())}k", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(VARIANTS, fontsize=11, rotation=15)
    ax.set_ylabel("average total tokens (thousands)")
    ax.set_title(f"{task.capitalize()} task - average token usage", fontsize=14, fontweight="bold", pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def ops_time(task, fname):
    """Vertical bars: agent wall-clock time per variant (s). Portrait."""
    d = OPS[task]
    secs = [d[v][0] for v in VARIANTS]
    x = np.arange(len(VARIANTS))
    fig, ax = plt.subplots(figsize=(6, 7.2))  # portrait
    bars = ax.bar(x, secs, 0.6, color=[COLORS[v] for v in VARIANTS])
    for b in bars:
        m = int(b.get_height())
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(secs) * 0.01,
                f"{m // 60}m{m % 60:02d}s", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(VARIANTS, fontsize=11, rotation=15)
    ax.set_ylabel("average agent run time (seconds)")
    ax.set_title(f"{task.capitalize()} task - average run time", fontsize=14, fontweight="bold", pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


if __name__ == "__main__":
    radar(WEATHER, "Weather task - quality by dimension", "radar_weather.png")
    radar(MOVIE, "Movie task - quality by dimension", "radar_movie.png")
    loop_before_after("loop_before_after.png")
    contrast("contrast_weather_movie.png")
    ops_tokens("weather", "ops_tokens_weather.png")
    ops_tokens("movie", "ops_tokens_movie.png")
    ops_time("weather", "ops_time_weather.png")
    ops_time("movie", "ops_time_movie.png")
    print("Note: '* test quality' axis kept on purpose; on movie it sits near zero for all "
          "variants (skill does not teach testing). Put the explanatory sentence in the post caption.")
    print("Cost intentionally OMITTED from charts (not estimated).")
