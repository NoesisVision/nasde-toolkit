#!/bin/bash
# Restore a ddd-weather-discount trial dir from the calibration sink, for trials
# whose local jobs/ artifacts are gone (published PRs outlive local job dirs).
#
# Rebuilds the evaluator contract exactly:
#   - workspace git where HEAD = start state (sink base branch) and the agent's
#     work is applied UNCOMMITTED (diff base..calib, .calibration excluded),
#   - minimal result.json / config.json synthesized from the sink's
#     .calibration/metrics.json (task_id.path pinned to the local task dir).
#
# Usage: ./calibration_round2_restore.sh <trial-suffix> <dest-job-dir>
set -euo pipefail
SUFFIX=${1:?trial suffix required (e.g. FjYQ3XQ)}
DEST_JOB=${2:?dest job dir required}
SINK_URL=${NASDE_SINK_URL:-https://github.com/NoesisVision/nasde-calibration.git}
BASE_BRANCH=base/itlibrium-DDD-starter-dotnet-7950712
CALIB_BRANCH="calib/itlibrium-DDD-starter-dotnet-7950712/ddd-weather-discount__${SUFFIX}"

TRIAL_DIR="$DEST_JOB/ddd-weather-discount__${SUFFIX}"
WS="$TRIAL_DIR/artifacts/workspace"
if [ -e "$TRIAL_DIR" ]; then echo "already exists: $TRIAL_DIR"; exit 0; fi
mkdir -p "$WS"

git -C "$WS" init -q
git -C "$WS" fetch -q --depth 1 "$SINK_URL" \
  "$BASE_BRANCH:refs/heads/sink-base" \
  "$CALIB_BRANCH:refs/heads/sink-calib"
git -C "$WS" checkout -q sink-base

# Agent's work as uncommitted changes (evaluator/publisher convention).
git -C "$WS" diff sink-base sink-calib -- . ':(exclude).calibration' | git -C "$WS" apply

# Trial metadata from the sink's calibration bundle.
git -C "$WS" show "sink-calib:.calibration/metrics.json" > "$TRIAL_DIR/metrics.json"
jq '{task_name, source, trial_name, started_at, finished_at,
     task_id: {path: "tasks/ddd-weather-discount"},
     verifier_result: {rewards: {reward: .harbor_reward}}}' \
  "$TRIAL_DIR/metrics.json" > "$TRIAL_DIR/result.json"
jq '{agent: {name: .agent_name}}' "$TRIAL_DIR/metrics.json" > "$TRIAL_DIR/config.json"

echo "restored: $TRIAL_DIR (workspace HEAD = start state, agent diff uncommitted)"
