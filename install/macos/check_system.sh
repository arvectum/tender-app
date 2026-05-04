#!/usr/bin/env bash
set -euo pipefail

echo "[check] OS"
uname -a | grep -qi darwin || { echo "macOS required"; exit 1; }

echo "[check] Python 3.11+"
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 11), "Python 3.11+ required"
print(sys.version.split()[0])
PY

echo "[check] PostgreSQL tools"
command -v psql >/dev/null || { echo "psql not found"; exit 1; }
command -v pg_dump >/dev/null || { echo "pg_dump not found"; exit 1; }

echo "System check OK"
