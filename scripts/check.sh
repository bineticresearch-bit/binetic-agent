#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m py_compile "$ROOT"/runtime/binetic-superagent/*.py
node --check "$ROOT/runtime/binetic-superagent/mac_model_proxy.mjs"
python3 - <<'PY'
import json
json.load(open('/root/agent-workspace/binetic-agent-creator/runtime/binetic-superagent/binetic-agent.json'))
print('config json ok')
PY
echo 'checks ok'
