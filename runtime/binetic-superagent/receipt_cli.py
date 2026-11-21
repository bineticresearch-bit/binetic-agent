#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_STATE = Path("/root/agent-workspace/binetic-superagent/state")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_chain(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_no}: {exc}")
            rows.append(row)
    return rows


def append_receipt(args: argparse.Namespace) -> None:
    path = Path(args.state) / "receipts.jsonl" if args.state else DEFAULT_STATE / "receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    chain = load_chain(path)
    prev_hash = chain[-1]["body_hash"] if chain else "0" * 64
    body: dict[str, Any] = {
        "version": 4,
        "kind": args.kind,
        "seq": len(chain),
        "route_id": args.route,
        "vport_id": args.vport,
        "model_id": args.model_id,
        "layer_id": args.layer_id,
        "block_id": args.block_id,
        "op_code": args.op_code,
        "input_hash": args.input_hash,
        "output_hash": args.output_hash,
        "state_before": args.state_before or prev_hash,
        "state_after": args.state_after or sha256_hex(canonical_json({
            "payload": args.payload,
            "input_hash": args.input_hash,
            "output_hash": args.output_hash,
        })),
        "payload": args.payload,
    }
    body_hash = sha256_hex(canonical_json(body))
    receipt = {"body": body, "prev_hash": prev_hash, "body_hash": body_hash}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"appended": True, "seq": body["seq"], "body_hash": body_hash, "path": str(path)}, sort_keys=True))


def verify_chain_path(path: Path) -> dict[str, Any]:
    chain = load_chain(path)
    issues: list[str] = []
    prev_hash = "0" * 64
    for index, receipt in enumerate(chain):
        body = receipt.get("body")
        if not isinstance(body, dict):
            issues.append(f"{index}: missing body")
            continue
        if sha256_hex(canonical_json(body)) != receipt.get("body_hash"):
            issues.append(f"{index}: body_hash mismatch")
        if receipt.get("prev_hash") != prev_hash:
            issues.append(f"{index}: prev_hash mismatch")
        if body.get("seq") != index:
            issues.append(f"{index}: seq mismatch")
        prev_hash = receipt.get("body_hash", prev_hash)
    return {
        "count": len(chain),
        "valid": not issues,
        "issues": issues,
        "chain_root": prev_hash,
        "path": str(path),
    }


def verify_receipts(args: argparse.Namespace) -> None:
    path = Path(args.state) / "receipts.jsonl" if args.state else DEFAULT_STATE / "receipts.jsonl"
    result = verify_chain_path(path)
    print(json.dumps(result, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="binetic-receipt-append")
    parser.add_argument("--state", default=None)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    append = sub.add_parser("append")
    append.add_argument("--kind", default="state")
    append.add_argument("--route", type=int, default=0)
    append.add_argument("--vport", type=int, default=0)
    append.add_argument("--model-id", type=int, default=0)
    append.add_argument("--layer-id", type=int, default=0)
    append.add_argument("--block-id", type=int, default=0)
    append.add_argument("--op-code", type=int, default=0)
    append.add_argument("--input-hash", default="0" * 64)
    append.add_argument("--output-hash", default="0" * 64)
    append.add_argument("--state-before", default=None)
    append.add_argument("--state-after", default=None)
    append.add_argument("--payload", required=True)
    append.set_defaults(func=append_receipt)

    verify = sub.add_parser("verify")
    verify.set_defaults(func=verify_receipts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
