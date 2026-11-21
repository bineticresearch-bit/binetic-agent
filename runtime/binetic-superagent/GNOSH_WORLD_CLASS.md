# Binetic Binetic Agent TUI — world-class interface layer

The Binetic Agent TUI is the main interface. This is the native control room added directly to Binetic Agent.

## Launch

```bash
export PATH=/root/agent-workspace/bin:$PATH
binetic-binetic-agent
```

`binetic-binetic-agent` bootstraps controls, trusts the project config, verifies receipt/B-PCM state, then launches Binetic Agent with the Binetic system prompt and native hooks.

## Doctor status — all green

```text
✓ binetic-agent v0.0.0-20261110232025-9733a4ce2b51
✓ config
✓ project settings trusted
✓ provider binetic-local: 1 models
✓ large model: binetic-local/binetic-local
✓ small model: binetic-local/binetic-local
✓ hooks: PreToolUse 1, PostToolUse 1, UserPromptSubmit 1, SessionStart 1, Stop 1, SessionEnd 1
✓ ripgrep: /usr/bin/rg
✓ data: /root/agent-workspace/binetic-superagent/.binetic-agent
```

## Native command palette skills

Press `ctrl+p`, then choose:

```text
user:binetic-control
user:binetic-verify
user:binetic-memory
user:binetic-superagent
```

### binetic-control

Single entry point for the control room:

```bash
binetic-cockpit doctor
binetic-cockpit dashboard
binetic-cockpit verify
binetic-cockpit verify-deep
binetic-cockpit control boot
binetic-cockpit control status
binetic-cockpit control demo
binetic-cockpit control certificate
binetic-cockpit control project
binetic-cockpit control test
binetic-cockpit receipt '{"message":"..."}'
```

### binetic-verify

Strict completion gate:

```text
no ok:true from binetic-cockpit verify → no "done" claim
```

### binetic-memory

Binetic Agent-native memory protocol:

```text
mem.Push(todo) → work → mem.Pop(todo, evidence)
mem.Next() for swarm leases
durable conclusions as facts
receipts for accepted state transitions
```

## Lifecycle hooks

Configured in `binetic-agent.json`:

- `SessionStart` → control-room dashboard + Binetic status
- `UserPromptSubmit` → live status/context
- `PreToolUse` → receipt command allow-list
- `PostToolUse` → post-tool receipt
- `Stop` → strict verification gate when `BINETIC_AGENT_REQUIRE_VERIFY=1`
- `SessionEnd` → session receipt

## Custom theme

Theme file:

```text
/root/.config/binetic_agent/themes/binetic-cosmos.json
```

Activated in `binetic-agent.json`:

```json
{ "tui": { "active_theme": "binetic-cosmos" } }
```

Design intent:

- deep navy base
- cyan/blue primary
- violet secondary
- emerald success/accent
- high-contrast status colors

## B-PCM v4

The control room is backed by B-PCM v4:

```text
full envelope on every output packet
byte-pocket bit lanes and qword views
in-band tool receipts with typed ucodes
SHA-256 packet hashes
state_before/state_after as packet roots
```

Verified clean demo:

```json
{
  "valid": true,
  "events": 11,
  "chain_root": "92941110427c94870d03cdb46143513b81cc9301fa56d81f7794e7172f0b5472",
  "state_root": "257bfc8da9bcdccdd424bc6f6b62edb87438cc63378946cc639e0db344f1af3e"
}
```

Certificate:

```text
887edef79df235877aa3c52a5ca7274ed0b03a15efc85899bffdcce3bae0afee
```

## Verified commands

```bash
binetic-cockpit bootstrap
binetic-cockpit dashboard
binetic-cockpit verify
binetic-cockpit verify-deep
python3 /root/agent-workspace/binetic-superagent/tests/test_bpcm_v4.py
```

All currently return clean/valid results.

## Honest boundary

This is a world-class Binetic Agent-native operator layer. It is not proof of consciousness and does not replay hidden model reasoning. It externalizes and verifies state transitions.
