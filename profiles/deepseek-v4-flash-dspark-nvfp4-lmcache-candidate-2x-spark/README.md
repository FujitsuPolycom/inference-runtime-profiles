# DeepSeek V4 Flash DSpark NVFP4 + LMCache Candidate (2x Spark, 4x GPU)

Isolated test profile that adds CPU RAM KV offloading to the DeepSeek V4 Flash DSpark Stage C
configuration. Uses the upstream vLLM `SimpleCPUOffloadConnector` which supports multi-group KV
cache (HMA) and packed DSv4 tensors natively.

Parent profile: [deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark](../deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark/)

## Model

| Parameter | Value |
|---|---|
| Model ID | deepseek-ai/DeepSeek-V4-Flash-DSpark |
| Quantization | NVFP4 |
| Served name | DeepSeek-V4-Flash-NVFP4-LMCache-Candidate |
| Tensor parallel | 2 (split across two Spark nodes) |
| MTP | 3 |
| Max context | 1,048,576 |
| KV cache dtype | nvfp4_ds_mla |
| Block size | 256 |
| GPU memory utilization | 75% (reduced to accommodate connector overhead) |
| KV connector | SimpleCPUOffloadConnector |
| CPU offload RAM | 2 GiB per rank (4 GiB total) |

## What Changed vs Stage C

| Parameter | Stage C (production) | Candidate |
|---|---|---|
| Port | 18006 | 18007 |
| Served name | DeepSeek-V4-Flash-NVFP4-StageC | DeepSeek-V4-Flash-NVFP4-LMCache-Candidate |
| KV connector | none | SimpleCPUOffloadConnector |
| CPU offload RAM | n/a | 2 GiB per rank (4 GiB total) |
| GPU mem util | 80% | 75% |
| PYTORCH_CUDA_ALLOC_CONF | expandable_segments:True | (unset — incompatible with connector) |
| Compose project | ds4f-nvfp4 | ds4f-nvfp4-lmcache-candidate |
| LiteLLM route | spark-dsv4f -> :18006 | NOT routed (test only) |

Everything else is identical: same model, same image, same topology (TP2/DCP1),
same KV dtype (nvfp4_ds_mla), same block size (256), same MTP3, same b12x env.

## Hardware

| Component | Configuration |
|---|---|
| GPUs | 2x NVIDIA GPUs per Spark node (2-node TP2) |
| GPU topology | Two-node tensor parallel over RDMA fabric |
| CUDA | CUDA 12.1a-class runtime |
| Storage | NVMe-backed model/cache filesystem |
| Parallelism | TP2 / DCP1 / MTP3 |

## Apply

1. Copy `profile.env.example` to `.env` on both Spark nodes
2. Replace all `REPLACE_WITH_*` placeholders
3. Use the same values on both nodes except `NODE_RANK` (0 on head, 1 on peer)
4. Set `MASTER_ADDR` to the head node IP
5. Set `NCCL_IB_HCA` / `NCCL_SOCKET_IFNAME` / `GLOO_SOCKET_IFNAME` to match RDMA interface
6. `docker compose up -d` on both nodes

## Verify

```bash
# Wait for model load (~130s cold start)
curl -s http://localhost:18007/v1/models | python3 -m json.tool
```

## Rollback

```bash
# Stop candidate on both nodes
docker compose -p ds4f-nvfp4-lmcache-candidate down

# Production Stage C on :18006 is untouched — no rollback needed
```