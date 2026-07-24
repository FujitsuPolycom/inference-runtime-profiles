# Results — NVFP4 LMCache Candidate

**Date:** (fill in after deployment)
**Candidate port:** 18007
**Production port:** 18006 (untouched)

## Deployment Checklist

- [ ] Copy candidate profile to both Spark nodes
- [ ] Copy `profile.env.example` to `.env` on both nodes, fill in placeholders
- [ ] Start peer (node-rank 1) first: `docker compose -p ds4f-nvfp4-lmcache-candidate up -d`
- [ ] Start head (node-rank 0): `docker compose -p ds4f-nvfp4-lmcache-candidate up -d`
- [ ] Wait for model load (~130s)
- [ ] Verify: `curl -s http://localhost:18007/v1/models`
- [ ] Run tests: `python3 test_correctness.py --url http://SPARK_HEAD:18007/v1 --stage C`

## Startup

| Metric | Stage C (production) | Candidate |
|--------|---------------------|-----------|
| Cold start time | ~130s | TBD |
| Engine-reported KV tokens | 1,515,055 | TBD |
| Connector initialized | n/a | TBD (check logs) |

## Cold Prefill

| Context | Stage C TTFT | Stage C tok/s | Candidate TTFT | Candidate tok/s |
|---------|:-----------:|:------------:|:--------------:|:--------------:|
| 8K | 4.29s | 1,911 | TBD | TBD |
| 32K | 16.83s | 1,922 | TBD | TBD |

## Repeat TTFT (LMCache hit)

| Context | Stage C repeat TTFT | Candidate cold TTFT | Candidate repeat TTFT | Speedup |
|---------|:-------------------:|:-------------------:|:----------------------:|:-------:|
| 8K | 0.37s (GPU prefix) | TBD | TBD | TBD |
| 32K | TBD (GPU prefix) | TBD | TBD | TBD |

## External Cache Metrics

| Metric | Stage C | Candidate |
|--------|---------|-----------|
| external_prefix_cache_queries_total | 0 | TBD |
| external_prefix_cache_hits_total | 0 | TBD |

## Correctness Gates

| Test | Stage C | Candidate |
|------|:-------:|:---------:|
| 1. 8K cold vs repeat (text match) | PASS | TBD |
| 2. 32K cold vs repeat (text match) | PASS | TBD |
| 3. 32K prefix + suffix (text match) | TBD | TBD |
| 4. Changed token → cache miss | TBD | TBD |
| 6. C2 same-prefix (both match) | TBD | TBD |
| 7. C2 unrelated-prefix (differ) | TBD | TBD |
| 8. 128K needle retrieval | TBD | TBD |

## Decode Performance

| Context | Stage C C1 | Stage C C4 | Candidate C1 | Candidate C4 |
|---------|:----------:|:----------:|:------------:|:------------:|
| 16K | 56.2 | 99.4 | TBD | TBD |
| 32K | 40.2 | 96.0 | TBD | TBD |

## MTP Acceptance

| Position | Stage C | Candidate |
|----------|:-------:|:---------:|
| 0 | 100% | TBD |
| 1 | 77% | TBD |
| 2 | 60% | TBD |

## Recommendation

TBD after testing.
