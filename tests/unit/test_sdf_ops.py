"""Tests for the Phase 3 third-slice SDF / organic primitive ops.

Covers ``sdf_sphere`` / ``sdf_capsule`` / ``sdf_box`` (single SDFExpr
constructors), ``sdf_smooth_union`` (N-ary IQ smooth-min blend) and
``sdf_extract`` (marching cubes -> ``ShapePrimitive(primitive_type=
"sdf_mesh")``). The SDF / mesh handoff is verified by inspecting the
emitted ``mesh_vertices`` and ``mesh_faces`` directly.
"""

from __future__ import annotations

import pytest

from lathe.f_rep import Capsule, Sphere, SmoothUnion, Translate
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.sdf_test\n"
        "asset sdf_test : hard_surface_prop {\n"
        "  intent { role = \"sdf test\" }\n"
        "  build {\n"
        "    shape {\n"
        "      mode = generate\n"
        "      candidates = 1\n"
        "      mesh_program {\n"
        f"{body}\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    program = parse_text(src)
    return program["assets"][0]["build"]["shape"]["mesh_program"]


def _extract_sphere_only(radius_cm: float = 30.0, resolution: int = 24) -> dict:
    """Helper — build an mesh_program AST that extracts a single sphere.

    Used by tests that only need to verify extraction emits a valid
    sdf_mesh primitive without composing a full creature.
    """
    return _parse_program(
        f"        let s = sdf_sphere(radius: {radius_cm}cm)\n"
        f"        sdf_extract(target: s, resolution: {resolution}, "
        "bounds_min: [-50cm, -50cm, -50cm], bounds_max: [50cm, 50cm, 50cm])"
    )


def test_sdf_sphere_constructs_valid_sdf_expr() -> None:
    # Drive the constructor directly so we can probe the underlying SDF.
    from lathe.mesh_program import _eval_sdf_sphere_call

    expr = _eval_sdf_sphere_call(
        [{"name": "radius", "value": {"type": "unit", "value": 30, "unit": "cm"}}],
        part="body",
        where="t",
    )
    assert isinstance(expr, Sphere)
    assert expr.radius == pytest.approx(30.0)
    # Distance at origin should equal -radius (interior).
    assert expr.distance([0.0, 0.0, 0.0]) == pytest.approx(-30.0)
    # Distance at (radius, 0, 0) should be 0 (on surface).
    assert expr.distance([30.0, 0.0, 0.0]) == pytest.approx(0.0, abs=1e-9)


def test_sdf_capsule_constructs_valid_sdf_expr() -> None:
    from lathe.mesh_program import _eval_sdf_capsule_call

    expr = _eval_sdf_capsule_call(
        [
            {"name": "half_height", "value": {"type": "unit", "value": 50, "unit": "cm"}},
            {"name": "radius", "value": {"type": "unit", "value": 30, "unit": "cm"}},
        ],
        part="body",
        where="t",
    )
    assert isinstance(expr, Capsule)
    assert expr.half_height == pytest.approx(50.0)
    assert expr.radius == pytest.approx(30.0)


def test_sdf_smooth_union_blends_pairs() -> None:
    # k > 0 should produce a smaller distance than the hard min when
    # the two SDF surfaces are within k of each other (the IQ blend
    # region). Sample a point equidistant from two unit spheres.
    from lathe.mesh_program import _apply_sdf_smooth_union, _Value

    bindings = {
        "a": _Value(kind="sdf", sdf_expr=Sphere(radius=10.0)),
        "b": _Value(
            kind="sdf",
            sdf_expr=Translate(expr=Sphere(radius=10.0), offset=(15.0, 0.0, 0.0)),
        ),
    }
    primitives: list = []
    blended = _apply_sdf_smooth_union(
        [
            {"name": "targets", "value": ["a", "b"]},
            {"name": "k", "value": {"type": "unit", "value": 5, "unit": "cm"}},
        ],
        bindings,
        primitives=primitives,
        part="body",
        where="t",
    )
    assert blended.kind == "sdf"
    assert isinstance(blended.sdf_expr, SmoothUnion)
    # At the midpoint, the blended distance should be at most the hard
    # min of the two component SDFs (smooth-min is <= min by design).
    midpoint = [7.5, 0.0, 0.0]
    hard_min = min(
        bindings["a"].sdf_expr.distance(midpoint),
        bindings["b"].sdf_expr.distance(midpoint),
    )
    soft = blended.sdf_expr.distance(midpoint)
    assert soft <= hard_min + 1e-9


def test_sdf_extract_emits_sdf_mesh_primitive() -> None:
    primitives = lower_mesh_program(_extract_sphere_only(radius_cm=30.0, resolution=24))
    assert len(primitives) == 1
    p = primitives[0]
    assert p.primitive_type == "sdf_mesh"
    assert p.mesh_vertices is not None and len(p.mesh_vertices) > 0
    assert p.mesh_faces is not None and len(p.mesh_faces) > 0
    # Each face is a triangle.
    assert all(len(f) == 3 for f in p.mesh_faces)
    # Each vertex is 3D.
    assert all(len(v) == 3 for v in p.mesh_vertices)
    assert "sdf" in p.tags
    assert "sdf_mesh" in p.tags
    # Approximate sphere extent: bounding box should be roughly +/- 30cm
    # on every axis (within marching-cubes voxel slop).
    xs = [v[0] for v in p.mesh_vertices]
    ys = [v[1] for v in p.mesh_vertices]
    zs = [v[2] for v in p.mesh_vertices]
    for coords in (xs, ys, zs):
        assert max(coords) == pytest.approx(30.0, abs=5.0)
        assert min(coords) == pytest.approx(-30.0, abs=5.0)


def test_sdf_translate_chains_into_translate_node() -> None:
    # ``.translate([...])`` on an SDF binding should wrap the expr in
    # an F-Rep Translate, NOT mutate a ShapePrimitive (which would only
    # happen for kind="primitive" bindings).
    mp = _parse_program(
        "        let head = sdf_sphere(radius: 20cm).translate([10cm, 60cm, 0cm])\n"
        "        sdf_extract(target: head, resolution: 16, "
        "bounds_min: [-50cm, 0cm, -50cm], bounds_max: [50cm, 100cm, 50cm])"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 1
    p = primitives[0]
    assert p.primitive_type == "sdf_mesh"
    # The sphere center should be at (10, 60, 0) — confirm the AABB.
    xs = [v[0] for v in p.mesh_vertices or []]
    ys = [v[1] for v in p.mesh_vertices or []]
    cx = (max(xs) + min(xs)) / 2.0
    cy = (max(ys) + min(ys)) / 2.0
    assert cx == pytest.approx(10.0, abs=5.0)
    assert cy == pytest.approx(60.0, abs=5.0)


def test_sdf_smooth_union_produces_extractable_blob() -> None:
    # Compose body + head and extract — must produce a single
    # connected-blob mesh, not two disconnected spheres. We don't
    # assert connectivity (marching cubes can leave seams), but we do
    # check that the extracted vertex span covers both source positions.
    mp = _parse_program(
        "        let body = sdf_capsule(half_height: 20cm, radius: 15cm)\n"
        "        let head = sdf_sphere(radius: 12cm).translate([0cm, 35cm, 0cm])\n"
        "        let blob = sdf_smooth_union(targets: [body, head], k: 8cm)\n"
        "        sdf_extract(target: blob, resolution: 32, "
        "bounds_min: [-40cm, -40cm, -40cm], bounds_max: [40cm, 60cm, 40cm])"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 1
    p = primitives[0]
    assert p.primitive_type == "sdf_mesh"
    ys = [v[1] for v in p.mesh_vertices or []]
    # Body bottom is around y = -35 (capsule half_height 20 + radius 15);
    # head top is around y = 35 + 12 = 47. The extracted mesh should
    # span roughly that range.
    assert min(ys) <= -25.0
    assert max(ys) >= 35.0


# ---------------------------------------------------------------------------
# Validation rejections — every named knob must reject obviously bad input.
# ---------------------------------------------------------------------------


def test_sdf_sphere_rejects_negative_radius() -> None:
    mp = _parse_program(
        "        let s = sdf_sphere(radius: -5cm)\n"
        "        sdf_extract(target: s, resolution: 16, "
        "bounds_min: [-10cm, -10cm, -10cm], bounds_max: [10cm, 10cm, 10cm])"
    )
    with pytest.raises(MeshProgramError, match="radius must be > 0"):
        lower_mesh_program(mp)


def test_sdf_capsule_rejects_zero_half_height() -> None:
    mp = _parse_program(
        "        let s = sdf_capsule(half_height: 0cm, radius: 10cm)\n"
        "        sdf_extract(target: s, resolution: 16, "
        "bounds_min: [-20cm, -20cm, -20cm], bounds_max: [20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="half_height must be > 0"):
        lower_mesh_program(mp)


def test_sdf_box_rejects_zero_extent_component() -> None:
    mp = _parse_program(
        "        let s = sdf_box(extents: [10cm, 0cm, 10cm])\n"
        "        sdf_extract(target: s, resolution: 16, "
        "bounds_min: [-20cm, -20cm, -20cm], bounds_max: [20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="extent components must be > 0"):
        lower_mesh_program(mp)


def test_sdf_smooth_union_rejects_negative_k() -> None:
    mp = _parse_program(
        "        let a = sdf_sphere(radius: 10cm)\n"
        "        let b = sdf_sphere(radius: 10cm).translate([20cm, 0cm, 0cm])\n"
        "        let blob = sdf_smooth_union(targets: [a, b], k: -1cm)\n"
        "        sdf_extract(target: blob, resolution: 16, "
        "bounds_min: [-30cm, -30cm, -30cm], bounds_max: [30cm, 30cm, 30cm])"
    )
    with pytest.raises(MeshProgramError, match="k must be >= 0"):
        lower_mesh_program(mp)


def test_sdf_extract_rejects_too_low_resolution() -> None:
    mp = _parse_program(
        "        let s = sdf_sphere(radius: 10cm)\n"
        "        sdf_extract(target: s, resolution: 4, "
        "bounds_min: [-20cm, -20cm, -20cm], bounds_max: [20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="resolution must be >= 8"):
        lower_mesh_program(mp)


def test_sdf_extract_rejects_inverted_bounds() -> None:
    mp = _parse_program(
        "        let s = sdf_sphere(radius: 10cm)\n"
        "        sdf_extract(target: s, resolution: 16, "
        "bounds_min: [20cm, -20cm, -20cm], bounds_max: [-20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="bounds_max"):
        lower_mesh_program(mp)


def test_sdf_extract_rejects_unknown_target() -> None:
    mp = _parse_program(
        "        let s = sdf_sphere(radius: 10cm)\n"
        "        sdf_extract(target: nope, resolution: 16, "
        "bounds_min: [-20cm, -20cm, -20cm], bounds_max: [20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="target 'nope' is unknown"):
        lower_mesh_program(mp)


def test_sdf_extract_rejects_non_sdf_target() -> None:
    # Targeting a regular ShapePrimitive (e.g. box) for sdf_extract is
    # an authoring error — only kind="sdf" bindings are valid targets.
    mp = _parse_program(
        "        let cube = box(extents: [10cm, 10cm, 10cm])\n"
        "        sdf_extract(target: cube, resolution: 16, "
        "bounds_min: [-20cm, -20cm, -20cm], bounds_max: [20cm, 20cm, 20cm])"
    )
    with pytest.raises(MeshProgramError, match="expected an SDF reference"):
        lower_mesh_program(mp)
