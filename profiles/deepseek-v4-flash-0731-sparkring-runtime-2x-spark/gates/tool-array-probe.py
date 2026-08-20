#!/usr/bin/env python3
"""Tool-array output-corruption probe.

Sends a chat completion carrying a programmatically generated array of
``--tools`` (default 34) distinct function-tool definitions, each with a
name, description, and a small JSON-Schema parameter object. The response is
streamed; content is accumulated and checked for two corruption signals:

- **Length floor** — a coherent response to this prompt exceeds
  ``--min-chars`` (default 800). A completion shorter than the threshold
  indicates the engine truncated or dropped content under the tool-array
  workload, which is the failure mode this probe targets: a from-source
  humming-W4A16 build deterministically corrupts output on a 34-tool
  request. This runtime streams clean, producing well over the threshold.
- **Leaked markers** — the accumulated text is scanned for end-of-sequence
  and template markers (``</s>``, ``<|``). A leaked marker means the
  model emitted a control or template token into visible output, which is a
  distinct corruption signature of the failing build. The qualified runtime
  emits none.

The tool array is generated, not captured from a real request. A captured
open-webui request carries private session data and is not reproducible from
this repository; a generated array of plausible function definitions is
deterministic for a given tool count and exercises the same code path — a
large tool array serialized into the prompt.

Determinism: tool definitions are built from a fixed template and numbered
index, so two runs with the same ``--tools`` produce a byte-identical tool
array and request body. ``--dry-run`` builds the request twice and prints each
SHA-256 to verify this.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request

_TOOL_DOMAINS = [
    ("weather", "Get current weather conditions", ["city", "units"]),
    ("calendar", "List calendar events", ["date", "calendar_id"]),
    ("email", "Send an email message", ["to", "subject", "body"]),
    ("search", "Search the web", ["query", "max_results"]),
    ("files", "List files in a directory", ["path", "recursive"]),
    ("database", "Run a SQL query", ["connection", "sql"]),
    ("translate", "Translate text between languages", ["text", "source", "target"]),
    ("calculator", "Evaluate a mathematical expression", ["expression", "precision"]),
    ("image", "Generate an image from a prompt", ["prompt", "width", "height"]),
    ("audio", "Transcribe an audio file", ["file_path", "language"]),
    ("video", "Encode a video file", ["input_path", "codec", "bitrate"]),
    ("notes", "Create a text note", ["title", "content", "tags"]),
    ("tasks", "Create a task item", ["title", "due_date", "priority"]),
    ("reminders", "Set a reminder", ["message", "remind_at"]),
    ("contacts", "Look up a contact", ["name", "field"]),
    ("maps", "Get directions between two points", ["origin", "destination", "mode"]),
    ("news", "Fetch headlines", ["category", "count"]),
    ("stocks", "Get a stock quote", ["symbol", "exchange"]),
    ("crypto", "Get cryptocurrency price", ["coin", "currency"]),
    ("finance", "Calculate a loan payment", ["principal", "rate", "term"]),
    ("shipping", "Track a package", ["tracking_number", "carrier"]),
    ("inventory", "Check stock level", ["sku", "warehouse"]),
    ("orders", "Place a purchase order", ["product_id", "quantity", "address"]),
    ("payments", "Process a payment", ["amount", "currency", "method"]),
    ("invoices", "Generate an invoice", ["customer_id", "items"]),
    ("tickets", "Create a support ticket", ["subject", "description", "severity"]),
    ("logs", "Query application logs", ["service", "level", "since"]),
    ("metrics", "Fetch system metrics", ["host", "metric", "window"]),
    ("alerts", "Create a monitoring alert", ["name", "condition", "threshold"]),
    ("deployments", "Trigger a deployment", ["app", "environment", "version"]),
    ("repositories", "List git repositories", ["organization", "page"]),
    ("branches", "List branches in a repository", ["repo", "limit"]),
    ("commits", "Get recent commits", ["repo", "branch", "count"]),
    ("pulls", "List open pull requests", ["repo", "state", "sort"]),
    ("reviews", "Get code review comments", ["pull_number", "repo"]),
    ("issues", "List repository issues", ["repo", "state", "labels"]),
    ("wikis", "Search wiki pages", ["space", "query"]),
    ("chat", "Post a message to a channel", ["channel", "message"]),
    ("users", "Look up a user profile", ["username", "fields"]),
    ("auth", "Issue an access token", ["client_id", "scope"]),
]

_LEAKED_MARKERS = ["</s>", "<|"]

# Timeout for establishing the connection and reading the full stream.
_TIMEOUT = 300


def _make_param_schema(param_names):
    """Build a small JSON-Schema object for the given parameter names."""
    props = {}
    required = []
    for name in param_names:
        props[name] = {"type": "string", "description": "Value for {}.".format(name)}
        required.append(name)
    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def build_tools(count):
    """Build ``count`` distinct function-tool definitions.

    Each tool has a unique name, description, and a JSON-Schema parameter
    object derived from a fixed domain table. When ``count`` exceeds the
    table length, names are suffixed with a numeric index to keep them
    distinct while preserving plausibility.
    """
    tools = []
    for i in range(count):
        domain, desc, params = _TOOL_DOMAINS[i % len(_TOOL_DOMAINS)]
        name = domain if i < len(_TOOL_DOMAINS) else "{}_{}".format(domain, i)
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": _make_param_schema(params),
            },
        })
    return tools


def build_request_body(model, tool_count):
    """Build the streaming chat-completion request body with tool array."""
    tools = build_tools(tool_count)
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant with access to the provided "
                    "tools. Explain which tools you would use to help the "
                    "user book a flight, reserve a hotel, and rent a car for "
                    "a trip. Describe your reasoning step by step."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I need to plan a trip to Zurich next month. Help me "
                    "figure out the tools to use for booking flights, "
                    "finding a hotel, and renting a car."
                ),
            },
        ],
        "tools": tools,
        "temperature": 0,
        "seed": 0,
        "stream": True,
        "max_tokens": 1024,
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


def stream_completion(endpoint, body):
    """Stream a chat completion and return the accumulated content string."""
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

    content_parts = []
    try:
        for raw_line in resp:
            line = raw_line.decode("utf-8", "replace").rstrip()
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            try:
                delta = chunk["choices"][0]["delta"]["content"]
            except (KeyError, IndexError, TypeError):
                continue
            if delta:
                content_parts.append(delta)
    finally:
        resp.close()

    return "".join(content_parts)


def check_leaked_markers(text):
    """Return a list of leaked markers found in the text."""
    return [m for m in _LEAKED_MARKERS if m in text]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Tool-array output-corruption probe. Sends a streaming chat "
            "completion carrying a generated tool array and checks the "
            "response for truncation (below --min-chars) and leaked "
            "end-of-sequence or template markers."
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
        "--min-chars",
        type=int,
        default=800,
        help="minimum acceptable response length in characters "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--tools",
        type=int,
        default=34,
        help="number of tool definitions to generate in the request "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the request body twice, print each SHA-256 to verify "
        "determinism, and exit without sending",
    )
    args = parser.parse_args()

    if args.tools < 1:
        parser.error("--tools must be a positive integer")
    if args.min_chars < 1:
        parser.error("--min-chars must be a positive integer")

    if args.dry_run:
        body1 = build_request_body(args.model, args.tools)
        body2 = build_request_body(args.model, args.tools)
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

    body = build_request_body(args.model, args.tools)
    start = time.monotonic()
    content = stream_completion(args.endpoint, body)
    elapsed = time.monotonic() - start

    char_count = len(content)
    leaked = check_leaked_markers(content)

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    print(
        "tool-array-probe tools={} chars={} elapsed={:.2f}s "
        "sha256={} leaked={}".format(
            args.tools, char_count, elapsed, digest,
            ",".join(leaked) if leaked else "none"
        )
    )

    failed = False
    if char_count < args.min_chars:
        print(
            "fail: response length {} is below threshold {}".format(
                char_count, args.min_chars
            ),
            file=sys.stderr,
        )
        failed = True
    if leaked:
        print(
            "fail: leaked markers found: {}".format(", ".join(leaked)),
            file=sys.stderr,
        )
        failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
