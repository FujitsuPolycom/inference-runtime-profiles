# DeepSeek-V4-Flash-0731 on 2x DGX Spark — SparkRing runtime, DSpark speculation, LMCache NVMe tier

Status: **qualified** — serving live on the reference pair with the
correctness gates in [RESULTS.md](RESULTS.md) passed 2026-08-19. Formal
throughput benchmarks beyond the single-stream measurement are pending.

## What this is

DeepSeek-V4-Flash (the 284B-parameter MoE, FP8 revision `913f0657a874` of
`deepseek-ai/DeepSeek-V4-Flash-0731`, 156 GB) served at TP2 across two NVIDIA
DGX Sparks connected by a direct 200GbE cable, with:

- **DSpark speculative decoding, depth 5** — serving correctly. On this
  runtime's component set (B12X MoE under speculation), the tool-heavy
  request class that corrupts output on a from-source humming-W4A16 build
  streams back clean. Measured single-stream decode: **~40 tok/s** vs 28.3
  without speculation on the same pair.
- **A persistent LMCache NVMe KV tier** — prefixes computed once are stored
  to NVMe and restored across full restarts of every process. Measured: an
  18,688-token context restored in 0.051 s with a byte-identical completion.
  With speculation active the engine registers **170 cache layers**
  wholesale (MLA latent KV, Lightning Indexer FP8 cache, sliding-window
  compressor state, SWA, and the three DSpark hidden-state caches), which is
  what makes restore correctness possible for this model.

The runtime is **not built here**: it is the SparkRing project's docker image
(`FujitsuPolycom/sparkring` — its `runtime/exl3-r7/pins.json` is the
component identity, `runtime/` the build recipe), image digest
`sha256:02881d5229d4f4d1cbba0cf40537492a2a505b9d4e43bbfe9a0b2a7bd0584513`
(tag `sparkring/glm52-exl3-r7-3.5bpw:r34-sm121a-flat2-20260810`), plus that
project's runtime overlay files bind-mounted over the image (the 47 paths in
[leg3pair.binds](leg3pair.binds)). This profile records how to run that
runtime on a two-node pair.

## Requirements

- 2x NVIDIA DGX Spark (GB10, ~121 GB unified memory each), driver 580.x,
  connected by at least one direct ConnectX-7 200GbE cable (RoCE).
- The SparkRing runtime image loaded on both nodes (build per the SparkRing
  repository's runtime recipe, or transfer the image from an existing
  SparkRing deployment; verify the digest above).
- The SparkRing runtime overlay files staged at their `/var/tmp/...` paths on
  both nodes — the exact path list is [leg3pair.binds](leg3pair.binds); the
  file contents correspond to the SparkRing repository's `runtime/` and
  `spark_transport/integrations/vllm/` trees. On the reference pair they were
  copied verbatim from a live SparkRing deployment.
- The checkpoint at
  `$HOME/work/qwen38-exl3/model/DeepSeek-V4-Flash-0731` on both nodes
  (`huggingface-cli download deepseek-ai/DeepSeek-V4-Flash-0731 --revision
  913f0657a874...` — 156 GB, 48 shards).
- For the cache tier: the LMCache wheel described below.

## Site constants to edit

The scripts carry the reference pair's values; adjust for your site:
fabric IPs `198.18.200.1/.2` (rank 0/1) and fabric interface `enp1s0f0np0`
in `leg3pair-launch.sh`; LAN IPs `192.168.0.200/.174` in the
`kv-transfer-config` server URLs; RDMA device `rocep1s0f0` and its GID index
(`0` = RoCE v1 on the reference pair); model and L2 paths under
`$HOME/work/qwen38-exl3/`.

## The LMCache wheel

The image ships lmcache `0.5.2+glm52dcp4.1`, an older cut of the fork lineage
that predates the hybrid cache-group transfer support this model's restore
correctness depends on. Build the qualified branch against the **image's**
torch (2.12) and the wheel is installed over it at container start:

```bash
git clone --branch release/v0.5.2-glm52-dcp-base --single-branch \
    https://github.com/local-inference-lab/LMCache
# verify: git rev-parse HEAD^{tree}  == e045d729bc5c... (the r18-qualified tree)
# apply the heartbeat dead-guard patch (the `{} is not None` guard at
# vllm_multi_process_adapter.py:730,733 makes the servers reap a healthy
# engine after ~150 s idle without it)
docker run --rm --entrypoint /bin/bash -v $PWD:/src -v $HOME/wheels:/out \
  -e TORCH_CUDA_ARCH_LIST=12.1 <sparkring-image> \
  -c 'cd /src && /opt/venv/bin/pip wheel . --no-deps --no-build-isolation -w /out'
```

Place the wheel in `$HOME/work/qwen38-exl3/wheels-t212/` on both nodes.

## Deploy

1. Stage overlays, model, wheel, and the two scripts
   ([leg3pair-launch.sh](leg3pair-launch.sh) →
   `$HOME/work/qwen38-exl3/`, [leg3pair-inner.sh](leg3pair-inner.sh) →
   `/var/tmp/`), plus [leg3pair.env](leg3pair.env) and
   [leg3pair.binds](leg3pair.binds) → `/var/tmp/`, on both nodes.
2. Launch rank 1 first, then rank 0 (each on its own host):
   `RANK=1 bash leg3pair-launch.sh` / `RANK=0 bash leg3pair-launch.sh`.
   `LMCACHE=0` launches without the cache tier. First launch pays a long
   JIT/AOT compile (the `/var/tmp/leg3-cache` mount persists it; later
   launches are much faster).
3. Verify: `curl localhost:8000/v1/models` on rank 0; the cache server log at
   `<L2 dir>/server.log` shows `Registered KV cache ... with 170 layers`.
4. Optional boot persistence: install
   [boot-dsv4-aa42.sh](boot-dsv4-aa42.sh) (rank 0) /
   [boot-dsv4-931e.sh](boot-dsv4-931e.sh) (rank 1) as `@reboot` user crontab
   entries. Both launch only when the container is absent, so the two boot
   paths cannot tear down a live follower.
5. Validate before trusting: run the gates in [RESULTS.md](RESULTS.md) —
   at minimum the cold-restart replay with planted-fact probes and the
   >10-minute-idle heartbeat check. Byte-identity is only meaningful under
   identical single-request greedy conditions; the behavioral gates use
   answer correctness.

## Configuration reference (deltas from the 4x SparkRing ring)

The launch is the ring's DeepSeek container spec with exactly these changes:

| Delta | Value | Why |
|---|---|---|
| Parallelism | `--tensor-parallel-size 2 --nnodes 2`, rank 1 `--headless` | two nodes |
| Custom transport | `SPARK_TP4_*` / `VLLM_SPARK_TP4_*` env removed | its source admits only `world_size == 4`; NCCL carries TP2 collectives (`VLLM_SPARK_SHARED_CAPTURE_STREAM=1` is kept — a source-patch gate the speculative graph capture needs, not a transport setting) |
| NCCL | single rail `rocep1s0f0`, GID 0, subnet-aware routing off | point-to-point pair, not a switchless 4-cycle |
| Speculation depth | 5 (ring runs 7) | 5 = the checkpoint's `dspark_block_size`, the validator's minimum; 7 also valid |
| Memory envelope | `--max-model-len 131072`, `--kv-cache-memory-bytes` 10 GiB, `--max-num-seqs 8`, `--gpu-memory-utilization 0.70` | TP2 doubles per-rank weight residency (~84 GB); 0.70 is the GB10 unified-memory ceiling above which loads are OOM-killed silently |
| Cache tier | wheel install + in-container MP server + `--kv-transfer-config` + `expandable_segments:False` | the connector pins KV via CUDA IPC; the VMM allocator must not remap. Server and engine share the container lifecycle, so a replacement can never leave a server holding a dead engine's IPC mappings |

Known limitations: depth 5 per-position acceptance is ~0.76/0.55/0.27/0.14/
0.07 (a depth-3 sweep is the obvious next tuning step); the memory envelope
has unmeasured headroom (KV usage <1% under single-stream load); concurrency
and long-context benchmarks are not yet published.
