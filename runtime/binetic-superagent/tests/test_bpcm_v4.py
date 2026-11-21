#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/root/agent-workspace/binetic-superagent")
BPCM = ROOT / "bpcm.py"
COCKPIT = ROOT / "binetic-cockpit.py"


def run(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, text=True, capture_output=True, cwd=cwd, timeout=timeout)


def base_stream(state: Path):
    result = run([sys.executable, str(BPCM), "--state-dir", str(state), "demo"])
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_happy_and_envelope():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        out = base_stream(state)
        assert out["valid"] and out["events"] == 11 and not out["issues"]
        cert = out["certificate"]
        assert cert["version"] == 4
        assert cert["profile"] == "extended-canonical-v4"
        assert cert["packet_bytes"] > 0
        assert cert["l0"] and cert["l1"] and cert["l2"] and cert["l3"]
        rows = [json.loads(x) for x in (state / "bpcm.jsonl").read_text().splitlines() if x.strip()]
        assert rows[0]["body_hash"].startswith("bpcm4:")
        assert rows[0]["envelope"]["packet_hash"] == rows[0]["body_hash"].split(":", 1)[1]
        assert rows[0]["envelope"]["base"]["bw"] == 32
        views = state / "views"
        assert (views / "envelope.json").exists()
        assert (views / "bit_packets.json").exists()
        assert (views / "ucodes.json").exists()
        bitpack = json.loads((views / "bit_packets.json").read_text())["sample"]
        assert len(bitpack["router_qwords"]) == 2
        assert len(bitpack["body_qwords"]) >= 1
        print("PASS happy_and_envelope")


def test_tamper():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        path = state / "bpcm.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        rows[-1]["body"]["payload"]["claim"] = "tampered"
        path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
        result = run([sys.executable, str(BPCM), "--state-dir", str(state), "verify"])
        assert result.returncode != 0
        doc = json.loads(result.stdout)
        assert not doc["valid"]
        assert any("mismatch" in i for i in doc["issues"])
        print("PASS tamper")


def test_original_ops_invalid():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        base_stream(state)
        payload = json.dumps({"intent": "illegal", "legacy": True})
        result = run([sys.executable, str(BPCM), "--state-dir", str(state), "append", "PACKET_OPEN", "--payload", payload])
        assert result.returncode != 0
        print("PASS original_ops_invalid")


def test_cockpit_verify():
    result = run([sys.executable, str(COCKPIT), "verify"], cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["bpcm"]["valid"] is True
    print("PASS cockpit_verify")


if __name__ == "__main__":
    test_happy_and_envelope()
    test_tamper()
    test_original_ops_invalid()
    test_cockpit_verify()
    print("ALL BPCM V4 TESTS PASSED")
