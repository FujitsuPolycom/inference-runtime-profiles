# GLM-5.2 v20 + LMCache, FP8 RoPE

Validated on the reference four-GPU PCIe host with TP4/DCP4/MTP3. This is the
working v20 LMCache-only profile: sparse decode and replicated-indexer overlays
are intentionally absent.

## Customization boundary

- Model execution is the published Gilded Gnosis v20 vLLM/SparkInfer stack.
- The local image adds LMCache and its grouped-DCP integration.
- A startup wrapper configures the 48 GB RAM and 96 GB filesystem tiers.
- No custom sparse-decode, replicated-indexer, or CKV-prefetch source overlay is
  mounted into the running container.

## Settings

- `KV_FP8_ROPE=1` -> native 368-byte CKV records
- 48 GB RAM L1, 96 GB filesystem-backed NVMe L2
- `MAX_MODEL_LEN=300000`
- `MAX_BATCHED_TOKENS=4096`, graph cap 32
- `DCP_PREFILL_WORKSPACE=auto`, `DCP_QUERY_SPLIT=0`, `DCP_CKV_GATHER=1`
- `GPU_MEMORY_UTILIZATION=0.9622`

The current profiled capacity is 301,279 global GPU KV tokens. Decode measured
113.3 tok/s at 8K and 111.8 tok/s at 64K, C1. Repeated requests produced L1
hits; a controlled 1 GB-L1 pressure test produced explicit L2 hits. A fixed-
seed, temperature-zero response matched clean v20 byte-for-byte.

Use the repository hardware/P2P checks before deployment. Do not raise memory
utilization to `.98` by default; it is a stress-test value because manual
memory pinning can hide transient graph allocations.
