#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ".env created from .env.example"
else
  echo ".env already exists"
fi
