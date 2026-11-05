#!/usr/bin/env bash
# Wait until a URL returns HTTP 2xx, or fail with a clear message.
# Usage: scripts/wait-for.sh http://localhost:8000/health [timeout_seconds]
set -euo pipefail

url="${1:?usage: wait-for.sh URL [timeout_seconds]}"
timeout="${2:-60}"
deadline=$(( $(date +%s) + timeout ))

until curl -fsS -o /dev/null "$url"; do
  if (( $(date +%s) >= deadline )); then
    echo "ERROR: $url not ready after ${timeout}s" >&2
    exit 1
  fi
  sleep 1
done
echo "ready: $url"
