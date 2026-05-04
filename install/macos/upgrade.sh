#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

bash install/macos/stop.sh || true

python -m app.cli backup-db

source .venv/bin/activate
pip install -e .[dev]

python -m app.cli db upgrade
python -m app.cli doctor

bash install/macos/start.sh
echo "Upgrade complete"
