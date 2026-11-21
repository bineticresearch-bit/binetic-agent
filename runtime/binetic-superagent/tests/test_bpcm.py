#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path("/root/agent-workspace/binetic-superagent")
BPCM = BASE / "bpcm.py"


def run(args, expect_ok=True):
    result = subprocess.run([sys.executable, str(BPCM), *args], text=True, capture_output=True)
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"command failed: {args}\n{result.stdout}\n{result.stderr}")
    return result


def base_stream(state):
    run(["--state-dir", str(state), "demo"])


def tamper_hash_chain():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        path = state / "bpcm.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        rows[-1]["body"]["payload"]["claim"] = "tampered claim"
        path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
        result = run(["--state-dir", str(state), "verify", "--level", "L3"], expect_ok=False)
        assert result.returncode != 0
        doc = json.loads(result.stdout)
        assert not doc["valid"]
        assert any("body_hash mismatch" in issue for issue in doc["issues"])
        print("PASS tamper_hash_chain")


def illegal_frame_pop():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        result = subprocess.run(
            [sys.executable, str(BPCM), "--state-dir", str(state), "append", "FRAME_POP",
             "--payload", json.dumps({"todo_id": "root", "result": "illegal"}), "--actor", "tester"],
            text=True, capture_output=True,
        )
        assert result.returncode != 0
        assert ("frame pop must close top frame" in (result.stdout + result.stderr) or "requires an active frame" in (result.stdout + result.stderr))
        print("PASS illegal_frame_pop")


def unsupported_final_claim():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        result = subprocess.run(
            [sys.executable, str(BPCM), "--state-dir", str(state), "append", "FINAL_CLAIM",
             "--payload", json.dumps({"claim": "unsupported", "evidence": ["nonexistent"]}), "--actor", "tester"],
            text=True, capture_output=True,
        )
        assert result.returncode != 0
        assert "final claim evidence unsupported" in (result.stdout + result.stderr)
        print("PASS unsupported_final_claim")


def duplicate_swarm_claim():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        result = subprocess.run(
            [sys.executable, str(BPCM), "--state-dir", str(state), "append", "SWARM_TODO_CLAIM",
             "--payload", json.dumps({"todo_id": "verify"}), "--actor", "worker-2"],
            text=True, capture_output=True,
        )
        assert result.returncode != 0
        assert "todo already leased" in (result.stdout + result.stderr)
        print("PASS duplicate_swarm_claim")


def unsafe_policy_admit():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        # Start fresh, then intentionally create a losing proposal.
        run(["--state-dir", str(state), "append", "INTENT_OPEN",
             "--payload", json.dumps({"intent": "policy safety test"}), "--actor", "creator"])
        run(["--state-dir", str(state), "append", "POLICY_PROPOSE",
             "--payload", json.dumps({"proposal_id": "bad", "patch": {"x": 1}}), "--actor", "tester"])
        run(["--state-dir", str(state), "append", "POLICY_VERIFY",
             "--payload", json.dumps({"proposal_id": "bad", "baseline_score": 0.9, "champion_score": 0.1, "invariant_violations": []}),
             "--actor", "verifier"])
        result = subprocess.run(
            [sys.executable, str(BPCM), "--state-dir", str(state), "append", "POLICY_ADMIT",
             "--payload", json.dumps({"proposal_id": "bad", "reason": "unsafe"}), "--actor", "tester"],
            text=True, capture_output=True,
        )
        assert result.returncode != 0
        assert "attempted to admit non-winning patch" in (result.stdout + result.stderr)
        print("PASS unsafe_policy_admit")


if __name__ == "__main__":
    tamper_hash_chain()
    illegal_frame_pop()
    unsupported_final_claim()
    duplicate_swarm_claim()
    unsafe_policy_admit()
    print("ALL BPCM TESTS PASSED")
