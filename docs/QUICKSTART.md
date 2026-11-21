# Binetic Agent Quickstart

## Prerequisites

- Go 1.23+
- Python 3.10+
- Node.js 18+ for the model router
- tmux for the live action terminal

## Build

```bash
./scripts/build.sh
```

## Run

```bash
export PATH="$PWD/bin:$PWD/release:$PATH"
binetic-agent
```

## Model route

Start Hermes on port 8001, then:

```bash
binetic-agent-router
```

The TUI uses:

```text
127.0.0.1:8645/v1
```

with model:

```text
tencent/hy4-flash:free
```

## Live terminal

```bash
./bin/binetic-live-terminal
tmux attach -t binetic-live
```
