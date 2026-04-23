#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: scripts/lathe_asset_loop.sh <file.lth> <asset_name> [out_dir]" >&2
  exit 2
fi

FILE="$1"
ASSET="$2"
OUT_DIR="${3:-dist}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m lathe.cli check "$FILE"
python -m lathe.cli plan "$FILE" "$ASSET"
python -m lathe.cli materialize "$FILE" "$ASSET"
python -m lathe.cli build "$FILE" "$ASSET" --out "$OUT_DIR"
