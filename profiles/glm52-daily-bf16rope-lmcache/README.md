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
- CUDA graph capture limit 32
- InstantTensor weight loading
- B12X MoE, sparse indexer, MLA, and no PCIe all-reduce

## Effective launch

The image is launched through `/usr/local/bin/serve-glm52-lmcache.sh`, which
builds the `vllm serve` command. The effective profile is:

```text
TP4 / DCP4 / MTP3 / DCP backend a2a
model length 300000 / max sequences 8 / max batched tokens 3072
GPU utilization 0.98 / KV pin 3489660928 bytes / graph 32
attention B12X_MLA_SPARSE / quantization nvfp4_nf3_hybrid
load format instanttensor / NCCL tensor-parallel all-reduce
```

The running deployment also bind-mounts the custom vLLM and SparkInfer source
trees plus small overlay files for the replicated-indexer, KV coordinator,
CKV/prefetch, scale-file, and LMCache integration changes. Those source trees
are intentionally represented as placeholders in this public profile; capture
their Git commit IDs separately when publishing a deployment manifest.

## Capacity

The current deployment reports approximately 307,712 GPU KV tokens. The 48 GB
LMCache setting is a host-RAM cache tier and does not increase GPU KV capacity;
it stores reusable KV outside VRAM for prefix reuse and reloads.

This profile is a template. Replace the image digest and local paths in a
private `.env`; do not commit those values. Capture the exact deployed image
and source revisions with `tools/Capture-Profile.ps1` after startup.
