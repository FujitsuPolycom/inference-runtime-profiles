# Results — DeepSeek-V4-Flash-0731, SparkRing runtime, 2x DGX Spark

All measurements 2026-08-19 on the reference pair (GB10, driver 580.173.02),
serving configuration as in the profile README. Single-request measurements
are greedy (temperature 0, fixed seed). Byte-identity claims hold only under
identical single-request greedy conditions; behavioral gates use answer
correctness (planted key-value facts at fixed depths in deterministic filler).

## Decode throughput

| Configuration | Single-stream decode | Conditions |
|---|---|---|
| This profile (DSpark depth 5) | **~40 tok/s** | engine-reported generation throughput, 1 running request, 2K-token generation |
| Same pair, from-source build, no speculation | 28.3 tok/s | 90 s sustained, client rate = server rate |

Speculation telemetry at depth 5 (engine `SpecDecoding metrics` during the
40 tok/s measurement): mean acceptance length ~2.8, per-position acceptance
0.76 / 0.55 / 0.27 / 0.14 / 0.07, draft acceptance ~36%. Positions 4-5
contribute little; a depth-3 configuration is expected to match or beat this
figure and has not yet been measured.

## Output correctness under speculation

The reproduction that deterministically corrupts the from-source
humming-W4A16 stack (a captured chat completion carrying a 34-tool array, as
open-webui sends) was replayed byte-for-byte against this profile with
speculation active: 1,963-2,156 characters of coherent markdown, zero leaked
end-of-sequence or template tokens, across repeated runs.

## LMCache tier gates (all passed)

| Gate | Condition | Result |
|---|---|---|
| Registration | engine start with tier on | `Registered KV cache ... with 170 layers` on both ranks (167 base cache groups + 3 DSpark hidden-state caches) |
| Store | 18,688-token deterministic prompt, cold | 3/3 planted facts; chunks on NVMe (~1.2 GB with spec caches) |
| Cold-restart replay | both containers removed and relaunched (kills engines, cache servers, L1, native prefix cache), identical request | all 18,688 tokens restored from NVMe in **0.051 s**; completion SHA-256 byte-identical; 3/3 facts |
| Indexer-desync extension | after the restore, a new question naming a fact never asked before | correct — fresh sparse top-k selection indexed into the restored region, which a restored-MLA/cold-indexer pairing cannot do |
| Heartbeat longevity | >12 min idle after store, then reap-line count on both servers | 0 reaps (the unpatched fork reaps a healthy engine at ~150 s; this gate must be rerun for every rebuild of the wheel) |

The same gate battery passed earlier the same day on the pair's from-source
stack without speculation (including a 77,568-token replay restored in
0.098 s), establishing the tier's behavior at longer contexts; the
speculation-active battery above is the qualifying run for this profile.

## Not yet measured

Concurrency curves, prefill throughput, long-context cells at 64K-131K,
TTFT with and without cache replay, depth 3 vs 5 vs 7 sweep.
