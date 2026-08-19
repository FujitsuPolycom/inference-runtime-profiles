# GLM-5.2 v20 r13 EXL3 3.0 bpw — 750k ceiling

Live-captured single-node four-GPU profile for the `brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw` checkpoint, quantized to 3.0 bits per weight in the EXL3 format (exllamav3 Trellis quantization). The sibling profile `profiles/glm52-v20-r7-exl3-3bpw` covers the same checkpoint on the v20 R7 runtime with a 262,144-token ceiling and serves as the rollback/reproduction record.

## Runtime and model

| Field | Value |
|---|---|
| Checkpoint | [`brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw`](https://huggingface.co/brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw) |
| Runtime | Gilded Gnosis v20 r13, vLLM `0.11.2.dev280…r13` — "r13" (like the sibling's "R7") is the revision tag of the Gilded Gnosis private vLLM image lineage; the immutable image digest below is the durable identifier |
| Immutable image | `voipmonitor/vllm@sha256:02796036c96a52fda0919aa260c45c70bc97d8e662a6ae5e614b5f987c20851b` |
| Parallelism | TP4 / DCP4 / MTP3 (tensor-parallel 4, decode-context-parallel 4, multi-token-prediction speculative depth 3) |
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
- `KV_FP8_ROPE=1` is enabled; dynamic NVFP4 MLA scale variables are not present.
- The profile contains deliberate manual DCP/PCIe/Trellis overrides, including query split disabled and `*_DMA_FP8=ag`.
- No benchmark or quality receipt is attached yet. Add a sanitized result summary to `RESULTS.md` when a controlled r13 run is performed.

## Apply

```bash
cp profile.env.example .env
docker compose --env-file .env -f compose.yml config
docker compose --env-file .env -f compose.yml up -d
```

Keep the populated `.env`, local mount paths, prompts, logs, and raw inspections private.
