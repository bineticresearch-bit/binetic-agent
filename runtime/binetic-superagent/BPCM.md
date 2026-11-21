# B-PCM v1 — Proof-Carrying Cognition Stream

B-PCM turns cognition into a replayable, hash-chained packet stream.

## What exists

- `bpcm.py`: deterministic event/receipt runtime
- `tests/test_bpcm.py`: adversarial suite
- `bpcm_state/bpcm.jsonl`: example stream
- `bpcm_state/views/*.json`: materialized cognition views
- `binetic-cognition`: command wrapper
- `binetic-superagent cognition ...`: launcher integration

## Event ops

```text
INTENT_OPEN
MEM_TODO_ADD
MEM_FACT_SET
FRAME_PUSH
FRAME_POP
TOOL_CALL
TOOL_RESULT
SWARM_TODO_CLAIM
SWARM_TODO_DONE
SWARM_TODO_RELEASE
POLICY_PROPOSE
POLICY_VERIFY
POLICY_ADMIT
POLICY_REJECT
FINAL_CLAIM
```

## Invariants enforced

- Hash envelope: canonical JSON `body_hash`, `prev_hash`, seq continuity.
- Replay: `state_before`/`state_after` recomputed from event semantics.
- Frames: cannot pop an inactive or non-top frame; cannot pop with open descendants; cannot pop with unmatched tool calls.
- Tool evidence: tool results require known call IDs and output hashes.
- Facts and claims: require evidence roots already present in the stream.
- Swarm: only one active lease per todo; done/release must be by lease owner.
- Policy: cannot admit losing patches or patches with invariant violations.

## Certificate

The emitted cognition certificate commits to:

```text
intent_hash
plan_root
frame_root
memory_root
tool_result_root
claim_root
final_state_root
chain_root
packet_count
receipt_bytes
L0/L1/L2/L3 flags
```

## Commands

```bash
export PATH=/root/agent-workspace/bin:$PATH

binetic-superagent status
binetic-superagent cognition demo
binetic-superagent cognition verify --level L3
binetic-superagent cognition certificate --level L3
binetic-superagent cognition project
binetic-superagent cognition-test
```

## Verified evidence

Final demo run:

```json
{
  "valid": true,
  "events": 19,
  "issues": [],
  "chain_root": "98a0c307479efc6714d719db86357f6563067d0020197777be2facef6d1430b4",
  "state_root": "5a4f9bc99ca1d70657b0c2290b45a93ee9da3f78ab0a51fcec5cbe352b1a38d2"
}
```

Certificate:

```json
{
  "certificate_hash": "2a5de26dec2f8990a4a2b32897e5690033579c91ed4b9bbb79848b5ac8259c14",
  "level0": true,
  "level1": true,
  "level2": true,
  "level3": true
}
```

Adversarial suite:

```text
PASS tamper_hash_chain
PASS illegal_frame_pop
PASS unsupported_final_claim
PASS duplicate_swarm_claim
PASS unsafe_policy_admit
ALL BPCM TESTS PASSED
```

## Honest boundary

B-PCM verifies externalized cognition transitions. It does not replay hidden LLM internal reasoning and is not a proof of consciousness.
