#!/usr/bin/env bash
set -euo pipefail

# Native Binetic packet benchmarks.
NATIVE=/root/agent-workspace/binetic-superagent/native
python3 /root/agent-workspace/binetic-superagent/binetic_kv.py bench --n "${ROUTE_N:-20000000}" --rounds "${ROUNDS:-5}"
"$NATIVE/bpcm_kv_simd" "${FOLD_ROWS:-100000}" "${FOLD_BYTES:-512}" "${ROUNDS:-5}"
"$NATIVE/bpcm_kv_hash" "${CRC_ROWS:-100000}" "${CRC_BYTES:-512}" "${ROUNDS:-5}"
