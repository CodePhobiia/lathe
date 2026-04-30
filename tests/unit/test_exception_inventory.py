from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("lathe", "scripts")
BROAD_EXCEPTION_ALLOWLIST = {
    "lathe/backends.py:624",
    "lathe/checker/experimental.py:384",
    "lathe/cli/build_cmd.py:220",
    "lathe/core/stages/package.py:148",
    "lathe/core/stages/package.py:389",
    "lathe/doctor.py:400",
    "lathe/executor.py:216",
    "lathe/executor.py:231",
    "lathe/repair_loop.py:275",
    "lathe/scaffold_compiler.py:110",
    "lathe/scaffold_compiler.py:136",
    "lathe/scaffold_compiler.py:152",
    "lathe/subproc.py:208",
    "scripts/bench_geometry_kernel.py:133",
    "scripts/bench_geometry_kernel.py:152",
    "scripts/bench_geometry_kernel.py:272",
}
PASS_ALLOWLIST = {
    "lathe/cache_paths.py:37",
    "lathe/cli/fmt_cmd.py:73",
    "lathe/core/common.py:58",
    "lathe/core/common.py:102",
    "lathe/core/geometry.py:49",
    "lathe/parser/imports.py:66",
    "lathe/publish/__init__.py:366",
    "lathe/selector_manifest.py:89",
    "lathe/validators/composition.py:127",
    "lathe/validators/composition.py:133",
    "lathe/validators/geometry_integrity.py:267",
    "lathe/validators/urdf_validation.py:205",
}


def _source_files() -> list[Path]:
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        paths.extend(path for path in (REPO_ROOT / root).rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(paths)


def _exception_names(node: ast.ExceptHandler) -> set[str]:
    if node.type is None:
        return {"bare"}
    if isinstance(node.type, ast.Name):
        return {node.type.id}
    if isinstance(node.type, ast.Attribute):
        return {node.type.attr}
    if isinstance(node.type, ast.Tuple):
        names: set[str] = set()
        for item in node.type.elts:
            if isinstance(item, ast.Name):
                names.add(item.id)
            elif isinstance(item, ast.Attribute):
                names.add(item.attr)
        return names
    return set()


def test_broad_exception_handlers_are_tracked() -> None:
    observed: set[str] = set()
    for path in _source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                names = _exception_names(node)
                if names & {"bare", "Exception", "BaseException"}:
                    observed.add(f"{rel}:{node.lineno}")

    assert observed == BROAD_EXCEPTION_ALLOWLIST


def test_noop_pass_nodes_are_tracked() -> None:
    observed: set[str] = set()
    for path in _source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                observed.add(f"{rel}:{node.lineno}")

    assert observed == PASS_ALLOWLIST
