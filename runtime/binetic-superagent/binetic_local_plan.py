#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys

prompt = " ".join(sys.argv[1:]) or "no prompt"
digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

print(json.dumps({
    "mode": "offline_plan_v1",
    "message": "No provider key is configured; running a deterministic local plan without network or model claims.",
    "prompt_hash": digest,
    "todos": [
        {"name": "symbolize-intent", "status": "ready"},
        {"name": "execute-with-evidence", "status": "blocked_by_model_provider"},
        {"name": "verify-receipt-chain", "status": "ready_local"},
    ],
    "binetic-agent_mem_program": [
        'root := mem.Todo("binetic superagent task")',
        'root.Todo("read and symbolize intent")',
        'root.Todo("execute with evidence")',
        'root.Todo("verify receipts and report")',
        'mem.Frame(root.Name()).Push()',
    ],
    "next_command": (
        "binetic-receipt-append append --kind result "
        f"--payload '{{\"prompt_hash\":\"{digest}\",\"mode\":\"offline\"}}' && binetic-verify-receipts"
    ),
}, indent=2))
