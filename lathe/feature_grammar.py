"""Feature grammar for hard-surface shape authoring.

Defines the feature vocabulary (panels, bevels, cuts, insets, rivets,
etc.) that scaffolds and user sources use to describe local geometry.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .assembly_kernel import BlueprintComponent, refresh_shape_ir
from .asset_graph import AssetGraph
from .candidate_search import CandidateParams
from .feature_ops import (
    antenna_module_features,
    arch_opening_features,
    barrel_module_features,
    blade_module_features,
    cable_attachment_features,
    bolt_grid_features,
    brass_band_rivets_features,
    clasp_set_features,
    column_set_features,
    corner_guard_features,
    edge_break_features,
    fastener_strip_features,
    fin_attachment_features,
    guard_bar_attachment_features,
    groove_channel_features,
    handle_bar_attachment_features,
    hinge_set_features,
    hull_keel_features,
    inset_panel_features,
    layer_plate_features,
    leg_module_features,
    linear_detail_array_features,
    outset_panel_features,
    panel_seam_features,
    panel_frame_features,
    pipe_run_features,
    power_cell_module_features,
    radial_detail_array_features,
    raised_ridge_features,
    recessed_handle_features,
    rib_features,
    rail_attachment_features,
    rotor_shroud_features,
    sensor_pod_module_features,
    shield_plate_module_features,
    socket_point_features,
    screen_bezel_features,
    support_bracket_features,
    strap_attachment_features,
    stair_step_features,
    structural_frame_features,
    silhouette_blade_features,
    silhouette_guard_cowl_features,
    silhouette_handle_features,
    silhouette_outrigger_features,
    silhouette_spine_features,
    silhouette_tower_features,
    silhouette_wing_features,
    trim_band_features,
    trim_strip_features,
    ornament_attachment_features,
    vent_stack_attachment_features,
    vent_grille_features,
    wheel_pair_features,
    wing_module_features,
)
from .fidelity import FidelityProfile
from .geometry_detail import (
    DetailZoneSpec,
    GeometryDetailControls,
    geometry_detail_controls_from_authoring,
)
from .shape_ir import ShapeIR, ShapePrimitive
from .shape_authoring_context import ShapeAuthoringContext, authoring_context_from_asset_graph

HIGH_FEATURE_DENSITY = 0.95

_AUTHORING_FEATURE_TRACE_SCHEMA = "lathe.shape.authoring_feature_trace.v1"


def _bounded_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _feature_kind(feature: ShapePrimitive) -> str:
    return str(feature.component or feature.primitive_type or "feature")


def _feature_tokens(feature: ShapePrimitive) -> str:
    return " ".join(
        [
            _feature_kind(feature),
            str(feature.part or ""),
            str(feature.region or ""),
            *[str(tag) for tag in feature.tags if str(tag)],
        ]
    )


def _feature_matches_authoring(feature: ShapePrimitive, context: ShapeAuthoringContext) -> bool:
    if not context.feature_allow:
        return True
    return context.matches_allowed_feature(
        _feature_kind(feature),
        feature.part,
        feature.region,
        _feature_tokens(feature),
    )


def _feature_density_cap(feature: ShapePrimitive, context: ShapeAuthoringContext) -> int | None:
    multiplier = context.density_multiplier
    if multiplier <= 0.0:
        return 0
    if multiplier >= 1.0:
        return None
    kind = _feature_kind(feature).lower()
    if any(token in kind for token in ("fastener", "bolt", "rivet", "socket")):
        return max(1, int(round(4 * multiplier)))
    if any(token in kind for token in ("vent", "slat", "grille", "rib")):
        return max(1, int(round(3 * multiplier)))
    if any(token in kind for token in ("trim", "frame", "panel", "groove", "ridge")):
        return max(1, int(round(2 * multiplier)))
    return max(1, int(round(2 * multiplier)))


def _annotate_feature_with_authoring(
    feature: ShapePrimitive,
    context: ShapeAuthoringContext,
    *,
    filter_state: str,
) -> None:
    metadata = dict(feature.semantic_metadata or {})
    metadata["authoring_feature"] = {
        "schema": _AUTHORING_FEATURE_TRACE_SCHEMA,
        "filter_state": filter_state,
        "feature_kind": _feature_kind(feature),
        "feature_allow": list(context.feature_allow),
        "feature_density": context.feature_density,
        "density_multiplier": context.density_multiplier,
        "source_paths": list(context.source_paths),
    }
    feature.semantic_metadata = metadata


def _filter_features_by_authoring_context(
    features: list[ShapePrimitive],
    context: ShapeAuthoringContext,
) -> tuple[list[ShapePrimitive], dict[str, Any]]:
    kept: list[ShapePrimitive] = []
    counts_before: dict[str, int] = {}
    counts_after: dict[str, int] = {}
    filtered_by_allow = 0
    filtered_by_density = 0
    for feature in features:
        kind = _feature_kind(feature)
        counts_before[kind] = counts_before.get(kind, 0) + 1
        if not _feature_matches_authoring(feature, context):
            filtered_by_allow += 1
            continue
        cap = _feature_density_cap(feature, context)
        if cap == 0:
            filtered_by_density += 1
            continue
        kept_for_kind = counts_after.get(kind, 0)
        if cap is not None and kept_for_kind >= cap:
            filtered_by_density += 1
            continue
        counts_after[kind] = kept_for_kind + 1
        _annotate_feature_with_authoring(feature, context, filter_state="kept")
        kept.append(feature)
    return kept, {
        "feature_count_before": len(features),
        "feature_count_after": len(kept),
        "filtered_by_feature_allow": filtered_by_allow,
        "filtered_by_density": filtered_by_density,
        "features_by_kind": dict(sorted(counts_before.items())),
        "kept_by_kind": dict(sorted(counts_after.items())),
    }


def _merge_authoring_filter_reports(
    context: ShapeAuthoringContext,
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        "consumed": context.to_dict(),
        "feature_count_before": 0,
        "feature_count_after": 0,
        "filtered_by_feature_allow": 0,
        "filtered_by_density": 0,
        "features_by_kind": {},
        "kept_by_kind": {},
    }
    for report in reports:
        summary["feature_count_before"] += int(report.get("feature_count_before", 0) or 0)
        summary["feature_count_after"] += int(report.get("feature_count_after", 0) or 0)
        summary["filtered_by_feature_allow"] += int(report.get("filtered_by_feature_allow", 0) or 0)
        summary["filtered_by_density"] += int(report.get("filtered_by_density", 0) or 0)
        for field in ("features_by_kind", "kept_by_kind"):
            totals = summary[field]
            values = report.get(field, {})
            if isinstance(values, dict):
                for key, value in values.items():
                    totals[str(key)] = int(totals.get(str(key), 0) or 0) + int(value or 0)
    summary["features_by_kind"] = dict(sorted(summary["features_by_kind"].items()))
    summary["kept_by_kind"] = dict(sorted(summary["kept_by_kind"].items()))
    return summary


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
    feature_count = (
        2
        if fidelity.tier == "blockout"
        else 4
        if fidelity.tier == "game"
        else 6
        if fidelity.tier == "hero"
        else 9
    )

    if component.component_type in {"shell", "body"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(
            trim_band_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        features.extend(
            inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        if density >= 1.0:
            features.extend(
                fastener_strip_features(
                    component,
                    count=min(6, 2 + fidelity.trim_complexity),
                    depth_scale=panel_depth,
                    size_scale=params.trim_scale,
                )
            )
        if _console_like_tokens(asset_graph, component):
            features.extend(
                rib_features(
                    component,
                    count=max(4, feature_count),
                    depth_scale=panel_depth,
                    thickness_scale=edge_scale * 0.85,
                )
            )
        if "plank_displacement" in component.tags:
            # Emit rivets only on the canonical body_shell component
            # (uniquely marked by the ``plank_displacement`` tag in
            # _chest_blueprint). Avoids triplicating across alternate
            # shell components that share the ``body`` tag.
            band_count = 3
            rivets_per_band = 8
            features.extend(
                brass_band_rivets_features(
                    component,
                    band_count=band_count,
                    rivets_per_band=rivets_per_band,
                    band_z_fractions=[-0.34, 0.0, 0.34],
                    radius_scale=params.trim_scale,
                )
            )
    elif component.component_type in {"lid", "door"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        features.extend(
            inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        features.extend(clasp_set_features(component, depth_scale=panel_depth))
        if any(region.component == "hinge" for region in shape_ir.regions):
            features.extend(hinge_set_features(component, depth_scale=panel_depth))
    elif component.component_type in {"frame", "bezel"}:
        features.extend(edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale))
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        if component.component_type == "bezel":
            features.extend(screen_bezel_features(component, depth_scale=panel_depth))
        if density >= 1.0:
            features.extend(
                fastener_strip_features(
                    component,
                    count=min(6, feature_count),
                    depth_scale=panel_depth,
                    size_scale=params.trim_scale,
                )
            )
    elif component.component_type in {"panel", "lock_plate", "latch", "socket_plate", "anchor_plate"}:
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        features.extend(
            inset_panel_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale)
        )
        if density >= HIGH_FEATURE_DENSITY:
            features.extend(
                fastener_strip_features(
                    component,
                    count=min(5, feature_count),
                    depth_scale=panel_depth,
                    size_scale=params.trim_scale,
                )
            )
        if _console_like_tokens(asset_graph, component):
            features.extend(
                trim_band_features(
                    component, depth_scale=panel_depth * 0.9, thickness_scale=params.trim_scale * 0.8
                )
            )
    elif component.component_type in {"handle"}:
        features.extend(recessed_handle_features(component, depth_scale=panel_depth))
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale * 0.8)
        )
    elif component.component_type in {"hinge"}:
        features.extend(hinge_set_features(component, depth_scale=panel_depth))
    elif component.component_type in {"foot", "stand", "bracket"}:
        features.extend(support_bracket_features(component, depth_scale=panel_depth))
        features.extend(
            edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale * 0.85)
        )
        if density >= HIGH_FEATURE_DENSITY:
            features.extend(
                rib_features(
                    component,
                    count=max(3, feature_count - 1),
                    depth_scale=panel_depth,
                    thickness_scale=edge_scale * 0.8,
                )
            )
        if _console_like_tokens(asset_graph, component):
            features.extend(
                fastener_strip_features(
                    component,
                    count=max(4, feature_count),
                    depth_scale=panel_depth,
                    size_scale=params.trim_scale * 0.75,
                )
            )
    elif component.component_type in {"vent", "grille"}:
        features.extend(
            vent_grille_features(component, count=max(5, feature_count + 1), depth_scale=panel_depth)
        )
        features.extend(
            edge_break_features(component, depth_scale=edge_scale * 0.85, thickness_scale=edge_scale * 0.75)
        )
    elif component.component_type in {"rotor_arm"}:
        features.extend(
            rib_features(
                component,
                count=max(3, fidelity.trim_complexity),
                depth_scale=panel_depth,
                thickness_scale=edge_scale,
            )
        )
        features.extend(
            edge_break_features(component, depth_scale=edge_scale, thickness_scale=edge_scale * 0.8)
        )
    elif component.component_type in {"rotor_pod"}:
        features.extend(rotor_shroud_features(component, scale=params.rotor_guard_scale))
        features.extend(
            panel_frame_features(component, depth_scale=panel_depth, thickness_scale=params.trim_scale * 0.7)
        )
    return features


_STYLE_MOTIFS = {
    "brutalist": ("corner_guard", "trim_strip", "bolt_grid", "panel_seam", "linear_detail_array", "guard_bar"),
    "industrial": ("panel_seam", "groove_channel", "bolt_grid", "trim_strip", "socket_point", "rail"),
    "modular": ("socket_point", "bolt_grid", "trim_strip", "linear_detail_array", "rail"),
    "elegant": ("raised_ridge", "layer_plate", "trim_strip", "edge_break"),
    "luxury": ("raised_ridge", "layer_plate", "trim_strip", "radial_detail_array"),
    "organic": ("raised_ridge", "groove_channel", "edge_break", "cable"),
    "prototype": ("socket_point", "panel_seam", "radial_detail_array", "layer_plate", "cable", "vent_stack"),
    "battle_worn": ("panel_seam", "groove_channel", "bolt_grid", "outset_panel", "strap"),
    "architectural": ("arch_frame", "column_set", "stair_step", "structural_frame", "trim_strip"),
    "urban": ("stair_step", "pipe_run", "rail", "panel_seam", "bolt_grid"),
    "vehicle": ("wheel_pair", "hull_keel", "pipe_run", "structural_frame", "raised_ridge"),
    "nautical": ("hull_keel", "pipe_run", "rail", "guard_bar"),
}

_MOTIF_ALIASES = {
    "bevel": "edge_break",
    "chamfer": "edge_break",
    "edge": "edge_break",
    "edge_treatment": "edge_break",
    "panel": "panel_seam",
    "cut_line": "panel_seam",
    "seam": "panel_seam",
    "groove": "groove_channel",
    "channel": "groove_channel",
    "ridge": "raised_ridge",
    "rib": "raised_ridge",
    "layer": "layer_plate",
    "plate": "layer_plate",
    "outset": "outset_panel",
    "inset": "inset_panel",
    "trim": "trim_strip",
    "bolt": "bolt_grid",
    "rivet": "bolt_grid",
    "fastener": "bolt_grid",
    "socket": "socket_point",
    "connector": "socket_point",
    "linear_array": "linear_detail_array",
    "radial_array": "radial_detail_array",
    "rails": "rail",
    "track": "rail",
    "tracks": "rail",
    "fins": "fin",
    "cooling_fin": "fin",
    "straps": "strap",
    "band": "strap",
    "cables": "cable",
    "wire": "cable",
    "wires": "cable",
    "vent": "vent_stack",
    "vents": "vent_stack",
    "handle": "handle_bar",
    "grab_handle": "handle_bar",
    "guard": "guard_bar",
    "guards": "guard_bar",
    "ornament": "ornament",
    "ornaments": "ornament",
    "stair": "stair_step",
    "stairs": "stair_step",
    "steps": "stair_step",
    "tread": "stair_step",
    "arch": "arch_frame",
    "arches": "arch_frame",
    "archway": "arch_frame",
    "portal": "arch_frame",
    "column": "column_set",
    "columns": "column_set",
    "pillar": "column_set",
    "pillars": "column_set",
    "pipe": "pipe_run",
    "pipes": "pipe_run",
    "conduit": "pipe_run",
    "conduits": "pipe_run",
    "wheel": "wheel_pair",
    "wheels": "wheel_pair",
    "tire": "wheel_pair",
    "tyre": "wheel_pair",
    "hull": "hull_keel",
    "keel": "hull_keel",
    "sponson": "hull_keel",
    "frame": "structural_frame",
    "cage": "structural_frame",
    "roll_cage": "structural_frame",
    "support": "support_bracket",
    "supports": "support_bracket",
    "brace": "support_bracket",
    "braces": "support_bracket",
}

_STRUCTURAL_GEOMETRY_MOTIFS = {
    "stair_step",
    "arch_frame",
    "column_set",
    "pipe_run",
    "wheel_pair",
    "hull_keel",
    "structural_frame",
    "support_bracket",
}

_ATTACHMENT_MOTIFS = {
    "rail",
    "fin",
    "strap",
    "cable",
    "vent_stack",
    "handle_bar",
    "guard_bar",
    "ornament",
}

_MODULE_CATEGORY_ALIASES = {
    "sensor": "sensor_pod",
    "sensors": "sensor_pod",
    "sensor_pods": "sensor_pod",
    "pod": "sensor_pod",
    "power": "power_cell",
    "battery": "power_cell",
    "batteries": "power_cell",
    "cell": "power_cell",
    "cells": "power_cell",
    "nozzle": "barrel",
    "barrels": "barrel",
    "muzzle": "barrel",
    "blade": "blade",
    "blades": "blade",
    "tool_head": "blade",
    "wing": "wing",
    "wings": "wing",
    "stabilizer": "wing",
    "stabilizers": "wing",
    "leg": "leg",
    "legs": "leg",
    "stand": "leg",
    "support_leg": "leg",
    "shield": "shield_plate",
    "armor": "shield_plate",
    "armour": "shield_plate",
    "armor_plate": "shield_plate",
    "antenna": "antenna",
    "antennae": "antenna",
    "mast": "antenna",
    "signal_mast": "antenna",
}

_MODULE_CATEGORIES = {
    "sensor_pod",
    "power_cell",
    "barrel",
    "blade",
    "wing",
    "leg",
    "shield_plate",
    "antenna",
}

_SILHOUETTE_PROFILE_MOTIFS = {
    "wide_heavy": ("outrigger", "guard_cowl", "spine"),
    "reinforced_field": ("outrigger", "guard_cowl", "spine"),
    "sleek_winged": ("wing", "spine", "sensor_mast"),
    "ornate_spire": ("spire", "spine", "blade"),
    "tower": ("tower", "spine"),
    "tall": ("tower", "spine"),
    "spined": ("spine", "guard_cowl"),
    "winged": ("wing", "spine"),
    "blade_like": ("blade", "guard_cowl"),
    "tripod": ("outrigger", "tower"),
    "compact": ("guard_cowl",),
}

_SILHOUETTE_MOTIF_ALIASES = {
    "fin": "wing",
    "fins": "wing",
    "side_fin": "wing",
    "side_fins": "wing",
    "wing": "wing",
    "wings": "wing",
    "stabilizer": "wing",
    "stabilizers": "wing",
    "spine": "spine",
    "spines": "spine",
    "dorsal_spine": "spine",
    "tower": "tower",
    "towers": "tower",
    "mast": "tower",
    "masts": "tower",
    "spire": "tower",
    "spires": "tower",
    "sensor_mast": "tower",
    "antenna": "tower",
    "outrigger": "outrigger",
    "outriggers": "outrigger",
    "stance": "outrigger",
    "support": "outrigger",
    "blade": "blade",
    "blades": "blade",
    "tool_head": "blade",
    "handle": "handle",
    "grab_handle": "handle",
    "guard": "guard_cowl",
    "guard_cowl": "guard_cowl",
    "cowl": "guard_cowl",
    "cowling": "guard_cowl",
    "armor_cowl": "guard_cowl",
}

_SILHOUETTE_MOTIFS = {"wing", "spine", "tower", "outrigger", "blade", "handle", "guard_cowl"}


def _token(value: object) -> str:
    return str(value).lower().replace("-", "_").replace(" ", "_").strip()


def _motif_set(values: tuple[str, ...]) -> set[str]:
    motifs: set[str] = set()
    for value in values:
        token = _token(value)
        motifs.add(_MOTIF_ALIASES.get(token, token))
    return motifs


def _module_category_set(values: tuple[str, ...]) -> set[str]:
    categories: set[str] = set()
    for value in values:
        token = _token(value)
        category = _MODULE_CATEGORY_ALIASES.get(token, token)
        if category in _MODULE_CATEGORIES:
            categories.add(category)
    return categories


def _silhouette_motif_set(controls: GeometryDetailControls) -> set[str]:
    motifs: set[str] = set()
    if controls.silhouette_profile:
        profile = _token(controls.silhouette_profile)
        motifs.update(_SILHOUETTE_PROFILE_MOTIFS.get(profile, ()))
    for value in controls.silhouette_motifs:
        token = _token(value)
        motif = _SILHOUETTE_MOTIF_ALIASES.get(token, token)
        if motif in _SILHOUETTE_MOTIFS:
            motifs.add(motif)
    return motifs


def _silhouette_target_ok(component: BlueprintComponent) -> bool:
    tokens = _component_zone_tokens(component)
    return bool(
        tokens
        & {
            "body",
            "shell",
            "core",
            "panel",
            "door",
            "lid",
            "frame",
            "spine",
            "socket",
            "mount",
            "blade",
            "guard",
            "stand",
            "base",
        }
    )


def _component_zone_tokens(component: BlueprintComponent) -> set[str]:
    tokens = {
        _token(component.name),
        _token(component.part),
        _token(component.component_type),
    }
    tokens.update(_token(tag) for tag in component.tags)
    return {token for token in tokens if token}


def _asset_graph_tokens(asset_graph: AssetGraph) -> set[str]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    values: list[object] = [
        asset_graph.family,
        asset_graph.kind,
        asset_graph.role,
        authoring.get("asset_class"),
        authoring.get("style_target"),
        authoring.get("family_ref"),
        authoring.get("from_family"),
    ]
    values.extend(asset_graph.styles)
    values.extend(asset_graph.materials)
    return {_token(value) for value in values if _token(value)}


def _console_like_tokens(asset_graph: AssetGraph, component: BlueprintComponent) -> bool:
    tokens = _component_zone_tokens(component) | _asset_graph_tokens(asset_graph)
    return bool(
        tokens
        & {
            "console",
            "terminal",
            "control",
            "controls",
            "interface",
            "screen",
            "display",
            "bezel",
            "keypad",
            "instrument",
            "dashboard",
        }
    )


def _matches_detail_zone(component: BlueprintComponent, controls: GeometryDetailControls) -> bool:
    if not controls.detail_zones:
        return True
    return bool(set(controls.detail_zones) & _component_zone_tokens(component))


def _matched_zone_specs(
    component: BlueprintComponent, controls: GeometryDetailControls
) -> list[DetailZoneSpec]:
    component_tokens = _component_zone_tokens(component)
    return [zone for zone in controls.zones if zone.name in component_tokens]


def _controlled_geometry_detail_features(
    component: BlueprintComponent,
    controls: GeometryDetailControls,
    params: CandidateParams,
) -> tuple[list[ShapePrimitive], list[dict[str, Any]]]:
    if not controls.active:
        return [], []

    applications: list[dict[str, Any]] = []
    all_features: list[ShapePrimitive] = []
    matched_zones = _matched_zone_specs(component, controls)
    if matched_zones:
        for zone in matched_zones:
            features, application = _detail_features_for_scope(component, controls, params, zone=zone)
            if features:
                all_features.extend(features)
                applications.append(application)
        return all_features, applications

    if not _matches_detail_zone(component, controls):
        return [], []
    features, application = _detail_features_for_scope(component, controls, params, zone=None)
    return features, [application] if features else []


def _detail_features_for_scope(
    component: BlueprintComponent,
    controls: GeometryDetailControls,
    params: CandidateParams,
    *,
    zone: DetailZoneSpec | None,
) -> tuple[list[ShapePrimitive], dict[str, Any]]:
    density = max(0.0, _zone_float(zone, "density", controls.detail_density))
    style_motifs = _style_motif_set(controls)
    motifs = _motif_set(zone.motifs if zone and zone.motifs else controls.detail_motifs) | style_motifs
    attachment_motifs = (
        _motif_set(zone.attachment_motifs if zone and zone.attachment_motifs else controls.attachment_motifs)
        | (motifs & _ATTACHMENT_MOTIFS)
    )
    module_categories = _module_category_set(
        zone.module_categories if zone and zone.module_categories else controls.module_categories
    )
    silhouette_motifs = _silhouette_motif_set(controls)
    falloff = zone.falloff if zone else "uniform"
    edge_bias = 1.25 if falloff in {"edge", "edges", "perimeter", "corners"} else 1.0
    center_bias = 1.20 if falloff in {"center", "face", "middle"} else 1.0
    style_density = _style_density_multiplier(controls)
    density *= style_density

    depth_scale = max(0.45, params.panel_depth * max(0.35, density))
    thickness_scale = max(0.45, params.trim_scale * max(0.35, density))
    edge_scale = max(0.0, _zone_float(zone, "edge_complexity", controls.edge_complexity))
    panel_count = _motif_count(
        "panel_seam",
        motifs,
        _zone_float(zone, "panelization", controls.panelization),
        density * center_bias,
        base=1,
        limit=8,
    )
    groove_count = _motif_count(
        "groove_channel",
        motifs,
        _zone_float(zone, "groove_density", controls.groove_density),
        density,
        base=0,
        limit=8,
    )
    ridge_count = _motif_count(
        "raised_ridge",
        motifs,
        _zone_float(zone, "ridge_density", controls.ridge_density),
        density,
        base=0,
        limit=8,
    )
    greeble_count = _motif_count(
        "bolt_grid",
        motifs,
        _zone_float(zone, "greeble_density", controls.greeble_density),
        density * edge_bias,
        base=0,
        limit=14,
    )
    trim_count = _motif_count(
        "trim_strip",
        motifs,
        _zone_float(zone, "trim_density", controls.trim_density),
        density * edge_bias,
        base=0,
        limit=8,
    )
    inset_count = _motif_count(
        "inset_panel",
        motifs,
        _zone_float(zone, "inset_depth", controls.inset_depth),
        density * center_bias,
        base=0,
        limit=4,
    )
    outset_count = _motif_count(
        "outset_panel",
        motifs,
        _zone_float(zone, "outset_depth", controls.outset_depth),
        density * center_bias,
        base=0,
        limit=6,
    )
    layer_count = min(5, _zone_int(zone, "surface_layer_count", controls.surface_layer_count))
    socket_count = min(
        10,
        _zone_int(zone, "modular_attachment_points", controls.modular_attachment_points)
        + len(controls.module_sockets),
    )
    linear_count = min(10, _zone_int(zone, "linear_detail_repeats", controls.linear_detail_repeats))
    radial_count = min(12, _zone_int(zone, "radial_detail_repeats", controls.radial_detail_repeats))
    attachment_count = min(10, _zone_int(zone, "attachment_count", controls.attachment_count))
    if attachment_motifs and attachment_count <= 0:
        attachment_count = min(6, max(2, int(round(density * 2.0))))
    module_count = min(8, _zone_int(zone, "module_count", controls.module_count))
    if module_categories and module_count <= 0:
        module_count = min(5, max(1, int(round(density * 1.75))))
    silhouette_count = min(4, max(1, int(round(max(density, 0.5) * controls.silhouette_intensity))))
    array_axis = _zone_str(zone, "detail_array_axis", controls.detail_array_axis)

    features: list[ShapePrimitive] = []
    if edge_scale >= 0.65 or motifs & {"edge_break", "corner_guard"}:
        features.extend(
            corner_guard_features(
                component,
                depth_scale=depth_scale,
                thickness_scale=max(0.55, edge_scale * edge_bias),
            )
        )
    if edge_scale >= 1.25 or "edge_break" in motifs:
        features.extend(
            edge_break_features(
                component,
                depth_scale=depth_scale * min(max(edge_scale, 1.0), 1.9),
                thickness_scale=thickness_scale * min(max(edge_scale, 1.0), 1.9),
            )
        )
    if panel_count > 0:
        features.extend(panel_seam_features(component, count=panel_count, depth_scale=depth_scale))
    if trim_count > 0:
        features.extend(
            trim_strip_features(
                component,
                count=trim_count,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if inset_count > 0:
        for _index in range(inset_count):
            features.extend(inset_panel_features(component, depth_scale=depth_scale, thickness_scale=thickness_scale))
    if outset_count > 0:
        features.extend(outset_panel_features(component, count=outset_count, depth_scale=depth_scale))
    if layer_count > 0:
        features.extend(layer_plate_features(component, count=layer_count, depth_scale=depth_scale))
    if groove_count > 0:
        features.extend(groove_channel_features(component, count=groove_count, depth_scale=depth_scale))
    if ridge_count > 0:
        features.extend(
            raised_ridge_features(
                component,
                count=ridge_count,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if socket_count > 0:
        features.extend(socket_point_features(component, count=socket_count, depth_scale=depth_scale))
    if greeble_count > 0:
        features.extend(bolt_grid_features(component, count=greeble_count, depth_scale=depth_scale))
    if linear_count > 0:
        features.extend(
            linear_detail_array_features(
                component,
                count=linear_count,
                axis=array_axis,
                depth_scale=depth_scale,
            )
        )
    if radial_count > 0:
        features.extend(radial_detail_array_features(component, count=radial_count, depth_scale=depth_scale))
    if attachment_motifs:
        features.extend(
            _attachment_motif_features(
                component,
                attachment_motifs=attachment_motifs,
                count=attachment_count,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    structural_motifs = motifs & _STRUCTURAL_GEOMETRY_MOTIFS
    if structural_motifs:
        features.extend(
            _structural_geometry_motif_features(
                component,
                structural_motifs=structural_motifs,
                count=max(2, int(round(density * 3.0))),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if module_categories:
        features.extend(
            _module_category_features(
                component,
                module_categories=module_categories,
                count=module_count,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if silhouette_motifs:
        features.extend(
            _silhouette_motif_features(
                component,
                silhouette_motifs=silhouette_motifs,
                count=silhouette_count,
                depth_scale=depth_scale * max(0.75, controls.silhouette_intensity),
                thickness_scale=thickness_scale * max(0.75, controls.silhouette_intensity),
            )
        )

    _tag_controlled_features(features, controls, zone)
    application = {
        "zone": zone.name if zone else "global",
        "target": component.name,
        "part": component.part,
        "component": component.component_type,
        "motifs": sorted(motifs),
        "attachment_motifs": sorted(attachment_motifs),
        "module_categories": sorted(module_categories),
        "silhouette_profile": controls.silhouette_profile,
        "silhouette_motifs": sorted(silhouette_motifs),
        "falloff": falloff,
        "feature_count": len(features),
    }
    return features, application


def _structural_geometry_motif_features(
    component: BlueprintComponent,
    *,
    structural_motifs: set[str],
    count: int,
    depth_scale: float,
    thickness_scale: float,
) -> list[ShapePrimitive]:
    features: list[ShapePrimitive] = []
    local_count = max(1, count)
    if "stair_step" in structural_motifs:
        features.extend(stair_step_features(component, count=min(10, max(3, local_count)), depth_scale=depth_scale))
    if "arch_frame" in structural_motifs:
        features.extend(
            arch_opening_features(component, depth_scale=depth_scale, thickness_scale=thickness_scale)
        )
    if "column_set" in structural_motifs:
        features.extend(column_set_features(component, count=min(6, max(2, local_count)), depth_scale=depth_scale))
    if "pipe_run" in structural_motifs:
        features.extend(pipe_run_features(component, count=min(7, max(2, local_count)), depth_scale=depth_scale))
    if "wheel_pair" in structural_motifs:
        features.extend(
            wheel_pair_features(component, count=min(4, max(1, local_count // 2)), depth_scale=depth_scale)
        )
    if "hull_keel" in structural_motifs:
        features.extend(hull_keel_features(component, depth_scale=depth_scale, thickness_scale=thickness_scale))
    if "structural_frame" in structural_motifs:
        features.extend(
            structural_frame_features(component, depth_scale=depth_scale, thickness_scale=thickness_scale)
        )
    if "support_bracket" in structural_motifs:
        features.extend(support_bracket_features(component, depth_scale=depth_scale))
    return features


def _silhouette_motif_features(
    component: BlueprintComponent,
    *,
    silhouette_motifs: set[str],
    count: int,
    depth_scale: float,
    thickness_scale: float,
) -> list[ShapePrimitive]:
    if not _silhouette_target_ok(component):
        return []
    features: list[ShapePrimitive] = []
    local_count = max(1, count)
    if "spine" in silhouette_motifs:
        features.extend(
            silhouette_spine_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "wing" in silhouette_motifs:
        features.extend(
            silhouette_wing_features(
                component,
                count=min(3, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "tower" in silhouette_motifs:
        features.extend(
            silhouette_tower_features(
                component,
                count=min(3, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "outrigger" in silhouette_motifs:
        features.extend(
            silhouette_outrigger_features(
                component,
                count=min(3, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "blade" in silhouette_motifs:
        features.extend(
            silhouette_blade_features(
                component,
                count=min(3, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "handle" in silhouette_motifs:
        features.extend(
            silhouette_handle_features(
                component,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "guard_cowl" in silhouette_motifs:
        features.extend(
            silhouette_guard_cowl_features(
                component,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    return features


def _module_category_features(
    component: BlueprintComponent,
    *,
    module_categories: set[str],
    count: int,
    depth_scale: float,
    thickness_scale: float,
) -> list[ShapePrimitive]:
    features: list[ShapePrimitive] = []
    local_count = max(1, count)
    if "sensor_pod" in module_categories:
        features.extend(
            sensor_pod_module_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "power_cell" in module_categories:
        features.extend(power_cell_module_features(component, count=min(5, local_count), depth_scale=depth_scale))
    if "barrel" in module_categories:
        features.extend(barrel_module_features(component, count=min(4, local_count), depth_scale=depth_scale))
    if "blade" in module_categories:
        features.extend(
            blade_module_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "wing" in module_categories:
        features.extend(
            wing_module_features(
                component,
                count=min(3, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "leg" in module_categories:
        features.extend(leg_module_features(component, count=min(4, local_count), depth_scale=depth_scale))
    if "shield_plate" in module_categories:
        features.extend(
            shield_plate_module_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "antenna" in module_categories:
        features.extend(antenna_module_features(component, count=min(4, local_count), depth_scale=depth_scale))
    return features


def _attachment_motif_features(
    component: BlueprintComponent,
    *,
    attachment_motifs: set[str],
    count: int,
    depth_scale: float,
    thickness_scale: float,
) -> list[ShapePrimitive]:
    features: list[ShapePrimitive] = []
    local_count = max(1, count)
    if "rail" in attachment_motifs:
        features.extend(
            rail_attachment_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "fin" in attachment_motifs:
        features.extend(
            fin_attachment_features(
                component,
                count=min(8, max(3, local_count)),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "strap" in attachment_motifs:
        features.extend(
            strap_attachment_features(
                component,
                count=min(4, local_count),
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "cable" in attachment_motifs:
        features.extend(cable_attachment_features(component, count=min(5, local_count), depth_scale=depth_scale))
    if "vent_stack" in attachment_motifs:
        features.extend(
            vent_stack_attachment_features(
                component,
                count=min(7, max(3, local_count)),
                depth_scale=depth_scale,
            )
        )
    if "handle_bar" in attachment_motifs:
        features.extend(
            handle_bar_attachment_features(
                component,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "guard_bar" in attachment_motifs:
        features.extend(
            guard_bar_attachment_features(
                component,
                depth_scale=depth_scale,
                thickness_scale=thickness_scale,
            )
        )
    if "ornament" in attachment_motifs:
        features.extend(
            ornament_attachment_features(
                component,
                count=min(10, max(4, local_count)),
                depth_scale=depth_scale,
            )
        )
    return features


def _style_motif_set(controls: GeometryDetailControls) -> set[str]:
    motifs: set[str] = set()
    for style in controls.style_modifiers:
        motifs.update(_STYLE_MOTIFS.get(style, ()))
    return motifs


def _style_density_multiplier(controls: GeometryDetailControls) -> float:
    if not controls.style_modifiers:
        return 1.0
    multiplier = 1.0
    if any(style in controls.style_modifiers for style in ("brutalist", "industrial", "prototype")):
        multiplier += 0.18
    if any(style in controls.style_modifiers for style in ("luxury", "hero")):
        multiplier += 0.12
    if any(style in controls.style_modifiers for style in ("architectural", "urban", "vehicle", "nautical")):
        multiplier += 0.16
    if "organic" in controls.style_modifiers:
        multiplier -= 0.08
    return max(0.7, multiplier)


def _motif_count(
    motif: str, motifs: set[str], control_value: float, density: float, *, base: int, limit: int
) -> int:
    effective = control_value
    if motif in motifs and effective <= 0.0:
        effective = 1.0
    return _detail_count(effective, density, base=base, limit=limit)


def _detail_count(control_value: float, density: float, *, base: int, limit: int) -> int:
    if control_value <= 0.0 or density <= 0.0:
        return 0
    return min(limit, max(0, int(round(base + control_value * density * 2.0))))


def _zone_float(zone: DetailZoneSpec | None, field: str, fallback: float) -> float:
    if zone is None:
        return fallback
    value = getattr(zone, field)
    return fallback if value is None else float(value)


def _zone_int(zone: DetailZoneSpec | None, field: str, fallback: int) -> int:
    if zone is None:
        return fallback
    value = getattr(zone, field)
    return fallback if value is None else int(value)


def _zone_str(zone: DetailZoneSpec | None, field: str, fallback: str) -> str:
    if zone is None:
        return fallback
    value = getattr(zone, field)
    return fallback if not value else str(value)


def _tag_controlled_features(
    features: list[ShapePrimitive], controls: GeometryDetailControls, zone: DetailZoneSpec | None
) -> None:
    edge_treatment = _zone_str(zone, "edge_treatment", controls.edge_treatment)
    edge_hardness = _zone_str(zone, "edge_hardness", controls.edge_hardness)
    bevel_width = _zone_float(zone, "bevel_width", controls.bevel_width)
    chamfer_width = _zone_float(zone, "chamfer_width", controls.chamfer_width)
    zone_tags = ["detail_zone", f"zone_{zone.name}"] if zone else []
    pack_tags = [f"style_pack_{style_pack}" for style_pack in controls.style_packs]
    style_tags = [f"style_{style}" for style in controls.style_modifiers]
    silhouette_tags = (
        [f"silhouette_profile_{controls.silhouette_profile}"] if controls.silhouette_profile else []
    )
    module_tags = [f"module_socket_{socket}" for socket in controls.module_sockets[:4]]
    edge_tags = [
        f"edge_treatment_{edge_treatment}",
        f"edge_hardness_{edge_hardness}",
    ]
    if bevel_width > 0.0:
        edge_tags.append("bevel_width_authored")
    if chamfer_width > 0.0:
        edge_tags.append("chamfer_width_authored")
    rounding = max(bevel_width, chamfer_width, 0.0)
    for feature in features:
        for tag in [
            "surface_detail",
            *zone_tags,
            *pack_tags,
            *style_tags,
            *silhouette_tags,
            *module_tags,
            *edge_tags,
        ]:
            if tag and tag not in feature.tags:
                feature.tags.append(tag)
        if rounding > 0.0:
            feature.rounding = max(feature.rounding, min(rounding, 2.5))


_MULTI_OCTAVE_PRIMARY_KINDS = {
    # Additive primaries that read as raised hardware where rivets/fasteners
    # belong. Subtractive features (inset_panel, panel_seam, vent slats) are
    # deliberately excluded — putting rivets inside a recess or cut line is
    # architecturally wrong.
    "frame_lip",
    "trim_band",
    "trim_strip",
    "outset_panel",
    "layer_plate",
    "screen_bezel",
    "corner_guard",
    "raised_ridge",
    "support_bracket",
    "hull_keel",
    "structural_frame",
}


def _polygon_extents(polygon: list[tuple[float, float]] | None) -> tuple[float, float]:
    if not polygon:
        return 0.0, 0.0
    us = [p[0] for p in polygon]
    vs = [p[1] for p in polygon]
    return (max(us) - min(us)), (max(vs) - min(vs))


def _axis_local_to_world(axis: str) -> tuple[str, str, str]:
    """Return (u_axis, v_axis, h_axis) world-axis labels for a local extrude axis.

    Convention matches _chamfered_rectangle_polygon + _feature_extruded_profile:
    polygon (u, v) lives in the plane perpendicular to ``axis``; ``extrude_height``
    sweeps along ``axis``.
    """
    if axis == "z":
        return ("x", "y", "z")
    if axis == "x":
        return ("y", "z", "x")
    return ("z", "x", "y")  # axis == "y"


def _offset_along_axis(
    center: tuple[float, float, float], axis: str, delta: float
) -> tuple[float, float, float]:
    cx, cy, cz = center
    if axis == "x":
        return (cx + delta, cy, cz)
    if axis == "y":
        return (cx, cy + delta, cz)
    return (cx, cy, cz + delta)


def _rivet_primitive(
    parent: ShapePrimitive,
    *,
    center: tuple[float, float, float],
    radius: float,
    depth: float,
    axis: str,
    octave: str,
    kind: str,
) -> ShapePrimitive:
    half_depth = max(depth * 0.5, radius * 0.18, 0.001)
    profile_points = [
        (-half_depth, radius * 0.82),
        (-half_depth * 0.18, radius),
        (half_depth * 0.48, radius * 0.74),
        (half_depth, radius * 0.18),
    ]
    parent_kind = parent.component or "feature"
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=parent.part,
        center=center,
        axis=axis,
        profile_points=profile_points,
        tags=[
            "feature",
            kind,
            "multi_octave",
            f"octave_{octave}",
            f"parent_{parent_kind}",
            "mesh_op_revolved_profile",
        ],
        component=kind,
        region=parent.region,
        blend_mode="union",
    )


def _multi_octave_features(
    parent_features: list[ShapePrimitive],
    fidelity_tier: str,
    asset_graph: AssetGraph | None = None,
    authoring_context: ShapeAuthoringContext | None = None,
) -> list[ShapePrimitive]:
    """Spawn high-frequency secondary detail (rivets, fasteners) over large primary features.

    For each primary feature whose ``component`` is in
    :data:`_MULTI_OCTAVE_PRIMARY_KINDS`, sample N small rivets along the
    feature's longest local axis. For ``cinematic`` tier, optionally
    emit a tiny tertiary micro-bevel below each rivet head to push the
    surface up another octave.

    Per-tier defaults (after Wave 2A gate retune):
      blockout/game: 0 (skip entirely)
      hero: 0 by default; opt-in via ``features { density = "high" }``
            adds 2 secondaries per primary so authors can request dense
            detail without inflating uniformity-based validators by default
      cinematic: 6 secondaries per primary (was 12), with one tertiary
            micro-bevel per secondary
    """
    if fidelity_tier not in {"hero", "cinematic"}:
        return []

    if authoring_context is None and asset_graph is not None:
        authoring_context = authoring_context_from_asset_graph(asset_graph)
    feature_density = (
        str(authoring_context.feature_density or "").lower()
        if authoring_context is not None
        else ""
    )
    density_multiplier = (
        float(authoring_context.density_multiplier)
        if authoring_context is not None
        else 1.0
    )

    if fidelity_tier == "hero":
        # Hero defaults to clean game-ready surfaces. Multi-octave detail is
        # opt-in via an authored high/hero/dense feature-density request.
        if feature_density not in {"high", "hero", "dense", "ultra"} and density_multiplier < 1.25:
            return []
        secondary_target = max(2, min(5, int(round(2 * density_multiplier))))
        tertiary_per_secondary = 0
    else:
        # cinematic: still visibly richer than hero, but tuned down from
        # the original 12-per-primary which inflated surface variance metrics.
        secondary_target = max(4, min(8, int(round(4 * density_multiplier))))
        tertiary_per_secondary = 1

    octave: list[ShapePrimitive] = []
    for parent in parent_features:
        if (parent.component or "") not in _MULTI_OCTAVE_PRIMARY_KINDS:
            continue
        # Estimate parent's footprint and longest local axis.
        if parent.primitive_type == "extruded_profile" and parent.profile_polygon:
            u_span, v_span = _polygon_extents(parent.profile_polygon)
            h_span = float(parent.extrude_height or 0.0)
            u_axis, v_axis, h_axis = _axis_local_to_world(parent.axis or "y")
            spans = [(u_span, u_axis), (v_span, v_axis), (h_span, h_axis)]
        elif parent.primitive_type in {"box", "subdivision_box"} and parent.extents:
            ex, ey, ez = parent.extents
            spans = [(ex, "x"), (ey, "y"), (ez, "z")]
        else:
            continue

        spans.sort(key=lambda item: item[0], reverse=True)
        long_span, long_axis = spans[0]
        short_span, _ = spans[1] if len(spans) > 1 else (long_span, long_axis)
        if long_span <= 0.4:
            continue

        # Rivet count scales with the primary's length.
        density_factor = min(1.4, max(0.5, long_span / 8.0))
        rivet_count = max(2, min(secondary_target, int(round(secondary_target * density_factor))))

        # Rivet size: tiny relative to short span and long span.
        rivet_radius = max(min(short_span * 0.18, long_span * 0.04, 0.40), 0.10)
        rivet_depth = max(rivet_radius * 1.05, 0.10)

        # Rivet axis: spawn rivets oriented outward along the parent's
        # extrusion/normal axis when known; for box-like parents use the
        # shortest dimension as the proud-out direction.
        if parent.primitive_type == "extruded_profile":
            rivet_axis = parent.axis or "y"
        else:
            shortest = min(spans, key=lambda item: item[0])
            rivet_axis = shortest[1]

        if rivet_count > 1:
            spacing = long_span * 0.78 / (rivet_count - 1)
            start = -spacing * (rivet_count - 1) / 2.0
        else:
            spacing = 0.0
            start = 0.0

        for index in range(rivet_count):
            delta = start + spacing * index
            center = _offset_along_axis(parent.center, long_axis, delta)
            rivet = _rivet_primitive(
                parent,
                center=center,
                radius=rivet_radius,
                depth=rivet_depth,
                axis=rivet_axis,
                octave="secondary",
                kind="multi_octave_rivet",
            )
            octave.append(rivet)

            for _t in range(tertiary_per_secondary):
                tertiary_radius = max(rivet_radius * 0.45, 0.05)
                tertiary_depth = max(rivet_depth * 0.55, 0.05)
                tertiary_center = _offset_along_axis(center, rivet_axis, -rivet_depth * 0.35)
                octave.append(
                    _rivet_primitive(
                        parent,
                        center=tertiary_center,
                        radius=tertiary_radius,
                        depth=tertiary_depth,
                        axis=rivet_axis,
                        octave="tertiary",
                        kind="multi_octave_micro_bevel",
                    )
                )

    return octave


def compile_feature_enhancements(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    *,
    fidelity: FidelityProfile,
    params: CandidateParams,
) -> tuple[ShapeIR, dict[str, Any]]:
    """Compile feature enhancements.

    Args:
        asset_graph: asset_graph argument.
        shape_ir: shape_ir argument.
        fidelity: fidelity argument.
        params: params argument.

    Returns:
        The result.
    """
    enriched = deepcopy(shape_ir)
    added = []
    geometry_detail_added = []
    geometry_detail_applications: list[dict[str, Any]] = []
    feature_ops_used: set[str] = set()
    multi_octave_added: list[ShapePrimitive] = []
    authoring_filter_reports: list[dict[str, Any]] = []
    authoring_context = authoring_context_from_asset_graph(asset_graph)
    effective_params = replace(
        params,
        feature_density=_bounded_float(
            params.feature_density * authoring_context.density_multiplier,
            0.0,
            3.0,
        ),
    )
    geometry_detail_controls = geometry_detail_controls_from_authoring(asset_graph.authoring)
    for region in shape_ir.regions:
        component = _component_from_region(shape_ir, region.name)
        if component is None:
            continue
        features = _shape_component_features(asset_graph, shape_ir, component, fidelity, effective_params)
        controlled_features, controlled_applications = _controlled_geometry_detail_features(
            component, geometry_detail_controls, effective_params
        )
        features.extend(controlled_features)
        octave_features = _multi_octave_features(
            features,
            fidelity.tier,
            asset_graph,
            authoring_context=authoring_context,
        )
        if octave_features:
            features.extend(octave_features)
        features, authoring_report = _filter_features_by_authoring_context(features, authoring_context)
        authoring_filter_reports.append(authoring_report)
        kept_ids = {id(feature) for feature in features}
        kept_controlled_features = [
            feature for feature in controlled_features if id(feature) in kept_ids
        ]
        kept_octave_features = [
            feature for feature in octave_features if id(feature) in kept_ids
        ]
        if kept_controlled_features:
            geometry_detail_added.extend(kept_controlled_features)
            geometry_detail_applications.extend(controlled_applications)
        if kept_octave_features:
            multi_octave_added.extend(kept_octave_features)
        if not features:
            continue
        added.extend(features)
        feature_ops_used.update({feature.component or "feature" for feature in features})
    enriched.primitives.extend(added)
    enriched = refresh_shape_ir(
        asset_graph,
        enriched,
        notes=[
            *list(shape_ir.signature.get("blueprint_notes", [])),
            f"fidelity={fidelity.tier}",
            f"feature_density={effective_params.feature_density:.3f}",
        ],
    )
    authoring_consumption = _merge_authoring_filter_reports(authoring_context, authoring_filter_reports)
    enriched.signature["authoring_context"] = authoring_context.to_dict()
    enriched.signature["authoring_feature_consumption"] = authoring_consumption
    enriched.assessment["authoring_feature_count_before"] = int(
        authoring_consumption["feature_count_before"]
    )
    enriched.assessment["authoring_feature_count_after"] = int(
        authoring_consumption["feature_count_after"]
    )
    enriched.assessment["authoring_features_filtered"] = int(
        authoring_consumption["filtered_by_feature_allow"]
        + authoring_consumption["filtered_by_density"]
    )
    geometry_detail_feature_types = sorted(
        {feature.component or "feature" for feature in geometry_detail_added}
    )
    if geometry_detail_controls.explicit_fields:
        enriched.signature["geometry_detail_controls"] = geometry_detail_controls.to_dict()
        enriched.assessment["geometry_detail_feature_count"] = len(geometry_detail_added)
        enriched.assessment["geometry_detail_feature_types"] = geometry_detail_feature_types
        if geometry_detail_applications:
            enriched.assessment["geometry_detail_zones_applied"] = geometry_detail_applications
    report = {
        "fidelity": fidelity.to_dict(),
        "candidate_params": params.to_dict(),
        "effective_candidate_params": effective_params.to_dict(),
        "authoring_context": authoring_context.to_dict(),
        "authoring_feature_consumption": authoring_consumption,
        "feature_ops_used": sorted(feature_ops_used),
        "feature_count_added": len(added),
    }
    if multi_octave_added:
        secondary = sum(1 for f in multi_octave_added if "octave_secondary" in f.tags)
        tertiary = sum(1 for f in multi_octave_added if "octave_tertiary" in f.tags)
        report["multi_octave_feature_count"] = len(multi_octave_added)
        report["multi_octave_secondary_count"] = secondary
        report["multi_octave_tertiary_count"] = tertiary
        enriched.assessment["multi_octave_feature_count"] = len(multi_octave_added)
    if geometry_detail_controls.explicit_fields:
        report["geometry_detail_controls"] = geometry_detail_controls.to_dict()
        report["geometry_detail_feature_count"] = len(geometry_detail_added)
        report["geometry_detail_feature_types"] = geometry_detail_feature_types
        report["geometry_detail_zones_applied"] = geometry_detail_applications
    return enriched, report
