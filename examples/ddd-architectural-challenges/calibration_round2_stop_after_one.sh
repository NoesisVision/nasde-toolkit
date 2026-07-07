#!/bin/bash
# Watchdog: kill the fable-driver loop the moment ONE new eval lands on disk,
# so the in-flight evaluation is not wasted but no further one runs.
set -u
export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$(dirname "$0")"
FP=8e0d00bfd8df
MODEL=claude-fable-5
SUBSET=(FjYQ3XQ 4njch2w ZvSsnyg aGTFmDh qHCAtXV)

count() {
  local total=0 t f
  for t in "${SUBSET[@]}"; do
    for f in "jobs/calibration-round2/ddd-weather-discount__${t}"/assessment_eval_*.json; do
      [ -e "$f" ] || continue
      jq -e --arg fp "$FP" --arg m "$MODEL" \
        'select(.dimensions_fingerprint==$fp and .evaluator_model==$m)' "$f" >/dev/null 2>&1 && total=$((total+1))
    done
  done
  echo "$total"
}

BASE=$(count)
echo "watchdog: baseline $BASE evals; waiting for +1"
while true; do
  cur=$(count)
  if [ "$cur" -gt "$BASE" ]; then
    echo "watchdog: eval landed ($BASE -> $cur) — stopping the loop"
    pkill -TERM -f "fable-driver.sh" 2>/dev/null || true
    sleep 1
    pkill -TERM -f "nasde eval jobs/calibration-round2-fable-topup" 2>/dev/null || true
    sleep 1
    pkill -TERM -f -- "claude -p --output-format json" 2>/dev/null || true
    echo "watchdog: stopped; total $MODEL evals on subset: $cur"
    exit 0
  fi
  sleep 15
done
