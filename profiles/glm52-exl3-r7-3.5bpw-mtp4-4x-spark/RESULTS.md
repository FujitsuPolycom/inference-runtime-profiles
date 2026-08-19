# Results

All figures are from evidence files committed in the sparkring repository at
`4545c4ec4740f203d4f427db265414a34bd8f5db`, cited per section. Aggregate figures are
aggregate across concurrent streams, not per-request.

## Accepted operator matrix (2026-08-13, `glm52-exl3-r7-current-best-matrix-20260813.json`)

Configuration: TP4/DCP4, fixed MTP4, dynamic per-token NVFP4 latent KV + FP8 RoPE,
exact-Q40 (capacity 40, route block 8).

**Prefill** (C1, 100% unique context, client-timed):

| Context | tok/s | TTFT |
|---:|---:|---:|
| 8K | 679 | 12.06 s |
| 16K | 673 | 24.36 s |
| 32K | 666 | 49.17 s |
| 64K | 657 | 99.72 s |
| 128K | 645 | 203.09 s |

**Aggregate decode tok/s** (context x concurrency):

| ctx \ conc | C1 | C2 | C4 | C8 |
|---|---:|---:|---:|---:|
| 4K | 22.6 | 32.7 | 50.3 | **78.4** |
| 8K | 22.0 | 35.3 | 51.9 | 71.3 |
| 16K | 21.3 | 32.9 | 49.2 | 70.0 |
| 32K | 20.4 | 32.3 | 45.6 | 65.5 |
| 64K | 21.4 | 30.4 | 47.2 | 67.8 |

Coding peak, C1: 5/5 runs, median 27.3, max 28.8 tok/s.

## MTP4 acceptance

96.64% (268 events; per-position accepted [266, 263, 255, 252]) — CKV-gather evidence,
2026-08-11. The fp8_ds_mla / 65,536-context configuration recorded in
`glm52-exl3-r7-mtp4-kv925-20260811.json` measured 96.996%.

## Exact-Q40 acceptance bracket (2026-08-12, `glm52-exl3-r7-mtp4-q40-block8-20260812.json`)

Matched warm 16K/C8 sealed-payload replay, 25 s window, 8/8 resident: baseline mean 61.344
tok/s vs candidate 73.208 = **+19.3%** (slowest candidate vs fastest baseline +14.9%).
Prefill nonregression: machine verdict fail on one cell (64K, -0.12% vs envelope-low),
recorded with an operator waiver as measurement-neutral; the failure record is preserved in
the evidence file.

## CKV-gather A/B (2026-08-11)

Sole delta between the arms: the two CKV-gather environment variables,
`VLLM_B12X_MLA_CKV_GATHER` and `VLLM_B12X_MLA_CKV_GATHER_MAX_TOKENS` (the pair
this repository's b12x profiles use to enable the gather; the exact values for
this run are recorded in the sparkring evidence files, not in this
repository).

Prefill 8K +14.9% (435 to 500 tok/s), 16K +39.2% (437 to 608), 64K +29.7% (434 to 563),
128K +29.8% (425 to 551). A +5.4% C8/16K decode delta was observed but is explicitly not
causally attributed — the gather affects prefill only.

## LMCache NVMe extension (2026-08-13, `glm52-exl3-r7-lmcache-nvme-20260813.json` — candidate, `accepted: false`)

lmcache `0.5.2+glm52dcp4.1`, one MP server per DCP rank, chunk 512 tokens, 512 MiB lazy L1 +
50 GiB O_DIRECT NVMe L2 per rank. A 32,506-token publication with cold TTFT 56.115 s replayed
after engine restart at TTFT **1.477 s = 38.0x** (external prefix hit 99.2%, native 0.0%).
Not a deterministic-output gate: cold and replay text differed. Restart contract: recycle the
LMCache servers before engine relaunch — they hold stale CUDA IPC ownership otherwise.

## fp8_ds_mla / 65,536-context configuration (`glm52-exl3-r7-mtp4-kv925-20260811.json`, scoped evidence)

A 2026-08-11 capture (`glm52-exl3-r7-mtp4-kv925-20260811.json`) at fp8_ds_mla KV, 65,536
context, 2,048 batch tokens measured decode C1 34.6 / C2 51.4 / C4 77.0 / C8 85.7 aggregate
tok/s and proved a long-context gate of at least 512,000 simultaneously resident logical
tokens (8x64K, zero preemptions). The sparkring repository scopes this as evidence for the
shared fixed-MTP4 and transport contract, **not** for the dynamic-NVFP4/262K/CKV-gather
profile documented here; the 1,156,864-token pool has not repeated the long-context gate.
