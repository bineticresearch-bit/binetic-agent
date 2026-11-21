#!/usr/bin/env bash
set -uo pipefail

# Run a command while showing my intent and result in the live action terminal.
# Usage: binetic-act "intent text" bash -lc 'command'
ROOT=/root/agent-workspace/binetic-superagent
LOG="$ROOT/live_action_log.sh"
INTENT="${1:-action}"
shift || true
if [ "$#" -eq 0 ]; then
  echo 'usage: binetic-act "intent text" command args...' >&2
  exit 2
fi
"$LOG" "ACT   │ $INTENT"
START="$(date +%s%3N)"
"$@"
RC=$?
END="$(date +%s%3N)"
MS=$((END-START))
"$LOG" "DONE  │ $INTENT │ exit=$RC │ ${MS}ms"
exit "$RC"
