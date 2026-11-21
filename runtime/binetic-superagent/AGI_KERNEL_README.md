# Binetic AGI Kernel v0.1

## What exists now

```text
/root/agent-workspace/binetic-superagent/agi_kernel.py
/root/agent-workspace/binetic-superagent/evolve_agi.py
/root/agent-workspace/binetic-superagent/agi_loop_start.sh
```

This is a **bounded autonomous cognition prototype**. It is not finished AGI and not a consciousness claim.

## Kernel loop

Each cycle:

```text
observe -> plan -> act -> evaluate -> learn -> receipt
```

World model fields:

```text
receipts_valid
bpcm_valid
tests_passing
fabric_ready
inference_ready
identity_bound
```

Goals:

```text
keep receipts valid
keep B-PCM valid
keep tests passing
keep free fabric ready
keep inference ready
keep identity/genesis hashes present
```

Actions are whitelisted:

```text
verify_receipts
verify_bpcm
run_tests
start_fabric
start_inference
bind_identity
propose_improvement
```

## Bounded self-improvement

```text
evolve_agi.py
```

Runs kernel cycles, computes stability, and may only adjust goal priority within bounds:

```text
allowed:
  goal_priority_within_bounds
  append_receipt
  create_proposal

forbidden:
  code self-editing
  honesty changes
  safety changes
  creator autonomy changes
  sandbox escape
  internet DNA search
  consciousness/godlike/universal-AGI claims
  unbounded self-modification
```

## Binetic Agent controls

New controls:

```text
agi-status
agi-cycle
agi-evolve
agi-loop
```

Dashboard line:

```text
AGI: kernel-v0.1 cycle=... reward=... claim=prototype
```

Start loop:

```bash
/root/agent-workspace/binetic-superagent/agi_loop_start.sh
```

Manual cycle:

```bash
python3 /root/agent-workspace/binetic-superagent/agi_kernel.py cycle
```

Status:

```bash
python3 /root/agent-workspace/binetic-superagent/agi_kernel.py status
```

## Current claim

```text
bounded autonomous cognition prototype; not AGI
```

The honest next steps are more capabilities and harder evaluations, not renaming this to AGI.
