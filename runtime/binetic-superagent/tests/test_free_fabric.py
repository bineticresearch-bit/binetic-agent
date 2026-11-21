from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('/root/agent-workspace/binetic-superagent')
sys.path.insert(0, str(ROOT))
from echo_phase_lock import phase_lock, pack_u256, u256  # noqa: E402


def test_three_u256_registers():
    m = 1 << 64
    wrap = 0xDEADBEEFCAFE
    regs = {
        'A_lo': pack_u256(u256(0)),
        'B_hi': pack_u256(u256(m)),
        'C_probe': pack_u256(u256((m << 128) | wrap)),
    }
    assert set(regs) == {'A_lo', 'B_hi', 'C_probe'}
    assert all(len(v) == 4 for v in regs.values())
    assert hashlib.sha256(json.dumps(regs, sort_keys=True).encode()).hexdigest()


def test_phase_lock_deterministic_zero_noise():
    m = 1 << 32
    wrap = 123456789
    result = phase_lock(wrap, m, noise=0, max_steps=128, seed=7)
    assert result['ok'] is True
    assert result['locked'] == wrap
    assert result['steps'] < 128


def test_phase_lock_with_small_noise():
    m = 1 << 48
    wrap = 987654321
    result = phase_lock(wrap, m, noise=37, max_steps=128, seed=11)
    # With generated oracle noise the loop must still converge in this fixture.
    assert result['ok'] is True
    assert result['steps'] < 128


if __name__ == '__main__':
    for fn in [test_three_u256_registers, test_phase_lock_deterministic_zero_noise, test_phase_lock_with_small_noise]:
        fn()
        print('PASS', fn.__name__)
    print('ALL FREE FABRIC TESTS PASSED')
