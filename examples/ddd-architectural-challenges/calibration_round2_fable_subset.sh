#!/bin/bash
# Fable subset pass — approved plan 2026-07-07:
#   5 stratified trials x 2 reps, max_turns untouched (comparability),
#   concurrency 1, zero-progress => sleep 20 min (window reset), resume.
# Run ONLY after Max 20x is active.
set -u
export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$(dirname "$0")"

FP=$(uv run python -c "from nasde_toolkit.evaluator import _dimensions_fingerprint; from pathlib import Path; print(_dimensions_fingerprint(Path('tasks/ddd-weather-discount/assessment_dimensions.json')))")
MODEL=claude-fable-5
TARGET=2
SUBSET=(FjYQ3XQ 4njch2w ZvSsnyg aGTFmDh qHCAtXV)   # A, D, C-lider-v1, B-rozstrzał, B-zaniżony
JOB=jobs/calibration-round2
TMPJOB=jobs/calibration-round2-fable-topup
MAX_STALLS=24

count_evals() {
  local dir=$1 n=0 f
  for f in "$dir"/assessment_eval_*.json; do
    [ -e "$f" ] || continue
    if jq -e --arg fp "$FP" --arg m "$MODEL" \
        'select(.dimensions_fingerprint==$fp and .evaluator_model==$m)' "$f" >/dev/null 2>&1; then
      n=$((n+1))
    fi
  done
  echo "$n"
}

missing_total() {
  local total=0 t d n
  for t in "${SUBSET[@]}"; do
    d="$JOB/ddd-weather-discount__${t}"
    [ -e "$d" ] || { echo "ERROR: brak triala $t w $JOB" >&2; exit 1; }
    n=$(count_evals "$d")
    [ "$n" -lt "$TARGET" ] && total=$((total + TARGET - n))
  done
  echo "$total"
}

stalls=0
while true; do
  rm -rf "$TMPJOB"; mkdir -p "$TMPJOB"
  before=$(missing_total)
  [ "$before" -eq 0 ] && break
  for t in "${SUBSET[@]}"; do
    d="$JOB/ddd-weather-discount__${t}"
    n=$(count_evals "$d")
    if [ "$n" -lt "$TARGET" ]; then
      ln -sfn "$(cd "$d" && pwd -P)" "$TMPJOB/$(basename "$d")"
    fi
  done
  echo "[$(date '+%F %T')] brakuje $before ocen (subset 5x$TARGET) — pass"
  uv run nasde eval "$TMPJOB" -C . \
    --eval-model "$MODEL" --eval-backend claude \
    --eval-repetitions 1 --max-concurrent-eval 1 || true
  after=$(missing_total)
  echo "[$(date '+%F %T')] pass: $before -> $after"
  if [ "$after" -ge "$before" ]; then
    stalls=$((stalls+1))
    [ "$stalls" -ge "$MAX_STALLS" ] && { echo "GIVING UP po $stalls jałowych passach"; exit 1; }
    echo "brak postępu (stall $stalls/$MAX_STALLS) — okno wyczerpane; sen 20 min"
    sleep 1200
  else
    stalls=0
  fi
done

echo "[$(date '+%F %T')] DONE: subset 5 triali x $TARGET oceny Fable"
uv run python calibration_round2_check.py "$JOB" -C . || true
