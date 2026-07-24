# Results

Latest sanitized runs on the reference 4x RTX PRO 6000 host. The service used
TP4/DCP4/MTP3, FP8 RoPE, grouped LMCache (48 GB RAM L1 + 96 GB NVMe L2),
`MAX_BATCHED_TOKENS=3072`, graph 32, and the NVIDIA PCIe P2P overrides.

## Full practical/coding run

Source: `v20-practical-coding-20260724-141006.json`.

| Context | C1 | C2 | C4 | C8 |
|---:|---:|---:|---:|---:|
| 16K | 111.0 | 132.9 | 206.4 | 262.0 |
| 32K | 115.0 | 129.7 | 193.5 | 274.2 |
| 64K | 110.5 | 133.3 | 201.8 | capacity-limited |
| 128K | 111.9 | 125.6 | capacity-limited | capacity-limited |
| 200K | 92.8 | 116.6 | capacity-limited | capacity-limited |
| 356K | 100.3 | capacity-limited | capacity-limited | capacity-limited |

Cold/integrated prefill was approximately 3,318 tok/s at 8K, 3,051 at 16K,
3,081 at 32K, 3,024 at 64K, 2,902 at 128K, 2,794 at 200K, and 2,593 at
356K. The measured prompt sizes were 8,197, 16,227, 32,318, 64,508, 128,877,
201,286, and 358,187 tokens respectively. The 10-run coding peak had a 134.3
tok/s median, 135.5 tok/s mean, and 143.2 tok/s maximum.

## Prior short run

Source: `v20-practical-coding-20260724-140930.json`. It completed the 8K
prefill scout at **3,369 tok/s** but did not produce sustained decode cells.

These are short operational snapshots, not statistical confidence intervals.
