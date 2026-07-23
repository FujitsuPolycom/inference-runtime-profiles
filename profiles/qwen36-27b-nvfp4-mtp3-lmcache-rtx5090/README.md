# Qwen3.6-27B NVFP4 MTP3 + LMCache on RTX 5090

Single-GPU deployment of the `lyf/Qwen3.6-27B-uncensored-heretic-v2-NVFP4-MTP`
checkpoint with native MTP3 speculative decoding and LMCache two-tier KV cache.

## Hardware

This profile targets a single-GPU host with a consumer-class NVIDIA card.

| Component | Configuration |
|---|---|
| GPU | 1x NVIDIA RTX 5090, 32 GiB |
| CUDA | CUDA 13.0-class runtime; SM120 kernels |
| System RAM | 919 GiB (LMCache L1 uses 256 GiB as pinned host memory) |
| Storage | Optane RAID0 for LMCache L2 (~200 GB), pmem for HF/vLLM caches |

## Stack

- vLLM 0.25.1 with compat image (`patch_qwen_mtp_lm_head.py` patches the
  `lm_head` and MTP layer for BF16 tensor compatibility with NVFP4 checkpoints)
- LMCache 0.5.1 (bundled in vLLM 0.25.1 image) with MP connector
- Native MTP3 speculative decoding (draft model shares target embeddings + lm_head)
- Hybrid KV cache: attention (FP8) + Mamba/SSM layers, `mamba_cache_mode=align`
- Prefix caching + chunked prefill enabled
- `max_num_batched_tokens=3199` (2 * 1600 - 1 for LMCache unified block size)

## LMCache tiers

- L1: 256 GB lazy pinned host RAM, LRU eviction (80% trigger, 20% ratio)
- L2: fs_native adapter on Optane RAID0, 180 GB capacity, 32 workers, O_DIRECT

Both containers use `ipc: host` for CUDA IPC buffer sharing. The LMCache server
runs as a separate container with a health check; the inference container waits
for it before starting.

## Capacity

| Metric | Value |
|---|---|
| Model weights | 18.65 GiB |
| Available KV cache | 7.83 GiB |
| GPU KV cache tokens | 204,039 |
| KV cache blocks | 151 (block_size=1600) |
| Max concurrency at 131K context | 1.56x |
| Total VRAM in use | ~31.6 GiB (96.8%) |

## Measured performance

| Metric | Value |
|---|---|
| MTP3 acceptance rate | 70.5% (across 17 requests) |
| Inter-token latency p50 | 35 ms |
| Inter-token latency p99 | 50 ms |
| TTFT p50 | 250 ms |
| Decode throughput | ~99 tok/s |
| LMCache L1 store | 1600 tokens in 0.011 s |
| LMCache L1 retrieve | 1600 tokens in 0.001 s |
| LMCache external hit rate | 16.5% (repeated-prefix stress test) |
| Preemptions | 0 |

## Known issues

- LMCache L2 (Optane) store fails with O_DIRECT on the RAID0 filesystem; L1
  RAM cache works correctly. Set `use_odirect=false` in the L2 adapter config
  if L2 persistence is needed.
- Prompts above ~3200 tokens may OOM at `gpu_memory_utilization=0.88` due to
  GDN/FLA chunk kernel temporary memory. Lower to 0.85 if longer prompts are
  needed.
- The compat image requires `patch_qwen_mtp_lm_head.py` to be applied during
  build. See the [lab repo](https://github.com/FujitsuPolycom/pve03-qwen27b-lmcache-lab)
  for the Dockerfile and patch script.

## Applying

```bash
cp profile.env.example .env
# Edit .env: set HF_CACHE_DIR, VLLM_CACHE_DIR, LMCACHE_L2_DIR to local paths
docker compose --env-file .env -f compose.yml up -d
```
