# Qwen3.6-27B NVFP4 MTP3 + LMCache (RTX 5090, 1x GPU)

Single-GPU profile for Qwen3.6-27B on a consumer RTX 5090 (32 GiB). Uses
NVFP4 quantization with MTP3 speculative decoding and LMCache for KV
reuse across sessions.

## Model

| Parameter | Value |
|---|---|
| Model ID | lyf/Qwen3.6-27B-uncensored-heretic-v2-NVFP4-MTP |
| Quantization | NVFP4 (mixed FP4) |
| Served name | Qwen3.6-27B-FP8-MTP |
| Tensor parallel | 1 |
| MTP | 3 |
| Max context | 131,072 |
| KV cache dtype | FP8 |
| Block size | 1600 |
| GPU memory utilization | 88% |

## Hardware

| Component | Configuration |
|---|---|
| GPU | 1x NVIDIA RTX 5090, 32 GiB |
| System RAM | 919 GiB (256 GiB pinned for LMCache L1) |
| CUDA | CUDA 13.0-class runtime; SM120 kernels |
| Storage | Optane RAID0 (~200 GB) for LMCache L2 |
| Parallelism | TP1 / MTP3 |

## Apply

1. Copy `profile.env.example` to `.env`
2. Replace `REPLACE_WITH_*` placeholders
3. `docker compose up -d`
4. Wait for model load (~135 seconds)