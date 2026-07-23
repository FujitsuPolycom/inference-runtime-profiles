# GLM-5.2 Daily BF16-RoPE Profile

Sanitized representation of the validated 4-GPU daily stack.

- TP4 / DCP4 / MTP3
- `nvfp4_ds_mla` with BF16 RoPE and 432-byte resident records
- Replicated indexer KV with DCP-sharded main CKV
- Full CKV gather and depth-3 shared-layer prefetch
- Sparse selected-record decode over CE transport
- NCCL tensor-parallel all-reduce
- LMCache grouped 48 GB host-RAM tier
- 300,000-token model limit and 3,072-token batch limit

This profile is a template. Replace the image digest and local paths in a
private `.env`; do not commit those values. Capture the exact deployed image
and source revisions with `tools/Capture-Profile.ps1` after startup.

