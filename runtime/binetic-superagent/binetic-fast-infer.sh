#!/usr/bin/env bash
set -euo pipefail

# Fast Binetic inference server.
# Uses llama.cpp server with separate batch (prefill) and decode thread counts.
# Defaults chosen from measured sweep on this 32-core Apple VM:
#   prefill threads 16  (~552 tok/s on Qwen2.5-0.5B-Q8 short prompt)
#   decode threads 10   (~127 tok/s on the same model)
# The packetized KV proxy on 8646 remains the Binetic Agent-facing endpoint when used.

MODEL="${MODEL:-/root/agent-workspace/models/Qwen2.5-0.5B-Instruct-Q8_0.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/root/agent-workspace/llama.cpp/build-binet/bin/llama-server}"
PORT="${PORT:-8645}"
HOST="${HOST:-127.0.0.1}"
CTX="${CTX:-512}"
TB="${TB:-16}"
T="${T:-10}"
SLOTS="${SLOTS:-1}"

if [ ! -x "$LLAMA_SERVER" ]; then
  echo "missing llama-server: $LLAMA_SERVER" >&2
  exit 2
fi
if [ ! -s "$MODEL" ]; then
  echo "missing model: $MODEL" >&2
  exit 2
fi

exec "$LLAMA_SERVER" \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --threads "$T" \
  --threads-batch "$TB" \
  --parallel "$SLOTS" \
  --no-webui
