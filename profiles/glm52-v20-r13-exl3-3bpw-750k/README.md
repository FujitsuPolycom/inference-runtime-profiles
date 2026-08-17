# GLM-5.2 v20 r13 EXL3 3.0 bpw — 750k ceiling

Live-captured single-node four-GPU profile for the Brandon EXL3 3.0 bpw GLM-5.2 checkpoint. It is a successor record to the historical r7 / 262k profile; the r7 bundle remains the rollback/reproduction record.

## Runtime and model

| Field | Value |
|---|---|
| Checkpoint | [`brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw`](https://huggingface.co/brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw) |
| Runtime | Gilded Gnosis v20 r13, vLLM `0.11.2.dev280…r13` |
| Immutable image | `voipmonitor/vllm@sha256:02796036c96a52fda0919aa260c45c70bc97d8e662a6ae5e614b5f987c20851b` |
| Parallelism | TP4 / DCP4 / MTP3 |
| API model / port | `GLM-5.2-EXL3-TR3-3.0bpw` / 5810 |
| Load format | InstantTensor |
| KV type | `nvfp4_ds_mla`, FP8 RoPE, 368-byte KV records |
| Request ceiling | 750,000 tokens |
| Scheduler | 8 sequences; 3,072 batched tokens; full-and-piecewise CUDA graphs to size 32 |

## Cache posture

This is **not an LMCache deployment**. It uses vLLM automatic prefix caching and ordinary GPU KV allocation only. Although r13 includes LMCache libraries and its internal API environment defaults, there is no `LMCACHE_MODE`, connector, RAM L1, disk L2, or `/lmcache` volume configured.

The persistent `/cache` mount contains JIT/AOT artifacts (about 3.9 GiB when captured), not an external KV cache.

## Host policy

The reference host is one Threadripper PRO 9965WX NUMA node with four RTX PRO 6000 Blackwell Workstation GPUs. The LACT boot-persistent profile applies a 400 W cap and P0 memory offset `+1000` to every GPU; it applies no core offset. ReBAR and the NVIDIA PCIe P2P registry settings from the repository root are required for the tested P2P path.

## Important caveats

- The request ceiling (750k) exceeds the explicit full-CKV gather ceiling (262,144). Requests above the latter may use a different prefill path.
- `KV_FP8_ROPE=1` is enabled, but the dynamic NVFP4 MLA scale variables are not present. This records the actual r13 service; it is not a claim that this is the later documented complete dynamic-NVFP4 configuration.
- The profile contains deliberate legacy DCP/PCIe/Trellis overrides, including query split disabled and `*_DMA_FP8=ag`. It is not the later r26+ helper auto-policy.
- No benchmark or quality receipt is attached yet. Add a sanitized result summary to `RESULTS.md` when a controlled r13 run is performed.

## Apply

```bash
cp profile.env.example .env
docker compose --env-file .env -f compose.yml config
docker compose --env-file .env -f compose.yml up -d
```

Keep the populated `.env`, local mount paths, prompts, logs, and raw inspections private.
