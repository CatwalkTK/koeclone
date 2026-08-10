#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PWD}/src"
exec .venv/bin/python -m uvicorn koeclone.api.app:create_default_app \
  --factory --host 127.0.0.1 --port "${KOECLONE_PORT:-8000}"
