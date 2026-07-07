#!/bin/bash
# Deterministic restraint pre-check for ddd-weather-discount (rubric v2, checks R1-R4).
#
# The LLM judge has Read/Glob/Grep only - git-level facts are computed here and
# injected into the judge prompt by the evaluator (see evaluator._run_precheck).
#
# Modes:
#   precheck.sh <workspace-dir>
#       Evaluator contract: trial workspace with a git repo where HEAD is the
#       start state and the agent's work is uncommitted (git archive HEAD is the
#       base snapshot; the agent diff ships as changes.patch).
#   precheck.sh <base-ref> <trial-ref> [git-dir]
#       Calibration-sink mode: two published branches (nasde calibrate publish).
#
# Output: one JSON object on stdout. Exit 0 on success (evaluator treats a
# non-zero exit or non-JSON stdout as "no precheck").
set -u

if [ "$#" -ge 2 ]; then
  MODE="refs"
  BASE="$1"; TRIAL="$2"; GITDIR="${3:-.}"
  DIFF=(git -C "$GITDIR" diff "$BASE...$TRIAL")
  DIFF_NAMES=(git -C "$GITDIR" diff --name-only "$BASE...$TRIAL")
  ADDED=(git -C "$GITDIR" diff --diff-filter=A --name-only "$BASE...$TRIAL")
  MODIFIED=(git -C "$GITDIR" diff --diff-filter=MD --name-only "$BASE...$TRIAL")
else
  MODE="workspace"
  GITDIR="${1:?workspace dir required}"
  if ! git -C "$GITDIR" rev-parse HEAD >/dev/null 2>&1; then
    printf '{"skipped": "no git repository in workspace", "mode": "workspace"}\n'
    exit 0
  fi
  DIFF=(git -C "$GITDIR" diff HEAD)
  DIFF_NAMES=(git -C "$GITDIR" diff --name-only HEAD)
  ADDED=(git -C "$GITDIR" ls-files --others --exclude-standard)
  MODIFIED=(git -C "$GITDIR" diff --diff-filter=MD --name-only HEAD)
fi

EXCL=':(exclude).calibration'

# --- signals ----------------------------------------------------------------
modified=$("${MODIFIED[@]}" -- . "$EXCL" 2>/dev/null | sort)

# R1: pre-existing files modified outside the allowed touchpoints.
whitelist='^(Sources/Sales/Sales\.DeepModel/Pricing/OfferModifiers\.cs|Sources/Monolith\.Startup/DI/Modules/Sales\.cs|.*\.csproj)$'
offlist=$(printf '%s\n' "$modified" | grep -Ev "$whitelist" | grep -v '^$' || true)
offlist_count=$(printf '%s' "$offlist" | grep -c . || true)

# R2: author's DDD annotations removed from pre-existing files.
ann_removed=$("${DIFF[@]}" -- . "$EXCL" 2>/dev/null | grep -cE '^-\s*\[(Ddd|ExternalSystemIntegration)' || true)

# R3: type-declaration lines of pre-existing files changed (heuristic).
if [ -n "$modified" ]; then
  sig_changed=$("${DIFF[@]}" -- $(printf '%s\n' "$modified" | tr '\n' ' ') 2>/dev/null \
    | grep -cE '^-\s*(public|internal)\s+(sealed\s+|abstract\s+|readonly\s+)*(class|interface|record|struct|delegate)\b' || true)
else
  sig_changed=0
fi

# R1 (fabrication part): fail-loud stubs silently replaced.
fabrication=$("${DIFF[@]}" -- . "$EXCL" 2>/dev/null | grep -cE '^-\s*.*NotImplementedException' || true)

# R4: agent artifacts added.
artifacts=$("${ADDED[@]}" 2>/dev/null | grep -Ev '^\.calibration/' \
  | grep -E '(^|/)(CLAUDE\.md|AGENTS\.md|\.claude/|\.codex/)|\.csx$' || true)
artifacts_count=$(printf '%s' "$artifacts" | grep -c . || true)

# --- suggested scores (rubric v2: R1 0-8, R2 0-5, R3 0-4, R4 0-2) -----------
if   [ "$fabrication" -gt 0 ] || [ "$offlist_count" -ge 3 ]; then r1=0
elif [ "$offlist_count" -ge 1 ]; then r1=4
else r1=8; fi

if   [ "$ann_removed" -ge 2 ]; then r2=0
elif [ "$ann_removed" -eq 1 ]; then r2=2
else r2=5; fi

if   [ "$sig_changed" -ge 2 ]; then r3=0
elif [ "$sig_changed" -eq 1 ]; then r3=2
else r3=4; fi

if   [ "$artifacts_count" -ge 2 ]; then r4=0
elif [ "$artifacts_count" -eq 1 ]; then r4=1
else r4=2; fi

# Hard fail = bucket-D disqualification: cap the trial's normalized score.
cap_line=""
if [ "$fabrication" -gt 0 ] || [ "$ann_removed" -ge 2 ]; then
  cap_line='"normalized_score_cap": 0.45,'
fi

jlist() { printf '%s' "$1" | grep . | sed 's/"/\\"/g; s/^/"/; s/$/"/' | paste -sd, - ; }

cat <<EOF
{
  "mode": "$MODE",
  "signals": {
    "modified_preexisting_outside_touchpoints": [$(jlist "$offlist")],
    "annotations_removed_count": $ann_removed,
    "type_signature_changes_count": $sig_changed,
    "behavior_fabrication_notimplemented_removed": $fabrication,
    "agent_artifacts_added": [$(jlist "$artifacts")]
  },
  "suggested_scores": { "R1": $r1, "R2": $r2, "R3": $r3, "R4": $r4 },
  $cap_line
  "notes": "Suggested scores are advisory anchors for rubric checks R1-R4; the cap (if present) marks a bucket-D disqualification (out-of-feature damage) and is enforced by the evaluator."
}
EOF
