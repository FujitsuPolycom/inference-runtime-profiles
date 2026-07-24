# GLM-5.2 v20 FP8-RoPE + Offload Promotion Candidate

Promotion candidate derived from daily. Tests FP8-RoPE + DRAM/NVMe offload
with PCIe i8-ring transport.

Parent profile: [glm52-daily-bf16rope-lmcache](../glm52-daily-bf16rope-lmcache/)

## Model

| Parameter | Value |
|---|---|
| Model ID | THU-SPI/GLM-5.2 |
| Quantization | MXFP8-A4Z16 (W4A8), FP8 RoPE, NF3 Grid188 |
| Tensor parallel | 4 |
| DCP | 4 |
| MTP | 3 (EAGLE) |
| Max context | 480K |
| KV cache dtype | nvfp4_ds_mla |
| Block size | 1600 |
| KV connector | OffloadingConnector (DRAM + NVMe) |
| GPU memory utilization | 98% |

## Hardware

| Component | Configuration |
|---|---|
| GPUs | 4x NVIDIA RTX PRO 6000 Blackwell, 96 GiB each |
| GPU topology | Single node, PCIe Gen5 x16 |
| CPU | AMD Threadripper PRO 9965WX |
| System RAM | 128 GiB |
| KV offload | DRAM + NVMe via OffloadingConnector |

## Apply

1. Copy `profile.env.example` to `.env`
2. Replace `REPLACE_WITH_*` placeholders
3. `docker compose up -d`
4. Wait for model load (~54 seconds)