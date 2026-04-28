#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON="$PYTHON_BIN"
elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="python"
fi

OUT_DIR="${LATHE_SMOKE_OUT:-tmp_lathe_smoke}"
PYTEST_ARGS=(
  -q
  tests/test_lathe.py
  tests/test_roundtrip.py
  tests/test_doctor.py
  tests/unit/test_runtime_config.py
  -m
  "not requires_blender and not requires_xatlas and not requires_torch and not requires_network"
)

"$PYTHON" -m lathe.cli doctor
"$PYTHON" -m lathe.cli check examples/courier_drone.lth
"$PYTHON" -m lathe.cli plan examples/courier_drone.lth courier_drone >/dev/null
"$PYTHON" -m pytest "${PYTEST_ARGS[@]}"
"$PYTHON" -m lathe.cli build examples/courier_drone.lth courier_drone --out "$OUT_DIR"

echo "Lathe smoke passed. Build artifacts written under $OUT_DIR/courier_drone."
