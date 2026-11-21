#!/usr/bin/env python3
"""Benchmark llama-cli prompt/decode throughput from its timing output."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


def bench(model: Path, llama_cli: Path, prompt: str, n: int, threads: int, ctx: int, repeats: int, extra: list[str] | None = None) -> dict:
    rows = []
    for rep in range(repeats):
        cmd = [
            str(llama_cli), "-m", str(model), "-t", str(threads), "-tb", str(threads),
            "-c", str(ctx), "-n", str(n), "-p", prompt, "--no-display-prompt",
        ]
        cmd.extend(extra or [])
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=1800)
        wall = time.perf_counter() - t0
        text = proc.stdout + proc.stderr
        m_eval = re.search(r"\[ Prompt: [^|]+\| Generation:\s*([0-9.]+)\s*t/s \]", text)
        m_prompt = re.search(r"\[ Prompt:\s*([0-9.]+)\s*t/s", text)
        prompt_tps = float(m_prompt.group(1)) if m_prompt else None
        eval_tps = float(m_eval.group(1)) if m_eval else None
        prompt_ms = prompt_tok = eval_ms = eval_tokens = None
        rows.append({
            "rep": rep,
            "exitCode": proc.returncode,
            "wall_s": wall,
            "prompt_ms": prompt_ms,
            "prompt_tokens": prompt_tok,
            "prompt_tps": prompt_tps,
            "eval_ms": eval_ms,
            "eval_tokens": eval_tokens,
            "eval_tps": eval_tps,
            "tail": text[-400:],
        })
    ok = [r for r in rows if r["exitCode"] == 0 and r["eval_tps"]]
    best_decode = max((r["eval_tps"] for r in ok), default=0.0)
    best_prefill = max((r["prompt_tps"] for r in ok if r["prompt_tps"]), default=0.0)
    return {
        "model": str(model),
        "llama_cli": str(llama_cli),
        "prompt_chars": len(prompt),
        "predict": n,
        "threads": threads,
        "ctx": ctx,
        "repeats": repeats,
        "best_prefill_tps": best_prefill,
        "best_decode_tps": best_decode,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/root/agent-workspace/models/Qwen2.5-0.5B-Instruct-Q8_0.gguf")
    ap.add_argument("--cli", default="/root/agent-workspace/llama.cpp/build-binet/bin/llama-cli")
    ap.add_argument("--prompt", default="Write a concise proof that packetized KV routing is a useful control plane. ")
    ap.add_argument("--prompt-file")
    ap.add_argument("-n", type=int, default=96)
    ap.add_argument("-t", "--threads", type=int, default=32)
    ap.add_argument("-c", "--ctx", type=int, default=1024)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else args.prompt
    result = bench(Path(args.model), Path(args.cli), prompt, args.n, args.threads, args.ctx, args.repeats)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
