#!/usr/bin/env python3
"""Bit-packet layer for B-PCM v4: byte pockets, lanes, masks, and qword packing."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

WORD_BITS = 64
BYTE_BITS = 8
LANES_PER_WORD = 8
MASK32 = (1 << 32) - 1


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class Pocket:
    lane: int
    value: int

    def __post_init__(self) -> None:
        if not 0 <= self.lane < LANES_PER_WORD:
            raise ValueError("lane out of range")
        if not 0 <= self.value <= 0xFF:
            raise ValueError("byte value out of range")

    def shifted(self) -> int:
        return (self.value & 0xFF) << (self.lane * BYTE_BITS)


@dataclass(frozen=True)
class Packet64:
    word: int

    def qwords(self) -> list[int]:
        return [
            (self.word >> 48) & 0xFFFF,
            (self.word >> 32) & 0xFFFF,
            (self.word >> 16) & 0xFFFF,
            self.word & 0xFFFF,
        ]

    def bytes(self) -> bytes:
        return self.word.to_bytes(8, "big", signed=False)

    def hex(self) -> str:
        return self.word.to_hex(8)


def pack_pockets(pockets: list[Pocket]) -> Packet64:
    """Pack up to 8 byte pockets into one 64-bit word by lane."""
    used = set()
    word = 0
    for pocket in pockets:
        if pocket.lane in used:
            raise ValueError(f"duplicate lane {pocket.lane}")
        used.add(pocket.lane)
        word |= pocket.shifted()
    return Packet64(word)


def routing_pockets(route_id: int, vport_id: int, model_id: int, layer_id: int, block_id: int, op_code: int) -> list[Pocket]:
    """14-byte routing header mapped to lanes cyclically."""
    values = [
        (route_id >> 8) & 0xFF, route_id & 0xFF,
        (vport_id >> 8) & 0xFF, vport_id & 0xFF,
        (model_id >> 8) & 0xFF, model_id & 0xFF,
        (layer_id >> 8) & 0xFF, layer_id & 0xFF,
        (block_id >> 24) & 0xFF, (block_id >> 16) & 0xFF,
        (block_id >> 8) & 0xFF, block_id & 0xFF,
        (op_code >> 8) & 0xFF, op_code & 0xFF,
    ]
    return [Pocket(index % LANES_PER_WORD, value) for index, value in enumerate(values)]


def pack_routing(route_id: int, vport_id: int, model_id: int, layer_id: int, block_id: int, op_code: int) -> list[Packet64]:
    pockets = routing_pockets(route_id, vport_id, model_id, layer_id, block_id, op_code)
    return [pack_pockets(pockets[i:i + LANES_PER_WORD]) for i in range(0, len(pockets), LANES_PER_WORD)]


def pack_bytes(data: bytes, *, route_id: int = 0, vport_id: int = 0, model_id: int = 0, layer_id: int = 0, block_id: int = 0, op_code: int = 0) -> dict[str, Any]:
    """Byte-stream packet with both raw bytes and lane-packed qword view."""
    header = pack_routing(route_id, vport_id, model_id, layer_id, block_id, op_code)
    body_packets: list[Packet64] = []
    for offset in range(0, len(data), LANES_PER_WORD):
        chunk = data[offset:offset + LANES_PER_WORD]
        body_packets.append(pack_pockets([Pocket(index, byte) for index, byte in enumerate(chunk)]))
    raw = b"".join(packet.bytes() for packet in header + body_packets)
    return {
        "kind": "bpcm/bitpacket.v4",
        "byte_length": len(data),
        "payload_bytes": data.hex(),
        "raw_hex": raw.hex(),
        "raw_sha256": sha256_hex(raw),
        "router_qwords": [packet.qwords() for packet in header],
        "body_qwords": [packet.qwords() for packet in body_packets],
        "packet_count": len(header) + len(body_packets),
    }


def pack_json(value: Any, **routing: Any) -> dict[str, Any]:
    return pack_bytes(canonical_json(value), **routing)


def qword(packet: int) -> tuple[int, int, int, int]:
    """Split a 64-bit word into four qwords (16 bits each)."""
    return (
        (packet >> 48) & 0xFFFF,
        (packet >> 32) & 0xFFFF,
        (packet >> 16) & 0xFFFF,
        packet & 0xFFFF,
    )


def masks(words: list[Packet64]) -> dict[str, str]:
    """Cheap coarse grain masks kept in-band for projections."""
    all_words = [packet.word for packet in words]
    return {
        "parity": "".join("1" if (word & 1) else "0" for word in all_words),
        "low32_xor": hex(_xor([word & MASK32 for word in all_words])),
        "hash": sha256_hex(b"".join(word.to_bytes(8, "big") for word in all_words)),
    }


def _xor(values: list[int]) -> int:
    out = 0
    for value in values:
        out ^= value
    return out
