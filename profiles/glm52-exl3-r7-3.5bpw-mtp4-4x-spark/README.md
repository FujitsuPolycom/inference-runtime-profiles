# GLM-5.2 EXL3 3.5-bpw, fixed MTP4 (4x DGX Spark, TP4/DCP4)

Four-node profile for GLM-5.2 served from an EXL3/Trellis 3.5-bpw quant across a directly
cabled DGX Spark ring at TP4/DCP4, with speculative decoding locked at four draft tokens,
dynamic per-token NVFP4 latent KV with FP8 RoPE at 262K context, and the sparkring project's
switchless RDMA collective transport.

**Status: `qualified` — the sparkring appliance's operator default (sparkring maturity label: `accepted`).** Not zero-build-ready:
the runtime image is locally built (`final_image: null`; live-validated image ID
`sha256:02881d5229d4...`), and the remaining promotion gate is an ARM64 image build from a
clean checkout passing the four-rank checklist against that exact image ID. The sparkring
repository's *public* default is a different lane (EXL3 3.25-bpw with an LMCache CS512 tier,
maturity `live-validated`).

Source of truth: the [sparkring repository](https://github.com/FujitsuPolycom/sparkring) at
commit `4545c4ec4740f203d4f427db265414a34bd8f5db` — recipe `recipes/glm52-exl3-r7-3.5bpw.json`,
operator docs `docs/EXL3_R7_QUICKSTART.md` and `docs/EXL3_R7_FIXED_MTP4_PROFILE.md`, evidence
under `docs/configurations/glm52-exl3-r7-*.json`. "R7" is that repository's durable recipe
identifier for this lane; "TR3" names the EXL3/Trellis quantization family.

## Model

| Parameter | Value |
|---|---|
| Model ID | brandonmusic/GLM-5.2-EXL3-TR3v4-3.5bpw-MTP78 |
| Revision | `9ab9579774cc432df91567a36f6e9e863e0d4c9f` (157 shards, ~346 GB, per-file SHA-256 verified) |
| Quantization | EXL3/Trellis 3.5 bpw routed experts (K3/K4/K5) + target-only **online EXL3 K6** overlay for eligible BF16 weights (`exl3-b6`, cache mode readwrite) |
| Speculative draft | reused layer-78 MTP head ("MTP78"): checkpoint EXL3 routed experts + BF16 non-expert weights, K6 disabled for the draft |
| Served name | glm-5.2-exl3-r7-3.5bpw |
| Load format | instanttensor |

## Serving configuration

| Parameter | Value |
|---|---|
| Parallelism | TP4 / DCP4 (`ag_rs`) / PP1 / DP1 |
| Speculation | **fixed MTP4**: depth locked at 4 draft tokens, greedy draft sampling, adaptive depth disabled; CUDA graphs captured Q1–Q40 (8 seqs x (4+1) rows), no eager execution |
| Attention backend | B12X_MLA_SPARSE |
| KV cache | `nvfp4_ds_mla`, dynamic per-token scale, FP8 RoPE, 368-byte record, B12X block 64 |
| KV pool | 1,156,864 tokens (9.25 GB/rank, 37 GB aggregate) |
| Max context / seqs / batch | 262,144 / 8 / 4,096 (`exl3_prefill_capacity` 4,096) |
| GPU memory utilization | 0.85 |
| Routed-MoE dispatch | exact-Q40 policy on the 75 mixed-EXL3 layers: capacity_rows 40, route_block_rows 8 (Q1–Q32 and the draft unchanged) |
| CKV gather | `b12x-transient-full-ckv-dcp-gather` enabled to 262,144 logical tokens (414.4 MiB/rank workspace) |
| Cache tier | **none** — native prefix caching only. An LMCache NVMe extension exists as a `candidate-extension` (`accepted: false`); see RESULTS |

## Transport

Four directly cabled DGX Sparks in a `direct-cycle-4` ring; two 200 Gb/s ConnectX-7 links per
node (both NIC cages), one point-to-point /24 per physical link, MTU 9000, RoCEv2 GID index 3.
TP collectives run on SIRCL — the sparkring project's Switchless Inference RDMA Collective
Layer (`two_slot_deferred_ack` graph protocol, `tiered_64k` kernel strategy) — with fallback to
NCCL 2.30.7 carrying the two sparkring patches (skip-tree-pat, advertise-all-listener-gids) at
NCCL commit `73cf1122`. DCP and indexer transports are stock.

## Runtime

vLLM from `local-inference-lab/vllm` base `e2666d9a65f41fc376607531453cbd57c4c71016` +
`vllm/integration.patch` (sha256 `8a726985...`), result tree `4d006a43928c`; pins in
`runtime/exl3-r7/pins.json` (b12x 1.2.1 patched, flashinfer, instanttensor, exllamav3 with
ARM64 patch). Platform: linux/arm64, sm_121, CUDA 13.2, Python 3.12. The image is built
locally from the sparkring repository; there is no registry-published image and no portable
compose file — launch is owned by the sparkring launcher at the pinned commit, which is why
this profile ships no `compose.yml`.

## Apply

1. Clone sparkring at `4545c4ec4740f203d4f427db265414a34bd8f5db`.
2. Follow `docs/EXL3_R7_OPERATOR_REPRODUCTION.md` (model download with per-file SHA-256
   verification and quarantine-on-corruption, image build, four-rank bring-up).
3. Validate against the acceptance evidence in `docs/configurations/` — the recipe records the
   expected image ID, KV capacity, and graph-node counts.

## Known limitations

- Aggregate throughput figures are aggregate, not per-request; no repeat distributions.
- The 1,156,864-token KV pool has not repeated the >=512,000-simultaneously-resident-tokens
  long-context gate (proven only on the 675,840-token fp8_ds_mla / 65,536-context
  configuration recorded in `glm52-exl3-r7-mtp4-kv925-20260811.json`; see RESULTS.md).
- Fixed MTP5 is unsupported by the qualified image (Q48 requires contract changes and a
  rebuilt native transport cap).
- Claims the sparkring repository itself rejects: blanket correctness, all-shape speedup,
  transferability beyond the qualified four-Spark appliance.
