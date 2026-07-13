#!/bin/bash
# Top up evaluations on an EXISTING job (no coding run) — used whenever a window
# limit or an interruption left a trial with an incomplete judge pair.
#
# Usage: eval_topup.sh <job-dir-name-under-jobs/> <judge-model> <repetitions>
#   eval_topup.sh 2026-07-10__14-30-58__claude-vanilla__opus48-van5 claude-fable-5 1
#   eval_topup.sh 2026-07-08__08-10-04__claude-vanilla__fable5-coder claude-opus-4-8 2
set -u
export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/examples/ddd-architectural-challenges

JOB=${1:?job dir name}
JUDGE=${2:?judge model}
REPS=${3:?repetitions}

uv run nasde eval "jobs/$JOB" -C . --eval-model "$JUDGE" --eval-backend claude \
  --eval-repetitions "$REPS" --max-concurrent-eval 1
echo "########## RESULTS (all evals in $JOB) ##########"
for f in jobs/"$JOB"/*/assessment_eval_*.json; do
  jq -c '{model: .evaluator_model, fp: .dimensions_fingerprint, norm: .normalized_score}' "$f"
done
