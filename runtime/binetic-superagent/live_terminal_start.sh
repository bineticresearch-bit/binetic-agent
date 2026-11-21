#!/usr/bin/env bash
set -euo pipefail

# Start/restart the persistent live terminal tmux session.
SESSION="${BINETIC_LIVE_SESSION:-binetic-live}"
ROOT=/root/agent-workspace/binetic-superagent
BIN=/root/agent-workspace/bin
PY="$ROOT/live_action_terminal.py"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  if [ "${BINETIC_LIVE_RESTART:-0}" = "1" ]; then
    tmux kill-session -t "$SESSION"
  else
    echo "session already running: $SESSION"
    echo "attach: tmux attach -t $SESSION"
    exit 0
  fi
fi

mkdir -p "$ROOT/live_view"
chmod 700 "$ROOT/live_view"
tmux new-session -d -s "$SESSION" -x 180 -y 50 \
  "bash -lc 'export PATH=$BIN:\$PATH; exec python3 "$PY"'"

echo "live terminal session started: $SESSION"
echo "attach: tmux attach -t $SESSION"
echo "detach: Ctrl-b d"
