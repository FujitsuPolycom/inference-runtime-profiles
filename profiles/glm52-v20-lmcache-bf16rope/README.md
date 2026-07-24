# GLM-5.2 v20 + LMCache, BF16 RoPE

Validated on the reference four-GPU PCIe host with TP4/DCP4/MTP3. This profile
uses the same LMCache and v20 settings as the FP8 profile, but preserves the
432-byte native CKV record layout.

- `KV_FP8_ROPE=0` -> 432-byte CKV records
- 48 GB RAM L1, 96 GB filesystem-backed NVMe L2
- `MAX_BATCHED_TOKENS=4096`, graph cap 32
- `DCP_PREFILL_WORKSPACE=auto`, `DCP_QUERY_SPLIT=0`, `DCP_CKV_GATHER=1`
- `GPU_MEMORY_UTILIZATION=0.9622`

Measured GPU KV capacity was 276,992 tokens. The L1/L2 cache behavior and
fixed-seed correctness checks passed. Expect lower capacity than FP8 RoPE.
See [RESULTS.md](RESULTS.md) for the benchmark status.
