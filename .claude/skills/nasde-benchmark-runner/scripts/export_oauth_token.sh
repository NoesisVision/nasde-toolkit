#!/bin/bash

# Extract Claude Code OAuth token and export it as CLAUDE_CODE_OAUTH_TOKEN.
#
# Source this script before running nasde to authenticate via your
# Claude Pro/Max subscription instead of ANTHROPIC_API_KEY:
#
#   source scripts/export_oauth_token.sh
#   nasde run --variant baseline -C my-benchmark
#
# Storage backend depends on OS:
#   - macOS: Keychain entry "Claude Code-credentials" (written by `claude` CLI)
#   - Linux: plain JSON at ~/.claude/.credentials.json
# Windows users: see scripts/export_oauth_token.ps1 (PowerShell).

# NOTE: Do NOT use `set -e` here -- this script is sourced into the user's
# shell, so errexit would persist and kill the terminal on any later non-zero
# exit code. Each command already has its own `|| { ... }` error handling.

_raw_creds=""

if command -v security >/dev/null 2>&1; then
    _raw_creds="$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)"
fi

if [ -z "$_raw_creds" ] && [ -f "$HOME/.claude/.credentials.json" ]; then
    _raw_creds="$(cat "$HOME/.claude/.credentials.json")"
fi

if [ -z "$_raw_creds" ]; then
    echo "ERROR: Could not read Claude Code credentials." >&2
    echo "  - macOS: keychain entry 'Claude Code-credentials' missing" >&2
    echo "  - Linux: ~/.claude/.credentials.json missing" >&2
    echo "Run 'claude' CLI and log in first." >&2
    return 1 2>/dev/null || exit 1
fi

CLAUDE_CODE_OAUTH_TOKEN="$(echo "$_raw_creds" | python3 -c "import sys,json; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])")" || {
    echo "ERROR: Failed to parse OAuth token from Claude credentials." >&2
    return 1 2>/dev/null || exit 1
}
export CLAUDE_CODE_OAUTH_TOKEN

unset _raw_creds

echo "✓ CLAUDE_CODE_OAUTH_TOKEN exported (${CLAUDE_CODE_OAUTH_TOKEN:0:20}...)"
