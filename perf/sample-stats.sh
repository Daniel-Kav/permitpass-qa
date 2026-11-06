#!/usr/bin/env bash
# Sample container CPU and memory every N seconds while a perf test runs.
# Usage: perf/sample-stats.sh <output.csv> [interval_seconds]
set -euo pipefail
out="${1:?usage: sample-stats.sh output.csv [interval]}"
interval="${2:-10}"
echo "timestamp,container,cpu_percent,mem_usage" > "$out"
while true; do
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' \
    | sed "s/^/$(date -u +%FT%TZ),/" >> "$out"
  sleep "$interval"
done
