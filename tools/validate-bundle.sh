#!/usr/bin/env bash
set -euo pipefail
path=${1:?bundle path required}
test -f "$path/manifest.json"
test -f "$path/README.md" || test -f "$path/profile.env.example"
if rg -n -i '(password|token|api[_-]?key|private[_-]?key|/home/[^/]+|/root/|192\.168\.|10\.[0-9]+\.|172\.(1[6-9]|2[0-9]|3[01])\.)' "$path" --glob '!*.md' --glob '!*.example'; then
  echo 'Possible private data found; review the bundle.' >&2
  exit 1
fi
echo "Bundle looks publishable: $path"

