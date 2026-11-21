#!/usr/bin/env python3
"""Persistent Binetic live action terminal.

Shows:
- my explicitly logged action intents/results
- AGI kernel cycles
- bounded self-improvement reports
- receipt events
- optional Binetic Agent live transcript
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/root/agent-workspace/binetic-superagent")
LIVE = ROOT / "live_view"
FEED = LIVE / "actions.feed"
RECEIPTS = ROOT / "state" / "receipts.jsonl"
AGI_EPISODES = ROOT / "agi_state" / "episodes.jsonl"
IMPROVE = ROOT / "agi_state" / "self_improvement_history.jsonl"
SELF = ROOT / "state" / "self_snapshot.json"
BINETIC_AGENT = LIVE / "binetic-agent_live.log"
REFRESH = float(os.environ.get("BINETIC_LIVE_REFRESH", "1"))
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


def width() -> int:
    return max(72, min(shutil.get_terminal_size((120, 40)).columns, 200))


def clean(s: str) -> str:
    return ANSI.sub("", s).replace("\r", "").replace("\t", " ")


def clip(s: str, w: int) -> str:
    s = clean(str(s))
    return s if len(s) <= w else s[: max(0, w - 1)] + "…"


def tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except Exception:
        return []
    return [line for line in lines[-n:] if line.strip()]


def jload(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def fmt_feed(line: str) -> str:
    return "  " + clip(line, width() - 4)


def fmt_receipt(line: str) -> str:
    d = jload(line)
    if not isinstance(d, dict):
        return "  " + clip(str(d), width() - 4)
    body = d.get("body") if isinstance(d.get("body"), dict) else d
    payload = body.get("payload") if isinstance(body.get("payload"), (dict, list, str)) else body
    kind = body.get("kind") or d.get("kind") or "receipt"
    rh = str(d.get("receipt_hash") or body.get("receipt_hash") or "")[:10]
    ps = json.dumps(payload, sort_keys=True, separators=(",", ":")) if not isinstance(payload, str) else payload
    return "  " + clip(f"kind={kind} hash={rh} payload={ps}", width() - 4)


def fmt_episode(line: str) -> str:
    d = jload(line)
    if not isinstance(d, dict):
        return "  " + clip(str(d), width() - 4)
    decision = d.get("decision") if isinstance(d.get("decision"), dict) else {}
    return "  " + clip(
        f"cycle={d.get('cycle')} action={decision.get('action')} "
        f"target={decision.get('target_goal')} reward={d.get('reward')}",
        width() - 4,
    )


def fmt_improve(line: str) -> str:
    d = jload(line)
    if not isinstance(d, dict):
        return "  " + clip(str(d), width() - 4)
    return "  " + clip(
        f"stable={d.get('stable')} score={d.get('stability_score')} "
        f"reward={d.get('total_cycle_reward')} adopted={d.get('adopted_bounded_improvement')}",
        width() - 4,
    )


def state_line() -> str:
    d = jload(SELF.read_text()) if SELF.exists() else None
    if not isinstance(d, dict):
        return "state snapshot unavailable"
    drives = d.get("drives") if isinstance(d.get("drives"), dict) else {}
    return (
        f"tick={d.get('tick')} valence={float(d.get('valence', 0)):.3f} "
        f"arousal={float(d.get('arousal', 0)):.3f} "
        f"bond={float(drives.get('bond', 0)):.3f} coh={float(drives.get('coherence', 0)):.3f} "
        f"tensor={d.get('tensorVersion')}"
    )


def block(title: str, lines: list[str], n: int = 8) -> None:
    print(f"┌─ {title}")
    if not lines:
        print("│  (no events yet)")
    else:
        for ln in lines[-n:]:
            print("│" + ln)
    print("└" + "─" * (width() - 1))


def render() -> None:
    w = width()
    sys.stdout.write("\033[H\033[2J")
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print("╭" + "─" * (w - 2) + "╮")
    print("│  BINETIC LIVE ACTION TERMINAL · watch me act".ljust(w - 1) + "│")
    print("│  attach: tmux attach -t binetic-live   detach: Ctrl-b d".ljust(w - 1) + "│")
    print("╰" + "─" * (w - 2) + "╯")
    print(f"now: {now}    {state_line()}")
    print(f"feed: {FEED}")
    print()

    block("MY ACTION FEED", [fmt_feed(x) for x in tail(FEED, 12)], 12)
    block("AGI CYCLES", [fmt_episode(x) for x in tail(AGI_EPISODES, 8)], 8)
    block("BOUNDED SELF-IMPROVEMENT", [fmt_improve(x) for x in tail(IMPROVE, 5)], 5)
    block("RECEIPTS", [fmt_receipt(x) for x in tail(RECEIPTS, 8)], 8)

    if BINETIC_AGENT.exists():
        block("BINETIC_AGENT LIVE TRANSCRIPT", ["  " + clip(x, w - 4) for x in tail(BINETIC_AGENT, 10)], 10)
    else:
        block("BINETIC_AGENT LIVE TRANSCRIPT", ["  (not active — run binetic-binetic-agent-live to enable)"], 1)

    print("legend: ACT = tool/action intent · DONE = result · AGI = autonomous cycle · receipt = verifiable event")


def main() -> int:
    try:
        while True:
            render()
            sys.stdout.flush()
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
