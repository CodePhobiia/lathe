"""Phase 5 tests for ``lathe.asset_quality.shape_ir_v2``.

Covers per task #5 of ``docs/asset-quality/improvement-tasklist.md``:

- ``ShapeOp`` and ``ShapeProgram`` are frozen dataclasses.
- The six op-family frozensets have their expected exact membership.
- ``ALL_OPS`` is the union and has the expected count.
- ``to_dict`` round-trips the dataclasses (tuples become lists, dicts
  preserved).
- ``validate_op`` accepts a well-formed op.
- ``validate_op`` rejects an unknown op name with a single
  ``unsupported_v2_op`` diagnostic.
- ``validate_op`` rejects an op missing required parameters with one
  ``missing_required_param`` diagnostic per missing key.
- ``lower_to_v1`` lowers a program of ``solid.box`` ops into v1 records
  with no diagnostics.
- ``lower_to_v1`` emits ``no_v1_equivalent`` for an op that v1 does not
  model (e.g. ``op.bevel``, ``op.weld_seam``).
- ``lower_to_v1`` is deterministic across invocations.
- A program of mixed valid + unknown ops produces a partial lowering
  alongside ``unsupported_v2_op`` diagnostics.
- ``ShapeProgram(ops=())`` lowers to an empty result with no
  diagnostics.
- ``SHAPE_IR_V2_VERSION == "shape_ir_v2"``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from lathe.asset_quality.shape_ir_v2 import (
    ALL_OPS,
    BOOLEAN_OPS,
    EDGE_OPS,
    INTEGRATION_OPS,
    REPETITION_OPS,
    SHAPE_IR_V2_VERSION,
    SOLID_OPS,
    SOP_OPS,
    WEAR_OPS,
    ZONE_OPS,
    ShapeOp,
    ShapeProgram,
    V1AdapterResult,
    lower_to_v1,
    validate_op,
)


def _box_op(part: str = "body") -> ShapeOp:
    return ShapeOp(
        op="solid.box",
        target=part,
        parameters={"width_cm": 92.0, "height_cm": 58.0, "depth_cm": 64.0},
        purpose="primary_volume",
    )


def _bevel_op() -> ShapeOp:
    return ShapeOp(
        op="op.bevel",
        target="body.outer_edges",
        parameters={"width_cm": 1.2, "segments": 3},
        purpose="catch_light_and_support_hard_surface_readability",
    )


def _program(ops: tuple[ShapeOp, ...]) -> ShapeProgram:
    return ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="industrial_crate",
        family="industrial_crate",
        ops=ops,
    )


def test_shape_op_dataclass_is_frozen() -> None:
    op = _box_op()
    with pytest.raises(FrozenInstanceError):
        op.op = "op.union"  # type: ignore[misc]


def test_shape_program_dataclass_is_frozen() -> None:
    program = _program(ops=(_box_op(),))
    with pytest.raises(FrozenInstanceError):
        program.asset_name = "other"  # type: ignore[misc]


def test_solid_ops_membership() -> None:
    assert frozenset(
        {
            "solid.box",
            "solid.branching_tree",
            "solid.capsule",
            "solid.cga_facade",
            "solid.curve_extruded_profile",
            "solid.curve_lofted_solid",
            "solid.curve_revolved_profile",
            "solid.curve_swept_profile",
            "solid.curved_tube",
            "solid.cylinder",
            "solid.extruded_profile",
            "solid.flange",
            "solid.gear",
            "solid.handle",
            "solid.hinge",
            "solid.ladder_frame",
            "solid.louver_panel",
            "solid.panel",
            "solid.perforated_panel",
            "solid.prism",
            "solid.rail",
            "solid.revolved_profile",
            "solid.ribbed_panel",
            "solid.rounded_box",
            "solid.sdf_metaball_cluster",
            "solid.sphere",
            "solid.spring",
            "solid.structural_beam",
            "solid.subdivision_box",
            "solid.swept_profile",
            "solid.terrain_patch",
            "solid.threaded_cylinder",
            "solid.torus",
            "solid.truss_frame",
            "solid.tube",
            "solid.wfc_modular_assembly",
        }
    ) == SOLID_OPS
    assert len(SOLID_OPS) == 36


def test_boolean_ops_membership() -> None:
    assert frozenset(
        {
            "op.countersunk_hole",
            "op.cut_panel_line",
            "op.extrude",
            "op.hull",
            "op.inset",
            "op.intersect",
            "op.minkowski",
            "op.rounded_slot",
            "op.shell",
            "op.subtract",
            "op.union",
        }
    ) == BOOLEAN_OPS
    assert len(BOOLEAN_OPS) == 11


def test_edge_ops_membership() -> None:
    assert frozenset(
        {
            "op.bevel",
            "op.chamfer",
            "op.weighted_normals",
            "op.mark_hard_edge",
        }
    ) == EDGE_OPS
    assert len(EDGE_OPS) == 4


def test_sop_ops_membership() -> None:
    assert frozenset(
        {
            "sop.bend",
            "sop.boolean",
            "sop.carve",
            "sop.copy_to_points",
            "sop.helical_sweep",
            "sop.loft",
            "sop.polybevel",
            "sop.polyextrude",
            "sop.polywire",
            "sop.remesh",
            "sop.scatter_on_surface",
            "sop.subdivide",
            "sop.sweep",
            "sop.taper",
            "sop.transform",
            "sop.twist",
        }
    ) == SOP_OPS
    assert len(SOP_OPS) == 16


def test_repetition_ops_membership() -> None:
    assert frozenset(
        {
            "op.corner_guard_set",
            "op.distribute",
            "op.fastener_grid",
            "op.mirror",
            "op.panel_frame",
            "op.repeat",
            "op.trim_band",
            "op.vent_slats",
        }
    ) == REPETITION_OPS
    assert len(REPETITION_OPS) == 8


def test_integration_ops_membership() -> None:
    assert frozenset(
        {
            "op.socket",
            "op.bracket",
            "op.mount_plate",
            "op.weld_seam",
        }
    ) == INTEGRATION_OPS
    assert len(INTEGRATION_OPS) == 4


def test_wear_ops_membership() -> None:
    assert frozenset(
        {
            "op.chip_edges",
            "op.scratch_mask",
            "op.dent_mask",
            "op.grime_mask",
        }
    ) == WEAR_OPS
    assert len(WEAR_OPS) == 4


def test_all_ops_is_union_of_families_with_current_count() -> None:
    assert ALL_OPS == (
        SOLID_OPS
        | BOOLEAN_OPS
        | EDGE_OPS
        | SOP_OPS
        | REPETITION_OPS
        | INTEGRATION_OPS
        | WEAR_OPS
        | ZONE_OPS
    )
    assert len(ALL_OPS) == 86


def test_zone_ops_exact_members() -> None:
    assert frozenset(
        {
            "op.material_zone",
            "op.decal_zone",
            "op.wear_zone",
        }
    ) == ZONE_OPS
    assert len(ZONE_OPS) == 3


def test_op_families_are_disjoint() -> None:
    families = (
        SOLID_OPS,
        BOOLEAN_OPS,
        EDGE_OPS,
        SOP_OPS,
        REPETITION_OPS,
        INTEGRATION_OPS,
        WEAR_OPS,
        ZONE_OPS,
    )
    seen: set[str] = set()
    for family in families:
        assert seen.isdisjoint(family)
        seen.update(family)


def test_version_constant() -> None:
    assert SHAPE_IR_V2_VERSION == "shape_ir_v2"


def test_shape_op_to_dict_round_trip() -> None:
    op = _box_op(part="body_shell")
    payload = op.to_dict()
    assert payload == {
        "op": "solid.box",
        "target": "body_shell",
        "parameters": {"width_cm": 92.0, "height_cm": 58.0, "depth_cm": 64.0},
        "purpose": "primary_volume",
    }


def test_shape_program_to_dict_preserves_order() -> None:
    op_a = _box_op(part="part_a")
    op_b = _box_op(part="part_b")
    program = _program(ops=(op_a, op_b))
    payload = program.to_dict()
    assert payload["version"] == SHAPE_IR_V2_VERSION
    assert payload["asset_name"] == "industrial_crate"
    assert payload["family"] == "industrial_crate"
    assert isinstance(payload["ops"], list)
    assert len(payload["ops"]) == 2
    assert payload["ops"][0]["target"] == "part_a"
    assert payload["ops"][1]["target"] == "part_b"


def test_validate_op_accepts_well_formed_box() -> None:
    is_valid, diagnostics = validate_op(_box_op())
    assert is_valid is True
    assert diagnostics == []


def test_validate_op_rejects_unknown_op_name() -> None:
    op = ShapeOp(op="op.does_not_exist", target=None, parameters={})
    is_valid, diagnostics = validate_op(op)
    assert is_valid is False
    assert diagnostics == ["unsupported_v2_op"]


def test_validate_op_rejects_missing_required_parameters() -> None:
    op = ShapeOp(op="solid.box", target="body", parameters={"width_cm": 10.0})
    is_valid, diagnostics = validate_op(op)
    assert is_valid is False
    assert diagnostics == [
        "missing_required_param: height_cm",
        "missing_required_param: depth_cm",
    ]


def test_lower_to_v1_lowers_solid_box_program_with_no_diagnostics() -> None:
    program = _program(ops=(_box_op(part="body_shell"),))
    result = lower_to_v1(program)
    assert isinstance(result, V1AdapterResult)
    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "box"
    assert record["part"] == "body_shell"
    assert record["extents"] == (92.0, 58.0, 64.0)
    assert record["v2_op"] == "solid.box"
    assert result.diagnostics == ()
    assert result.unsupported_ops == ()


def test_lower_to_v1_lowers_solid_rounded_box_with_rounding() -> None:
    op = ShapeOp(
        op="solid.rounded_box",
        target="lid",
        parameters={
            "width_cm": 80.0,
            "height_cm": 40.0,
            "depth_cm": 50.0,
            "radius_cm": 1.5,
        },
    )
    result = lower_to_v1(_program(ops=(op,)))
    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "box"
    assert record["rounding"] == 1.5
    assert "rounded" in record["tags"]
    assert result.diagnostics == ()


def test_lower_to_v1_requires_source_for_op_bevel() -> None:
    # ``op.bevel`` lowers by piercing through to its source primitive and
    # tagging the result with bevel intent. Without a ``source`` parameter
    # the lowering cannot resolve a primitive to bevel, so it emits a
    # parameter validation diagnostic rather than producing a record.
    program = _program(ops=(_bevel_op(),))
    result = lower_to_v1(program)
    assert result.v1_records == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic["code"] == "parameter_type_mismatch"
    assert diagnostic["op"] == "op.bevel"
    assert "source" in diagnostic["reason"]
    assert result.unsupported_ops == ()


def test_lower_to_v1_lowers_solid_rail_as_first_class_rail() -> None:
    op = ShapeOp(
        op="solid.rail",
        target="body.bottom_front",
        parameters={"length_cm": 60.0, "profile_cm": 4.0},
        purpose="foot_rails.front",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "rail"
    assert record["part"] == "body.bottom_front"
    assert record["axis"] == "x"
    assert record["length"] == 60.0
    assert record["profile"] == 4.0
    assert record["profile_height"] == 4.0
    assert record["profile_shape"] == "square"
    assert record["tags"] == ["solid_rail", "rail_profile"]
    assert record["v2_op"] == "solid.rail"
    assert record["v2_rail_modifier"]["method"] == "extruded_mechanical_rail_profile_v1"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_solid_panel_as_first_class_panel() -> None:
    op = ShapeOp(
        op="solid.panel",
        target="body.front_panel",
        parameters={"width_cm": 32.0, "height_cm": 20.0, "thickness_cm": 1.5},
        purpose="lid_seam.panel",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "panel"
    assert record["part"] == "body.front_panel"
    assert record["axis"] == "z"
    assert record["width"] == 32.0
    assert record["height"] == 20.0
    assert record["thickness"] == 1.5
    assert record["component"] == "panel"
    assert record["tags"] == ["solid_panel", "panel_profile"]
    assert record["v2_op"] == "solid.panel"
    assert record["v2_panel_modifier"]["method"] == "rect_panel_profile_v1"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_solid_prism_as_extruded_profile() -> None:
    op = ShapeOp(
        op="solid.prism",
        target="roof.wedge",
        parameters={"width_cm": 24.0, "height_cm": 12.0, "depth_cm": 18.0},
        purpose="roof.prism",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "extruded_profile"
    assert record["part"] == "roof.wedge"
    assert record["axis"] == "z"
    assert record["extrude_height"] == 18.0
    assert record["profile_polygon"] == (
        (-12.0, -6.0),
        (12.0, -6.0),
        (0.0, 6.0),
    )
    assert record["tags"] == ["solid_prism"]
    assert record["v2_op"] == "solid.prism"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_sop_boolean_source_with_blend_mode() -> None:
    op = ShapeOp(
        op="sop.boolean",
        target="body.cut",
        parameters={
            "operation": "subtract",
            "source": {
                "op": "solid.panel",
                "target": "body.slot",
                "parameters": {"width_cm": 12.0, "height_cm": 4.0, "thickness_cm": 2.0},
            },
        },
        purpose="slot.cut",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    # The inner ``solid.panel`` source lowers to a first-class ``panel``
    # primitive (v1 ShapeIR carries solid.panel through directly rather
    # than collapsing it to a generic extruded_profile).
    assert record["primitive_type"] == "panel"
    assert record["part"] == "body.cut"
    assert record["blend_mode"] == "subtract"
    assert "sop_boolean" in record["tags"]
    assert "boolean_subtract" in record["tags"]
    assert record["v2_op"] == "sop.boolean"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_sop_polybevel_box_source_to_subdivision_box() -> None:
    op = ShapeOp(
        op="sop.polybevel",
        target="body.beveled",
        parameters={
            "width_cm": 1.25,
            "segments": 5,
            "source": {
                "op": "solid.box",
                "target": "body",
                "parameters": {"width_cm": 20.0, "height_cm": 10.0, "depth_cm": 8.0},
            },
        },
        purpose="body.bevel",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "subdivision_box"
    assert record["part"] == "body.beveled"
    assert record["corner_radii"] == (1.25,) * 8
    assert record["corner_segments"] == 5
    assert "sop_polybevel" in record["tags"]
    assert "polybeveled_box_to_subdivision" in record["tags"]
    assert record["v2_op"] == "sop.polybevel"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_sop_carve_swept_source_path() -> None:
    op = ShapeOp(
        op="sop.carve",
        target="cable.segment",
        parameters={
            "u_start": 0.25,
            "u_end": 0.75,
            "source": {
                "op": "solid.swept_profile",
                "target": "cable",
                "parameters": {
                    "cross_section": [(-1.0, -1.0), (1.0, -1.0), (0.0, 1.0)],
                    "sweep_path": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                },
            },
        },
        purpose="cable.visible_segment",
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "swept_profile"
    assert record["part"] == "cable.segment"
    assert record["sweep_path"] == ((5.0, 0.0, 0.0), (15.0, 0.0, 0.0))
    assert "sop_carve" in record["tags"]
    assert record["v2_op"] == "sop.carve"
    assert result.diagnostics == ()


def test_lower_to_v1_lowers_op_weld_seam_as_first_class_weld_seam() -> None:
    # ``op.weld_seam`` is a first-class v1 primitive — lowering emits a
    # ``weld_seam`` record with a circular cross-section, axis routing,
    # and an attached polybevel modifier targeting the seam edge group.
    op = ShapeOp(
        op="op.weld_seam",
        target="body.lid_seam",
        parameters={"width_cm": 0.4},
    )
    result = lower_to_v1(_program(ops=(op,)))
    assert len(result.v1_records) == 1
    record = result.v1_records[0]
    assert record["primitive_type"] == "weld_seam"
    assert record["part"] == "body.lid_seam"
    assert record["weld_mode"] == "axis"
    assert record["width"] == 0.4
    assert record["v2_op"] == "op.weld_seam"
    assert record["v2_weld_seam_modifier"]["seam_group"] == "body.lid_seam_weld_edge"
    assert record["bevel_seam_groups"][0]["target_seam_groups"] == ["body.lid_seam_weld_edge"]
    assert result.diagnostics == ()


def test_lower_to_v1_is_deterministic() -> None:
    program = _program(ops=(_box_op(), _bevel_op()))
    first = lower_to_v1(program)
    second = lower_to_v1(program)
    assert first == second


def test_lower_to_v1_partial_lowering_with_unknown_op() -> None:
    unknown = ShapeOp(op="op.fake", target=None, parameters={})
    program = _program(ops=(_box_op(part="body"), unknown, _box_op(part="lid")))
    result = lower_to_v1(program)
    assert len(result.v1_records) == 2
    assert result.v1_records[0]["part"] == "body"
    assert result.v1_records[1]["part"] == "lid"
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0]["code"] == "unsupported_v2_op"
    assert result.diagnostics[0]["op"] == "op.fake"
    assert result.unsupported_ops == ("op.fake",)


def test_lower_to_v1_missing_required_param_does_not_crash() -> None:
    op = ShapeOp(op="solid.box", target="body", parameters={"width_cm": 1.0})
    result = lower_to_v1(_program(ops=(op,)))
    assert result.v1_records == ()
    codes = sorted({diagnostic["code"] for diagnostic in result.diagnostics})
    assert codes == ["missing_required_param"]
    assert len(result.diagnostics) == 2


def test_lower_to_v1_parameter_type_mismatch_does_not_crash() -> None:
    op = ShapeOp(
        op="solid.panel",
        target="body.front_panel",
        parameters={"width_cm": "wide", "height_cm": 20.0, "thickness_cm": 1.5},
    )
    result = lower_to_v1(_program(ops=(op,)))

    assert result.v1_records == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic["code"] == "parameter_type_mismatch"
    assert diagnostic["op"] == "solid.panel"
    assert "width_cm" in diagnostic["reason"]


def test_lower_to_v1_empty_program_is_empty_result() -> None:
    program = _program(ops=())
    result = lower_to_v1(program)
    assert result.v1_records == ()
    assert result.diagnostics == ()
    assert result.unsupported_ops == ()


def test_lower_to_v1_dedupes_unsupported_ops() -> None:
    unknown = ShapeOp(op="op.fake", target=None, parameters={})
    program = _program(ops=(unknown, unknown))
    result = lower_to_v1(program)
    assert len(result.diagnostics) == 2
    assert result.unsupported_ops == ("op.fake",)
