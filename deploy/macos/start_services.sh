#!/usr/bin/env bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
launchctl load "$LAUNCH_DIR/com.tendercalc.dashboard.plist"
launchctl load "$LAUNCH_DIR/com.tendercalc.scheduler.plist"

echo "Services started"
