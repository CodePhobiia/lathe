from __future__ import annotations

from copy import deepcopy
from typing import Any

from .asset_graph import AssetGraph
from .assembly_kernel import refresh_shape_ir
from .candidate_search import CandidateParams
from .fidelity import FidelityProfile
from .feature_ops import (
    clasp_set_features,
    edge_break_features,
    fastener_strip_features,
    hinge_set_features,
    inset_panel_features,
    panel_frame_features,
    recessed_handle_features,
    rib_features,
    rotor_shroud_features,
    screen_bezel_features,
    support_bracket_features,
    trim_band_features,
    vent_grille_features,
)
from .shape_ir import ShapeIR
from .assembly_kernel import BlueprintComponent


def _component_from_region(shape_ir: ShapeIR, region_name: str) -> BlueprintComponent | None:
    region = next((item for item in shape_ir.regions if item.name == region_name), None)
    if region is None:
        return None
    return BlueprintComponent(
        name=region.name,
        component_type=region.component,
        part=region.part,
        center=region.center,
        extents=region.extents,
        tags=list(region.tags),
        adjacency=list(region.adjacency),
        axis="y",
        symmetry_mate=region.symmetry_mate,
        interface_role=region.interface_role,
    )


def _shape_component_features(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    component: BlueprintComponent,
    fidelity: FidelityProfile,
    params: CandidateParams,
) -> list:
    density = max(0.6, params.feature_density)
    edge_scale = max(0.75, params.edge_weight)
    panel_depth = max(0.7, params.panel_depth)
    features = []
    feature_count = 2 if fidelity.tier == "blockout" else 4 if fidelity.tier == "game" else 6

    if component.component_type in {"shell", "body"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(trim_band_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        features.extend(inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        if density >= 1.0:
            features.extend(fastener_strip_features(component, count=min(6, 2 + fidelity.trim_complexity), depth_scale=panel_depth, size_scale=params.trim_scale))
        if asset_graph.family == "console_terminal":
            features.extend(rib_features(component, count=max(4, feature_count), depth_scale=panel_depth, thickness_scale=edge_scale * 0.85))
    elif component.component_type in {"lid", "door"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        features.extend(inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        features.extend(clasp_set_features(component, depth_scale=panel_depth))
        if any(region.component == "hinge" for region in shape_ir.regions):
            features.extend(hinge_set_features(component, depth_scale=panel_depth))
    elif component.component_type in {"frame", "bezel"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        if component.component_type == "bezel":
            features.extend(screen_bezel_features(component, depth_scale=panel_depth))
        if density >= 1.0:
            features.extend(fastener_strip_features(component, count=min(6, feature_count), depth_scale=panel_depth, size_scale=params.trim_scale))
    elif component.component_type in {"panel", "lock_plate", "latch", "socket_plate", "anchor_plate"}:
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        features.extend(inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale))
        if density >= 0.95:
            features.extend(fastener_strip_features(component, count=min(5, feature_count), depth_scale=panel_depth, size_scale=params.trim_scale))
        if asset_graph.family == "console_terminal":
            features.extend(trim_band_features(component, depth_scale=panel_depth * 0.9, thickness_scale=params.trim_scale * 0.8))
    elif component.component_type in {"handle"}:
        features.extend(recessed_handle_features(component, depth_scale=panel_depth))
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale * 0.8))
    elif component.component_type in {"hinge"}:
        features.extend(hinge_set_features(component, depth_scale=panel_depth))
    elif component.component_type in {"foot", "stand", "bracket"}:
        features.extend(support_bracket_features(component, depth_scale=panel_depth))
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale * 0.85))
        if density >= 0.95:
            features.extend(rib_features(component, count=max(3, feature_count - 1), depth_scale=panel_depth, thickness_scale=edge_scale * 0.8))
        if asset_graph.family == "console_terminal":
            features.extend(fastener_strip_features(component, count=max(4, feature_count), depth_scale=panel_depth, size_scale=params.trim_scale * 0.75))
    elif component.component_type in {"vent", "grille"}:
        features.extend(vent_grille_features(component, count=max(5, feature_count + 1), depth_scale=panel_depth))
        features.extend(edge_break_features(component, depth_scale=edge_scale * 0.85, thickness_scale=edge_scale * 0.75))
    elif component.component_type in {"rotor_arm"}:
        features.extend(rib_features(component, count=max(3, fidelity.trim_complexity), depth_scale=panel_depth, thickness_scale=edge_scale))
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale * 0.8))
    elif component.component_type in {"rotor_pod"}:
        features.extend(rotor_shroud_features(component, scale=params.rotor_guard_scale))
        features.extend(panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale * 0.7))
    return features


def compile_feature_enhancements(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    *,
    fidelity: FidelityProfile,
    params: CandidateParams,
) -> tuple[ShapeIR, dict[str, Any]]:
    enriched = deepcopy(shape_ir)
    added = []
    feature_ops_used: set[str] = set()
    for region in shape_ir.regions:
        component = _component_from_region(shape_ir, region.name)
        if component is None:
            continue
        features = _shape_component_features(asset_graph, shape_ir, component, fidelity, params)
        if not features:
            continue
        added.extend(features)
        feature_ops_used.update({feature.component or "feature" for feature in features})
    enriched.primitives.extend(added)
    enriched = refresh_shape_ir(asset_graph, enriched, notes=list(shape_ir.signature.get("blueprint_notes", [])) + [f"fidelity={fidelity.tier}", f"feature_density={params.feature_density:.3f}"])
    return enriched, {
        "fidelity": fidelity.to_dict(),
        "candidate_params": params.to_dict(),
        "feature_ops_used": sorted(feature_ops_used),
        "feature_count_added": len(added),
    }
