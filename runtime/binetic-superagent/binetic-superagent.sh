#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]}"
while [ -L "$SOURCE_PATH" ]; do
  LINK_TARGET="$(readlink "$SOURCE_PATH")"
  case "$LINK_TARGET" in
    /*) SOURCE_PATH="$LINK_TARGET" ;;
    *) SOURCE_PATH="$(dirname "$SOURCE_PATH")/$LINK_TARGET" ;;
  esac
done
SELF_DIR="$(cd "$(dirname "$SOURCE_PATH")" && pwd)"
BINETIC_AGENT_BIN="${BINETIC_BINETIC_AGENT_BIN:-/root/agent-workspace/bin/binetic-agent}"
PROMPT_FILE="${SELF_DIR}/BINETIC_SYSTEM_PROMPT.md"
STATE_DIR="${BINETIC_SUPERAGENT_STATE:-${SELF_DIR}/state}"
BPCM_STATE_DIR="${BINETIC_BPCM_STATE:-${SELF_DIR}/bpcm_state}"
mkdir -p "$STATE_DIR" "$BPCM_STATE_DIR"

has_provider() {
  env | grep -Eq '^(ANTHROPIC_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|OPENROUTER_API_KEY|GROQ_API_KEY|HF_TOKEN|VERTEXAI_PROJECT|AWS_ACCESS_KEY_ID)=' \
    || [ -f "$HOME/.config/binetic-agent/binetic-agent.json" ] \
    || [ -f "$HOME/.config/binetic-agent/binetic-agentrc" ] \
    || [ -f "$HOME/.config/binetic_agent/binetic-agent.json" ] \
    || [ -f "$HOME/.config/binetic_agent/binetic-agentrc" ] \
    || [ -f "$HOME/.config/klash/klash.json" ] \
    || [ -f "$HOME/.config/klash/klashrc" ]
}

case "${1:-run}" in
  status)
    cat <<EOF
{"name":"binetic-superagent","version":"0.2.0","binetic-agent":"$BINETIC_AGENT_BIN","prompt":"$PROMPT_FILE","stateDir":"$STATE_DIR","bpcmStateDir":"$BPCM_STATE_DIR","receipts":"$STATE_DIR/receipts.jsonl","bpcm":"$BPCM_STATE_DIR/bpcm.jsonl","offlineFallback":true}
EOF
    ;;
  run)
    shift || true
    if ! has_provider; then
      exec python3 "${SELF_DIR}/binetic_local_plan.py" "$@"
    fi
    exec "$BINETIC_AGENT_BIN" --append-system-prompt-file "$PROMPT_FILE" "$@"
    ;;
  cognition)
    shift || true
    exec python3 "${SELF_DIR}/bpcm.py" --state-dir "$BPCM_STATE_DIR" "$@"
    ;;
  cognition-test)
    exec python3 "${SELF_DIR}/tests/test_bpcm.py"
    ;;
  doctor)
    shift || true
    exec "$BINETIC_AGENT_BIN" doctor "$@"
    ;;
  memory)
    shift || true
    exec "$BINETIC_AGENT_BIN" mem "$@"
    ;;
  verify)
    exec python3 "${SELF_DIR}/verify_receipts.py" "$STATE_DIR/receipts.jsonl"
    ;;
  receipt)
    shift || true
    exec python3 "${SELF_DIR}/receipt_cli.py" "$@"
    ;;
  *)
    echo "Usage: binetic-superagent {run|status|doctor|memory|verify|receipt|cognition|cognition-test}" >&2
    exit 2
    ;;
esac
