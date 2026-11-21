#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/binetic-agent"
go build -trimpath -o "$ROOT/release/binetic-agent-linux-arm64" .
echo "$ROOT/release/binetic-agent-linux-arm64"
