#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Blocks destructive commands agents should never
# run unattended: dropping the Qdrant collection, k6 against a non-local host,
# rm -rf, and tearing down volumes. Exit 2 blocks the call and feeds stderr back
# to the calling agent as the reason.
set -u
input="$(cat)"
command_str="$(printf '%s' "$input" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tool_input",{}).get("command",""))
except Exception:
    print("")
')"

[ -z "$command_str" ] && exit 0

deny() {
  echo "Blocked by guard_destructive.sh: $1" >&2
  exit 2
}

lower="$(printf '%s' "$command_str" | tr '[:upper:]' '[:lower:]')"

case "$lower" in
  *"rm -rf"*|*"rm -fr"*)
    deny "rm -rf is not allowed unattended — confirm with the user first." ;;
  *"docker compose down"*"-v"*|*"docker-compose down"*"-v"*)
    deny "tearing down Compose volumes destroys Qdrant/Grafana/Prometheus data — confirm with the user first." ;;
esac

if printf '%s' "$lower" | grep -Eq '(curl|http).*qdrant.*collections/[a-z0-9_-]+.*-x *delete'; then
  deny "dropping a Qdrant collection is destructive — confirm with the user first."
fi

if printf '%s' "$lower" | grep -Eq '\bk6\b.*\brun\b'; then
  if ! printf '%s' "$lower" | grep -Eq 'localhost|127\.0\.0\.1|backend:8000|host\.docker\.internal'; then
    deny "k6 run targeting a non-local host — confirm the target with the user first."
  fi
fi

exit 0
