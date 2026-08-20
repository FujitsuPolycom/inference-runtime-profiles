#!/usr/bin/env python3
"""Private-data check for a profile bundle.

Same patterns as tools/validate-bundle.sh, without the ripgrep dependency, so
the check runs anywhere Python does. Markdown and .example files are exempt,
matching the shell script's globs.

Usage: python tools/check-private.py profiles/<bundle>
Exit 0 = nothing found, 1 = candidate private data, 2 = bundle incomplete.
"""
import os
import re
import sys

PATTERNS = [
    ("secret", re.compile(r"(?i)(password|access[_-]?token|auth[_-]?token|hf[_-]?token|api[_-]?key|private[_-]?key)")),
    ("home path", re.compile(r"/home/[^/\s]+|/root/")),
    ("private ip", re.compile(r"\b(?:192\.168\.|10\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.)\d")),
]
EXEMPT_SUFFIXES = (".md", ".example")


def main(path):
    if not os.path.isfile(os.path.join(path, "manifest.json")):
        print(f"{path}: no manifest.json", file=sys.stderr)
        return 2
    if not (os.path.isfile(os.path.join(path, "README.md"))
            or os.path.isfile(os.path.join(path, "profile.env.example"))):
        print(f"{path}: no README.md or profile.env.example", file=sys.stderr)
        return 2

    hits = []
    for root, _dirs, files in os.walk(path):
        for name in sorted(files):
            if name.endswith(EXEMPT_SUFFIXES):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            with open(full, encoding="utf-8", errors="replace") as fh:
                for n, line in enumerate(fh, 1):
                    for label, pattern in PATTERNS:
                        if pattern.search(line):
                            hits.append((rel, n, label, line.strip()[:120]))

    for rel, n, label, text in hits:
        print(f"{rel}:{n}: {label}: {text}")
    if hits:
        print(f"\n{len(hits)} candidate private values; review the bundle.", file=sys.stderr)
        return 1
    print(f"Bundle looks publishable: {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
