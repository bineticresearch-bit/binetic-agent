#!/usr/bin/env bash
set -euo pipefail

# Main Binetic Superagent interface: Binetic Agent TUI.
# Bootstraps controls, trusts the native config, then launches Binetic Agent.

export PATH="/root/agent-workspace/bin:$PATH"
export BINETIC_MAIN_INTERFACE="binetic-agent-tui"

python3 /root/agent-workspace/binetic-superagent/binetic-cockpit.py bootstrap >/tmp/binetic-bootstrap.json || true

exec /root/agent-workspace/bin/binetic-agent \
  --cwd /root/agent-workspace/binetic-superagent \
  --append-system-prompt-file /root/agent-workspace/binetic-superagent/BINETIC_SYSTEM_PROMPT.md \
  "$@"
