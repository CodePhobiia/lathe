"""ShapeIR v2 next-tier feature ops registry (Wave 6).

Per ``docs/research/newresearch.md`` Milestone 4: the priority ops are
``op.panel_inset``, ``op.edge_group_select``, ``op.weighted_bevel``,
``op.trim_sweep``, ``op.profile_sweep``, ``op.fastener_pattern``,
``op.boolean_group``, ``op.lod_policy``.

This module is the declarative substrate: each op has a parameter
schema, a kernel-state classification (executed / approximated /
unsupported), and a generator/lowering hook. The actual lowering
implementation lives in ``lathe/asset_quality/shape_ir_v2.py`` — this
module is the contract surface so generators + repair operators can
reference ops by id without import cycles.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.shape.feature_ops_v2_v1"


@dataclass(frozen=True)
class FeatureOpSpec:
    """Declarative spec for a ShapeIR v2 feature op."""

    op_id: str
    required_params: tuple[str, ...]
    optional_params: tuple[str, ...] = ()
    kernel_state: str = "approximated"  # executed | approximated | unsupported
    description: str = ""
    semantic_role: str = "structural"  # structural | surface | metadata


PRIORITY_FEATURE_OPS: dict[str, FeatureOpSpec] = {
    "op.panel_inset": FeatureOpSpec(
        op_id="op.panel_inset",
        required_params=("target_face", "margin_cm", "depth_cm"),
        optional_params=("bevel_policy", "material_zone", "corner_radius_cm"),
        kernel_state="approximated",
        description=(
            "Inset a rectangular panel into the target face by ``margin_cm`` "
            "and recess by ``depth_cm``. Drives crates' lid seams, sci-fi "
            "panels, terminals, mechanical housings."
        ),
        semantic_role="structural",
    ),
    "op.edge_group_select": FeatureOpSpec(
        op_id="op.edge_group_select",
        required_params=("name", "where"),
        kernel_state="executed",
        description=(
            "Declarative edge selector. ``where`` is a predicate dict over "
            "edge attributes (angle_gt_deg, exposed, role_in, "
            "feature_scale_gt). Produces a named edge group consumed by "
            "op.weighted_bevel and op.trim_sweep."
        ),
        semantic_role="metadata",
    ),
    "op.weighted_bevel": FeatureOpSpec(
        op_id="op.weighted_bevel",
        required_params=("edge_group", "radius_cm"),
        optional_params=("segments", "profile", "normal_policy", "zone_policy"),
        kernel_state="executed",
        description=(
            "Apply a chamfer/round to a named edge group with weighted "
            "radius + segments + profile. Replaces the uniform bevel-all-"
            "sharp-edges behavior."
        ),
        semantic_role="structural",
    ),
    "op.trim_sweep": FeatureOpSpec(
        op_id="op.trim_sweep",
        required_params=("path", "profile"),
        optional_params=(
            "frame_policy",
            "join_policy",
            "material_zone",
            "fuse_policy",
        ),
        kernel_state="approximated",
        description=(
            "Sweep a 2D cross-section profile along a path. Trim bands, "
            "raised borders, lid seams, rails. ``fuse_policy: separate_"
            "submesh`` keeps the trim as its own material zone."
        ),
        semantic_role="structural",
    ),
    "op.profile_sweep": FeatureOpSpec(
        op_id="op.profile_sweep",
        required_params=("path", "cross_section"),
        optional_params=("scale_along_path", "rotation_along_path", "twist_deg"),
        kernel_state="approximated",
        description=(
            "General profile sweep — non-planar paths, variable cross "
            "section along path. Cables, pipes, handles, decorative trims."
        ),
        semantic_role="structural",
    ),
    "op.fastener_pattern": FeatureOpSpec(
        op_id="op.fastener_pattern",
        required_params=("pattern_type", "count", "anchor_set"),
        optional_params=("fastener_template", "spacing_cm", "stagger"),
        kernel_state="executed",
        description=(
            "Distribute fastener instances over an anchor set with a "
            "named pattern (grid, line, ring, perimeter, stagger). "
            "Anchor set comes from the placement-binding layer."
        ),
        semantic_role="structural",
    ),
    "op.boolean_group": FeatureOpSpec(
        op_id="op.boolean_group",
        required_params=("target", "operation", "cutters"),
        optional_params=("evaluation", "preserve_provenance"),
        kernel_state="approximated",
        description=(
            "Batched boolean: collect interacting cutters per spatial "
            "cluster, materialize once, apply grouped expression, extract "
            "once. Replaces serial binary booleans. ``evaluation: batched``"
            " engages the cluster compiler."
        ),
        semantic_role="structural",
    ),
    "op.lod_policy": FeatureOpSpec(
        op_id="op.lod_policy",
        required_params=("lods",),
        kernel_state="metadata",
        description=(
            "Per-LOD policy block: bevel_segments, fastener_representation"
            " (geometry|normal_stamp|texture|removed), panel_groove "
            "representation, target_tris. Consumed by the optimize/LOD "
            "stage to emit per-LOD ShapeProgram variants."
        ),
        semantic_role="metadata",
    ),
}


def get_spec(op_id: str) -> FeatureOpSpec | None:
    return PRIORITY_FEATURE_OPS.get(op_id)


def validate_op_params(op_id: str, parameters: Mapping[str, Any]) -> list[str]:
    """Return list of missing required params (empty when valid)."""
    spec = PRIORITY_FEATURE_OPS.get(op_id)
    if spec is None:
        return [f"unknown_op:{op_id}"]
    missing: list[str] = []
    for required in spec.required_params:
        if required not in parameters:
            missing.append(required)
    return missing


__all__ = [
    "CONTRACT_VERSION",
    "FeatureOpSpec",
    "PRIORITY_FEATURE_OPS",
    "get_spec",
    "validate_op_params",
]
