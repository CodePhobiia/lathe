"""Architecture / layering contract tests (Plan 03 Phase 3).

Runs the import-linter contracts declared in ``.importlinter``. Skips
cleanly when import-linter is not installed so the core test matrix
can continue to exercise lower-layer contracts on minimal dev
environments.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".importlinter"


def _importlinter_installed() -> bool:
    try:
        import importlinter  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(
    not _importlinter_installed(),
    reason="import-linter not installed (install via `pip install -e .[dev]`)",
)
def test_importlinter_contracts_pass() -> None:
    """All contracts in ``.importlinter`` must be kept.

    This exercises the Plan 03 Phase 3 layering contracts:
    frontend/core/contracts layering, backend-sibling isolation,
    contract-module purity, and provider-adapter isolation.
    """
    assert CONFIG_PATH.exists(), f"missing importlinter config at {CONFIG_PATH}"

    try:
        from importlinter.api import use_cases
    except ImportError:  # pragma: no cover - fall back to the CLI
        import shutil

        lint_imports_bin = shutil.which("lint-imports")
        if lint_imports_bin is None:
            pytest.skip("neither importlinter.api nor the lint-imports CLI is available")
        result = subprocess.run(
            [lint_imports_bin, "--config", str(CONFIG_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"import-linter contracts broken:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        return

    import os

    prev_cwd = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        passed = use_cases.lint_imports(config_filename=str(CONFIG_PATH))
    finally:
        os.chdir(prev_cwd)

    assert passed, (
        "import-linter contracts broken. Run `lint-imports --config .importlinter` "
        "locally to see broken contracts."
    )
