#!/usr/bin/env python3
"""Binetic recreation of Kapitsa packetized KV cache.

Core rule from Kapitsa: bits route, bytes hold data.

This module implements a CPU/format slice:
- 64-bit Route: V4 in high half, channel mask + branch mask in low half.
- V4: mode(2)|type(3)|sequence(9)|index(18).
- V6: node_prefix(48)|bank(16)|v4_index(32)|lane_offset(32).
- Slot: address + route + opaque payload bytes or bit planes.
- Receipt: deterministic SHA-256 over route/address/lane metadata/payload,
  with state chaining through prev_hash -> state_before/state_after.
- ReceiptIndex: lookup by kind/channel/op/block/model-layer/lane/prev/hash
  and prefix/dedup/branch ranking without reading payload bytes.
- ConsolidatedState: deterministic reward/drive digest and reward-biased
  prefetch ranking. CPU/proxy only.

No model, no GPU, no wall-clock value enters a route or receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable

MASK48 = (1 << 48) - 1
MASK32 = (1 << 32) - 1
MASK16 = (1 << 16) - 1
MASK18 = (1 << 18) - 1
MASK9 = (1 << 9) - 1
ZERO = "0" * 64
DOC_DOMAIN = "binetic.kapitsa.packet_kv.v1"

MODE_OPAQUE = 0
MODE_WORD_LANE = 1
MODE_BIT_PLANE = 3

TYPE_TENSOR = 0
TYPE_STATE = 1
TYPE_KV = 2
TYPE_CONTROL = 3
TYPE_RECEIPT = 4
TYPE_CHECKPOINT = 5

LANE_OPAQUE = 0
LANE_BIT_PLANES = 1
BYTE_PLANES = 8
SEQUENCE_SPAN = 512


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def h(value: Any) -> str:
    return sha(canon(value))


def u16(value: int) -> bytes:
    return int(value & MASK16).to_bytes(2, "little")


def u32(value: int) -> bytes:
    return int(value & MASK32).to_bytes(4, "little")


def u64(value: int) -> bytes:
    return int(value & MASK32).to_bytes(8, "little")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


class V4:
    __slots__ = ("mode", "type", "sequence", "index")

    def __init__(self, mode: int = 0, type_: int = 0, sequence: int = 0, index: int = 0):
        self.mode = mode & 3
        self.type = type_ & 7
        self.sequence = sequence & MASK9
        self.index = index & MASK18

    def word(self) -> int:
        return ((self.mode & 3) << 30) | ((self.type & 7) << 27) | ((self.sequence & MASK9) << 18) | (self.index & MASK18)

    @classmethod
    def decode(cls, word: int) -> "V4":
        return cls((word >> 30) & 3, (word >> 27) & 7, (word >> 18) & MASK9, word & MASK18)

    def to_json(self) -> dict[str, int]:
        return {"mode": self.mode, "type": self.type, "sequence": self.sequence, "index": self.index}

    @classmethod
    def from_json(cls, d: dict[str, int]) -> "V4":
        return cls(d.get("mode", 0), d.get("type", 0), d.get("sequence", 0), d.get("index", 0))


class V6:
    __slots__ = ("node_prefix", "bank", "v4_index", "lane_offset")

    def __init__(self, node_prefix: int = 0, bank: int = 0, v4_index: int = 0, lane_offset: int = 0):
        self.node_prefix = node_prefix & MASK48
        self.bank = bank & MASK16
        self.v4_index = v4_index & MASK32
        self.lane_offset = lane_offset & MASK32

    def key(self) -> str:
        hi = ((self.node_prefix & MASK48) << 16) | self.bank
        lo = (self.v4_index << 32) | self.lane_offset
        return f"{hi:016x}{lo:016x}"

    @classmethod
    def from_key(cls, key: str) -> "V6":
        raw = int(key, 16)
        hi = raw >> 64
        lo = raw & MASK64
        return cls(hi >> 16, hi & MASK16, lo >> 32, lo & MASK32)

    def bytes(self) -> bytes:
        hi = ((self.node_prefix & MASK48) << 16) | self.bank
        lo = (self.v4_index << 32) | self.lane_offset
        return hi.to_bytes(8, "big") + lo.to_bytes(8, "big")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "V6":
        hi = int.from_bytes(raw[:8], "big")
        lo = int.from_bytes(raw[8:16], "big")
        return cls(hi >> 16, hi & MASK16, lo >> 32, lo & MASK32)

    def to_json(self) -> dict[str, int]:
        return {"node_prefix": self.node_prefix, "bank": self.bank, "v4_index": self.v4_index, "lane_offset": self.lane_offset}

    @classmethod
    def from_json(cls, d: dict[str, int]) -> "V6":
        return cls(d.get("node_prefix", 0), d.get("bank", 0), d.get("v4_index", 0), d.get("lane_offset", 0))


MASK64 = (1 << 64) - 1


class Route:
    __slots__ = ("bits",)

    def __init__(self, bits: int = 0):
        self.bits = bits & MASK64

    @classmethod
    def make(cls, v4: V4, channel: int = 0, branch: int = 0) -> "Route":
        return cls((v4.word() << 32) | ((channel & MASK16) << 16) | (branch & MASK16))

    def v4(self) -> V4:
        return V4.decode(self.bits >> 32)

    def channel(self) -> int:
        return (self.bits >> 16) & MASK16

    def branch(self) -> int:
        return self.bits & MASK16

    def to_json(self) -> dict[str, int]:
        return {"bits": self.bits, "v4": self.v4().to_json(), "channel": self.channel(), "branch": self.branch()}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Route":
        if "bits" in d:
            return cls(int(d["bits"]))
        return cls.make(V4.from_json(d.get("v4", {})), int(d.get("channel", 0)), int(d.get("branch", 0)))


class PrefixQuery:
    def __init__(self, match: int = 0, mask: int = 0):
        self.match = match & MASK32
        self.mask = mask & MASK32

    def matches(self, slot: "Slot") -> bool:
        return (slot.address.v4_index & self.mask) == (self.match & self.mask) and (slot.route.v4().word() & self.mask) == (self.match & self.mask)


def popcount16(v: int) -> int:
    return (v & MASK16).bit_count()


def best_branch(branches: int, valid: int) -> int:
    ok = branches & valid
    return ok.bit_length() - 1 if ok else -1


class Slot:
    def __init__(self, address: V6 | None = None, route: Route | None = None, lane_width: int = LANE_OPAQUE, lane_count: int = 0, plane_mask: int = 0, payload: bytes = b""):
        self.address = address or V6()
        self.route = route or Route()
        self.lane_width = lane_width
        self.lane_count = lane_count
        self.plane_mask = plane_mask & MASK16
        self.payload = payload

    @property
    def kind(self) -> int:
        return self.route.v4().type

    @property
    def model_id(self) -> int:
        return self.address.node_prefix

    @property
    def layer_id(self) -> int:
        return self.address.bank

    def block_position(self) -> int:
        v = self.route.v4()
        if v.mode == MODE_OPAQUE:
            return (self.address.lane_offset << 9) | v.sequence
        return v.sequence

    def set_block_position(self, block: int) -> None:
        v = self.route.v4()
        v.sequence = block & MASK9
        if v.mode == MODE_OPAQUE:
            self.address.lane_offset = (block >> 9) & MASK32
        self.route = Route.make(v, self.route.channel(), self.route.branch())

    def clone(self) -> "Slot":
        return Slot(V6(self.address.node_prefix, self.address.bank, self.address.v4_index, self.address.lane_offset), Route(self.route.bits), self.lane_width, self.lane_count, self.plane_mask, self.payload)

    def to_json(self) -> dict[str, Any]:
        return {
            "address": self.address.to_json(), "route": self.route.to_json(),
            "lane_width": self.lane_width, "lane_count": self.lane_count,
            "plane_mask": self.plane_mask, "payload": self.payload.hex(),
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Slot":
        return cls(V6.from_json(d.get("address", {})), Route.from_json(d.get("route", {})), int(d.get("lane_width", 0)), int(d.get("lane_count", 0)), int(d.get("plane_mask", 0)), bytes.fromhex(d.get("payload", "")))


class Receipt:
    def __init__(self, op_code: int = 0, channel_mask: int = 0, seq: int = 0, layer_id: int = 0, model_id: int = 0, payload_length: int = 0, reward_q8: int = 0, drive_mask: int = 0, prev: str = ZERO, state_before: str = ZERO, state_after: str = ZERO, input_hash: str = ZERO, output_hash: str = ZERO, body: str = ZERO):
        self.op_code = op_code & MASK16
        self.channel_mask = channel_mask & MASK16
        self.seq = seq & MASK32
        self.layer_id = layer_id & MASK16
        self.model_id = model_id & MASK48
        self.payload_length = payload_length & MASK32
        self.reward_q8 = max(-128, min(127, reward_q8))
        self.drive_mask = drive_mask & MASK16
        self.prev = prev
        self.state_before = state_before
        self.state_after = state_after
        self.input_hash = input_hash
        self.output_hash = output_hash
        self.body = body

    def header(self) -> dict[str, Any]:
        return {
            "domain": DOC_DOMAIN, "op_code": self.op_code, "channel_mask": self.channel_mask,
            "seq": self.seq, "layer_id": self.layer_id, "model_id": self.model_id,
            "payload_length": self.payload_length, "reward_q8": self.reward_q8,
            "drive_mask": self.drive_mask, "prev": self.prev, "state_before": self.state_before,
            "input_hash": self.input_hash, "output_hash": self.output_hash,
        }

    def to_json(self) -> dict[str, Any]:
        return {**self.header(), "kind_code": self.kind_code, "body": self.body}

    @property
    def kind_code(self) -> int:
        return ((self.op_code >> 8) & 7) + 1

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Receipt":
        r = cls(
            int(d.get("op_code", 0)), int(d.get("channel_mask", 0)), int(d.get("seq", 0)),
            int(d.get("layer_id", 0)), int(d.get("model_id", 0)), int(d.get("payload_length", 0)),
            int(d.get("reward_q8", 0)), int(d.get("drive_mask", 0)),
            str(d.get("prev", ZERO)), str(d.get("state_before", ZERO)), str(d.get("state_after", ZERO)),
            str(d.get("input_hash", ZERO)), str(d.get("output_hash", ZERO)), str(d.get("body", ZERO)),
        )
        return r


class BodyHasher:
    def __init__(self) -> None:
        self.h = hashlib.sha256()

    def update(self, data: bytes) -> None:
        self.h.update(data)

    def done(self) -> str:
        return self.h.hexdigest()


def preimage_chunks(slot: Slot, r: Receipt) -> list[bytes]:
    route = slot.route.bits.to_bytes(8, "little")
    addr = slot.address.bytes()
    return [
        canon(r.header()), route, addr,
        u16(slot.lane_width), u16(slot.lane_count), u16(slot.plane_mask),
        slot.payload,
    ]


def begin_body(slot: Slot, r: Receipt) -> BodyHasher:
    bh = BodyHasher()
    for chunk in preimage_chunks(slot, r):
        bh.update(chunk)
    return bh


def emit(slot: Slot, r: Receipt) -> Receipt:
    r.channel_mask = slot.route.channel()
    r.layer_id = slot.address.bank
    r.model_id = slot.address.node_prefix
    r.seq = slot.route.v4().sequence
    r.payload_length = len(slot.payload)
    r.body = begin_body(slot, r).done()
    r.state_after = hash_pair(r.state_before, r.body)
    return r


def verify(slot: Slot, r: Receipt) -> bool:
    return r.body != ZERO and begin_body(slot, r).done() == r.body


def hash_pair(a: str, b: str) -> str:
    return sha(bytes.fromhex(a) + bytes.fromhex(b))


def hash_hashes(values: Iterable[str]) -> str:
    h = hashlib.sha256()
    for value in values:
        h.update(bytes.fromhex(value))
    return h.hexdigest()


def split_planes(slot: Slot) -> dict[str, Any]:
    if slot.lane_width != LANE_BIT_PLANES:
        raise ValueError("not bit-plane slot")
    data: list[bytes] = []
    at = 0
    for plane in range(8):
        if not (slot.plane_mask >> plane) & 1:
            continue
        length = (slot.lane_count + 7) // 8
        data.append(slot.payload[at:at + length])
        at += length
    return {"mask": slot.plane_mask, "data": data}


def restore_planes(planes: dict[str, Any], byte_length: int) -> bytes:
    out = bytearray(byte_length)
    plane_indexes = [i for i in range(8) if (planes["mask"] >> i) & 1]
    if len(plane_indexes) != len(planes["data"]):
        raise ValueError("plane count mismatch")
    for plane, data in zip(plane_indexes, planes["data"]):
        for lane in range(byte_length):
            byte_at = lane // 8
            bit_at = 7 - (lane % 8)
            if byte_at < len(data) and (data[byte_at] >> bit_at) & 1:
                out[lane] |= 1 << plane
    return bytes(out)


def bitplane_slot(exact: Slot) -> Slot:
    s = exact.clone()
    s.lane_width = LANE_BIT_PLANES
    s.lane_count = len(s.payload) * 8
    s.plane_mask = 0xFF
    planes = []
    for plane in range(8):
        row = bytearray((s.lane_count + 7) // 8)
        for lane, byte in enumerate(exact.payload):
            if (byte >> plane) & 1:
                row[lane // 8] |= 1 << (7 - (lane % 8))
        planes.append(bytes(row))
    s.payload = b"".join(planes)
    v = s.route.v4()
    v.mode = MODE_BIT_PLANE
    s.address.lane_offset = 0
    s.route = Route.make(v, s.route.channel(), s.route.branch())
    return s


def elide_zero_planes(slot: Slot) -> Slot:
    planes = split_planes(slot)
    keep_mask = 0
    data: list[bytes] = []
    original_planes = [i for i in range(8) if (planes["mask"] >> i) & 1]
    for plane_index, chunk in zip(original_planes, planes["data"]):
        if any(chunk):
            keep_mask |= 1 << plane_index
            data.append(chunk)
    s = slot.clone()
    s.plane_mask = keep_mask
    s.payload = b"".join(data)
    return s


class ReceiptIndex:
    def __init__(self) -> None:
        self.records: list[tuple[Slot, Receipt]] = []

    def add(self, slot: Slot, receipt: Receipt) -> None:
        self.records.append((slot, receipt))

    def validate_all(self) -> bool:
        return all(verify(slot, r) for slot, r in self.records)

    def by_kind(self, type_code: int) -> list[int]:
        return [i for i, (s, _) in enumerate(self.records) if s.kind + 1 == type_code]

    def by_channel(self, channel: int) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.channel_mask == channel]

    def by_op(self, op: int) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.op_code == op]

    def by_block(self, block: int) -> list[int]:
        return [i for i, (s, _) in enumerate(self.records) if s.block_position() == block]

    def by_model_layer(self, model: int, layer: int) -> list[int]:
        return [i for i, (s, _) in enumerate(self.records) if s.model_id == model and s.layer_id == layer]

    def by_lane(self, lane: int) -> list[int]:
        return [i for i, (s, _) in enumerate(self.records) if (s.lane_width << 32) | s.lane_count == lane]

    def by_prev(self, prev: str) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.prev == prev]

    def by_input(self, ih: str) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.input_hash == ih]

    def by_output(self, oh: str) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.output_hash == oh]

    def by_state_before(self, sb: str) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.state_before == sb]

    def by_state_after(self, sa: str) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.state_after == sa]

    def by_drive(self, drive: int) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.drive_mask & drive]

    def by_reward(self, min_reward: int) -> list[int]:
        return [i for i, (_, r) in enumerate(self.records) if r.reward_q8 >= min_reward]

    def prefix(self, q: PrefixQuery) -> list[int]:
        return [i for i, (s, _) in enumerate(self.records) if q.matches(s)]

    def duplicates(self) -> list[tuple[int, list[int]]]:
        groups: dict[str, list[int]] = {}
        for i, (s, r) in enumerate(self.records):
            key = f"{s.address.key()}:{r.output_hash}"
            groups.setdefault(key, []).append(i)
        return [(v[0], v[1:]) for v in groups.values() if len(v) > 1]

    def rank_branches(self, valid: int) -> list[int]:
        return sorted(range(len(self.records)), key=lambda i: (-best_branch(self.records[i][0].route.branch(), valid), i))

    def top_experiences(self, min_reward_q8: int, drive_filter: int, limit: int) -> list[int]:
        candidates = []
        for i, (_, r) in enumerate(self.records):
            if r.reward_q8 < min_reward_q8 or (drive_filter and not (r.drive_mask & drive_filter)):
                continue
            candidates.append((r.reward_q8, r.seq, r.body, i))
        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
        return [c[3] for c in candidates[:limit]]

    def consolidate(self, ids: list[int], before: "ConsolidatedState | None" = None) -> "ConsolidatedState":
        state = before or ConsolidatedState()
        for i in ids:
            r = self.records[i][1]
            state.receipts.append(r.body)
            state.reward_sum += r.reward_q8
            state.drive_mask |= r.drive_mask
            state.steps += 1
            state.digest = hash_pair(state.digest, r.body)
        return state

    def rank_consolidated(self, valid: int, state: "ConsolidatedState") -> list[int]:
        folded = set(state.receipts)
        keys: dict[int, tuple[bool, int, int, int]] = {}
        for i, (s, r) in enumerate(self.records):
            keys[i] = (r.body in folded, r.reward_q8, best_branch(s.route.branch(), valid), -i)
        return sorted(range(len(self.records)), key=lambda i: keys[i], reverse=True)


class ConsolidatedState:
    def __init__(self) -> None:
        self.steps = 0
        self.reward_sum = 0
        self.drive_mask = 0
        self.digest = ZERO
        self.receipts: list[str] = []

    def to_json(self) -> dict[str, Any]:
        return {"steps": self.steps, "reward_sum": self.reward_sum, "drive_mask": self.drive_mask, "digest": self.digest, "receipts": self.receipts}


class TeleportPlan:
    def __init__(self, valid: int, state: ConsolidatedState, index: ReceiptIndex):
        folded = set(state.receipts)
        self.teleport: list[int] = []
        self.slices: list[dict[str, Any]] = []
        for i, (slot, r) in enumerate(index.records):
            if r.body in folded:
                self.teleport.append(i)
                continue
            branch = best_branch(slot.route.branch(), valid)
            if branch >= 0:
                self.slices.append({"id": i, "key": slot.address.key(), "branch": branch, "body": r.body})

    def to_json(self) -> dict[str, Any]:
        return {"teleport": self.teleport, "fanout": len(self.slices), "slices": self.slices}


# ---- Binetic Agent-native persistence and HTTP proxy ----

STATE_ROOT = Path("/root/agent-workspace/binetic-superagent/kv_state")
SLOTS_PATH = STATE_ROOT / "slots.jsonl"
RECEIPTS_PATH = STATE_ROOT / "receipts.jsonl"
METRICS_PATH = STATE_ROOT / "metrics.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.strip()]


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(to_jsonable(value), sort_keys=True) + "\n")


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(to_jsonable(value), sort_keys=True, indent=2))
    tmp.replace(path)


def make_exact_slot(model_prefix: str, layer: int, block: int, payload: bytes, channel: int = 0, branch: int = 0) -> Slot:
    model_id = int.from_bytes(hashlib.sha256(model_prefix.encode()).digest()[:6], "little") & MASK48
    address = V6(model_id, layer, 0, 0)
    route = Route.make(V4(MODE_OPAQUE, TYPE_KV, 0, 0), channel, branch)
    slot = Slot(address, route, LANE_OPAQUE, 0, 0, payload)
    slot.set_block_position(block)
    return slot


def record_slot(slot: Slot, *, op_code: int = 0x0101, reward_q8: int = 0, drive_mask: int = 0, input_hash: str = ZERO, output_hash: str | None = None) -> dict[str, Any]:
    chain = load_jsonl(RECEIPTS_PATH)
    prev = chain[-1]["body"] if chain else ZERO
    state_before = chain[-1].get("state_chain", chain[-1].get("state_after", ZERO)) if chain else ZERO
    receipt = Receipt(op_code, slot.route.channel(), slot.route.v4().sequence, slot.layer_id, slot.model_id, len(slot.payload), reward_q8, drive_mask, prev, state_before, ZERO, input_hash, output_hash or sha(slot.payload))
    emit(slot, receipt)
    persisted = receipt.to_json()
    persisted["state_chain"] = receipt.state_after
    append_jsonl(SLOTS_PATH, {"slot": slot.to_json(), "receipt": receipt.to_json()})
    append_jsonl(RECEIPTS_PATH, persisted)
    return {"slot": slot.to_json(), "receipt": receipt.to_json()}


def load_index() -> ReceiptIndex:
    index = ReceiptIndex()
    for row in load_jsonl(SLOTS_PATH):
        index.add(Slot.from_json(row["slot"]), Receipt.from_json(row["receipt"]))
    return index


def store_query(kind: str, value: Any) -> dict[str, Any]:
    index = load_index()
    if kind == "prefix":
        ids = index.prefix(PrefixQuery(int(value.get("match", 0)), int(value.get("mask", 0))))
    elif kind == "kind":
        ids = index.by_kind(int(value))
    elif kind == "block":
        ids = index.by_block(int(value))
    elif kind == "model_layer":
        ids = index.by_model_layer(int(value["model"]), int(value["layer"]))
    elif kind == "duplicates":
        ids = index.duplicates()
    else:
        raise ValueError(f"unknown query {kind}")
    return {"kind": kind, "ids": ids, "valid": index.validate_all()}


def proxy_bench(n: int = 512, rounds: int = 3) -> dict[str, Any]:
    """Packed route decision throughput; native ARM core when available."""
    native = Path("/root/agent-workspace/binetic-superagent/native/bpcm_route_bench")
    if native.exists():
        result = subprocess.run([str(native), str(n), str(rounds)], text=True, capture_output=True)
        if result.returncode == 0:
            doc = json.loads(result.stdout)
            doc["backend"] = "native-arm-neon"
            doc["claim"] = "CPU packet-lane routing proxy, not tok/s"
            return doc
    index = load_index()
    best = 0.0
    for _ in range(rounds):
        t0 = time.perf_counter_ns()
        for i in range(n):
            valid = (1 << (i % 16)) - 1 or 1
            best_branch(index.records[i % len(index.records)][0].route.branch() if index.records else 0xA5A5, valid)
        best = max(best, (time.perf_counter_ns() - t0) / 1_000_000)
    return {"decisions": n, "best_ms": best, "decisions_per_s": n / (best / 1000) if best else 0, "backend": "python", "claim": "CPU routing proxy, not inference speed"}


def metrics() -> dict[str, Any]:
    chain = load_jsonl(RECEIPTS_PATH)
    index = load_index()
    return {
        "slots": len(index.records),
        "receipts": len(chain),
        "valid": index.validate_all(),
        "chain_root": chain[-1]["body"] if chain else ZERO,
        "state_root": chain[-1].get("state_chain", chain[-1].get("state_after", ZERO)) if chain else ZERO,
        "last_metrics": load_jsonl(METRICS_PATH)[-1] if METRICS_PATH.exists() else None,
    }


def cmd_demo() -> dict[str, Any]:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    SLOTS_PATH.unlink(missing_ok=True)
    RECEIPTS_PATH.unlink(missing_ok=True)
    rows = []
    for i in range(5):
        payload = bytes([0x10 + i, 0x00, 0xFF]) * 8
        slot = make_exact_slot("binetic-agent-binetic-local", layer=i % 3, block=70000 + i, payload=payload, channel=0xBEEF, branch=1 << (i % 8))
        rows.append(record_slot(slot, op_code=0x1001 + i, reward_q8=30 + i * 10, drive_mask=1 if i % 2 == 0 else 2, input_hash=h({"prompt": i})))
    index = load_index()
    valid = index.validate_all()
    chosen = index.top_experiences(50, 1, 2)
    state = index.consolidate(chosen)
    plan = TeleportPlan(0xFF, state, index)
    result = {
        "kind": "binetic-packet-kv-demo", "version": 1,
        "slots": len(index.records), "valid": valid,
        "duplicate_groups": index.duplicates(),
        "top_experiences": chosen, "consolidated_state": state.to_json(),
        "teleport_plan": plan.to_json(), "metrics": metrics(),
    }
    final_metrics = metrics()
    result["metrics"] = final_metrics
    append_jsonl(METRICS_PATH, result)
    save_json(STATE_ROOT / "demo.json", result)
    return result


class KVProxy:
    """OpenAI-compatible in-VM proxy with packetized KV bookkeeping."""

    def __init__(self, upstream: str, listen: str, port: int):
        self.upstream = upstream
        self.listen = listen
        self.port = port

    def http_json(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
        import urllib.error
        import urllib.request
        data = canon(body) if body is not None else None
        req = urllib.request.Request(self.upstream + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                raw = response.read()
                try:
                    return response.status, json.loads(raw)
                except Exception:
                    return response.status, raw.decode(errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode(errors="replace")
        except Exception as exc:
            return 502, str(exc)

    def serve(self) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                pass

            def _reply(self, status: int, value: Any) -> None:
                raw = canon(value)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if self.path == "/binetic/kv/metrics":
                    self._reply(200, metrics())
                    return
                if self.path == "/binetic/kv/demo":
                    self._reply(200, load_jsonl(METRICS_PATH)[-1] if METRICS_PATH.exists() else {})
                    return
                status, value = outer.http_json("GET", self.path)
                if isinstance(value, (dict, list)):
                    self._reply(status, value)
                else:
                    self.send_response(status)
                    self.end_headers()
                    self.wfile.write(str(value).encode())

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw or b"{}")
                except Exception:
                    body = {}
                if self.path == "/binetic/kv/query":
                    try:
                        self._reply(200, store_query(body.get("kind", "prefix"), body.get("value", {})))
                    except Exception as exc:
                        self._reply(400, {"error": str(exc)})
                    return
                if self.path == "/binetic/kv/bench":
                    self._reply(200, proxy_bench(int(body.get("n", 512)), int(body.get("rounds", 3))))
                    return
                if self.path == "/binetic/kv/record":
                    slot = Slot.from_json(body["slot"])
                    self._reply(200, record_slot(slot, **body.get("options", {})))
                    return
                status, value = outer.http_json("POST", self.path, body)
                if isinstance(value, (dict, list)):
                    self._reply(status, value)
                else:
                    self.send_response(status)
                    self.end_headers()
                    self.wfile.write(str(value).encode())

        ThreadingHTTPServer((self.listen, self.port), Handler).serve_forever()


def main() -> None:
    parser = __import__("argparse").ArgumentParser(prog="binetic-kv")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    sub.add_parser("metrics")
    query = sub.add_parser("query")
    query.add_argument("kind")
    query.add_argument("--value", default="{}")
    bench = sub.add_parser("bench")
    bench.add_argument("--n", type=int, default=512)
    bench.add_argument("--rounds", type=int, default=3)
    proxy = sub.add_parser("proxy")
    proxy.add_argument("--upstream", default="http://127.0.0.1:8645")
    proxy.add_argument("--listen", default="127.0.0.1")
    proxy.add_argument("--port", type=int, default=8646)
    args = parser.parse_args()
    if args.cmd == "demo":
        print(json.dumps(cmd_demo(), indent=2, sort_keys=True))
    elif args.cmd == "metrics":
        print(json.dumps(metrics(), indent=2, sort_keys=True))
    elif args.cmd == "query":
        print(json.dumps(store_query(args.kind, json.loads(args.value)), indent=2, sort_keys=True))
    elif args.cmd == "bench":
        print(json.dumps(proxy_bench(args.n, args.rounds), indent=2, sort_keys=True))
    elif args.cmd == "proxy":
        KVProxy(args.upstream, args.listen, args.port).serve()


if __name__ == "__main__":
    main()
