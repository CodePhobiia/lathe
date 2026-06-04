"""Contract test: kernel_program public surface is preserved across extractions.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.4 acceptance:

> Public surface preserved (every symbol in ``lathe.geometry`` package
> ``__init__`` still accessible by the same name from the same import
> path).

This test is the safety net for the per-op decomposition tasks
(§5.3): every extraction that moves a builder/executor/op-count from
``kernel_program/__init__.py`` into a per-op module
(``kernel_program/boolean.py``, ``hull.py``, etc.) must preserve the
public import path. The test pins the documented public surface in
two places:

  1. Every symbol must be importable from ``lathe.geometry.kernel_program``.
  2. Every symbol must be importable from ``lathe.geometry``.
  3. The symbol obtained from each path must be the *same object*
     (identity check), so a future re-export cannot drift apart.

Adding a symbol is a deliberate change: update both ``_PUBLIC_SYMBOLS``
here and ``lathe/geometry/__init__.py`` together. The test forces
that paired update.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

# Canonical public surface of ``lathe.geometry.kernel_program``. Listed
# in groups matching the §5.3 decomposition layout — when boolean.py,
# hull.py, etc. land, the symbol stays at the same import path so each
# extraction is invisible to callers.
_PUBLIC_SYMBOLS: tuple[str, ...] = (
    # Versioning constant
    "KERNEL_PROGRAM_VERSION",
    # Core dataclasses + exceptions
    "KernelOperand",
    "KernelProgramCapabilityError",
    "KernelProgramResult",
    # Manifest builders (one per program kind)
    "build_boolean_program_manifest",
    "build_carve_program_manifest",
    "build_component_assembly_program_manifest",
    "build_deform_program_manifest",
    "build_hull_program_manifest",
    "build_import_program_manifest",
    "build_instances_program_manifest",
    "build_minkowski_program_manifest",
    "build_polyextrude_program_manifest",
    "build_profile_path_program_manifest",
    "build_refine_program_manifest",
    "build_sdf_field_program_manifest",
    "build_terrain_field_program_manifest",
    "build_transform_program_manifest",
    # Operation-count helpers (one per program kind)
    "boolean_kernel_call_count",
    "boolean_operation_count",
    "carve_operation_count",
    "component_assembly_operation_count",
    "deform_operation_count",
    "hull_operation_count",
    "import_operation_count",
    "instances_operation_count",
    "minkowski_operation_count",
    "polyextrude_operation_count",
    "profile_path_operation_count",
    "refine_operation_count",
    "sdf_field_operation_count",
    "terrain_field_operation_count",
    "transform_operation_count",
    # Executors (one per program kind)
    "execute_boolean_program",
    "execute_carve_program",
    "execute_component_assembly_program",
    "execute_deform_program",
    "execute_hull_program",
    "execute_import_program",
    "execute_instances_program",
    "execute_minkowski_program",
    "execute_polyextrude_program",
    "execute_profile_path_program",
    "execute_refine_program",
    "execute_sdf_field_program",
    "execute_terrain_field_program",
    "execute_transform_program",
    # Semantic-metadata helper consumed by downstream shape_ir_lowering
    "semantic_metadata_from_primitive",
)


@pytest.fixture(scope="module")
def kernel_program_module() -> Any:
    """Fresh import of lathe.geometry.kernel_program for symbol-table inspection."""
    return importlib.import_module("lathe.geometry.kernel_program")


@pytest.fixture(scope="module")
def geometry_module() -> Any:
    """Fresh import of the parent lathe.geometry package."""
    return importlib.import_module("lathe.geometry")


@pytest.mark.parametrize("symbol_name", _PUBLIC_SYMBOLS)
def test_symbol_importable_from_kernel_program(
    kernel_program_module: Any,
    symbol_name: str,
) -> None:
    """Every documented public symbol resolves from the package root."""
    assert hasattr(kernel_program_module, symbol_name), (
        f"lathe.geometry.kernel_program.{symbol_name} is missing — "
        "an extraction lost the re-export."
    )
    symbol = getattr(kernel_program_module, symbol_name)
    assert symbol is not None, (
        f"lathe.geometry.kernel_program.{symbol_name} is None — "
        "the re-export resolved to a placeholder."
    )


@pytest.mark.parametrize("symbol_name", _PUBLIC_SYMBOLS)
def test_symbol_importable_from_geometry_parent(
    geometry_module: Any,
    symbol_name: str,
) -> None:
    """Every documented public symbol also resolves from lathe.geometry directly."""
    assert hasattr(geometry_module, symbol_name), (
        f"lathe.geometry.{symbol_name} is missing — the parent package "
        "must re-export every kernel_program public symbol."
    )


@pytest.mark.parametrize("symbol_name", _PUBLIC_SYMBOLS)
def test_symbol_identity_matches_across_paths(
    kernel_program_module: Any,
    geometry_module: Any,
    symbol_name: str,
) -> None:
    """The same object resolves from both import paths.

    Catches accidental shims where ``lathe.geometry.X`` and
    ``lathe.geometry.kernel_program.X`` end up as two different
    function objects after a refactor — identity is the only test
    that catches that drift.
    """
    from_kp = getattr(kernel_program_module, symbol_name)
    from_geo = getattr(geometry_module, symbol_name)
    assert from_kp is from_geo, (
        f"identity drift: lathe.geometry.{symbol_name} and "
        f"lathe.geometry.kernel_program.{symbol_name} resolve to "
        "different objects. A re-export must be a direct reference."
    )


def test_public_symbol_count_pinned() -> None:
    """Pin the public symbol count so additions are deliberate.

    A new symbol landing in the public surface must update this list
    and the parent ``lathe.geometry.__init__`` together. The pin
    catches accidental additions/removals from the public API in code
    review.
    """
    assert len(_PUBLIC_SYMBOLS) == 48, (
        f"public symbol count drift: pinned 48, found {len(_PUBLIC_SYMBOLS)}. "
        "If this change is intentional, update the pin and the parent "
        "lathe.geometry.__init__ together."
    )


def test_geometry_module_all_lists_every_public_kernel_program_symbol(
    geometry_module: Any,
) -> None:
    """Every documented symbol appears in lathe.geometry.__all__.

    Without this, ``from lathe.geometry import *`` would silently miss
    symbols a downstream caller relies on.
    """
    geo_all = set(getattr(geometry_module, "__all__", ()))
    missing = sorted(set(_PUBLIC_SYMBOLS) - geo_all)
    assert not missing, (
        f"lathe.geometry.__all__ missing kernel_program symbols: "
        f"{missing!r}. Every public symbol must be in __all__ so "
        "star-imports remain stable across extractions."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
