# Results

Quick post-reboot screen on the reference 4x RTX PRO 6000 Blackwell host.
NVIDIA P2P overrides and Resizable BAR were active. Each cell is one short
measurement and should be treated as a performance snapshot, not a confidence
interval.

## Published v20 with P2P settings

| Metric | 8K | 64K | 128K |
|---|---:|---:|---:|
| Cold prefill tok/s | 2,738 | 3,019 | 2,849 |
| C1 aggregate decode tok/s | 103.4 | 95.8 | - |
| C2 aggregate decode tok/s | 122.3 | 115.6 | - |

## Host-setting comparison

The image and benchmark command were unchanged across this short comparison.

| Metric | P2P settings absent | P2P settings active | Change |
|---|---:|---:|---:|
| C1 decode, 8K | 60.8 | 103.4 | +70.1% |
| C1 decode, 64K | 59.2 | 95.8 | +61.8% |
| C2 decode, 8K | 77.6 | 122.3 | +57.6% |
| C2 decode, 64K | 74.4 | 115.6 | +55.4% |
| Prefill, 64K | 3,007 | 3,019 | +0.4% |

The result is consistent with a repaired decode-side PCIe P2P/collective path,
while prefill remained within single-sample noise. Repeat longer runs before
using the percentages as production guarantees.

