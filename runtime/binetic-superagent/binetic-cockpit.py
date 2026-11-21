#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

STATE = Path("/root/agent-workspace/binetic-superagent/state")
BPCM_STATE = Path("/root/agent-workspace/binetic-superagent/bpcm_state")
ROOT = Path("/root/agent-workspace/binetic-superagent")
BIN = Path("/root/agent-workspace/bin")
MY_AGENT = Path("/root/my-agent")
ZERO = "0" * 64


def cj(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def h(value: Any) -> str:
    return hashlib.sha256(cj(value)).hexdigest()


def run_json(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {
            "command": shlex.join(cmd),
            "exitCode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"command": shlex.join(cmd), "exitCode": 124, "stdout": "", "stderr": "timeout"}


def try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text if text else None


def bootstrap_state() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    BPCM_STATE.mkdir(parents=True, exist_ok=True)
    (BIN).mkdir(parents=True, exist_ok=True)
    receipts = STATE / "receipts.jsonl"
    if not receipts.exists():
        receipts.write_text("")


def bootstrap() -> dict[str, Any]:
    bootstrap_state()
    actions = []

    # Idempotent symlinks for all native controls.
    links = {
        "binetic-cognition": ROOT / "bpcm.py",
        "binetic-receipt-append": ROOT / "receipt_cli.py",
        "binetic-verify-receipts": ROOT / "verify_receipts.py",
        "binetic-superagent": ROOT / "binetic-superagent.sh",
        "binetic-cockpit": ROOT / "binetic-cockpit.py",
        "binetic-kv": ROOT / "binetic_kv.py",
        "binetic-kv-start": ROOT / "binetic-kv-start.sh",
        "binetic-fast-infer": ROOT / "binetic-fast-infer.sh",
        "binetic-fast-infer-start": ROOT / "binetic-fast-infer-start.sh",
        "binetic-native-bench": ROOT / "binetic-native-bench.sh",
        "binetic-evolve": ROOT / "evolve_infer.py",
        "binetic-fast-evolved": ROOT / "binetic-fast-infer-evolved-start.sh",
        "binetic-free-fabric": ROOT / "binetic-free-fabric-start.sh",
        "binetic-bff": ROOT / "bff_fabric.py",
        "binetic-echo-lock": ROOT / "echo_phase_lock.py",
        "binetic-genesis": ROOT / "genesis_seed_from_self.py",
        "binetic-agi": ROOT / "agi_kernel.py",
        "binetic-evolve-agi": ROOT / "evolve_agi.py",
        "binetic-agi-loop": ROOT / "agi_loop_start.sh",
        "binetic-binetic-agent": ROOT / "run-binetic-binetic-agent.sh",
        "binetic-agent": Path("/root/agent-workspace/bin/binetic-agent"),
    }
    for name, target in links.items():
        link = BIN / name
        if not link.exists():
            if name == "binetic-agent":
                actions.append({"link": str(link), "status": "exists"})
                continue
            try:
                link.symlink_to(target)
                actions.append({"link": str(link), "status": "created", "target": str(target)})
            except FileExistsError:
                actions.append({"link": str(link), "status": "exists"})
        else:
            actions.append({"link": str(link), "status": "exists"})

    # Trust the project so binetic-agent.json hooks and permissions load.
    trust = run_json(["/root/agent-workspace/bin/binetic-agent", "trust", str(ROOT)], 60)
    actions.append({"trust": trust["exitCode"] == 0, "exitCode": trust["exitCode"]})

    # Verify current receipts and B-PCM.
    receipts = run_json(["/root/agent-workspace/bin/binetic-verify-receipts"], 60)
    bpcm = run_json(["/root/agent-workspace/bin/binetic-cognition", "--state-dir", str(BPCM_STATE), "verify"], 60)
    return {
        "ok": receipts["exitCode"] == 0 and bpcm["exitCode"] == 0,
        "actions": actions,
        "receipts": try_json(receipts["stdout"]),
        "bpcm": try_json(bpcm["stdout"]),
    }


def status() -> dict[str, Any]:
    bootstrap_state()
    ps = run_json(["bash", "-lc", "ps -eo pid,args | grep -E 'convex dev|model-proxy.mjs|sandbox/bridge.mjs|vite|binetic_kv.py proxy|llama-server|binetic-fast-infer' | grep -v grep || true"], 30)
    py = run_json([sys.executable, str(ROOT / "verify_receipts.py"), str(STATE / "receipts.jsonl")], 60)
    bpcm_path = BPCM_STATE / "bpcm.jsonl"
    bpcm_events = 0
    if bpcm_path.exists():
        bpcm_events = sum(1 for line in bpcm_path.read_text(errors="replace").splitlines() if line.strip())
    views = sorted(str(p.name) for p in (BPCM_STATE / "views").glob("*.json")) if (BPCM_STATE / "views").exists() else []
    kv_metrics = run_json([sys.executable, str(ROOT / "binetic_kv.py"), "metrics"], 60)
    evolved_path = ROOT / "tuner_state" / "best_config.json"
    evolved = try_json(evolved_path.read_text()) if evolved_path.exists() else {}
    fabric_status = run_json([sys.executable, str(ROOT / "bff_fabric.py"), "status", "--host", "0.0.0.0", "--port", "8650"], 60)
    return {
        "tick": int(os.environ.get("TICK", "0") or 0),
        "identity": {
            "name": "Binetic Superagent",
            "mainInterface": "Binetic Agent TUI",
            "version": "1.0.0",
            "root": str(ROOT),
        },
        "services": [line for line in ps["stdout"].splitlines() if line.strip()],
        "receipts": try_json(py["stdout"]),
        "bpcm": {"events": bpcm_events, "state": str(BPCM_STATE), "views": views},
        "kv": try_json(kv_metrics["stdout"]),
        "evolved": evolved,
        "fabric": try_json(fabric_status["stdout"]),
        "paths": {
            "bin": str(BIN),
            "cockpit": str(BIN / "binetic-cockpit"),
            "binetic-agent": str(BIN / "binetic-binetic-agent"),
        },
    }


def dashboard(session: str = "default", mem_status: str = "") -> dict[str, Any]:
    st = status()
    receipts = st.get("receipts") or {}
    if not isinstance(receipts, dict):
        receipts = {}
    chain_valid = bool(receipts.get("valid", False))
    chain_count = int(receipts.get("count", 0) or 0)
    chain_root = str(receipts.get("chain_root", ZERO))
    bpcm_events = int((st.get("bpcm") or {}).get("events", 0) or 0)
    view_count = len((st.get("bpcm") or {}).get("views", []))
    service_count = len(st.get("services", []))
    kv = st.get("kv") or {}
    kv_slots = int(kv.get("slots", 0) or 0)
    kv_valid = bool(kv.get("valid", False))
    kv_root = str(kv.get("chain_root", ZERO))
    evolved = st.get("evolved") or {}
    evolved_cfg = evolved.get("config") or {}
    model_name = Path(str(evolved_cfg.get("model", ""))).name or "none"
    fabric = st.get("fabric") or {}
    fabric_self = fabric.get("self") or {}
    fabric_nodes = len(fabric.get("nodes") or [])
    genesis_path = ROOT / "genesis_state" / "genesis_seed.json"
    genesis = try_json(genesis_path.read_text()) if genesis_path.exists() else {}
    genesis_id = str(genesis.get("seed_id", "none"))
    agi = try_json(run_json([sys.executable, str(ROOT / "agi_kernel.py"), "status"], 60)["stdout"]) or {}
    agi_cycle = int(agi.get("cycle", 0) or 0)
    agi_reward = float(agi.get("total_reward", 0.0) or 0.0)
    lines = [
        "╭─ BINETIC SUPERAGENT · GNOS CONTROL ROOM ──────────────────────────────╮",
        f"│ main interface: Binetic Agent TUI                                             │",
        f"│ receipts: {'VALID' if chain_valid else 'INVALID'}  count={chain_count:<5} root={chain_root[:12]}…  │",
        f"│ B-PCM:    events={bpcm_events:<5} projections={view_count:<2}                           │",
        f"│ services: {service_count:<2} active                                                │",
        f"│ KV:       {'VALID' if kv_valid else 'EMPTY/INVALID'} slots={kv_slots:<5} root={kv_root[:10]}… │",
        f"│ EVOLVED:  {model_name[:38]:<38} score={float(evolved.get('score',0) or 0):7.2f} │",
        f"│ FABRIC:   self={str(fabric_self.get('node_id','none'))[:16]:<16} peers={fabric_nodes:<4} chain={str(fabric.get('chain_root','0'*64))[:10]}… │",
        f"│ GENESIS:  seed={genesis_id[:20]:<20} dna={str(((genesis.get('blueprint') or {}).get('creator_dna_hash','none')))[:16]}… │",
        f"│ AGI:      kernel-v0.1     cycle={agi_cycle:<5} reward={agi_reward:7.2f} claim=prototype │",
        f"│ session:  {session[:28]:<28}                            │",
    ]
    if mem_status:
        lines.append(f"│ mem:      {mem_status[:58]:<58} │")
    lines.append("╰───────────────────────────────────────────────────────────────────────╯")
    lines.append("")
    lines.append("Native controls: ctrl+p → user:binetic-control, user:binetic-kv, user:binetic-verify")
    return {"text": "\n".join(lines), "status": st}


def receipt(payload: Any, kind: str = "binetic-agent") -> dict[str, Any]:
    bootstrap_state()
    wrapper = {
        "source": "binetic-agent",
        "kind": kind,
        "sessionId": os.environ.get("BINETIC_AGENT_SESSION_ID", ""),
        "event": os.environ.get("BINETIC_AGENT_EVENT", "manual"),
        "payload": payload,
    }
    cmd = [
        "/root/agent-workspace/bin/binetic-receipt-append",
        "append",
        "--kind", kind,
        "--input-hash", h(payload),
        "--output-hash", h(wrapper),
        "--payload", json.dumps(wrapper, sort_keys=True, separators=(",", ":")),
    ]
    result = run_json(cmd, 60)
    return {"ok": result["exitCode"] == 0, "result": try_json(result["stdout"]), "stderr": result["stderr"]}


def guarded_receipt(command: str, decision: str = "allow") -> dict[str, Any]:
    payload = {"command": command, "decision": decision, "toolName": os.environ.get("BINETIC_AGENT_TOOL_NAME", "bash")}
    rec = receipt(payload, "pretooluse" if decision == "allow" else "guard")
    return {"version": 1, "decision": decision, "context": f"Binetic receipt: {rec.get('result', {}).get('body_hash', 'unavailable')}"}


def verify(deep: bool = False) -> dict[str, Any]:
    bootstrap_state()
    receipt_cmd = run_json(["/root/agent-workspace/bin/binetic-verify-receipts"], 60)
    bpcm_cmd = run_json(["/root/agent-workspace/bin/binetic-cognition", "--state-dir", str(BPCM_STATE), "verify"], 120)
    out = {
        "receipts": try_json(receipt_cmd["stdout"]),
        "bpcm": try_json(bpcm_cmd["stdout"]),
        "ok": receipt_cmd["exitCode"] == 0 and bpcm_cmd["exitCode"] == 0,
    }
    if deep:
        tests = run_json([sys.executable, str(ROOT / "tests" / "test_bpcm_v4.py")], 120)
        out["tests"] = {"stdout": tests["stdout"], "stderr": tests["stderr"], "exitCode": tests["exitCode"]}
        out["ok"] = out["ok"] and tests["exitCode"] == 0
    return out


def control(action: str) -> dict[str, Any]:
    bootstrap_state()
    env = dict(os.environ)
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")
    if action == "boot":
        cmd = ["/bin/bash", "-lc", "bash /root/my-agent/start.sh && /root/agent-workspace/bin/binetic-superagent status"]
    elif action == "demo":
        cmd = [str(BIN / "binetic-cognition"), "--state-dir", str(BPCM_STATE), "demo"]
    elif action == "certificate":
        cmd = [str(BIN / "binetic-cognition"), "--state-dir", str(BPCM_STATE), "certificate"]
    elif action == "project":
        cmd = [str(BIN / "binetic-cognition"), "--state-dir", str(BPCM_STATE), "project"]
    elif action == "test":
        cmd = [sys.executable, str(ROOT / "tests" / "test_bpcm_v4.py")]
    elif action == "kv-demo":
        cmd = [sys.executable, str(BIN / "binetic-kv"), "demo"]
    elif action == "kv-bench":
        cmd = [sys.executable, str(BIN / "binetic-kv"), "bench"]
    elif action == "native-bench":
        cmd = [str(BIN / "binetic-native-bench")]
    elif action == "fast-infer":
        cmd = [str(BIN / "binetic-fast-infer-start")]
    elif action == "fast-evolved":
        cmd = [str(BIN / "binetic-fast-evolved")]
    elif action == "agi-status":
        cmd = [sys.executable, str(BIN / "binetic-agi"), "status"]
    elif action == "agi-cycle":
        cmd = [sys.executable, str(BIN / "binetic-agi"), "cycle"]
    elif action == "agi-evolve":
        cmd = [sys.executable, str(BIN / "binetic-evolve-agi"), "--cycles", os.environ.get("BINETIC_AGI_CYCLES", "2")]
    elif action == "agi-loop":
        cmd = [str(BIN / "binetic-agi-loop")]
    elif action == "free-fabric":
        cmd = [str(BIN / "binetic-free-fabric")]
    elif action == "fabric-status":
        cmd = [str(BIN / "binetic-bff"), "status", "--host", "0.0.0.0", "--port", "8650"]
    elif action == "echo-lock":
        cmd = [sys.executable, str(BIN / "binetic-echo-lock"), "demo"]
    elif action == "genesis-seed":
        dna = os.environ.get("BINETIC_DNA", "CREATOR_DNA_SEED")
        name = os.environ.get("BINETIC_GENESIS_NAME", "genesis-0")
        cmd = [sys.executable, str(BIN / "binetic-genesis"), "--dna", dna, "--name", name]
    elif action == "evolve-infer":
        cfg = json.loads(os.environ.get("BINETIC_MODEL_CONFIG", "{}"))
        model = cfg.get("model", os.environ.get("BINETIC_MODEL", "/root/agent-workspace/models/hf/Qwen3-4B-Q4_K_M.gguf"))
        cmd = [sys.executable, str(BIN / "binetic-evolve"), "--model", model,
               "--generations", os.environ.get("BINETIC_GENERATIONS", "4"),
               "--children", os.environ.get("BINETIC_CHILDREN", "4"),
               "--repeats", os.environ.get("BINETIC_REPEATS", "2"),
               "--objective", os.environ.get("BINETIC_OBJECTIVE", "decode")]
    elif action == "status":
        cmd = [str(BIN / "binetic-superagent"), "status"]
    else:
        raise SystemExit(f"unknown action {action}")
    result = run_json(cmd, 240)
    rec = receipt({"action": action, "command": shlex.join(cmd), "exitCode": result["exitCode"]}, "control")
    return {"action": action, "ok": result["exitCode"] == 0, "result": result, "receipt": rec}


def goal_monitor() -> dict[str, Any]:
    """Stop hook: continue if verification is not valid when BINETIC_AGENT_REQUIRE_VERIFY=1."""
    if os.environ.get("BINETIC_AGENT_REQUIRE_VERIFY", "") != "1":
        print(json.dumps({"version": 1}, separators=(",", ":")))
        return {"checked": False}
    v = verify(False)
    if v["ok"]:
        print(json.dumps({"version": 1}, separators=(",", ":")))
        return {"checked": True, "block": False}
    reason = "B-PCM or receipt verification failed; keep working."
    print(json.dumps({"version": 1, "decision": "block", "reason": reason}, separators=(",", ":")), file=sys.stderr)
    raise SystemExit(2)


def hook_dispatch(event: str) -> int:
    session = os.environ.get("BINETIC_AGENT_SESSION_ID", "manual")
    mem_status = os.environ.get("BINETIC_AGENT_MEM_STATUS", "")
    if event == "SessionStart":
        d = dashboard(session, mem_status)
        print(d["text"])
        print(json.dumps({"version": 1, "context": d["text"]}, separators=(",", ":")))
        return 0
    if event == "UserPromptSubmit":
        d = dashboard(session, mem_status)
        print(json.dumps({"version": 1, "context": d["text"]}, separators=(",", ":")))
        return 0
    if event == "PreToolUse":
        cmd = os.environ.get("BINETIC_AGENT_TOOL_INPUT_COMMAND", "")
        if cmd.startswith("binetic-") or "binetic-superagent" in cmd or "/root/my-agent/start.sh" in cmd:
            print(json.dumps(guarded_receipt(cmd, "allow"), separators=(",", ":")))
        else:
            print(json.dumps({"version": 1}, separators=(",", ":")))
        return 0
    if event == "PostToolUse":
        cmd = os.environ.get("BINETIC_AGENT_TOOL_INPUT_COMMAND", "")
        if cmd:
            receipt({"command": cmd, "toolUseId": os.environ.get("BINETIC_AGENT_TOOL_USE_ID", "")}, "posttooluse")
        print(json.dumps({"version": 1}, separators=(",", ":")))
        return 0
    if event == "Stop":
        goal_monitor()
        return 0
    if event in {"SessionEnd", "SubagentStop", "PreCompact", "PostCompact", "InstructionsLoaded", "Notification"}:
        if event == "SessionEnd":
            receipt({"reason": os.environ.get("BINETIC_AGENT_SESSION_END_REASON", "")}, "sessionend")
        print(json.dumps({"version": 1}, separators=(",", ":")))
        return 0
    print(json.dumps({"version": 1}, separators=(",", ":")))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="binetic-cockpit")
    parser.add_argument("--hook", choices=[
        "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop",
        "SessionEnd", "SubagentStop", "PreCompact", "PostCompact",
        "InstructionsLoaded", "Notification",
    ])
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("bootstrap")
    sub.add_parser("doctor")
    sub.add_parser("status")
    sub.add_parser("dashboard")
    sub.add_parser("verify")
    sub.add_parser("verify-deep")
    rec = sub.add_parser("receipt")
    rec.add_argument("--kind", default="binetic-agent")
    rec.add_argument("payload", nargs="?")
    ctrl = sub.add_parser("control")
    ctrl.add_argument("action", choices=["boot", "status", "demo", "certificate", "project", "test", "kv-demo", "kv-bench", "native-bench", "fast-infer", "fast-evolved", "evolve-infer", "free-fabric", "fabric-status", "echo-lock", "genesis-seed", "agi-status", "agi-cycle", "agi-evolve", "agi-loop"])
    sub.add_parser("goal-monitor")
    args = parser.parse_args()

    if args.hook:
        raise SystemExit(hook_dispatch(args.hook))
    if args.cmd == "bootstrap":
        print(json.dumps(bootstrap(), indent=2, sort_keys=True))
    elif args.cmd == "doctor":
        print(json.dumps(status(), indent=2, sort_keys=True))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, sort_keys=True))
    elif args.cmd == "dashboard":
        print(dashboard()["text"])
    elif args.cmd == "verify":
        print(json.dumps(verify(False), indent=2, sort_keys=True))
    elif args.cmd == "verify-deep":
        print(json.dumps(verify(True), indent=2, sort_keys=True))
    elif args.cmd == "receipt":
        print(json.dumps(receipt(try_json(args.payload or '{}'), args.kind), indent=2, sort_keys=True))
    elif args.cmd == "control":
        print(json.dumps(control(args.action), indent=2, sort_keys=True))
    elif args.cmd == "goal-monitor":
        goal_monitor()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
