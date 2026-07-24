# GLM-5.2 Daily v20, No LMCache

Current daily profile for a single-node, four-GPU RTX PRO 6000 Blackwell
workstation. It uses only features shipped in the published July 23 v20 image:
no source overlay, sparse-decode experiment, replicated-indexer patch, or
external KV cache.

## Runtime

| Setting | Value |
|---|---|
| Image | `voipmonitor/vllm:gilded-gnosis-v20-vllm7e3bee1-si6234185-fi801d57a-cu132-20260723` |
| Model | `GLM-5.2-MXFP8-NVFP4-NF3-Hybrid` |
| Parallelism | TP4 / DCP4 / MTP3 |
| Maximum model length | 262,144 |
| Maximum sequences | 8 |
| Maximum batched tokens | 2,048 |
| CUDA graph ceiling | 64 |
| GPU memory utilization | 0.96 |
| KV cache | `nvfp4_ds_mla`, 432-byte record, BF16 RoPE |
| Reported GPU KV capacity | 482,560 tokens |
| LMCache / offload | Disabled |

At TP4/DCP4, the image helper resolves `DCP_PREFILL_WORKSPACE=auto`,
`DCP_QUERY_SPLIT=auto`, and `DCP_CKV_GATHER=auto` to the supported optimized
paths. B12X PCIe DMA is enabled without F8 compression. The image also enables
its PCIe one-shot all-reduce path with the shipped 64 KiB all-reduce and 84 KiB
fused add/RMS thresholds.

## Host prerequisite

This profile depends on the NVIDIA PCIe P2P registry settings below. On the
reference machine, omitting them reduced C1 decode from approximately 100 tok/s
to approximately 60 tok/s.

Create `/etc/modprobe.d/nvidia-p2p-override.conf`:

```text
options nvidia NVreg_RegistryDwords="ForceP2P=0x11;RMForceP2PType=1;RMPcieP2PType=2;GrdmaPciTopoCheckOverride=1;EnableResizableBar=1"
```

Then rebuild the initramfs and reboot:

```bash
update-initramfs -u
reboot
```

Verify after reboot:

```bash
grep -E 'EnableResizableBar|RegistryDwords' /proc/driver/nvidia/params
```

These settings are hardware and driver specific. Validate P2P connectivity and
retain console access before applying them to another host.

## Apply

```bash
cp profile.env.example .env
# Fill in the four host-local directories.
docker compose --env-file .env config
docker compose --env-file .env up -d
```

The API serves `GLM-5.2` on the configured port. The reference LiteLLM aliases
are `ai01-glm52` and `ai01-glm5.2`.

## Notes

- The server warns that 2,048 batched tokens may be undersized for MTP3.
  Preserve it for exact reproduction; test 3,072 as a separate tuning change.
- The 482,560-token KV capacity exceeds the 262,144 model limit and provides
  concurrency headroom; it does not raise the per-request context ceiling.
- PCIe links may report Gen1 while idle and should rise under load.
- Benchmark prompts must be unique when measuring cold prefill.

