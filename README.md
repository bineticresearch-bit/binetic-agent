# Binetic Agent — Creator Edition

Private creator build of the Binetic Agent TUI and runtime.

Binetic Agent is the Gnosh/Crush agent harness packaged with the Binetic runtime layered in: receipted tool use, BPCM/KV packet routing, echo phase-lock, live action terminal, AGI kernel, local/remote model routing, and Mac/Linux launchers.

> This repository is private because it is the creator version.

## Layout

- `binetic-agent/` — vendored upstream TUI source, kept close to upstream for build stability
- `runtime/binetic-superagent/` — Binetic runtime code and launchers
- `scripts/` — build and check scripts
- `docs/` — quickstart and creator notes

## Build

```bash
./scripts/build.sh
./release/binetic-agent-linux-arm64 --version
```

## Run

```bash
export PATH="$PWD/bin:$PWD/release:$PATH"
binetic-agent
```

## Model route

```text
binetic-agent -> 127.0.0.1:8645/v1 -> 127.0.0.1:8001
```

Configured model:

```text
tencent/hy4-flash:free
```

## Privacy

No credentials, model weights, live DBs, personal state, or session transcripts are included.
