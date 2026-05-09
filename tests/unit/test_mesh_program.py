"""Tests for the V1.4 §5.1 ``mesh_program{}`` block.

Covers:

* Parser captures ``let`` bindings, chained ``.translate(...)``, and
  bare ``fillet_edge(...)`` calls in the order they appear.
* Lowering produces deterministic ``ShapePrimitive`` records with the
  expected ``boolean_seam_groups`` and ``bevel_seam_groups`` records.
* End-to-end mesh from the lowered primitives matches the Python
  helper baseline (``examples/bevel_demo.py``): 112 verts / 172 faces
  on the 10cm cube + 8x8x4cm subtract-with-bevel demo.
"""
from __future__ import annotations

import pytest

from lathe.exact_solids import compile_explicit_surface_mesh
from lathe.fidelity import _profile_from_tier
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text
from lathe.shape_ir import ShapeIR


_SOURCE = """
module demo.bevel
asset bevel_demo : hard_surface_prop {
  intent { role = "bevel demo" }
  build {
    shape {
      mode = generate
      candidates = 1
      mesh_program {
        let body = box(extents: [10cm, 10cm, 10cm])
        let cutout = box(extents: [8cm, 8cm, 4cm]).translate([0cm, 0cm, 4cm])
        let result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
        fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)
      }
    }
  }
}
"""


def _parsed_mesh_program() -> dict:
    program = parse_text(_SOURCE)
    return program["assets"][0]["build"]["shape"]["mesh_program"]


def test_parser_captures_ordered_statements() -> None:
    mp = _parsed_mesh_program()
    assert mp["node_type"] == "mesh_program"
    statements = mp["statements"]
    assert len(statements) == 4
    kinds = [stmt["node_type"] for stmt in statements]
    targets = [stmt.get("target") for stmt in statements]
    assert kinds == ["mesh_let", "mesh_let", "mesh_let", "mesh_call"]
    assert targets[:3] == ["body", "cutout", "result"]
    # The cutout's expression is a chained method_call against a box(...).
    cutout_expr = statements[1]["expr"]
    assert cutout_expr["type"] == "method_call"
    assert cutout_expr["method"] == "translate"
    assert cutout_expr["receiver"]["type"] == "call"
    assert cutout_expr["receiver"]["name"] == "box"


def test_lowering_produces_canonical_primitives() -> None:
    primitives = lower_mesh_program(_parsed_mesh_program())
    assert len(primitives) == 2
    body, cutout = primitives
    assert body.primitive_type == "box"
    assert body.center == (0.0, 0.0, 0.0)
    assert body.extents == (10.0, 10.0, 10.0)
    assert body.blend_mode == "union"
    assert cutout.primitive_type == "box"
    assert cutout.center == (0.0, 0.0, 4.0)
    assert cutout.extents == (8.0, 8.0, 4.0)
    assert cutout.blend_mode == "subtract"
    seam_names = {entry["name"] for entry in cutout.boolean_seam_groups}
    assert seam_names == {"lip"}
    bevel_targets = [
        tuple(entry["target_seam_groups"]) for entry in cutout.bevel_seam_groups
    ]
    assert bevel_targets == [("lip",)]


def test_end_to_end_matches_python_helper_baseline() -> None:
    primitives = lower_mesh_program(_parsed_mesh_program())
    ir = ShapeIR(
        asset_name="bevel_demo",
        family="hard_surface_prop",
        blueprint_id="bevel_demo_v1",
        symmetry_axis=None,
        units="cm",
        primitives=primitives,
        regions=[],
        primitives_used=["box"],
        part_graph=[],
        signature={},
    )
    fid = _profile_from_tier("hero")
    mesh, _, report = compile_explicit_surface_mesh(ir, fid)
    # Same vertex/face counts as ``examples/bevel_demo.py`` so the
    # source-level surface stays in lockstep with the Python helper.
    assert len(mesh.vertices) == 112
    assert len(mesh.faces) == 172
    assert report["post_boolean_polybevel_method"] == "edge_loop_cutback_strip_v1"
    assert report["post_boolean_polybevel_group_count"] == 1
    assert report["post_boolean_polybevel_edge_count"] == 23
    # ``post_boolean_polybevel_face_count`` is the full mesh face count
    # after the cutback pass; it has the same value as ``len(mesh.faces)``.
    assert report["post_boolean_polybevel_face_count"] == 172


def test_fillet_edge_rejects_undeclared_seam_group() -> None:
    src = _SOURCE.replace('edge_class: "lip"', 'edge_class: "missing"')
    program = parse_text(src)
    mp = program["assets"][0]["build"]["shape"]["mesh_program"]
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "missing" in str(excinfo.value)


def test_lowering_rejects_unknown_method() -> None:
    src = _SOURCE.replace(".translate([0cm, 0cm, 4cm])", ".rotate([0cm, 0cm, 4cm])")
    program = parse_text(src)
    mp = program["assets"][0]["build"]["shape"]["mesh_program"]
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "rotate" in str(excinfo.value)


def test_boolean_op_validation() -> None:
    src = _SOURCE.replace("op: subtract", "op: nope")
    program = parse_text(src)
    mp = program["assets"][0]["build"]["shape"]["mesh_program"]
    with pytest.raises(MeshProgramError) as excinfo:
        lower_mesh_program(mp)
    assert "boolean" in str(excinfo.value)


def test_unit_literal_regex_accepts_negative_values() -> None:
    from lathe.parser.grammar import _UNIT_RE, _num

    for text, expected_value, expected_unit in (
        ("-12cm", -12, "cm"),
        ("-4m", -4, "m"),
        ("-5mm", -5, "mm"),
        ("-2.5cm", -2.5, "cm"),
        ("-90deg", -90, "deg"),
        ("12cm", 12, "cm"),
        ("0.5m", 0.5, "m"),
    ):
        match = _UNIT_RE.match(text)
        assert match is not None, f"_UNIT_RE rejected {text!r}"
        assert _num(match.group("value")) == expected_value
        assert match.group("unit") == expected_unit


def test_mesh_program_parses_negative_unit_literal_in_translate() -> None:
    src = _SOURCE.replace(".translate([0cm, 0cm, 4cm])", ".translate([0cm, 0cm, -12cm])")
    program = parse_text(src)
    mp = program["assets"][0]["build"]["shape"]["mesh_program"]
    cutout_args = mp["statements"][1]["expr"]["args"][0]["value"]
    assert cutout_args[2] == {"type": "unit", "value": -12, "unit": "cm"}


def test_mesh_program_lowers_negative_translate_offset() -> None:
    src = _SOURCE.replace(".translate([0cm, 0cm, 4cm])", ".translate([0cm, 0cm, -12cm])")
    program = parse_text(src)
    mp = program["assets"][0]["build"]["shape"]["mesh_program"]
    primitives = lower_mesh_program(mp)
    cutout = primitives[1]
    assert cutout.center == (0.0, 0.0, -12.0)
