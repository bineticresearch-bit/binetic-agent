#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/binetic-fast-infer.log
PIDFILE=/tmp/binetic-fast-infer.pid
PORT="${PORT:-8641}"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "binetic-fast-infer already running pid=$(cat "$PIDFILE")"
  exit 0
fi

PORT="$PORT" nohup /root/agent-workspace/binetic-superagent/binetic-fast-infer.sh >"$LOG" 2>&1 &
echo $! >"$PIDFILE"
for i in $(seq 1 30); do
  if curl -sS --max-time 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "binetic-fast-infer ready pid=$(cat "$PIDFILE") port=$PORT log=$LOG"
    exit 0
  fi
  sleep 1
done
echo "binetic-fast-infer failed to become ready; see $LOG" >&2
exit 1
