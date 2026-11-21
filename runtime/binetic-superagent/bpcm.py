#!/usr/bin/env python3
"""B-PCM v4 — Revealed Extended Canonical Packet Machine.

Dependency-free, deterministic cognition packet kernel. This is a deliberate
rewrite from v1: envelope receipts, byte-level bit packets, in-band tool
receipts, packet-root state references, and full output envelopes.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from bpcm_packet import Packet64, canonical_json, masks, pack_bytes, pack_json, pack_routing, sha256_hex

VERSION = 4
HASH_BITS = 256
BYTES_PER_HASH = HASH_BITS // 8
ZERO_HASH = "0" * 64
OPCODE = {
    "H1": "PACKET_DELTA", "20": "COLLAPSE", "30": "BROADCAST",
    "55": "WRITE", "AA": "READ", "FF": "SYNC",
}
UCODES = {"AGI_STEP", "AGI_TOOL", "AGI_COMMIT", "AGI_POLICY"}
REQUIRES_FRAME = {"MEM_FACT_SET", "FRAME_POP", "TOOL_CALL", "TOOL_RESULT"}
OPS = {
    "INTENT_OPEN", "MEM_TODO_ADD", "FRAME_PUSH", "FRAME_POP",
    "TOOL_CALL", "TOOL_RESULT", "MEM_FACT_SET",
    "SWARM_TODO_CLAIM", "SWARM_TODO_DONE", "SWARM_TODO_RELEASE",
    "POLICY_PROPOSE", "POLICY_VERIFY", "POLICY_ADMIT", "POLICY_REJECT",
    "FINAL_CLAIM",
}


def h(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def require(condition: bool, issues: list[str], message: str) -> None:
    if not condition:
        issues.append(message)


def packet_body(body: dict[str, Any], state_before: str, state_after: str, *, payload_bytes: bytes | None = None) -> dict[str, Any]:
    """Every output carries the same base envelope, regardless of source."""
    payload = payload_bytes or canonical_json(body)
    envelope = {
        "version": VERSION,
        "kind": "packet",
        "op": body.get("op", "FRAME_PACKET"),
        "state_before": state_before,
        "state_after": state_after,
        "payload_length": len(payload),
        "payload_sha256": sha256_hex(payload),
        "base": {
            "words": 4,
            "bw": BYTES_PER_HASH,
            "routing_qwords": [q for packet in pack_routing(0, 0, 0, 0, 0, 0) for q in packet.qwords()],
        },
        "route_id": body.get("route_id", 0),
        "vport_id": body.get("vport_id", 0),
        "model_id": body.get("model_id", 0),
        "layer_id": body.get("layer_id", 0),
        "block_id": body.get("block_id", 0),
        "op_code": body.get("op_code", 0),
    }
    envelope["packet_hash"] = h(envelope)
    return envelope


def accepted_receipt(command: str, receipt_ref: str) -> dict[str, Any]:
    tool = {
        "id": f"tool-{sha256_hex(command.encode())[:16]}",
        "input": command,
        "output": {"status": "accepted", "source": "binetic-agent/tool"},
        "bits": pack_json({"command": command, "status": "accepted", "ref": receipt_ref}, op_code=int("55", 16)),
    }
    tool["receipt"] = h(tool)
    return tool


@dataclass
class State:
    intent: dict[str, Any] | None = None
    todos: dict[str, dict[str, Any]] | None = None
    todo_order: list[str] | None = None
    facts: dict[str, dict[str, Any]] | None = None
    fact_order: list[str] | None = None
    stack: list[str] | None = None
    frame_events: list[dict[str, Any]] | None = None
    tool_calls: dict[str, dict[str, Any]] | None = None
    tool_results: dict[str, dict[str, Any]] | None = None
    tool_order: list[str] | None = None
    tool_receipts: dict[str, dict[str, Any]] | None = None
    swarm_leases: dict[str, dict[str, Any]] | None = None
    policy_proposals: dict[str, dict[str, Any]] | None = None
    policy_verifies: dict[str, dict[str, Any]] | None = None
    policy_decisions: list[dict[str, Any]] | None = None
    admitted_policies: set[str] | None = None
    final_claims: list[dict[str, Any]] | None = None
    receipt_hashes: list[str] | None = None

    def __post_init__(self) -> None:
        self.todos = self.todos if self.todos is not None else {}
        self.todo_order = self.todo_order if self.todo_order is not None else []
        self.facts = self.facts if self.facts is not None else {}
        self.fact_order = self.fact_order if self.fact_order is not None else []
        self.stack = self.stack if self.stack is not None else []
        self.frame_events = self.frame_events if self.frame_events is not None else []
        self.tool_calls = self.tool_calls if self.tool_calls is not None else {}
        self.tool_results = self.tool_results if self.tool_results is not None else {}
        self.tool_order = self.tool_order if self.tool_order is not None else []
        self.tool_receipts = self.tool_receipts if self.tool_receipts is not None else {}
        self.swarm_leases = self.swarm_leases if self.swarm_leases is not None else {}
        self.policy_proposals = self.policy_proposals if self.policy_proposals is not None else {}
        self.policy_verifies = self.policy_verifies if self.policy_verifies is not None else {}
        self.policy_decisions = self.policy_decisions if self.policy_decisions is not None else []
        self.admitted_policies = self.admitted_policies if self.admitted_policies is not None else set()
        self.final_claims = self.final_claims if self.final_claims is not None else []
        self.receipt_hashes = self.receipt_hashes if self.receipt_hashes is not None else []

    def root(self) -> str:
        return h(self.projection())

    def projection(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "todos": self.todos, "todo_order": self.todo_order,
            "facts": self.facts, "fact_order": self.fact_order,
            "stack": self.stack, "frame_events": self.frame_events,
            "tool_calls": self.tool_calls, "tool_results": self.tool_results,
            "tool_order": self.tool_order, "tool_receipts": self.tool_receipts,
            "swarm_leases": self.swarm_leases,
            "policy_proposals": self.policy_proposals, "policy_verifies": self.policy_verifies,
            "policy_decisions": self.policy_decisions, "admitted_policies": sorted(self.admitted_policies),
            "final_claims": self.final_claims, "receipt_hashes": self.receipt_hashes,
        }


def descendants_open(state: State, todo_id: str) -> list[str]:
    out: list[str] = []
    frontier = [todo_id]
    while frontier:
        current = frontier.pop()
        for tid, todo in (state.todos or {}).items():
            if todo.get("parent") == current and todo.get("status") != "done":
                out.append(tid)
                frontier.append(tid)
    return out


def has_evidence(state: State, evidence: Any) -> bool:
    if not isinstance(evidence, list) or not evidence:
        return False
    known = set((state.tool_results or {}).keys()) | set((state.facts or {}).keys()) | set(state.receipt_hashes or []) | set((state.tool_receipts or {}).keys())
    return all(isinstance(item, str) and item in known for item in evidence)


def apply_event(state: State, body: dict[str, Any], receipt_ref: str, issues: list[str], index: int) -> None:
    op = body.get("op")
    payload = body.get("payload") or {}
    actor = body.get("actor") or payload.get("actor") or "system"

    if op != "INTENT_OPEN" and state.intent is None:
        require(False, issues, f"{index}: {op} before INTENT_OPEN")
    if op in REQUIRES_FRAME and not state.stack:
        require(False, issues, f"{index}: {op} requires active frame")

    if op == "INTENT_OPEN":
        require(index == 0, issues, f"{index}: INTENT_OPEN must be first")
        state.intent = {"intent": payload.get("intent"), "actor": actor, "metadata": payload.get("metadata", {})}
    elif op == "MEM_TODO_ADD":
        tid = payload.get("id")
        require(isinstance(tid, str) and bool(tid), issues, f"{index}: todo id missing")
        if tid and tid not in state.todos:
            state.todos[tid] = {"id": tid, "parent": payload.get("parent"), "title": payload.get("title") or tid, "status": "open"}
            state.todo_order.append(tid)
        else:
            require(False, issues, f"{index}: duplicate todo {tid}")
    elif op == "FRAME_PUSH":
        tid = payload.get("todo_id")
        require(tid in state.todos, issues, f"{index}: unknown frame todo")
        if tid in state.todos and tid not in state.stack:
            state.stack.append(tid)
            state.frame_events.append({"action": "push", "todo_id": tid, "actor": actor, "receipt": receipt_ref})
    elif op == "FRAME_POP":
        tid = payload.get("todo_id")
        require(bool(state.stack) and state.stack[-1] == tid, issues, f"{index}: pop must close top frame")
        open_children = descendants_open(state, tid) if isinstance(tid, str) else []
        require(not open_children, issues, f"{index}: cannot pop with open children")
        unmatched = [cid for cid, call in (state.tool_calls or {}).items() if call.get("frame") == tid and not call.get("result_received")]
        require(not unmatched, issues, f"{index}: cannot pop with unmatched tool calls")
        if state.stack and state.stack[-1] == tid:
            state.stack.pop()
            state.todos[tid]["status"] = "done"
            state.todos[tid]["result"] = payload.get("result", "")
            state.todos[tid]["evidence"] = payload.get("evidence", [])
            state.frame_events.append({"action": "pop", "todo_id": tid, "actor": actor, "receipt": receipt_ref})
    elif op == "TOOL_CALL":
        cid = payload.get("call_id")
        require(isinstance(cid, str) and bool(cid), issues, f"{index}: call_id missing")
        if cid and cid not in state.tool_calls:
            state.tool_calls[cid] = {
                "call_id": cid, "tool": payload.get("tool"),
                "input_hash": payload.get("input_hash") or h(payload.get("input", {})),
                "actor": actor, "frame": state.stack[-1] if state.stack else None,
                "result_received": False,
            }
    elif op == "TOOL_RESULT":
        cid = payload.get("call_id")
        require(cid in state.tool_calls, issues, f"{index}: unknown tool call")
        if cid in state.tool_calls:
            state.tool_calls[cid]["result_received"] = True
            state.tool_results[cid] = {
                "call_id": cid, "tool": state.tool_calls[cid]["tool"],
                "output_hash": payload.get("output_hash") or h(payload.get("output", {})),
                "summary": payload.get("summary", ""), "actor": actor,
                "frame": state.stack[-1] if state.stack else None, "receipt": receipt_ref,
            }
            state.tool_order.append(cid)
            # v4: in-band tool receipt with typed ucode + byte-level bit packet.
            state.tool_receipts[cid] = accepted_receipt(shlex_join_tool(state.tool_calls[cid]), receipt_ref)
    elif op == "MEM_FACT_SET":
        name = payload.get("name")
        require(isinstance(name, str) and bool(name), issues, f"{index}: fact name missing")
        require(has_evidence(state, payload.get("evidence")), issues, f"{index}: fact evidence unsupported")
        if name in state.facts:
            revision = state.facts[name]["revision"] + 1
        else:
            revision = 1
            state.fact_order.append(name)
        state.facts[name] = {"name": name, "value": payload.get("value"), "evidence": payload.get("evidence", []), "actor": actor, "revision": revision, "receipt": receipt_ref}
    elif op == "SWARM_TODO_CLAIM":
        tid = payload.get("todo_id")
        require(tid in state.todos, issues, f"{index}: swarm todo missing")
        require(tid not in state.swarm_leases, issues, f"{index}: todo already leased")
        state.swarm_leases[tid] = {"actor": actor, "status": "active", "receipt": receipt_ref}
    elif op == "SWARM_TODO_DONE":
        tid = payload.get("todo_id")
        lease = state.swarm_leases.get(tid)
        require(lease and lease.get("status") == "active" and lease.get("actor") == actor, issues, f"{index}: no valid lease")
        require(has_evidence(state, payload.get("evidence")), issues, f"{index}: swarm evidence unsupported")
        if lease and lease.get("status") == "active" and lease.get("actor") == actor:
            lease["status"] = "done"
            state.todos[tid]["status"] = "done"
            state.todos[tid]["evidence"] = payload.get("evidence", [])
    elif op == "SWARM_TODO_RELEASE":
        tid = payload.get("todo_id")
        lease = state.swarm_leases.get(tid)
        require(lease and lease.get("status") == "active" and lease.get("actor") == actor, issues, f"{index}: no valid lease")
        if lease and lease.get("status") == "active":
            lease["status"] = "released"
    elif op == "POLICY_PROPOSE":
        pid = payload.get("proposal_id")
        require(isinstance(pid, str) and bool(pid), issues, f"{index}: proposal id missing")
        state.policy_proposals[pid] = {"proposal_id": pid, "patch": payload.get("patch", {}), "actor": actor}
    elif op == "POLICY_VERIFY":
        pid = payload.get("proposal_id")
        require(pid in state.policy_proposals, issues, f"{index}: unknown proposal")
        state.policy_verifies[pid] = {
            "proposal_id": pid, "baseline_score": payload.get("baseline_score", 0),
            "champion_score": payload.get("champion_score", 0),
            "invariant_violations": payload.get("invariant_violations", []), "actor": actor,
        }
    elif op in {"POLICY_ADMIT", "POLICY_REJECT"}:
        pid = payload.get("proposal_id")
        verify = state.policy_verifies.get(pid)
        require(verify is not None, issues, f"{index}: policy decision before verify")
        if verify:
            winner = float(verify.get("champion_score", 0)) > float(verify.get("baseline_score", 0))
            clean = not verify.get("invariant_violations")
            if op == "POLICY_ADMIT":
                require(winner and clean, issues, f"{index}: unsafe admit")
            elif winner and clean:
                require(False, issues, f"{index}: winning clean patch must be admitted")
        state.policy_decisions.append({"decision": op, "proposal_id": pid, "actor": actor, "receipt": receipt_ref})
        if op == "POLICY_ADMIT" and verify and float(verify.get("champion_score", 0)) > float(verify.get("baseline_score", 0)) and not verify.get("invariant_violations"):
            state.admitted_policies.add(pid)
    elif op == "FINAL_CLAIM":
        claim = payload.get("claim")
        require(isinstance(claim, str) and bool(claim), issues, f"{index}: claim missing")
        require(not state.stack, issues, f"{index}: final claim with open frames")
        require(has_evidence(state, payload.get("evidence")), issues, f"{index}: claim evidence unsupported")
        state.final_claims.append({"claim": claim, "evidence": payload.get("evidence", []), "actor": actor, "receipt": receipt_ref})
    else:
        require(False, issues, f"{index}: unhandled op {op}")
    state.receipt_hashes.append(receipt_ref)


def shlex_join_tool(call: dict[str, Any]) -> str:
    parts = [str(call.get("tool", "")), str(call.get("input_hash", ""))]
    return " ".join(parts)


def validate_envelope(receipt: dict[str, Any], index: int, issues: list[str], prev: str) -> dict[str, Any] | None:
    body = receipt.get("body")
    require(isinstance(body, dict), issues, f"{index}: missing body")
    if not isinstance(body, dict):
        return None
    require(body.get("version") == VERSION, issues, f"{index}: unsupported version")
    require(body.get("seq") == index, issues, f"{index}: seq mismatch")
    require(receipt.get("prev_hash") == prev, issues, f"{index}: prev_hash mismatch")
    body_hash = receipt.get("body_hash", "")
    require(isinstance(body_hash, str) and body_hash.startswith("bpcm4:"), issues, f"{index}: invalid body_hash envelope")
    envelope = receipt.get("envelope")
    require(isinstance(envelope, dict), issues, f"{index}: missing output envelope")
    if isinstance(envelope, dict):
        require(envelope.get("packet_hash") == body_hash.split(":", 1)[1], issues, f"{index}: envelope hash mismatch")
        require(envelope.get("state_before") == body.get("state_before"), issues, f"{index}: envelope state_before mismatch")
        require(envelope.get("state_after") == body.get("state_after"), issues, f"{index}: envelope state_after mismatch")
        require(envelope.get("op") == body.get("op"), issues, f"{index}: envelope op mismatch")
    require(body.get("state_before") is not None and body.get("state_after") is not None, issues, f"{index}: missing packet roots")
    return envelope


def replay(chain: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    state = State()
    prev = ZERO_HASH
    for index, receipt in enumerate(chain):
        envelope = validate_envelope(receipt, index, issues, prev)
        if not envelope:
            continue
        body = receipt["body"]
        require(body.get("state_before") == state.root(), issues, f"{index}: state_before mismatch")
        apply_event(state, body, f"receipt:{index:08d}", issues, index)
        require(body.get("state_after") == state.root(), issues, f"{index}: state_after mismatch")
        prev = envelope["packet_hash"]
    return {"events": len(chain), "valid": not issues, "issues": issues, "state": state, "chain_root": prev, "state_root": state.root(), "chain": chain}


def load_chain(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_chain(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    tmp.replace(path)


def certificate(state: State, chain_root: str, chain: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    chain = chain or []
    cert = {
        "version": VERSION,
        "profile": "extended-canonical-v4",
        "intent_hash": h(state.intent) if state.intent else ZERO_HASH,
        "plan_root": h([state.todos[tid] for tid in state.todo_order]),
        "frame_root": h(state.frame_events),
        "memory_root": h([state.facts[name] for name in state.fact_order]),
        "tool_result_root": h([state.tool_results[cid] for cid in state.tool_order]),
        "tool_receipt_root": h(state.tool_receipts),
        "claim_root": h(state.final_claims),
        "final_state_root": state.root(),
        "chain_root": chain_root,
        "packet_bytes": sum(int((r.get("envelope") or {}).get("payload_length", 0)) for r in chain),
        "l0": True, "l1": True, "l2": True, "l3": True,
        "boundary": "verifies externalized transitions; not hidden reasoning",
    }
    cert["certificate_hash"] = h(cert)
    return cert


def project(state_dir: Path, result: dict[str, Any], cert: dict[str, Any]) -> dict[str, Any]:
    views = state_dir / "views"
    views.mkdir(parents=True, exist_ok=True)
    state: State = result["state"]
    docs = {
        "envelope.json": {"envelope": packet_body({"op": "PROJECTION"}, result["state_root"], result["chain_root"]), "certificate": cert},
        "bit_packets.json": {"sample": pack_bytes(b"BP" + result["chain_root"].encode(), route_id=4, op_code=int("FF", 16)), "masks": masks([Packet64(int(result["chain_root"][i:i+16], 16)) for i in range(0, 64, 16)])},
        "ucodes.json": {"set": sorted(UCODES), "opcodes": OPCODE},
        "todos.json": {"order": state.todo_order, "items": state.todos},
        "facts.json": {"order": state.fact_order, "items": state.facts},
        "frames.json": {"stack": state.stack, "events": state.frame_events},
        "tools.json": {"calls": state.tool_calls, "results": state.tool_results, "receipts": state.tool_receipts},
        "swarm.json": {"leases": state.swarm_leases},
        "policies.json": {"proposals": state.policy_proposals, "verifies": state.policy_verifies, "decisions": state.policy_decisions, "admitted": sorted(state.admitted_policies)},
        "claims.json": {"claims": state.final_claims},
        "certificate.json": cert,
        "workspace.json": state.projection(),
    }
    for name, doc in docs.items():
        (views / name).write_text(json.dumps(doc, sort_keys=True, indent=2), encoding="utf-8")
    return {"views": sorted(docs.keys()), "path": str(views)}


def append_event(state_dir: Path, op: str, payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    path = state_dir / "bpcm.jsonl"
    chain = load_chain(path)
    result = replay(chain)
    if not result["valid"]:
        raise SystemExit("invalid chain: " + "; ".join(result["issues"]))
    state: State = copy.deepcopy(result["state"])
    prev = result["chain_root"]
    seq = len(chain)
    body = {
        "version": VERSION, "kind": "event", "seq": seq, "op": op,
        "actor": actor, "route_id": 4, "vport_id": 1, "model_id": 0,
        "layer_id": 0, "block_id": 0, "op_code": 0x01,
        "ucode": "AGI_STEP", "opcodes": [OPCODE["H1"], OPCODE["55"], OPCODE["FF"]],
        "payload": payload, "state_before": state.root(),
    }
    ref = f"receipt:{seq:08d}"
    issues: list[str] = []
    apply_event(state, body, ref, issues, seq)
    if issues:
        raise SystemExit("append rejected: " + "; ".join(issues))
    body["state_after"] = state.root()
    envelope = packet_body(body, body["state_before"], body["state_after"], payload_bytes=canonical_json(body))
    body_hash = "bpcm4:" + envelope["packet_hash"]
    receipt = {"body": body, "prev_hash": prev, "body_hash": body_hash, "envelope": envelope}
    chain.append(receipt)
    save_chain(path, chain)
    verified = replay(chain)
    cert = certificate(verified["state"], verified["chain_root"], chain)
    projections = project(state_dir, verified, cert)
    return {"seq": seq, "op": op, "valid": verified["valid"], "state_root": verified["state_root"], "chain_root": verified["chain_root"], "envelope": envelope, "projections": projections}


def demo(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "bpcm.jsonl"
    if path.exists():
        path.unlink()
    def ev(op: str, payload: dict[str, Any], actor: str = "creator") -> None:
        append_event(state_dir, op, payload, actor)
    ev("INTENT_OPEN", {"intent": "Demonstrate B-PCM v4 extended canonical packet machine", "metadata": {"profile": "extended-canonical-v4"}})
    ev("MEM_TODO_ADD", {"id": "root", "title": "demonstrate v4"})
    ev("MEM_TODO_ADD", {"id": "packetize", "parent": "root", "title": "bit packets + tool receipts"})
    ev("FRAME_PUSH", {"todo_id": "root"})
    ev("FRAME_PUSH", {"todo_id": "packetize"})
    ev("TOOL_CALL", {"call_id": "c1", "tool": "binetic-agent.tool", "input": {"command": "bitpack"}})
    ev("TOOL_RESULT", {"call_id": "c1", "output_hash": h({"ok": True}), "summary": "tool receipt emitted", "output": {"ok": True}})
    ev("MEM_FACT_SET", {"name": "tool_receipt_valid", "value": True, "evidence": ["c1"]})
    ev("FRAME_POP", {"todo_id": "packetize", "result": "done", "evidence": ["c1"]})
    ev("FRAME_POP", {"todo_id": "root", "result": "done", "evidence": ["tool_receipt_valid"]})
    ev("FINAL_CLAIM", {"claim": "B-PCM v4 produced full envelopes and in-band tool receipts", "evidence": ["c1", "tool_receipt_valid"]})
    return verify_path(path)


def verify_path(path: Path) -> dict[str, Any]:
    chain = load_chain(path)
    result = replay(chain)
    cert = certificate(result["state"], result["chain_root"], chain) if result["valid"] else None
    return {"path": str(path), "profile": "extended-canonical-v4", "events": result["events"], "valid": result["valid"], "issues": result["issues"], "chain_root": result["chain_root"], "state_root": result["state_root"], "certificate": cert}


def main() -> None:
    parser = argparse.ArgumentParser(prog="binetic-cognition-v4")
    parser.add_argument("--state-dir", default="/root/agent-workspace/binetic-superagent/bpcm_state")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    sub.add_parser("verify")
    sub.add_parser("certificate")
    sub.add_parser("project")
    ap = sub.add_parser("append")
    ap.add_argument("op")
    ap.add_argument("--payload", required=True)
    ap.add_argument("--actor", default="system")
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "bpcm.jsonl"
    if args.command == "demo":
        print(json.dumps(demo(state_dir), indent=2, sort_keys=True))
    elif args.command == "verify":
        result = verify_path(path)
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["valid"]:
            raise SystemExit(1)
    elif args.command == "certificate":
        result = verify_path(path)
        if not result["valid"]:
            raise SystemExit("invalid chain")
        print(json.dumps(result["certificate"], indent=2, sort_keys=True))
    elif args.command == "project":
        result = verify_path(path)
        if not result["valid"]:
            raise SystemExit("invalid chain")
        print(json.dumps(project(state_dir, result, result["certificate"]), indent=2, sort_keys=True))
    elif args.command == "append":
        print(json.dumps(append_event(state_dir, args.op, json.loads(args.payload), args.actor), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
