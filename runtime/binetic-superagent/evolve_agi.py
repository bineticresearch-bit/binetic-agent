#!/usr/bin/env python3
"""Bounded AGI self-improvement loop.

Runs N AGI kernel cycles, computes stability score, can tighten the test goal
priority within hard bounds if all goals are stable, and receipts every pass.
It cannot edit code, safety, identity, DNA, or creator files.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path('/root/agent-workspace/binetic-superagent')
STATE_DIR = ROOT / 'agi_state'
STATE_DIR.mkdir(parents=True, exist_ok=True)
REPORT = STATE_DIR / 'self_improvement_report.json'
HISTORY = STATE_DIR / 'self_improvement_history.jsonl'


def sha(obj: Any) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def run(cmd: list[str], timeout: int = 600) -> Any:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {p.stderr or p.stdout}")
    return json.loads(p.stdout)


def main() -> None:
    lock_path = STATE_DIR / 'self_improvement.lock'
    lock_fh = lock_path.open('a+')
    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    ap = argparse.ArgumentParser()
    ap.add_argument('--cycles', type=int, default=3)
    args = ap.parse_args()

    results = []
    for _ in range(max(1, args.cycles)):
        results.append(run([sys.executable, str(ROOT / 'agi_kernel.py'), 'cycle'], 600))

    status = run([sys.executable, str(ROOT / 'agi_kernel.py'), 'status'], 120)
    world = status.get('world') or {}
    keys = ['receipts_valid', 'bpcm_valid', 'tests_passing', 'fabric_ready', 'inference_ready', 'identity_bound']
    stable = all(bool(world.get(k)) for k in keys)
    positive = sum(float(r.get('reward', 0)) for r in results)
    stability = (sum(1 for k in keys if bool(world.get(k))) / len(keys)) + min(0.2, max(0.0, positive) / 10)
    adopted = False

    if stable:
        # The only allowed optimization: slightly raise priority of test goal,
        # always within [0.5, 1.5]. No code edits.
        run([
            sys.executable, str(ROOT / 'agi_kernel.py'), 'add-goal',
            '--id', 'tests_passing',
            '--description', 'Keep core and free-fabric tests passing.',
            '--evaluator', 'tests_passing',
            '--priority', '1.35',
        ], 120)
        adopted = True

    report = {
        'ts': time.time(),
        'cycles': len(results),
        'stable': stable,
        'stability_score': round(stability, 4),
        'total_cycle_reward': positive,
        'adopted_bounded_improvement': adopted,
        'allowed_mutations': ['goal_priority_within_bounds', 'append_receipt', 'create_proposal'],
        'forbidden_mutations': status.get('immutable', []),
        'world_hash': sha(world),
        'report_hash': sha({'stable': stable, 'score': stability, 'rewards': positive}),
    }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True))
    with HISTORY.open('a') as f:
        f.write(json.dumps(report, sort_keys=True) + '\n')

    subprocess.run([
        sys.executable, str(ROOT / 'receipt_cli.py'), 'append',
        '--kind', 'agi_self_improvement',
        '--input-hash', sha(results),
        '--output-hash', report['report_hash'],
        '--payload', json.dumps(report, sort_keys=True, separators=(',', ':')),
    ], check=True, capture_output=True)

    print(json.dumps({'ok': True, 'report': report, 'path': str(REPORT)}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
