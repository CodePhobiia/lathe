#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

DEV=0
HUNYUAN_HTTP=0
VGGT=0
XATLAS=0
EXPORT=0
SKIP_DOCTOR=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev) DEV=1 ;;
    --hunyuan-http) HUNYUAN_HTTP=1 ;;
    --vggt) VGGT=1 ;;
    --xatlas) XATLAS=1 ;;
    --export) EXPORT=1 ;;
    --skip-doctor) SKIP_DOCTOR=1 ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
if [[ ! -x "$VENV_PYTHON" ]]; then
  VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
fi

"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

declare -a EXTRAS=()
if [[ "$DEV" -eq 1 ]]; then EXTRAS+=("dev"); fi
if [[ "$EXPORT" -eq 1 ]]; then EXTRAS+=("export"); fi
if [[ "$HUNYUAN_HTTP" -eq 1 ]]; then EXTRAS+=("hunyuan_http"); fi
if [[ "$VGGT" -eq 1 ]]; then EXTRAS+=("vggt"); fi
if [[ "$XATLAS" -eq 1 ]]; then
  VSDEVCMD="/c/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat"
  if command -v nmake >/dev/null 2>&1 || command -v cmake >/dev/null 2>&1 || [[ -f "$VSDEVCMD" ]]; then
    EXTRAS+=("xatlas")
  else
    echo "warning: skipping xatlas extra because native build tools are unavailable" >&2
  fi
fi

PACKAGE_SPEC="."
if [[ "${#EXTRAS[@]}" -gt 0 ]]; then
  PACKAGE_SPEC=".[${EXTRAS[*]}]"
  PACKAGE_SPEC="${PACKAGE_SPEC// /,}"
fi

if [[ "$XATLAS" -eq 1 && -f "${VSDEVCMD:-}" ]]; then
  cmd.exe /c "\"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat\" -host_arch=x64 -arch=x64 && \"$VENV_PYTHON\" -m pip install -e \"$PACKAGE_SPEC\""
else
  "$VENV_PYTHON" -m pip install -e "$PACKAGE_SPEC"
fi

if [[ "$VGGT" -eq 1 ]]; then
  cat <<'EOF'

VGGT note:
  The pip extra installs torch only. The official VGGT package is not currently published on PyPI.
  Install it manually if needed:
    git clone https://github.com/facebookresearch/vggt.git external/vggt
    ./.venv/Scripts/python.exe -m pip install -e ./external/vggt
EOF
fi

if [[ "$SKIP_DOCTOR" -ne 1 ]]; then
  "$VENV_PYTHON" -m lathe.cli doctor
fi
