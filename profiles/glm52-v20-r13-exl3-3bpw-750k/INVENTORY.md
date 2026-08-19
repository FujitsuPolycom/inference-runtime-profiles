# Component Inventory — GLM-5.2 EXL3 TP4/DCP4 Production Stack (`<inference-host>`)

**Serving endpoint:** `http://<host>:5810/v1`; served model `GLM-5.2-EXL3-TR3-3.0bpw`; OpenAI-compatible host-network service.
**Host:** single-node Debian 13 / kernel `7.0.14-4-pve`; captured live 2026-08-17.
**Container:** `glm52-v20-r7-exl3`; healthy since 2026-07-30, restart count `0`.
The container name predates the image change and does not indicate the runtime
revision; the running image digest below (v20 r13) is authoritative.

## 1. Hardware and host policy

| Component | Detail | Status |
|---|---|---|
| CPU / NUMA | AMD Threadripper PRO 9965WX, 24C/48T, single NUMA domain | Live |
| System memory | 125 GiB installed, 93 GiB available at capture; 71 GiB swap | Live |
| GPUs | 4× RTX PRO 6000 Blackwell Workstation Edition, 97,887 MiB each | Live |
| Driver | NVIDIA `610.43.02` | Live |
| PCIe topology | All GPU pairs report `NODE`; CPU affinity `0-47` / NUMA 0 | Live |
| Exposed order | `CUDA_VISIBLE_DEVICES=3,1,2,0`; PCI bus ordering requested | Intentional |
| P2P / ReBAR | NVIDIA P2P registry override and ReBAR enabled; see root `HARDWARE.md` | Required host policy |
| Power / OC | LACT boot service active; 400 W cap and P0 VRAM offset `+1000` per GPU; no core offset | Persistent |

The LACT profile name `vram-oc-plus-500` does not reflect its configured memory offset, which is `1000`.

## 2. Model artifact

| Component | Detail | Status |
|---|---|---|
| Checkpoint | `brandonmusic/GLM-5.2-EXL3-TR3-3.0bpw`, local tree 329 GiB | Local, mounted read-only |
| Architecture | `GlmMoeDsaForCausalLM` / `glm_moe_dsa`; 78 layers; hidden 6144; 64 attention/KV heads; vocabulary 154,880 | Checkpoint config |
| Model-declared context | 1,048,576 positions | Checkpoint config |
| Quant metadata | NVFP4 ModelOpt dispatch shim; 4-bit group size 16; selected embeddings/attention/shared-expert/early-layer targets excluded | Checkpoint config |
| `config.json` SHA-256 | `e36a632a8eaa6a98a318483dfcdb615ff2be9794a1f772800f144aa000da5c62` | Captured |
| `generation_config.json` SHA-256 | `ac76b43d8683d3b930126870fc8be73d8679308fe752fa1f381096d8354f6a55` | Captured |

## 3. Inference runtime

| Component | Version / source identity | Role |
|---|---|---|
| Image | `voipmonitor/vllm@sha256:02796036c96a52fda0919aa260c45c70bc97d8e662a6ae5e614b5f987c20851b` | Gilded Gnosis v20 r13 |
| vLLM | `0.11.2.dev280+gilded.gnosis.v20.vllm69ba80b.sia2ea608.fi801d57a.cu132.20260730.r13`; base `f978d009…`, composed tree `69ba80b9…` | Engine |
| B12X / SparkInfer | base `36cade0b…`, composed tree `a2ea6083…` | Sparse MLA / MoE |
| EXL3 | `brandonmmusic-max/exllamav3` `a1-retile-sm120` @ `704aefd7…` | Trellis loader/kernels |
| FlashInfer | `801d57a0…` | kernels/sampler |
| Torch / CUDA | Torch `2.12.0+cu132`; CUDA `13.2.1`; cuDNN runtime `9.20.0.48` | Framework |
| NCCL | local-inference `2.30.4`, preloaded and passed through `VLLM_NCCL_SO_PATH` | PCIe collectives |
| LMCache | `0.5.2+glm52dcp.4` library is in image, but no external tier is configured | Dormant |

## 4. Effective serving contract

| Area | Effective configuration |
|---|---|
| Parallelism | TP4 / DCP4 (tensor-parallel 4, decode-context-parallel 4); DCP backend A2A; interleave 64 |
| Quant / backend | EXL3; `nvfp4_ds_mla` KV; B12X sparse MLA attention and B12X MoE; InstantTensor loader |
| Capacity | GMU 0.96; model ceiling 750,000; 8 sequences; 3,072 batched tokens |
| CUDA graphs | `FULL_AND_PIECEWISE`; capture sizes 4, 8, 12, 16, 20, 24, 28, 32; max 32 |
| Prefill / prefix | Chunked prefill, EXL3 chunk 128, vLLM prefix cache enabled |
| Tool/reasoning | Auto tool choice; `glm47` tool parser; `glm45` reasoning parser; `reasoning_effort=high` default template kwarg |
| Speculation | MTP depth 3; Triton draft MoE; greedy draft sampling; async scheduling disabled |
| API | host network; port 5810; model name above |

Startup confirms `KV_FP8_ROPE=1`, `kv_gmem_stride=368`, and `nvfp4_ds_mla` KV.

## 5. Deliberate environment overrides

| Area | Settings |
|---|---|
| CKV gather | enabled; minimum 512 / maximum 262,144 tokens |
| DCP policy | B12X A2A enabled; small A2A limit 16; large path `ag_rs`; query split forced off; draft sharding on |
| Sparse/indexer | B12X sparse indexer, global top-k, MHC max 16,384, SM120 unified MLA |
| PCIe collectives | B12X PCIe AR; one-shot AR 64 KiB; fused add/RMS 84 KiB; RTX6K fused add disabled |
| PCIe wire representation | `VLLM_PCIE_DMA_FP8=ag`, `B12X_PCIE_DMA_FP8=ag` |
| EXL3 | Trellis min/max/block M = 4/32/8; W4A16 tensor-core decode; force A16 MoE |
| Compiler | AOT on; V2 model runner; FlashInfer sampler; grouped MoE top-k; breakable CUDA graph off |
| NCCL / host | IB disabled; P2P level `SYS`; `LL,LL128,Simple`; OMP threads 16 |

## 6. Storage, cache, and container policy

| Component | Detail |
|---|---|
| Model mount | `<model-root>/GLM-5.2-EXL3-TR3-3.0bpw:/model:ro` |
| JIT/runtime cache | `<cache-root>/glm52-v20-r7-exl3:/cache:rw`; about 3.9 GiB at capture; fingerprint `vllmf978d009fa-b12x36cade0bd8-c7b723e0fea550e8` |
| Temp mount | `<tmp-root>/glm52-v20-r7-exl3:/container-tmp:rw` |
| External cache | **None.** No `LMCACHE_MODE`, connector, RAM L1, disk L2, or LMCache volume. `/cache` is a JIT/AOT cache, not an external KV tier. |
| Docker | host networking; privileged; IPC host; 32 GiB shared memory; unlimited memlock; no CPU/RAM cgroup cap; `unless-stopped` restart policy |
| Logs | Docker local driver, 100 MiB × 5 files |

## 7. Validation and caveats

- `/v1/models` responds successfully and reports the 750,000-token request ceiling.
- No controlled benchmark or quality receipt belongs to this profile yet; put summarized reproducible results in `RESULTS.md`.
- The 750k request ceiling exceeds the 262,144-token CKV-gather ceiling, so longer prefills may use a different path.
- FP8 RoPE is enabled; dynamic-NVFP4 scale variables are not set.
- This profile uses deliberate manual DCP/PCIe/Trellis overrides.
