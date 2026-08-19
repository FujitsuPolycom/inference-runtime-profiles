# Standardized Benchmark Commands

These commands use
[`local-inference-lab/llm-inference-bench`](https://github.com/local-inference-lab/llm-inference-bench)
against an OpenAI-compatible endpoint. They are written for Windows PowerShell
controlling a Linux inference host over SSH while retaining the benchmark's live
terminal dashboard.

## Reference Endpoint

| Setting | Value |
|---|---|
| SSH host | `<inference-host>` (placeholder — the repository's privacy rules forbid committed hostnames) |
| API | `127.0.0.1:5810` |
| Model | `GLM-5.2` |
| Benchmark checkout | `/opt/llm-inference-bench` |
| Results directory | `/srv/ai/bench-results` |

Change these values when testing a different profile or host. Name each output
file `<profile-slug>-<matrix>-$ts.json` so the result carries the profile slug
under test.

## Default Methodology

The benchmark's standard sustained-decode matrix uses:

- Contexts: `0,16k,32k,64k,128k`
- Concurrency: `1,2,4,8,16,32,64,128`
- 30 seconds per cell
- 2,048 generated-token ceiling
- Integrated prefill scouts
- Sustained decode as the primary metric
- Automatic capacity skipping

There is no separate named "standard" preset. The full command below states the
important defaults explicitly so saved runs remain understandable.

## Quick Screen

Two contexts and two concurrency levels, 15 seconds per cell:

```powershell
ssh -tt <inference-host> 'cd /opt/llm-inference-bench && mkdir -p /srv/ai/bench-results && ts=$(date +%Y%m%d-%H%M%S) && PYTHONUNBUFFERED=1 ./.venv/bin/python -u llm_decode_bench.py --host 127.0.0.1 --port 5810 --model GLM-5.2 --contexts 8k,64k --concurrency 1,2 --duration 15 --display-mode live --output /srv/ai/bench-results/<profile-slug>-quick-$ts.json'
```

## Practical Matrix

Useful for routine comparisons without running the full concurrency ladder:

```powershell
ssh -tt <inference-host> 'cd /opt/llm-inference-bench && mkdir -p /srv/ai/bench-results && ts=$(date +%Y%m%d-%H%M%S) && PYTHONUNBUFFERED=1 ./.venv/bin/python -u llm_decode_bench.py --host 127.0.0.1 --port 5810 --model GLM-5.2 --contexts 8k,32k,64k,128k --concurrency 1,2,4 --duration 20 --display-mode live --output /srv/ai/bench-results/<profile-slug>-practical-$ts.json'
```

## Full Standard Matrix

This is the canonical sustained-decode run:

```powershell
ssh -tt <inference-host> 'cd /opt/llm-inference-bench && mkdir -p /srv/ai/bench-results && ts=$(date +%Y%m%d-%H%M%S) && PYTHONUNBUFFERED=1 ./.venv/bin/python -u llm_decode_bench.py --host 127.0.0.1 --port 5810 --model GLM-5.2 --contexts 0,16k,32k,64k,128k --concurrency 1,2,4,8,16,32,64,128 --duration 30 --display-mode live --output /srv/ai/bench-results/<profile-slug>-standard-$ts.json'
```

Add `--run-burst --burst-requests-per-concurrency 5` when a burst-throughput
report is also required.

## Cold Prefill Only

```powershell
ssh -tt <inference-host> 'cd /opt/llm-inference-bench && mkdir -p /srv/ai/bench-results && ts=$(date +%Y%m%d-%H%M%S) && PYTHONUNBUFFERED=1 ./.venv/bin/python -u llm_decode_bench.py --host 127.0.0.1 --port 5810 --model GLM-5.2 --prefill-only --prefill-contexts 8k,32k,64k,128k --display-mode live --output /srv/ai/bench-results/<profile-slug>-prefill-$ts.json'
```

## Operating Rules

- Keep OpenWebUI, LiteLLM clients, and other API users idle during measurements.
- Use unique prompts when measuring cold prefill.
- Treat first-use JIT cells as warmup and rerun affected cells.
- Compare runs with identical model, topology, MTP, cache format, and graph settings.
- Record whether the NVIDIA P2P driver settings described in [HARDWARE.md](HARDWARE.md) were active.
- Press `q` for a graceful partial result or `Ctrl+C` to stop immediately.
- Publish summarized results, not raw prompts or logs containing private data.
