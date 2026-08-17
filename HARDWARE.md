# Reference Hardware

The repository contains profiles for several hardware classes. Never transfer
topology-specific settings between them without an explicit validation plan.

## RTX workstation reference rig

| Component | Reference configuration |
|---|---|
| GPUs | 4x NVIDIA RTX PRO 6000 Blackwell Workstation Edition, 96 GiB each |
| GPU topology | Single host; peer links report `NODE`; PCIe Gen5 x16-class slots |
| CPU | AMD Threadripper PRO 9965WX |
| Platform | ASUS WRX90E-SAGE-class workstation board; one NUMA domain |
| System RAM | 128 GiB |
| CUDA | CUDA 13.2-class runtime; SM120/SM120a kernels |
| Storage | NVMe-backed model/cache filesystem; capacity and free space vary |
| Parallelism | Typical GLM run: TP4 / DCP4 / MTP3 |

## Critical NVIDIA P2P settings

The reference host requires the following NVIDIA registry values for the
intended direct PCIe P2P path:

```text
ForceP2P=0x11
RMForceP2PType=1
RMPcieP2PType=2
GrdmaPciTopoCheckOverride=1
EnableResizableBar=1
```

They are persisted in `/etc/modprobe.d/nvidia-p2p-override.conf` as:

```text
options nvidia NVreg_RegistryDwords="ForceP2P=0x11;RMForceP2PType=1;RMPcieP2PType=2;GrdmaPciTopoCheckOverride=1;EnableResizableBar=1"
```

Changing NVIDIA module parameters requires `update-initramfs -u` and a reboot.
After reboot, confirm the active values in `/proc/driver/nvidia/params`.

A controlled A/B on the v20 profile, changing only this host state, measured the following. C1 decode increased from 60.8
to 103.4 tok/s at 8K and from 59.2 to 95.8 tok/s at 64K. Prefill at 64K
remained effectively unchanged (3,007 versus 3,019 tok/s). This makes driver
state part of every reproducible performance record, not an optional tuning
detail.

Do not copy these settings to a different GPU topology without console access
and an explicit P2P validation plan.

## Reference timings

These are operational expectations, not guarantees. Cold startup includes weight
loading, JIT/AOT compilation, KV allocation, and CUDA graph capture.

| Event | Typical observation |
|---|---:|
| Weight load with InstantTensor | ~54 seconds |
| Warm repeat request | Sub-second to a few seconds, depending on context |
| First cold request | Can be dominated by JIT or graph warmup |
| Rebuild after changing kernels/flags | Several minutes; fresh Triton/AOT caches can be much longer |

## Published performance snapshots

Results depend heavily on KV format, context length, batch size, MTP, and
whether the run is cold or warm. Compare only rows with identical profiles.

| Profile/test | Prefill | C1 decode | C2 decode | GPU KV |
|---|---:|---:|---:|---:|
| Clean v20 daily, P2P settings active | 3,019 tok/s at 64K | 103.4 at 8K / 95.8 at 64K | 122.3 at 8K / 115.6 at 64K | 482,560 tokens |
| Daily-style FP8-RoPE, TP4/DCP4/MTP3 | ~3.2k tok/s at ~120K | ~80 tok/s class | tested separately | ~307k tokens |
| BF16-RoPE DCP comparison, sparse CE | n/a | 72.7 at 8K | 90.96 at 8K | 220,160 tokens |
| BF16-RoPE DCP1 reference | n/a | 81.2 at 8K | n/a | 90,240 tokens |
| Qwen3.6-27B NVFP4 MTP3, RTX 5090 TP1 | ~135 tok/s prefill | ~99 tok/s decode | n/a | 204,039 tokens |

The BF16 rows are a separate controlled comparison and are included to show the
DCP penalty/recovery shape; they are not a baseline for the FP8-RoPE profile.

## Four-node DGX Spark reference cluster

The SparkRing GLM-5.2 profile targets four independent DGX Spark systems
connected without an Ethernet switch in the inference data path.

| Component | Reference configuration |
|---|---|
| Nodes | 4x NVIDIA DGX Spark |
| SoC | NVIDIA GB10 |
| Memory | 128 GiB unified memory per node |
| Inference fabric | Switchless ring; two direct ConnectX-7 200 GbE RoCE links per node |
| Management plane | Independent interface for SSH, Gloo, and NCCL bootstrap |
| Parallelism | TP4 / DCP4 (`ag_rs`) / PP1 / MTP4 |
| Model | `aidendle94/GLM-5.2-MXFP4-Experts-GPTQ` |
| KV | `nvfp4_ds_mla`, per-token scale, 4,000,000,000 bytes per rank |
| Logical KV pool | 500,224 tokens measured; 458,752-token request ceiling |
| Batch limits | 4,096 tokens / 8 sequences |

### DGX Spark performance snapshot

| Metric | Observation |
|---|---:|
| Uncached prefill | 844 / 876 / 830 / 832 / 796 tok/s at 8K / 16K / 32K / 64K / 128K |
| C1 aggregate decode | 19.0-20.3 tok/s across 8K-128K |
| C8 aggregate decode | 47.7-53.3 tok/s across 8K-128K |
| Workload-dependent C8 window | 66.3 aggregate tok/s |

The main table is client-observed end-to-end serving. Most prefill context
lengths are single-sample scouts. The 66.3 tok/s figure is a short
workload-dependent server window, not the controlled baseline.

The two RoCE ports are inference links, not management links. Preserve
independent management access and verify each direct cable bidirectionally
before launching the four-rank communicator. Optional 10 GbE diagonal links
are not required by the published profile and receive no performance credit.

See the
[GLM-5.2 SparkRing + SparkCache profile](profiles/glm52-sparkring-sparkcache-4x-spark/)
for exact runtime settings, source-status caveats, and cache measurements.

## Interpretation

- GPU KV capacity is a VRAM allocation, not LMCache capacity.
- The GLM-5.2 v20 + Grouped LMCache profile (`profiles/glm52-v20-lmcache-fp8rope/`) uses a 48 GB host-RAM LMCache tier; its NVMe filesystem is
  available for general caches but is not automatically an LMCache KV tier.
- Increasing DCP reduces KV duplication but adds communication.
- MTP increases decode work per scheduling step and changes the useful comparison
  point; always record MTP with throughput.
- Cold numbers must be reported separately from warm numbers because JIT and
  graph capture can dominate the first sample.

## Consumer GPU rig (RTX 5090)

The Qwen3.6-27B profile targets this class of single-GPU host.

| Component | Configuration |
|---|---|
| GPU | 1x NVIDIA RTX 5090, 32 GiB |
| System RAM | 919 GiB (LMCache L1 uses 256 GiB as pinned host memory) |
| CUDA | CUDA 13.0-class runtime; SM120 kernels |
| Storage | Optane RAID0 (~200 GB) for LMCache L2; pmem for HF/vLLM caches |
| Parallelism | TP1 / MTP3 |

### RTX 5090 performance snapshots

| Metric | Value |
|---|---|
| Model weights (NVFP4) | 18.65 GiB |
| GPU KV cache tokens | 204,039 |
| MTP3 acceptance rate | 70.5% |
| Inter-token latency p50 | 35 ms |
| Decode throughput | ~99 tok/s |
| LMCache L1 store / retrieve | 0.011 s / 0.001 s (1600-token chunk) |

