#!/bin/bash

# Validate available Gemini authentication methods.
#
# Run this script to check which Gemini auth methods are configured:
#
#   bash scripts/validate_gemini_auth.sh
#
# Checks (in priority order):
#   1. GEMINI_API_KEY env var
#   2. GOOGLE_API_KEY env var
#   3. ~/.gemini/oauth_creds.json (from `gemini login`)

set -e

_found=0

if [ -n "$GEMINI_API_KEY" ]; then
    echo "GEMINI_API_KEY is set (${GEMINI_API_KEY:0:8}...)"
    _found=1
else
    echo "GEMINI_API_KEY is not set."
fi

if [ -n "$GOOGLE_API_KEY" ]; then
    echo "GOOGLE_API_KEY is set (${GOOGLE_API_KEY:0:8}...)"
    _found=1
else
    echo "GOOGLE_API_KEY is not set."
fi

_gemini_creds_path="$HOME/.gemini/oauth_creds.json"
if [ -f "$_gemini_creds_path" ]; then
    echo "OAuth credentials found at $_gemini_creds_path"
    _found=1
else
    echo "OAuth credentials not found at $_gemini_creds_path"
fi

echo ""

if [ "$_found" -eq 1 ]; then
    echo "At least one Gemini auth method is available."
    exit 0
else
    echo "ERROR: No Gemini auth method found." >&2
    echo "Set GEMINI_API_KEY, GOOGLE_API_KEY, or run 'gemini login'." >&2
    exit 1
fi
