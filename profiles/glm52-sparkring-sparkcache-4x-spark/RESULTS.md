# Results

These are end-to-end observations from the four-node switchless reference
cluster. The primary table is a controlled client-observed matrix from the
GPTQ RC1 serving configuration. Peak windows and later SparkCache (the persistent context cache)
measurements are labeled separately so they are not confused with that
baseline.

## Benchmark identity

The primary serving matrix is one coherent run, not a collage of best results
from different configurations.

| Item | Recorded value |
|---|---|
| Checkpoint | `aidendle94/GLM-5.2-MXFP4-Experts-GPTQ` |
| Topology | 4x DGX Spark, switchless four-link 200 GbE RoCE ring |
| Parallelism | TP4 / DCP4 (`ag_rs`) / PP1 |
| Speculation | MTP4; adaptive verification depths 2 and 4, window 32 |
| Draft execution | True selected-depth drafting enabled in RC1 |
| KV cache | `nvfp4_ds_mla`, per-token scale, 4,000,000,000 bytes/rank |
| Capacity contract | 500,224-token measured pool; 458,752-token request ceiling |
| Batch contract | 4,096 max batched tokens; 8 max sequences |
| Execution | `FULL_AND_PIECEWISE` CUDA graphs |
| Loader | safetensors |
| Benchmark | `llm-inference-bench` v0.4.31, `llm_decode_bench.py` |
| Decode protocol | 30-second sustained cells; C1/C2/C4/C8; 100% shared contexts |
| Prefill protocol | standalone cold prefill; client-observed `prompt_tokens / TTFT` |
| Raw artifact | `glm52-live-20260727-233436.json`, SHA-256 `5d18c7a31bc191cda72136583579b32dbf9a7a5cb94743294cecc464fec14daf` |
| Public evidence | [`evidence/serving-matrix-rc1-20260727.json`](evidence/serving-matrix-rc1-20260727.json) |

The sanitized equivalent benchmark command is:

```powershell
.\.venv\Scripts\python.exe .\llm_decode_bench.py `
  --host <rank0-management-address> `
  --port 8210 `
  --model glm-5.2 `
  --concurrency 1,2,4,8 `
  --contexts 8k,16k,32k,64k,128k `
  --duration 30 `
  --max-tokens 2048 `
  --kv-budget 500224 `
  --dcp-size 4 `
  --standalone-prefill `
  --unique-context-percent 0 `
  --output .\bench-results\glm52-sparkring-rc1.json
```

All 20 decode cells completed with zero request errors, zero queued requests,
zero underfilled cells, zero capacity-limited cells, and zero warmup timeouts.
Measured cell durations were 29.672-30.000 seconds.

## Controlled throughput matrix

### Uncached prefill

| Context | TTFT | Prefill | Samples |
|---:|---:|---:|---:|
| 8K | 9.71 s | 844 tok/s | 2 |
| 16K | 18.53 s | 876 tok/s | 1 |
| 32K | 38.94 s | 830 tok/s | 1 |
| 64K | 77.47 s | 832 tok/s | 1 |
| 128K | 161.95 s | 796 tok/s | 1 |

These are uncached prefill measurements, not prefix-cache hits. Except at 8K,
each context is a single sample and should be treated as a scout rather than a
distribution.

### Aggregate decode

| Context | C1 | C2 | C4 | C8 |
|---:|---:|---:|---:|---:|
| 8K | 20.3 | 27.1 | 40.5 | 49.2 |
| 16K | 19.0 | 26.4 | 37.9 | 53.3 |
| 32K | 20.3 | 27.6 | 38.6 | 51.9 |
| 64K | 20.3 | 27.0 | 39.4 | 50.9 |
| 128K | 19.7 | 26.3 | 37.2 | 47.7 |

Values are aggregate output tok/s. Concurrency cells use the profile's maximum
of eight active sequences and are not per-user throughput. The shared-context
protocol isolates decode scaling; it is not a unique-context capacity test.

## Same-lane workload-dependent observations

- A real C8 serving window reached **66.3 aggregate tok/s** with 65.1% draft
  acceptance and zero waiting requests or request errors.
- Two concurrent structured webpage-generation prompts produced short
  **34-42 tok/s aggregate** windows.

These are useful evidence that the path scales, but they are short
workload-dependent windows, not replacements for the controlled matrix.

## SparkCache v47

The cache results below came from the later v47 overlay, not from the RC1
matrix above. The checkpoint, TP/DCP geometry, KV format and allocation, model
length, batch limits, and physical fabric were retained. SparkCache activation
and overlay generation changed; v47 also recorded true selected-depth drafting
as disabled. Cache figures and serving figures therefore are not presented as
one atomic benchmark run.

At approximately 393K tokens, per-rank measurements were:

| Stage | Observed time |
|---|---:|
| Foreground snapshot | 3.63-4.16 s |
| Background commit | 11.23-15.55 s |

The asynchronous store path avoided an approximately 18-second
freeze-the-world event. 30 seconds and
post-first-token decode increase by 1.78 seconds.

A separate no-reload 32K overlap test observed a 1.1643-second four-rank
snapshot union while an unrelated 1,023-token carrier request continued before
and after the snapshot. The API stayed healthy with no waiting requests,
restart, reset, or deletion. Event-gap data did not resolve an additional
snapshot-specific pause above the normal concurrent-prefill interference, so
this is evidence of continued service, not proof of zero pause.

## Capacity

The reference deployment reserved 4,000,000,000 bytes of KV memory per rank and
reported a 500,224-token logical KV pool. The public request ceiling remained
458,752 tokens to preserve operating margin.

## Claim boundaries

- No 10 GbE diagonal-link gain is included in these results.
- Transport-only microbenchmarks from the SparkRing transport layer are not serving throughput.
- The serving matrix predates the v47 SparkCache overlay; it is a same-core
  RC1 serving baseline, not a cache-enabled throughput claim.
- The public v48-next SparkCache source was not deployed for these measurements.
- The exact reference vLLM overlay is not currently public, so these results are
  a measured configuration record rather than a clean-room reproduction claim.
