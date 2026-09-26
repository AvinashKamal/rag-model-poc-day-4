#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit). Best-effort auto-format; never blocks the agent.
set -u
input="$(cat)"
file_path="$(printf '%s' "$input" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    ti=d.get("tool_input",{})
    print(ti.get("file_path") or "")
except Exception:
    print("")
')"

[ -z "$file_path" ] && exit 0
[ -f "$file_path" ] || exit 0

case "$file_path" in
  *.py)
    command -v ruff >/dev/null 2>&1 && ruff format --quiet "$file_path" >/dev/null 2>&1
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.css|*.json)
    command -v prettier >/dev/null 2>&1 && prettier --write "$file_path" >/dev/null 2>&1
    ;;
esac

exit 0
