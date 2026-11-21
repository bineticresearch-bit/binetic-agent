#!/usr/bin/env bash
set -euo pipefail

# Packetized KV proxy: exact-mode OpenAI-compatible forwarder on 127.0.0.1:8646.
# Upstream 127.0.0.1:8645 is the existing model forwarder. No model load/GPU
# operation is performed here.

LOG=/tmp/binetic-kv-proxy.log
PIDFILE=/tmp/binetic-kv-proxy.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "binetic-kv-proxy already running pid=$(cat "$PIDFILE")"
  exit 0
fi

nohup python3 /root/agent-workspace/binetic-superagent/binetic_kv.py proxy \
  --upstream http://127.0.0.1:8645 \
  --listen 127.0.0.1 \
  --port 8646 >"$LOG" 2>&1 &
echo $! >"$PIDFILE"
sleep 1
echo "binetic-kv-proxy started pid=$! port=8646 log=$LOG"
