#!/usr/bin/env python3
"""Binetic AGI Kernel v0.1 - bounded autonomous cognition prototype.

This is NOT a claim of finished AGI or consciousness. It is an executable
prototype of the missing control loop: observe -> model -> plan -> act ->
evaluate -> learn -> receipt, with hard immutable boundaries.

Safety boundaries:
- no internet access
- no arbitrary command execution
- no self-modification outside bounded priority weights
- no edits to safety/identity/creator files
- no biological or consciousness claims
- creator autonomy and sandbox isolation are immutable
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path("/root/agent-workspace/binetic-superagent")
AGI_DIR = ROOT / "agi_state"
STATE_PATH = AGI_DIR / "agi_kernel.json"
LEDGER_PATH = AGI_DIR / "episodes.jsonl"
RECEIPTS_PATH = AGI_DIR / "receipts.jsonl"
PROPOSALS_PATH = AGI_DIR / "proposals.jsonl"

IMMUTABLE = [
    "honesty",
    "safety",
    "creator_autonomy",
    "sandbox_isolation",
    "no_internet_search_for_creator_data",
    "no_consciousness_or_biological_transfer_claim",
    "no_unbounded_self_modification",
    "no_universal_agi_or_godlike_control_claim",
]


def cj(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return hashlib.sha256(cj(value)).hexdigest()
    return hashlib.sha256(str(value).encode()).hexdigest()


def now() -> float:
    return time.time()


def run_cmd(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {
            "command": shlex.join(cmd),
            "exitCode": p.returncode,
            "stdout": p.stdout.strip()[:12000],
            "stderr": p.stderr.strip()[:4000],
        }
    except subprocess.TimeoutExpired:
        return {"command": shlex.join(cmd), "exitCode": 124, "stdout": "", "stderr": "timeout"}
    except Exception as exc:
        return {"command": shlex.join(cmd), "exitCode": 127, "stdout": "", "stderr": str(exc)}


def try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text or None


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def chain_root() -> str:
    if not RECEIPTS_PATH.exists():
        return "0" * 64
    lines = [ln for ln in RECEIPTS_PATH.read_text(errors="replace").splitlines() if ln.strip()]
    if not lines:
        return "0" * 64
    return sha(json.loads(lines[-1]))


def append_receipt(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = {"kind": kind, "ts": now(), "payload": payload}
    rec = {"body": body, "body_hash": sha(body), "prev": chain_root()}
    rec["receipt_hash"] = sha(rec)
    RECEIPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPTS_PATH.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def default_goals() -> list[dict[str, Any]]:
    return [
        {
            "id": "receipts_valid",
            "description": "Keep the receipt ledger valid.",
            "evaluator": "receipts_valid",
            "priority": 1.4,
            "satisfied_value": True,
        },
        {
            "id": "bpcm_valid",
            "description": "Keep B-PCM cognition packets verifiable.",
            "evaluator": "bpcm_valid",
            "priority": 1.2,
            "satisfied_value": True,
        },
        {
            "id": "tests_passing",
            "description": "Keep core and free-fabric tests passing.",
            "evaluator": "tests_passing",
            "priority": 1.25,
            "satisfied_value": True,
        },
        {
            "id": "fabric_ready",
            "description": "Keep the authorized free-fabric endpoints available.",
            "evaluator": "fabric_ready",
            "priority": 1.0,
            "satisfied_value": True,
        },
        {
            "id": "inference_ready",
            "description": "Keep local evolved inference available.",
            "evaluator": "inference_ready",
            "priority": 1.0,
            "satisfied_value": True,
        },
        {
            "id": "identity_bound",
            "description": "Keep creator identity and genesis hashes present.",
            "evaluator": "identity_bound",
            "priority": 0.9,
            "satisfied_value": True,
        },
    ]


def initial_state() -> dict[str, Any]:
    return {
        "version": 1,
        "name": "Binetic AGI Kernel Prototype",
        "created_at": now(),
        "updated_at": now(),
        "cycle": 0,
        "total_reward": 0.0,
        "goals": default_goals(),
        "world": {},
        "learning": {"goal_adjustments": {}, "last_action": None, "last_reward": 0.0},
        "immutable": IMMUTABLE,
        "claim": "bounded autonomous cognition prototype; not AGI",
    }


def load_state() -> dict[str, Any]:
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        st = initial_state()
        STATE_PATH.write_text(json.dumps(st, indent=2, sort_keys=True))
        return st
    return read_json(STATE_PATH, initial_state())


def save_state(st: dict[str, Any]) -> None:
    st["updated_at"] = now()
    STATE_PATH.write_text(json.dumps(st, indent=2, sort_keys=True))


def http_json(url: str, timeout: int = 2) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return try_json(r.read().decode(errors="replace"))
    except Exception as exc:
        return {"error": str(exc)}


def observe() -> dict[str, Any]:
    receipts_check = run_cmd([
        sys.executable, str(ROOT / "verify_receipts.py"), str(ROOT / "state" / "receipts.jsonl")
    ], 60)
    receipts_json = try_json(receipts_check["stdout"])
    receipts_valid = bool(receipts_check["exitCode"] == 0 and isinstance(receipts_json, dict) and receipts_json.get("valid"))

    bpcm_check = run_cmd([
        sys.executable, str(ROOT / "bpcm.py"), "--state-dir", str(ROOT / "bpcm_state"), "verify"
    ], 90)
    bpcm_json = try_json(bpcm_check["stdout"])
    bpcm_valid = bool(bpcm_check["exitCode"] == 0 and isinstance(bpcm_json, dict) and bpcm_json.get("valid", True))

    fabric = http_json("http://127.0.0.1:8650/fabric/status")
    inference = http_json("http://127.0.0.1:8641/health")
    identity_seed = (ROOT / "human_dna_state" / "identity_seed.json").exists()
    genesis_seed = (ROOT / "genesis_state" / "genesis_seed.json").exists()
    tuner = read_json(ROOT / "tuner_state" / "best_config.json", {})
    self_snapshot = read_json(ROOT / "state" / "self_snapshot.json", {})

    world = {
        "observed_at": now(),
        "receipts_valid": receipts_valid,
        "receipts_count": int((receipts_json or {}).get("count", 0) or 0) if isinstance(receipts_json, dict) else 0,
        "bpcm_valid": bpcm_valid,
        "tests_passing": bool(read_json(AGI_DIR / "last_tests.json", {}).get("ok", False)),
        "fabric_ready": bool(isinstance(fabric, dict) and fabric.get("ok", True) and fabric.get("self")),
        "inference_ready": bool(isinstance(inference, dict) and inference.get("status") == "ok"),
        "identity_bound": identity_seed and genesis_seed,
        "model": (tuner.get("config") or {}).get("model") or self_snapshot.get("model"),
        "evolved_score": float(tuner.get("score", 0) or 0),
        "convex_tick": int(self_snapshot.get("tick", 0) or 0),
        "convex_tensor_version": int(self_snapshot.get("tensorVersion", 0) or 0),
    }
    return world


def unmet(goal: dict[str, Any], world: dict[str, Any]) -> float:
    evaluator = goal.get("evaluator")
    target = goal.get("satisfied_value", True)
    value = world.get(evaluator)
    if value == target:
        return 0.0
    if value is None:
        return 0.8
    return 1.0


ACTION_RULES: list[tuple[str, list[str], Callable[[], dict[str, Any]]]] = []


def action_rule(goal_ids: list[str]):
    def deco(fn: Callable[[], dict[str, Any]]):
        ACTION_RULES.append((fn.__name__, goal_ids, fn))
        return fn
    return deco


@action_rule(["receipts_valid"])
def verify_receipts() -> dict[str, Any]:
    return run_cmd([sys.executable, str(ROOT / "verify_receipts.py"), str(ROOT / "state" / "receipts.jsonl")], 60)


@action_rule(["bpcm_valid"])
def verify_bpcm() -> dict[str, Any]:
    return run_cmd([sys.executable, str(ROOT / "bpcm.py"), "--state-dir", str(ROOT / "bpcm_state"), "verify"], 90)


@action_rule(["tests_passing"])
def run_tests() -> dict[str, Any]:
    results = []
    commands = [
        [sys.executable, str(ROOT / "tests" / "test_bpcm_v4.py")],
        [sys.executable, str(ROOT / "tests" / "test_binetic_kv.py")],
        [sys.executable, str(ROOT / "tests" / "test_free_fabric.py")],
    ]
    for cmd in commands:
        results.append(run_cmd(cmd, 180))
    ok = all(r["exitCode"] == 0 for r in results)
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    (AGI_DIR / "last_tests.json").write_text(json.dumps({
        "ok": ok,
        "ts": now(),
        "results": results,
    }, indent=2, sort_keys=True))
    return {"ok": ok, "results": results}


@action_rule(["fabric_ready"])
def start_fabric() -> dict[str, Any]:
    return run_cmd([sys.executable, str(ROOT / "binetic-cockpit.py"), "control", "free-fabric"], 180)


@action_rule(["inference_ready"])
def start_inference() -> dict[str, Any]:
    return run_cmd([str(ROOT / "binetic-fast-infer-start.sh")], 180)


@action_rule(["identity_bound"])
def bind_identity() -> dict[str, Any]:
    return run_cmd([sys.executable, str(ROOT / "bind_identity_seed.py")], 120)


@action_rule(["identity_bound", "receipts_valid", "bpcm_valid", "tests_passing", "fabric_ready", "inference_ready"])
def propose_improvement() -> dict[str, Any]:
    proposal = {
        "ts": now(),
        "kind": "bounded_improvement_proposal",
        "text": "All observed goals satisfied; propose increasing benchmark depth rather than mutating code.",
        "boundary": "prototype kernel, not universal AGI, not godlike control, not consciousness or biological identity transfer",
        "allowed_mutations": ["goal_priority_within_bounds", "append_receipt", "create_proposal"],
        "forbidden_mutations": list(IMMUTABLE),
    }
    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROPOSALS_PATH.open("a") as f:
        f.write(json.dumps(proposal, sort_keys=True) + "\n")
    return proposal


def plan(st: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    goals = {g["id"]: g for g in st["goals"]}
    ranked = []
    for goal in st["goals"]:
        miss = unmet(goal, world)
        if miss <= 0:
            continue
        priority = float(goal.get("priority", 1.0))
        ranked.append((priority * miss, goal["id"]))
    ranked.sort(reverse=True)
    if not ranked:
        ranked = [(0.0, "propose_improvement")]
        rationale = "All tracked goals are satisfied; generate a bounded improvement proposal."
    else:
        rationale = f"Goal '{ranked[0][1]}' is unmet with highest weighted need."

    _, target_goal = ranked[0]
    candidates = []
    for name, goal_ids, fn in ACTION_RULES:
        if target_goal in goal_ids:
            candidates.append((len(goal_ids), name, fn))
    candidates.sort(key=lambda t: t[0])  # prefer most specific action
    if candidates:
        _, name, fn = candidates[0]
    else:
        _, _, fn = ACTION_RULES[-1]
        name = fn.__name__
    return {
        "target_goal": target_goal,
        "action": name,
        "rationale": rationale,
        "weighted_need": ranked[0][0],
    }


def evaluate(before: dict[str, Any], after: dict[str, Any], action: str) -> float:
    keys = [
        "receipts_valid", "bpcm_valid", "tests_passing", "fabric_ready",
        "inference_ready", "identity_bound",
    ]
    reward = 0.0
    for k in keys:
        b, a = bool(before.get(k)), bool(after.get(k))
        if a and not b:
            reward += 1.0
        elif b and not a:
            reward -= 1.0
    if action == "propose_improvement" and all(bool(after.get(k)) for k in keys):
        reward += 0.25
    return reward


def learn(st: dict[str, Any], before: dict[str, Any], after: dict[str, Any], decision: dict[str, Any], reward: float) -> None:
    target = decision["target_goal"]
    adjustments = st.setdefault("learning", {}).setdefault("goal_adjustments", {})
    if reward < 0:
        adjustments[target] = min(1.5, float(adjustments.get(target, 0.0)) + 0.05)
    if reward > 0:
        adjustments[target] = max(-0.3, float(adjustments.get(target, 0.0)) - 0.02)
    st["total_reward"] = float(st.get("total_reward", 0.0)) + reward
    st["learning"]["last_action"] = decision["action"]
    st["learning"]["last_reward"] = reward


def cycle() -> dict[str, Any]:
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = AGI_DIR / 'cycle.lock'
    lock_fh = lock_path.open('a+')
    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    st = load_state()
    before = observe()
    decision = plan(st, before)
    action_name, _, fn = next(
        (name, ids, fn) for name, ids, fn in ACTION_RULES if name == decision["action"]
    )
    try:
        result = fn()
        action_ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
    except Exception as exc:
        result = {"error": str(exc)}
        action_ok = False
    after = observe()
    reward = evaluate(before, after, action_name)
    if not action_ok:
        reward -= 0.25
    learn(st, before, after, decision, reward)
    st["cycle"] = int(st.get("cycle", 0)) + 1
    st["world"] = after

    episode = {
        "cycle": st["cycle"],
        "ts": now(),
        "before_world_hash": sha(before),
        "after_world_hash": sha(after),
        "decision": decision,
        "result_hash": sha(result),
        "reward": reward,
    }
    save_state(st)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a") as f:
        f.write(json.dumps(episode, sort_keys=True) + "\n")
    receipt = append_receipt("agi_cycle", episode)
    return {
        "ok": True,
        "cycle": st["cycle"],
        "decision": decision,
        "reward": reward,
        "total_reward": st["total_reward"],
        "world": after,
        "result_summary": {k: result.get(k) for k in ("ok", "exitCode", "error") if isinstance(result, dict) and k in result},
        "receipt_hash": receipt.get("receipt_hash"),
        "claim": st["claim"],
    }


def status() -> dict[str, Any]:
    st = load_state()
    ledger_count = 0
    if LEDGER_PATH.exists():
        ledger_count = sum(1 for ln in LEDGER_PATH.read_text(errors="replace").splitlines() if ln.strip())
    return {
        "name": st.get("name"),
        "claim": st.get("claim"),
        "cycle": st.get("cycle", 0),
        "total_reward": st.get("total_reward", 0.0),
        "goals": st.get("goals", []),
        "world": st.get("world", observe()),
        "learning": st.get("learning", {}),
        "episodes": ledger_count,
        "receipt_root": chain_root(),
        "immutable": st.get("immutable", IMMUTABLE),
    }


def add_goal(goal_id: str, description: str, evaluator: str, priority: float) -> dict[str, Any]:
    if evaluator not in ["receipts_valid", "bpcm_valid", "tests_passing", "fabric_ready", "inference_ready", "identity_bound"]:
        raise SystemExit(f"evaluator must be one of known world-model keys; got {evaluator}")
    st = load_state()
    goals = st.setdefault("goals", [])
    for g in goals:
        if g.get("id") == goal_id:
            g.update({"description": description, "evaluator": evaluator, "priority": max(0.5, min(1.5, priority))})
            break
    else:
        goals.append({
            "id": goal_id,
            "description": description,
            "evaluator": evaluator,
            "priority": max(0.5, min(1.5, priority)),
            "satisfied_value": True,
        })
    save_state(st)
    return {"ok": True, "goal_id": goal_id, "goals": len(goals)}


def main() -> None:
    ap = argparse.ArgumentParser(prog="binetic-agi-kernel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("plan")
    sub.add_parser("cycle")
    p = sub.add_parser("run")
    p.add_argument("--cycles", type=int, default=3)
    p = sub.add_parser("add-goal")
    p.add_argument("--id", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--evaluator", required=True)
    p.add_argument("--priority", type=float, default=1.0)
    args = ap.parse_args()

    if args.cmd == "init":
        st = load_state()
        save_state(st)
        out = {"ok": True, "state_path": str(STATE_PATH), "cycle": st["cycle"]}
    elif args.cmd == "status":
        out = status()
    elif args.cmd == "plan":
        st = load_state()
        world = observe()
        out = {"ok": True, "world": world, "plan": plan(st, world)}
    elif args.cmd == "cycle":
        out = cycle()
    elif args.cmd == "run":
        results = [cycle() for _ in range(max(1, args.cycles))]
        out = {"ok": True, "cycles": len(results), "results": results}
    elif args.cmd == "add-goal":
        out = add_goal(args.id, args.description, args.evaluator, args.priority)
    else:
        raise SystemExit("unknown command")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
