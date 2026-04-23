from __future__ import annotations

from typing import Any


def derive_uv_semantics(topology_bundle: dict[str, Any], shape_bundle: dict[str, Any]) -> dict[str, Any]:
    topology_semantics = topology_bundle.get("feature_semantics", {})
    bake_groups = topology_semantics.get("bake_groups", [])
    panel_seams = topology_semantics.get("panel_seams", [])
    material_boundaries = [group["name"] for group in bake_groups if group.get("material_boundary")]
    return {
        "seam_guides": panel_seams,
        "bake_groups": bake_groups,
        "material_boundaries": material_boundaries,
        "lightmap_ready": bool(topology_bundle.get("panel_seams")),
        "feature_semantics": shape_bundle.get("shape_assessment", {}),
    }
