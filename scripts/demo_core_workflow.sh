#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON_BIN:-}"
SOURCE="examples/courier_drone.lth"
ASSET="courier_drone"
OUT_DIR="${LATHE_DEMO_OUT:-tmp_lathe_demo}"
DRY_RUN=0
SKIP_BUILD=0
VERBOSE_OUTPUT=0

if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
  elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON="python"
  fi
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --asset) ASSET="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --verbose-output) VERBOSE_OUTPUT=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

DEMO_DIR="$OUT_DIR/_demo_workflow"
if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$DEMO_DIR"
fi

run_step() {
  local title="$1"
  local artifact="$2"
  local status=0
  shift
  shift
  echo
  echo "== $title =="
  echo "$PYTHON $*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  if [[ -n "$artifact" ]]; then
    local artifact_path="$DEMO_DIR/$artifact"
    mkdir -p "$(dirname "$artifact_path")"
    if [[ "$VERBOSE_OUTPUT" -eq 1 ]]; then
      set +e
      "$PYTHON" "$@" 2>&1 | tee "$artifact_path"
      status="${PIPESTATUS[0]}"
      set -e
    else
      set +e
      "$PYTHON" "$@" >"$artifact_path" 2>&1
      status="$?"
      set -e
    fi
    if [[ "$status" -ne 0 ]]; then
      echo "Command failed. See $artifact_path for details." >&2
      exit "$status"
    fi
    echo "Saved output: $artifact_path"
  else
    "$PYTHON" "$@"
  fi
}

echo "Lathe core workflow demo"
echo "Source: $SOURCE"
echo "Asset:  $ASSET"
echo "Output: $OUT_DIR/$ASSET"

run_step "Check local environment" "doctor.txt" -m lathe.cli doctor
run_step "Normalize source" "normalized_program.json" -m lathe.cli normalize "$SOURCE"
run_step "Run semantic checks" "check.txt" -m lathe.cli check "$SOURCE"
run_step "Show build plan" "plan.json" -m lathe.cli plan "$SOURCE" "$ASSET"
run_step "Materialize asset" "materialized_asset.json" -m lathe.cli materialize "$SOURCE" "$ASSET"

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  run_step "Build certified package" "build_report_cli.json" -m lathe.cli build "$SOURCE" "$ASSET" --out "$OUT_DIR" --report json
  run_step "Inspect build report" "inspect.json" -m lathe.cli inspect "$OUT_DIR/$ASSET" --json
fi

echo
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. Re-run without --dry-run to execute the demo."
elif [[ "$SKIP_BUILD" -eq 1 ]]; then
  echo "Demo commands passed through materialization. Outputs are in $DEMO_DIR."
  echo "Re-run without --skip-build to create packaged artifacts."
else
  echo "Demo complete. Outputs are in $DEMO_DIR."
  echo "Open $OUT_DIR/$ASSET/stages/package/package_manifest.json for packaged artifacts."
fi
