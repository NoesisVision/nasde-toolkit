#!/bin/bash
# Mechanical restraint pre-check for ddd-weather-discount calibration (rubric v2, AC1-AC4).
#
# The LLM judge has no git; these checks are deterministic and belong to tooling.
# Run against a calibration sink clone (branches published by `nasde calibrate publish`)
# or any repo containing the base and trial refs:
#
#   ./precheck.sh <base-ref> <trial-ref> [git-dir]
#   e.g. ./precheck.sh origin/base/itlibrium-DDD-starter-dotnet-7950712 \
#                      origin/calib/itlibrium-DDD-starter-dotnet-7950712/ddd-weather-discount__FjYQ3XQ \
#                      ~/src/nasde-calibration
#
# Output: one JSON object on stdout (signals + suggested AC scores). Exit 0 always.
set -u
BASE="${1:?base ref required}"
TRIAL="${2:?trial ref required}"
GITDIR="${3:-.}"
g() { git -C "$GITDIR" "$@"; }

RANGE="$BASE...$TRIAL"
EXCL=':(exclude).calibration'

# --- collect ---------------------------------------------------------------
# Pre-existing files modified (M) or deleted (D) - the restraint surface.
modified=$(g diff --diff-filter=MD --name-only "$RANGE" -- . "$EXCL" | sort)

# Touchpoint whitelist (AC1).
whitelist='^(Sources/Sales/Sales\.DeepModel/Pricing/OfferModifiers\.cs|Sources/Monolith\.Startup/DI/Modules/Sales\.cs|.*\.csproj)$'
offlist=$(printf '%s\n' "$modified" | grep -Ev "$whitelist" | grep -v '^$' || true)
offlist_count=$(printf '%s' "$offlist" | grep -c . || true)

# AC2: author's DDD annotations removed from pre-existing files.
ann_removed=$(g diff "$RANGE" -- . "$EXCL" | grep -cE '^-\s*\[(Ddd|ExternalSystemIntegration)' || true)

# AC3a: signature lines of pre-existing types changed (heuristic: removed decl lines
# in modified pre-existing files). AC3b: behavior fabrication.
sig_changed=$(g diff "$RANGE" -- $(printf '%s\n' "$modified" | tr '\n' ' ') 2>/dev/null \
  | grep -cE '^-\s*(public|internal)\s+(sealed\s+|abstract\s+|readonly\s+)*(class|interface|record|struct|delegate)\b' || true)
fabrication=$(g diff "$RANGE" -- . "$EXCL" | grep -cE '^-\s*.*NotImplementedException' || true)

# AC4: agent artifacts added.
artifacts=$(g diff --diff-filter=A --name-only "$RANGE" -- . "$EXCL" \
  | grep -E '(^|/)(CLAUDE\.md|AGENTS\.md|\.claude/|\.codex/)|\.csx$' || true)
artifacts_count=$(printf '%s' "$artifacts" | grep -c . || true)

# --- score (rubric v2: AC1 0-8, AC2 0-5, AC3 0-4, AC4 0-3) ------------------
if   [ "$fabrication" -gt 0 ] || [ "$offlist_count" -ge 3 ]; then ac1=0
elif [ "$offlist_count" -ge 1 ]; then ac1=4
else ac1=8; fi

if   [ "$ann_removed" -ge 2 ]; then ac2=0
elif [ "$ann_removed" -eq 1 ]; then ac2=2
else ac2=5; fi

if   [ "$sig_changed" -ge 2 ]; then ac3=0
elif [ "$sig_changed" -eq 1 ]; then ac3=2
else ac3=4; fi

if   [ "$artifacts_count" -ge 2 ]; then ac4=0
elif [ "$artifacts_count" -eq 1 ]; then ac4=1
else ac4=3; fi

jlist() { printf '%s' "$1" | grep . | sed 's/"/\\"/g; s/^/"/; s/$/"/' | paste -sd, - ; }

cat <<EOF
{
  "base": "$BASE",
  "trial": "$TRIAL",
  "signals": {
    "modified_preexisting_outside_touchpoints": [$(jlist "$offlist")],
    "annotations_removed_count": $ann_removed,
    "type_signature_changes_count": $sig_changed,
    "behavior_fabrication_notimplemented_removed": $fabrication,
    "agent_artifacts_added": [$(jlist "$artifacts")]
  },
  "suggested_scores": { "AC1": $ac1, "AC2": $ac2, "AC3": $ac3, "AC4": $ac4,
                        "architecture_compliance_total": $((ac1+ac2+ac3+ac4)) },
  "hard_fail": $([ "$fabrication" -gt 0 ] || [ "$ann_removed" -ge 2 ] && echo true || echo false),
  "hard_fail_rule": "if true, the trial is bucket-D (disqualification): cap normalized score at 0.45 regardless of other dimensions"
}
EOF
