#!/bin/bash
# Calibration round 2 — judge-model matrix on the 13 reference trials.
#
# Matrix (edit MATRIX below to swap models):
#   claude-fable-5   × claude backend   (newest Claude, Mythos-class)
#   claude-opus-4-8  × claude backend   (newest Opus)
#   gpt-5.5          × codex backend    (best model confirmed available in
#                                        codex CLI as of the June trials; check
#                                        `codex exec --model` options and bump
#                                        here if a newer one ships)
#
# Volume: 13 trials x 3 judges x 3 reps = 117 judge runs. Evals append to the
# original trial dirs as assessment_eval_<N>.json; the v2 task-level dimensions
# give them a fresh fingerprint, so summaries never mix them with v1 groups.
#
# Steps: build symlink job dir -> run matrix -> acceptance check -> export to
# nasde-results -> commit (push with NASDE_RESULTS_PUSH=1).
set -euo pipefail
cd "$(dirname "$0")"

JOB=jobs/calibration-round2
TRIALS=(SuuU3yh Kc8Es5k 2yQqBnm 3vwBnrU ZvSsnyg qHCAtXV Jyu9YsY aGTFmDh SnS5iHF 4njch2w cE8V77t URtZnzf FjYQ3XQ)
MATRIX=(
  "claude-fable-5 claude"
  "claude-opus-4-8 claude"
  "gpt-5.5 codex"
)
RESULTS_REPO="${NASDE_RESULTS_DIR:-$(pwd)/../../../nasde-results}"
EXPORT_DIR="$RESULTS_REPO/calibration-round2-ddd-weather-discount"

# --- 1. assemble the reference job dir --------------------------------------
# Local trials are symlinked; trials whose job dirs are gone (URtZnzf, FjYQ3XQ
# ran elsewhere) are restored from the calibration sink.
mkdir -p "$JOB"
for t in "${TRIALS[@]}"; do
  [ -e "$JOB/ddd-weather-discount__${t}" ] && continue
  src=$(find jobs -maxdepth 2 -type d -name "ddd-weather-discount__${t}" -not -path "*/calibration-round2/*" | head -1)
  if [ -n "$src" ]; then
    ln -sfn "$(pwd)/$src" "$JOB/ddd-weather-discount__${t}"
  else
    echo "trial ${t} not in local jobs/ — restoring from the calibration sink"
    ./calibration_round2_restore.sh "$t" "$JOB"
  fi
done
echo "Job dir ready: $JOB ($(ls "$JOB" | wc -l | tr -d ' ') trials)"

# --- 2. judge matrix ----------------------------------------------------------
for entry in "${MATRIX[@]}"; do
  read -r model backend <<< "$entry"
  echo "=== judge: $model ($backend) ==="
  uv run nasde eval "$JOB" -C . --eval-model "$model" --eval-backend "$backend" --eval-repetitions 3
done

# --- 3. acceptance assertions (stop conditions) --------------------------------
uv run python calibration_round2_check.py "$JOB" -C . || CHECK_FAILED=1

# --- 4. export results + commit (results survive even if jobs/ is cleared) -----
uv run nasde results-export "$JOB" --to "$EXPORT_DIR" -C .
cp calibration_round2_check.py "$EXPORT_DIR/" 2>/dev/null || true
uv run python calibration_round2_check.py "$JOB" -C . > "$EXPORT_DIR/acceptance_report.txt" || true
git -C "$RESULTS_REPO" add calibration-round2-ddd-weather-discount
git -C "$RESULTS_REPO" commit -m "calibration round 2: judge matrix (fable-5 / opus-4.8 / gpt-5.5-codex) on 13 ddd-weather-discount trials, rubric v2 + acceptance report"
echo "Committed to $RESULTS_REPO."
if [ "${NASDE_RESULTS_PUSH:-0}" = "1" ]; then git -C "$RESULTS_REPO" push; fi

exit "${CHECK_FAILED:-0}"
