# DeepSeek V4 Flash DSpark NVFP4 Stage C (2x Spark, 4x GPU)

Sanitized representation of a production-oriented, memory-focused DeepSeek V4
Flash DSpark profile for two Blackwell DGX Spark nodes connected over QSFP
RDMA fabric.

## Model

| Parameter | Value |
|---|---|
| Model ID | deepseek-ai/DeepSeek-V4-Flash-DSpark |
| Quantization | NVFP4 |
| Served name | DeepSeek-V4-Flash-NVFP4-StageC |
| Tensor parallel | 2 (split across two Spark nodes) |
| MTP | 3 |
| Max context | 1,048,576 |
| KV cache dtype | nvfp4_ds_mla |
| Block size | 256 |
| GPU memory utilization | 80% |

## Hardware

| Component | Configuration |
|---|---|
| GPUs | 2x NVIDIA GPUs per Spark node (2-node TP2) |
| GPU topology | Two-node tensor parallel over RDMA fabric |
| CUDA | CUDA 12.1a-class runtime |
| Storage | NVMe-backed model/cache filesystem |
| Parallelism | TP2 / DCP1 / MTP3 |

## Key Features

- TP2 / PP1 / DSpark MTP3 with probabilistic draft sampling
- `nvfp4_ds_mla` KV cache with a fixed 10 GiB allocation per rank
- 1,048,576-token request ceiling and an engine-reported 1,515,055-token
  usable shared KV pool
- Eight sequence slots with an 8,192-token batch budget
- CUDA graph capture size computed as `max_num_seqs * (mtp + 1)` = 32
- Prefix caching, chunked prefill, asynchronous scheduling, and FlashInfer
  autotuning enabled
- RDMA transport via NCCL IB, with NCCL and Gloo pinned to the deployment's
  fabric interfaces through the private `.env`
- B12x MoE and WO-projection paths enabled with tuned W4A16 block overrides
- Triton MLA sparse attention with 256 MiB sparse-indexer logits budget
- DSpark proposer patched via read-only bind mount of `dspark_proposer.py`
- Reasoning parser `deepseek_v4` with explicit `reasoning_start_str`/`reasoning_end_str`
  markers and `thinking: false` default chat template

## Apply

Copy `profile.env.example` to a private `.env` on both nodes. Use the same
values on each node except `NODE_RANK`; set it to `0` on the fabric head and
`1` on the peer. Set `MASTER_ADDR`, RDMA interface names (`NCCL_IB_HCA`,
`NCCL_SOCKET_IFNAME`, `GLOO_SOCKET_IFNAME`, `TP_SOCKET_IFNAME`), model cache
location, `DSPARK_PROPOSER_PATH`, and image reference privately.

The compose file uses `shm_size: 68719476736` (64 GiB) to accommodate the
multi-node tensor-parallel collective buffers. Docker's default 64 MiB shared
memory is insufficient and will cause NCCL timeouts.
## Key Environment Variables

### DSpark Speculative Decoding

| Variable | Value | Purpose |
|----------|-------|---------|
| `MTP_NUM_TOKENS` | 3 | Number of speculative tokens per draft |
| `VLLM_DSPARK_CONFIDENCE_THRESHOLD` | 0.0 | No confidence filtering on drafts |
| `VLLM_DSPARK_CONFIDENCE_SCHEDULER` | off | Disable confidence-based scheduling |
| `VLLM_DSPARK_LOCAL_ARGMAX` | 1 | Use local argmax for draft selection |
| `VLLM_DSPARK_REPLICATE_MARKOV_W1` | 1 | Replicate Markov W1 weights |
| `VLLM_DSPARK_GPU_REJECTED_CONTEXT_MASK` | 1 | GPU-side rejected context masking |
| `VLLM_DSPARK_HARDWARE_SCHEDULER_EARLY_STOP` | 1 | Early-stop hardware scheduler |
| `VLLM_DSPARK_FUSED_MARKOV_ARGMAX` | 0 | Disable fused Markov argmax |
| `VLLM_DSPARK_REFERENCE_KV_QUANT_DEQUANT` | 0 | Disable reference KV quant/dequant |

### B12x MoE

| Variable | Value | Purpose |
|----------|-------|---------|
| `VLLM_USE_B12X_MOE` | 1 | Enable B12x MoE fused kernels |
| `VLLM_USE_B12X_WO_PROJECTION` | 1 | Enable WO projection fusion |
| `B12X_W4A16_TC_DECODE` | 0 | Disable tensor-core decode path |
| `VLLM_B12X_W4A16_FORCE_BLOCKS_MAX_M` | 16 | Max M dimension for W4A16 blocks |
| `VLLM_B12X_W4A16_FORCE_BLOCKS_PER_SM` | 0 | Auto-select blocks per SM |
| `VLLM_B12X_W4A16_FORCE_TILE_CONFIG` | (empty) | Auto-select tile config |

### Sparse Attention

| Variable | Value | Purpose |
|----------|-------|---------|
| `VLLM_TRITON_MLA_SPARSE` | 1 | Enable Triton MLA sparse attention |
| `VLLM_SPARSE_INDEXER_MAX_LOGITS_MB` | 256 | Max logits buffer for sparse indexer |

### RDMA / NCCL

| Variable | Example | Purpose |
|----------|---------|---------|
| `NCCL_NET` | IB | Use InfiniBand transport |
| `NCCL_IB_HCA` | rocep1s0f1 | RDMA HCA device |
| `NCCL_SOCKET_IFNAME` | enp1s0f1np1 | NCCL socket interface |
| `GLOO_SOCKET_IFNAME` | enp1s0f1np1 | Gloo transport interface |
| `TP_SOCKET_IFNAME` | enP7s7 | Tensor-parallel control interface |
| `NCCL_CROSS_NIC` | 1 | Enable cross-NIC communication |
| `NCCL_CUMEM_ENABLE` | 0 | Disable CUDA memory management |
| `NCCL_IGNORE_CPU_AFFINITY` | 1 | Ignore CPU affinity for NCCL |
| `NCCL_NVLS_ENABLE` | 0 | Disable NVLink SHARP |

## Apply

1. Copy `profile.env.example` to `.env` on both Spark nodes
2. Replace all `REPLACE_WITH_*` placeholders
3. Use the same values on both nodes except `NODE_RANK` (0 on head, 1 on peer)
4. Set `MASTER_ADDR` to the head node IP
5. Set `NCCL_IB_HCA` / `NCCL_SOCKET_IFNAME` / `GLOO_SOCKET_IFNAME` to match RDMA interface
6. `docker compose up -d` on both nodes