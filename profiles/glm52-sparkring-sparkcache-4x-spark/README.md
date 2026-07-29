# GLM-5.2 SparkRing + SparkCache (4x DGX Spark)

Sanitized reference profile for serving
`aidendle94/GLM-5.2-MXFP4-Experts-GPTQ` on four directly cabled NVIDIA DGX
Spark systems. The inference fabric is a switchless 200 GbE RoCE ring:
each node uses both ConnectX-7 ports and no Ethernet switch carries model
payloads.

This profile records the live v47 deployment that produced the measurements in
[RESULTS.md](RESULTS.md). It also points to the newer public
[SparkRing](https://github.com/FujitsuPolycom/sparkring) source, but does not
claim that the public builder reproduces the complete measured runtime yet.

## Configuration

| Parameter | Value |
|---|---|
| Nodes | 4x NVIDIA DGX Spark, GB10, 128 GiB unified memory each |
| Model | `aidendle94/GLM-5.2-MXFP4-Experts-GPTQ` |
| Served name | `glm-5.2` |
| Parallelism | TP4 / DCP4 (`ag_rs`) / PP1 |
| Speculation | MTP4; adaptive verification depths 2 and 4, window 32 |
| KV cache | `nvfp4_ds_mla`, per-token scale |
| KV reservation | 4,000,000,000 bytes per rank |
| Logical KV capacity | 500,224 tokens measured in the reference deployment |
| Request ceiling | 458,752 tokens |
| Batch limits | 4,096 tokens / 8 sequences |
| Execution | `FULL_AND_PIECEWISE` CUDA graphs |
| Weight loader | safetensors |
| Context cache | SparkCache, DCP4-sharded NVMe persistence |

## What SparkRing supplies

- **SIRCL**, the Switchless Inference RDMA Collective Layer, for direct-cable
  inference collectives.
- Custom TP4 all-reduce, vocabulary, DCP query, and DCP combine paths.
- A checksum-pinned NCCL 2.30.7 switchless-ring fallback for collectives that
  have not moved to SIRCL.
- CUDA-graph-aware capture buckets through query width 40.
- SparkCache persistent context snapshots and restore for the DCP4-sharded KV
  layout.

The management interface carries SSH, Gloo, and NCCL bootstrap traffic only.
Model payloads use the two RoCE interfaces. Optional 10 GbE diagonal links are
not required by this reference profile and are not credited with the measured
throughput.

## Reproduction status

There are two source lanes:

1. **Measured reference lane (v47):** the exact locally built image and
   attested launch overlay used by the live cluster. Its identities are
   recorded in `manifest.json`, but the complete private vLLM overlay and
   orchestration layer are not published.
2. **Public next lane:** SparkRing commit
   `7840ce58794126c73f1076538938749aedb189b1`, which publishes SIRCL,
   SparkCache, the pinned runtime builder, and fail-closed public patches. Its
   larger reference vLLM overlay still needs provenance cleanup or independent
   replacement before it can reproduce every serving feature.

Consequently, `compose.yml` is an exact configuration envelope, not a promise
that stock vLLM plus the public repository will immediately produce the same
runtime. It deliberately requires private values for the image, launcher,
source bundle, native libraries, peer addresses, and artifact hashes. Do not
remove the attestation checks to make an incompatible build start.

## Fabric layout

Cable the four nodes as a ring. On every node, one ConnectX-7 port faces the
previous rank and the other faces the next rank:

```text
rank 0 ===== rank 1
  ||           ||
rank 3 ===== rank 2
```

Each `=====` is one direct 200 GbE RoCE link. Assign a distinct point-to-point
subnet to each physical edge. Populate `SPARK_TP4_PEER0` and
`SPARK_TP4_PEER1` with the two directly attached neighbor addresses for that
rank. Do not use the sample placeholders as addresses.

Before model launch, verify every cable in both directions with the cable and
RDMA probes documented by SparkRing. A link that negotiates but drops or
reorders under load is not an acceptable inference link.

## Apply

1. Build or obtain the attested reference-compatible image and native
   libraries.
2. Copy `profile.env.example` to a private `.env` on all four nodes.
3. Use identical artifact hashes and cluster-wide settings on every node.
4. Set per-node `NODE_RANK`, model/cache paths, management interface, direct
   neighbor addresses, and graph-status path.
5. Validate the rendered configuration:

   ```bash
   docker compose --env-file .env -f compose.yml config
   ```

6. Launch all four ranks as one coordinated operation. Rank 0 hosts the API;
   ranks 1-3 must run headless.
7. Require all four runtime attestations, graph census, transport counters, and
   a short correctness request to pass before admitting user traffic.

The reference orchestration is intentionally fail-closed. The Compose file uses
`restart: "no"` so one failed rank cannot independently rejoin a live
communicator.

## SparkCache

The live v47 profile enables native SparkCache restore with a 256 MiB native
arena and eight I/O workers. At approximately 393K tokens, foreground snapshot
work measured 3.63-4.16 seconds per rank and background commit completed in
11.23-15.55 seconds. The asynchronous store path avoided an 18-second
freeze-the-world event, though strict interference budgets were not yet met.

The public next lane adds stronger immutable checkpoint identity and source
contracts. Migrate those changes as a separately attested release; do not mix
v48-next hashes into a live v47 manifest.

## Safety and privacy

- Never commit `.env`, raw Docker inspection output, node addresses, Wi-Fi
  credentials, SSH usernames, model paths, or context snapshots.
- Keep management access independent of the two RoCE ports before rebinding or
  testing NIC drivers.
- Context snapshots may contain recoverable user data. Treat the SparkCache
  directory as sensitive model-serving storage.
- Preserve NCCL/SIRCL fallbacks and fail-closed checks until each replacement
  path has passed byte-exact or bounded-numerical shadow validation.
