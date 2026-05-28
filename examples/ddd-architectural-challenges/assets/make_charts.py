#!/usr/bin/env python3
"""Generate blog charts for the tactical-ddd post from the FINAL experiment numbers.

Data hard-coded here = means from EXPERIMENT_LOG.md (source of truth in nasde-toolkit):
Weather n=5 attempts, Movie n=3 attempts x 6 evals. Mean of attempt-means. Self-contained.

All on-chart text is ENGLISH (these go straight into the post). Titles are short so
they don't collide with the legend; explanatory captions belong in the post body,
not on the image.

Run:  uv run --with matplotlib python make_charts.py
Outputs: radar_weather.png, radar_movie.png, loop_before_after.png, increment_vs_vanilla.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# --- FINAL DATA (Weather n=5 attempts; means, normalized 0-1) ---
# 5 axes (full pentagon). Test quality INCLUDED on purpose: on movie it collapses to
# the centre for EVERY variant -> visually shows the skill does not touch that axis.
DIMS = ["Domain\nmodeling", "Encapsulation", "Architecture", "Extensibility", "Test\nquality"]
WEATHER = {
    "vanilla":      [0.81, 0.75, 0.81, 0.74, 0.79],
    "guided":       [0.84, 0.79, 0.82, 0.75, 0.80],
    "public skill": [0.95, 0.86, 0.83, 0.84, 0.76],
    "repo-tuned":   [0.99, 0.95, 0.88, 0.83, 0.88],
}
MOVIE = {
    "vanilla":      [0.62, 0.67, 0.74, 0.67, 0.12],
    "guided":       [0.63, 0.67, 0.76, 0.68, 0.09],
    "public skill": [0.62, 0.61, 0.74, 0.66, 0.10],
    "repo-tuned":   [0.66, 0.75, 0.86, 0.72, 0.09],
}
OVERALL = {
    "vanilla":      {"weather": 0.795, "movie": 0.563},
    "guided":       {"weather": 0.80, "movie": 0.565},
    "public skill": {"weather": 0.864, "movie": 0.543},
    "repo-tuned":   {"weather": 0.91, "movie": 0.612},
}
COLORS = {"vanilla": "#9aa0a6", "guided": "#f4b400", "public skill": "#4285f4", "repo-tuned": "#0f9d58"}

# --- OPERATIONAL metrics: AVERAGED over all 3 agent runs/variant. Cost OMITTED. ---
# (time_s, total_tokens_k) = mean agent wall-clock seconds, mean total (input+output) tokens.
OPS = {
    "weather": {
        #              time_s  total_k   (n=5 attempts, failed/incomplete excluded)
        "vanilla":      (776,  2033),
        "guided":       (653,  5470),
        "public skill": (948,  4371),
        "repo-tuned":   (960,  3354),
    },
    "movie": {
        "vanilla":      (738,  1262),
        "guided":       (683,  1375),
        "public skill": (1121,  887),
        "repo-tuned":   (1176, 1589),
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
    """Increment vs vanilla per task. Absolute scores across tasks are NOT comparable
    (task difficulty sets the baseline) — the INCREMENT over vanilla is. Line at 0 =
    vanilla; above = better than the bare model, below = worse."""
    steps = ["vanilla", "guided", "public skill", "repo-tuned"]
    x = np.arange(len(steps))
    w_inc = [OVERALL[v]["weather"] - OVERALL["vanilla"]["weather"] for v in steps]
    m_inc = [OVERALL[v]["movie"] - OVERALL["vanilla"]["movie"] for v in steps]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(0, color="#9aa0a6", linewidth=1.4, linestyle="--", zorder=1)
    ax.text(0.02, 0.004, "vanilla baseline", color="#777", fontsize=9, va="bottom")
    ax.plot(x, w_inc, "-o", color="#4285f4", linewidth=2.6, markersize=8,
            label="Weather (feature, clean DDD)")
    ax.plot(x, m_inc, "-o", color="#db4437", linewidth=2.6, markersize=8,
            label="Movie (legacy refactor)")
    for xi, yi in zip(x, w_inc):
        ax.annotate(f"{yi:+.2f}", (xi, yi), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=9, color="#4285f4")
    for xi, yi in zip(x, m_inc):
        ax.annotate(f"{yi:+.2f}", (xi, yi), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=9, color="#db4437")
    ax.set_xticks(x)
    ax.set_xticklabels(steps, fontsize=11)
    ax.set_ylabel("quality gain over vanilla (normalized points)")
    ax.set_title("How much each step lifts quality OVER the bare model",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_ylim(-0.04, 0.17)
    ax.legend(fontsize=10, frameon=False, loc="upper left")
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


def code_snippet_bootstrap(fname):
    """Render the actual bootstrap code as a syntax-highlighted PNG (Substack has no
    code blocks). The code mirrors the three prose steps 1:1 and really returns
    is_real=True on these illustrative numbers (verified). Uses Pygments' own image
    formatter so monospace spacing is exact (no hand-placed token positions)."""
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import ImageFormatter

    code = '''import numpy as np

# the run-scores we actually have, one per run
A = [0.78, 0.81, 0.84, 0.83, 0.80]
B = [0.89, 0.91, 0.93, 0.90, 0.92]

def one_resample(scores):
    # 1. draw the same count of scores, WITH replacement
    #    (a run can be picked twice, or not at all)
    pick = np.random.choice(scores, len(scores))
    return pick.mean()              # 2. average this pretend run

# 3. do that thousands of times; record each A-vs-B difference
diffs = [one_resample(B) - one_resample(A) for _ in range(20_000)]

# verdict: does the whole spread stay on one side of zero?
lo, hi = np.percentile(diffs, [2.5, 97.5])
is_real = lo > 0 or hi < 0     # here lo=+0.08, hi=+0.12  ->  real
'''
    png = highlight(
        code, PythonLexer(),
        ImageFormatter(style="default", font_size=30, line_numbers=False,
                       line_pad=8, image_pad=26, font_name="Menlo"),
    )
    with open(fname, "wb") as f:
        f.write(png)
    print("saved", fname)


def signal_vs_noise(fname):
    """Two panels building the 'is the gap bigger than the wobble?' intuition.

    Each curve = the spread of a configuration's REPEATED runs (deliberately NOT
    labelled 'normal distribution' — the post argues against leaning on that at small
    n). Left: spreads overlap heavily, the gap drowns in the wobble -> a wash.
    Right: spreads sit apart, the gap clears the wobble -> real. Illustrative shapes,
    no axis numbers, no n, no model name."""
    def bump(ax, centre, color, label, spread=0.06):
        xs = np.linspace(0, 1, 400)
        ys = np.exp(-0.5 * ((xs - centre) / spread) ** 2)
        ax.plot(xs, ys, color=color, linewidth=2.4)
        ax.fill_between(xs, ys, color=color, alpha=0.12)
        ax.axvline(centre, color=color, linewidth=1.2, linestyle=":", ymax=0.92)
        ax.text(centre, 1.07, label, ha="center", va="bottom", fontsize=11,
                color=color, fontweight="bold")

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    BLUE, GREEN = "#4285f4", "#0f9d58"

    # Left — heavy overlap: gap < wobble
    bump(axL, 0.43, BLUE, "config A")
    bump(axL, 0.59, GREEN, "config B")
    axL.annotate("", xy=(0.59, 0.5), xytext=(0.43, 0.5),
                 arrowprops=dict(arrowstyle="<->", color="#5f6671", lw=1.4))
    axL.text(0.51, 0.40, "gap", ha="center", fontsize=10, color="#5f6671")
    axL.set_title("Gap smaller than the noise", fontsize=13, fontweight="bold", pad=22)
    axL.text(0.5, -0.16, "the two could easily swap places  ->  too close to call",
             ha="center", fontsize=10.5, color="#5f6671", transform=axL.transAxes)

    # Right — separated: gap > wobble
    bump(axR, 0.34, BLUE, "config A")
    bump(axR, 0.70, GREEN, "config B")
    axR.annotate("", xy=(0.70, 0.5), xytext=(0.34, 0.5),
                 arrowprops=dict(arrowstyle="<->", color="#5f6671", lw=1.4))
    axR.text(0.52, 0.40, "gap", ha="center", fontsize=10, color="#5f6671")
    axR.set_title("Gap bigger than the noise", fontsize=13, fontweight="bold", pad=22)
    axR.text(0.5, -0.16, "they stay apart however the runs fall  ->  real",
             ha="center", fontsize=10.5, color="#5f6671", transform=axR.transAxes)

    for ax in (axL, axR):
        ax.set_ylim(0, 1.25); ax.set_xlim(0, 1)
        ax.set_xlabel("quality score across repeated runs of one configuration", fontsize=9.5)
        ax.set_yticks([]); ax.set_xticks([])
        ax.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle("When is a difference real? When it's bigger than the noise",
                 fontsize=15, fontweight="bold")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def bootstrap_explainer(fname):
    """Left: the raw run-scores for two configs (dots) with their averages (diamonds).
    Right: the bootstrap spread of their differences, with the zero line. Whole spread
    off zero (green) = real. Illustrative numbers; no run-count or model text on image."""
    rng = np.random.default_rng(7)
    # Illustrative run-scores: a clean "real" case whose difference spread genuinely
    # sits off zero (so the picture matches its 'right of zero' caption).
    A = np.array([0.78, 0.81, 0.84, 0.83, 0.80])   # lower configuration
    B = np.array([0.89, 0.91, 0.93, 0.90, 0.92])   # higher configuration
    BLUE, GREEN, DARK = "#4285f4", "#0f9d58", "#202945"

    boot = np.array([rng.choice(B, len(B)).mean() - rng.choice(A, len(A)).mean()
                     for _ in range(20000)])

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4),
                                   gridspec_kw={"width_ratios": [1, 1.4]})

    # Left: raw runs as dots, average as a diamond just below each row
    for vals, color, y, name in [(A, BLUE, 1.0, "config A"), (B, GREEN, 0.0, "config B")]:
        jit = np.linspace(-0.10, 0.10, len(vals))  # spread evenly, no overlap
        axL.scatter(vals, np.full_like(vals, y) + jit, s=70, color=color,
                    alpha=0.85, edgecolor="white", linewidth=0.8, zorder=2)
        axL.scatter([vals.mean()], [y - 0.30], s=150, marker="D", color=color,
                    edgecolor="white", linewidth=1.2, zorder=3)
        axL.text(vals.mean(), y - 0.52, "average", ha="center", fontsize=8.5, color=color)
        axL.text(0.755, y, name, ha="left", va="center", fontsize=11.5,
                 color=color, fontweight="bold")
    axL.set_ylim(-0.85, 1.4); axL.set_xlim(0.75, 0.97)
    axL.set_yticks([])
    axL.set_xlabel("the run-scores we actually have\n(dots = runs, diamond = their average)", fontsize=9.5)
    axL.set_title("Start: the runs we have", fontsize=13, fontweight="bold")
    axL.spines[["top", "right", "left"]].set_visible(False)

    # Right: bootstrap spread of B - A differences
    counts, _, _ = axR.hist(boot, bins=55, color=GREEN, alpha=0.55, edgecolor="none")
    top = counts.max()
    axR.axvline(0, color=DARK, linewidth=1.6, zorder=3)
    axR.text(-0.004, top * 0.5, "zero = no difference", color=DARK, fontsize=9.5,
             ha="right", va="center", rotation=90)
    axR.set_title("Thousands of simulated differences (B minus A)", fontsize=13, fontweight="bold")
    axR.set_xlabel("difference between the two configurations", fontsize=10)
    axR.set_yticks([])
    axR.set_xlim(-0.03, 0.16)
    axR.set_ylim(0, top * 1.25)
    axR.annotate("the whole spread sits right of zero,\nso the difference is real",
                 xy=(np.percentile(boot, 1), top * 0.30),
                 xytext=(0.052, top * 1.12),
                 fontsize=10.5, color=GREEN, fontweight="bold", ha="left",
                 arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.4))
    axR.spines[["top", "right", "left"]].set_visible(False)

    fig.suptitle("Bootstrapping: simulate the repeats we can't afford to run",
                 fontsize=15, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def ops_combo(task, fname):
    """One image per task = tokens (left) + run time (right), side by side.

    Replaces the four separate ops_* charts: each task section in the post carries
    a single operational figure instead of two. Bars colored per variant to match
    the radar. Tokens in thousands; time shown as m:ss on the bar label."""
    d = OPS[task]
    tokens = [d[v][1] for v in VARIANTS]
    secs = [d[v][0] for v in VARIANTS]
    x = np.arange(len(VARIANTS))
    fig, (axt, axs) = plt.subplots(1, 2, figsize=(11, 5.2))

    bt = axt.bar(x, tokens, 0.62, color=[COLORS[v] for v in VARIANTS])
    for b in bt:
        axt.text(b.get_x() + b.get_width() / 2, b.get_height() + max(tokens) * 0.01,
                 f"{int(b.get_height())}k", ha="center", va="bottom", fontsize=10)
    axt.set_xticks(x); axt.set_xticklabels(VARIANTS, fontsize=10.5, rotation=15)
    axt.set_ylabel("average total tokens (thousands)")
    axt.set_title("Tokens", fontsize=13, fontweight="bold")
    axt.set_ylim(0, max(tokens) * 1.15)
    axt.spines[["top", "right"]].set_visible(False)

    bs = axs.bar(x, secs, 0.62, color=[COLORS[v] for v in VARIANTS])
    for b in bs:
        m = int(b.get_height())
        axs.text(b.get_x() + b.get_width() / 2, b.get_height() + max(secs) * 0.01,
                 f"{m // 60}m{m % 60:02d}s", ha="center", va="bottom", fontsize=10)
    axs.set_xticks(x); axs.set_xticklabels(VARIANTS, fontsize=10.5, rotation=15)
    axs.set_ylabel("average agent run time (seconds)")
    axs.set_title("Run time", fontsize=13, fontweight="bold")
    axs.set_ylim(0, max(secs) * 1.15)
    axs.spines[["top", "right"]].set_visible(False)

    fig.suptitle(f"{task.capitalize()} task - cost of the run", fontsize=15, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


# --- BOOTSTRAP significance: Δ (gain) + 95% percentile CI per comparison. ---
# CIs computed from the per-attempt means (source of truth: EXPERIMENT_LOG.md), 20k
# resamples. Hard-coded here so the chart is self-contained and matches the post tables.
# A comparison stands out from the noise iff its CI excludes zero.
CI_ROWS = [
    # (label, delta, ci_low, ci_high)
    ("Weather: bare model -> public skill",   0.069,  0.018, 0.120),
    ("Weather: bare model -> repo-tuned",     0.115,  0.073, 0.161),
    ("Weather: guidelines -> repo-tuned",     0.111,  0.059, 0.167),
    ("Weather: public skill -> repo-tuned",   0.046,  0.003, 0.091),
    ("Weather: bare model -> guidelines",     0.005, -0.040, 0.049),
    ("Movie: bare model -> repo-tuned",       0.049,  0.034, 0.067),
    ("Movie: public skill -> repo-tuned",     0.070,  0.028, 0.106),
    ("Movie: guidelines -> repo-tuned",       0.047,  0.035, 0.062),
    ("Movie: bare model -> public skill",    -0.020, -0.056, 0.021),
    ("Movie: bare model -> guidelines",       0.002, -0.030, 0.034),
]


def significance_forest(fname):
    """Forest plot: each comparison's quality gain with its 95% bootstrap interval.

    The vertical line at zero is the whole point. A bar whose interval clears zero is
    a real difference; one that straddles zero is noise. Green = clears zero,
    grey = straddles it. This replaces the old formula/sigma-table images entirely."""
    rows = list(reversed(CI_ROWS))  # first row at top
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    ax.axvline(0, color="#202945", linewidth=1.4, zorder=1)
    ax.text(0.004, -0.85, "no difference", color="#202945", fontsize=9,
            ha="left", va="center")
    for yi, (label, d, lo, hi) in zip(y, rows):
        clears = lo > 0 or hi < 0
        c = "#0f9d58" if clears else "#9aa0a6"
        ax.plot([lo, hi], [yi, yi], color=c, linewidth=2.6, solid_capstyle="round", zorder=2)
        ax.plot([lo, lo], [yi - 0.12, yi + 0.12], color=c, linewidth=2.0)
        ax.plot([hi, hi], [yi - 0.12, yi + 0.12], color=c, linewidth=2.0)
        ax.plot(d, yi, "o", color=c, markersize=8, zorder=3)
        ax.annotate(f"{d:+.2f}", (d, yi), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=9, color=c, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    ax.set_xlabel("quality gain over the other configuration (normalized points)")
    ax.set_title("Which differences clear the noise", fontsize=15, fontweight="bold", pad=14)
    ax.set_xlim(-0.10, 0.20)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    ax.set_ylim(-1.2, len(rows) - 0.3)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


# Encapsulation, ONE dimension, both tasks. Bootstrap 95% CI (source: handover,
# levels verified against EXPERIMENT_LOG). This single dimension replays the whole
# narrative: guided is placebo on both; tuned beats the bare model on both; the public
# skill helps only on greenfield; and on legacy, tuning really beats the public skill -
# which the aggregate did not show.
ENCAP_ROWS = [
    # (label, delta, ci_low, ci_high)
    ("Weather: bare model -> guidelines",    0.00, -0.060, 0.060),
    ("Weather: bare model -> public skill",  0.10,  0.003, 0.190),
    ("Weather: bare model -> repo-tuned",    0.18,  0.100, 0.250),
    ("Weather: public skill -> repo-tuned",  0.08, -0.000, 0.163),
    ("Movie: bare model -> guidelines",     -0.01, -0.060, 0.045),
    ("Movie: bare model -> public skill",   -0.06, -0.150, 0.030),
    ("Movie: bare model -> repo-tuned",      0.08,  0.037, 0.127),
    ("Movie: public skill -> repo-tuned",    0.14,  0.045, 0.237),
]


def significance_forest_encapsulation(fname):
    """Forest plot of ONE dimension (encapsulation) across both tasks. Same green/grey
    rule as significance_forest. Tasks are visually grouped (Weather block, Movie block)
    so the reader can see the same pattern repeat on each. No run-count / model text."""
    rows = list(reversed(ENCAP_ROWS))  # first row at top
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.axvline(0, color="#202945", linewidth=1.4, zorder=1)
    ax.text(0.004, -0.9, "no difference", color="#202945", fontsize=9,
            ha="left", va="center")
    # faint divider between the Movie block (rows 0-3 from top after reverse) and Weather
    ax.axhline(3.5, color="#e3e6ea", linewidth=1.0, zorder=0)
    for yi, (label, d, lo, hi) in zip(y, rows):
        clears = lo > 0 or hi < 0
        c = "#0f9d58" if clears else "#9aa0a6"
        ax.plot([lo, hi], [yi, yi], color=c, linewidth=2.6, solid_capstyle="round", zorder=2)
        ax.plot([lo, lo], [yi - 0.12, yi + 0.12], color=c, linewidth=2.0)
        ax.plot([hi, hi], [yi - 0.12, yi + 0.12], color=c, linewidth=2.0)
        ax.plot(d, yi, "o", color=c, markersize=8, zorder=3)
        ax.annotate(f"{d:+.2f}", (d, yi), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=9, color=c, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    ax.set_xlabel("encapsulation gain over the other configuration (normalized points)")
    ax.set_title("One dimension, both tasks: which differences are real",
                 fontsize=15, fontweight="bold", pad=14)
    ax.set_xlim(-0.20, 0.30)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    ax.set_ylim(-1.3, len(rows) - 0.3)
    plt.tight_layout()
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def _unused_variance_formulas(fname):
    """Render the two variance formulas used in the post's measurement section.

    1. Noise adds in quadrature (Pythagoras for variance), not linearly.
    2. Averaging n runs shrinks spread by sqrt(n); a gap is real only past ~2*sigma (~0.06).
    mathtext only, no LaTeX install. Colors match the rest of the charts."""
    DARK, GREEN, GREY = "#202945", "#0f9d58", "#5f6671"
    fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=200)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white"); ax.axis("off")
    ax.text(0.5, 0.90, "Two independent noise sources don't add up. They add in quadrature:",
            ha="center", va="center", fontsize=12.5, color=GREY)
    ax.text(0.5, 0.72,
            r"$\sigma_{\mathrm{total}} \; = \; \sqrt{\,\sigma_{\mathrm{agent}}^{2} \; + \; \sigma_{\mathrm{eval}}^{2}\,}$",
            ha="center", va="center", fontsize=27, color=DARK)
    ax.text(0.5, 0.555, "agent writes different code   +   judge scores it differently",
            ha="center", va="center", fontsize=10.5, color=GREY, style="italic")
    ax.plot([0.18, 0.82], [0.46, 0.46], color="#e3e6ea", lw=1.2)
    ax.text(0.5, 0.37, "Averaging $n$ runs shrinks that spread, and a gap is real only when it clears it:",
            ha="center", va="center", fontsize=12.5, color=GREY)
    ax.text(0.30, 0.17, r"$\sigma_{\bar{x}} \; = \; \dfrac{\sigma}{\sqrt{n}}$",
            ha="center", va="center", fontsize=27, color=DARK)
    ax.text(0.72, 0.17, r"$\Delta_{\mathrm{real}} \; \gtrsim \; 2\,\sigma_{\bar{x}} \; \approx \; 0.06$",
            ha="center", va="center", fontsize=27, color=GREEN)
    ax.plot([0.47, 0.47], [0.08, 0.27], color="#e3e6ea", lw=1.2)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(fname, facecolor="white", bbox_inches="tight", pad_inches=0.25)
    plt.close()
    print("saved", fname)


def _unused_variance_table(fname):
    """Render the per-configuration σ_eval / σ_agent table as an image.

    Substack has no native table block, so this table ships as a PNG like the
    other charts. Numbers = the experiment's measured noise per source.
    Style matches the rest of the charts."""
    DARK, GREY, LINE = "#202945", "#5f6671", "#e3e6ea"
    rows = [
        ("Weather, repo-tuned",   "0.013", "0.023"),
        ("Weather, public skill", "0.016", "0.036"),
        ("Weather, baseline",     "0.037", "0.026"),
        ("Movie, public skill",   "0.051", "0.025"),
        ("Movie, other configs",  "0.024–0.038", "≈ 0  (lost in judge noise)"),
    ]
    headers = ("Configuration", "σ_eval\n(judge, same code)", "σ_agent\n(agent, new code)")
    col_x = [0.04, 0.50, 0.78]
    fig, ax = plt.subplots(figsize=(9.0, 3.6), dpi=200)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white"); ax.axis("off")

    y = 0.90
    for cx, h in zip(col_x, headers):
        ax.text(cx, y, h, ha="left", va="center", fontsize=12.5, fontweight="bold", color=DARK)
    ax.plot([0.02, 0.98], [y - 0.10, y - 0.10], color=DARK, lw=1.4)

    y -= 0.21
    for label, se, sa in rows:
        ax.text(col_x[0], y, label, ha="left", va="center", fontsize=12, color=DARK)
        ax.text(col_x[1], y, se, ha="left", va="center", fontsize=12, color=GREY)
        ax.text(col_x[2], y, sa, ha="left", va="center", fontsize=12, color=GREY)
        ax.plot([0.02, 0.98], [y - 0.075, y - 0.075], color=LINE, lw=0.8)
        y -= 0.15

    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(fname, facecolor="white", bbox_inches="tight", pad_inches=0.25)
    plt.close()
    print("saved", fname)


def _radar_on_ax(ax, data, title):
    """Draw a 5-axis radar onto an existing polar axis (for the hero composite)."""
    N = len(DIMS)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    for name, vals in data.items():
        v = vals + vals[:1]
        ax.plot(angles, v, color=COLORS[name], linewidth=2.0, label=name)
        ax.fill(angles, v, color=COLORS[name], alpha=0.07)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIMS, fontsize=9)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels([], fontsize=7, color="#bbb")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=30)
    ax.grid(color="#ddd")


def _ops_bars_on_ax(ax, task):
    """Token bars per variant on an existing axis (compact, for the hero composite)."""
    d = OPS[task]
    tokens = [d[v][1] for v in VARIANTS]
    x = np.arange(len(VARIANTS))
    bars = ax.bar(x, tokens, 0.64, color=[COLORS[v] for v in VARIANTS])
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(tokens) * 0.02,
                f"{int(b.get_height())}k", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(VARIANTS, fontsize=8.5, rotation=15)
    ax.set_ylim(0, max(tokens) * 1.18)
    ax.set_yticks([])
    ax.set_title("Tokens used", fontsize=11, fontweight="bold")
    ax.spines[["top", "right", "left"]].set_visible(False)


def hero_radar_ops(fname):
    """Hero image: two columns (Weather | Movie); each column is a radar on top of its
    token bars. One picture carries the whole 'same skill, different tasks' story plus
    the cost. No run-count / model text on the image (red lines)."""
    fig = plt.figure(figsize=(12, 8.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[2.1, 1.0], hspace=0.28, wspace=0.22)
    axW = fig.add_subplot(gs[0, 0], polar=True)
    axM = fig.add_subplot(gs[0, 1], polar=True)
    _radar_on_ax(axW, WEATHER, "New feature (clean codebase)")
    _radar_on_ax(axM, MOVIE, "Legacy refactor")
    axWo = fig.add_subplot(gs[1, 0])
    axMo = fig.add_subplot(gs[1, 1])
    _ops_bars_on_ax(axWo, "weather")
    _ops_bars_on_ax(axMo, "movie")
    # one shared legend along the bottom
    handles = [plt.Line2D([0], [0], color=COLORS[v], lw=3) for v in VARIANTS]
    fig.legend(handles, VARIANTS, loc="lower center", ncol=4, frameon=False,
               fontsize=11, bbox_to_anchor=(0.5, -0.01))
    fig.subplots_adjust(bottom=0.10, top=0.95)
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


def hero_aggregate_vs_dimensions(fname):
    """Alt hero: the post's thesis as one picture. Left = the single aggregate gain on
    the legacy task (looks like almost nothing). Right = the same result split into
    dimensions, four of them clearly up. 'The headline lies; the breakdown tells the
    truth.' Movie vanilla->repo-tuned. No run-count / model text."""
    GREEN, GREY, RED, DARK = "#0f9d58", "#9aa0a6", "#db4437", "#202945"
    # Movie vanilla -> repo-tuned, per dimension (verified vs EXPERIMENT_LOG)
    dims = ["Architecture", "Encapsulation", "Extensibility", "Domain\nmodeling", "Test\nquality"]
    deltas = [0.120, 0.078, 0.049, 0.037, -0.035]
    agg = 0.049

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 6.0),
                                   gridspec_kw={"width_ratios": [1, 2.0]})

    # Left: the single aggregate bar
    axL.bar([0], [agg], 0.5, color=GREY)
    axL.text(0, agg + 0.004, f"+{agg:.2f}", ha="center", va="bottom",
             fontsize=13, fontweight="bold", color=DARK)
    axL.set_xticks([0]); axL.set_xticklabels(["aggregate\nscore"], fontsize=11)
    axL.set_ylim(-0.06, 0.16)
    axL.axhline(0, color=DARK, linewidth=1.0)
    axL.set_yticks([])
    axL.set_title("What the headline shows", fontsize=13, fontweight="bold")
    axL.text(0, 0.13, "\"barely moved -\nskip it\"", ha="center", va="center",
             fontsize=10.5, color=GREY, style="italic")
    axL.spines[["top", "right", "left"]].set_visible(False)

    # Right: the same result, per dimension
    y = np.arange(len(dims))[::-1]
    colors = [GREEN if d > 0 else RED for d in deltas]
    axR.barh(y, deltas, 0.62, color=colors)
    for yi, d in zip(y, deltas):
        off = 0.004 if d > 0 else -0.004
        ha = "left" if d > 0 else "right"
        axR.text(d + off, yi, f"{d:+.2f}", va="center", ha=ha,
                 fontsize=11, fontweight="bold", color=GREEN if d > 0 else RED)
    axR.set_yticks(y); axR.set_yticklabels(dims, fontsize=11)
    axR.axvline(0, color=DARK, linewidth=1.0)
    axR.set_xlim(-0.09, 0.17)
    axR.set_xticks([])
    axR.set_title("What the five dimensions show", fontsize=13, fontweight="bold")
    axR.spines[["top", "right", "bottom"]].set_visible(False)
    axR.tick_params(left=False)

    fig.suptitle("One number said the skill did almost nothing. The breakdown said otherwise.",
                 fontsize=15.5, fontweight="bold", y=1.0)
    fig.text(0.5, 0.005, "Legacy refactor: quality gain from tuning the skill, aggregate vs per dimension",
             ha="center", fontsize=10, color="#5f6671")
    plt.tight_layout(rect=[0, 0.03, 1, 0.94])
    plt.savefig(fname, dpi=140, bbox_inches="tight")
    plt.close()
    print("saved", fname)


if __name__ == "__main__":
    radar(WEATHER, "Weather task - quality by dimension", "radar_weather.png")
    radar(MOVIE, "Movie task - quality by dimension", "radar_movie.png")
    loop_before_after("loop_before_after.png")
    contrast("increment_vs_vanilla.png")
    # One combined operational figure per task (tokens + time), interleaved into the
    # task sections — replaces the four separate ops_tokens_/ops_time_ images.
    ops_combo("weather", "ops_combo_weather.png")
    ops_combo("movie", "ops_combo_movie.png")
    # Significance now shown as a bootstrap forest plot — replaces variance_formulas
    # (CLT sigma/sqrt-n + 0.06 threshold) and variance_table, which no longer match
    # the method. The two _unused_* funcs are kept only as dead reference.
    significance_forest("significance_forest.png")
    significance_forest_encapsulation("significance_forest_encapsulation.png")
    # Two intuition-builders for the measurement section (break up the wall of text):
    signal_vs_noise("signal_vs_noise.png")
    bootstrap_explainer("bootstrap_explainer.png")
    code_snippet_bootstrap("code_bootstrap.png")
    # Hero images (article header / social card). Red lines: no run-count, no model name.
    hero_radar_ops("hero_radar_ops.png")
    hero_aggregate_vs_dimensions("hero_aggregate_vs_dimensions.png")
    print("Note: '* test quality' axis kept on purpose; on movie it sits near zero for all "
          "variants (skill does not teach testing). Put the explanatory sentence in the post caption.")
    print("Cost intentionally OMITTED from charts (not estimated).")
    print("Method = bootstrap percentile CI (no t-test, no CLT, no 1.96). CI excludes zero => real.")
