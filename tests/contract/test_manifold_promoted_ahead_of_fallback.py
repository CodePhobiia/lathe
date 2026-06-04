"""Contract test: Manifold is promoted ahead of the reference fallback.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 1 and §5.4 acceptance:

> Manifold promoted ahead of fallback where primitive coverage is
> sufficient. Capability negotiation drives the choice, not family
> name.
>
> ``manifold_v1`` chosen ahead of fallback whenever capability
> resolution permits. A test fixture proves this for at least 5
> distinct primitive sets.

This test exercises five structurally-distinct ShapeIR primitive sets
through ``execute_shape_ir_boolean_program`` and asserts each run
records ``kernel_program_kernel = "lathe.geometry.manifold_v1"``. The
chosen kernel comes from ``resolve_geometry_kernel()`` with no
runtime config and no env override — i.e., the default path. If
manifold3d is not importable in the current environment the test
skips with an explicit reason.

The trace-level evidence — ``details["kernel_program_kernel"]`` —
proves capability negotiation, not family name, drove the choice.
None of the five fixture ShapeIRs declare a hero-family identity in
ways that would route them through a recipe gate.
"""

from __future__ import annotations

import pytest
from lathe.adapters.manifold_kernel import manifold_available
from lathe.geometry import resolve_geometry_kernel
from lathe.geometry.kernel import MANIFOLD_KERNEL_ID
from lathe.geometry.shape_ir_lowering import execute_shape_ir_boolean_program
from lathe.shape_ir import ShapeIR, ShapePrimitive


def _ir(asset_name: str, primitives: list[ShapePrimitive], used: list[str]) -> ShapeIR:
    """Build a minimal ShapeIR wrapping the given primitive list."""
    return ShapeIR(
        asset_name=asset_name,
        family="manifold_promote_probe",
        blueprint_id=asset_name,
        symmetry_axis=None,
        units="cm",
        primitives=primitives,
        regions=[],
        primitives_used=used,
        part_graph=[],
        signature={},
    )


# Five structurally-distinct primitive sets. Each set exercises a
# different mix of primitive types and/or blend modes so the test
# proves Manifold is chosen across breadth, not for one accidental
# happy path.
_FIVE_PRIMITIVE_SETS: tuple[tuple[str, ShapeIR], ...] = (
    (
        "single_box",
        _ir(
            "single_box",
            [
                ShapePrimitive(
                    primitive_type="box",
                    part="body",
                    center=(0.0, 0.0, 0.0),
                    extents=(10.0, 10.0, 10.0),
                ),
            ],
            ["box"],
        ),
    ),
    (
        "box_with_subtracted_cylinder",
        _ir(
            "box_with_subtracted_cylinder",
            [
                ShapePrimitive(
                    primitive_type="box",
                    part="body",
                    center=(0.0, 0.0, 0.0),
                    extents=(10.0, 10.0, 10.0),
                ),
                ShapePrimitive(
                    primitive_type="cylinder",
                    part="bore",
                    center=(0.0, 0.0, 0.0),
                    radius=2.0,
                    height=12.0,
                    axis="z",
                    sections=24,
                    blend_mode="subtract",
                ),
            ],
            ["box", "cylinder"],
        ),
    ),
    (
        "cylinder_plus_sphere_union",
        _ir(
            "cylinder_plus_sphere_union",
            [
                ShapePrimitive(
                    primitive_type="cylinder",
                    part="shaft",
                    center=(0.0, 0.0, 0.0),
                    radius=2.0,
                    height=8.0,
                    axis="z",
                    sections=24,
                ),
                ShapePrimitive(
                    primitive_type="sphere",
                    part="cap",
                    center=(0.0, 0.0, 4.0),
                    radius=3.0,
                    sections=24,
                ),
            ],
            ["cylinder", "sphere"],
        ),
    ),
    (
        "box_intersect_sphere",
        _ir(
            "box_intersect_sphere",
            [
                ShapePrimitive(
                    primitive_type="box",
                    part="bounds",
                    center=(0.0, 0.0, 0.0),
                    extents=(10.0, 10.0, 10.0),
                    blend_mode="intersect",
                ),
                ShapePrimitive(
                    primitive_type="sphere",
                    part="ball",
                    center=(0.0, 0.0, 0.0),
                    radius=6.0,
                    sections=24,
                    blend_mode="intersect",
                ),
            ],
            ["box", "sphere"],
        ),
    ),
    (
        "compound_box_cylinder_subtract_sphere",
        _ir(
            "compound_box_cylinder_subtract_sphere",
            [
                ShapePrimitive(
                    primitive_type="box",
                    part="frame",
                    center=(0.0, 0.0, 0.0),
                    extents=(12.0, 8.0, 4.0),
                ),
                ShapePrimitive(
                    primitive_type="cylinder",
                    part="rib",
                    center=(0.0, 0.0, 0.0),
                    radius=1.5,
                    height=4.5,
                    axis="z",
                    sections=24,
                ),
                ShapePrimitive(
                    primitive_type="sphere",
                    part="indent",
                    center=(0.0, 0.0, 0.0),
                    radius=2.5,
                    sections=24,
                    blend_mode="subtract",
                ),
            ],
            ["box", "cylinder", "sphere"],
        ),
    ),
)


@pytest.mark.skipif(
    not manifold_available(),
    reason="manifold3d not importable; resolve_geometry_kernel will not select Manifold",
)
@pytest.mark.parametrize(
    "fixture_id, shape_ir",
    _FIVE_PRIMITIVE_SETS,
    ids=[case[0] for case in _FIVE_PRIMITIVE_SETS],
)
def test_manifold_selected_for_distinct_primitive_set(
    fixture_id: str,
    shape_ir: ShapeIR,
) -> None:
    """Manifold runs the program for each of 5 distinct primitive sets.

    The resolver is called with no runtime_config and no env override.
    The boolean program executes, and the resulting trace records
    ``kernel_program_kernel = MANIFOLD_KERNEL_ID``.
    """
    kernel = resolve_geometry_kernel()
    assert kernel.name == MANIFOLD_KERNEL_ID, (
        f"resolver returned {kernel.name!r} but manifold3d is importable; "
        "Manifold must be promoted ahead of the reference fallback."
    )

    result = execute_shape_ir_boolean_program(kernel, shape_ir)

    actual_kernel = result.details.get("kernel_program_kernel")
    assert actual_kernel == MANIFOLD_KERNEL_ID, (
        f"primitive set {fixture_id!r} executed via "
        f"kernel_program_kernel={actual_kernel!r} but expected "
        f"{MANIFOLD_KERNEL_ID!r}. Capability resolution must route to "
        "Manifold whenever its capabilities are sufficient."
    )

    # Trace must show the program actually produced a mesh — empty mesh
    # would mean Manifold "ran" but did not execute anything meaningful.
    assert len(result.mesh.faces) > 0, (
        f"primitive set {fixture_id!r} produced an empty mesh; "
        "kernel selection cannot be trusted without geometric output."
    )
    assert result.details.get("kernel_program_emitted_watertight") is True, (
        f"primitive set {fixture_id!r} produced a non-watertight mesh; "
        "Manifold should yield watertight output for valid CSG inputs."
    )


def test_five_primitive_sets_pinned() -> None:
    """Pin the fixture-set size so reductions don't silently weaken the test.

    Plan v2 §5.4 requires proof across **at least 5** distinct primitive
    sets. This pin makes the count regression-visible.
    """
    assert len(_FIVE_PRIMITIVE_SETS) >= 5, (
        f"Manifold-promotion fixture has {len(_FIVE_PRIMITIVE_SETS)} cases; "
        "plan requires at least 5 distinct primitive sets."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
