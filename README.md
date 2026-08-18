# Reproducible Runtime Profiles

Small, shareable bundles for GPU inference deployments. A profile records the
image digest, launch arguments, environment, mounts, source revisions, hardware
summary, and benchmark references without copying model weights or private
machine details.

## Privacy rules

Never commit raw `docker inspect`, shell history, logs, `.env` files, SSH
configuration, tokens, model-cache paths, or benchmark prompts. Use the capture
script, which replaces usernames, hostnames, IP addresses, home directories,
mount paths, container IDs, and secret-looking values with placeholders.

Review every generated `manifest.json` before publishing. The redactor is a
guardrail, not a guarantee.

## Important Hardware / Software Settings

### NVIDIA PCIe P2P driver configuration

The four-GPU RTX PRO 6000 Blackwell profiles depend on direct PCIe peer access.
The setup scripts and `llm-inference-bench` both detect the recommended
NVIDIA registry settings. Measured on the RTX workstation reference rig ([HARDWARE.md](HARDWARE.md)): the
model started without them, but decode performance fell from approximately
**100 tok/s to 60 tok/s**.

Create `/etc/modprobe.d/nvidia-p2p-override.conf`:

```text
options nvidia NVreg_RegistryDwords="ForceP2P=0x11;RMForceP2PType=1;RMPcieP2PType=2;GrdmaPciTopoCheckOverride=1;EnableResizableBar=1"
```

Apply the configuration:

```bash
update-initramfs -u
reboot
```

Verify it after reboot:

```bash
grep -E 'EnableResizableBar|RegistryDwords' /proc/driver/nvidia/params
```

Expected values include `EnableResizableBar: 1` and all four registry entries
above. `nvidia-smi` may show PCIe Gen1 while idle; verify Gen5 x16 under load.

These values are specific to the tested NVIDIA PCIe workstation topology. Keep
console access available, verify peer connectivity after reboot, and do not
blindly apply them to unrelated hardware or driver versions. See
[HARDWARE.md](HARDWARE.md) and the
[v20 + LMCache NF3 hybrid profile](profiles/glm52-v20-lmcache-fp8rope/) for
the reference configuration and measured comparison.

## Benchmarking

See [BENCHMARKING.md](BENCHMARKING.md) for PowerShell-ready quick, practical,
full-standard, and cold-prefill benchmark commands using
`local-inference-lab/llm-inference-bench`.

For the four-GPU RTX workstation reference rig ([HARDWARE.md](HARDWARE.md)), run `tools/check-pcie-p2p.sh` as root
before deployment. It checks the NVIDIA registry override, runtime driver
parameters, GPU topology, and CUDA peer-access visibility.

## Layout

```text
profiles/<profile-name>/
  profile.env.example       # non-secret knobs only
  compose.yml               # portable compose template
  manifest.json             # sanitized, immutable run metadata
  RESULTS.md                # optional summarized measurements
  README.md                 # profile-specific notes
```

## Profiles by GPU count

### 4x RTX workstation profiles

Target a single-node workstation with **4x NVIDIA RTX PRO 6000 Blackwell 96 GiB GPUs**, an **AMD Threadripper PRO 9965WX**, **128 GiB system RAM 6400 (8x16GB)**, PCIe Gen5 x16-class GPU slots, and an NVMe-backed model/cache filesystem. Typical GLM testing uses **TP4/DCP4/MTP3**. The v20 + LMCache NF3 hybrid profile below is the maintained LMCache deployment and daily reference. See [HARDWARE.md](HARDWARE.md) for startup timings and comparable benchmark data.

#### GLM-5.2

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [**v20 R13 EXL3 3.0 bpw, 750k ceiling**](profiles/glm52-v20-r13-exl3-3bpw-750k/) | GLM-5.2 EXL3 3.0 bpw · `nvfp4_ds_mla`, FP8 RoPE, 368 B | 750,000 | 831,911 | 3,072 | 8 | TP4 / DCP4 / MTP3 | none (GPU-only KV, deliberately) | Long-context profile; manual DCP/Trellis overrides recorded |
| [**v20 R7 EXL3 3.0 bpw**](profiles/glm52-v20-r7-exl3-3bpw/) | GLM-5.2 EXL3 3.0 bpw · `nvfp4_ds_mla`, FP8 RoPE, 368 B | 262,144 | 813,568 | 3,072 | 8 | TP4 / DCP4 / MTP3 | none (GPU-only KV, deliberately) | Validated GPU-only lane, largest KV pool |
| [v20 + LMCache NF3 hybrid](profiles/glm52-v20-lmcache-fp8rope/) | GLM-5.2 NVFP4 + NF3 hybrid · `nvfp4_ds_mla`, FP8 RoPE, 368 B | 400,384 | 433,152 | 3,072 | 8 | TP4 / DCP4 / MTP3 | LMCache 48 GiB RAM L1 + 96 GiB NVMe L2, chunk 512 | Daily reference deployment, longest context |

### 4x DGX Spark profiles

These profiles target multi-node GB10 clusters rather than a single PCIe
workstation. SparkRing is the switchless direct-cable RoCE ring serving fabric
these clusters use; SparkCache is its DCP-sharded NVMe context-snapshot cache.
Fabric topology, management-plane isolation, and per-rank attestation are part
of the configuration.

#### GLM-5.2

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [GLM-5.2 EXL3 3.5 bpw fixed-MTP4, 4x Spark](profiles/glm52-exl3-r7-3.5bpw-mtp4-4x-spark/) | GLM-5.2 EXL3/Trellis 3.5 bpw + online K6 · `nvfp4_ds_mla`, FP8 RoPE, 368 B | 262,144 | 1,156,864 | 4,096 | 8 | TP4 / DCP4 / MTP4 (fixed) | none accepted (native prefix caching; LMCache NVMe is an unaccepted candidate, 38.0x replay evidence) | sparkring operator default; SIRCL switchless transport |
| [GLM-5.2 SparkRing + SparkCache, 4x Spark](profiles/glm52-sparkring-sparkcache-4x-spark/) | GLM-5.2 MXFP4-Experts GPTQ · `nvfp4_ds_mla` | 458,752 | 500,224 | 4,096 | 8 | TP4 / DCP4 / MTP4 | SparkCache (not LMCache): DCP4-sharded NVMe context snapshots, 256 MiB arena | Switchless direct-cable serving with persistent context snapshots |

### 2x DGX Spark profiles

These are separate from the 4x RTX workstation profiles and target two DGX
Spark systems. They should not be treated as interchangeable launch recipes.

#### DeepSeek V4 Flash

DSpark is the speculative-decoding proposer these profiles run (MTP-style
probabilistic draft sampling); `(dspark)` in the parallelism column marks its
MTP implementation.

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [DeepSeek V4 Flash DSpark NVFP4 Stage C, 2x Spark](profiles/deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark/) | DeepSeek-V4-Flash-DSpark NVFP4 · `nvfp4_ds_mla`, block 256 | 1,048,576 | 1,515,055 | 8,192 | 8 | TP2 / MTP3 (dspark) | none | Two-node long-context DeepSeek profile |
| [DeepSeek V4 Flash DSpark NVFP4 CPU Offload Candidate](profiles/deepseek-v4-flash-dspark-nvfp4-cpu-offload-candidate-2x-spark/) | DeepSeek-V4-Flash-DSpark NVFP4 · `nvfp4_ds_mla`, block 256 | 1,048,576 | not yet measured | 8,192 | 8 | TP2 / MTP3 (dspark) | SimpleCPUOffloadConnector: 2 GiB/rank CPU RAM, no NVMe | Test build with CPU RAM KV offload |

#### Qwen3.8-27B

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [Qwen3.8-27B EXL3 K5/K6 MTP2 + LMCache, 2x Spark](profiles/qwen38-27b-exl3-k5k6-mtp2-lmcache-2x-spark/) | Qwen3.8-27B EXL3 K5/K6 · `fp8`, block 1600 (GDN) | 262,144 | 3,893,434 | 3,072 | 64 | TP2 / MTP2 | LMCache 4 GB L1 + 200 GB NVMe L2, chunk 1600 (≈59K / ≈3.0M tokens) | Near-BF16 EXL3 lane (0.00276 KLD), two-rail RoCE striping |

### 1x DGX Spark profile

The Qwen3.8-27B profile below is the same bundle as its 2x entry, run with `TP=1` — one node
carries all weights and every KV head, so the KV pool shrinks and the LMCache chunk doubles to
213 MB (an 8 GB L1 stages ~59K replayable tokens at TP1 versus ~118K at TP2). No ray, no
striping, no second cache server. Measured: decode 23.8 / 43.1 / 85.2 tok/s at 4k context for
cc1/2/4; prefill 330-667 tok/s from 4k to 32k.

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [Qwen3.8-27B EXL3 K5/K6 MTP2 + LMCache, 1x Spark](profiles/qwen38-27b-exl3-k5k6-mtp2-lmcache-2x-spark/) | Qwen3.8-27B EXL3 K5/K6 · `fp8`, block 1600 (GDN) | 262,144 | 1,669,678 | 3,072 | 64 (lowering recommended for the smaller pool) | TP1 / MTP2 | LMCache 8 GB L1 + 200 GB NVMe L2, chunk 1600 (213 MB/chunk at TP1) | Single-Spark deployment of the same near-BF16 EXL3 lane |

### 1x GPU profile

| Profile | Model / quant / KV | Max model len | Max GPU KV | Batch | Seqs | Parallelism | Cache tier | Main use |
|---|---|---:|---:|---:|---:|---|---|---|
| [Qwen3.6-27B NVFP4 MTP3 + LMCache, RTX 5090](profiles/qwen36-27b-nvfp4-mtp3-lmcache-rtx5090/) | Qwen3.6-27B NVFP4 · `fp8`, block 1600 (mamba) | 131,072 | 204,039 | 3,199 | 1 | TP1 / MTP3 | LMCache 256 GB pinned-RAM L1 + 180 GB Optane L2, chunk 1600 | Single-GPU Qwen hybrid/Mamba with LMCache |

## Commands

From the deployment host:

```bash
./tools/capture-profile.sh --container glm52-prod --name daily-v20
./tools/validate-bundle.sh profiles/daily-v20
```

On Windows PowerShell:

```powershell
./tools/capture-profile.ps1 --container glm52-prod --name daily-v20
./tools/validate-bundle.ps1 -Path profiles/daily-v20
```

Capture writes only to `profiles/<name>/`. It does not stop, restart, or modify
the running container.

## Applying a profile

Copy `profile.env.example` to a private `.env`, fill in local paths, and review
the compose file. Do not commit the private file.

```bash
docker compose --env-file .env -f profiles/daily-v20/compose.yml config
docker compose --env-file .env -f profiles/daily-v20/compose.yml up -d
```

Use immutable image digests, explicit ports, and a separate project name for
each profile. Record benchmark results in `RESULTS.md`, not raw request data.

These are sanitized templates, not executable claims about a particular host.
Every local path, image digest, and scale-file location must be filled in via a
private `.env` before launch.
