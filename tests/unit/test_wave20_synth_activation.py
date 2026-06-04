"""Wave 20 tests: synth activation — 6 feature ops + anchor bridge."""

from __future__ import annotations

from lathe.asset_quality.feature_ops_v2_lowering import (
    FeatureOpLoweringContext,
    lower_boolean_group,
    lower_edge_group_select,
    lower_fastener_pattern,
    lower_feature_op_v2,
    lower_lod_policy,
    lower_profile_sweep,
    lower_trim_sweep,
)
from lathe.asset_quality.procedural_synthesizer.generators._anchor_bridge import (
    ResolvedAnchorFrame,
    resolved_anchor_for,
    stash_anchor_resolution,
)
from lathe.asset_quality.shape_ir_v2 import ShapeOp


def _ctx() -> FeatureOpLoweringContext:
    return FeatureOpLoweringContext(
        asset_id="crate",
        body_dimensions_cm={"x": 90.0, "y": 60.0, "z": 50.0},
    )


def test_lower_trim_sweep_emits_segments() -> None:
    op = ShapeOp(
        op="op.trim_sweep",
        target="lid_seam_trim",
        parameters={
            "path": [(0.0, 30.0, 0.0), (45.0, 30.0, 0.0), (45.0, 30.0, 25.0)],
            "profile": {"width_cm": 2.0, "height_cm": 0.8},
            "fuse_policy": "separate_submesh",
            "material_zone": "brass_trim",
        },
        purpose="test",
    )
    out = lower_trim_sweep(op, _ctx())
    # 3 path points → 2 segments. separate_submesh skips unions.
    segments = [o for o in out if o.op == "solid.box"]
    unions = [o for o in out if o.op == "op.union"]
    assert len(segments) == 2
    assert len(unions) == 0
    assert segments[0].parameters["region_id"] == "brass_trim"


def test_lower_trim_sweep_fuses_when_policy_requires() -> None:
    op = ShapeOp(
        op="op.trim_sweep",
        target="trim",
        parameters={
            "path": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
            "profile": {"width_cm": 1.0, "height_cm": 0.5},
            "fuse_policy": "fused_to_host",
        },
        purpose="test",
    )
    out = lower_trim_sweep(op, _ctx())
    segments = [o for o in out if o.op == "solid.box"]
    unions = [o for o in out if o.op == "op.union"]
    assert len(segments) == 1
    assert len(unions) == 1


def test_lower_profile_sweep_annotates_scale_and_rotation() -> None:
    op = ShapeOp(
        op="op.profile_sweep",
        target="cable",
        parameters={
            "path": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 5.0, 0.0)],
            "cross_section": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            "scale_along_path": [1.0, 0.8],
            "rotation_along_path": [0.0, 15.0],
            "twist_deg": 5.0,
        },
        purpose="test",
    )
    out = lower_profile_sweep(op, _ctx())
    segments = [o for o in out if o.op == "solid.box"]
    assert len(segments) >= 1
    assert segments[0].parameters["scale_factor"] == 1.0
    assert segments[0].parameters["twist_deg"] == 5.0


def test_lower_fastener_pattern_grid() -> None:
    op = ShapeOp(
        op="op.fastener_pattern",
        target="rivet",
        parameters={
            "pattern_type": "grid",
            "count": 8,
            "fastener_template": {"head_radius_cm": 0.4, "head_height_cm": 0.4},
        },
        purpose="test",
    )
    out = lower_fastener_pattern(op, _ctx())
    cylinders = [o for o in out if o.op == "solid.cylinder"]
    assert len(cylinders) == 8
    # Each cylinder has a unique center.
    centers = {tuple(o.parameters["center"]) for o in cylinders}
    assert len(centers) == 8


def test_lower_fastener_pattern_ring() -> None:
    op = ShapeOp(
        op="op.fastener_pattern",
        target="rivet",
        parameters={"pattern_type": "ring", "count": 6},
        purpose="test",
    )
    out = lower_fastener_pattern(op, _ctx())
    assert len([o for o in out if o.op == "solid.cylinder"]) == 6


def test_lower_boolean_group_tags_cluster() -> None:
    op = ShapeOp(
        op="op.boolean_group",
        target="body",
        parameters={
            "operation": "difference",
            "cutters": ["cut1", "cut2", "cut3"],
            "evaluation": "batched",
        },
        purpose="test",
    )
    out = lower_boolean_group(op, _ctx())
    assert len(out) == 3
    for op_record in out:
        assert op_record.parameters["_lathe_boolean_evaluation"] == "batched"
        assert op_record.parameters["operation"] == "difference"


def test_lower_lod_policy_passes_through() -> None:
    op = ShapeOp(
        op="op.lod_policy",
        target=None,
        parameters={"lods": [{"lod_id": "LOD0", "target_tris": 18000}]},
        purpose="test",
    )
    out = lower_lod_policy(op, _ctx())
    assert out == (op,)


def test_lower_edge_group_select_passes_through() -> None:
    op = ShapeOp(
        op="op.edge_group_select",
        target=None,
        parameters={"name": "hero_silhouette", "where": {"angle_gt_deg": 35}},
        purpose="test",
    )
    out = lower_edge_group_select(op, _ctx())
    assert out == (op,)


def test_lower_feature_op_v2_dispatch_all_priority_ops() -> None:
    """Every priority op has a registered dispatch."""
    ctx = _ctx()
    for op_id in (
        "op.panel_inset",
        "op.weighted_bevel",
        "op.trim_sweep",
        "op.profile_sweep",
        "op.fastener_pattern",
        "op.boolean_group",
        "op.lod_policy",
        "op.edge_group_select",
    ):
        op = ShapeOp(op=op_id, target=None, parameters={}, purpose="test")
        out = lower_feature_op_v2(op, ctx)
        assert isinstance(out, tuple)


def test_anchor_bridge_round_trip() -> None:
    resolved = ResolvedAnchorFrame(
        transform_world_cm=(15.0, 0.0, 12.5),
        z_axis=(0.0, 0.0, 1.0),
        source_anchor_id="fastener.0.mount",
        target_anchor_id="body.face.pos_z",
        relation="attached_to",
    )
    payload = stash_anchor_resolution({"existing": "field"}, resolved)
    assert payload["existing"] == "field"
    assert payload["position_cm"] == (15.0, 0.0, 12.5)

    class _Node:
        raw_attributes = payload

    decoded = resolved_anchor_for(_Node())
    assert decoded is not None
    assert decoded.transform_world_cm == (15.0, 0.0, 12.5)
    assert decoded.target_anchor_id == "body.face.pos_z"
    assert decoded.relation == "attached_to"


def test_anchor_bridge_returns_none_when_absent() -> None:
    class _Node:
        raw_attributes = {"position_cm": (0, 0, 0)}

    assert resolved_anchor_for(_Node()) is None
