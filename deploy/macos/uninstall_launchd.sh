#!/usr/bin/env bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"

for file in "$LAUNCH_DIR/com.tendercalc.dashboard.plist" "$LAUNCH_DIR/com.tendercalc.scheduler.plist"; do
  if [[ -f "$file" ]]; then
    launchctl unload "$file" >/dev/null 2>&1 || true
    rm -f "$file"
    echo "Removed $file"
  fi
done
