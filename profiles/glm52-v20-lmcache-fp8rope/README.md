# GLM-5.2 v20 + Grouped LMCache, FP8 RoPE

Current daily profile for the reference four-GPU PCIe workstation. This is
the latest stock v20 runtime with grouped LMCache added; the experimental
replicated-indexer and sparse-decode overlays are disabled.

## Checkpoint

| Field | Value |
|---|---|
| Hugging Face repository | [`madeby561/GLM-5.2-MXFP8-NVFP4-NF3-Hybrid`](https://huggingface.co/madeby561/GLM-5.2-MXFP8-NVFP4-NF3-Hybrid) |
| Local directory | `GLM-5.2-MXFP8-NVFP4-NF3-Hybrid` |
| Model family | GLM-5.2 hybrid/MoE/DSA |
| Quantization | NVFP4 + NF3 hybrid, MXFP8-served non-expert layers |
| KV implementation | `nvfp4_ds_mla` |
| KV record format | 368 bytes, FP8 RoPE |
| Served name | `GLM-5.2` |

## Reference hardware

- 4x NVIDIA RTX PRO 6000 Blackwell, 96 GiB each
- AMD Threadripper PRO 9965WX
- ASUS Pro WS WRX90E-SAGE SE
- 128 GiB system RAM 8x16GB DDR5-6400
- PCIe Gen5 x16-class GPU links, direct motherboard/riser topology
- TP4 / DCP4 / MTP3

## IMPORTANT: P2P Settings - Without this expect -30% decode loses at C1+
The NVIDIA P2P and Resizable BAR settings are required for the reference
decode results. Verify them with the repository hardware checks before use on
another machine.

Verify: 
```bash
grep -E 'EnableResizableBar|RegistryDwords' /proc/driver/nvidia/params
```
 - EnableResizableBar: 1
 - ForceP2P=0x11
 - RMForceP2PType=1
 - RMPcieP2PType=2
 - GrdmaPciTopoCheckOverride=1

options nvidia NVreg_RegistryDwords="ForceP2P=0x11;RMForceP2PType=1;RMPcieP2PType=2;GrdmaPciTopoCheckOverride=1;EnableResizableBar=1"

## Runtime configuration

| Setting | Value |
|---|---|
| Base image lineage | `voipmonitor/vllm:gilded-gnosis-v20-vllm7e3bee1-si6234185-fi801d57a-cu132-20260723` |
| Current local image | `ai01/glm52-v20-lmcache:grouped-dcp-0.5.2-hma` |
| Maximum model length | `400384` tokens |
| Maximum available GPU KV | `433152` tokens |
| Maximum sequences | `8` |
| Maximum batched tokens | `3072` |
| CUDA graph ceiling | `32` |
| GPU memory utilization | `0.9640` |
| KV RoPE mode | `KV_FP8_ROPE=1` |
| DCP prefill workspace | `auto` |
| DCP query split | `0` |
| DCP CKV gather | `1` |
| Replicated indexer cache | `0` |
| Sparse decode CKV gather | `0` |
| Sparse decode bulk prefetch | `0` |
| PCIe all-reduce | Enabled, C++ backend |
| Fused RTX6K all-reduce | Disabled |

The 433,152-token value is the runtime-reported GPU KV capacity. It is larger
than the 400,384-token per-request ceiling to leave allocator and scheduling
headroom; it is not an instruction to raise `MAX_MODEL_LEN` to the full KV
capacity.

## LMCache configuration

LMCache is grouped by DCP rank and has two tiers:

| Tier | Configuration |
|---|---|
| L1 | 48 GiB host RAM, preallocated |
| L2 | 96 GiB NVMe-backed local disk |
| Chunk size | 512 tokens |
| Disk sharding | `by_gpu` |
| Async loading | Disabled |
| Layerwise mode | Disabled |
| Decode-cache saving | Disabled |

Relevant variables:

```text
LMCACHE_DCP_GROUPED=1
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=48
LMCACHE_LOCAL_DISK=file:///lmcache-l2
LMCACHE_MAX_LOCAL_DISK_SIZE=96
LMCACHE_LOCAL_DISK_PATH_SHARDING=by_gpu
LMCACHE_CHUNK_SIZE=512
LMCACHE_ENABLE_ASYNC_LOADING=False
LMCACHE_USE_LAYERWISE=False
LMCACHE_SAVE_DECODE_CACHE=False
```

## Source lineage

The exact source metadata for the live deployment is in [`manifest.json`](manifest.json).
The important revisions are:

- vLLM: `7e3bee1ed4bc87efbdc36060647a3475cfaa1f1e`
- B12X/SparkInfer: `62341856cc5497d0c8ba33012dab6118925a6cfb`
- FlashInfer: `801d57a08958c13d375ddbb6be3be4808f48a708`
- CUDA: `13.2.1`
- PyTorch: `2.12.0+cu132`
- NCCL: `2.30.4`

The current image is a local LMCache overlay. A public v20 image alone does
not reproduce the grouped LMCache integration.

## Apply

Copy the sanitized environment template and replace only local paths and the
image reference:

```bash
cp profile.env.example .env
docker compose --env-file .env -f compose.yml config
docker compose --env-file .env -f compose.yml up -d
```

Required host-local mounts are:

- model directory, mounted read-only at `/model`
- writable JIT/cache directory at `/cache`
- writable NVMe LMCache directory at `/lmcache-l2`

Do not commit `.env`, raw Docker inspection output, hostnames, IP addresses,
model-cache paths, credentials, or request prompts.

## Validation

After startup, verify the logs contain values equivalent to:

```text
GPU KV cache size: 433152 tokens
Maximum concurrency for 400384 tokens per request: 1.08x
Application startup complete
```

Run the repository P2P check before benchmarking. Then use the standardized
commands in [`../../BENCHMARKING.md`](../../BENCHMARKING.md). Results for the
current profile are in [`RESULTS.md`](RESULTS.md).

## Measured snapshot

The latest 10-run coding peak reached 134.3 tok/s median, 135.5 tok/s mean,
and 143.2 tok/s maximum. Cold/integrated prefill measured approximately
3,318 tok/s at 8K, 3,051 at 16K, 3,081 at 32K, 3,024 at 64K, 2,902 at 128K,
2,794 at 200K, and 2,593 at 356K.

Decode and prefill details, including capacity-limited cells, are recorded in
[`RESULTS.md`](RESULTS.md). These are short operational snapshots rather than
confidence intervals.
