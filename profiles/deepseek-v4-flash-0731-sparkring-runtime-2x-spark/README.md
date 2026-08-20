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

The runtime is **not built here**: it is the SparkRing project's image plus
three patch files bind-mounted over it. This profile records how to run that
runtime on a two-node pair. Pull the image from the GitHub Container Registry:

```bash
docker pull ghcr.io/fujitsupolycom/gb10-vllm-serving:r34-20260810
```

| Identifier | Value |
|---|---|
| Registry reference | `ghcr.io/fujitsupolycom/gb10-vllm-serving:r34-20260810` |
| Manifest digest, for pinning | `sha256:df0e2068fc7034a1ec7a2c1fa4e0c3224c720161539525b5a7cbb037dc1d0f8e` |
| Image ID after pull | `sha256:02881d5229d4f4d1cbba0cf40537492a2a505b9d4e43bbfe9a0b2a7bd0584513` |
| Size, architecture | 30.8 GB, arm64 |

The published image is a flattened single-layer capture: `docker history`
reports one layer created by import, so it carries no build steps. Its
component identity lives in its own labels — vLLM commit `fcc61414` from
`local-inference-lab/vllm`, b12x commit `284a2eae`, torch 2.12.0+cu132, NCCL
2.30.4 — and in `runtime/exl3-r7/pins.json` in `FujitsuPolycom/sparkring`,
whose builder overlay is on a separate branch. Rebuilding it from source is
therefore a SparkRing task, not something this profile describes.

## Requirements

- 2x NVIDIA DGX Spark (GB10, ~121 GB unified memory each), driver 580.x,
  connected by at least one direct ConnectX-7 200GbE cable (RoCE).
- The runtime image pulled on both nodes from the registry reference above.
  The launcher uses that reference by default; override it with
  `RUNTIME_IMAGE` to run a locally built or locally tagged image instead.
- **Three patch files mounted over the image**, all obtainable from the
  SparkRing repository rather than from a running deployment:
  - `kernel_warmup.py` over
    `/opt/venv/lib/python3.12/site-packages/vllm/model_executor/warmup/` —
    apply `runtime/hotfixes/deployed-r34-20260810/model_executor__warmup__kernel_warmup.py.patch`.
    Without it the first non-GLM model served from this image dies during
    memory determination.
  - `quack/copy_utils.py` and `quack/layout_utils.py` over the image's `quack`
    package — annotation fixes for a `quack`/`cutlass` version skew that
    otherwise raises `module cutlass.cute.core has no attribute ThrMma`.
  - the `tvm-ffi` directory on `PYTHONPATH` — without it the workers raise
    `make_kwargs_wrapper() got an unexpected keyword argument`.

  **Verified minimal set:** the reference pair serves and passes every gate
  in [RESULTS.md](RESULTS.md) with exactly 8 bind mounts — those three patches
  plus the model, cache, HuggingFace-cache and transport-library mounts.
  [leg3pair.binds](leg3pair.binds) ships the reference pair's full 51-mount
  list, captured from a live SparkRing deployment; 43 of those 51 are inert
  under this configuration, because the custom four-node transport that
  imports them is disabled at TP2. Filtering the list to the 8 that matter:

  ```bash
  grep -E 'kernel_warmup|/quack/|tvm-ffi|:/models/|:/cache|huggingface|libspark_transport_capi' \
      leg3pair.binds > minimal.binds
  ```
- The checkpoint at
  `${HOST_WORK_DIR}/model/DeepSeek-V4-Flash-0731` on both nodes
  (`huggingface-cli download deepseek-ai/DeepSeek-V4-Flash-0731 --revision
  913f0657a874...` — 156 GB, 48 shards).
- For the cache tier: the LMCache wheel described below.

## Private deployment variables

Copy `profile.env.example` to a private `.env` beside
`leg3pair-launch.sh` on each node and replace every `REPLACE_WITH_*` value.
The launcher sources `.env` with Bash. It then expands the variable tokens in
`leg3pair.env` and `leg3pair.binds` one line at a time before passing those
lines to Docker as `-e` and `-v` arguments. Docker receives concrete values;
neither template relies on Docker environment-file expansion.

| Variable | Example | Role |
|---|---|---|
| `HOST_WORK_DIR` | `/srv/dsv4` | Host directory holding the checkpoint, the LMCache wheel, the launcher and the L2 cache |
| `HOST_HF_CACHE_DIR` | `/srv/hf-cache` | Host HuggingFace cache, bind source |
| `CONTAINER_HF_HOME` | `/root/.cache/huggingface` | HuggingFace cache path inside the container |
| `RANK0_FABRIC_ADDR` | `203.0.113.1` | Rank 0 on the direct link between the nodes; also the TP2 master address |
| `RANK1_FABRIC_ADDR` | `203.0.113.2` | Rank 1 on the direct link |
| `RANK0_LAN_ADDR` | `203.0.113.10` | Rank 0's LMCache server address, as the other rank reaches it |
| `RANK1_LAN_ADDR` | `203.0.113.11` | Rank 1's LMCache server address |
| `SPARKRING_MASTER_ADDR` | `203.0.113.20` | `MASTER_ADDR` as captured in the SparkRing container environment |
| `RANK1_SSH_TARGET` | `203.0.113.2` | The address rank 0's boot script uses to reach rank 1 over SSH; the fabric address, where a LAN address may have no host key |

Addresses above are from the documentation range reserved by RFC 5737 and are
placeholders, not a topology. Two nodes need a direct link between them and a
route by which each rank's cache server reaches the other; the addressing is
the deployment's own.

`CONTAINER_HF_HOME` is the only container-internal variable. It should remain
`/root/.cache/huggingface` for the recorded image layout; operators do not need
to adapt it to a host filesystem. Ports, interface names, image identity,
model identity, and tuning values remain literal in the profile.

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

Place the wheel in `${HOST_WORK_DIR}/wheels-t212/` on both nodes.

## Deploy

1. Copy `profile.env.example` to a private `.env` and replace every
   placeholder. Stage `.env`, [leg3pair-launch.sh](leg3pair-launch.sh),
   [leg3pair.env](leg3pair.env), and either
   [leg3pair.binds](leg3pair.binds) as shipped or the 8-line minimal filter
   above together in `${HOST_WORK_DIR}` on both nodes. Stage
   [leg3pair-inner.sh](leg3pair-inner.sh) at
   `/var/tmp/leg3pair-inner.sh`. Mount sources must exist at the paths the bind
   list names.
2. Launch rank 1 first, then rank 0 (each on its own host):
   `RANK=1 bash leg3pair-launch.sh` / `RANK=0 bash leg3pair-launch.sh`.
   `LMCACHE=0` launches without the cache tier. First launch pays a long
   JIT/AOT compile (the `/var/tmp/leg3-cache` mount persists it; later
   launches are much faster).
3. Verify: `curl localhost:8000/v1/models` on rank 0; the cache server log at
   `<L2 dir>/server.log` shows `Registered KV cache ... with 170 layers`.
4. Optional boot persistence: place
   [boot-dsv4-aa42.sh](boot-dsv4-aa42.sh) (rank 0) or
   [boot-dsv4-931e.sh](boot-dsv4-931e.sh) (rank 1) beside that node's private
   `.env`, then install it as an `@reboot` user crontab entry. Both scripts
   launch only when the container is absent, so the two boot paths cannot tear
   down a live follower.
5. Validate before trusting: run the gates in [RESULTS.md](RESULTS.md) —
   at minimum the cold-restart replay with planted-fact probes and the
   >10-minute-idle heartbeat check. Byte-identity is only meaningful under
   identical single-request greedy conditions; the behavioral gates use
   answer correctness.

### What the environment file does not carry

`leg3pair.env` holds the container environment captured from a running
SparkRing deployment, with the custom-transport family stripped. It carries no
model-identity or build-lineage variables — `SPARKRING_MODEL_REPOSITORY`,
`SPARKRING_MODEL_REVISION`, `SPARKRING_MODEL_CONFIG_SHA256`,
`SPARKRING_KV_PROFILE`, `SPARKRING_RUNTIME_ID` and the `SPARKRING_NF3_*`
commit pins. Those are inputs to the image's own entrypoints
(`/opt/sparkring/public-entrypoint.sh`, `/opt/sparkring-exl3/entrypoint.sh`),
which this launch replaces with `--entrypoint /bin/bash`, and the values a
SparkRing capture carries describe that deployment's checkpoint rather than
the one served here. `SPARKRING_IMAGE_DIGEST` remains, because it identifies
the image this profile actually runs.

Restoring the image entrypoint means supplying those variables for the
checkpoint being served; the entrypoint fails closed when one is unset, and
`public-entrypoint.sh` additionally rejects a `SPARKRING_KV_PROFILE` that
disagrees with `VLLM_SPARK_KV_PROFILE`.

`SPARK_GLM52_MTP_INDEX_REUSE=0` stays despite naming another model family:
`/opt/spark-vllm/sitecustomize.py` reads it, so it is a runtime gate rather
than provenance, and it is set to the disabling value.

## Configuration reference (deltas from the 4x SparkRing ring)

The launch is the ring's DeepSeek container spec with exactly these changes:

| Delta | Value | Why |
|---|---|---|
| Parallelism | `--tensor-parallel-size 2 --nnodes 2`, rank 1 `--headless` | two nodes |
| Custom transport | `SPARK_TP4_*` / `VLLM_SPARK_TP4_*` env removed | its source admits only `world_size == 4`; NCCL carries TP2 collectives (`VLLM_SPARK_SHARED_CAPTURE_STREAM=1` is kept — a source-patch gate the speculative graph capture needs, not a transport setting) |
| NCCL | single rail `rocep1s0f0`, GID 0, subnet-aware routing off | point-to-point pair, not a switchless 4-cycle |
| Speculation depth | 5 (ring runs 7) | 5 = the checkpoint's `dspark_block_size`, the validator's minimum; 7 also valid |
| Memory envelope | `--kv-cache-memory-bytes` 10 GiB, `--max-num-seqs 32`, `--gpu-memory-utilization 0.70` | 0.70 is the GB10 unified-memory ceiling above which loads are OOM-killed silently, with no error on the rank that dies |
| Bind mounts | 3 patch files plus 5 infrastructure mounts | the ring's remaining 43 mounts serve its four-node transport and adaptive-depth machinery, neither of which is enabled here |
| Cache tier | wheel install + in-container MP server + `--kv-transfer-config` + `expandable_segments:False` | the connector pins KV via CUDA IPC; the VMM allocator must not remap. Server and engine share the container lifecycle, so a replacement can never leave a server holding a dead engine's IPC mappings |

**Sizing rule — do not raise `--kv-cache-memory-bytes` while the cache tier is
enabled.** 10 GiB is qualified. Attempts at 24 GiB and 32 GiB both die the same
way: the key-value pool allocates successfully (4,246,848 and 5,662,523 tokens
respectively), then a worker is killed by signal during LMCache connector
initialisation, surfacing as `RuntimeError("cancelled")` from the shared-memory
broadcast. Halving `--max-model-len` while holding the budget at 24 GiB fails
identically, so the context limit is not the cause: the MP connector registers
the entire allocation through CUDA IPC, and a pool that size exceeds what the
tier can map alongside its own staging buffer.

The failure is not contained. On the reference pair, the follower node reached
a state where its kernel still answered ICMP and accepted TCP on every
listening port, while no connection — including SSH — could complete a
handshake, because userspace could not obtain memory to fork. Nothing recovers
that node remotely; it requires a power cycle. **Treat the key-value budget as
a hardware-safety parameter on unified memory, not a tuning knob**, and change
it only with physical or out-of-band access to both nodes.

**A long-context prefill is the memory-critical operation.** With an 8 GiB
LMCache L1 buffer, a 64K-token prefill drove the serving node to 113 GB used
of ~121 GB with swap active, and the engine core was killed shortly
afterwards; the API server then shut down cleanly, so the container exits 0
and the failure resembles a graceful stop rather than a crash. Include a
long-context cell in any acceptance battery: the correctness and concurrency
gates all use short prompts and never reach this limit.

**The L1 buffer size trades replay reach against host-memory headroom.**
`leg3pair-inner.sh` ships `--l1-size-gb 4`. A lookup counts an L2 hit only
after the chunk stages into L1, and LMCache's default trim policy truncates a
lookup at the first chunk that fails to stage, so a prefix longer than L1 holds
is recomputed rather than restored — slower, never wrong. What bounds staging is the stored chunk
footprint per rank, and two stores are on record: 18,688 tokens in about
1.2 GB with speculative caches, and 77,568 tokens in 6.1 GiB per rank without
speculation. Those are 64 and 84 KB per token per rank, so a 4 GiB buffer
stages 50,000 to 67,000 tokens and an 8 GiB buffer 100,000 to 134,000, against
a 131,072-token context limit. The engine's own key-value pool costs about
18.5 KB per token at that limit — a different quantity, measured on the GPU
side, which does not bound staging. An L1 buffer is host memory on a
unified-memory node, which is the other side of the trade. Status: the shipped
4 GiB value is **qualified** for serving and for long-context prefill
headroom — a 65,536-token prefill leaves 11 GB available per node against
12.5 GB at idle, where the same operation at 8 GiB reached the 7-8 GB at which
the engine core was killed. The gates and benchmarks recorded in
[RESULTS.md](RESULTS.md) under an 8 GiB buffer are marked there.

Note that a large budget is unnecessary in any case: per-token cost falls as
the context limit rises (bounded cache groups amortise over more tokens), and
at a 1,048,576-token limit the pool costs about 6 KB per token, so 10 GiB
already holds roughly 1.5 full contexts.

Known limitations and open tuning: speculative depth 5 is the checkpoint's
floor, not a choice — `dspark_block_size` is 5 and the engine rejects lower
values; depth 7 serves but measures slower. Per-position acceptance falls to
0.14 and 0.07 at the last two positions, so the runtime's built-in confidence
scheduler (shipped disabled as `VLLM_DSPARK_CONFIDENCE_SCHEDULER=off`) is an
untested opportunity to stop paying for draft work that rarely lands. The
memory envelope is conservative: the engine reports 581,194 key-value cache
tokens for the 10 GiB budget and 101 GiB free after load, and measured cache
occupancy is 5.8% at sixteen concurrent streams.
