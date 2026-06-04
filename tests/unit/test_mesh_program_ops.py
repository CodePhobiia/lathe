"""Tests for V1.4 §5.7 mesh_program ops: 8-op first wave from ShapeIR v2.

Covers:

* 5 solid constructors that wrap existing v1 lowerers in shape_ir_v2.py
  (``solid_panel``, ``solid_rail``, ``solid_prism``, ``solid_cylinder``,
  ``solid_rounded_box``).
* 3 compound ops that compose into multiple ``ShapePrimitive`` records
  (``op_fastener_grid``, ``op_vent_slats``, ``op_trim_band``).

Each test parses a ``.lth`` source through ``parse_text``, lowers via
``lower_mesh_program``, and asserts the deterministic primitive count
and key field values.
"""

from __future__ import annotations

import pytest
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.ops_test\n"
        "asset ops_test : hard_surface_prop {\n"
        "  intent { role = \"ops test\" }\n"
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
# Solid constructors
# ---------------------------------------------------------------------------


def test_solid_panel_emits_extruded_profile_with_panel_tags() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [40cm, 30cm, 2cm])"
    )
    primitives = lower_mesh_program(mp)
    # Constructors don't auto-append; need a follow-up op to flush.
    # Verify by binding into a boolean to materialize.
    mp2 = _parse_program(
        "let body = solid_panel(extents: [40cm, 30cm, 2cm])\n"
        "        let cutout = box(extents: [4cm, 4cm, 4cm])\n"
        "        let result = boolean(op: subtract, a: body, b: cutout, seam_group: \"slot\")"
    )
    primitives = lower_mesh_program(mp2)
    body = primitives[0]
    assert body.primitive_type == "extruded_profile"
    assert body.axis == "z"
    assert body.extrude_height == 2.0
    assert body.profile_polygon == [
        (-20.0, -15.0),
        (20.0, -15.0),
        (20.0, 15.0),
        (-20.0, 15.0),
    ]
    assert "solid_panel" in body.tags


def test_solid_rail_emits_square_section_extrusion() -> None:
    mp = _parse_program(
        "let beam = solid_rail(length: 50cm, profile: 3cm)\n"
        "        let cutout = box(extents: [2cm, 2cm, 2cm])\n"
        "        let r = boolean(op: subtract, a: beam, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    rail = primitives[0]
    assert rail.primitive_type == "extruded_profile"
    assert rail.axis == "x"
    assert rail.extrude_height == 50.0
    assert rail.profile_polygon == [
        (-1.5, -1.5),
        (1.5, -1.5),
        (1.5, 1.5),
        (-1.5, 1.5),
    ]
    assert "solid_rail" in rail.tags


def test_solid_prism_emits_triangular_extrusion() -> None:
    mp = _parse_program(
        "let wedge = solid_prism(extents: [10cm, 8cm, 4cm])\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: wedge, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    wedge = primitives[0]
    assert wedge.primitive_type == "extruded_profile"
    assert wedge.profile_polygon == [
        (-5.0, -4.0),
        (5.0, -4.0),
        (0.0, 4.0),
    ]
    assert wedge.extrude_height == 4.0
    assert "solid_prism" in wedge.tags


def test_solid_cylinder_emits_round_column() -> None:
    mp = _parse_program(
        "let pillar = solid_cylinder(radius: 5cm, height: 20cm)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: pillar, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    pillar = primitives[0]
    assert pillar.primitive_type == "cylinder"
    assert pillar.radius == 5.0
    assert pillar.height == 20.0
    assert pillar.axis == "y"
    assert "solid_cylinder" in pillar.tags


def test_solid_rounded_box_carries_rounding() -> None:
    mp = _parse_program(
        "let body = solid_rounded_box(extents: [20cm, 20cm, 5cm], radius: 5mm)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: body, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    body = primitives[0]
    assert body.primitive_type == "box"
    assert body.extents == (20.0, 20.0, 5.0)
    assert body.rounding == pytest.approx(0.5)
    assert "solid_rounded_box" in body.tags


# ---------------------------------------------------------------------------
# Compound ops
# ---------------------------------------------------------------------------


def test_fastener_grid_emits_rows_times_cols_cylinders() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [40cm, 30cm, 2cm])\n"
        "        op_fastener_grid("
        "target: body, face: \"+z\", rows: 2, cols: 6, spacing: 5cm, "
        "fastener_radius: 2mm, fastener_height: 4mm, seam_group: \"rivets\")"
    )
    primitives = lower_mesh_program(mp)
    # 1 panel + 2*6 = 12 fasteners = 13
    assert len(primitives) == 13
    body = primitives[0]
    fasteners = primitives[1:]
    assert all(p.primitive_type == "cylinder" for p in fasteners)
    assert all(p.blend_mode == "union" for p in fasteners)
    assert all(p.radius == pytest.approx(0.2) for p in fasteners)
    assert all(p.height == pytest.approx(0.4) for p in fasteners)
    # The face is +z so cylinders' axis is "z" and they sit slightly above
    # body.center.z + body.thickness/2.
    assert all(p.axis == "z" for p in fasteners)
    expected_z = body.center[2] + 1.0 + 0.2  # half-thickness (1.0) + half-height (0.2)
    for p in fasteners:
        assert p.center[2] == pytest.approx(expected_z)
    # All fasteners carry the seam_group tag
    seam_names = {
        group.get("name")
        for p in fasteners
        for group in p.boolean_seam_groups
    }
    assert seam_names == {"rivets"}


def test_vent_slats_emits_count_subtract_boxes() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [40cm, 30cm, 2cm])\n"
        "        op_vent_slats("
        "target: body, face: \"+z\", count: 8, "
        "slot_width: 6mm, slot_length: 20cm, slot_depth: 1cm, "
        "spacing: 12mm, axis: \"x\", seam_group: \"vent\")"
    )
    primitives = lower_mesh_program(mp)
    # 1 panel + 8 slats = 9
    assert len(primitives) == 9
    body = primitives[0]
    slats = primitives[1:]
    assert all(p.primitive_type == "box" for p in slats)
    assert all(p.blend_mode == "subtract" for p in slats)
    # Each slat is slot_width along x, slot_length along y, slot_depth along z
    for p in slats:
        assert p.extents == pytest.approx((0.6, 20.0, 1.0))
    # Slats march along x, centered around body center x
    xs = [p.center[0] for p in slats]
    assert xs == sorted(xs)
    # The slats are inset from the +z face by half_depth (0.5)
    expected_z = body.center[2] + 1.0 - 0.5  # face_center_z (1.0) - half_depth
    for p in slats:
        assert p.center[2] == pytest.approx(expected_z)
    seam_names = {
        group.get("name")
        for p in slats
        for group in p.boolean_seam_groups
    }
    assert seam_names == {"vent"}


def test_trim_band_emits_single_inflated_box() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [40cm, 30cm, 2cm])\n"
        "        op_trim_band(target: body, axis: \"y\", width: 1cm, depth: 2mm)"
    )
    primitives = lower_mesh_program(mp)
    # 1 panel + 1 band = 2
    assert len(primitives) == 2
    band = primitives[1]
    assert band.primitive_type == "box"
    # Width along y = 1cm; perpendicular extents inflated by 2*depth (0.4cm)
    assert band.extents == pytest.approx((40.4, 1.0, 2.4))
    assert "op_trim_band" in band.tags


def test_compound_ops_chain_with_boolean_and_fillet() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [20cm, 20cm, 2cm])\n"
        "        let cutout = box(extents: [4cm, 4cm, 4cm])\n"
        "        let r = boolean(op: subtract, a: body, b: cutout, seam_group: \"slot\")\n"
        "        fillet_edge(target: r, edge_class: \"slot\", radius: 5mm, segments: 4)\n"
        "        op_fastener_grid("
        "target: body, face: \"+z\", rows: 2, cols: 4, spacing: 4cm, "
        "fastener_radius: 2mm, fastener_height: 3mm)"
    )
    primitives = lower_mesh_program(mp)
    # 1 panel + 1 cutout (subtract) + 8 fasteners = 10
    assert len(primitives) == 10
    # The cutout primitive carries the bevel modifier
    cutout_prim = primitives[1]
    assert cutout_prim.blend_mode == "subtract"
    assert cutout_prim.bevel_seam_groups
    assert cutout_prim.bevel_seam_groups[0]["target_seam_groups"] == ["slot"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_solid_panel_rejects_missing_extents() -> None:
    mp = _parse_program(
        "let body = solid_panel()\n"
        "        let c = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: body, b: c, seam_group: \"s\")"
    )
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "extents" in str(excinfo.value)


def test_solid_cylinder_rejects_missing_height() -> None:
    mp = _parse_program(
        "let body = solid_cylinder(radius: 3cm)\n"
        "        let c = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: body, b: c, seam_group: \"s\")"
    )
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "height" in str(excinfo.value)


def test_fastener_grid_rejects_unknown_target() -> None:
    mp = _parse_program(
        "op_fastener_grid("
        "target: missing, face: \"+z\", rows: 1, cols: 1, spacing: 1cm, "
        "fastener_radius: 1mm, fastener_height: 1mm)"
    )
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "missing" in str(excinfo.value).lower() or "target" in str(excinfo.value).lower()


def test_vent_slats_rejects_axis_equal_to_face_normal() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [10cm, 10cm, 2cm])\n"
        "        op_vent_slats("
        "target: body, face: \"+z\", count: 4, "
        "slot_width: 5mm, slot_length: 5cm, slot_depth: 5mm, "
        "spacing: 1cm, axis: \"z\")"
    )
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "axis" in str(excinfo.value).lower()


def test_fastener_grid_invalid_face() -> None:
    mp = _parse_program(
        "let body = solid_panel(extents: [10cm, 10cm, 2cm])\n"
        "        op_fastener_grid("
        "target: body, face: \"top\", rows: 1, cols: 1, spacing: 1cm, "
        "fastener_radius: 1mm, fastener_height: 1mm)"
    )
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "face" in str(excinfo.value).lower()
