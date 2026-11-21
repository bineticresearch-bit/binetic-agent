#!/usr/bin/env bash
set -euo pipefail

# Start bounded Binetic AGI self-improvement loop as a local supervised process.
# Safe-by-construction: calls only binetic-agi-kernel/evolve_agi and receipts.
ROOT=/root/agent-workspace/binetic-superagent
LOG=/tmp/binetic-agi-loop.log
PID=/tmp/binetic-agi-loop.pid
INTERVAL="${BINETIC_AGI_INTERVAL:-300}"

if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  echo "agi-loop already running pid=$(cat "$PID")"
  exit 0
fi

nohup bash -lc "while true; do python3 '$ROOT/evolve_agi.py' --cycles 2 >>'$LOG' 2>&1; sleep '$INTERVAL'; done" >/dev/null 2>&1 &
echo $! >"$PID"
echo "agi-loop started pid=$(cat "$PID") interval=${INTERVAL}s log=$LOG"
