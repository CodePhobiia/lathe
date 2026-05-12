"""Primitive selector for routing component intent to richer ShapeIR solids.

The assembly builders are intentionally conservative and component-local.
This module adds a thin semantic routing layer above them: it looks at the
component type plus creative/style controls and upgrades obvious box/cylinder
approximations into richer primitives already supported by the stable ShapeIR
handoff.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .shape_ir import ShapePrimitive


_ROUND_BAR_COMPONENTS = {
    "access_ladder",
    "guardrail",
    "mast",
    "rigging",
    "scaffold_frame",
    "safety_gate",
}
_ROUND_BAR_TAGS = {
    "crossbar",
    "deck_tie",
    "fore_aft_stay",
    "front_left_pole",
    "front_right_pole",
    "hinge_post",
    "latch_handle",
    "latch_post",
    "left_post",
    "left_side_rail",
    "lower_crossbar",
    "mid_rail",
    "rear_left_pole",
    "rear_right_pole",
    "right_post",
    "right_side_rail",
    "rung",
    "standing_line",
    "top_bar",
    "top_rail",
    "upper_crossbar",
}
_RING_CYLINDER_TAGS = {
    "anchor_ring",
    "left_coupler",
    "muzzle_ring",
    "right_coupler",
    "thrust_ring",
    "turret_ring",
}
_LATHED_PLATE_TAGS = {"base", "capital", "base_plate", "top_plate"}
_ROOF_BOX_TAGS = {
    "dormer_roof",
    "left_roof_plane",
    "ridge_cap",
    "ridge_mass",
    "right_roof_plane",
    "roof_cap",
    "roof_peak",
    "roof_plate",
}
_SOFT_VOLUME_COMPONENTS = {
    "appliance_body",
    "body",
    "cabinet_body",
    "cabin",
    "cargo_bay",
    "cargo_module",
    "chassis",
    "deck",
    "duct_run",
    "furniture_base",
    "hull",
    "junction_box",
    "kiosk_body",
    "magazine",
    "pontoon",
    "service_rail",
    "stock",
    "street_crate",
    "track",
    "transformer_box",
    "trash_bin",
    "weapon_body",
}
_SOFT_VOLUME_TAGS = {
    "bin_body",
    "body",
    "cabinet_body",
    "cargo_bay_volume",
    "cargo_shell",
    "crate_body",
    "duct_body",
    "float_body",
    "floor_footprint",
    "hull",
    "junction_body",
    "kiosk_body",
    "magazine_body",
    "receiver_core",
    "rail_body",
    "service_body",
    "stock_body",
    "track_belt",
    "transformer_body",
}
_EXTRUDED_PANEL_TAGS = {
    "bow",
    "butt_pad",
    "cargo_hatch",
    "cargo_lid",
    "floorplate",
    "keel",
    "lower_receiver",
    "magazine_floorplate",
    "raised_deck",
    "stock_body",
    "top_rail",
    "track_shoe",
    "underbarrel_rail",
    "underframe",
    "upper_collar",
    "upper_run",
    "lower_collar",
    "center_block",
    "trigger_guard",
}
_TERRAIN_VOLUME_COMPONENTS = {"terrain", "ground", "ridge", "cliff", "terrain_platform"}
_FACADE_PANEL_COMPONENTS = {
    "door",
    "frame",
    "panel",
    "parapet",
    "wall",
    "window",
}
_FACADE_PANEL_TAGS = {
    "door_slab",
    "face",
    "front_face",
    "lintel",
    "mullion",
    "partition_lintel",
    "partition_wall",
    "panel",
    "wall",
    "window_frame",
    "window_cutout",
}
_ROAD_SURFACE_COMPONENTS = {
    "crosswalk",
    "curb_ramp",
    "lane_arrow",
    "median",
    "path",
    "road",
    "road_branch",
    "road_junction",
    "roundabout",
    "stop_line",
    "street",
    "turnout",
}
_ROAD_SURFACE_TAGS = {
    "apron",
    "crosswalk_pad",
    "junction_pad",
    "median_body",
    "paint",
    "road_surface",
    "roundabout_pad",
    "turnout_pad",
}
_VEGETATION_RUNNER_COMPONENTS = {
    "fallen_log",
    "root",
    "tree_branch",
    "tree_trunk",
    "vine",
}
_VEGETATION_RUNNER_TAGS = {
    "bark_ridge",
    "branch",
    "log_body",
    "root_runner",
    "trunk_core",
    "vine_line",
}
_MACHINE_VOLUME_COMPONENTS = {
    "conveyor",
    "crane_boom",
    "gear",
    "hydraulic_piston",
    "machine_base",
    "machine_column",
    "tank",
}
_FURNITURE_PANEL_COMPONENTS = {
    "cabinet_body",
    "chair_back",
    "chair_seat",
    "counter_top",
    "drawer",
    "shelf_unit",
    "table_top",
}
_FURNITURE_PANEL_TAGS = {
    "apron",
    "back_panel",
    "cabinet_front",
    "drawer_front",
    "inset",
    "seat_panel",
    "shelf_board",
    "table_surface",
    "top_panel",
}
_CHEST_VOLUME_COMPONENTS = {
    "shell",
    "body",
    "lid",
}
_CHEST_PANEL_COMPONENTS = {
    "clasp_set",
    "door",
    "fastener_strip",
    "frame",
    "inset_panel",
    "latch",
    "lock_plate",
    "trim_band",
}
_CHEST_PANEL_TAGS = {
    "brass",
    "clasp",
    "door",
    "fastener",
    "front",
    "frame",
    "hatch",
    "inset",
    "latch",
    "lid_break",
    "lock",
    "panel",
    "plate",
    "rear",
    "strap",
    "trim",
}
_CHEST_BARREL_COMPONENTS = {
    "hinge",
}
_CHEST_SELECTOR_FAMILIES = {
    "brassbound_chest",
    "industrial_crate",
    "supply_container",
}
_CHEST_SELECTOR_TOKENS = {
    "brassbound",
    "chest",
    "crate",
    "loot",
    "supply_container",
}

# --- courier_drone family --------------------------------------------------
_DRONE_SELECTOR_FAMILIES = {"courier_drone", "courier_drone_family"}
_DRONE_SELECTOR_TOKENS = {"drone", "courier", "rotorcraft"}
_DRONE_VOLUME_COMPONENTS = {"shell", "body", "chassis", "cabin", "cargo_bay", "cargo_module"}
_DRONE_PANEL_COMPONENTS = {"door", "panel", "frame", "trim_band", "inset_panel"}
_DRONE_LATHED_COMPONENTS = {"rotor_pod", "engine", "thruster", "wheel", "sensor", "sensor_pod"}
_DRONE_SWEPT_COMPONENTS = {"antenna", "rigging", "rotor_arm", "wing", "stabilizer", "strut", "landing_leg"}

# --- mechanical_door family ------------------------------------------------
_DOOR_SELECTOR_FAMILIES = {"mechanical_door", "mechanical_door_family"}
_DOOR_SELECTOR_TOKENS = {"airlock", "door", "mechanical_door"}
_DOOR_VOLUME_COMPONENTS = {"shell", "body"}
_DOOR_PANEL_COMPONENTS = {
    "door",
    "frame",
    "panel",
    "lock_plate",
    "bezel",
    "bracket",
    "latch",
    "trim_band",
    "inset_panel",
    "fastener_strip",
}
_DOOR_BARREL_COMPONENTS = {"hinge", "bolt"}
_DOOR_PANEL_TAGS = {
    "door",
    "frame",
    "panel",
    "plate",
    "lock",
    "latch",
    "threshold",
    "screen",
    "bracket",
    "mount",
}

# --- console_terminal family -----------------------------------------------
_CONSOLE_SELECTOR_FAMILIES = {"console_terminal", "console_terminal_family"}
_CONSOLE_SELECTOR_TOKENS = {"console", "terminal", "kiosk"}
_CONSOLE_VOLUME_COMPONENTS = {"shell", "body", "stand"}
_CONSOLE_PANEL_COMPONENTS = {
    "panel",
    "frame",
    "bezel",
    "socket_plate",
    "vent",
    "trim_band",
    "fastener_strip",
}
_CONSOLE_PANEL_TAGS = {"bezel", "frame", "panel", "screen", "vent", "socket", "plate"}

# --- service_cabinet family -----------------------------------------------
_CABINET_SELECTOR_FAMILIES = {"service_cabinet", "service_cabinet_family"}
_CABINET_SELECTOR_TOKENS = {"cabinet", "service_cabinet", "locker"}
_CABINET_VOLUME_COMPONENTS = {"shell", "body"}
_CABINET_PANEL_COMPONENTS = {
    "door",
    "panel",
    "frame",
    "vent",
    "trim_band",
    "inset_panel",
    "fastener_strip",
}
_CABINET_PANEL_TAGS = {"door", "panel", "shelf", "frame", "vent"}

# --- control_pedestal family ----------------------------------------------
_PEDESTAL_SELECTOR_FAMILIES = {"control_pedestal", "control_pedestal_family"}
_PEDESTAL_SELECTOR_TOKENS = {"pedestal", "podium", "control_pedestal"}
_PEDESTAL_VOLUME_COMPONENTS = {"shell", "body"}
_PEDESTAL_PANEL_COMPONENTS = {
    "panel",
    "bezel",
    "door",
    "frame",
    "socket_plate",
    "trim_band",
    "fastener_strip",
}
_PEDESTAL_LATHED_COMPONENTS = {"stand", "column", "cap"}
_PEDESTAL_PANEL_TAGS = {"panel", "bezel", "frame", "screen", "socket", "plate", "hatch"}

# --- sci_fi_wall_panel family ---------------------------------------------
_WALL_PANEL_SELECTOR_FAMILIES = {"sci_fi_wall_panel", "sci_fi_wall_panel_family"}
_WALL_PANEL_SELECTOR_TOKENS = {"wall_panel", "sci_fi_wall_panel", "console_strip"}
_WALL_PANEL_VOLUME_COMPONENTS = {"shell", "body"}
_WALL_PANEL_PANEL_COMPONENTS = {
    "panel",
    "frame",
    "bezel",
    "vent",
    "bracket",
    "seam",
    "inset_panel",
    "trim_band",
    "fastener_strip",
}
_WALL_PANEL_PANEL_TAGS = {"panel", "frame", "bezel", "vent", "mount", "seam", "inset"}


@dataclass(frozen=True)
class PrimitiveSelectionResult:
    """Selected primitives plus a compact audit trail."""

    primitives: tuple[ShapePrimitive, ...]
    applied: tuple[dict[str, Any], ...]


def select_component_primitives(
    component: Any,
    primitives: list[ShapePrimitive],
    *,
    creative_grammar: dict[str, Any] | None = None,
    family: str = "",
) -> PrimitiveSelectionResult:
    """Upgrade component primitives according to semantic/style intent."""

    style = _style_context(creative_grammar or {}, family=family)
    selected: list[ShapePrimitive] = []
    applied: list[dict[str, Any]] = []
    component_type = str(getattr(component, "component_type", "") or "")

    for primitive in primitives:
        replacement, reason = _select_replacement(component_type, primitive, style)
        if replacement is None:
            selected.append(primitive)
            continue
        selected.append(replacement)
        applied.append(
            {
                "component": component_type,
                "part": primitive.part,
                "from": primitive.primitive_type,
                "to": replacement.primitive_type,
                "reason": reason,
                "tags": list(replacement.tags),
            }
        )

    return PrimitiveSelectionResult(primitives=tuple(selected), applied=tuple(applied))


def primitive_selection_summary(applied: list[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic aggregate metadata for ShapeIR signatures."""

    by_component: dict[str, int] = {}
    by_target: dict[str, int] = {}
    for item in applied:
        component = str(item.get("component") or "")
        target = str(item.get("to") or "")
        by_component[component] = by_component.get(component, 0) + 1
        by_target[target] = by_target.get(target, 0) + 1
    return {
        "applied_count": len(applied),
        "by_component": dict(sorted(by_component.items())),
        "by_target": dict(sorted(by_target.items())),
        "records": list(applied),
    }


def _style_context(creative_grammar: dict[str, Any], *, family: str) -> dict[str, Any]:
    shape_controls = creative_grammar.get("shape_controls", {})
    if not isinstance(shape_controls, dict):
        shape_controls = {}
    summary = creative_grammar.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    tokens = {str(item) for item in summary.get("tokens", []) if item}
    tokens.update(str(item) for item in summary.get("matched_presets", []) if item)
    tokens.update(str(item) for item in shape_controls.get("creative_tags", []) if item)
    style_pack = str(shape_controls.get("style_pack", "") or "")
    edge_treatment = str(shape_controls.get("edge_treatment", "") or "")
    return {
        "family": family,
        "tokens": tokens,
        "shape_controls": shape_controls,
        "style_pack": style_pack,
        "edge_treatment": edge_treatment,
        "soft": bool(
            tokens & {"arcane", "royal", "organic", "alien", "forest", "swamp"}
            or edge_treatment in {"soft", "rounded"}
            or "arcane" in style_pack
        ),
        "industrial": bool(tokens & {"industrial", "workshop", "military", "sci_fi", "cyberpunk"}),
    }


def _is_chest_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _CHEST_SELECTOR_FAMILIES, _CHEST_SELECTOR_TOKENS)


def _confirm_chest_primitive(
    component_type: str,
    primitive: ShapePrimitive,
) -> tuple[ShapePrimitive, str] | None:
    """Confirm rich primitives the chest builders emit directly.

    The chest's component builders bypass the box→rich upgrade path by
    emitting subdivision_box/extruded_profile/revolved_profile/swept_profile
    directly. Record those as confirmed selections so the audit trail in
    signature.primitive_selector reflects actual selector activity rather
    than appearing inert.
    """
    pt = primitive.primitive_type
    if pt == "box":
        return None
    if "primitive_selector" in primitive.tags:
        return None

    if component_type in _CHEST_VOLUME_COMPONENTS and pt == "subdivision_box":
        return _confirmed(primitive, "selected_subdivision_box"), "hero_container_volume_subdivision_box_confirmed"
    if component_type == "foot" and pt in {"subdivision_box", "revolved_profile"}:
        return _confirmed(primitive, "selected_chest_foot"), "hero_container_foot_confirmed"
    if component_type == "handle" and pt == "swept_profile":
        return _confirmed(primitive, "selected_swept_runner"), "hero_container_handle_swept_profile_confirmed"
    if component_type in _CHEST_BARREL_COMPONENTS and pt in {"revolved_profile", "extruded_profile"}:
        return _confirmed(primitive, "selected_chest_barrel"), "hero_container_barrel_confirmed"
    if component_type in _CHEST_PANEL_COMPONENTS and pt in {"extruded_profile", "revolved_profile"}:
        return _confirmed(primitive, "selected_polyextrude_panel"), "hero_container_panel_confirmed"
    if _has_any_tag(primitive, _CHEST_PANEL_TAGS) and pt in {"extruded_profile", "revolved_profile"}:
        return _confirmed(primitive, "selected_polyextrude_panel"), "hero_container_panel_tag_confirmed"
    return None


def _confirmed(primitive: ShapePrimitive, marker: str) -> ShapePrimitive:
    """Return primitive with selector audit tags appended; geometry unchanged."""
    return replace(primitive, tags=_copy_tags(primitive, "primitive_selector", marker))


def _matches_selector_context(
    style: dict[str, Any],
    families: set[str],
    tokens_set: set[str],
) -> bool:
    family = str(style.get("family") or "").lower()
    tokens = {str(item).lower() for item in style.get("tokens", set()) if item}
    style_pack = str(style.get("style_pack") or "").lower()
    return (
        family in families  # no-family-dispatch: `families` is a per-selector configured set passed in by the caller, not a centralized dispatch table; this is the selector's data contract — match-when-family-in-allowed-set
        or bool(tokens & tokens_set)
        or any(token in style_pack for token in tokens_set)
    )


def _is_drone_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _DRONE_SELECTOR_FAMILIES, _DRONE_SELECTOR_TOKENS)


def _is_door_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _DOOR_SELECTOR_FAMILIES, _DOOR_SELECTOR_TOKENS)


def _is_console_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _CONSOLE_SELECTOR_FAMILIES, _CONSOLE_SELECTOR_TOKENS)


def _is_cabinet_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _CABINET_SELECTOR_FAMILIES, _CABINET_SELECTOR_TOKENS)


def _is_pedestal_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(style, _PEDESTAL_SELECTOR_FAMILIES, _PEDESTAL_SELECTOR_TOKENS)


def _is_wall_panel_selector_context(style: dict[str, Any]) -> bool:
    return _matches_selector_context(
        style, _WALL_PANEL_SELECTOR_FAMILIES, _WALL_PANEL_SELECTOR_TOKENS
    )


def _select_replacement(
    component_type: str,
    primitive: ShapePrimitive,
    style: dict[str, Any],
) -> tuple[ShapePrimitive | None, str]:
    if _is_chest_selector_context(style):
        confirmed = _confirm_chest_primitive(component_type, primitive)
        if confirmed is not None:
            return confirmed

    if primitive.primitive_type == "box":
        if _is_chest_selector_context(style):
            if component_type in _CHEST_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.18), "hero_container_volume_subdivision_box"

            if component_type == "foot":
                return _lathed_foot_from_box(primitive), "hero_container_foot_revolved_profile"

            if component_type == "handle":
                return _swept_runner_from_box(primitive), "hero_container_handle_swept_profile"

            if component_type in _CHEST_BARREL_COMPONENTS:
                return _revolved_barrel_from_box(primitive), "hero_container_barrel_revolved_profile"

            if component_type in _CHEST_PANEL_COMPONENTS or _has_any_tag(primitive, _CHEST_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "hero_container_panel_to_polyextrude"

        if _is_drone_selector_context(style):
            if component_type in _DRONE_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.16), "selected_drone_subdivision_volume"
            if component_type in _DRONE_LATHED_COMPONENTS:
                return _revolved_barrel_from_box(primitive), "selected_drone_revolved_engine"
            if component_type in _DRONE_SWEPT_COMPONENTS:
                return _swept_runner_from_box(primitive), "selected_drone_swept_runner"
            if component_type == "foot":
                return _swept_runner_from_box(primitive), "selected_drone_landing_strut_swept"
            if component_type == "handle":
                return _swept_runner_from_box(primitive), "selected_drone_handle_swept_profile"
            if component_type in _DRONE_PANEL_COMPONENTS:
                return _extruded_panel_from_box(primitive), "selected_drone_panel_polyextrude"

        if _is_door_selector_context(style):
            if component_type in _DOOR_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.10), "selected_door_subdivision_shell"
            if component_type in _DOOR_BARREL_COMPONENTS:
                return _revolved_barrel_from_box(primitive), "selected_door_revolved_barrel"
            if component_type == "handle":
                return _swept_runner_from_box(primitive), "selected_door_handle_swept_profile"
            if component_type in _DOOR_PANEL_COMPONENTS or _has_any_tag(primitive, _DOOR_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "selected_door_panel_polyextrude"

        if _is_console_selector_context(style):
            if component_type in _CONSOLE_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.14), "selected_console_subdivision_housing"
            if component_type == "foot":
                return _lathed_foot_from_box(primitive), "selected_console_lathed_foot"
            if component_type == "handle":
                return _swept_runner_from_box(primitive), "selected_console_handle_swept_profile"
            if component_type in _CONSOLE_PANEL_COMPONENTS or _has_any_tag(primitive, _CONSOLE_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "selected_console_panel_polyextrude"

        if _is_cabinet_selector_context(style):
            if component_type in _CABINET_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.12), "selected_cabinet_subdivision_body"
            if component_type == "foot":
                return _lathed_foot_from_box(primitive), "selected_cabinet_lathed_foot"
            if component_type == "handle":
                return _swept_runner_from_box(primitive), "selected_cabinet_handle_swept_profile"
            if component_type in _CABINET_PANEL_COMPONENTS or _has_any_tag(primitive, _CABINET_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "selected_cabinet_panel_polyextrude"

        if _is_pedestal_selector_context(style):
            if component_type in _PEDESTAL_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.14), "selected_pedestal_subdivision_body"
            if component_type in _PEDESTAL_LATHED_COMPONENTS:
                return _lathed_plate_from_box(primitive), "selected_pedestal_revolved_column"
            if component_type == "foot":
                return _lathed_foot_from_box(primitive), "selected_pedestal_lathed_foot"
            if component_type in _PEDESTAL_PANEL_COMPONENTS or _has_any_tag(primitive, _PEDESTAL_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "selected_pedestal_panel_polyextrude"

        if _is_wall_panel_selector_context(style):
            if component_type in _WALL_PANEL_VOLUME_COMPONENTS:
                return _rounded_box(primitive, radius_scale=0.08), "selected_wall_panel_subdivision_shell"
            if component_type in _WALL_PANEL_PANEL_COMPONENTS or _has_any_tag(primitive, _WALL_PANEL_PANEL_TAGS):
                return _extruded_panel_from_box(primitive), "selected_wall_panel_polyextrude"

        if component_type in _ROUND_BAR_COMPONENTS and _has_any_tag(primitive, _ROUND_BAR_TAGS):
            return _round_bar_from_box(primitive), "box_bar_to_swept_profile"

        if component_type in {"column", "access_support"} and _has_any_tag(primitive, _LATHED_PLATE_TAGS):
            return _lathed_plate_from_box(primitive), "architectural_plate_revolved_profile"

        if component_type in _FACADE_PANEL_COMPONENTS and _has_any_tag(primitive, _FACADE_PANEL_TAGS):
            return _extruded_panel_from_box(primitive), "facade_box_to_polyextrude"

        if component_type in {"roof", "roof_ridge", "dormer", "kiosk_body", "tunnel_segment"} and _has_any_tag(primitive, _ROOF_BOX_TAGS):
            return _roof_profile_from_box(primitive), "roof_box_to_extruded_profile"

        if component_type in _TERRAIN_VOLUME_COMPONENTS:
            return _rocky_subdivision_box(primitive), "terrain_mass_subdivision_box"

        if component_type in _ROAD_SURFACE_COMPONENTS and _has_any_tag(primitive, _ROAD_SURFACE_TAGS):
            if _has_any_tag(primitive, {"paint", "lane_arrow", "stop_line", "crosswalk_stripe"}):
                return _extruded_panel_from_box(primitive), "road_marking_to_polyextrude"
            return _rounded_box(primitive, radius_scale=0.08), "road_surface_subdivision_box"

        if component_type in _VEGETATION_RUNNER_COMPONENTS and _has_any_tag(primitive, _VEGETATION_RUNNER_TAGS):
            return _swept_runner_from_box(primitive), "vegetation_runner_to_swept_profile"

        if component_type in _MACHINE_VOLUME_COMPONENTS and _has_any_tag(primitive, _SOFT_VOLUME_TAGS):
            return _rounded_box(primitive, radius_scale=0.18), "machine_volume_subdivision_box"

        if component_type in _FURNITURE_PANEL_COMPONENTS and _has_any_tag(primitive, _FURNITURE_PANEL_TAGS):
            return _extruded_panel_from_box(primitive), "furniture_panel_to_polyextrude"

        if _has_any_tag(primitive, _EXTRUDED_PANEL_TAGS):
            return _extruded_panel_from_box(primitive), "box_panel_to_polyextrude"

        if component_type in _SOFT_VOLUME_COMPONENTS and (
            _has_any_tag(primitive, _SOFT_VOLUME_TAGS) or "feature" not in primitive.tags
        ):
            return _rounded_box(primitive, radius_scale=0.16), "semantic_body_subdivision_box"

    if component_type == "lamp" and primitive.primitive_type == "cylinder" and "shade" in primitive.tags:
        return _lamp_shade_profile(primitive), "lamp_shade_taper_profile"

    if component_type == "furniture_leg" and primitive.primitive_type == "cylinder":
        if "leg_post" in primitive.tags:
            return _tapered_leg_profile_from_cylinder(primitive), "furniture_leg_revolved_profile"

    if (
        _is_chest_selector_context(style)
        and component_type == "hinge"
        and primitive.primitive_type == "cylinder"
    ):
        return _rounded_cap_profile_from_cylinder(primitive), "hero_container_hinge_revolved_profile"

    if (
        _is_door_selector_context(style)
        and component_type in _DOOR_BARREL_COMPONENTS
        and primitive.primitive_type == "cylinder"
    ):
        return _rounded_cap_profile_from_cylinder(primitive), "selected_door_barrel_revolved_profile"

    if (
        _is_drone_selector_context(style)
        and component_type in _DRONE_LATHED_COMPONENTS
        and primitive.primitive_type == "cylinder"
    ):
        return _nozzle_profile_from_cylinder(primitive), "selected_drone_nozzle_revolved_profile"

    if (
        _is_pedestal_selector_context(style)
        and component_type in _PEDESTAL_LATHED_COMPONENTS
        and primitive.primitive_type == "cylinder"
    ):
        return _tapered_leg_profile_from_cylinder(primitive), "selected_pedestal_column_revolved_profile"

    if component_type in {"barrel", "anchor", "pipe_run", "thruster", "turret"}:
        if primitive.primitive_type == "cylinder" and _has_any_tag(primitive, _RING_CYLINDER_TAGS):
            return _ring_from_cylinder(primitive), "cylinder_collar_to_torus"

    if component_type in {"engine", "thruster"} and primitive.primitive_type == "cylinder":
        if "engine_core" in primitive.tags or "thruster_nozzle" in primitive.tags:
            return _nozzle_profile_from_cylinder(primitive), "nozzle_revolved_profile"

    if component_type == "cushion" and primitive.primitive_type == "box":
        if "soft_volume" in primitive.tags or "puffed_top" in primitive.tags or style["soft"]:
            return _rounded_box(primitive, radius_scale=0.32), "soft_cushion_subdivision_box"

    if component_type == "natural_rock" and primitive.primitive_type == "box":
        if style["family"] == "procedural_terrain" or style["soft"]:
            return _rocky_subdivision_box(primitive), "terrain_rock_subdivision_box"

    if component_type == "manhole_cover" and primitive.primitive_type == "cylinder":
        if "outer_rim" in primitive.tags:
            return _ring_from_cylinder(primitive), "manhole_outer_rim_torus"

    if component_type == "fire_hydrant" and primitive.primitive_type == "cylinder":
        if "cap" in primitive.tags:
            return _rounded_cap_profile_from_cylinder(primitive), "hydrant_cap_revolved_profile"
        if "left_nozzle" in primitive.tags or "right_nozzle" in primitive.tags:
            return _nozzle_profile_from_cylinder(primitive), "hydrant_nozzle_revolved_profile"

    if component_type == "bollard" and primitive.primitive_type == "cylinder":
        if "cap" in primitive.tags:
            return _sphere_from_cylinder_cap(primitive), "bollard_rounded_cap_sphere"

    return None, ""


def _copy_tags(primitive: ShapePrimitive, *extra: str) -> list[str]:
    tags = list(primitive.tags)
    for tag in extra:
        if tag not in tags:
            tags.append(tag)
    return tags


def _has_any_tag(primitive: ShapePrimitive, tags: set[str]) -> bool:
    return bool(set(primitive.tags) & tags)


def _round_bar_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    axis_index = max(range(3), key=lambda index: extents[index])
    perpendicular = [extents[index] for index in range(3) if index != axis_index]
    radius = max(min(perpendicular) * 0.50, 0.001)
    height = max(extents[axis_index], radius * 2.0)
    return ShapePrimitive(
        primitive_type="swept_profile",
        part=primitive.part,
        center=primitive.center,
        cross_section=_round_cross_section(radius),
        sweep_path=_axis_sweep_path(height, axis_index),
        tags=_copy_tags(primitive, "primitive_selector", "selected_swept_round_bar"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _swept_runner_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    axis_index = max(range(3), key=lambda index: extents[index])
    perpendicular = [extents[index] for index in range(3) if index != axis_index]
    radius = max(min(perpendicular) * 0.42, 0.001)
    length = max(extents[axis_index], radius * 2.0)
    path = _axis_sweep_path(length, axis_index)
    if axis_index == 0:
        path = [(x, y + math.sin((x / max(length, 0.001)) * math.pi) * radius * 0.35, z) for x, y, z in path]
    elif axis_index == 2:
        path = [(x, y + math.sin((z / max(length, 0.001)) * math.pi) * radius * 0.35, z) for x, y, z in path]
    return ShapePrimitive(
        primitive_type="swept_profile",
        part=primitive.part,
        center=primitive.center,
        cross_section=_round_cross_section(radius, segments=9),
        sweep_path=path,
        tags=_copy_tags(primitive, "primitive_selector", "selected_swept_runner"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _round_cross_section(radius: float, segments: int = 10) -> list[tuple[float, float]]:
    segments = max(6, min(24, segments))
    radius = max(float(radius), 0.001)
    return [
        (
            math.cos(math.tau * index / segments) * radius,
            math.sin(math.tau * index / segments) * radius,
        )
        for index in range(segments)
    ]


def _axis_sweep_path(length: float, axis_index: int) -> list[tuple[float, float, float]]:
    half = max(float(length), 0.001) * 0.5
    if axis_index == 0:
        return [(-half, 0.0, 0.0), (half, 0.0, 0.0)]
    if axis_index == 2:
        return [(0.0, 0.0, -half), (0.0, 0.0, half)]
    return [(0.0, -half, 0.0), (0.0, half, 0.0)]


def _rounded_box(primitive: ShapePrimitive, *, radius_scale: float) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    radius = max(min(extents) * radius_scale, 0.0)
    return ShapePrimitive(
        primitive_type="subdivision_box",
        part=primitive.part,
        center=primitive.center,
        extents=extents,
        tags=_copy_tags(primitive, "primitive_selector", "selected_subdivision_box"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        corner_radii=(radius,) * 8,
        corner_segments=5,
    )


def _lathed_plate_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    axial_height = max(extents[1], 0.001)
    radius = max(extents[0], extents[2]) * 0.50
    half_h = axial_height * 0.50
    profile = [
        (-half_h, radius * 0.78),
        (-half_h * 0.58, radius),
        (half_h * 0.58, radius),
        (half_h, radius * 0.78),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis="y",
        tags=_copy_tags(primitive, "primitive_selector", "selected_lathed_plate"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _axis_from_index(index: int) -> str:
    if index == 0:
        return "x"
    if index == 2:
        return "z"
    return "y"


def _revolved_barrel_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    axis_index = max(range(3), key=lambda index: extents[index])
    length = max(extents[axis_index], 0.001)
    perpendicular = [extents[index] for index in range(3) if index != axis_index]
    radius = max(min(perpendicular) * 0.48, 0.001)
    half = length * 0.50
    profile = [
        (-half, radius * 0.78),
        (-half * 0.86, radius),
        (half * 0.86, radius),
        (half, radius * 0.78),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis=_axis_from_index(axis_index),
        tags=_copy_tags(primitive, "primitive_selector", "selected_chest_revolved_barrel"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _lathed_foot_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    height = max(extents[1], 0.001)
    radius = max(extents[0], extents[2]) * 0.52
    half_h = height * 0.50
    profile = [
        (-half_h, radius * 0.98),
        (-height * 0.22, radius * 0.74),
        (height * 0.16, radius * 0.62),
        (half_h, radius * 0.44),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis="y",
        tags=_copy_tags(primitive, "primitive_selector", "selected_chest_lathed_foot"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _chamfered_polygon(width: float, height: float, chamfer_scale: float = 0.14) -> list[tuple[float, float]]:
    half_w = max(width * 0.5, 0.001)
    half_h = max(height * 0.5, 0.001)
    cut = max(min(width, height) * chamfer_scale, 0.0)
    cut = min(cut, half_w * 0.72, half_h * 0.72)
    if cut <= 0.0:
        return [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    return [
        (-half_w + cut, -half_h),
        (half_w - cut, -half_h),
        (half_w, -half_h + cut),
        (half_w, half_h - cut),
        (half_w - cut, half_h),
        (-half_w + cut, half_h),
        (-half_w, half_h - cut),
        (-half_w, -half_h + cut),
    ]


def _extruded_panel_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    profile = _chamfered_polygon(max(extents[0], 0.001), max(extents[1], 0.001), 0.12)
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=primitive.part,
        center=primitive.center,
        axis="z",
        profile_polygon=profile,
        extrude_height=max(extents[2], 0.001),
        tags=_copy_tags(primitive, "primitive_selector", "selected_polyextrude_panel"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _roof_profile_from_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    width = max(extents[0], 0.001)
    height = max(extents[1], 0.001)
    depth = max(extents[2], 0.001)
    if "roof_peak" in primitive.tags or "ridge_mass" in primitive.tags:
        profile = [
            (-width * 0.50, -height * 0.48),
            (width * 0.50, -height * 0.48),
            (0.0, height * 0.52),
        ]
    elif "left_roof_plane" in primitive.tags:
        profile = [
            (-width * 0.50, -height * 0.45),
            (width * 0.50, -height * 0.30),
            (width * 0.38, height * 0.45),
            (-width * 0.42, height * 0.32),
        ]
    elif "right_roof_plane" in primitive.tags:
        profile = [
            (-width * 0.50, -height * 0.30),
            (width * 0.50, -height * 0.45),
            (width * 0.42, height * 0.32),
            (-width * 0.38, height * 0.45),
        ]
    else:
        profile = _chamfered_polygon(width, height, 0.18)
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=primitive.part,
        center=primitive.center,
        axis="z",
        profile_polygon=profile,
        extrude_height=depth,
        tags=_copy_tags(primitive, "primitive_selector", "selected_roof_profile"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _rocky_subdivision_box(primitive: ShapePrimitive) -> ShapePrimitive:
    extents = primitive.extents or (0.0, 0.0, 0.0)
    base = max(min(extents) * 0.14, 0.0)
    radii = (
        base * 0.35,
        base * 0.80,
        base * 0.55,
        base * 0.18,
        base * 0.70,
        base * 0.28,
        base,
        base * 0.45,
    )
    return ShapePrimitive(
        primitive_type="subdivision_box",
        part=primitive.part,
        center=primitive.center,
        extents=extents,
        tags=_copy_tags(primitive, "primitive_selector", "selected_rocky_subdivision_box"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        corner_radii=radii,
        corner_segments=3,
    )


def _tapered_leg_profile_from_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    radius = max(float(primitive.radius or 0.0), 0.001)
    height = max(float(primitive.height or 0.0), radius * 2.0, 0.001)
    half_h = height * 0.50
    profile = [
        (-half_h, radius * 1.12),
        (-height * 0.34, radius * 0.82),
        (height * 0.28, radius * 0.68),
        (half_h, radius * 0.96),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis=primitive.axis,
        tags=_copy_tags(primitive, "primitive_selector", "selected_tapered_leg_profile"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _rounded_cap_profile_from_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    radius = float(primitive.radius or 0.0)
    height = max(float(primitive.height or 0.0), radius * 0.35, 0.001)
    half_h = height * 0.50
    profile = [
        (-half_h, radius * 0.96),
        (-height * 0.10, radius * 1.08),
        (height * 0.24, radius * 0.82),
        (half_h, radius * 0.18),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis=primitive.axis,
        tags=_copy_tags(primitive, "primitive_selector", "selected_rounded_cap_profile"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _lamp_shade_profile(primitive: ShapePrimitive) -> ShapePrimitive:
    radius = float(primitive.radius or 0.0)
    height = float(primitive.height or 0.0)
    profile = [
        (-height * 0.50, radius * 1.10),
        (-height * 0.34, radius * 1.02),
        (height * 0.34, radius * 0.78),
        (height * 0.50, radius * 0.70),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis=primitive.axis,
        tags=_copy_tags(primitive, "primitive_selector", "selected_revolved_profile"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _nozzle_profile_from_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    radius = float(primitive.radius or 0.0)
    height = max(float(primitive.height or 0.0), radius * 2.0, 0.001)
    half_h = height * 0.50
    profile = [
        (-half_h, radius * 1.18),
        (-height * 0.22, radius * 1.05),
        (height * 0.08, radius * 0.78),
        (height * 0.34, radius * 0.92),
        (half_h, radius * 0.68),
    ]
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=primitive.part,
        center=primitive.center,
        axis=primitive.axis,
        tags=_copy_tags(primitive, "primitive_selector", "selected_nozzle_profile"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        profile_points=profile,
    )


def _ring_from_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    radius = float(primitive.radius or 0.0)
    height = float(primitive.height or 0.0)
    minor = max(min(radius * 0.12, height * 0.55), 0.001)
    major = max(radius - minor, minor)
    return ShapePrimitive(
        primitive_type="torus",
        part=primitive.part,
        center=primitive.center,
        axis=primitive.axis,
        tags=_copy_tags(primitive, "primitive_selector", "selected_torus"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        major_radius=major,
        minor_radius=minor,
    )


def _sphere_from_cylinder_cap(primitive: ShapePrimitive) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="sphere",
        part=primitive.part,
        center=primitive.center,
        radius=float(primitive.radius or 0.0),
        tags=_copy_tags(primitive, "primitive_selector", "selected_sphere_cap"),
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
    )
