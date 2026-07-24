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
The published v20 launcher and `llm-inference-bench` both detect the recommended
NVIDIA registry settings. On the reference host, the model started without them
but decode performance fell from approximately **100 tok/s to 60 tok/s**.

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
[clean v20 daily profile](profiles/glm52-daily-v20-clean-no-lmcache/) for the
reference configuration and measured comparison.

## Benchmarking

See [BENCHMARKING.md](BENCHMARKING.md) for PowerShell-ready quick, practical,
full-standard, and cold-prefill benchmark commands using
`local-inference-lab/llm-inference-bench`.

For the reference four-GPU PCIe host, run `tools/check-pcie-p2p.sh` as root
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

### 4x GPU profiles

Target a single-node workstation with **4x NVIDIA RTX PRO 6000 Blackwell 96 GiB GPUs**, an **AMD Threadripper PRO 9965WX**, **128 GiB system RAM 6400 (8x16GB)**, PCIe Gen5 x16-class GPU slots, and an NVMe-backed model/cache filesystem. Typical GLM testing uses **TP4/DCP4/MTP3**. The maintained 4x GLM profile below is the current LMCache deployment and daily reference. See [HARDWARE.md](HARDWARE.md) for startup timings and comparable benchmark data.

#### GLM-5.2

| Name | Link | KV type | Max available GPU KV | Max model length | Batch tokens |
|---|---|---|---:|---:|---:|
| **Current daily v20 + LMCache** | [Open profile](profiles/glm52-v20-lmcache-fp8rope/) | `nvfp4_ds_mla`, FP8 RoPE, 368 B | 433,152 | 400,384 | 3,072 |

### 2x DGX Spark profiles

These are separate from the 4x RTX workstation profiles and target two DGX
Spark systems. They should not be treated as interchangeable launch recipes.

#### DeepSeek V4 Flash

| Profile | Main use | KV / offload |
|---|---|---|
| [DeepSeek V4 Flash DSpark NVFP4 Stage C, 2x Spark](profiles/deepseek-v4-flash-dspark-nvfp4-stage-c-2x-spark/) | Two-node long-context DeepSeek profile | `nvfp4_ds_mla`, TP2, MTP3, 1M request ceiling |
| [DeepSeek V4 Flash DSpark NVFP4 LMCache Candidate](profiles/deepseek-v4-flash-dspark-nvfp4-lmcache-candidate-2x-spark/) | Test build with SimpleCPUOffloadConnector (CPU RAM KV offload) | CPU RAM offload, TP2, MTP3 |

### 1x GPU profile

| Profile | Main use | KV / offload |
|---|---|---|
| [Qwen3.6-27B NVFP4 MTP3 + LMCache, RTX 5090](profiles/qwen36-27b-nvfp4-mtp3-lmcache-rtx5090/) | Single-GPU Qwen hybrid/Mamba with LMCache | FP8 KV, 204K tokens, 256 GB RAM L1 + Optane L2 |

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
