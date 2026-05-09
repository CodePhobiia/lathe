"""Tests for V1.4 §6.x mesh_program scatter / Copy-to-Points ops.

Covers:

* Point-set generators: ``points_grid``, ``points_random``, ``points_circle``.
* Point-set combiner: ``points_combine``.
* The ``scatter(primitive:, points:, jitter:?, seam_group:?)`` op
  itself — one declaration replaces N explicit translates.
* Validation rejections (zero counts, negative jitter, missing args,
  unknown identifiers, kind mismatches, etc.).
"""

from __future__ import annotations

import math

import pytest

from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.scatter_test\n"
        "asset scatter_test : hard_surface_prop {\n"
        "  intent { role = \"scatter test\" }\n"
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


# ---------------------------------------------------------------------------
# Point-set generators
# ---------------------------------------------------------------------------


def test_points_grid_via_scatter_emits_rows_times_cols_copies() -> None:
    mp = _parse_program(
        "let rivet = solid_cylinder(radius: 3mm, height: 4mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [36cm, 26cm], rows: 4, cols: 8)\n"
        "        scatter(primitive: rivet, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 32
    for p in primitives:
        assert p.primitive_type == "cylinder"
        assert "scatter" in p.tags
    centers = {p.center for p in primitives}
    # All copies should land at distinct centers.
    assert len(centers) == 32


def test_points_grid_centered_on_origin() -> None:
    mp = _parse_program(
        "let rivet = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: rivet, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    centers = sorted(p.center for p in primitives)
    # 2x2 grid in [-5, +5] cm on the XY plane (default plane='+z').
    assert centers == [
        (-5.0, -5.0, 0.0),
        (-5.0, 5.0, 0.0),
        (5.0, -5.0, 0.0),
        (5.0, 5.0, 0.0),
    ]


def test_points_grid_single_row_centers_along_one_axis() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [12cm, 8cm], rows: 1, cols: 3)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    centers = sorted(p.center for p in primitives)
    # rows=1 collapses U axis to 0; cols=3 walks V from -4 to +4.
    assert centers == [(0.0, -4.0, 0.0), (0.0, 0.0, 0.0), (0.0, 4.0, 0.0)]


def test_points_random_is_deterministic_for_same_seed() -> None:
    body = (
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_random(count: 6, seed: 42, extents: [20cm, 20cm])\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives_a = lower_mesh_program(_parse_program(body))
    primitives_b = lower_mesh_program(_parse_program(body))
    centers_a = [p.center for p in primitives_a]
    centers_b = [p.center for p in primitives_b]
    assert centers_a == centers_b
    assert len(centers_a) == 6


def test_points_random_changes_with_different_seed() -> None:
    seed_a = (
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_random(count: 6, seed: 1, extents: [20cm, 20cm])\n"
        "        scatter(primitive: m, points: pts)"
    )
    seed_b = (
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_random(count: 6, seed: 999, extents: [20cm, 20cm])\n"
        "        scatter(primitive: m, points: pts)"
    )
    centers_a = [p.center for p in lower_mesh_program(_parse_program(seed_a))]
    centers_b = [p.center for p in lower_mesh_program(_parse_program(seed_b))]
    assert centers_a != centers_b


def test_points_random_3d_extents_uses_z_axis() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_random(count: 50, seed: 5, extents: [10cm, 10cm, 10cm])\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    z_values = [p.center[2] for p in primitives]
    # 50 points in a 10cm Z extent — at least some should be off Z=0.
    assert any(abs(z) > 0.5 for z in z_values)


def test_points_circle_emits_count_points_at_uniform_spacing() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_circle(count: 4, radius: 10cm, axis: \"y\")\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 4
    for p in primitives:
        # Y axis is normal -> XZ plane circle of radius 10
        cx, cy, cz = p.center
        assert abs(cy) < 1e-6
        assert math.isclose(math.hypot(cx, cz), 10.0, abs_tol=1e-6)


def test_points_combine_concatenates_multiple_sources() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let a = points_grid(extents: [6cm, 6cm], rows: 2, cols: 2)\n"
        "        let b = points_circle(count: 3, radius: 4cm, axis: \"z\")\n"
        "        let combined = points_combine([a, b])\n"
        "        scatter(primitive: m, points: combined)"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 7  # 4 grid + 3 circle


# ---------------------------------------------------------------------------
# scatter behaviour
# ---------------------------------------------------------------------------


def test_scatter_translates_each_copy_to_its_point() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    centers = sorted(p.center for p in primitives)
    assert centers == [
        (-2.0, -2.0, 0.0),
        (-2.0, 2.0, 0.0),
        (2.0, -2.0, 0.0),
        (2.0, 2.0, 0.0),
    ]


def test_scatter_preserves_primitive_attributes_on_each_copy() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 5mm, height: 7mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    for p in primitives:
        assert p.primitive_type == "cylinder"
        assert p.radius == pytest.approx(0.5)  # 5mm == 0.5cm
        assert p.height == pytest.approx(0.7)
        assert p.axis == "z"


def test_scatter_with_translated_template_offsets_copies() -> None:
    # The template carries .translate([0, 0, 1cm]) — every copy's center
    # should be the point offset PLUS the template's intrinsic 1cm Z lift.
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "              .translate([0cm, 0cm, 1cm])\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    z_values = {p.center[2] for p in primitives}
    assert z_values == {1.0}


def test_scatter_jitter_is_deterministic() -> None:
    body = (
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts, jitter: 1mm)"
    )
    centers_a = [p.center for p in lower_mesh_program(_parse_program(body))]
    centers_b = [p.center for p in lower_mesh_program(_parse_program(body))]
    assert centers_a == centers_b


def test_scatter_zero_jitter_lands_exactly_on_points() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    centers = sorted(p.center for p in primitives)
    assert centers == [
        (-2.0, -2.0, 0.0),
        (-2.0, 2.0, 0.0),
        (2.0, -2.0, 0.0),
        (2.0, 2.0, 0.0),
    ]


def test_scatter_jitter_offsets_copies_within_bound() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts, jitter: 1mm)"
    )
    primitives = lower_mesh_program(mp)
    # Anchor centers are the 4 corners of [-5, +5] x [-5, +5]. With jitter
    # at 1mm = 0.1cm, every emitted center must be within 0.1cm of its
    # nearest anchor on each axis (deterministic so the bound is tight).
    anchors = [(-5.0, -5.0, 0.0), (-5.0, 5.0, 0.0), (5.0, -5.0, 0.0), (5.0, 5.0, 0.0)]
    for p in primitives:
        nearest = min(
            anchors,
            key=lambda a: sum((p.center[i] - a[i]) ** 2 for i in range(3)),
        )
        for axis in range(3):
            assert abs(p.center[axis] - nearest[axis]) <= 0.1 + 1e-9


def test_scatter_tags_each_copy_with_source_index() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts)"
    )
    primitives = lower_mesh_program(mp)
    indices = sorted(
        int(t.split(":")[2])
        for p in primitives
        for t in p.tags
        if t.startswith("scatter:m:")
    )
    assert indices == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_points_grid_rejects_zero_rows() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 0, cols: 4)\n"
        "        scatter(primitive: m, points: pts)"
    )
    with pytest.raises(MeshProgramError, match="rows/cols must each be >= 1"):
        lower_mesh_program(mp)


def test_points_grid_rejects_unknown_plane() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2, plane: \"z\")\n"
        "        scatter(primitive: m, points: pts)"
    )
    with pytest.raises(MeshProgramError, match="plane"):
        lower_mesh_program(mp)


def test_points_random_rejects_zero_count() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_random(count: 0, seed: 1, extents: [10cm, 10cm])\n"
        "        scatter(primitive: m, points: pts)"
    )
    with pytest.raises(MeshProgramError, match="count must be >= 1"):
        lower_mesh_program(mp)


def test_points_circle_rejects_negative_radius() -> None:
    # Use a literal that the parser accepts but the validator rejects.
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_circle(count: 4, radius: -5cm, axis: \"y\")\n"
        "        scatter(primitive: m, points: pts)"
    )
    with pytest.raises(MeshProgramError, match="radius must be > 0"):
        lower_mesh_program(mp)


def test_scatter_rejects_negative_jitter() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: m, points: pts, jitter: -1mm)"
    )
    with pytest.raises(MeshProgramError, match="jitter must be >= 0"):
        lower_mesh_program(mp)


def test_scatter_rejects_unknown_primitive_ident() -> None:
    mp = _parse_program(
        "let pts = points_grid(extents: [10cm, 10cm], rows: 2, cols: 2)\n"
        "        scatter(primitive: ghost, points: pts)"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier 'ghost'"):
        lower_mesh_program(mp)


def test_scatter_rejects_non_point_set_for_points_arg() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let other = solid_panel(extents: [10cm, 10cm, 1cm])\n"
        "        scatter(primitive: m, points: other)"
    )
    with pytest.raises(MeshProgramError, match="must reference a point_set"):
        lower_mesh_program(mp)


def test_points_combine_rejects_unknown_identifier() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let a = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        let combined = points_combine([a, ghost])\n"
        "        scatter(primitive: m, points: combined)"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier 'ghost'"):
        lower_mesh_program(mp)


def test_points_combine_rejects_non_point_set() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let p = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        let combined = points_combine([p, m])\n"
        "        scatter(primitive: m, points: combined)"
    )
    with pytest.raises(MeshProgramError, match="must reference a point_set"):
        lower_mesh_program(mp)


def test_scatter_multi_source_via_points_combine_emits_union() -> None:
    mp = _parse_program(
        "let m = solid_cylinder(radius: 1mm, height: 1mm, axis: \"z\")\n"
        "        let a = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        let b = points_circle(count: 5, radius: 8cm, axis: \"z\")\n"
        "        let combined = points_combine([a, b])\n"
        "        scatter(primitive: m, points: combined)"
    )
    primitives = lower_mesh_program(mp)
    assert len(primitives) == 9  # 4 grid + 5 circle
