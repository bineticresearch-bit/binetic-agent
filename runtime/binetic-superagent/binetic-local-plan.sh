#!/usr/bin/env bash
set -euo pipefail

# Tiny offline planner used when no model provider is configured.
# It exercises the same receipt discipline and shared-memory protocol without
# pretending to call an LLM.
SOURCE_PATH="${BASH_SOURCE[0]}"
while [ -L "$SOURCE_PATH" ]; do
  LINK_TARGET="$(readlink "$SOURCE_PATH")"
  case "$LINK_TARGET" in
    /*) SOURCE_PATH="$LINK_TARGET" ;;
    *) SOURCE_PATH="$(dirname "$SOURCE_PATH")/$LINK_TARGET" ;;
  esac
done
SELF_DIR="$(cd "$(dirname "$SOURCE_PATH")" && pwd)"
PROMPT="${*:-no prompt}"
HASH="$(printf '%s' "$PROMPT" | sha256sum | cut -d' ' -f1)"

echo "BINETIC LOCAL PLAN"
echo "prompt_hash=$HASH"
echo "no LLM provider configured; running deterministic offline plan"
echo
echo "1. Decompose intent into explicit todos in Binetic Agent mem."
echo "2. Enter work with mem.Push, verify with executable checks, exit with mem.Pop."
echo "3. Append a receipt for every accepted state transition."
echo "4. Verify the receipt chain before claiming completion."
echo
echo "Suggested Gno mem calls:"
cat <<'EOF'
root := mem.Todo("binetic superagent task")
root.Todo("read and symbolize intent")
root.Todo("execute with evidence")
root.Todo("verify receipts and report")
mem.Frame(root.Name()).Push()
EOF
echo
echo "Run: binetic-receipt-append append --kind result --payload '{\"prompt_hash\":\"$HASH\",\"mode\":\"offline\"}' && binetic-verify-receipts"
