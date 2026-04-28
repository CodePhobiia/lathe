from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TYPECHECK_TARGETS = (
    "lathe/errors.py",
    "lathe/assembly_ir.py",
    "lathe/feature_ir.py",
    "lathe/fit_ir.py",
    "lathe/kit_ir.py",
    "lathe/materials.py",
    "lathe/mesh_ir.py",
    "lathe/proposals.py",
    "lathe/ref.py",
    "lathe/reference_ir.py",
    "lathe/reuse_ir.py",
    "lathe/shape_ir.py",
    "lathe/solid_ir.py",
    "lathe/stages/budgets.py",
    "lathe/stages/lod.py",
    "lathe/surface_ir.py",
    "lathe/texture_control_pack.py",
    "lathe/transfer_ir.py",
    "lathe/validators/geometry_integrity.py",
    "lathe/validators/semantic_quality.py",
    "lathe/validators/surface_quality.py",
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_pre_commit_wires_format_lint_and_type_gates() -> None:
    config = _read(".pre-commit-config.yaml")

    assert "- id: ruff" in config
    assert "- id: ruff-format" in config
    assert "- id: mypy-typed-surface" in config
    assert "python -m mypy --follow-imports=silent" in config
    assert "language: system" in config
    assert "pass_filenames: false" in config
    for target in TYPECHECK_TARGETS:
        assert target in config


def test_lint_workflow_enforces_format_lint_and_type_gates() -> None:
    workflow = _read(".github/workflows/lint.yml")

    assert "ruff check ." in workflow
    assert "pre-commit run ruff-format" in workflow
    assert "mypy typed surface" in workflow
    assert "mypy" in workflow
    assert "--follow-imports=silent" in workflow
    assert "continue-on-error" not in workflow
    for target in TYPECHECK_TARGETS:
        assert target in workflow
