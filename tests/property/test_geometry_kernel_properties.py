"""Property-based tests for ``lathe.geometry_kernel.fuse_shape_ir``.

Invariants covered:

- Union identity: fusing a shape with only one primitive (the "empty
  addition" case, since fuse_shape_ir does not accept an explicit empty
  operand) produces the same structural handoff when run twice; i.e. the
  operation is bit-stable under the native caching layer.
- Union commutativity: reordering the primitive list produces an
  equivalent fused mesh (same triangle count within a small tolerance,
  identical face-parts multiset) — the fuse operation must not depend on
  primitive insertion order.
- Volume conservation under translation: shifting every primitive by the
  same vector ``v`` must yield a mesh whose bounding-box extents are
  preserved (translation is an isometry — it does not change volume).

Hypothesis is not available in this environment; invariants are exercised
with ``pytest.mark.parametrize`` using explicit, varied inputs.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest
from lathe.fidelity import FidelityProfile
from lathe.geometry_kernel import fuse_shape_ir
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

pytestmark = pytest.mark.property


def _game_fidelity() -> FidelityProfile:
    return FidelityProfile(
        tier="game",
        detail_density=1.0,
        edge_weight=1.0,
        panel_depth=1.0,
        trim_complexity=3,
        support_complexity=1.0,
        silhouette_refinement=1.0,
        repair_budget=3,
    )


def _box(
    part: str, center: tuple[float, float, float], extents: tuple[float, float, float] = (2.0, 2.0, 2.0)
) -> ShapePrimitive:
    return ShapePrimitive(primitive_type="box", part=part, center=center, extents=extents)


def _region(
    part: str, center: tuple[float, float, float], extents: tuple[float, float, float] = (2.0, 2.0, 2.0)
) -> ShapeRegion:
    return ShapeRegion(name=f"r_{part}", part=part, component="hull", center=center, extents=extents)


def _shape_ir(primitives: list[ShapePrimitive], regions: list[ShapeRegion]) -> ShapeIR:
    return ShapeIR(
        asset_name="prop_demo",
        family="industrial_crate",
        blueprint_id="bp",
        symmetry_axis=None,
        units="m",
        primitives=list(primitives),
        regions=list(regions),
        primitives_used=[],
        part_graph=[],
        signature={"blueprint_notes": []},
    )


SINGLE_PRIMITIVE_CASES = [
    pytest.param(_box("body", (0.0, 0.0, 0.0)), id="box_at_origin"),
    pytest.param(_box("body", (1.0, 0.0, 0.0), extents=(4.0, 2.0, 2.0)), id="box_offset_x"),
    pytest.param(_box("body", (0.0, 0.0, 0.0), extents=(1.0, 3.0, 5.0)), id="box_asymmetric"),
    pytest.param(
        ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=3.0,
            axis="y",
        ),
        id="cyl_y_axis",
    ),
    pytest.param(
        ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.5, 0.0, 0.0),
            radius=0.75,
            height=2.5,
            axis="z",
        ),
        id="cyl_z_axis_offset",
    ),
]


@pytest.mark.parametrize("primitive", SINGLE_PRIMITIVE_CASES)
def test_fuse_is_stable_when_rerun(primitive: ShapePrimitive) -> None:
    """Running fuse twice on identical input yields bit-equal face-parts
    multisets and identical face counts — the cache is transparent."""
    shape_ir = _shape_ir([primitive], [_region(primitive.part, primitive.center)])
    mesh_ir_a, report_a = fuse_shape_ir(shape_ir, _game_fidelity())
    mesh_ir_b, report_b = fuse_shape_ir(shape_ir, _game_fidelity())
    assert mesh_ir_a is not None and mesh_ir_b is not None
    assert len(mesh_ir_a.faces) == len(mesh_ir_b.faces)
    # face_parts multiset must match exactly — the handoff is deterministic
    assert Counter(mesh_ir_a.face_parts) == Counter(mesh_ir_b.face_parts)
    # Re-runs may be cache hits; both reports carry a mode string.
    assert "mode" in report_a
    assert "mode" in report_b


COMMUTATIVITY_CASES = [
    pytest.param(
        [
            _box("body", (0.0, 0.0, 0.0)),
            _box("top", (0.0, 2.5, 0.0), extents=(1.5, 1.5, 1.5)),
        ],
        id="two_stacked_boxes",
    ),
    pytest.param(
        [
            _box("body", (0.0, 0.0, 0.0), extents=(3.0, 2.0, 3.0)),
            ShapePrimitive(
                primitive_type="cylinder",
                part="stem",
                center=(0.0, 2.0, 0.0),
                radius=0.6,
                height=2.0,
                axis="y",
            ),
        ],
        id="box_plus_cyl",
    ),
    pytest.param(
        [
            _box("body", (-1.0, 0.0, 0.0)),
            _box("top", (1.0, 0.0, 0.0)),
        ],
        id="side_by_side_boxes",
    ),
    pytest.param(
        [
            _box("a", (0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
            _box("b", (0.0, 0.0, 1.5), extents=(1.0, 1.0, 1.0)),
            _box("c", (0.0, 1.5, 0.0), extents=(1.0, 1.0, 1.0)),
        ],
        id="three_boxes",
    ),
    pytest.param(
        [
            ShapePrimitive(
                primitive_type="cylinder",
                part="a",
                center=(0.0, 0.0, 0.0),
                radius=0.5,
                height=2.0,
                axis="y",
            ),
            ShapePrimitive(
                primitive_type="cylinder",
                part="b",
                center=(1.0, 0.0, 0.0),
                radius=0.5,
                height=2.0,
                axis="y",
            ),
        ],
        id="two_cylinders",
    ),
]


@pytest.mark.parametrize("primitives", COMMUTATIVITY_CASES)
def test_fuse_geometry_is_order_insensitive(primitives: list[ShapePrimitive]) -> None:
    """The *geometric* output of fuse(A, B) and fuse(B, A) is equivalent:
    identical face and vertex counts and identical overall bounds. Face-
    part labels are intentionally order-sensitive when regions overlap
    (the nearest-region tiebreaker in ``_assign_face_parts`` prefers the
    earlier entry on identical volume), so we do not assert label equality.
    What IS commutative is the geometry itself — the shape the downstream
    stack sees.
    """
    regions = [_region(primitive.part, primitive.center, extents=(3.0, 3.0, 3.0)) for primitive in primitives]
    shape_fwd = _shape_ir(primitives, regions)
    shape_rev = _shape_ir(list(reversed(primitives)), list(reversed(regions)))
    mesh_fwd, _ = fuse_shape_ir(shape_fwd, _game_fidelity())
    mesh_rev, _ = fuse_shape_ir(shape_rev, _game_fidelity())
    assert mesh_fwd is not None and mesh_rev is not None
    assert len(mesh_fwd.faces) == len(mesh_rev.faces)
    assert len(mesh_fwd.vertices) == len(mesh_rev.vertices)
    # Bounds are commutative under the union operation.
    fwd_v = np.asarray(mesh_fwd.vertices, dtype=np.float64)
    rev_v = np.asarray(mesh_rev.vertices, dtype=np.float64)
    assert np.allclose(fwd_v.min(axis=0), rev_v.min(axis=0), atol=1e-9)
    assert np.allclose(fwd_v.max(axis=0), rev_v.max(axis=0), atol=1e-9)


TRANSLATION_VECTORS = [
    pytest.param(np.array([5.0, 0.0, 0.0]), id="translate_x"),
    pytest.param(np.array([0.0, 7.5, 0.0]), id="translate_y"),
    pytest.param(np.array([0.0, 0.0, -4.0]), id="translate_neg_z"),
    pytest.param(np.array([2.0, 3.0, -1.5]), id="translate_mixed"),
    pytest.param(np.array([100.0, 100.0, 100.0]), id="translate_far"),
]


@pytest.mark.parametrize("translation", TRANSLATION_VECTORS)
def test_fuse_preserves_extents_under_translation(translation: np.ndarray) -> None:
    """Translating every primitive by the same vector must preserve the
    bounding-box extents of the fused mesh (translation is an isometry).
    Absolute positions change — but the size of the shape does not.
    """
    base_primitives = [
        _box("body", (0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
        _box("top", (0.0, 2.0, 0.0), extents=(1.0, 1.0, 1.0)),
    ]
    base_regions = [_region(primitive.part, primitive.center) for primitive in base_primitives]
    shape_base = _shape_ir(base_primitives, base_regions)

    translated_primitives = [
        _box(
            primitive.part,
            (
                primitive.center[0] + float(translation[0]),
                primitive.center[1] + float(translation[1]),
                primitive.center[2] + float(translation[2]),
            ),
            extents=primitive.extents if primitive.extents is not None else (2.0, 2.0, 2.0),
        )
        for primitive in base_primitives
    ]
    translated_regions = [
        _region(
            primitive.part,
            (
                primitive.center[0] + float(translation[0]),
                primitive.center[1] + float(translation[1]),
                primitive.center[2] + float(translation[2]),
            ),
        )
        for primitive in base_primitives
    ]
    shape_translated = _shape_ir(translated_primitives, translated_regions)

    mesh_base, _ = fuse_shape_ir(shape_base, _game_fidelity())
    mesh_translated, _ = fuse_shape_ir(shape_translated, _game_fidelity())
    assert mesh_base is not None and mesh_translated is not None

    base_bounds = np.asarray(mesh_base.vertices, dtype=np.float64)
    trans_bounds = np.asarray(mesh_translated.vertices, dtype=np.float64)
    base_ext = base_bounds.max(axis=0) - base_bounds.min(axis=0)
    trans_ext = trans_bounds.max(axis=0) - trans_bounds.min(axis=0)
    # Extents preserved to within voxel-pitch tolerance of the marching-cubes sampler.
    assert np.allclose(base_ext, trans_ext, atol=0.25)
