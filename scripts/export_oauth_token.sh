#!/bin/bash

# Extract Claude Code OAuth token from macOS Keychain and export it.
#
# Source this script before running nasde to authenticate via your
# Claude Pro/Max subscription instead of ANTHROPIC_API_KEY:
#
#   source scripts/export_oauth_token.sh
#   nasde run --variant baseline -C my-benchmark
#
# The token is extracted from the macOS Keychain entry "Claude Code-credentials"
# which is written by Claude Code when you authenticate via `claude` CLI.

# NOTE: Do NOT use `set -e` here — this script is sourced into the user's
# shell, so errexit would persist and kill the terminal on any later non-zero
# exit code. Each command already has its own `|| { ... }` error handling.

_raw_creds="$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)" || {
    echo "ERROR: Could not read 'Claude Code-credentials' from macOS Keychain." >&2
    echo "Make sure you are logged into Claude Code ('claude' CLI) on this machine." >&2
    return 1 2>/dev/null || exit 1
}

CLAUDE_CODE_OAUTH_TOKEN="$(echo "$_raw_creds" | python3 -c "import sys,json; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])")" || {
    echo "ERROR: Failed to parse OAuth token from Keychain credentials." >&2
    return 1 2>/dev/null || exit 1
}
export CLAUDE_CODE_OAUTH_TOKEN

unset _raw_creds

echo "✓ CLAUDE_CODE_OAUTH_TOKEN exported (${CLAUDE_CODE_OAUTH_TOKEN:0:20}...)"
