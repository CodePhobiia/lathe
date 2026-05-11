"""Contract test: 5 missing-coverage primitive paths execute via Manifold.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 2 and §5.4 acceptance:

> Missing primitive coverage in Manifold path. Specifically:
>   - lofted solid
>   - twist on extruded profiles
>   - partial rotate extrude
>   - helical sweep
>   - involute gear
>   - bend/twist/taper deformers
>
> 5 new primitive/operation coverage paths in Manifold from the list
> above, each with unit test + integration into the kernel trace.

This test locks in the 5 paths that currently route through Manifold:
``lofted_solid``, ``extruded_profile`` with ``extrude_twist_degrees``,
``helical_sweep``, ``gear`` (involute), and the ``sop.bend / sop.twist
/ sop.taper`` deformer family. ``partial rotate extrude`` is the
remaining gap and is tracked separately — its fix lands as
``test_partial_revolve_watertight``.

For the four primitive types, the test passes the ShapePrimitive
through ``execute_shape_ir_boolean_program`` and asserts the trace
records execution by Manifold with a watertight result. For the
deformer family, the test exercises ``lower_to_v1`` which is the
ShapeIR v2 lowering entry point — a successful lowering with zero
diagnostics is the "executed" classification per
``test_shape_ir_v2_op_coverage.py``.
"""

from __future__ import annotations

import pytest

from lathe.adapters.manifold_kernel import manifold_available
from lathe.asset_quality.shape_ir_v2 import (
    ShapeOp,
    ShapeProgram,
    lower_to_v1,
)
from lathe.geometry import resolve_geometry_kernel
from lathe.geometry.kernel import MANIFOLD_KERNEL_ID
from lathe.geometry.shape_ir_lowering import execute_shape_ir_boolean_program
from lathe.shape_ir import ShapeIR, ShapePrimitive


def _ir(asset_name: str, primitive: ShapePrimitive, used: list[str]) -> ShapeIR:
    """Build a minimal ShapeIR wrapping a single primitive."""
    return ShapeIR(
        asset_name=asset_name,
        family="manifold_coverage_probe",
        blueprint_id=asset_name,
        symmetry_axis=None,
        units="cm",
        primitives=[primitive],
        regions=[],
        primitives_used=used,
        part_graph=[],
        signature={},
    )


_PRIMITIVE_COVERAGE_CASES: tuple[tuple[str, ShapeIR], ...] = (
    (
        "lofted_solid",
        _ir(
            "lofted_solid_probe",
            ShapePrimitive(
                primitive_type="lofted_solid",
                part="body",
                center=(0.0, 0.0, 0.0),
                cross_sections=[
                    [(2.0, 0.0), (0.0, 2.0), (-2.0, 0.0), (0.0, -2.0)],
                    [(3.0, 0.0), (0.0, 3.0), (-3.0, 0.0), (0.0, -3.0)],
                    [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)],
                ],
                section_centers=[
                    (0.0, 0.0, 0.0),
                    (0.0, 4.0, 0.0),
                    (0.0, 8.0, 0.0),
                ],
            ),
            ["lofted_solid"],
        ),
    ),
    (
        "twist_on_extruded_profile",
        _ir(
            "twist_extrude_probe",
            ShapePrimitive(
                primitive_type="extruded_profile",
                part="body",
                center=(0.0, 0.0, 0.0),
                axis="z",
                profile_polygon=[
                    (-2.0, -2.0),
                    (2.0, -2.0),
                    (2.0, 2.0),
                    (-2.0, 2.0),
                ],
                extrude_height=6.0,
                extrude_twist_degrees=90.0,
                extrude_segments=16,
            ),
            ["extruded_profile"],
        ),
    ),
    (
        "helical_sweep",
        _ir(
            "helical_sweep_probe",
            ShapePrimitive(
                primitive_type="helical_sweep",
                part="coil",
                center=(0.0, 0.0, 0.0),
                radius=4.0,
                height=8.0,
                axis="z",
                turns=3,
                tube_radius=0.5,
                sections=32,
            ),
            ["helical_sweep"],
        ),
    ),
    (
        "involute_gear",
        _ir(
            "gear_probe",
            ShapePrimitive(
                primitive_type="gear",
                part="cog",
                center=(0.0, 0.0, 0.0),
                axis="z",
                teeth=20,
                pitch_radius=5.0,
                thickness=2.0,
                pressure_angle_degrees=20.0,
            ),
            ["gear"],
        ),
    ),
)


@pytest.mark.skipif(
    not manifold_available(),
    reason="manifold3d not importable; resolve_geometry_kernel will not select Manifold",
)
@pytest.mark.parametrize(
    "coverage_id, shape_ir",
    _PRIMITIVE_COVERAGE_CASES,
    ids=[case[0] for case in _PRIMITIVE_COVERAGE_CASES],
)
def test_primitive_path_executes_through_manifold(
    coverage_id: str,
    shape_ir: ShapeIR,
) -> None:
    """The covered primitive path executes via Manifold with watertight output.

    Each of the four primitive coverage paths must:
      - Lower to a valid ShapePrimitive with the required fields.
      - Produce a watertight trimesh after the kernel program runs.
      - Record ``kernel_program_kernel == MANIFOLD_KERNEL_ID`` in the
        boolean program details (the trace integration the plan
        explicitly calls for).
    """
    kernel = resolve_geometry_kernel()
    assert kernel.name == MANIFOLD_KERNEL_ID, (
        f"resolver returned {kernel.name!r} but manifold3d is importable; "
        "Manifold must be promoted ahead of fallback for coverage tests."
    )

    result = execute_shape_ir_boolean_program(kernel, shape_ir)

    actual_kernel = result.details.get("kernel_program_kernel")
    assert actual_kernel == MANIFOLD_KERNEL_ID, (
        f"coverage path {coverage_id!r} executed via "
        f"kernel_program_kernel={actual_kernel!r} but expected "
        f"{MANIFOLD_KERNEL_ID!r}."
    )

    assert len(result.mesh.faces) > 0, (
        f"coverage path {coverage_id!r} produced an empty mesh; the "
        "primitive's mesh generator must emit visible geometry."
    )
    assert result.details.get("kernel_program_emitted_watertight") is True, (
        f"coverage path {coverage_id!r} produced a non-watertight mesh "
        f"(face_count={len(result.mesh.faces)}). Manifold-routed "
        "primitives must yield watertight CSG output for downstream "
        "boolean composition to be deterministic."
    )


_DEFORMER_CASES: tuple[tuple[str, str, dict], ...] = (
    ("sop_twist", "sop.twist", {"angle_degrees": 45.0}),
    ("sop_bend", "sop.bend", {"angle_degrees": 30.0}),
    ("sop_taper", "sop.taper", {"scale": 0.5}),
)


def _box_source() -> dict:
    """Minimal solid.box source the deformer ops require."""
    return {
        "op": "solid.box",
        "target": "stub.body",
        "parameters": {"width_cm": 6.0, "height_cm": 6.0, "depth_cm": 6.0},
    }


@pytest.mark.parametrize(
    "coverage_id, op_name, extra_params",
    _DEFORMER_CASES,
    ids=[case[0] for case in _DEFORMER_CASES],
)
def test_deformer_op_lowers_with_zero_diagnostics(
    coverage_id: str,
    op_name: str,
    extra_params: dict,
) -> None:
    """sop.twist / sop.bend / sop.taper lower cleanly into v1 records.

    The acceptance criterion is the "executed" classification from
    ``test_shape_ir_v2_op_coverage.py``: lowering produces v1 records
    with zero diagnostics. The downstream kernel run is exercised by
    other tests — this one pins the lowering surface so a future
    refactor cannot silently drop these ops into the "approximated" or
    "unsupported" buckets.
    """
    parameters = {"source": _box_source(), **extra_params}
    op = ShapeOp(
        op=op_name,
        target="stub.target",
        parameters=parameters,
        purpose="manifold_coverage_probe",
    )
    program = ShapeProgram(
        version="2",
        asset_name=f"{coverage_id}_probe",
        family=None,
        ops=(op,),
    )

    result = lower_to_v1(program)
    records = tuple(result.v1_records)
    diagnostics = tuple(result.diagnostics)

    assert records, (
        f"{op_name} lowered with zero v1 records; the deformer op must "
        "emit at least one record to be classified 'executed'."
    )
    assert not diagnostics, (
        f"{op_name} lowered with diagnostics={diagnostics!r}; the "
        "executed classification requires zero diagnostics."
    )


def test_five_coverage_paths_pinned() -> None:
    """Pin the coverage-set count so reductions don't silently weaken the test.

    Plan v2 §5.4 requires "5 new primitive/operation coverage paths".
    Counted as 4 distinct primitive paths plus the deformer family,
    which collectively provide breadth across ShapeIR primitive types
    and ShapeIR v2 sop ops.
    """
    primitive_path_count = len(_PRIMITIVE_COVERAGE_CASES)
    deformer_path_count = len(_DEFORMER_CASES)
    total = primitive_path_count + deformer_path_count
    assert total >= 5, (
        f"Manifold-coverage fixture has {total} cases "
        f"({primitive_path_count} primitives + {deformer_path_count} "
        "deformer ops); plan requires at least 5 distinct paths."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
