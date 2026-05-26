#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    PYTHON_BIN=python
  fi
fi
"$PYTHON_BIN" -m pip install -e ".[dev]"
"$PYTHON_BIN" -m PyInstaller --noconfirm LCSMILES.spec
