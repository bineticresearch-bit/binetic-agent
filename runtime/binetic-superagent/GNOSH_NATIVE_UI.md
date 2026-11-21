# Binetic Agent TUI is the main Binetic interface

The web panel is now secondary/observer-only. The main operator interface is the Binetic Agent TUI.

## Launch the main interface

```bash
export PATH=/root/agent-workspace/bin:$PATH
binetic-binetic-agent
```

This runs:

```bash
binetic-agent \
  --cwd /root/agent-workspace/binetic-superagent \
  --append-system-prompt-file /root/agent-workspace/binetic-superagent/BINETIC_SYSTEM_PROMPT.md
```

## Native menu / command palette

A user-invocable skill was installed at:

```text
/root/.config/binetic_agent/skills/binetic-superagent/SKILL.md
```

Inside Binetic Agent, use the command palette and select:

```text
user:binetic-superagent
```

Then ask for any control:

```text
boot everything
show status
verify B-PCM
show the certificate
project views
run adversarial tests
```

## SessionStart hook

A native SessionStart hook injects live status every time Binetic Agent starts a session.

Config:

```text
/root/agent-workspace/binetic-superagent/binetic-agent.json
```

Hook:

```text
/root/agent-workspace/binetic-superagent/binetic-agent-hooks/binetic-session-start.sh
```

The project config also pre-allows the Binetic control commands.

Verified hook output includes:

```text
BINETIC SUPERAGENT MAIN INTERFACE ACTIVE
Binetic Agent is the main operator interface. The web app is secondary/observer only.
status: {...version 0.2.0...}
bpcm: valid=True events=19 chain_root=98a0c307479efc6714d719db86357f6563067d0020197777be2facef6d1430b4
```

## Native controls

Inside Binetic Agent, the assistant can run:

```bash
# Boot all backing services.
bash /root/my-agent/start.sh

# Superagent state.
binetic-superagent status

# B-PCM verification.
binetic-cognition --state-dir /root/agent-workspace/binetic-superagent/bpcm_state verify --level L3

# Certificate.
binetic-cognition --state-dir /root/agent-workspace/binetic-superagent/bpcm_state certificate --level L3

# Materialized views.
binetic-cognition --state-dir /root/agent-workspace/binetic-superagent/bpcm_state project

# Adversarial suite.
python3 /root/agent-workspace/binetic-superagent/tests/test_bpcm.py
```

## Visualization surfaces

B-PCM views remain available as files that can be opened natively in Binetic Agent:

```text
/root/agent-workspace/binetic-superagent/bpcm_state/views/
```

## Important distinction

I previously added the control surface to the web app. That was the wrong target. The implementation now treats the Binetic Agent TUI as primary and the web app as a secondary observer.
