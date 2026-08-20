# Correctness gates

Two probes that check what [RESULTS.md](../RESULTS.md) claims about this
profile. Both use the standard library only, take an OpenAI-compatible
`--endpoint` (default loopback) and `--model`, and exit non-zero when the
property they assert does not hold. Run them from any host that can reach the
endpoint.

`--dry-run` builds the request, prints its SHA-256 and exits without sending,
so a reader can confirm the request is deterministic before spending engine
time on it.

## `replay-gate.py` — planted-fact correctness over a long prompt

Builds a filler prompt of approximately `--tokens` tokens from `--seed`, plants
three facts at spread positions, and asks a question that cannot be answered
without all three. Reports elapsed seconds, the completion's SHA-256 and
`facts=N/3`, and exits 0 only when N is 3.

`store` and `replay` send the identical prompt; they differ in intent. Run
`store` to populate the cache tier, replace both containers, then run `replay`
and compare elapsed time and completion hash against the store run. A restore
that works shows a much shorter elapsed time with the same answers.

```bash
python3 replay-gate.py store --tokens 24000
python3 replay-gate.py replay --tokens 24000
```

Token counts are estimated as words times 4/3, not counted with the model's
tokenizer, so `--tokens` sets prompt size approximately.

## `tool-array-probe.py` — output integrity under a large tool array

Generates `--tools` distinct function-tool definitions (default 34), sends them
with a chat completion, streams the response, and reports character count and
whether any end-of-sequence or template marker leaked into the content. Exits
non-zero below `--min-chars` (default 800) or on a leaked marker.

The array is generated rather than captured, so the request is reproducible and
carries no recorded conversation.

```bash
python3 tool-array-probe.py
```

A component set that mishandles large tool arrays returns short or
marker-contaminated output; the profile's runtime returns long coherent prose.

## Results on the reference pair

Measured 2026-08-20 against the deployment described in
[RESULTS.md](../RESULTS.md), at concurrency 1:

| Gate | Result |
|---|---|
| `replay-gate.py store --tokens 24000` | `facts=3/3`, 13.28 s, exit 0 |
| `tool-array-probe.py` | 34 tools, 2,499 characters, no leaked markers, 14.08 s, exit 0 |
