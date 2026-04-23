#!/usr/bin/env bash
# clean_workspace.sh — remove transient build roots + parser cache.
#
# Safety model:
#   * Refuses to run outside the repo root (checks for pyproject.toml
#     in the current working directory).
#   * Requires --confirm / -y before touching anything.
#   * Always lists targets first.
#   * Idempotent: missing directories are skipped silently.
#
# Usage:
#   scripts/clean_workspace.sh            # dry-run: list only
#   scripts/clean_workspace.sh --confirm  # delete
#   scripts/clean_workspace.sh -y

set -euo pipefail

confirm=0
for arg in "$@"; do
    case "$arg" in
        --confirm|-y)
            confirm=1
            ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *)
            echo "unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

if [ ! -f "pyproject.toml" ]; then
    echo "refusing to run: pyproject.toml not found in cwd ($PWD). Run from the repo root." >&2
    exit 2
fi

# Glob patterns for transient roots documented in CLAUDE.md.
patterns=(
    'dist_*'
    'tmp_*'
    'warm_*'
    'v05_*'
    'cache_probe_*'
)

# Fixed targets (not globbed).
fixed_targets=(
    '.lathe_lark_cache'
    '.venv_old_broken'
)

targets=()

shopt -s nullglob
for pat in "${patterns[@]}"; do
    for match in $pat; do
        if [ -d "$match" ]; then
            targets+=("$match")
        fi
    done
done
shopt -u nullglob

for t in "${fixed_targets[@]}"; do
    if [ -e "$t" ]; then
        targets+=("$t")
    fi
done

if [ ${#targets[@]} -eq 0 ]; then
    echo "nothing to clean."
    exit 0
fi

echo "targets (${#targets[@]}):"
for t in "${targets[@]}"; do
    echo "  $t"
done

if [ "$confirm" -ne 1 ]; then
    echo
    echo "dry run. pass --confirm (or -y) to delete."
    exit 0
fi

for t in "${targets[@]}"; do
    rm -rf -- "$t"
    echo "removed $t"
done

echo "done."
