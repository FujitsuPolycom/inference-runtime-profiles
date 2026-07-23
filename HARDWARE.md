# Reference Rig

All GLM profiles in this repository were developed and tested on this class of
single-node system.

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
| Daily-style FP8-RoPE, TP4/DCP4/MTP3 | ~3.2k tok/s at ~120K | ~80 tok/s class | tested separately | ~307k tokens |
| BF16-RoPE DCP comparison, sparse CE | n/a | 72.7 at 8K | 90.96 at 8K | 220,160 tokens |
| BF16-RoPE DCP1 reference | n/a | 81.2 at 8K | n/a | 90,240 tokens |
| Qwen3.6-27B NVFP4 MTP3, RTX 5090 TP1 | ~135 tok/s prefill | ~99 tok/s decode | n/a | 204,039 tokens |

The BF16 rows are an earlier controlled comparison and are included to show the
DCP penalty/recovery shape; they are not a baseline for the FP8-RoPE profile.

## Interpretation

- GPU KV capacity is a VRAM allocation, not LMCache capacity.
- The daily profile uses a 48 GB host-RAM LMCache tier; its NVMe filesystem is
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

