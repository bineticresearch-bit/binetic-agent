#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from receipt_cli import verify_chain_path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/root/agent-workspace/binetic-superagent/state/receipts.jsonl")
result = verify_chain_path(path)
print(json.dumps(result, sort_keys=True))
if not result["valid"]:
    raise SystemExit(1)
