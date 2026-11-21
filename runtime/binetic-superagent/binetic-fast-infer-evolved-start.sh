#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/binetic-fast-infer-evolved.log
PIDFILE=/tmp/binetic-fast-infer-evolved.pid
PORT="${PORT:-8641}"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "evolved infer already running pid=$(cat "$PIDFILE")"
  exit 0
fi

PORT="$PORT" nohup /root/agent-workspace/binetic-superagent/binetic-fast-infer-evolved.sh >"$LOG" 2>&1 &
echo $! >"$PIDFILE"
for i in $(seq 1 60); do
  if curl -sS --max-time 1 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    echo "evolved infer ready pid=$(cat "$PIDFILE") port=$PORT log=$LOG"
    exit 0
  fi
  sleep 1
done
echo "evolved infer failed to become ready; see $LOG" >&2
exit 1
