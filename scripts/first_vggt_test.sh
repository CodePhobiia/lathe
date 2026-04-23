#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
if [[ ! -x "$VENV_PYTHON" ]]; then
  VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing repo-local virtualenv at .venv. Run scripts/bootstrap_local.sh first." >&2
  exit 1
fi

RUNTIME_CONFIG="examples/runtime_configs/vggt_local.json"
OUT_DIR="dist_vggt_first_test"

echo "Running Lathe doctor with VGGT runtime config..."
"$VENV_PYTHON" -m lathe.cli doctor --runtime-config "$RUNTIME_CONFIG"

echo
echo "Running first strict VGGT build. This can take a while on CPU..."
"$VENV_PYTHON" -m lathe.cli build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out "$OUT_DIR" --runtime-config "$RUNTIME_CONFIG"
