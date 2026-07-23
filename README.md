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

- `glm52-daily-bf16rope-lmcache`: TP4/DCP4/MTP3 daily stack with BF16 RoPE,
  replicated indexer, depth-3 prefetch, sparse CE decode, and 48 GB LMCache RAM.
- `glm52-v20-promotion-fp8rope-offload`: separate v20 FP8-RoPE/Grid188 profile
  with PCIe i8-ring and DRAM/NVMe offload.

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
