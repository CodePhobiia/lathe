# Lathe task runner (https://just.systems/)
# Cross-platform recipes. Requires `uv` (https://docs.astral.sh/uv/).

# Hero assets from CLAUDE.md (native-only defaults).
HEROES := "courier_drone brassbound_chest industrial_crate mechanical_door console_terminal sci_fi_wall_panel service_cabinet control_pedestal supply_container"

# Hero source files: assumes examples/<asset>.lth for each (adjust if sources
# differ). courier_drone is the canonical hero.
default:
    @just --list

# ------------------------------------------------------------------
# Bootstrap / environment
# ------------------------------------------------------------------

# Minimal dev install via uv.
bootstrap:
    uv sync --dev

# Full install including optional extras (ml, docs, etc).
bootstrap-full:
    uv sync --all-extras

# Environment / provider / backend diagnostics.
doctor:
    uv run python -m lathe.cli doctor

# ------------------------------------------------------------------
# Core compiler loop
# ------------------------------------------------------------------

# Static check on a .lth source.
check FILE:
    uv run python -m lathe.cli check {{FILE}}

# Emit effective build plan.
plan FILE ASSET:
    uv run python -m lathe.cli plan {{FILE}} {{ASSET}}

# Build a single asset into ./dist.
build FILE ASSET:
    uv run python -m lathe.cli build {{FILE}} {{ASSET}} --out dist

# Build every hero-family asset listed in CLAUDE.md.
# Each hero is assumed to live at examples/<asset>.lth.
build-heroes:
    #!/usr/bin/env bash
    set -euo pipefail
    heroes=(courier_drone brassbound_chest industrial_crate mechanical_door console_terminal sci_fi_wall_panel service_cabinet control_pedestal supply_container)
    for asset in "${heroes[@]}"; do
        src="examples/${asset}.lth"
        if [ ! -f "$src" ]; then
            echo "skip ${asset}: ${src} not found" >&2
            continue
        fi
        echo "=== build ${asset} ==="
        uv run python -m lathe.cli build "$src" "$asset" --out dist
    done

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

# Full pytest suite.
test:
    uv run pytest -q

# Run tests from a single file.
test-file FILE:
    uv run pytest -q {{FILE}}

# Run tests matching a name expression (pytest -k).
test-one NAME:
    uv run pytest -q -k {{NAME}}

# Lathe-level tests (runs `test` declarations inside .lth sources).
lathe-test:
    uv run python -m lathe.cli test

# Lathe-level benchmarks.
bench:
    uv run python -m lathe.cli bench

# ------------------------------------------------------------------
# Lint / format / types / docs
# ------------------------------------------------------------------

lint:
    uv run ruff check .
    uv run ruff format --check .

fmt:
    uv run ruff format .
    uv run ruff check --fix .

typecheck:
    uv run mypy lathe/

docs:
    uv run mkdocs build --strict

docs-serve:
    uv run mkdocs serve

# ------------------------------------------------------------------
# Cleaning / locks / containers
# ------------------------------------------------------------------

# Remove transient build roots + parser cache.
# Windows users: run `pwsh scripts/clean_workspace.ps1 -Confirm` instead.
clean:
    bash scripts/clean_workspace.sh --confirm

lock:
    uv lock

lock-upgrade:
    uv lock --upgrade

docker-build:
    docker build -t lathe:local .

# ------------------------------------------------------------------
# CI aggregate
# ------------------------------------------------------------------

ci: lint typecheck test
