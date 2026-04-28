from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_fast_ci_matrix_covers_supported_operating_systems_and_python_versions() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    fast_test = workflow["jobs"]["fast-test"]
    matrix = fast_test["strategy"]["matrix"]

    assert fast_test["runs-on"] == "${{ matrix.os }}"
    assert set(matrix["os"]) == {"ubuntu-latest", "windows-latest", "macos-latest"}
    assert set(matrix["python-version"]) == {"3.11", "3.12"}


def test_cross_platform_ci_runs_real_project_smoke_checks_without_soft_failures() -> None:
    workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "continue-on-error" not in workflow_text
    assert "python -m pytest -q" in workflow_text
    assert "tests/unit/test_sandbox_blender.py" in workflow_text
    assert "tests/unit/test_subproc_failure_modes.py" in workflow_text
    assert "python -m lathe.cli doctor" in workflow_text
    assert "python -m lathe.cli check examples/courier_drone.lth" in workflow_text
