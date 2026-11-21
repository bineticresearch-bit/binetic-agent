# Better model + evolved inference

## Downloaded stronger model

```text
/root/agent-workspace/models/hf/Qwen3-4B-Q4_K_M.gguf
size: 2.4 GiB
sha256: 7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
```

This replaces the 0.5B demo model as the evolved inference target.

## Evolution method

New tuner:

```text
/root/agent-workspace/binetic-superagent/evolve_infer.py
```

It is a bounded hill-climber over runtime knobs only:

```text
decode threads
batch/prefill threads
ctx size
batch size
predict length
```

It does not mutate weights, crypto, safety, user autonomy, or core code.

Objective used:

```text
decode tok/s + 0.02 * prefill tok/s
```

## Measured evolution run

Command:

```bash
python3 evolve_infer.py \
  --model /root/agent-workspace/models/hf/Qwen3-4B-Q4_K_M.gguf \
  --generations 4 --children 4 --repeats 2 --objective decode --seed 7331
```

Baseline:

```text
threads=10
threads_batch=16
ctx=512
n_batch=512
decode=12.4 tok/s
prefill=51.3 tok/s
score=13.43
```

Best evolved:

```text
threads=10
threads_batch=4
ctx=512
n_batch=256
n_predict=48
decode=17.1 tok/s
prefill=14.9 tok/s
score=17.40
```

Important finding: on this VM, batch threads above 4 destroy decode throughput for the 4B model. Also, 20-24 decode threads collapse to ~3 tok/s. The old assumption "more threads = faster" is false here.

## Promoted runtime

Start scripts:

```bash
binetic-cockpit control fast-evolved
```

Scripts:

```text
binetic-fast-infer-evolved.sh
binetic-fast-infer-evolved-start.sh
```

Current server:

```text
port: 8641
model: Qwen3-4B-Q4_K_M.gguf
threads: 10
threads_batch: 4
ctx: 512
n_batch: 256
```

Health/model confirmed:

```text
/status -> ok
/v1/models -> Qwen3-4B-Q4_K_M.gguf
```

## HTTP benchmark on evolved server

Command:

```bash
python3 bench_http.py \
  --model /root/agent-workspace/models/hf/Qwen3-4B-Q4_K_M.gguf \
  --repeats 5 --max-tokens 96
```

Result:

```text
best decode: ~17.1 tok/s
```

The HTTP result varies with request mix and first-token latency; CLI tuner measurement is the stable promotion signal.

## Binetic Agent integration

Palette:

```text
user:binetic-evolve
```

Cockpit commands:

```bash
binetic-cockpit control evolve-infer
binetic-cockpit control fast-evolved
```

Dashboard:

```text
EVOLVED: Qwen3-4B-Q4_K_M.gguf score=17.40
```

## Next evolution targets

1. Try Qwen3-8B-Q4_K_M if memory remains stable; likely lower tok/s but stronger.
2. Try speculative/draft decoding in llama.cpp if a compatible draft is available.
3. Fuse packet KV receipt lookup into the HTTP transport instead of proxy layering.
4. Add request classification to choose prefill-heavy vs decode-heavy server profiles.
5. Add A/B harness across Kapitsa, llama.cpp default, and evolved profiles.

## Honest boundary

"Evolve" here means benchmark-driven runtime configuration search, not model self-modification or consciousness. The downloaded model is a strong open model, not a Binetic-trained model.
