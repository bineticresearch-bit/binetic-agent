#!/usr/bin/env bash
set -euo pipefail

# Cooperative live-view Binetic Agent launcher.
# Starts Binetic Agent in a script(1) terminal recording so I can inspect the live pane
# via the transcript file. This captures the terminal stream, not your Mac screen.
export PATH="/root/agent-workspace/bin:$PATH"
ROOT=/root/agent-workspace/binetic-superagent
VIEW="$ROOT/live_view"
mkdir -p "$VIEW"
chmod 700 "$VIEW"

LOG="$VIEW/binetic-agent_live.log"
: >"$LOG"
chmod 600 "$LOG"

python3 "$ROOT/binetic-cockpit.py" bootstrap >/tmp/binetic-bootstrap.json || true

exec script -qfec "stty -echo; export PATH='/root/agent-workspace/bin:$PATH'; exec /root/agent-workspace/bin/binetic-binetic-agent" "$LOG"
