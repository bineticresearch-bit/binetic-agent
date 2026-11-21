#!/usr/bin/env bash
set -euo pipefail

# Start Binetic Free Fabric + echo phase-lock oracle in network-in-motion mode.
ROOT=/root/agent-workspace/binetic-superagent
FABRIC_LOG=/tmp/bff-fabric.log
FABRIC_PID=/tmp/bff-fabric.pid
ORACLE_LOG=/tmp/bff-echo-oracle.log
ORACLE_PID=/tmp/bff-echo-oracle.pid

start_one() {
  name="$1"; pidfile="$2"; log="$3"; shift 3
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "$name already running pid=$(cat "$pidfile")"
    return
  fi
  nohup python3 "$@" >"$log" 2>&1 &
  echo $! >"$pidfile"
  echo "$name started pid=$(cat "$pidfile") log=$log"
}

start_one fabric "$FABRIC_PID" "$FABRIC_LOG" "$ROOT/bff_fabric.py" serve --host 0.0.0.0 --port 8650
start_one echo-oracle "$ORACLE_PID" "$ORACLE_LOG" "$ROOT/echo_phase_lock.py" serve --host 0.0.0.0 --port 8651

for i in $(seq 1 20); do
  if curl -sS --max-time 1 http://127.0.0.1:8650/fabric/status >/dev/null 2>&1 \
     && curl -sS --max-time 1 http://127.0.0.1:8651/echo/oracle >/dev/null 2>&1; then
    echo "free-fabric ready"
    exit 0
  fi
  sleep 1
done
echo "free-fabric failed readiness; logs: $FABRIC_LOG $ORACLE_LOG" >&2
exit 1
