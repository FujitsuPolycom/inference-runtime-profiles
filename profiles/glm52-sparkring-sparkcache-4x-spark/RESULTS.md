# Results

These are end-to-end observations from the four-node switchless reference
deployment. The primary table is a controlled client-observed matrix. Peak
windows and cache measurements are labeled separately so they are not confused
with the baseline.

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
of eight active sequences and are not per-user throughput.

## Workload-dependent peaks

- A real C8 serving window reached **66.3 aggregate tok/s** with 65.1% draft
  acceptance and zero waiting requests or request errors.
- Two concurrent structured webpage-generation prompts produced short
  **34-42 tok/s aggregate** windows.

These are useful evidence that the path scales, but they are short
workload-dependent windows, not replacements for the controlled matrix.

## SparkCache live v47

At approximately 393K tokens, per-rank measurements were:

| Stage | Observed time |
|---|---:|
| Foreground snapshot | 3.63-4.16 s |
| Background commit | 11.23-15.55 s |

The asynchronous store path removed the earlier approximately 18-second
freeze-the-world event. It did not yet satisfy the strict sidecar interference
budget: one test observed TTFT increase by 1.30 seconds and
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
- Transport-only microbenchmarks from SparkRing are not serving throughput.
- The public v48-next SparkCache source was not deployed for these measurements.
- The exact reference vLLM overlay is not currently public, so these results are
  a measured configuration record rather than a clean-room reproduction claim.
