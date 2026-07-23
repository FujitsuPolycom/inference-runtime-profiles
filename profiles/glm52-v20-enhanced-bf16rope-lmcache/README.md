# GLM-5.2 v20 + Local Enhancements (Staged)

This is the proposed migration of the daily stack onto the fixed v20 image.
It is **not GPU-validated yet**. The current daily profile remains the known
good rollback baseline.

## Base

- v20 image with the DCP workspace fixes
- `DCP_PREFILL_WORKSPACE=auto` (do not force `0`)
- TP4 / DCP4 / MTP3
- BF16 RoPE (`KV_FP8_ROPE=0`) to preserve the current accuracy comparison
- 300,000-token model limit, 3,072 batch tokens, graph 32
- NCCL tensor-parallel all-reduce
- 48 GB LMCache host-RAM tier

## Layered enhancements

The profile carries the flags for the features that are expected to remain
compatible with v20:

- replicated indexer KV with DCP-sharded main CKV
- full CKV gather and depth-3 prefetch
- shared-layer bulk sparse prefetch
- selected-record sparse decode over CE transport
- grouped LMCache RAM connector
- calibrated NVFP4 MLA scale file

The source overlays are intentionally not embedded in the image. Before GPU
validation, mount the v20-compatible versions of the vLLM/SparkInfer source
trees and verify the symbols listed above are present. If a flag is ignored,
the run is not an apples-to-apples enhanced test.

## Validation order

1. Start v20 base with CKV/sparse enhancements disabled.
2. Enable replicated indexer and CKV prefetch.
3. Enable sparse CE decode.
4. Enable LMCache RAM tier.
5. Run correctness at 64K and 300K before performance measurements.

