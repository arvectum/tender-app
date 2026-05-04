#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

bash install/macos/check_system.sh

python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

bash install/macos/create_env.sh

mkdir -p data logs exports backups data/browser_state

python -m app.cli init-db

echo "Create admin user:"
echo "python -m app.cli user create --username admin --email admin@example.com --role admin --password 'ChangeMe123!'"

bash install/macos/install_services.sh

echo "Install complete"
echo "Dashboard: http://127.0.0.1:8000"
echo "Useful commands:"
echo "  bash install/macos/status.sh"
echo "  python -m app.cli doctor"
