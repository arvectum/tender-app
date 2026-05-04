#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

DELETE_DATA=false
if [[ "${1:-}" == "--delete-data" ]]; then
  DELETE_DATA=true
fi

bash deploy/macos/stop_services.sh || true
bash deploy/macos/uninstall_launchd.sh || true

if [[ "$DELETE_DATA" == "true" ]]; then
  rm -rf data logs exports backups
  echo "Runtime data removed"
else
  echo "Runtime data kept (use --delete-data to remove)"
fi
