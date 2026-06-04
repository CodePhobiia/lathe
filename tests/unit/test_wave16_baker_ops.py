"""Wave 16 tests: PBR baker + feature op lowering."""

from __future__ import annotations

from lathe.asset_quality.feature_ops_v2_lowering import (
    FeatureOpLoweringContext,
    lower_feature_op_v2,
    lower_panel_inset,
    lower_weighted_bevel,
)
from lathe.asset_quality.shape_ir_v2 import ShapeOp
from lathe.surface_graph.pbr_baker import (
    bake_pbr_material_slots,
    manifest_to_dict,
)
from lathe.surface_graph.zone_binding import FaceZoneAssignment, ZoneAtlas, ZoneTag


def _sample_atlas() -> ZoneAtlas:
    return ZoneAtlas(
        zones=(
            ZoneTag(zone_id="body", material_class="painted_steel", uv_policy="box_projected_worldscale"),
            ZoneTag(zone_id="corner_guard", material_class="raw_steel", uv_policy="trim_sheet_metal"),
            ZoneTag(zone_id="trim_band", material_class="painted_steel", uv_policy="trim_sheet_metal"),
        ),
        face_assignments=(
            FaceZoneAssignment(face_index=0, zone_id="body"),
            FaceZoneAssignment(face_index=1, zone_id="body"),
            FaceZoneAssignment(face_index=2, zone_id="corner_guard"),
            FaceZoneAssignment(face_index=3, zone_id="trim_band"),
        ),
    )


def test_baker_emits_slot_per_zone() -> None:
    atlas = _sample_atlas()
    manifest = bake_pbr_material_slots("crate_42", atlas, visual_language_id="utility_industrial_v1")
    assert manifest.slot_count() == 3
    body_slot = manifest.slot_by_zone("body")
    assert body_slot is not None
    assert body_slot.material_class == "painted_steel"
    assert body_slot.archetype_id == "painted_steel.utility_industrial"
    assert body_slot.face_count == 2


def test_baker_condition_affects_channels() -> None:
    """Higher condition → rougher, more rust-tinted channels."""
    atlas = _sample_atlas()
    clean = bake_pbr_material_slots(
        "crate", atlas, condition_by_zone={"body": 0.05}, environment="neutral"
    )
    worn = bake_pbr_material_slots(
        "crate", atlas, condition_by_zone={"body": 0.85}, environment="humid_industrial"
    )
    clean_body = clean.slot_by_zone("body").channels
    worn_body = worn.slot_by_zone("body").channels
    assert worn_body.roughness > clean_body.roughness
    assert worn_body.ao_intensity > clean_body.ao_intensity


def test_manifest_round_trips_to_dict() -> None:
    atlas = _sample_atlas()
    manifest = bake_pbr_material_slots("crate", atlas)
    blob = manifest_to_dict(manifest)
    assert blob["contract_version"] == "lathe.surface.pbr_baker_v1"
    assert blob["slot_count"] == 3
    assert len(blob["slots"]) == 3
    assert blob["slots"][0]["channels"]["roughness"] > 0


def test_lower_panel_inset_emits_cutter_and_union() -> None:
    op = ShapeOp(
        op="op.panel_inset",
        target="body.front_face",
        parameters={
            "target_face": "body.face.pos_y",
            "margin_cm": 4.0,
            "depth_cm": 1.5,
            "material_zone": "painted_panel_inset",
        },
        purpose="test",
    )
    ctx = FeatureOpLoweringContext(
        asset_id="crate",
        body_dimensions_cm={"x": 90.0, "y": 60.0, "z": 50.0},
    )
    lowered = lower_panel_inset(op, ctx)
    assert len(lowered) == 2
    cutter, union = lowered
    assert cutter.op == "solid.box"
    # For a pos_y face, the recess depth is along Y → height_cm.
    # width_cm + depth_cm carry the panel's face extents minus margin.
    assert cutter.parameters["height_cm"] == 1.5
    assert cutter.parameters["width_cm"] == 90.0 - 2 * 4.0  # X face minus margin
    assert cutter.parameters["depth_cm"] == 50.0 - 2 * 4.0  # Z face minus margin
    assert "center" in cutter.parameters
    assert union.op == "op.union"
    assert union.parameters["operation"] == "difference"


def test_lower_weighted_bevel_emits_one_op_bevel() -> None:
    op = ShapeOp(
        op="op.weighted_bevel",
        target="body",
        parameters={
            "edge_group": "hero_silhouette_edges",
            "radius_cm": 0.6,
            "segments": 1,
            "profile": "chamfer",
            "normal_policy": "hard_break",
        },
        purpose="test",
    )
    ctx = FeatureOpLoweringContext(
        asset_id="crate",
        body_dimensions_cm={"x": 90.0, "y": 60.0, "z": 50.0},
    )
    lowered = lower_weighted_bevel(op, ctx)
    assert len(lowered) == 1
    bevel = lowered[0]
    assert bevel.op == "op.bevel"
    assert bevel.parameters["edge_group"] == "hero_silhouette_edges"
    assert bevel.parameters["weighted"] is True


def test_dispatch_passes_through_unknown_ops() -> None:
    """Ops without specialized lowering pass through unchanged."""
    op = ShapeOp(op="op.unsupported", target=None, parameters={}, purpose="test")
    ctx = FeatureOpLoweringContext(
        asset_id="crate",
        body_dimensions_cm={"x": 30.0, "y": 30.0, "z": 30.0},
    )
    lowered = lower_feature_op_v2(op, ctx)
    assert lowered == (op,)
