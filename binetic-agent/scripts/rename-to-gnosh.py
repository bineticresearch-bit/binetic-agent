#!/usr/bin/env python3
"""Rename klash to binetic-agent in a checkout of the repository.

Jae, 2026-10-30: "we're renaming to binetic-agent... no more KLASH anywhere. all
BINETIC_AGENT".

A branch made before the rename takes it in four steps, from the top of the
checkout, with the script copied from main:

    git show main:scripts/rename-to-binetic-agent.py > /tmp/rename-to-binetic-agent.py
    python3 /tmp/rename-to-binetic-agent.py
    git commit -qam "Rename klash to binetic-agent (scripted)"
    git merge <main's scripted rename commit>
    git merge main

The scripted rename commit on main holds exactly what this script makes, so
it merges cleanly, apart from lines the branch itself changed. Main's later
commits then merge on top: the hand-written code that keeps the old names
readable among them. The script refuses to run in a checkout that already
tracks it, where the rename is done and it would rename those old names.

What it changes: every klash, Klash and KLASH in tracked text files becomes
binetic-agent, Binetic Agent and BINETIC_AGENT, and every tracked path with klash in its name is
moved (git mv). github.com/klash-pro/klash becomes github.com/binetic-agent-ai/binetic-agent,
and klash.pro becomes binetic-agent.local, the licence's Designation with it ("built on
binetic-agent", https://binetic-agent.local): Jae, 2026-10-30, "just edit the license directly".

What it leaves alone, on purpose, because what is stored depends on it:
- the Gno package paths klash/gnomem/v1, klash/gnomem/v2 and klash/bptree/v0,
  the realm path klash.local/r/mem, and internal/gnovm/klashlibs, where those
  packages live: journals replay them, and a mem's layout pins them;
- gnomem v1, which is frozen, and the sources TestMemLayoutPinned hashes
  (memLayoutFiles in internal/gnovm/memrealm.go), since a change to any of
  them is a new layout, and every mem is then rebuilt;
- in internal/gnovm, the strings a mem stores or derives: the journal's
  "klash_gnovm_journal" field, the store key "klash/stamp", the "klash mem"
  address seed, the prelude's "klash:mem", the chain domain "klash.local",
  and "klash" itself, the VM's chain id and the name a mem's journal records
  for the calls binetic-agent makes on its own;
- metrics.klash.pro, where opted-in metrics go until binetic-agent.local points at
  Jae's server. Today binetic-agent.local resolves to a parking host, and usage data
  must never be sent there.
"""

import os
import re
import subprocess
import sys

SELF = "scripts/rename-to-binetic-agent.py"

# Kept verbatim. Each is held aside before the rename and put back after, so
# the rename never sees it.
PROTECT = [
    "metrics.klash.pro",
    "klash_gnovm_journal",
    "klash/gnomem",
    "klash/bptree",
    "klash.local/",
    "klashlib",
]

# Kept verbatim in internal/gnovm as well: strings a mem stores or derives.
PROTECT_GNOVM = [
    '"klash mem"',
    '"klash:mem"',
    '"klash/stamp"',
    '"klash.local"',
    '"klash"',
]

# Exact rewrites, done before the general rename.
SPECIFIC = [
    ("github.com/klash-pro/klash", "github.com/binetic-agent-ai/binetic-agent"),
    ("klash-pro/klash", "binetic-agent-ai/binetic-agent"),
    ("klash-pro", "binetic-agent-ai"),
    ("klash.pro", "binetic-agent.local"),
]

GENERAL = [("KLASH", "BINETIC_AGENT"), ("Klash", "Binetic Agent"), ("klash", "binetic-agent")]

FROZEN_DIR = "internal/gnovm/klashlibs/klash/gnomem/v1/"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def tracked_files():
    return [p for p in git("ls-files", "-z").decode().split("\0") if p]


def layout_files():
    """The sources TestMemLayoutPinned hashes, as paths in the checkout."""
    try:
        with open("internal/gnovm/memrealm.go", encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return set()
    block = re.search(r"var memLayoutFiles = \[\]string\{(.*?)\}", src, re.S)
    if not block:
        return set()
    return {"internal/gnovm/" + p for p in re.findall(r'"([^"]+)"', block.group(1))}


def is_text(path):
    try:
        with open(path, "rb") as f:
            return b"\0" not in f.read(8192)
    except OSError:
        return False


def rename_text(s, protect=PROTECT):
    held = {}
    for i, tok in enumerate(protect):
        mark = f"\0KEEP{i}\0"
        held[mark] = tok
        s = s.replace(tok, mark)
    for a, b in SPECIFIC + GENERAL:
        s = s.replace(a, b)
    for mark, tok in held.items():
        s = s.replace(mark, tok)
    return s


def main():
    if not os.path.exists(".git"):
        sys.exit("rename-to-binetic-agent: run this from the top of a git checkout")
    if subprocess.run(["git", "ls-files", "--error-unmatch", SELF], capture_output=True).returncode == 0:
        sys.exit(f"rename-to-binetic-agent: this checkout has the rename already ({SELF} is in it); "
                 "running it again would rename the old names kept there on purpose")
    frozen = layout_files()
    changed = 0
    for path in tracked_files():
        if path.startswith(FROZEN_DIR) or path in frozen or os.path.islink(path) or not is_text(path):
            continue
        protect = PROTECT + PROTECT_GNOVM if path.startswith("internal/gnovm/") else PROTECT
        with open(path, encoding="utf-8", errors="surrogateescape") as f:
            s = f.read()
        t = rename_text(s, protect)
        if t != s:
            with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(t)
            changed += 1
    moved = 0
    for path in tracked_files():
        if "klashlib" in path:
            continue
        new = "/".join(rename_text(p) for p in path.split("/"))
        if new != path:
            os.makedirs(os.path.dirname(new) or ".", exist_ok=True)
            git("mv", path, new)
            moved += 1
            try:
                os.removedirs(os.path.dirname(path))  # the directories it left empty
            except OSError:
                pass
    print(f"rename-to-binetic-agent: {changed} files rewritten, {moved} paths moved")


if __name__ == "__main__":
    main()
