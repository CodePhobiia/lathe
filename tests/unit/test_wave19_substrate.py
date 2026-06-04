"""Wave 19 tests: 5 substrate gaps closed."""

from __future__ import annotations

import json
from pathlib import Path

from lathe.asset_quality.edge_group_selector import (
    EdgeMetadata,
    default_edge_metadata_for_box,
    select_edge_group,
)
from lathe.asset_quality.lod_policy import default_lod_policy
from lathe.asset_quality.multi_lod_emission import emit_lod_variants
from lathe.asset_quality.shape_ir_v2 import ShapeOp, ShapeProgram
from lathe.shape.support_proof import LoadPathEvidence, prove_support_relation
from lathe.surface_graph.zone_propagation import (
    decode_face_zones_from_vertex_properties,
    encode_zone_property_channel,
    propagate_zones_via_face_parts,
)


# S1: Zone propagation via vert_properties + fallback


def test_zone_channel_encoding_round_trip() -> None:
    """Encoded zone channel values decode back to their zone_ids."""
    zone_ids = ["body", "trim", "corner_guard", "decal_warning"]
    values, reverse = encode_zone_property_channel(zone_ids)
    assert len(values) == 4
    for v, expected in zip(values, zone_ids):
        assert reverse[v] == expected


def test_decode_face_zones_majority_vote() -> None:
    """Triangle vertices vote on the face's zone; majority wins."""
    values, reverse = encode_zone_property_channel(["body", "trim"])
    body_v, trim_v = values
    # Triangle 0: 3 body vertices → body wins.
    # Triangle 1: 2 trim + 1 body → trim wins.
    vertex_props = [
        (0.0, 0.0, 0.0, body_v),
        (0.0, 0.0, 0.0, body_v),
        (0.0, 0.0, 0.0, body_v),
        (0.0, 0.0, 0.0, trim_v),
        (0.0, 0.0, 0.0, trim_v),
    ]
    triangles = [(0, 1, 2), (2, 3, 4)]
    face_zones = decode_face_zones_from_vertex_properties(
        vertex_props, triangles, reverse, zone_channel_index=3
    )
    assert face_zones == ("body", "trim")


def test_propagate_via_face_parts_fallback() -> None:
    """Legacy face_parts path produces a valid ZonePropagationResult."""
    result = propagate_zones_via_face_parts(
        ["body", "body", "trim"], region_id_by_part={"body": "body_zone", "trim": "trim_zone"}
    )
    assert result.method == "face_parts_fallback"
    assert result.face_zone_ids == ("body_zone", "body_zone", "trim_zone")
    assert result.zone_id_to_face_count == {"body_zone": 2, "trim_zone": 1}


# S2: Edge-group selector resolver


def test_edge_group_filters_by_angle() -> None:
    edges = [
        EdgeMetadata("e0", role="generic", dihedral_angle_deg=30.0, exposed=True),
        EdgeMetadata("e1", role="generic", dihedral_angle_deg=45.0, exposed=True),
        EdgeMetadata("e2", role="generic", dihedral_angle_deg=89.0, exposed=True),
    ]
    group = select_edge_group("hero_silhouette", {"angle_gt_deg": 35}, edges)
    assert set(group.edge_ids) == {"e1", "e2"}


def test_edge_group_filters_by_role() -> None:
    edges = [
        EdgeMetadata("e0", role="outer_corner_x", exposed=True),
        EdgeMetadata("e1", role="panel_border", exposed=True),
        EdgeMetadata("e2", role="interior_seam", exposed=False),
    ]
    group = select_edge_group(
        "exposed_outer", {"role_in": ["outer_corner", "panel_border"], "exposed": True}, edges
    )
    assert set(group.edge_ids) == {"e0", "e1"}


def test_edge_group_filters_by_axis() -> None:
    edges = [
        EdgeMetadata("ex", role="generic", axis="x"),
        EdgeMetadata("ey", role="generic", axis="y"),
        EdgeMetadata("ez", role="generic", axis="z"),
    ]
    group = select_edge_group("z_aligned", {"axis_aligned_to": "z"}, edges)
    assert group.edge_ids == ("ez",)


def test_default_edge_metadata_for_box_emits_12_edges() -> None:
    edges = default_edge_metadata_for_box({"x": 90.0, "y": 60.0, "z": 50.0})
    assert len(edges) == 12
    axes = {e.axis for e in edges}
    assert axes == {"x", "y", "z"}


# S3: Schemas exist + loadable


def test_morphology_profile_schema_loads() -> None:
    path = Path("lathe/asset_quality/procedural_synthesizer/knowledge_loader/schemas/morphology_profile.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema["title"] == "MorphologyProfile"
    assert "id" in schema["required"]


def test_all_new_schemas_exist() -> None:
    base = Path("lathe/asset_quality/procedural_synthesizer/knowledge_loader/schemas")
    for name in (
        "morphology_profile.schema.json",
        "visual_language.schema.json",
        "class_anchor_rubric.schema.json",
        "kit_graph.schema.json",
        "lod_policy.schema.json",
    ):
        assert (base / name).is_file(), f"missing {name}"


# S4: Support load-path proof


def test_support_proof_rejects_misaligned_normal() -> None:
    result = prove_support_relation(
        source_contact_origin=(0.0, 0.0, 0.0),
        source_contact_normal=(1.0, 0.0, 0.0),  # sideways — doesn't fight gravity
        source_contact_bounds_cm=(10.0, 10.0, 1.0),
        target_com_world_cm=(0.0, 0.0, 10.0),
        target_footprint_bounds_cm=(8.0, 8.0, 5.0),
    )
    assert not result.valid
    assert "normal alignment" in result.rejection_reason


def test_support_proof_rejects_tiny_contact() -> None:
    result = prove_support_relation(
        source_contact_origin=(0.0, 0.0, 0.0),
        source_contact_normal=(0.0, 0.0, 1.0),  # upward — opposed to gravity ✓
        source_contact_bounds_cm=(1.0, 1.0, 1.0),  # 1cm² < min 4cm²
        target_com_world_cm=(0.0, 0.0, 10.0),
        target_footprint_bounds_cm=(8.0, 8.0, 5.0),
    )
    assert not result.valid
    assert "contact area" in result.rejection_reason


def test_support_proof_rejects_offset_com() -> None:
    result = prove_support_relation(
        source_contact_origin=(0.0, 0.0, 0.0),
        source_contact_normal=(0.0, 0.0, 1.0),
        source_contact_bounds_cm=(10.0, 10.0, 1.0),
        target_com_world_cm=(50.0, 0.0, 10.0),  # 50cm offset > max 5cm
        target_footprint_bounds_cm=(8.0, 8.0, 5.0),
    )
    assert not result.valid
    assert "COM offset" in result.rejection_reason


def test_support_proof_accepts_aligned_well_supported() -> None:
    result = prove_support_relation(
        source_contact_origin=(0.0, 0.0, 0.0),
        source_contact_normal=(0.0, 0.0, 1.0),
        source_contact_bounds_cm=(10.0, 10.0, 1.0),
        target_com_world_cm=(2.0, 1.0, 10.0),  # within 5cm offset
        target_footprint_bounds_cm=(8.0, 8.0, 5.0),
    )
    assert result.valid
    assert result.normal_alignment_score == 1.0
    assert result.contact_area_cm2 == 100.0


# S5: Multi-LOD ShapeProgram emission


def _sample_program() -> ShapeProgram:
    return ShapeProgram(
        version="2",
        asset_name="crate",
        family=None,
        ops=(
            ShapeOp(op="solid.rounded_box", target="body", parameters={}, purpose="procedural_primary_volume"),
            ShapeOp(op="op.bevel", target="body", parameters={"segments": 3, "radius_cm": 0.6}, purpose="procedural_primary_volume.bevel"),
            ShapeOp(op="solid.cylinder", target="rivet_1", parameters={}, purpose="procedural_fastener.rivet"),
            ShapeOp(op="solid.cylinder", target="rivet_2", parameters={}, purpose="procedural_fastener.rivet"),
            ShapeOp(op="solid.box", target="trim_band", parameters={}, purpose="procedural_trim.band"),
        ),
    )


def test_emit_lod_variants_drops_fasteners_at_low_lod() -> None:
    program = _sample_program()
    policy = default_lod_policy("crate")
    variants = emit_lod_variants(program, policy)
    assert len(variants) == 4

    lod0_fasteners = sum(1 for op in variants[0].ops if "fastener" in op.purpose.lower())
    lod3_fasteners = sum(1 for op in variants[3].ops if "fastener" in op.purpose.lower())
    # LOD0 keeps fastener geometry; LOD3 removes it per policy.
    assert lod0_fasteners == 2
    assert lod3_fasteners == 0


def test_emit_lod_variants_downgrades_bevel_segments() -> None:
    program = _sample_program()
    policy = default_lod_policy("crate")
    variants = emit_lod_variants(program, policy)
    lod0_bevel = next(op for op in variants[0].ops if op.op == "op.bevel")
    assert lod0_bevel.parameters["segments"] == 2  # LOD0 = 2 segments per policy
    # LOD3 drops bevel entirely.
    lod3_bevels = [op for op in variants[3].ops if op.op == "op.bevel"]
    assert lod3_bevels == []


def test_emit_lod_variants_preserves_body() -> None:
    """Primary volume should always be in every LOD."""
    program = _sample_program()
    policy = default_lod_policy("crate")
    variants = emit_lod_variants(program, policy)
    for variant in variants:
        body_ops = [op for op in variant.ops if "primary_volume" in op.purpose]
        assert len(body_ops) >= 1
