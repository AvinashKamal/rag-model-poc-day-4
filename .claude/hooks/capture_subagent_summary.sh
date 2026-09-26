#!/usr/bin/env bash
# SubagentStop hook. Extracts the agent's STATUS/FILES_CHANGED/KEY_DECISIONS/OPEN_ISSUES
# block from its transcript and appends ONE compact entry to PROJECT_STATE.md.
# This is the enforcement point for "memory budget: summary only, never full history".
set -u
project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
state_file="$project_dir/.claude/PROJECT_STATE.md"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$script_dir/capture_subagent_summary.py" "$state_file"
exit 0
