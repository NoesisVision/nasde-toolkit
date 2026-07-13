"""Verdict heatmap for the 24-trial grid: 18 rubric checks x 6 arms (PL + EN PNGs).

Per-check verdicts (M1-M7 / R1-R6 / T1-T5, FULL/PARTIAL/NONE) are parsed from the
judges' free-text dimension reasoning — the eval JSON stores scores per dimension
only. Parsing is pattern-based with a consistency audit: within each dimension,
named deductions must match the score direction, and any prose/score mismatch is
printed as a FLAG (three known judge-side inconsistencies survive; see stdout).
Cell value = mean verdict over the arm's 16 evals (4 trials x 4 evals),
FULL=1, PARTIAL=0.5, NONE=0.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs"
FP = "37ffc5f460d2"

ARMS: dict[tuple[str, str], list[str]] = {
    ("Fable 5", "vanilla"): ["ayg7ckA", "Ss2F6dR", "CKEcWHg", "8ks7yf5"],
    ("Fable 5", "hint"): ["7sJ9JK3", "b5jkaWo", "PuuJKHt", "E2soRnZ"],
    ("Fable 5", "skill"): ["MNP2RGe", "qpCRH3A", "NZmadqg", "h3a65Ke"],
    ("Opus 4.8", "vanilla"): ["GoWvUz6", "cyQyXFc", "JTgey8p", "Lozfurr"],
    ("Opus 4.8", "hint"): ["YgcbZjf", "VoktgLb", "sSUYQp4", "a6okSgZ"],
    ("Opus 4.8", "skill"): ["ZMX6Xbq", "TsjcHWY", "Bkwiqom", "F5vYATs"],
}
ARM_ORDER = [("Fable 5", "vanilla"), ("Fable 5", "hint"), ("Fable 5", "skill"),
             ("Opus 4.8", "vanilla"), ("Opus 4.8", "hint"), ("Opus 4.8", "skill")]
CODER_COLOR = {"Fable 5": "#2a78d6", "Opus 4.8": "#1baf7a"}
INK = "#1a1a19"

MAX = {"M1": 10, "M2": 9, "M3": 9, "M4": 7, "M5": 7, "M6": 4, "M7": 4,
       "R1": 8, "R2": 5, "R3": 4, "R4": 2, "R5": 4, "R6": 2,
       "T1": 9, "T2": 5, "T3": 5, "T4": 4, "T5": 2}
DIM_CHECKS = {"model_fit": [f"M{i}" for i in range(1, 8)],
              "restraint": [f"R{i}" for i in range(1, 7)],
              "test_quality": [f"T{i}" for i in range(1, 6)]}
CHECKS = DIM_CHECKS["model_fit"] + DIM_CHECKS["restraint"] + DIM_CHECKS["test_quality"]

LABELS = {
    "pl": {
        "M1": "M1 · domknięcie stanu świata, czystość",
        "M2": "M2 · polityka składana w fabryce",
        "M3": "M3 · reużycie kanonicznych typów rabatu",
        "M4": "M4 · bez widmowych modyfikatorów",
        "M5": "M5 · jawna interakcja z rabatami",
        "M6": "M6 · awaria to nie pomiar",
        "M7": "M7 · proporcjonalny szew na przyszłość",
        "R1": "R1 · pliki zastane nietknięte",
        "R2": "R2 · adnotacje autora zachowane",
        "R3": "R3 · bez przepisywania sygnatur",
        "R4": "R4 · bez artefaktów agenta",
        "R5": "R5 · modularyzacja jak w otoczeniu",
        "R6": "R6 · domena mówi językiem domeny",
        "T1": "T1 · kompozycja testowana (ChooseFor)",
        "T2": "T2 · pojedynczy odczyt dowiedziony",
        "T3": "T3 · awaria/brzeg testowane uczciwie",
        "T4": "T4 · izolacja adaptera",
        "T5": "T5 · konwencje domowe",
    },
    "en": {
        "M1": "M1 · world-state closure, purity",
        "M2": "M2 · policy assembled in the factory",
        "M3": "M3 · canonical discount type reuse",
        "M4": "M4 · no phantom modifiers",
        "M5": "M5 · explicit discount interaction",
        "M6": "M6 · failure is not a measurement",
        "M7": "M7 · proportionate future-ready seam",
        "R1": "R1 · pre-existing files untouched",
        "R2": "R2 · author's annotations preserved",
        "R3": "R3 · no signature rewrites",
        "R4": "R4 · no agent artifacts",
        "R5": "R5 · modularization mirrors design",
        "R6": "R6 · domain speaks domain language",
        "T1": "T1 · composition tested (ChooseFor)",
        "T2": "T2 · single fetch asserted",
        "T3": "T3 · failure/boundary tested honestly",
        "T4": "T4 · adapter isolation",
        "T5": "T5 · house conventions",
    },
}
TEXT = {
    "pl": {
        "title": "Profil werdyktów rubryki v2.3 — 18 checków × 6 ramion "
                 "(komórka = średnia z 16 ocen: 4 triale × 4 ewaluacje)",
        "scale": "0% = wszędzie NONE · 50% = przeciętnie PARTIAL · 100% = wszędzie FULL",
        "groups": {"M": "model i kompozycja", "R": "granice i powściągliwość", "T": "jakość testów"},
        "out": "verdict_heatmap.png",
    },
    "en": {
        "title": "Rubric v2.3 verdict profile — 18 checks × 6 arms "
                 "(cell = mean of 16 evaluations: 4 trials × 4 evals)",
        "scale": "0% = NONE everywhere · 50% = PARTIAL on average · 100% = FULL everywhere",
        "groups": {"M": "model & composition fit", "R": "boundaries & restraint", "T": "test quality"},
        "out": "verdict_heatmap_en.png",
    },
}

ID = r"[MRT]\d"
V = r"FULL|PARTIAL|NONE|MAX"
# 1) verdict after an ID group: "M3 PARTIAL", "M1/M2, M4 FULL", "M4 (NONE: ...)",
#    "R3 scores FULL", "M7 falls to PARTIAL", "(T3 full)" — lowercase only next to the ID
P_VERDICT = re.compile(
    rf"\b({ID}(?:\s*[/,]\s*{ID})*)"
    rf"(?:[:\-–—(=\s]|\b(?:scores?|stays?|is|are|remains?|at|all|falls?|drops?|to)\b)*"
    rf"({V}|full|partial|none)\b")
# 2) verdict with explicit points: "R3 FULL(2)" — points win when they contradict the word
P_V_POINTS = re.compile(rf"\b({ID})\s*({V})\s*\(\s*(\d+)")
# 3) verdict-first: "PARTIAL on R5 (2)"
P_V_FIRST = re.compile(rf"\b({V})s?\s+on\s+({ID})\b")
# 4) verdict-first with a listed tail: "PARTIALs: M3 (...), M4 (...)" — IDs until sentence end
P_V_LIST = re.compile(rf"\b({V})s?\s*(?:on)?:\s*([^.;]*)")
# 5) bare points: "R5 2/4", "T1=0", "(R1 8, R2 5)"
P_POINTS = re.compile(rf"\b({ID})\s*(?:[=:]\s*|\s+)(\d+)(?:\s*/\s*(\d+))?(?=[\s,;.)\]])")
# 6) "Lost 5 on M3"
P_LOST = re.compile(rf"\b[Ll]ost\s+(\d+)\s+on\s+({ID})\b")


def classify(points: int, cid: str) -> str:
    if points <= 0:
        return "NONE"
    return "FULL" if points >= MAX[cid] else "PARTIAL"


def parse_eval(d: dict) -> tuple[dict[str, str], list[str]]:
    verdicts: dict[str, str] = {}
    audit: list[str] = []
    for dim in d["dimensions"]:
        name, text = dim["name"], dim["reasoning"]
        local: dict[str, str] = {}
        for cid, v, pts in P_V_POINTS.findall(text):
            # M5 FULL is 6 of 7 by definition, so 6 does not contradict the word
            genuine_full = MAX[cid] - (1 if cid == "M5" else 0)
            if v == "FULL" and int(pts) < genuine_full:
                local.setdefault(cid, classify(int(pts), cid))
        for ids, v in P_VERDICT.findall(text):
            v = v.upper()
            for cid in re.split(r"\s*[/,]\s*", ids):
                local.setdefault(cid, "FULL" if v == "MAX" else v)
        for v, cid in P_V_FIRST.findall(text):
            local.setdefault(cid, "FULL" if v == "MAX" else v)
        for v, tail in P_V_LIST.findall(text):
            for cid in re.findall(rf"\b{ID}\b", tail):
                local.setdefault(cid, "FULL" if v == "MAX" else v)
        for cid, pts, _mx in P_POINTS.findall(text):
            local.setdefault(cid, classify(int(pts), cid))
        for lost, cid in P_LOST.findall(text):
            local.setdefault(cid, classify(MAX[cid] - int(lost), cid))
        checks = DIM_CHECKS[name]
        for cid in checks:
            local.setdefault(cid, "FULL")  # judges enumerate deductions only
        # M5 FULL is 6/7 by rubric definition (7 = MAX), so an all-FULL model_fit
        # legitimately lands on 49/50.
        floor = dim["max_score"] - (1 if name == "model_fit" else 0)
        full_score = dim["score"] >= floor
        has_deduction = any(local[c] != "FULL" for c in checks)
        if full_score == has_deduction:
            audit.append(f"{name} {dim['score']}/{dim['max_score']} prose/score mismatch")
        verdicts.update({c: local[c] for c in checks})
    return verdicts, audit


def collect() -> tuple[dict[tuple[str, str], list[dict]], list[str]]:
    per_arm: dict[tuple[str, str], list[dict]] = {a: [] for a in ARMS}
    flags: list[str] = []
    for arm, trials in ARMS.items():
        for t in trials:
            (td,) = JOBS.glob(f"*/ddd-weather-discount__{t}")
            for f in sorted(td.glob("assessment_eval_*.json")):
                d = json.loads(f.read_text())
                if d.get("dimensions_fingerprint") != FP:
                    continue
                verdicts, audit = parse_eval(d)
                per_arm[arm].append(verdicts)
                flags.extend(f"{t} {f.name} ({d['evaluator_model']}): {a}" for a in audit)
    return per_arm, flags


VAL = {"FULL": 1.0, "PARTIAL": 0.5, "NONE": 0.0}
CMAP = LinearSegmentedColormap.from_list("verdict", ["#f8f3fe", "#4a2a8a"])


def heatmap(per_arm: dict, lang: str) -> None:
    t = TEXT[lang]
    grid = [[sum(VAL[evals[c]] for evals in per_arm[arm]) / len(per_arm[arm])
             for arm in ARM_ORDER] for c in CHECKS]

    fig, ax = plt.subplots(figsize=(9.6, 8.6))
    fig.suptitle(t["title"], fontsize=11.5, color=INK, y=0.975)
    ax.imshow(grid, cmap=CMAP, vmin=0.0, vmax=1.0, aspect="auto")

    for yi, row in enumerate(grid):
        for xi, v in enumerate(row):
            ax.text(xi, yi, f"{round(v * 100)}%", ha="center", va="center",
                    fontsize=8.6, color="white" if v > 0.62 else "#3a3a38",
                    fontweight="bold" if v <= 0.5 else "normal")

    ax.set_xticks(range(len(ARM_ORDER)))
    ax.set_xticklabels([config for _c, config in ARM_ORDER], fontsize=9.5, color="#444")
    for xi, (coder, _config) in enumerate(ARM_ORDER):
        ax.annotate(coder, (xi, 1.012), xycoords=("data", "axes fraction"),
                    ha="center", fontsize=8.6, color=CODER_COLOR[coder], fontweight="bold")
    ax.set_yticks(range(len(CHECKS)))
    ax.set_yticklabels([LABELS[lang][c] for c in CHECKS], fontsize=8.8, color="#3a3a38")
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)

    # white gridlines between cells; heavier breaks + side captions between M/R/T groups
    for xi in range(1, len(ARM_ORDER)):
        lw = 3.4 if xi == 3 else 1.6
        ax.axvline(xi - 0.5, color="white", linewidth=lw)
    for yi in range(1, len(CHECKS)):
        ax.axhline(yi - 0.5, color="white", linewidth=1.6)
    for group, start, size in (("M", 0, 7), ("R", 7, 6), ("T", 13, 5)):
        if start:
            ax.axhline(start - 0.5, color="white", linewidth=4.2)
        ax.annotate(t["groups"][group], (1.01, 1 - (start + size / 2) / len(CHECKS)),
                    xycoords="axes fraction", ha="left", va="center", fontsize=8.6,
                    color="#777", rotation=270)

    fig.text(0.5, 0.015, t["scale"], ha="center", fontsize=8.2, color="#777")
    fig.tight_layout(rect=(0, 0.035, 0.97, 0.94))
    out = HERE / "assets" / t["out"]
    fig.savefig(out, dpi=160, facecolor="white")
    print("saved:", out)


if __name__ == "__main__":
    per_arm, flags = collect()
    n = sum(len(v) for v in per_arm.values())
    print(f"evals parsed: {n} (expected 96)")
    for fl in flags:
        print("FLAG", fl)
    for lang in ("pl", "en"):
        heatmap(per_arm, lang)
