# GLM-5.2 Daily BF16-RoPE + LMCache

Single-node 4-GPU profile. TP4 / DCP4 / MTP3, BF16 RoPE, 48 GB host-RAM
LMCache tier.

Child profile: [v20-promotion-fp8rope-offload](../glm52-v20-promotion-fp8rope-offload/)

## Model

| Parameter | Value |
|---|---|
| Model ID | THU-SPI/GLM-5.2 |
| Quantization | MXFP8-A4Z16 (W4A8), BF16 RoPE |
| Tensor parallel | 4 |
| DCP | 4 |
| MTP | 3 (EAGLE) |
| Max context | 128K |
| KV cache dtype | nvfp4_ds_mla |
| Block size | 1600 |

## Hardware

| Component | Configuration |
|---|---|
| GPUs | 4x NVIDIA RTX PRO 6000 Blackwell, 96 GiB each |
| GPU topology | Single node, PCIe Gen5 x16 |
| CPU | AMD Threadripper PRO 9965WX |
| System RAM | 128 GiB |
| LMCache L1 | 48 GiB host RAM (lazy mode) |

## Performance snapshots

| Metric | Value |
|---|---|
| Prefill | ~3,200 tok/s at ~120K |
| Decode C1 | ~80 tok/s class |
| Decode C2 | tested separately |
| GPU KV tokens | ~307,000 |
| Cold start (weight load) | ~54 seconds |
| Warm repeat | Sub-second to a few seconds |

## Apply

1. Copy `profile.env.example` to `.env`
2. Replace `REPLACE_WITH_*` placeholders
3. `docker compose up -d`
4. Wait for model load (~54 seconds)