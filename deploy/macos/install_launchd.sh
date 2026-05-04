#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
LAUNCH_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LAUNCH_DIR"
mkdir -p "$PROJECT_DIR/logs"

for name in tender-dashboard tender-scheduler; do
  src="$PROJECT_DIR/deploy/macos/${name}.plist.example"
  dst="$LAUNCH_DIR/com.tendercalc.${name#tender-}.plist"
  sed "s|__PROJECT_DIR__|$PROJECT_DIR|g; s|__PYTHON_BIN__|$PYTHON_BIN|g" "$src" > "$dst"
  launchctl unload "$dst" >/dev/null 2>&1 || true
  launchctl load "$dst"
  echo "Installed $dst"
done

echo "Done. Use deploy/macos/start_services.sh to start manually if needed."
