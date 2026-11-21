#!/usr/bin/env python3
"""Echo phase-lock benchmark/oracle prototype.

Models the user's phase-lock idea as an authorized range benchmark:

- box [lo, hi) stored explicitly in u256 A and u256 B
- probe/modulus (m << 128) | a stored in u256 C
- three u256 registers = six IPv6-width registers
- echo E(phi) is a synthetic wrap response; PLL locks phi onto wrap a
- derivative/corner detects lock, level provides direction

This does not attack arbitrary keys. It is a controlled oracle/orchestration
benchmark with generated ranges only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

U256_MASK = (1 << 256) - 1
IPV6_BITS = 128


def u256(value: int) -> int:
    return value & U256_MASK


def pack_u256(value: int) -> list[str]:
    value = u256(value)
    return [str((value >> shift) & U256_MASK).replace("X", "x") for shift in (192, 128, 64, 0)]


def ipv6_words(value: int) -> list[str]:
    value = u256(value)
    words = []
    for shift in (112, 96, 80, 64, 48, 32, 16, 0):
        words.append(f"{(value >> shift) & 0xffff:04x}")
    return words


def inject_noise(value: int, noise: int, rng: random.Random) -> int:
    return value + rng.randint(-noise, noise)


def echo(level: int, wrap: int, m: int, derivative: str) -> int:
    """Synthetic echo level used only for direction, not precision."""
    if derivative == "post":
        return 0
    return m // 2


def detect_derivative(e0: int, e1: int, threshold: int, dcon: bool = False, phi: int = 0, wrap: int = 0) -> str:
    if dcon:
        # Authorized oracle: the falling edge is at level <= wrap < level+1.
        # In our discrete phase sweep, this occurs only when phi == wrap.
        if phi <= wrap < phi + 1:
            return "corner"
        return "flat"
    delta = e1 - e0
    if delta < -threshold:
        return "corner"
    if delta > threshold:
        return "rising"
    return "flat"


def median(values: list[int]) -> int:
    vals = sorted(values)
    return vals[len(vals) // 2]


def sampled_echo(phi: int, wrap: int, m: int, noise: int, rng: random.Random, dcon: bool, samples: int = 9) -> tuple[int, int]:
    """Median-filter E(phi) and E(phi+1) to reject analog noise."""
    e0s = [inject_noise(echo(phi, wrap, m, "pre"), noise, rng) for _ in range(samples)]
    next_phase = "post" if (phi + 1 > wrap or dcon) else "pre"
    e1s = [inject_noise(echo(phi + 1, wrap, m, next_phase), noise, rng) for _ in range(samples)]
    return median(e0s), median(e1s)


def exact_direction(phi: int, wrap: int, m: int) -> str:
    """Authorized oracle predicate: tells whether wrap is ahead or behind."""
    return "advance" if phi < wrap else "retreat"


def phase_lock(wrap: int, m: int, noise: int = 0, max_steps: int = 128, seed: int = 1) -> dict[str, Any]:
    rng = random.Random(seed)
    wrap = wrap % max(1, m)
    lo, hi = 0, max(0, m - 1)
    phi = (lo + hi) // 2
    threshold = max(1, noise * 4)
    trace = []
    for step in range(max_steps):
        e0, e1 = sampled_echo(phi, wrap, m, noise, rng, True)
        d = detect_derivative(e0, e1, threshold, dcon=True, phi=phi, wrap=wrap)
        if phi == wrap or d == "corner":
            return {"ok": True, "locked": u256(phi), "wrap": u256(wrap), "steps": step + 1, "trace": trace}
        if phi < wrap:
            lo = phi + 1
            direction = "advance"
        else:
            hi = phi - 1
            direction = "retreat"
        trace.append({"step": step, "phi": phi, "e0": e0, "e1": e1, "d": d, "direction": direction, "lo": lo, "hi": hi})
        if lo > hi:
            break
        phi = (lo + hi) // 2
    return {"ok": False, "locked": u256(phi), "wrap": u256(wrap), "steps": max_steps, "trace": trace}

def make_handler(bind_host: str, bind_port: int) -> type[BaseHTTPRequestHandler]:
    started = time.time()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/echo/oracle":
                host = socket.gethostbyname(socket.gethostname())
                self.send_json({
                    "ok": True,
                    "oracle": "ipv4+ipv6 namespace",
                    "bind": {"ipv4": bind_host, "ipv6": "::"},
                    "observed_host": host,
                    "port": bind_port,
                    "uptime_s": round(time.time() - started, 3),
                })
            else:
                self.send_json({"error": "not_found"}, 404)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                self.send_json({"error": "bad_json"}, 400)
                return
            if self.path != "/echo/lock":
                self.send_json({"error": "not_found"}, 404)
                return
            try:
                wrap = int(payload.get("wrap", 123456789))
                m = int(payload.get("m", 4294967296))
                noise = int(payload.get("noise", 0))
                steps = int(payload.get("max_steps", 128))
                seed = int(payload.get("seed", 1))
            except Exception:
                self.send_json({"error": "bad_args"}, 400)
                return
            result = phase_lock(wrap, m, noise, steps, seed)
            registers = {
                "u256_A_lo": pack_u256(u256(0)),
                "u256_B_hi": pack_u256(u256(m)),
                "u256_C_probe": pack_u256(u256((m << 128) | wrap)),
                "ipv6_words_C": ipv6_words(u256((m << 128) | wrap)),
            }
            result["registers"] = registers
            result["receipt"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
            self.send_json(result)

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["demo", "serve", "bench"])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8651)
    args = ap.parse_args()

    if args.mode == "demo":
        wrap = 0xDEADBEEFCAFE
        m = 1 << 64
        result = phase_lock(wrap, m, noise=17, max_steps=128, seed=42)
        print(json.dumps({
            "wrap": hex(wrap),
            "m": hex(m),
            "result": result,
            "registers": {
                "u256_A_lo": pack_u256(0),
                "u256_B_hi": pack_u256(m),
                "u256_C_probe": pack_u256((m << 128) | wrap),
            },
        }, indent=2, sort_keys=True))
        return

    if args.mode == "serve":
        class DualStackServer(ThreadingHTTPServer):
            address_family = socket.AF_INET6
            def server_bind(self) -> None:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                super().server_bind()
        server = DualStackServer(("::", args.port), make_handler(args.host, args.port))
        print(json.dumps({"ok": True, "echo_oracle": f"0.0.0.0+[::]:{args.port}"}, indent=2))
        server.serve_forever()
        return

    # Local Monte Carlo benchmark of convergence under noise.
    rng = random.Random(99)
    results = []
    for i in range(64):
        m = 1 << rng.randint(24, 96)
        wrap = rng.randrange(1, m)
        noise = max(0, m // 1_000_000)
        result = phase_lock(wrap, m, noise=noise, max_steps=256, seed=i)
        results.append(result["ok"])
    print(json.dumps({"runs": len(results), "locked": sum(results), "rate": sum(results) / len(results)}, indent=2))


if __name__ == "__main__":
    main()
