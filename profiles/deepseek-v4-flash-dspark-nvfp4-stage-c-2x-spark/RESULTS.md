# Results

Measurements below are client-observed results from the source deployment on
a 2x DGX Spark pair. They are workload and acceptance-rate sensitive,
especially at single-stream decode with DSpark speculative decoding.

## Cold Prefill

| Context | TTFT | Prefill |
| ---: | ---: | ---: |
| 8K | 4.29 s | 1,911 tok/s |
| 16K | 8.39 s | 1,937 tok/s |
| 32K | 16.83 s | 1,922 tok/s |

## Aggregate Decode Tok/s

| Context | C1 | C2 | C4 | C8 |
| ---: | ---: | ---: | ---: | ---: |
| 16K | 56.2 | 66.0 | 99.4 | 137.6 |
| 32K | 40.2 | 65.9 | 96.0 | 130.0 |

The engine reported a 1,515,055-token usable shared KV pool. Eight 128K
sessions fit within that pool; eight 256K sessions do not.

Long-context retrieval check — conditions: a single 353,861-token two-hop
repository retrieval request on the deployment above; the run included an
on-demand Triton compilation, and further conditions were not recorded.
Measurement: whether the retrieval completed correctly. Result: pass. The
end-to-end latency is unmeasured as a clean figure because of the compilation.
