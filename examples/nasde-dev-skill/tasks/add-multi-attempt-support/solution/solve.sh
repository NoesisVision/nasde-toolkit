#!/bin/bash
cd /app

git cherry-pick 812b189 --no-commit 2>/dev/null || true

if ! grep -q "\-\-attempts" CLAUDE.md 2>/dev/null; then
    sed -i '/--without-eval/a\  --attempts INT                       # Number of independent attempts per task (default: 1)\n  -n INT                               # Short alias for --attempts' CLAUDE.md
fi

if ! grep -q "\-\-attempts" README.md 2>/dev/null; then
    sed -i '/--without-eval/a\| `--attempts` / `-n` | Number of independent attempts per task (default: 1) |' README.md
fi
