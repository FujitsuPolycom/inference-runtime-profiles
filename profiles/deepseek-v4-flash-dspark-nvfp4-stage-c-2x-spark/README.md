# DeepSeek V4 Flash DSpark NVFP4 Stage C on Two DGX Spark Nodes

Sanitized representation of a production-oriented, memory-focused DeepSeek V4
Flash DSpark profile for two Blackwell Spark-class nodes.

* TP2 / PP1 / DSpark MTP3
* `nvfp4_ds_mla` KV cache with a fixed 10 GiB allocation per rank
* 1,048,576-token request ceiling and an engine-reported 1,515,055-token
  usable shared KV pool
* Eight sequence slots with an 8,192-token batch budget
* Prefix caching, chunked prefill, asynchronous scheduling, and FlashInfer
  autotuning enabled
* RDMA transport, with NCCL and Gloo pinned to the deployment's fabric
  interfaces through the private `.env`

This profile intentionally does not include LMCache. Its target is long-lived
agentic coding work where resident NVFP4 KV capacity is more valuable than a
larger host-side prefix tier.

## Applying The Template

Copy `profile.env.example` to a private `.env` on both nodes. Use the same
values on each node except `NODE_RANK`; set it to `0` on the fabric head and
`1` on the peer. Set `MASTER_ADDR`, RDMA interface names, model cache location,
and image reference privately.

Start the peer first, then the head, with the same compose template and each
node's private `.env`. The compose file is a launch template, not a complete
cluster manager: it assumes a reachable RDMA fabric and existing local model
cache.

## Notes

The recorded image is a locally built runtime tag, so the public template uses
an image placeholder rather than claiming a registry-published digest. Review
the generated compose configuration and benchmark the target hardware before
promoting it to a default service.
