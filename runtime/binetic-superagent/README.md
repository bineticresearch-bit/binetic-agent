# Binetic Superagent

A receipted adapter layer around `binetic-agent.pandora`, the Convex `my-agent` entity substrate, and the Binetic packet/receipt architecture.

## Installed paths

- Binetic Agent upstream clone: `/root/agent-workspace/binetic-agent.pandora` at commit `9733a4ce2b5182d59a334c7cb7428954af8deb73`
- Binetic Agent binary: `/root/agent-workspace/bin/binetic-agent`
- Binetic superagent launcher: `binetic-superagent` on PATH via `/root/agent-workspace/bin`
- Binetic system prompt: `BINETIC_SYSTEM_PROMPT.md`
- Simple receipt chain: `state/receipts.jsonl`
- B-PCM cognition stream: `bpcm_state/bpcm.jsonl`
- B-PCM projected views: `bpcm_state/views/*.json`
- Binetic Agent runtime config: `binetic-agentrc` (trust this folder in Binetic Agent if you want it applied)

## Major components

### 1. Binetic Agent adapter

Binetic Agent is used as the execution harness:

- frames: `mem.Push` / `mem.Pop`
- durable GnoVM `mem`
- swarm sessions on one plan
- fail-closed hooks
- security-first tool boundaries
- MCP/LSP/model provider integration

The Binetic system prompt is injected before every Binetic Agent run.

### 2. Simple receipt chain

`binetic-receipt-append` and `binetic-verify-receipts` implement canonical JSON + SHA-256 hash chaining for general runtime events.

### 3. B-PCM v1

`binetic-cognition` implements **Proof-Carrying Cognition Streams**:

```text
intent → todos → frames → tool calls → memory facts
→ swarm leases → policy mutation gates → final claims
→ replay verifier → cognition certificate → materialized views
```

Details and verified evidence are in `BPCM.md`.

## Usage

```bash
export PATH=/root/agent-workspace/bin:$PATH

# Runtime status.
binetic-superagent status

# Run through Binetic Agent when a provider/model is configured.
binetic-superagent run "read this repo and propose a plan in mem"

# Simple receipts.
binetic-receipt-append append --kind result --payload '{"event":"test"}'
binetic-verify-receipts

# B-PCM proof-carrying cognition.
binetic-superagent cognition demo
binetic-superagent cognition verify --level L3
binetic-superagent cognition certificate --level L3
binetic-superagent cognition project
binetic-superagent cognition-test
```

## Verified checks performed

- Binetic Agent built successfully from commit `9733a4ce2b51` with Go 1.27.0.
- `binetic-agent --help` and `binetic-agent doctor` executed successfully as binaries.
- `binetic-superagent status` returns adapter, state, and B-PCM paths.
- `binetic-superagent run` correctly uses offline fallback while no provider key is configured.
- Simple receipt chain verifies valid.
- Tampering with simple receipts is rejected.
- B-PCM demo produces a valid 19-event cognition stream.
- B-PCM certificate hash: `2a5de26dec2f8990a4a2b32897e5690033579c91ed4b9bbb79848b5ac8259c14`
- B-PCM adversarial suite passes all five invariant tests.

## Honest boundaries

- This is a working adapter and cognition-proof harness, not proof of consciousness.
- Receipts are tamper-evident logs certified by SHA-256 canonical JSON; they are not ZK proofs or hardware attestation.
- B-PCM verifies externalized cognition transitions, not hidden LLM internal reasoning.
- Binetic Agent needs a configured provider/model for real model calls; no external API key is bundled. The `binetic-agentrc` points at a local llama.cpp endpoint, but it must be running separately.
- The Convex entity state remains the authority for internal affect/drive state; Binetic Agent is the advanced execution harness layered on top.
