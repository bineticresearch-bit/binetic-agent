#!/usr/bin/env bash
set -euo pipefail

# Starts the evolved best real inference configuration from tuner_state.
STATE=/root/agent-workspace/binetic-superagent/tuner_state/best_config.json
LLAMA_SERVER="${LLAMA_SERVER:-/root/agent-workspace/llama.cpp/build-binet/bin/llama-server}"
PORT="${PORT:-8641}"
HOST="${HOST:-127.0.0.1}"
SLOTS="${SLOTS:-1}"

if [ ! -s "$STATE" ]; then
  echo "missing evolved config: $STATE" >&2
  exit 2
fi
if [ ! -x "$LLAMA_SERVER" ]; then
  echo "missing llama-server: $LLAMA_SERVER" >&2
  exit 2
fi

CFG=$(python3 - "$STATE" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); c=d['config']
print('\t'.join(str(c[k]) for k in ['model','threads','threads_batch','ctx','n_batch']))
PY
)
IFS=$'\t' read -r MODEL T TB CTX NBATCH <<<"$CFG"

exec "$LLAMA_SERVER" \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --batch-size "$NBATCH" \
  --threads "$T" \
  --threads-batch "$TB" \
  --parallel "$SLOTS" \
  --no-webui
