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

# Verify uv.lock and generated requirements exports match pyproject.toml.
deps-check:
    python scripts/check_dependency_sync.py

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
# Local security / release gates
# ------------------------------------------------------------------

# Run the same security scanners wired in CI. Requires bandit, semgrep,
# gitleaks, and pip-audit on PATH.
security-local:
    #!/usr/bin/env bash
    set -euo pipefail
    bandit --configfile bandit.yaml --severity-level medium --confidence-level medium --recursive lathe/
    semgrep --error --config p/python --config p/security-audit --config p/owasp-top-ten lathe/
    gitleaks detect --config=.gitleaks.toml --source=. --verbose
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    grep -vE '^-e[[:space:]]+\.' requirements.txt > "$tmpdir/lathe-requirements-audit.txt"
    grep -vE '^-e[[:space:]]+\.' requirements-dev.txt > "$tmpdir/lathe-requirements-dev-audit.txt"
    pip-audit --strict --no-deps --requirement "$tmpdir/lathe-requirements-audit.txt"
    pip-audit --strict --no-deps --requirement "$tmpdir/lathe-requirements-dev-audit.txt"

# Run the local release-candidate gate before opening or tagging a release.
release-local:
    #!/usr/bin/env bash
    set -euo pipefail
    python scripts/check_release_metadata.py --expected-tag "${EXPECTED_TAG:-v0.2.0-rc.1}"
    ruff check .
    python -m pytest -q
    DISABLE_MKDOCS_2_WARNING=true mkdocs build --strict --site-dir site
    python -m pip install build twine
    python -m build
    twine check dist/*
    cyclonedx-py environment --output-format JSON --schema-version 1.5 --outfile dist/sbom.json
    cyclonedx-py environment --output-format XML --schema-version 1.5 --outfile dist/sbom.xml

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

# CI mirror recipes assume the project has already been installed with the same
# editable dev setup used by GitHub Actions:
#   python -m pip install --upgrade pip
#   python -m pip install -e ".[dev]"

lint-required:
    ruff check .

lint-format-advisory:
    -ruff format --check .

mypy-advisory:
    -mypy lathe/

ci-fast-test:
    python -m pytest -q tests/test_lathe.py tests/test_roundtrip.py tests/test_backends.py tests/test_doctor.py tests/test_gallery.py tests/test_remediation_metadata.py tests/test_language_v08.py tests/test_language_v09.py tests/test_language_v10.py tests/unit/test_net.py tests/unit/test_runtime_config.py tests/unit/test_schema.py tests/unit/test_paths.py tests/unit/test_ref.py tests/unit/test_ref_phase2.py tests/unit/test_stage_collision.py tests/unit/test_telemetry.py tests/unit/test_validators_surface.py tests/unit/test_validators_visual.py tests/unit/test_utils.py tests/bugs -m "not requires_blender and not requires_xatlas and not requires_torch and not requires_network"
    python -m lathe.cli doctor
    python -m lathe.cli check examples/courier_drone.lth

ci-contract-golden:
    python -m pytest -q -m "contract or golden" tests/contract tests/golden

ci-property:
    python -m pytest -q -m property tests/property

ci-coverage:
    python -m pytest --cov=lathe --cov-report=xml --cov-report=term

ci-examples-check:
    #!/usr/bin/env bash
    set -e
    FAILED=0
    for f in examples/*.lth examples/api/*.lth examples/corpus/*.lth; do
        [ -e "$f" ] || continue
        echo "::group::check $f"
        if ! python -m lathe.cli check "$f"; then
            echo "::error file=$f::parse/check failed"
            FAILED=1
        fi
        echo "::endgroup::"
    done
    exit $FAILED

ci-corpus-pytest:
    python -m pytest -q tests/unit/test_example_corpus.py

clean-clone-readme: deps-check
    #!/usr/bin/env bash
    set -euo pipefail
    bash scripts/bootstrap_local.sh --dev --export
    bash scripts/lathe_smoke.sh

devcontainer-validate:
    #!/usr/bin/env bash
    set -euo pipefail
    python - <<'PY'
    import json
    from pathlib import Path

    config = json.loads(Path(".devcontainer/devcontainer.json").read_text(encoding="utf-8"))
    if "build" in config:
        raise SystemExit("devcontainer must not point at the Blender Dockerfile unless that image is buildable")
    if "blender" in config.get("name", "").lower():
        raise SystemExit("devcontainer name must not claim Blender support")
    if config.get("containerEnv", {}).get("LATHE_BLENDER_PATH"):
        raise SystemExit("devcontainer must not set LATHE_BLENDER_PATH without installing Blender")
    expected_post_create = "bash scripts/bootstrap_local.sh --dev --export"
    if config.get("postCreateCommand") != expected_post_create:
        raise SystemExit(f"postCreateCommand must match README bootstrap: {expected_post_create}")
    PY

ci: lint-required ci-fast-test ci-contract-golden ci-property devcontainer-validate
