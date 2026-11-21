#!/usr/bin/env bash
set -euo pipefail

# Append a human-readable Binetic action event to the live terminal feed.
ROOT=/root/agent-workspace/binetic-superagent
LIVE="$ROOT/live_view"
mkdir -p "$LIVE"
chmod 700 "$LIVE"
FEED="$LIVE/actions.feed"
TS="$(date -Iseconds)"
if [ "$#" -eq 0 ]; then
  MSG="idle"
else
  MSG="$*"
fi
printf '%s │ %s\n' "$TS" "$MSG" >>"$FEED"
chmod 600 "$FEED"
printf '%s\n' "$FEED"
