#!/usr/bin/env python3
"""Planted-fact correctness probe over a long deterministic prompt.

Sends a single greedy chat completion (temperature 0, fixed seed) to an
OpenAI-compatible endpoint. The prompt plants exactly three retrievable facts
at spread positions inside deterministic filler text, then asks one question
whose correct answer requires all three. The script checks whether the
completion names all three facts and prints the completion's SHA-256 so two
runs can be compared for byte-identity.

``store`` and ``replay`` modes send the byte-identical request body.
``store`` labels a run intended to populate an external KV-cache tier;
``replay`` labels a re-issue of that same request after a restart, so a reader
can compare elapsed time and completion hash across the two runs. The modes do
not construct different prompts.

Token count is an approximation: the filler is sized in words and multiplied
by 4/3 to estimate tokens. This is not a tokenizer count; the actual token
count depends on the endpoint's tokenizer. Determinism comes from a seeded
``random.Random`` building filler from a fixed word list, so two invocations
with the same ``--seed`` produce a byte-identical prompt and request body.

Assertions and their detection targets:

- ``facts=N/3`` — the completion must name all three planted facts. This
  detects KV-cache corruption: if an external cache tier restores or
  recomputes the prompt incorrectly, the model loses access to facts planted
  in the filler and cannot answer the question correctly.
- ``sha256=<digest>`` — the completion hash, printed so a ``store`` run and
  a ``replay`` run after a full restart can be compared for byte-identity
  under identical greedy conditions. A mismatch means the serving path is
  non-deterministic or the cache tier altered the prompt.
- Exit 0 only when all three facts are found. A partial score means the model
  could not retrieve every fact from the long context, which indicates either
  cache corruption or a context-length limitation.
"""
import argparse
import hashlib
import json
import random
import sys
import time
import urllib.error
import urllib.request

# Fixed word pool for filler generation. The exact words are irrelevant; what
# matters is that the pool is fixed so the seeded RNG always selects the same
# sequence, making the prompt byte-identical for a given seed.
_WORD_POOL = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi", "rho",
    "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega",
    "vector", "matrix", "tensor", "scalar", "gradient", "divergence",
    "curl", "laplacian", "hamiltonian", "lagrangian", "eigenvalue",
    "eigenvector", "manifold", "topology", "calculus", "algebra",
    "theorem", "lemma", "corollary", "axiom", "postulate", "conjecture",
    "hypothesis", "experiment", "observation", "measurement", "analysis",
    "synthesis", "model", "simulation", "parameter", "variable",
    "constant", "function", "operator", "domain", "range", "kernel",
]

# Three facts planted at spread positions in the filler. Each is a (label,
# value) pair. The question asks for all three labels; the check searches for
# the distinctive part of each value in the completion.
_FACTS = [
    ("authorization code", "XJ-7Q29"),
    ("shipment weight", "814 metric tons"),
    ("receiving officer", "Dr. Helene Voss"),
]

# Substrings searched for in the completion to confirm each fact was retained.
# Using the distinctive part of each value makes the check robust to minor
# rephrasing by the model while still requiring the specific fact.
_FACT_NEEDLES = ["XJ-7Q29", "814", "Helene Voss"]

# Timeout for the HTTP request, seconds. A 24K-token cold prefill can take
# over 40 seconds on the reference hardware, so the timeout is generous.
_TIMEOUT = 300


def build_prompt(tokens, seed):
    """Build a deterministic prompt of approximately ``tokens`` tokens.

    Token count is estimated as words times 4/3; this is an approximation,
    not a tokenizer count. Three facts are planted at roughly the 25%, 50%,
    and 75% positions of the filler. A question requiring all three facts
    is appended at the end.
    """
    rng = random.Random(seed)
    # 1 token ≈ 4/3 words, so words ≈ tokens * 3/4
    target_words = max(1, int(tokens * 3 / 4))
    segment_len = target_words // 4

    def make_filler(n):
        words = [rng.choice(_WORD_POOL) for _ in range(n)]
        paragraphs = []
        for i in range(0, len(words), 80):
            paragraphs.append(" ".join(words[i:i + 80]))
        return "\n\n".join(paragraphs)

    parts = [
        make_filler(segment_len),
        "The {} is {}.".format(_FACTS[0][0], _FACTS[0][1]),
        make_filler(segment_len),
        "The {} is {}.".format(_FACTS[1][0], _FACTS[1][1]),
        make_filler(segment_len),
        "The {} is {}.".format(_FACTS[2][0], _FACTS[2][1]),
        make_filler(segment_len),
    ]
    filler = "\n\n".join(parts)

    question = (
        "Based only on the information above, state three things: "
        "the authorization code, the shipment weight, and the "
        "receiving officer's name."
    )
    return filler + "\n\n" + question


def build_request_body(model, tokens, seed):
    """Build the chat-completion request body as a dict."""
    prompt = build_prompt(tokens, seed)
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a retrieval assistant. Answer questions using "
                    "only the information provided in the user's message."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "seed": seed,
        "stream": False,
        "max_tokens": 512,
    }


def _print_conn_error(url, err):
    """Print a human-readable connection error and exit."""
    if isinstance(err, urllib.error.HTTPError):
        msg = "HTTP {} {}".format(err.code, err.reason)
        body_text = err.read().decode("utf-8", "replace")[:500]
        print("error: cannot reach {}: {}".format(url, msg), file=sys.stderr)
        if body_text:
            print("  response: {}".format(body_text), file=sys.stderr)
    else:
        reason = getattr(err, "reason", err)
        if isinstance(reason, OSError):
            msg = reason.strerror or str(reason)
        else:
            msg = str(reason)
        print("error: cannot reach {}: {}".format(url, msg), file=sys.stderr)


def send_request(endpoint, body):
    """Send a non-streaming chat completion and return the content string."""
    url = endpoint.rstrip("/") + "/v1/chat/completions"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=_TIMEOUT)
    except urllib.error.HTTPError as e:
        _print_conn_error(url, e)
        sys.exit(1)
    except urllib.error.URLError as e:
        _print_conn_error(url, e)
        sys.exit(1)
    except OSError as e:
        print(
            "error: cannot reach {}: {}".format(url, e.strerror or e),
            file=sys.stderr,
        )
        sys.exit(1)

    raw = resp.read().decode("utf-8")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(
            "error: endpoint returned non-JSON: {}".format(raw[:500]),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(
            "error: unexpected response shape: {}".format(raw[:500]),
            file=sys.stderr,
        )
        sys.exit(1)


def check_facts(completion):
    """Return the count of planted facts found in the completion text."""
    return sum(1 for needle in _FACT_NEEDLES if needle in completion)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Planted-fact correctness probe over a long deterministic "
            "prompt. Sends a greedy completion whose prompt plants three "
            "facts at spread positions in deterministic filler, then checks "
            "whether the completion names all three."
        ),
    )
    parser.add_argument(
        "mode",
        choices=["store", "replay"],
        help=(
            "store: run to populate a cache tier; "
            "replay: re-issue the identical prompt after a restart"
        ),
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000",
        help="OpenAI-compatible endpoint base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default="dsv4-flash",
        help="model name served by the endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--tokens",
        type=int,
        default=24000,
        help="approximate prompt token count, estimated as words * 4/3 "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed for filler generation and the API request seed "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the request body twice, print each SHA-256 to verify "
        "determinism, and exit without sending",
    )
    args = parser.parse_args()

    if args.tokens < 1:
        parser.error("--tokens must be a positive integer")

    if args.dry_run:
        body1 = build_request_body(args.model, args.tokens, args.seed)
        body2 = build_request_body(args.model, args.tokens, args.seed)
        h1 = hashlib.sha256(
            json.dumps(body1, sort_keys=True).encode("utf-8")
        ).hexdigest()
        h2 = hashlib.sha256(
            json.dumps(body2, sort_keys=True).encode("utf-8")
        ).hexdigest()
        print("sha256: {}".format(h1))
        print("sha256: {}".format(h2))
        print("deterministic: {}".format(h1 == h2))
        return

    body = build_request_body(args.model, args.tokens, args.seed)
    start = time.monotonic()
    completion = send_request(args.endpoint, body)
    elapsed = time.monotonic() - start

    digest = hashlib.sha256(completion.encode("utf-8")).hexdigest()
    facts = check_facts(completion)

    print(
        "replay-gate mode={} tokens={} seed={} elapsed={:.2f}s "
        "sha256={} facts={}/3".format(
            args.mode, args.tokens, args.seed, elapsed, digest, facts
        )
    )

    if facts != 3:
        sys.exit(1)


if __name__ == "__main__":
    main()
