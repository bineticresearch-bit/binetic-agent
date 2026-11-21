#!/usr/bin/env python3
"""Binetic Free Fabric Inference (BFFI).

A bounded prototype for network-in-motion inference resources.

This does not crack keys or attack systems. It models authorized peer nodes
advertising CPU/GPU slots as moving "fibers"; routes token work onto the best
fiber by measured latency/throughput; and writes receipts for every handoff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path("/root/agent-workspace/binetic-superagent")
FABRIC_DIR = ROOT / "fabric_state"
REGISTRY = FABRIC_DIR / "nodes.jsonl"
RECEIPTS = FABRIC_DIR / "receipts.jsonl"


def cj(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sha(payload: Any) -> str:
    return hashlib.sha256(cj(payload)).hexdigest()


@dataclass
class Node:
    node_id: str
    host: str
    port: int
    capability: str
    max_slots: int = 1
    latency_ms: float = 0.0
    last_seen: float = 0.0
    score: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "capability": self.capability,
            "max_slots": self.max_slots,
            "latency_ms": round(self.latency_ms, 3),
            "last_seen": round(self.last_seen, 3),
            "score": round(self.score, 3),
        }


class Fabric:
    def __init__(self, self_id: str, host: str, port: int, capability: str, max_slots: int = 1):
        self.self_id = self_id
        self.host = host
        self.port = port
        self.capability = capability
        self.max_slots = max_slots
        self.nodes: dict[str, Node] = {}
        self.lock = threading.Lock()
        FABRIC_DIR.mkdir(parents=True, exist_ok=True)
        if REGISTRY.exists():
            for line in REGISTRY.read_text(errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    node = Node(
                        str(item.get("node_id") or "peer"),
                        str(item.get("host") or "127.0.0.1"),
                        int(item.get("port") or 0),
                        str(item.get("capability") or "cpu"),
                        int(item.get("max_slots") or 1),
                    )
                    self.nodes[node.node_id] = node
                except Exception:
                    continue

    def append_receipt(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"kind": kind, "fabric_node": self.self_id, "ts": time.time(), **payload}
        body_hash = sha(body)
        prev = self.chain_root()
        record = {"body": body, "body_hash": body_hash, "prev": prev}
        with RECEIPTS.open("a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
        return {"body_hash": body_hash, "prev": prev, "root": sha(record)}

    def chain_root(self) -> str:
        if not RECEIPTS.exists():
            return "0" * 64
        lines = [line for line in RECEIPTS.read_text(errors="replace").splitlines() if line.strip()]
        return sha(json.loads(lines[-1])) if lines else "0" * 64

    def register(self, node: Node) -> None:
        node.last_seen = time.time()
        with self.lock:
            self.nodes[node.node_id] = node
            with REGISTRY.open("a") as f:
                f.write(json.dumps(node.to_json(), sort_keys=True) + "\n")

    def self_node(self) -> Node:
        return Node(self.self_id, self.host, self.port, self.capability, self.max_slots, 0.0, time.time(), 1.0)

    def probe(self, node: Node) -> Node:
        host = node.host
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        elif ":" in host and not host.startswith("["):
            host = f"[{host}]"
        url = f"http://{host}:{node.port}/echo/oracle"
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                resp.read()
            latency = (time.perf_counter() - t0) * 1000
        except Exception:
            latency = 9999.0
        node.latency_ms = latency
        node.last_seen = time.time()
        cap_score = {"gpu": 3.0, "cpu": 2.0, "light": 1.0}.get(node.capability, 1.0)
        node.score = cap_score * node.max_slots / max(1.0, latency)
        return node

    def route(self) -> Node:
        with self.lock:
            candidates = list(self.nodes.values())
        if not candidates:
            return self.self_node()
        probed = [self.probe(n) for n in candidates]
        return max(probed, key=lambda n: n.score)

    def status(self) -> dict[str, Any]:
        with self.lock:
            nodes = [n.to_json() for n in self.nodes.values()]
        return {
            "self": self.self_node().to_json(),
            "nodes": nodes,
            "chain_root": self.chain_root(),
            "claim": "authorized free-fabric inference prototype",
        }


def make_handler(fabric: Fabric) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = cj(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/fabric/ping":
                self.send_json({"ok": True, "node": fabric.self_id, "t": time.time()})
            elif self.path == "/fabric/status":
                self.send_json(fabric.status())
            else:
                self.send_json({"error": "not_found"}, 404)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length)
            try:
                incoming = json.loads(raw or b"{}")
            except Exception:
                self.send_json({"error": "bad_json"}, 400)
                return
            if self.path == "/fabric/register":
                node = Node(
                    str(incoming.get("node_id") or f"peer-{len(fabric.nodes)}"),
                    str(incoming.get("host") or self.client_address[0]),
                    int(incoming.get("port") or 0),
                    str(incoming.get("capability") or "cpu"),
                    int(incoming.get("max_slots") or 1),
                )
                fabric.register(node)
                receipt = fabric.append_receipt("fabric_register", {"node": node.to_json()})
                self.send_json({"ok": True, "receipt": receipt})
            elif self.path == "/fabric/infer":
                chosen = fabric.route()
                receipt = fabric.append_receipt("fabric_infer_route", {
                    "prompt_hash": hashlib.sha256(str(incoming.get("prompt", "")).encode()).hexdigest(),
                    "chosen": chosen.to_json(),
                })
                self.send_json({"ok": True, "route": chosen.to_json(), "receipt": receipt})
            else:
                self.send_json({"error": "not_found"}, 404)

    return Handler


def register_peer(url: str, node_id: str, host: str, port: int, capability: str) -> dict[str, Any]:
    payload = cj({"node_id": node_id, "host": host, "port": port, "capability": capability, "max_slots": 1})
    req = urllib.request.Request(url + "/fabric/register", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["serve", "status", "register", "infer"])
    ap.add_argument("--node-id", default=os.uname().nodename)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8650)
    ap.add_argument("--capability", default="cpu")
    ap.add_argument("--router", default="http://127.0.0.1:8650")
    ap.add_argument("--peer-host", default="127.0.0.1")
    ap.add_argument("--peer-port", type=int, default=8650)
    ap.add_argument("--peer-id")
    ap.add_argument("--prompt", default="hello fabric")
    args = ap.parse_args()

    fabric = Fabric(args.node_id, args.host, args.port, args.capability)

    if args.mode == "serve":
        server = ThreadingHTTPServer((args.host, args.port), make_handler(fabric))
        receipt = fabric.append_receipt("fabric_serve", {"host": args.host, "port": args.port, "capability": args.capability})
        print(json.dumps({"ok": True, "listening": f"{args.host}:{args.port}", "receipt": receipt}, indent=2))
        server.serve_forever()
    elif args.mode == "status":
        print(json.dumps(fabric.status(), indent=2, sort_keys=True))
    elif args.mode == "register":
        peer_id = args.peer_id or f"{args.peer_host}:{args.peer_port}"
        print(json.dumps(register_peer(args.router, peer_id, args.peer_host, args.peer_port, args.capability), indent=2, sort_keys=True))
    elif args.mode == "infer":
        payload = cj({"prompt": args.prompt})
        req = urllib.request.Request(args.router + "/fabric/infer", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(json.dumps(json.loads(resp.read()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
