# B-PCM v4 — Revealed Extended Canonical Packet Machine

This is a clean rewrite of the packet core, not a patch on v1.

## Four fixes requested

### 1. Every packet carries the full envelope

`packet_body()` is centralized. Receipts no longer rely on parsed payload structure to know the header layout. Every output packet carries:

```text
version
kind
op
state_before
state_after
payload_length
payload_sha256
base.words
base.bw
base.routing_qwords
route_id / vport_id / model_id / layer_id / block_id / op_code
packet_hash
```

Replay also verifies the attached `envelope` against `body_hash`.

### 2. Pipelining lives in byte pockets, not injected two-level objects

`bpcm_packet.py` packs raw bytes into 8-lane byte pockets and 64-bit words with qword views. The router and payload are real bytes:

```text
pack_bytes(...)
pack_json(...)
router_qwords
body_qwords
payload_bytes
raw_hex
raw_sha256
```

### 3. Tool receipts are in-band tool packets

`TOOL_RESULT` emits an embedded in-band tool receipt with:

```text
id
input
output.status
output.source
bits: byte-level bit packet
receipt: SHA-256
```

No timestamp or other nondeterministic value is included. Replay and certificate generation are deterministic.

### 4. Codes are explicit

```text
OPCODE: H1 PACKET_DELTA, 20 COLLAPSE, 30 BROADCAST, 55 WRITE, AA READ, FF SYNC
UCODES: AGI_STEP, AGI_TOOL, AGI_COMMIT, AGI_POLICY
```

Events carry explicit `ucode`, `opcodes`, and `op_code`.

## `state_before` / `state_after`

Now they are packet roots, computed by canonical hashing of the full state projection:

```text
state_root = SHA256(canonical_json({ envelope: {...}, state: {...} }))
```

## Verified clean demo

```json
{
  "valid": true,
  "events": 11,
  "issues": [],
  "chain_root": "92941110427c94870d03cdb46143513b81cc9301fa56d81f7794e7172f0b5472",
  "state_root": "257bfc8da9bcdccdd424bc6f6b62edb87438cc63378946cc639e0db344f1af3e"
}
```

Certificate:

```json
{
  "version": 4,
  "profile": "extended-canonical-v4",
  "packet_bytes": 5007,
  "tool_receipt_root": "0af173e08b98ad4c823272d9193a69f086bec92d33925ab446e14405c9ed64ef",
  "l0": true,
  "l1": true,
  "l2": true,
  "l3": true,
  "certificate_hash": "887edef79df235877aa3c52a5ca7274ed0b03a15efc85899bffdcce3bae0afee"
}
```

## Files

- `bpcm.py`
- `bpcm_packet.py`
- `tests/test_bpcm_v4.py`
- `BPCM_V4.md`
- `bpcm_state/views/envelope.json`
- `bpcm_state/views/bit_packets.json`
- `bpcm_state/views/ucodes.json`

## Honest boundary

B-PCM v4 verifies externalized packet-state transitions. It does not replay hidden model reasoning and is not proof of consciousness.
