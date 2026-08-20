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
    apply `runtime/patches/00-reference-vllm/model_executor__warmup__kernel_warmup.py.patch`
    from `FujitsuPolycom/sparkring` to the image's copy of that file. It warms
    the DeepSeek mHC kernels across the CUDA-graph capture sizes; without it
    the first non-GLM model served from this image dies during memory
    determination.
  - `quack/copy_utils.py` and `quack/layout_utils.py` over the image's `quack`
    package — annotation fixes for a `quack`/`cutlass` version skew that
    otherwise raises `module cutlass.cute.core has no attribute ThrMma`.
  - the `tvm-ffi` directory on `PYTHONPATH` — without it the workers raise
    `make_kwargs_wrapper() got an unexpected keyword argument`.

  **Minimal set:** seven of the mounts in [leg3pair.binds](leg3pair.binds)
  matter — the three patches above plus the checkpoint, the JIT cache, and the
  HuggingFace cache. That file ships the reference pair's full 51-mount list
  captured from a live SparkRing deployment, and the rest are inert here
  because the custom four-node transport that imports them is disabled at TP2.
  **Do not launch with the 51-line list as shipped:** 44 of its sources are
  paths that exist only on that pair. Step 6 of the procedure below filters it.

  One further mount in that file,
  `libspark_transport_capi.so` over `/opt/sparkring/spark_transport/`, is not
  in the filtered set. On the reference pair the library is present in the
  container and mapped by none of its eight processes, while `libnccl`
  appears in 42 mappings across the same processes: at TP2 the collectives go
  through NCCL and the transport library is never loaded. Omitting it also
  removes a build artifact that is not obtainable from a public repository.
- The checkpoint on both nodes: 156 GB across 48 shards, revision
  `913f0657a874`, fetched in step 3.
- The LMCache wheel on both nodes, built in step 5 from the branch and the
  patch named there. The cache tier does not start without it.

The launcher assumes the interface names a DGX Spark presents: `enp1s0f0np0`
for the socket interfaces and `rocep1s0f0` for the RDMA device. Step 1 confirms
them and names what to edit when a pair differs.

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

## Bringing it up

Run every step on **both** nodes unless a step says otherwise. `$WORK` below is
the directory you will set as `HOST_WORK_DIR`; `$IMG` is the registry
reference from the top of this document.

```bash
WORK=/srv/dsv4                                   # your choice; both nodes alike
IMG=ghcr.io/fujitsupolycom/gb10-vllm-serving:r34-20260810
mkdir -p "$WORK"/{model,wheels-t212,lmcache-l2-dsv4-0731-spec-b256} /var/tmp/leg3-cache
```

### 1. Confirm the hardware names the launcher assumes

```bash
ip link | grep -E 'enp1s0f0np0|enp1s0f1np1'      # socket interfaces
ibv_devices | grep rocep1s0f0                     # RDMA device
```

Both must appear. If this pair names them differently, edit the
`NCCL_SOCKET_IFNAME`, `GLOO_SOCKET_IFNAME`, `TP_SOCKET_IFNAME` and
`NCCL_IB_HCA` values in [leg3pair-launch.sh](leg3pair-launch.sh) to match, and
`OMPI_MCA_btl_tcp_if_include` and `MN_IF_NAME` in
[leg3pair.env](leg3pair.env).

### 2. Pull the runtime image

```bash
docker pull "$IMG"
```

### 3. Download the checkpoint

156 GB across 48 shards, pinned to the revision this profile was measured on:

```bash
huggingface-cli download deepseek-ai/DeepSeek-V4-Flash-0731 \
    --revision 913f0657a874 --local-dir "$WORK/model/DeepSeek-V4-Flash-0731"
```

### 4. Build the three patched files the image needs

Extract the originals from the image, then apply the patches in
[patches/](patches/). The target filenames are the ones the bind list names, so
keep them exactly.

```bash
docker run --rm --entrypoint /bin/bash -v /var/tmp:/out "$IMG" -c '
  P=/opt/venv/lib/python3.12/site-packages
  cp $P/vllm/model_executor/warmup/kernel_warmup.py /out/kernel_warmup.py
  cp $P/quack/copy_utils.py   /out/sparkring-r7-quack-copy_utils-annotations.py
  cp $P/quack/layout_utils.py /out/sparkring-r7-quack-layout_utils-annotations.py'

patch /var/tmp/sparkring-r7-quack-copy_utils-annotations.py \
      < patches/quack-copy_utils-thrcopy-annotation.patch
patch /var/tmp/sparkring-r7-quack-layout_utils-annotations.py \
      < patches/quack-layout_utils-thrmma-annotation.patch
```

`kernel_warmup.py` takes its patch from `FujitsuPolycom/sparkring`, which is
not part of this bundle:

```bash
curl -fsSL https://raw.githubusercontent.com/FujitsuPolycom/sparkring/main/runtime/patches/00-reference-vllm/model_executor__warmup__kernel_warmup.py.patch \
  | patch /var/tmp/kernel_warmup.py
```

Unpack the pinned `tvm-ffi` wheel into the directory the bind list mounts onto
`PYTHONPATH`:

```bash
pip download apache-tvm-ffi==0.1.10 --no-deps --python-version 3.12 \
    --only-binary=:all: --platform manylinux_2_28_aarch64 -d /tmp/tvmffi
unzip -q /tmp/tvmffi/apache_tvm_ffi-0.1.10-*.whl \
    -d /var/tmp/sparkring-r7-tvm-ffi-0.1.10-r1
```

### 5. Build the LMCache wheel

The image ships lmcache `0.5.2+glm52dcp4.1`, which predates the hybrid
cache-group transfer support this model's restore correctness depends on.
Build the qualified branch against the **image's** torch 2.12, with the
heartbeat guard fix from [patches/](patches/) applied first:

```bash
git clone --branch release/v0.5.2-glm52-dcp-base --single-branch \
    https://github.com/local-inference-lab/LMCache /tmp/lmcache
cd /tmp/lmcache
git rev-parse HEAD^{tree}          # expect e045d729bc5c...
patch -p1 < "$OLDPWD"/patches/lmcache-mp-heartbeat-guard.patch
docker run --rm --entrypoint /bin/bash -v /tmp/lmcache:/src -v "$WORK/wheels-t212":/out \
  -e TORCH_CUDA_ARCH_LIST=12.1 "$IMG" \
  -c 'cd /src && /opt/venv/bin/pip wheel . --no-deps --no-build-isolation -w /out'
```

### 6. Stage the bundle and its private values

```bash
cp leg3pair-launch.sh leg3pair.env profile.env.example "$WORK"/
cp leg3pair-inner.sh /var/tmp/leg3pair-inner.sh
grep -E 'kernel_warmup|/quack/|tvm-ffi|:/models/|:/cache$|HF_CACHE_DIR' \
    leg3pair.binds > "$WORK"/leg3pair.binds
mv "$WORK"/profile.env.example "$WORK"/.env      # then edit every REPLACE_WITH_ value
```

`$WORK/leg3pair.binds` must list exactly seven mounts. Every source path it names
must exist before launch: Docker creates a directory in place of a missing bind
source, so a missing patch file becomes a silently wrong mount rather than an
error.

### 7. Launch, rank 1 first

The launcher replaces its own container, so no teardown step is needed.

```bash
# on rank 1
RANK=1 bash "$WORK"/leg3pair-launch.sh
# on rank 0
RANK=0 bash "$WORK"/leg3pair-launch.sh
```

`LMCACHE=0` launches without the cache tier. A first launch pays a long JIT and
AOT compile; the `/var/tmp/leg3-cache` mount persists it, and later launches
reach a serving endpoint in roughly seven minutes, about four of which is
checkpoint load.

### 8. Confirm it serves

```bash
curl -s http://127.0.0.1:8000/v1/models                       # rank 0
grep 'Registered KV cache' "$WORK"/lmcache-l2-dsv4-0731-spec-b256/server.log
```

The cache server log must report `Registered KV cache ... with 170 layers`. A
lower count means the speculative caches did not register and restore
correctness does not hold.

### 9. Run the correctness gates

```bash
python3 gates/replay-gate.py store  --tokens 24000
python3 gates/tool-array-probe.py
```

Both must exit 0. To exercise restore across a restart, run
`gates/replay-gate.py store`, replace both containers, then
`gates/replay-gate.py replay` and compare the reported elapsed time and
completion hash. [RESULTS.md](RESULTS.md) records what these gates returned on
the reference pair.

### 10. Optional: bring the pair up at boot

Place [boot-dsv4-aa42.sh](boot-dsv4-aa42.sh) on rank 0 or
[boot-dsv4-931e.sh](boot-dsv4-931e.sh) on rank 1 beside that node's `.env`, and
install it as an `@reboot` user crontab entry. Each script launches only when
its container is absent, so neither boot path can tear down a live follower.

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
