from __future__ import annotations

from typing import Any


def derive_topology_semantics(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    shape_ir = shape_bundle.get("shape_ir", [])
    if not shape_ir:
        return {"hard_edge_groups": [], "panel_seams": [], "bake_groups": [], "feature_semantics": {}}
    primary = shape_ir[0]
    regions = primary.get("regions", [])
    panel_seams = [
        region["name"]
        for region in regions
        if region.get("component") in {"panel", "frame", "bezel", "door", "lid"}
    ]
    hard_edge_groups = [
        {
            "name": region["name"],
            "part": region["part"],
            "edge_class": "hard_surface_feature"
            if region.get("component") not in {"vent", "grille"}
            else "grille",
        }
        for region in regions
    ]
    bake_groups = [
        {
            "name": region["name"],
            "part": region["part"],
            "material_boundary": region.get("component")
            in {"panel", "bezel", "screen_bezel", "lock_plate", "socket_plate"},
        }
        for region in regions
    ]
    return {
        "hard_edge_groups": hard_edge_groups,
        "panel_seams": panel_seams,
        "bake_groups": bake_groups,
        "feature_semantics": shape_bundle.get("shape_assessment", {}),
    }


def should_preserve_integrated_shape(
    shape_bundle: dict[str, Any], runtime_config: dict[str, Any] | None = None
) -> bool:
    topology_cfg = (runtime_config or {}).get("topology", {})
    if topology_cfg.get("adapter") not in {None, "", "auto"}:
        return False
    selected_id = shape_bundle.get("selected_candidate_id")
    candidate = next(
        (item for item in shape_bundle.get("candidates", []) if item.get("candidate_id") == selected_id), None
    )
    if not candidate:
        return False
    integration = candidate.get("integration_report", {})
    return integration.get("mode") in {"sdf_voxel_fusion", "exact_component_assembly"}
