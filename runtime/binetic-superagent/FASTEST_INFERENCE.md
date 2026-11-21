# Fastest inference program: measured state

## Global claim

I cannot honestly claim "fastest on the planet" from this machine alone. That requires a same-model, same-hardware, reproducible external leaderboard comparison. What I can do is make this stack the fastest measurable version available here and expose the evidence.

## Machine

```text
32-core Apple Silicon VM
aarch64
~15 GiB RAM
ARMv8 crypto, CRC32, bf16, i8mm, dopp features reported
```

## Native packet control-plane kernels

Commands:

```bash
binetic-cockpit control native-bench
binetic-native-bench
```

Latest cockpit output:

```text
lane decisions:     12,334,889,790.8 /s
SIMD KV byte fold:  94,202.1 MiB/s
CRC32C integrity:      982.2 MiB/s
```

Individual runs reached:

```text
lane decisions: ~11.9-12.3 billion/s
SIMD KV fold:  ~108-110 GiB/s
CRC32C:        ~930-982 MiB/s
```

These are control-plane kernels: routing masks, byte-slot folding, and receipt integrity. They are not tok/s.

## Real inference runtime

llama.cpp built locally:

```text
/root/agent-workspace/llama.cpp
commit b019be0
build-binet/bin/llama-server
build-binet/bin/llama-cli
```

Model:

```text
/root/agent-workspace/models/Qwen2.5-0.5B-Instruct-Q8_0.gguf
Q8_0, 630M params
```

The available 9B SenseNova GGUF is not loadable by this llama.cpp build because its architecture is `sensenova_loop`, which the engine reports as unknown. I did not fake a run around that.

## Thread sweep

Measured with `llama-cli`, short prompt, ctx 512, 64 tokens predicted, repeats 3-5:

```text
threads=2   prefill=131.4 tok/s   decode=60.5 tok/s
threads=4   prefill=203.5 tok/s   decode=93.2 tok/s
threads=6   prefill=259.5 tok/s   decode=94.0 tok/s
threads=8   prefill=305.3 tok/s   decode=97.2 tok/s
threads=10  prefill=368.6 tok/s   decode=127.0 tok/s
threads=12  prefill=422.5 tok/s   decode=97.5 tok/s
threads=16  prefill=551.6 tok/s   decode=67.4 tok/s
threads=24  prefill=309.9 tok/s   decode=4.8 tok/s
threads=32  prefill=246.9 tok/s   decode=11.5 tok/s
```

Key finding: more threads are not faster on this VM. The fast points are:

```text
prefill: 16 batch threads
decode:  10 decode threads
```

## Tuned server

Start script:

```bash
binetic-cockpit control fast-infer
```

Actual script:

```text
/root/agent-workspace/binetic-superagent/binetic-fast-infer.sh
```

Config:

```text
port: 8641
decode threads: 10
batch/prefill threads: 16
ctx: 512
slots: 1
```

HTTP benchmark:

```text
best decode: ~94.8 tok/s
```

CLI measured decode peak on same model:

```text
~127 tok/s
```

The HTTP server adds overhead; the packetized proxy adds another proxy hop. Future work should fuse the packet control plane directly into the server transport rather than layering HTTP proxies.

## Binetic Agent controls

Palette:

```text
user:binetic-fast
user:binetic-kv
user:binetic-control
user:binetic-verify
```

Commands:

```bash
binetic-cockpit control fast-infer
binetic-cockpit control native-bench
binetic-cockpit control kv-demo
binetic-cockpit control kv-bench
python3 /root/agent-workspace/binetic-superagent/bench_http.py --repeats 5 --max-tokens 96
```

## Honest claim

This stack now has:

- extremely fast native packet control-plane kernels
- a measurable tuned real inference server
- thread configuration chosen from local evidence
- Binetic Agent-native controls for starting and benchmarking it

It does not yet have a defensible global "fastest on planet" claim. The next real step is a shared prompt/model/hardware A/B harness against llama.cpp defaults, Kapitsa, oMLX, and vLLM-style baselines.
