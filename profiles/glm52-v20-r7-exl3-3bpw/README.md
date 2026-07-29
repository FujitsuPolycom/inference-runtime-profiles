# GLM-5.2 v20 R7 EXL3 3.0 bpw

Validated four-GPU profile for the EXL3 3.0 bpw GLM-5.2 checkpoint. It uses
GPU-only KV caching: LMCache and NVMe KV offload are intentionally disabled.

## Checkpoint and runtime

| Field | Value |
|---|---|
| Hugging Face repository | [`brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw`](https://huggingface.co/brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw) |
| Quantization | EXL3, 3.0 bpw |
| Runtime | Gilded Gnosis v20 R7 |
| Image | `voipmonitor/vllm@sha256:fdc107c917f5ce7c7f78a51a2b76b171a0eb25569be58c1284809e7e6ba33482` |
| Load format | InstantTensor |
| Parallelism | TP4 / DCP4 / MTP3 |

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

The earlier 16,384-token ceiling caused prefills above 16K to leave the
optimized full-CKV gather path. The compact FP8-RoPE layout reduces each KV
record from 432 to 368 bytes and the persistent gather workspace from 486.5
to 414.4 MiB per GPU. This keeps the optimized path eligible throughout the
supported context window while providing 813,568 GPU KV tokens, or 3.10
full-length requests.

The tested `3072` batched-token and `0.96` memory-utilization combination is
intentional. A `4192` batched-token experiment exhausted GPU memory during a
DCP all-gather even though startup succeeded.

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
