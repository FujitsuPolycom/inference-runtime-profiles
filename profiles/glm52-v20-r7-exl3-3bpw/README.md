# GLM-5.2 v20 R7 EXL3 3.0 bpw

Four-GPU profile for the GLM-5.2 checkpoint quantized with EXL3 at 3.0 bits per weight. It uses
GPU-only KV caching: LMCache and NVMe KV offload are intentionally disabled.

Status: `implemented` — verified live on the reference host, 2026-07-28
(original status label: verified-live).

## Checkpoint and runtime

| Field | Value |
|---|---|
| Hugging Face repository | [`brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw`](https://huggingface.co/brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw) |
| Quantization | EXL3, 3.0 bpw |
| Runtime | Gilded Gnosis v20 R7 — "R7" is the revision tag of the Gilded Gnosis private vLLM image lineage; the immutable image digest below is the durable identifier |
| Image | `voipmonitor/vllm@sha256:fdc107c917f5ce7c7f78a51a2b76b171a0eb25569be58c1284809e7e6ba33482` |
| Load format | InstantTensor |
| Parallelism | TP4 (tensor parallel) / DCP4 (decode context parallel) / MTP3 (multi-token-prediction speculative decoding, 3 draft tokens) |

## Validated configuration

| Setting | Value |
|---|---:|
| Maximum model length | 262,144 |
| Auto-sized GPU KV capacity | 813,568 tokens |
| Full-context concurrency | 3.10x |
| Maximum batched tokens | 3,072 |
| Maximum sequences | 8 |
| GPU memory utilization | 0.96 |
| KV type | `nvfp4_ds_mla` |
| KV record size | 368 bytes |
| FP8 RoPE | Enabled |
| Persistent CKV workspace | 414.4 MiB/GPU |
| EXL3 Trellis prefill arena | 1,054.2 MiB/GPU |

The CKV gather ceiling is deliberately equal to the request ceiling:

```text
VLLM_B12X_MLA_CKV_GATHER_MAX_TOKENS=262144
KV_FP8_ROPE=1
```

A 16,384-token ceiling would cause prefills above 16K to leave the
optimized full-CKV gather path. The compact FP8-RoPE layout reduces each KV
record from 432 to 368 bytes and the persistent gather workspace from 486.5
to 414.4 MiB per GPU. This keeps the optimized path eligible throughout the
supported context window while providing 813,568 GPU KV tokens, or 3.10
full-length requests.

Invariant: with `gpu_memory_utilization=0.96`, the maximum batched-token
setting must not exceed the validated `3,072` — at `4,192` (the measured
failing value; intermediate values are unmeasured) the DCP all-gather
workspace exhausts device memory after a successful startup.

## Apply

```bash
cp profile.env.example .env
docker compose --env-file .env -f compose.yml config
docker compose --env-file .env -f compose.yml up -d
```

After startup, verify:

```text
Preallocated 414.4 MiB for 2 persistent CKV execution lane(s)
GPU KV cache size: 813,568 tokens
Maximum concurrency for 262,144 tokens per request: 3.10x
Application startup complete
```

Do not commit the populated `.env`, raw container inspection, host paths,
credentials, request prompts, or logs.
