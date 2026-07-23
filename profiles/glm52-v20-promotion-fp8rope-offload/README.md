# GLM-5.2 v20 Promotion / FP8-RoPE Offload Profile

Sanitized representation of the v20 promotion candidate used for D-Rock
validation.

- TP4 / DCP4 / MTP3
- `nvfp4_ds_mla` with FP8 RoPE and 368-byte records
- Grid188 and v20 B12X decode features
- PCIe all-reduce with `i8_ring` FP8 DMA
- 480,000-token model limit
- 64 GB DRAM offload plus a filesystem/NVMe tier

This is deliberately separate from the daily profile. It does not claim to
contain the daily profile's replicated-indexer, depth-3 sparse-prefetch, or CE
sparse-decode overlay. Fill in local paths privately and capture the exact
image/source metadata after launch.

