#!/bin/bash

# Export Gemini CLI OAuth credentials for subscription-based authentication.
#
# Source this script before running nasde to authenticate via your
# Google/Gemini subscription instead of GEMINI_API_KEY:
#
#   source scripts/export_gemini_oauth_token.sh
#   uv run nasde run --variant gemini-vanilla -C my-benchmark
#
# Prerequisites: run `gemini login` to authenticate via Google.
# The token is read from ~/.gemini/oauth_creds.json.

# NOTE: Do NOT use `set -e` here — this script is sourced into the user's
# shell, so errexit would persist and kill the terminal on any later non-zero
# exit code. Each command already has its own `|| { ... }` error handling.

_gemini_creds_path="$HOME/.gemini/oauth_creds.json"

if [ ! -f "$_gemini_creds_path" ]; then
    echo "ERROR: $_gemini_creds_path not found." >&2
    echo "Run 'gemini login' to authenticate via Google." >&2
    return 1 2>/dev/null || exit 1
fi

_gemini_creds="$(cat "$_gemini_creds_path")" || {
    echo "ERROR: Failed to read $_gemini_creds_path." >&2
    return 1 2>/dev/null || exit 1
}

python3 -c "import json; d=json.loads('''$_gemini_creds'''); assert d, 'empty credentials'" 2>/dev/null || {
    echo "ERROR: $_gemini_creds_path does not contain valid JSON credentials." >&2
    return 1 2>/dev/null || exit 1
}

_access_token="$(python3 -c "import json; print(json.load(open('$_gemini_creds_path')).get('access_token',''))")" || _access_token=""

if [ -n "$_access_token" ]; then
    _exp="$(echo "$_access_token" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('exp',0))" 2>/dev/null)" || _exp=0
    _now="$(python3 -c "import time; print(int(time.time()))")"
    if [ "$_exp" -gt 0 ] && [ "$_now" -gt "$_exp" ]; then
        echo "WARNING: access_token appears expired. Run 'gemini login' to refresh." >&2
        echo "Proceeding anyway -- Gemini CLI may auto-refresh via refresh_token." >&2
    fi
fi

GEMINI_OAUTH_CREDS="$_gemini_creds"
export GEMINI_OAUTH_CREDS

echo "GEMINI_OAUTH_CREDS exported (${_gemini_creds:0:20}...)"

unset _gemini_creds_path _gemini_creds _access_token _exp _now
