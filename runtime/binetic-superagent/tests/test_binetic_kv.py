#!/usr/bin/env python3
"""Tests for the Binetic recreation of Kapitsa packetized KV cache."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/root/agent-workspace/binetic-superagent")
sys.path.insert(0, str(ROOT))

import binetic_kv as kv


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def test_v4_v6_route():
    v = kv.V4(kv.MODE_WORD_LANE, kv.TYPE_KV, 511, 0x3FFFF)
    assert v.word() == 0x57FFFFFF
    back = kv.V4.decode(v.word())
    assert (back.mode, back.type, back.sequence, back.index) == (v.mode, v.type, v.sequence, v.index)
    a = kv.V6(0x123456789ABC, 42, 0xDEADBEEF, 0xCAFEBABE)
    assert kv.V6.from_key(a.key()).bytes() == a.bytes()
    r = kv.Route.make(kv.V4(kv.MODE_OPAQUE, kv.TYPE_KV, 123, 0x12345), 0xBEEF, 0x0011)
    assert r.v4().type == kv.TYPE_KV
    assert r.v4().sequence == 123
    assert r.channel() == 0xBEEF
    assert r.branch() == 0x0011
    assert kv.popcount16(0xBEEF) == 13
    assert kv.best_branch(0x0011, 0x0010) == 4
    assert kv.best_branch(0x0001, 0x0010) == -1
    print("PASS v4_v6_route")


def test_slot_receipt_and_tamper():
    slot = kv.make_exact_slot("binetic-agent-binetic-local", 7, 70000, bytes([1, 2, 3]) * 8, 0xBEEF, 0x0011)
    assert slot.block_position() == 70000
    assert slot.route.v4().sequence == (70000 & kv.MASK9)
    assert slot.address.lane_offset == (70000 >> 9)
    r = kv.Receipt(0x1001, 0, 0, slot.layer_id, slot.model_id, len(slot.payload), 50, 1, input_hash=kv.ZERO, output_hash=kv.sha(slot.payload))
    kv.emit(slot, r)
    assert kv.verify(slot, r)
    assert r.channel_mask == slot.route.channel()
    assert r.layer_id == slot.layer_id
    assert r.model_id == slot.model_id
    assert r.payload_length == len(slot.payload)
    changed = slot.clone()
    changed.payload = bytes([9]) + changed.payload[1:]
    assert not kv.verify(changed, r)
    changed = slot.clone()
    changed.address.lane_offset += 1
    assert not kv.verify(changed, r)
    print("PASS slot_receipt_and_tamper")


def test_bitplanes_lossless_and_elision():
    exact = kv.make_exact_slot("planes", 1, 300, bytes([0, 1, 2, 128]) * 4)
    planes = kv.bitplane_slot(exact)
    assert planes.lane_width == kv.LANE_BIT_PLANES
    assert planes.lane_count == len(exact.payload) * 8
    assert planes.plane_mask == 0xFF
    restored = kv.restore_planes(kv.split_planes(planes), len(exact.payload))
    assert restored == exact.payload
    elided = kv.elide_zero_planes(planes)
    assert elided.plane_mask != 0xFF
    assert kv.restore_planes(kv.split_planes(elided), len(exact.payload)) == exact.payload
    print("PASS bitplanes_lossless_and_elision")


def test_index_consolidation_teleport():
    ix = kv.ReceiptIndex()
    for i in range(4):
        slot = kv.make_exact_slot("consolidate", i % 2, 20 + i, bytes([i, 0, 255]) * 8, 0xFFFF if i % 2 == 0 else 0xA5A5, 1 << i)
        r = kv.Receipt(0x2000 + i, 0, i, slot.layer_id, slot.model_id, len(slot.payload), [10, 90, 70, 30][i], [1, 2, 1, 0][i], input_hash=kv.ZERO, output_hash=kv.sha(slot.payload))
        kv.emit(slot, r)
        ix.add(slot, r)
    assert ix.validate_all()
    assert ix.by_kind(kv.TYPE_KV + 1) == [0, 1, 2, 3]
    assert ix.by_channel(0xA5A5) == [1, 3]
    assert ix.by_block(22) == [2]
    assert ix.by_drive(1) == [0, 2]
    assert ix.by_reward(70) == [1, 2]
    assert ix.top_experiences(50, 1, 2) == [2]
    chosen = ix.top_experiences(50, 1, 2)
    state = ix.consolidate(chosen)
    assert state.steps == len(chosen)
    assert state.steps >= 1
    assert state.digest != kv.ZERO
    plan = kv.TeleportPlan(0b1111, state, ix)
    assert len(plan.teleport) == len(chosen)
    assert len(plan.slices) >= 1
    print("PASS index_consolidation_teleport")


def test_cli_demo():
    result = run([sys.executable, str(ROOT / "binetic_kv.py"), "demo"])
    assert result.returncode == 0, result.stdout + result.stderr
    doc = json.loads(result.stdout)
    assert doc["valid"] is True
    assert doc["slots"] == 5
    assert doc["metrics"]["valid"] is True
    assert doc["teleport_plan"]["fanout"] >= 1
    bench = run([sys.executable, str(ROOT / "binetic_kv.py"), "bench", "--n", "256", "--rounds", "1"])
    assert bench.returncode == 0
    b = json.loads(bench.stdout)
    assert b["decisions"] == 256
    assert b["decisions_per_s"] > 0
    print("PASS cli_demo")


if __name__ == "__main__":
    test_v4_v6_route()
    test_slot_receipt_and_tamper()
    test_bitplanes_lossless_and_elision()
    test_index_consolidation_teleport()
    test_cli_demo()
    print("ALL BINETIC KV TESTS PASSED")
