# Reproducible Runtime Profiles

A profile is a small bundle that records how one model was served on one class
of hardware: image reference and digest, launch arguments, environment, mounts,
source revisions, a hardware summary, and the measurements taken. It carries no
model weights and no private machine details.

Each profile stands alone. Its own `README.md` is the instruction set; this page
only helps choose one.

## Quickstart

```bash
git clone https://github.com/FujitsuPolycom/inference-runtime-profiles
cd inference-runtime-profiles/profiles/<profile-name>
```

Then follow that profile's `README.md`. Every profile follows the same shape:

1. Copy `profile.env.example` to a private `.env` and fill in local paths,
   addresses and device names. Never commit it.
2. Obtain the image and the checkpoint the profile names, by digest.
3. Launch — some profiles ship `compose.yml`, others ship launcher scripts for
   multi-node deployments.
4. Run the profile's gates before trusting it. `RESULTS.md` records what those
   gates returned on the reference hardware.

Check a bundle before publishing or after editing:

```bash
./tools/validate-bundle.sh profiles/<profile-name>     # needs ripgrep
python tools/check-private.py profiles/<profile-name>  # same patterns, no dependencies
```

## Profiles

Status labels follow [AGENTS.md](AGENTS.md): `qualified` means the repository
records conditions, measurement and result; `implemented` means it runs and
nothing measured it; `research-only` means it is not for deployment.

### 2x NVIDIA DGX Spark

| Profile | Model | Parallelism | Cache tier | Status |
|---|---|---|---|---|
| [DeepSeek-V4-Flash-0731, SparkRing runtime](profiles/deepseek-v4-flash-0731-sparkring-runtime-2x-spark/) | DeepSeek-V4-Flash-0731 FP8, 131,072 ctx | TP2, DSpark depth 5 | LMCache 4 GiB L1 + 200 GiB NVMe L2 | qualified |
| [DeepSeek V4 Flash DSpark NVFP4, GPU-only KV](profiles/deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark/) | DeepSeek-V4-Flash-DSpark NVFP4, 1,048,576 ctx | TP2, MTP3 | none | implemented |
| [DeepSeek V4 Flash DSpark NVFP4, CPU KV offload](profiles/deepseek-v4-flash-dspark-nvfp4-cpu-offload-candidate-2x-spark/) | DeepSeek-V4-Flash-DSpark NVFP4, 1,048,576 ctx | TP2, MTP3 | 2 GiB/rank CPU RAM | research-only |
| [Qwen3.8-27B EXL3 K5/K6 + LMCache](profiles/qwen38-27b-exl3-k5k6-lmcache-2x-spark/) | Qwen3.8-27B EXL3, 262,144 ctx | TP2, MTP3 | LMCache 4 GB L1 + 200 GB NVMe L2 | qualified |

The Qwen3.8-27B bundle also serves a single Spark at `TP=1`; its README covers
what changes.

### 4x NVIDIA DGX Spark

| Profile | Model | Parallelism | Cache tier | Status |
|---|---|---|---|---|
| [GLM-5.2 EXL3 3.5 bpw fixed-MTP4](profiles/glm52-exl3-r7-3.5bpw-mtp4-4x-spark/) | GLM-5.2 EXL3/Trellis 3.5 bpw, 262,144 ctx | TP4 / DCP4 / MTP4 | native prefix caching | qualified |
| [GLM-5.2 SparkRing + SparkCache](profiles/glm52-sparkring-sparkcache-4x-spark/) | GLM-5.2 MXFP4-Experts GPTQ, 458,752 ctx | TP4 / DCP4 / MTP4 | SparkCache NVMe snapshots | qualified |

### 4x RTX PRO 6000 Blackwell workstation

| Profile | Model | Parallelism | Cache tier | Status |
|---|---|---|---|---|
| [GLM-5.2 v20 + grouped LMCache, FP8 RoPE](profiles/glm52-v20-lmcache-fp8rope/) | GLM-5.2 v20 | TP4 / DCP4 / MTP3 | LMCache, grouped | implemented |
| [GLM-5.2 v20 r13 EXL3 3.0 bpw](profiles/glm52-v20-r13-exl3-3bpw-750k/) | GLM-5.2 EXL3 3.0 bpw, 750K ceiling | TP4 | see profile | implemented |
| [GLM-5.2 v20 r7 EXL3 3.0 bpw](profiles/glm52-v20-r7-exl3-3bpw/) | GLM-5.2 EXL3 3.0 bpw | TP4 | see profile | implemented |

These rigs need a PCIe peer-access override; without it decode falls by roughly
40% at 8K context. [HARDWARE.md](HARDWARE.md) carries the setting and the
controlled comparison, and `tools/check-pcie-p2p.sh` verifies it.

### 1x GPU

| Profile | Model | Parallelism | Cache tier | Status |
|---|---|---|---|---|
| [Qwen3.6-27B NVFP4 MTP3 + LMCache, RTX 5090](profiles/qwen36-27b-nvfp4-mtp3-lmcache-rtx5090/) | Qwen3.6-27B NVFP4, 131,072 ctx | TP1 / MTP3 | LMCache 256 GB RAM L1 + 180 GB Optane L2 | implemented |

## Measured throughput

Single-stream decode at concurrency 1 unless stated. Conditions for every
figure are in the profile's own `RESULTS.md`; these rows are an index, not a
comparison — the profiles differ in model, quantisation, context and hardware.

| Profile | Decode | Prefill | Notes |
|---|---:|---:|---|
| [DeepSeek-V4-Flash-0731, 2x Spark](profiles/deepseek-v4-flash-0731-sparkring-runtime-2x-spark/RESULTS.md) | 43.4 tok/s | 1,623 tok/s at 64K | 59.9 tok/s median on coding output; 160.3 tok/s aggregate at 16 streams |
| [Qwen3.8-27B EXL3, 2x Spark](profiles/qwen38-27b-exl3-k5k6-lmcache-2x-spark/RESULTS.md) | 27.0 tok/s | 1,375 tok/s cold | 275 tok/s aggregate at 64 streams |
| [GLM-5.2 EXL3 3.5 bpw, 4x Spark](profiles/glm52-exl3-r7-3.5bpw-mtp4-4x-spark/RESULTS.md) | 27.3 tok/s | — | median on coding output at peak |

Profiles without a row have no throughput measurement recorded.

## What a bundle contains

```text
profiles/<profile-name>/
  README.md               # what it is, requirements, step-by-step
  manifest.json           # sanitized run metadata: image, runtime, benchmarks
  profile.env.example     # every site-specific value, as placeholders
  compose.yml             # or launcher scripts, for multi-node profiles
  RESULTS.md              # measurements with their conditions
  gates/                  # reproducible correctness probes, where a profile has them
  patches/                # patches the runtime needs, where a profile needs them
```

## Privacy rules

Never commit raw `docker inspect` output, shell history, logs, `.env` files,
SSH configuration, tokens, model-cache paths, or benchmark prompts. Use the
capture script, which replaces usernames, hostnames, IP addresses, home
directories, mount paths, container IDs and secret-looking values with
placeholders.

Review every generated `manifest.json` before publishing, and run one of the
two bundle checks above. The redactor is a guardrail, not a guarantee. Both
checks skip Markdown, so read the prose too: a bundle passes while its README
still states a private address or home directory.

## Capturing a profile

From the deployment host. Capture writes only to `profiles/<name>/` and never
stops, restarts or modifies the running container.

```bash
./tools/capture-profile.sh --container <container> --name <profile-name>
./tools/validate-bundle.sh profiles/<profile-name>
```

```powershell
./tools/capture-profile.ps1 --container <container> --name <profile-name>
./tools/validate-bundle.ps1 -Path profiles/<profile-name>
```

## Also here

- [AGENTS.md](AGENTS.md) — the writing standard this repository's prose follows.
- [HARDWARE.md](HARDWARE.md) — reference rigs, the PCIe peer-access setting, startup timings.
- [BENCHMARKING.md](BENCHMARKING.md) — benchmark commands used to produce the figures above.
