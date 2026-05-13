"""Contract test: every KernelProgram manifest emits a uniform field set.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 3:

> Backend chain telemetry consistent across all executors:
> ``attempted_backend``, ``actual_backend``, ``fallback_reason``,
> ``unsupported_primitives``, ``capability_diagnostics``. Trace
> fields uniform.

Backend chain telemetry is populated by the per-op executors at run
time, but the structural foundation is the pre-execution **manifest**
produced by each ``build_*_program_manifest`` builder. Every
manifest must carry the canonical field set so the executor has the
same shape to fill in.

This test calls every ``build_*_program_manifest`` builder with
minimal stub operands and asserts the returned manifest contains the
required keys. Adding a new builder without the canonical fields
fails the test; mutating a field name in one builder without the
others fails the test.

The runtime telemetry assertion (every executor emits the
``attempted_backend`` / ``actual_backend`` / ``fallback_reason``
fields at execution time) is its own follow-up test that runs a
real kernel; this manifest-shape test is the fast pre-runtime gate.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from lathe.geometry.kernel_program import (
    KernelOperand,
    build_boolean_program_manifest,
    build_carve_program_manifest,
    build_component_assembly_program_manifest,
    build_deform_program_manifest,
    build_hull_program_manifest,
    build_import_program_manifest,
    build_instances_program_manifest,
    build_minkowski_program_manifest,
    build_polyextrude_program_manifest,
    build_profile_path_program_manifest,
    build_refine_program_manifest,
    build_sdf_field_program_manifest,
    build_terrain_field_program_manifest,
    build_transform_program_manifest,
)

_CANONICAL_MANIFEST_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "version",
        "program_kind",
        "route",
        "backend",
        "operation_count",
        "kernel_call_count",
        "operation_limit",
        "required_capabilities",
        "operand_count",
        "operands",
        "semantic_operation_record_count",
        "semantic_operation_counts",
        "semantic_operation_records",
        "diagnostics",
    }
)


def _stub_operand(operand_id: str = "stub_a") -> KernelOperand:
    """Build a stub KernelOperand with a non-None handle for manifest tests."""
    return KernelOperand(
        operand_id=operand_id,
        handle=object(),  # opaque non-None handle
        source_mesh=None,
        blend_mode="union",
        part="stub_part",
        primitive_type="box",
    )


# Each entry: (program_kind, builder, builder-invocation-callable).
# Builders have differing arities — boolean takes a list, transform
# takes a single operand, instances takes (operand, matrices), etc.
_BUILDER_CASES: tuple[tuple[str, str, Callable[[], dict[str, Any]]], ...] = (
    (
        "boolean",
        "build_boolean_program_manifest",
        lambda: build_boolean_program_manifest([_stub_operand("a"), _stub_operand("b")]),
    ),
    (
        "hull",
        "build_hull_program_manifest",
        lambda: build_hull_program_manifest([_stub_operand("a"), _stub_operand("b")]),
    ),
    (
        "minkowski",
        "build_minkowski_program_manifest",
        lambda: build_minkowski_program_manifest(
            _stub_operand("source"), _stub_operand("structuring")
        ),
    ),
    (
        "transform",
        "build_transform_program_manifest",
        lambda: build_transform_program_manifest(
            _stub_operand("a"),
            matrix=[
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        ),
    ),
    (
        "deform",
        "build_deform_program_manifest",
        lambda: build_deform_program_manifest(
            _stub_operand("a"),
            deform_operation="bend",
            axis="x",
            angle_degrees=30.0,
        ),
    ),
    (
        "refine",
        "build_refine_program_manifest",
        lambda: build_refine_program_manifest(
            _stub_operand("a"),
            refine_operation="subdivide",
            levels=1,
        ),
    ),
    (
        "carve",
        "build_carve_program_manifest",
        lambda: build_carve_program_manifest(
            _stub_operand("a"),
            u_start=0.0,
            u_end=1.0,
            axis="x",
        ),
    ),
    (
        "polyextrude",
        "build_polyextrude_program_manifest",
        lambda: build_polyextrude_program_manifest(
            _stub_operand("a"),
            axis="z",
            distance_cm=5.0,
        ),
    ),
    (
        "component_assembly",
        "build_component_assembly_program_manifest",
        lambda: build_component_assembly_program_manifest(
            [_stub_operand("a"), _stub_operand("b")],
            assembly_kind="union",
        ),
    ),
    (
        "profile_path",
        "build_profile_path_program_manifest",
        lambda: build_profile_path_program_manifest(
            _stub_operand("a"),
        ),
    ),
    (
        "sdf_field",
        "build_sdf_field_program_manifest",
        lambda: build_sdf_field_program_manifest(
            _stub_operand("a"),
        ),
    ),
    (
        "terrain_field",
        "build_terrain_field_program_manifest",
        lambda: build_terrain_field_program_manifest(
            _stub_operand("a"),
        ),
    ),
    (
        "import",
        "build_import_program_manifest",
        lambda: build_import_program_manifest(
            _stub_operand("a"),
        ),
    ),
    (
        "instances",
        "build_instances_program_manifest",
        lambda: build_instances_program_manifest(
            _stub_operand("a"),
            matrices=[
                [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            ],
        ),
    ),
)


@pytest.mark.parametrize(
    "program_kind, builder_name, invoke",
    _BUILDER_CASES,
    ids=[case[0] for case in _BUILDER_CASES],
)
def test_manifest_contains_canonical_keys(
    program_kind: str,
    builder_name: str,
    invoke: Callable[[], dict[str, Any]],
) -> None:
    """Every builder returns a manifest with the canonical field set.

    Missing keys mean an executor would have nothing to fill in for
    that telemetry slot — breaking the backend-chain-telemetry
    uniformity criterion.
    """
    try:
        manifest = invoke()
    except (TypeError, ValueError) as exc:
        pytest.fail(
            f"{builder_name}() raised {type(exc).__name__} with stub inputs: "
            f"{exc}. The minimal-stub call should always produce a manifest "
            "even if some fields end up with empty/default values."
        )
    assert isinstance(manifest, dict), (
        f"{builder_name}() returned {type(manifest).__name__}, not dict"
    )
    actual_keys = set(manifest.keys())
    missing = _CANONICAL_MANIFEST_KEYS - actual_keys
    if missing:
        pytest.fail(
            f"{builder_name}() manifest missing canonical keys "
            f"{sorted(missing)!r}. "
            f"Present keys: {sorted(actual_keys)!r}. "
            "Every KernelProgram manifest must carry the uniform "
            "telemetry field set so executors can fill in "
            "attempted_backend / actual_backend / fallback_reason "
            "consistently."
        )
    # program_kind in the manifest must match the kind we invoked
    assert manifest["program_kind"] == program_kind, (
        f"{builder_name} reports program_kind={manifest['program_kind']!r} "
        f"but test expected {program_kind!r}"
    )


def test_all_14_manifest_kinds_covered() -> None:
    """Sanity check that this test exercises all 14 program kinds.

    Pin matches the 14 ``execute_*_program`` functions in
    ``lathe/geometry/kernel_program/__init__.py``. Adding a new
    builder requires adding a case to ``_BUILDER_CASES``.
    """
    kinds = {case[0] for case in _BUILDER_CASES}
    expected = {
        "boolean", "hull", "minkowski", "transform", "deform", "refine",
        "carve", "polyextrude", "component_assembly", "profile_path",
        "sdf_field", "terrain_field", "import", "instances",
    }
    assert kinds == expected, (
        f"manifest test cases ({sorted(kinds)}) do not exactly match "
        f"expected program kinds ({sorted(expected)}). Update "
        "_BUILDER_CASES or the expected set."
    )


def test_manifest_canonical_key_set_is_pinned() -> None:
    """The canonical key set is pinned. Adding fields requires intent.

    A new uniform telemetry field landing in every manifest is a
    valid change but must be deliberate — this test prevents accidental
    silent additions. Update both the set and this test when adding.
    """
    assert frozenset({
        "schema",
        "version",
        "program_kind",
        "route",
        "backend",
        "operation_count",
        "kernel_call_count",
        "operation_limit",
        "required_capabilities",
        "operand_count",
        "operands",
        "semantic_operation_record_count",
        "semantic_operation_counts",
        "semantic_operation_records",
        "diagnostics",
    }) == _CANONICAL_MANIFEST_KEYS, "canonical manifest key set drift detected; intentional?"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
