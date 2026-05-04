#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== launchd status ==="
launchctl list | grep -E "tender-dashboard|tender-scheduler" || true

echo "=== healthcheck ==="
python -m app.cli healthcheck || true

echo "=== last logs ==="
tail -n 40 logs/connectors.log 2>/dev/null || true
tail -n 40 logs/import.log 2>/dev/null || true
