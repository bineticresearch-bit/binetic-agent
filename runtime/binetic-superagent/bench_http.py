#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.request


def chat(base: str, model: str, prompt: str, max_tokens: int, stream: bool = False) -> dict:
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": stream,
    }).encode()
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as response:
        raw = response.read()
    wall = time.perf_counter() - t0
    doc = json.loads(raw)
    usage = doc.get("usage") or {}
    return {
        "wall_s": wall,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "decode_tps": (usage.get("completion_tokens") / wall) if usage.get("completion_tokens") else None,
        "prompt_tps": (usage.get("prompt_tokens") / wall) if usage.get("prompt_tokens") else None,
        "content": (doc.get("choices") or [{}])[0].get("message", {}).get("content", "")[:200],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8641")
    ap.add_argument("--model", default="/root/agent-workspace/models/Qwen2.5-0.5B-Instruct-Q8_0.gguf")
    ap.add_argument("--prompt", default="Write a concise proof that packetized KV routing is a useful control plane.")
    ap.add_argument("--max-tokens", type=int, default=96)
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    rows = [chat(args.base, args.model, args.prompt, args.max_tokens) for _ in range(args.repeats)]
    best = max((r["decode_tps"] or 0) for r in rows)
    print(json.dumps({"base": args.base, "best_decode_tps": best, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
