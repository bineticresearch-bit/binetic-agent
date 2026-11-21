#!/usr/bin/env bash
set -euo pipefail

# Friendly alias for Binetic local/offline planning.
# Usage:
#   binetic-local "goal or prompt"
#   binetic-local status
#   binetic-local --help
#
# For a literal CLI status, this delegates to binetic-cockpit status.
# Everything else is treated as an offline planning prompt.

export PATH="/root/agent-workspace/bin:$PATH"
ROOT=/root/agent-workspace/binetic-superagent
PLAN_PY="$ROOT/binetic_local_plan.py"

case "${1:-}" in
  "")
    echo "binetic-local: missing prompt" >&2
    echo "usage: binetic-local \"goal or prompt\" | status | --help" >&2
    exit 2
    ;;
  -h|--help|help)
    cat <<'EOF'
binetic-local — Binetic offline/local planner alias

Usage:
  binetic-local "build a local plan for X"
  binetic-local status
  binetic-local --help

Notes:
  No provider key, no network, no model claim.
  Emits deterministic offline plan JSON.
EOF
    exit 0
    ;;
  status)
    exec /root/agent-workspace/bin/binetic-cockpit status
    ;;
  *)
    exec python3 "$PLAN_PY" "$@"
    ;;
esac
