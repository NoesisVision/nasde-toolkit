#!/bin/bash
# ONE Fable evaluation on a single trial (cost-bounded iteration).
# Usage: fable-one.sh <suffix>
set -u
export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$(dirname "$0")"
SUFFIX=${1:?suffix}
TMPJOB=jobs/calibration-round2-one
rm -rf "$TMPJOB"; mkdir -p "$TMPJOB"
TRIAL=$(cd "jobs/calibration-round2/ddd-weather-discount__${SUFFIX}" && pwd -P)
ln -sfn "$TRIAL" "$TMPJOB/ddd-weather-discount__${SUFFIX}"
uv run nasde eval "$TMPJOB" -C . --eval-model claude-fable-5 --eval-backend claude \
  --eval-repetitions 1 --max-concurrent-eval 1
rc=$?
latest=$(ls -t "$TRIAL"/assessment_eval_*.json 2>/dev/null | head -1)
if [ -n "$latest" ]; then
  echo "=== wynik ==="
  jq -c '{model: .evaluator_model, normalized: .normalized_score, dims: [.dimensions[] | {(.name): .score}], cap: .precheck.normalized_score_cap, cap_applied: .precheck.normalized_score_cap_applied, duration_sec}' "$latest"
fi
exit $rc
