#!/usr/bin/env python3
"""Evolutionary tuner for Binetic inference configurations.

This is a small, bounded hill-climber over safe runtime knobs:
decode threads, batch/prefill threads, ctx size, and n_batch.

It does NOT modify model weights, cryptography, safety, autonomy, or code.
It benchmark-runs llama-cli with a fixed prompt and promotes the best config
into a JSON file used by cockpit/server start scripts.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path("/root/agent-workspace/binetic-superagent")
STATE = ROOT / "tuner_state"
BEST_PATH = STATE / "best_config.json"
HISTORY_PATH = STATE / "history.jsonl"
DEFAULT_CLI = "/root/agent-workspace/llama.cpp/build-binet/bin/llama-cli"


PROMPT = "Write a concise proof that packetized KV routing is a useful control plane. "


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def default_config(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "cli": DEFAULT_CLI,
        "prompt": PROMPT,
        "n_predict": 64,
        "threads": 10,
        "threads_batch": 16,
        "ctx": 512,
        "n_batch": 512,
        "repeats": 2,
    }


def parse_cli(text: str) -> tuple[float | None, float | None]:
    prompt = re.search(r"\[ Prompt:\s*([0-9.]+)\s*t/s", text)
    gen = re.search(r"Generation:\s*([0-9.]+)\s*t/s", text)
    return (float(prompt.group(1)) if prompt else None, float(gen.group(1)) if gen else None)


def evaluate(cfg: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        cfg["cli"], "-m", cfg["model"],
        "-t", str(cfg["threads"]), "-tb", str(cfg["threads_batch"]),
        "-c", str(cfg["ctx"]), "-n", str(cfg["n_predict"]),
        "-p", cfg["prompt"], "--no-display-prompt",
        "--batch-size", str(cfg["n_batch"]),
    ]
    repeats = max(1, int(cfg.get("repeats", 2)))
    decodes: list[float] = []
    prefills: list[float] = []
    walls: list[float] = []
    last_error = ""
    for _ in range(repeats):
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=1800)
        except Exception as exc:
            last_error = str(exc)
            break
        walls.append(time.perf_counter() - t0)
        if proc.returncode != 0:
            last_error = (proc.stdout + proc.stderr)[-500:]
            break
        prefill, decode = parse_cli(proc.stdout + proc.stderr)
        if decode:
            decodes.append(decode)
        if prefill:
            prefills.append(prefill)
    if not decodes:
        return {"ok": False, "error": last_error or "no decode timing", "config": cfg}
    return {
        "ok": True,
        "config": cfg,
        "decode_tps": max(decodes),
        "prefill_tps": max(prefills) if prefills else 0.0,
        "wall_s": sum(walls) / len(walls) if walls else 0.0,
    }


def fitness(row: dict[str, Any], objective: str) -> float:
    if not row.get("ok"):
        return -1e9
    decode = float(row.get("decode_tps", 0))
    prefill = float(row.get("prefill_tps", 0))
    if objective == "decode":
        return decode + 0.02 * prefill
    if objective == "prefill":
        return prefill + 0.02 * decode
    return 0.5 * decode + 0.5 * prefill


def mutate(cfg: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    out = copy.deepcopy(cfg)
    choices = [
        ("threads", [1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]),
        ("threads_batch", [1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]),
        ("ctx", [256, 384, 512, 768, 1024, 2048, 4096]),
        ("n_batch", [128, 256, 512, 1024, 2048]),
        ("n_predict", [48, 64, 96, 128]),
    ]
    # 1-2 safe mutations per child.
    for key, values in rng.sample(choices, k=rng.choice([1, 1, 2])):
        out[key] = rng.choice(values)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cli", default=DEFAULT_CLI)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--children", type=int, default=4)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--objective", choices=["decode", "prefill", "balanced"], default="decode")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    if BEST_PATH.exists():
        base = json.loads(BEST_PATH.read_text()).get("config", default_config(args.model))
        if base.get("model") != args.model:
            base = default_config(args.model)
    else:
        base = default_config(args.model)
    base["model"] = args.model
    base["cli"] = args.cli
    base["repeats"] = args.repeats

    best_row = evaluate(base)
    best_score = fitness(best_row, args.objective)
    append_jsonl(HISTORY_PATH, {"generation": -1, "row": best_row, "score": best_score})
    print(f"baseline: score={best_score:.2f} decode={best_row.get('decode_tps', 0):.1f} prefill={best_row.get('prefill_tps', 0):.1f}", flush=True)

    for gen in range(args.generations):
        candidates = [mutate(base if gen == 0 else best_row["config"], rng) for _ in range(args.children)]
        for cfg in candidates:
            cfg["repeats"] = args.repeats
            row = evaluate(cfg)
            score = fitness(row, args.objective)
            append_jsonl(HISTORY_PATH, {"generation": gen, "row": row, "score": score})
            print(f"g{gen} score={score:.2f} decode={row.get('decode_tps', 0):.1f} prefill={row.get('prefill_tps', 0):.1f} cfg={ {k: cfg[k] for k in ['threads','threads_batch','ctx','n_batch','n_predict']} }", flush=True)
            if score > best_score:
                best_score, best_row, base = score, row, cfg

    BEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    BEST_PATH.write_text(json.dumps({"objective": args.objective, "score": best_score, **best_row}, indent=2, sort_keys=True))
    print(json.dumps({"best": BEST_PATH.as_posix(), "score": best_score, "config": best_row.get("config")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
