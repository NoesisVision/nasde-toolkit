#!/bin/bash
# One trial end-to-end, the pattern battle-tested in the 2026-07 Fable/Opus grid:
# token preflight -> guards -> coding run -> smoke check -> 2x Fable + 2x Opus evals.
#
# Usage: trial_probe.sh <variant> <coder-model> <job-suffix> [smoke-grep-in-workspace-CLAUDE.md]
#   trial_probe.sh claude-vanilla       claude-fable-5   fable5-van6
#   trial_probe.sh claude-deeper-hint   claude-opus-4-8  opus48-deeperhint5 "think deeply"
#   trial_probe.sh claude-ntcoding-tactical-ddd claude-opus-4-8 opus48-ntcoding5 tactical-ddd
#
# Judges are fixed (claude-fable-5 x2, claude-opus-4-8 x2) — edit below if the
# judge pair changes. Run from anywhere; paths are absolute.
set -u
export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd /Users/szjanikowski/Documents/git/noesis/sdlc-projects/nasde-toolkit/examples/ddd-architectural-challenges

VARIANT=${1:?variant}
MODEL=${2:?coder model}
SUFFIX=${3:?job suffix}
SMOKE=${4:-}

# --- token preflight: refresh via cheap keychain-auth ping when < 100 min left
# (a machine restart once rotated the token mid-run and burned a trial on 401s).
unset CLAUDE_CODE_OAUTH_TOKEN 2>/dev/null || true
CJ=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null || true)
REMAIN=$(printf '%s' "$CJ" | jq -r '(((.claudeAiOauth.expiresAt // 0) - now*1000)/60000)|floor' 2>/dev/null || echo 0)
echo "token valid_min: $REMAIN"
if [ "${REMAIN:-0}" -lt 100 ]; then
  echo "token stale -> forcing CLI refresh (haiku ping)"
  claude --model claude-haiku-4-5-20251001 -p "ok" >/dev/null 2>&1 || true
  CJ=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null || true)
fi
TOKEN=$(printf '%s' "$CJ" | jq -r '.claudeAiOauth.accessToken // .accessToken // empty')
unset CJ
[ -z "$TOKEN" ] && { echo "ERROR: no token"; exit 1; }
export CLAUDE_CODE_OAUTH_TOKEN="$TOKEN"; unset TOKEN
echo "token: extracted (not shown)"

[ -f "variants/$VARIANT/CLAUDE.md" ] || { echo "ERROR: variants/$VARIANT/CLAUDE.md missing"; exit 1; }
grep -q "Fit into the existing DDD architecture" tasks/ddd-weather-discount/instruction.md \
  || { echo "ERROR: instruction.md is not canonical"; exit 1; }

echo "########## STAGE 1: coding run ($VARIANT, $MODEL, xhigh) ##########"
uv run nasde run --variant "$VARIANT" --tasks ddd-weather-discount \
  --model "$MODEL" --effort xhigh --timeout 3600 --without-eval \
  --job-suffix "$SUFFIX" -C .
rc=$?; echo "=== nasde run exit: $rc ==="; [ $rc -ne 0 ] && exit $rc

job=$(ls -td jobs/*"$SUFFIX"* 2>/dev/null | head -1)
trial=$(ls -d "$job"/ddd-weather-discount__* 2>/dev/null | head -1)
[ -z "$trial" ] && { echo "ERROR: no trial dir"; exit 1; }
jq -c '{trial_name, harbor_reward: (.verifier_result.rewards.reward // null), exception: (.exception_info != null)}' "$trial/result.json"

ws="$trial/artifacts/workspace"
if [ -n "$SMOKE" ]; then
  grep -q "$SMOKE" "$ws/CLAUDE.md" 2>/dev/null && echo "SMOKE OK: '$SMOKE' in workspace CLAUDE.md" || echo "SMOKE WARN: '$SMOKE' not found"
else
  [ -f "$ws/CLAUDE.md" ] && echo "SMOKE OK: CLAUDE.md mounted" || echo "SMOKE WARN: no CLAUDE.md"
fi
[ -d "$ws/.git" ] && git -C "$ws" diff HEAD --stat | tail -6 && git -C "$ws" ls-files --others --exclude-standard | sed 's/^/ NEW: /' | head -20

echo "########## STAGE 2: 2x Fable evals ##########"
uv run nasde eval "$job" -C . --eval-model claude-fable-5 --eval-backend claude --eval-repetitions 2 --max-concurrent-eval 1
echo "########## STAGE 3: 2x Opus evals ##########"
uv run nasde eval "$job" -C . --eval-model claude-opus-4-8 --eval-backend claude --eval-repetitions 2 --max-concurrent-eval 1

echo "########## RESULTS ##########"
for f in "$trial"/assessment_eval_*.json; do
  jq -c '{model: .evaluator_model, fp: .dimensions_fingerprint, norm: .normalized_score, dims: [.dimensions[] | {(.name): .score}]}' "$f"
done
echo "########## PROBE DONE ##########"
