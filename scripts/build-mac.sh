#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/binetic-agent"
GOOS=darwin GOARCH=arm64 go build -trimpath -o "$ROOT/release/binetic-agent-darwin-arm64" .
echo "$ROOT/release/binetic-agent-darwin-arm64"
