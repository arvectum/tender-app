#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Database bootstrap is environment-specific."
echo "Use your PostgreSQL admin account to create DB/user if needed."
echo "Then run: python -m app.cli init-db"
