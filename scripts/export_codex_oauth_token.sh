#!/bin/bash

# Validate Codex OAuth auth.json for ChatGPT subscription-based authentication.
#
# Source this script before running nasde to verify that your ChatGPT
# subscription credentials are valid:
#
#   source scripts/export_codex_oauth_token.sh
#   uv run nasde run --variant codex-vanilla -C my-benchmark
#
# Prerequisites: run `codex login` to authenticate via ChatGPT.
# The token is read from ~/.codex/auth.json.

set -e

_codex_auth_path="$HOME/.codex/auth.json"

if [ ! -f "$_codex_auth_path" ]; then
    echo "ERROR: $_codex_auth_path not found." >&2
    echo "Run 'codex login' to authenticate via ChatGPT subscription." >&2
    return 1 2>/dev/null || exit 1
fi

_auth_mode="$(python3 -c "import json; print(json.load(open('$_codex_auth_path')).get('auth_mode', ''))")" || {
    echo "ERROR: Failed to parse $_codex_auth_path." >&2
    return 1 2>/dev/null || exit 1
}

if [ "$_auth_mode" != "chatgpt" ]; then
    echo "ERROR: auth_mode is '$_auth_mode', expected 'chatgpt'." >&2
    echo "Run 'codex login' to authenticate via ChatGPT subscription." >&2
    return 1 2>/dev/null || exit 1
fi

_access_token="$(python3 -c "import json; print(json.load(open('$_codex_auth_path')).get('tokens',{}).get('access_token',''))")" || {
    echo "ERROR: Failed to extract access_token from $_codex_auth_path." >&2
    return 1 2>/dev/null || exit 1
}

if [ -z "$_access_token" ]; then
    echo "ERROR: access_token is empty in $_codex_auth_path." >&2
    echo "Run 'codex login' to re-authenticate." >&2
    return 1 2>/dev/null || exit 1
fi

_exp="$(echo "$_access_token" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('exp',0))" 2>/dev/null)" || _exp=0
_now="$(python3 -c "import time; print(int(time.time()))")"
if [ "$_exp" -gt 0 ] && [ "$_now" -gt "$_exp" ]; then
    echo "WARNING: access_token expired. Run 'codex login' to refresh." >&2
    echo "Proceeding anyway -- Codex CLI may auto-refresh via refresh_token." >&2
fi

echo "Codex OAuth validated (auth_mode=chatgpt, token=${_access_token:0:20}...)"

unset _codex_auth_path _auth_mode _access_token _exp _now
