# Results — DeepSeek-V4-Flash-0731, SparkRing runtime, 2x DGX Spark

All measurements 2026-08-19 on the reference pair (GB10, driver 580.173.02),
serving configuration as in the profile README. Single-request measurements
are greedy (temperature 0, fixed seed). Byte-identity claims hold only under
identical single-request greedy conditions; behavioral gates use answer
correctness (planted key-value facts at fixed depths in deterministic filler).

## Decode throughput

| Configuration | Single-stream decode | Conditions |
|---|---|---|
| DSpark depth 5, 8 GiB L1 buffer | **36-40 tok/s** | client-observed 36.2, engine-reported peak 38.6-40; 1 request, 512-2048 token generations |
| DSpark depth 5, shipped 4 GiB L1 buffer | **42.5-43.4 tok/s** | client-observed over two runs, mean acceptance length 2.80 and 2.97; conditions in the 4 GiB section below |
| Same pair, from-source build, no speculation | 28.3 tok/s | 90 s sustained, client rate = server rate |
| Speculative depth 7 | 31.3 tok/s | same measurement, otherwise identical configuration |

Speculation therefore contributes about **1.35x** over unspeculated decode on
this hardware. An unrelated engine (a `ds4` fork serving the same checkpoint
family on a single Spark with 2-bit weights) reports 1.38x for its own DSpark
implementation, which is consistent.

**Depth is not a free parameter.** The checkpoint declares
`dspark_block_size: 5` and the engine rejects `num_speculative_tokens` below
it, so depth 3 cannot be run at all; depth 7 runs and passes every correctness
check but measures 14% slower. Depth 5 is both the floor and the best
measured value.

Speculation telemetry at depth 5: mean acceptance length 2.6-2.8, per-position
acceptance 0.76 / 0.55 / 0.27 / 0.14 / 0.07, draft acceptance 35-37%.

## Concurrency

Client-observed aggregate throughput, 256-token prompts, 512-token
generations, 180 s per cell:

| Concurrency | `--max-num-seqs 8` | `--max-num-seqs 32` |
|---:|---:|---:|
| 1 | 36.2 tok/s | — |
| 4 | 84.3 tok/s | — |
| 8 | 120.5 tok/s | 117.8 tok/s |
| 16 | — | **160.3 tok/s** |

Key-value cache occupancy peaked at 2.9% (8 streams) and 5.8% (16 streams) of
the 10 GiB budget, so the sequence limit rather than memory is what bounds
concurrency here. The profile ships `--max-num-seqs 32` for that reason.

At a 32,768-token context the same cells measure 32.1 tok/s at one stream and
52.2 tok/s at four. Those are **warm-prefix** figures: each worker reuses its
own prompt prefix, so after the first request the cache tier serves it. They
are not cold-prefill measurements.

## Prefill and coding throughput

Measured at concurrency 1 with the benchmark harness's exact-token targeting.
Prefill is cold in each cell (distinct prompts):

| Context | Prompt tokens | Time to first token | Prefill throughput |
|---|---:|---:|---:|
| 4K | 4,096 | 2.58 s | 1,589 tok/s |
| 8K | 8,192 | 4.52 s | 1,814 tok/s |
| 64K | 65,536 | 40.38 s | 1,623 tok/s |

Prefill throughput is roughly flat from 4K to 64K, so time to first token
scales close to linearly with prompt length.

**Coding output decodes far faster than prose.** A sequential coding probe
(a Sieve of Eratosthenes implementation, streaming, 2,000 max tokens, three
runs) measured **59.9 tok/s median** (mean 59.1, max 62.2, 3 of 3 runs
successful), against 33-37 tok/s on general prose in the same configuration.
Speculative draft acceptance rises sharply on structured output, so the
workload most people point this deployment at is roughly 1.6x faster than the
headline single-stream figure suggests. An unrelated engine serving the same
checkpoint family reports the same pattern — 1.38x speculation gain on its
mixed suite against 1.71x on structured content.

## Memory headroom is thin, and long-context work can exhaust it

**Observed on the qualified configuration with an 8 GiB LMCache L1 buffer.**
During a benchmark run that included a 64K-token prefill cell, the serving
node reached 113 GB used of ~121 GB with 7-8 GB available and swap actively in
use. The engine core was then killed during a subsequent decode cell; the API
server, finding its core gone, shut down cleanly, so the container exited 0
with no traceback — the failure looks like a graceful stop rather than a
crash, and the benchmark simply recorded zeros for the remaining cells.

The correctness and concurrency gates elsewhere in this document all use short
prompts and never approach this limit. Treat a long-context prefill as the
memory-critical operation on this deployment and include a long-context cell
in any acceptance battery so this failure mode cannot pass unnoticed.

`leg3pair-inner.sh` ships `--l1-size-gb 4` for that headroom. The cost is
staging reach: a lookup counts an L2 hit only after the chunk stages into L1,
and LMCache's default trim policy truncates a lookup at the first chunk that
fails to stage. Two store
footprints are on record below — about 1.2 GB for the 18,688-token prompt with
spec caches, and 6.1 GiB per rank for the 77,568-token store without
speculation, so 64 and 84 KB per token per rank — which puts a 4 GiB buffer at
50,000 to 67,000 tokens of staging reach and an 8 GiB buffer at 100,000 to
134,000. Prefixes past that reach recompute instead of restoring. Every gate in
this document sits inside 50,000 tokens except the 77,568-token store, which
was taken on the from-source stack at 8 GiB.

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

## Minimal bind-mount set

The reference pair's launcher mounts 51 paths over the image, captured from a
running SparkRing deployment. Removing them in three groups — the
`/opt/sparkring-*` contracts, the `/opt/spark-vllm/` adapters, and the
site-packages overrides — fails on every group individually:

| Group removed | Fatal error |
|---|---|
| `/opt/sparkring-*` (12) | `make_kwargs_wrapper() got an unexpected keyword argument map_dataclass_to_tuple` |
| `/opt/spark-vllm/` (25) | `ModuleNotFoundError: No module named spark_adaptive_mtp_launch_policy_controller` |
| site-packages except `kernel_warmup.py` (9) | `module cutlass.cute.core has no attribute ThrMma` |

Those failures are interdependent, not engine-essential: the module-not-found
error is raised by an overlay `scheduler.py` that is itself one of the mounts.
Removing **all three groups together**, keeping only `kernel_warmup.py`, the
two `quack/` files and `tvm-ffi`, serves and passes the full battery — **8
mounts instead of 51**, and all three patches are available from the SparkRing
repository rather than only from a running deployment.

## Operational gates

| Gate | Condition | Result |
|---|---|---|
| Boot scripts | containers stopped, rank-0 boot script run by hand | exit 0, stack restored, full battery passed |
| Boot idempotence | boot script re-run against a live stack | exit 0 in under a second; running containers untouched |
| Cache server lost mid-flight | rank-1 cache server killed, then a request whose prefix was stored | correct answers (3/3 facts) by recomputation in 71.3 s — degrades to slow, never to wrong |
| Long idle | 13 minutes idle after a store, then replay | zero reap events on either rank; replay restored in 1.57 s |

## The 4 GiB L1 buffer, measured

Conditions: both nodes carrying `--l1-size-gb 4`, both containers relaunched,
endpoint ready 404 s after launch, concurrency 1, 2026-08-20.

| Cell | Result |
|---|---|
| 34-tool corruption probe under speculation | 2,125 and 1,743 characters over two runs, no leaked template markers |
| Planted facts, 24,000-token prompt | 3/3 |
| Single-stream decode | 43.4 and 42.5 tok/s, mean acceptance length 2.97 and 2.80 |
| Planted facts, 65,536-token prompt | 3/3 |
| Available memory at the low point of the 65,536-token prefill | 11 GB per node, against 12.5 GB at idle; free swap held at 11 GB |

The 65,536-token prefill was computed rather than restored: prompt throughput
held 1,344-1,534 tok/s across it, near the 1,623 tok/s recorded above for a
cold prefill at that length, and the external prefix cache hit rate read 33.7%
during it against 97.2% on the 24,000-token prompt in the same run. Those two
figures bound the staging reach between 24,000 and 65,536 tokens, measuring
what the per-token footprint arithmetic estimates at 50,000 to 67,000.

A 64K-token prefill therefore costs about 1.5 GB of available memory at this
buffer size, against the 7-8 GB reached with an 8 GiB buffer, where the engine
core was killed. One gigabyte of margin remains above the abort floor the
acceptance battery uses, and 65,536 tokens is the longest prompt measured on
this configuration.

## Reproducing these gates

[gates/](gates/) carries two probes that assert the correctness properties
recorded above, against any endpoint serving this profile:
`replay-gate.py` for planted-fact correctness over a long prompt, and
`tool-array-probe.py` for output integrity under a 34-tool array. Both
generate their requests from a seed rather than replaying a captured one.
Measured on the reference pair 2026-08-20: `facts=3/3` in 13.28 s at 24,000
tokens, and 2,499 characters with no leaked markers from the tool array.

## Not yet measured

Time to first token with a cache-tier hit against a cold prefill of the same
prompt, decode throughput at contexts beyond 32K, the prompt length at which
the memory floor is crossed, and the effect of the DSpark confidence controls
(`dspark_confidence_threshold`, `dspark_confidence_temperature`,
`dspark_budget_frac` in the speculative config).

Every measurement in this document was taken with an 8 GiB LMCache L1 buffer.
`leg3pair-inner.sh` ships 4 GiB, and nothing here was re-measured at that
value. Two cells decide whether the shipped value holds: a 64K-token prefill,
which must leave the node with memory headroom rather than reaching the state
described above, and a replay of a prefix beyond the ~65,000-token staging
reach, which must degrade to recomputation with correct output rather than
returning a partial restore.
