#!/usr/bin/env bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
launchctl unload "$LAUNCH_DIR/com.tendercalc.dashboard.plist" >/dev/null 2>&1 || true
launchctl unload "$LAUNCH_DIR/com.tendercalc.scheduler.plist" >/dev/null 2>&1 || true

echo "Services stopped"
