#!/usr/bin/env bash
# Plan 03 Phase 3: run the import-linter layering contracts defined in
# .importlinter.  Exit non-zero if any contract is broken.
#
# Usage:
#   scripts/check_arch.sh
#
# Requires ``import-linter`` from the [dev] extra:
#   pip install -e ".[dev]"
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v lint-imports >/dev/null 2>&1; then
  echo "error: 'lint-imports' not on PATH. Install it with: pip install -e \".[dev]\"" >&2
  exit 2
fi

exec lint-imports --config .importlinter "$@"
