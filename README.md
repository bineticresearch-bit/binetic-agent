# Binetic Agent — Creator Edition

Private creator build of the Binetic Agent TUI and runtime.

Binetic Agent is a rebranded, self-contained fork of the Gnosh/Crush agent harness with the Binetic runtime layered in: receipted tool use, BPCM/KV packet routing, echo phase-lock, live action terminal, AGI kernel, local/remote model routing, and Mac/Linux launchers.

> This repository is private because it is the creator version.

## What is included

- `binetic-agent/` — vendored Go TUI source
- `runtime/binetic-superagent/` — Python/runtime superagent code
- `docs/` — creator quickstart and architecture notes
- `scripts/` — build and check scripts
- `release/` — release artifact staging
- `bin/` — generated launchers and release helpers

## Quickstart

### Build from source

```bash
./scripts/build.sh
./release/binetic-agent-linux-arm64 --version
```

### Run the runtime with the bundled config

```bash
export PATH="$PWD/bin:$PWD/release:$PATH"
binetic-agent --cwd runtime/binetic-superagent \
  --append-system-prompt-file runtime/binetic-superagent/BINETIC_SYSTEM_PROMPT.md
```

### Live action terminal

```bash
./bin/binetic-live-terminal
tmux attach -t binetic-live
```

## Model route

The private creator config keeps the stable local route:

```text
binetic-agent -> 127.0.0.1:8645/v1 -> 127.0.0.1:8001
```

Configured model:

```text
tencent/hy4-flash:free
```

## Privacy boundary

This repo intentionally excludes:

- model weights
- compiled Linux/macOS binaries
- live Gnosh/Convex databases
- personal identity/DNA seeds
- session transcripts and live logs
- tokens/credentials

Build artifacts and secrets must stay out of commits.
