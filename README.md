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

## Layout

```text
profiles/<profile-name>/
  profile.env.example       # non-secret knobs only
  compose.yml               # portable compose template
  manifest.json             # sanitized, immutable run metadata
  RESULTS.md                # optional summarized measurements
  README.md                 # profile-specific notes
```

## Profiles

| Profile | Main use | KV / offload |
|---|---|---|
| [GLM-5.2 daily BF16-RoPE + LMCache](profiles/glm52-daily-bf16rope-lmcache/) | Validated daily TP4/DCP4/MTP3 stack | 432-byte BF16-RoPE, 48 GB RAM tier |
| [GLM-5.2 v20 FP8-RoPE promotion](profiles/glm52-v20-promotion-fp8rope-offload/) | Separate v20/Grid188/offload candidate | 368-byte FP8-RoPE, DRAM + NVMe tier |
| [DeepSeek V4 Flash DSpark NVFP4 Stage C, 2x Spark](profiles/deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark/) | Two-node long-context DeepSeek profile | `nvfp4_ds_mla`, TP2, MTP3, 1M request ceiling |

Hardware and comparison card: [HARDWARE.md](HARDWARE.md)

### Reference Rig

All profiles target a single-node workstation with **4x NVIDIA RTX PRO 6000
Blackwell 96 GiB GPUs**, an **AMD Threadripper PRO 9965WX**, **128 GiB system
RAM**, PCIe Gen5 x16-class GPU slots, and an NVMe-backed filesystem. Typical
GLM testing uses **TP4/DCP4/MTP3**. The daily profile uses a **48 GB host-RAM
LMCache tier**; NVMe is not automatically part of that tier. See
[HARDWARE.md](HARDWARE.md) for startup timings and comparable benchmark data.

- `glm52-daily-bf16rope-lmcache`: TP4/DCP4/MTP3 daily stack with BF16 RoPE,
  replicated indexer, depth-3 prefetch, sparse CE decode, and 48 GB LMCache RAM.
- `glm52-v20-promotion-fp8rope-offload`: separate v20 FP8-RoPE/Grid188 profile
  with PCIe i8-ring and DRAM/NVMe offload.
- `deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark`: two-node TP2 / MTP3
  DeepSeek V4 Flash DSpark profile with resident NVFP4 KV.

These are sanitized templates, not executable claims about a particular host.
Every local path, image digest, and scale-file location must be filled in via a
private `.env` before launch.

## Commands

From the deployment host:

```bash
./tools/capture-profile.sh --container glm52-prod --name daily-v20
./tools/validate-bundle.sh profiles/daily-v20
```

On Windows PowerShell:

```powershell
.\tools\Capture-Profile.ps1 -Container glm52-prod -Name daily-v20
.\tools\Validate-Bundle.ps1 -Path profiles\daily-v20
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
