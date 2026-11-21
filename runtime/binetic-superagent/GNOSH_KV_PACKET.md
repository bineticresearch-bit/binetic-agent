# Kapitsa KV packets wired into Binetic Agent

## Source read

I read Kapitsa's explicit packetized KV research and implementation basis:

- `docs/research/packetized-kv-cache.md`
- `src/engine/packet_kv.h`
- `tests/packet_kv_test.cpp`
- `src/engine/engine_disk.cpp` exact receipt integration
- local A/B logs: `real_kv_ab_1k.log`, `real_kv_ab_4k_correct.log`, `real_kv_ab_16k.log`, `real_attn_bench.log`, `real_bw_floor.log`

Kapitsa's central rule:

```text
bits route, bytes hold data
```

The routing plane carries V4/V6 coordinates, channel bits, branch bits, and receipts. The data plane remains opaque KV bytes. The planes do not interpret each other.

## What Kapitsa actually claims

From `docs/research/packetized-kv-cache.md`:

- The packetized KV implementation is CPU-only format/index prototype work.
- Exact mode is same-token by design: routing, receipts, reward/drive annotations, dedup and prefetch only.
- Bit-plane and quantization modes are separate; they can change tokens.
- No GPU inference speed claim is made by the research doc.
- Disk-cache exact receipts are wired and tested on CPU; GPU token identity is not claimed there.

This distinction is preserved.

## What I recreated in Binetic/Binetic Agent

File:

```text
/root/agent-workspace/binetic-superagent/binetic_kv.py
```

Implemented:

- V4 register index: `mode(2)|type(3)|sequence(9)|index(18)`
- V6 address: `node_prefix(48)|bank(16)|v4_index(32)|lane_offset(32)`
- 64-bit Route: V4 high half, channel mask and branch mask low half
- Slot: address + route + lane metadata + opaque bytes
- PrefixQuery over masked V4 coordinates
- `popcount16` / `best_branch` SWAR decision
- exact path block-position extension using `lane_offset` as high bits
- bit-plane decomposition and lossless zero-plane elision
- deterministic SHA-256 receipt over route, address, lane metadata and payload
- state chaining through `prev_hash`, `state_before`, `state_after`
- ReceiptIndex lookup by kind/channel/op/block/model/layer/lane/hash/prefix
- duplicate detection and branch ranking without payload reads
- reward/drive annotations committed in receipts
- ConsolidatedState digest and reward-biased prefetch ordering
- TeleportPlan with consolidated-record bypass and branch slices

## Binetic Agent wiring

New commands:

```bash
binetic-kv-start
binetic-kv demo
binetic-kv metrics
binetic-kv bench
binetic-cockpit control kv-demo
binetic-cockpit control kv-bench
```

Palette skill:

```text
user:binetic-kv
```

Dashboard line:

```text
KV: VALID slots=5 root=...
```

Exact-mode proxy:

```text
127.0.0.1:8646 -> 127.0.0.1:8645 -> model server
```

The proxy adds Binetic KV endpoints and forwards OpenAI-compatible traffic unchanged. It does not load a model or touch a GPU.

## Verification

All Binetic KV tests pass:

```text
PASS v4_v6_route
PASS slot_receipt_and_tamper
PASS bitplanes_lossless_and_elision
PASS index_consolidation_teleport
PASS cli_demo
ALL BINETIC KV TESTS PASSED
```

Demo result:

```text
slots: 5
valid: true
receipt chain root: b7935565192cf3537ca5ad5a26a28d6946d989645bda1ad77d83ed406f28d1eb
state root: 071490c963c0692057c56bc76b8d81df8392c17e1ae8b6f16deb5aeead47df2a
teleport fanout: 3
```

## Kapitsa measurements read from local logs

These are Kapitsa machine logs, not Binetic/Binetic Agent benchmarks:

- 1K prompt: ~471-473 tok/s prefill, ~40 tok/s decode; int8 A/B essentially identical at 1K.
- 4K correct prompt: ~488-489 tok/s prefill, ~40 tok/s decode; int8 essentially identical.
- 16K: fp16 ~361 tok/s prefill / ~36 tok/s decode; int8 ~308 tok/s / ~31 tok/s, so int8 is worse at 16K on that run.
- attention: ~15-18 TFLOP/s at 4K-32K prefill shapes.
- bandwidth floor: ~690-720 GB/s.

I am not presenting these as Binetic Agent results. They are the measured source context.

## Novel next step

The novel Binetic path is not “copy the KV cache.” It is:

```text
KV rows become routable receipted slots
branch masks become packed candidate decisions
reward/drive metadata commits into receipt bodies
consolidated slots bypass transport lanes
remaining slots fan out by branch bit
Binetic Agent sees the whole thing natively in the command palette/dashboard
```

This changes the control plane first. Any tok/s gain must be proven with a real engine A/B.

## Honest boundary

This is a CPU/format/proxy recreation wired into Binetic Agent. It is not a GPU kernel, not a model-output identity proof, and not a measured inference speedup by itself. The fast path is designed for in-transport decisions without payload reads; the speed claim remains unproven until a real engine A/B measures it.
