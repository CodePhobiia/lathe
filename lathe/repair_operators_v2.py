"""Canonical repair operator registry (research §16).

Per research §16: for "this asset doesn't look game-ready," the
repair loop must mutate the intent/policy graph, not the final mesh.
This registry names 12 operators with declarative payloads + the
expected graph mutation.

Each operator is registered by name with:
  - signature: required + optional payload fields
  - mutation_target: which graph stage receives the mutation
  - reentry_point: where the pipeline restarts after applying

The repair_executor consumes these to apply graph-level patches;
the repair_loop's classifier uses the registry to surface available
actions to validators.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.repair.operators_v2_v1"


@dataclass(frozen=True)
class RepairOperatorSpec:
    """Declarative spec for one canonical repair operator."""

    op_id: str
    required_payload: tuple[str, ...]
    optional_payload: tuple[str, ...] = ()
    mutation_target: str = "construction_graph"  # construction_graph | policy_brief | style_overlay | seed_scope
    reentry_point: str = "shape"  # shape | topology | uv | surface | validate
    description: str = ""


CANONICAL_REPAIR_OPERATORS: dict[str, RepairOperatorSpec] = {
    "insert_required_feature": RepairOperatorSpec(
        op_id="insert_required_feature",
        required_payload=("role",),
        optional_payload=("count", "anchor_role"),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="Insert a typed node of the named role with default attrs.",
    ),
    "panelize_face": RepairOperatorSpec(
        op_id="panelize_face",
        required_payload=("target_face",),
        optional_payload=("margin_cm", "depth_cm", "subdivisions"),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="Add panel-inset op breaking up a flat face.",
    ),
    "add_reinforcement_pattern": RepairOperatorSpec(
        op_id="add_reinforcement_pattern",
        required_payload=("anchor_set",),
        optional_payload=("pattern", "node_type"),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="Add brackets / edge bands / cross braces at named anchor set.",
    ),
    "strengthen_silhouette": RepairOperatorSpec(
        op_id="strengthen_silhouette",
        required_payload=("role",),
        optional_payload=("scale_factor",),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="Promote a feature from texture/normal to geometry.",
    ),
    "assign_material_zone": RepairOperatorSpec(
        op_id="assign_material_zone",
        required_payload=("target", "material_class"),
        optional_payload=("uv_policy", "decal_allowed"),
        mutation_target="construction_graph",
        reentry_point="surface",
        description="Tag a part / region with a material_class for downstream PBR.",
    ),
    "add_decal_zone": RepairOperatorSpec(
        op_id="add_decal_zone",
        required_payload=("target", "decal_role"),
        optional_payload=("size_cm", "host_face_axis"),
        mutation_target="construction_graph",
        reentry_point="surface",
        description="Reserve a decal placement surface for a named role.",
    ),
    "increase_bevel_readability": RepairOperatorSpec(
        op_id="increase_bevel_readability",
        required_payload=("edge_group",),
        optional_payload=("radius_cm", "segments", "normal_policy"),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="Apply a stronger weighted bevel to a named edge group.",
    ),
    "add_surface_wear": RepairOperatorSpec(
        op_id="add_surface_wear",
        required_payload=("target", "wear_role"),
        optional_payload=("condition", "environment"),
        mutation_target="construction_graph",
        reentry_point="surface",
        description="Attach a wear_zone recipe to a part / material zone.",
    ),
    "promote_detail_to_geometry": RepairOperatorSpec(
        op_id="promote_detail_to_geometry",
        required_payload=("feature",),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="A feature was authored as normal-stamp/texture; promote to geometry.",
    ),
    "demote_detail_to_texture": RepairOperatorSpec(
        op_id="demote_detail_to_texture",
        required_payload=("feature",),
        mutation_target="construction_graph",
        reentry_point="shape",
        description="A feature is over budget; demote from geometry to normal-stamp / texture.",
    ),
    "adjust_style_weights": RepairOperatorSpec(
        op_id="adjust_style_weights",
        required_payload=("visual_language", "weight_overrides"),
        mutation_target="style_overlay",
        reentry_point="shape",
        description="Tweak feature_weight_overrides for the VisualLanguage pack.",
    ),
    "resample_variation": RepairOperatorSpec(
        op_id="resample_variation",
        required_payload=("seed_scope",),
        mutation_target="seed_scope",
        reentry_point="shape",
        description="Resample within a single feature family (handle, decal) without re-rolling whole asset.",
    ),
}


def get_operator(op_id: str) -> RepairOperatorSpec | None:
    return CANONICAL_REPAIR_OPERATORS.get(op_id)


def validate_payload(op_id: str, payload: Mapping[str, Any]) -> list[str]:
    """Return missing required-payload keys."""
    spec = CANONICAL_REPAIR_OPERATORS.get(op_id)
    if spec is None:
        return [f"unknown_operator:{op_id}"]
    missing = [k for k in spec.required_payload if k not in payload]
    return missing


__all__ = [
    "CONTRACT_VERSION",
    "RepairOperatorSpec",
    "CANONICAL_REPAIR_OPERATORS",
    "get_operator",
    "validate_payload",
]
