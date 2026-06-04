"""Procedural broad-family assembly blueprints."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..assembly_kernel import AssemblyBlueprint
from ..asset_graph import AssetGraph
from ..path_profiles import path_profile_from_controls
from ..structural_profiles import structural_elements_for_facade, structural_elements_for_path
from .common import _component, _part_name


def _shape_controls(asset_graph: AssetGraph) -> dict[str, Any]:
    raw = asset_graph.authoring.get("shape_controls", {})
    return raw if isinstance(raw, dict) else {}


def _count(controls: dict[str, Any], *keys: str, default: int, minimum: int, maximum: int) -> int:
    for key in keys:
        value = controls.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return min(maximum, max(minimum, 1 if value else minimum))
        try:
            return min(maximum, max(minimum, round(float(value))))
        except (TypeError, ValueError):
            continue
    return default


def _level(controls: dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        value = controls.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return default


def _choice(controls: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = controls.get(key)
        if value is None:
            continue
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if text:
            return text
    return default


def _assembly_mode(controls: dict[str, Any]) -> str:
    return _choice(controls, "assembly_mode", "assembly_type", "assembly_layout", default="")


def _assembly_member(controls: dict[str, Any]) -> bool:
    value = controls.get("assembly_member")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on", "member"}
    return bool(value)


def _assembly_count(controls: dict[str, Any], *, default: int = 1, maximum: int = 64) -> int:
    return _count(
        controls,
        "assembly_slot_count",
        "assembly_count",
        "slot_count",
        "generator_count",
        default=default,
        minimum=0,
        maximum=maximum,
    )


def _control_strings(controls: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = controls.get(key)
        if isinstance(value, str) and value:
            return [value.strip().lower().replace("-", "_").replace(" ", "_")]
        if isinstance(value, list):
            out = [str(item).strip().lower().replace("-", "_").replace(" ", "_") for item in value if item]
            if out:
                return out
    return []


_FAMILY_LOADOUT_ALIASES: dict[str, tuple[str, ...]] = {
    "vehicle": ("vehicle_loadout", "vehicle_archetype", "loadout", "family_loadout", "archetype"),
    "boat": ("boat_loadout", "boat_archetype", "vessel_loadout", "loadout", "family_loadout", "archetype"),
    "weapon": (
        "weapon_loadout",
        "weapon_archetype",
        "tool_loadout",
        "tool_archetype",
        "loadout",
        "family_loadout",
        "archetype",
    ),
}

_PROCEDURAL_LOADOUTS: dict[str, dict[str, dict[str, Any]]] = {
    "vehicle": {
        "patrol_vtol": {
            "drive_type": "vtol",
            "wheel_count": 0,
            "wing_count": 2,
            "rotor_count": 4,
            "crew_bay_count": 1,
            "cargo_bay_count": 1,
            "hardpoint_count": 4,
            "module_socket_count": 2,
            "thruster_count": 4,
            "stabilizer_count": 2,
            "sensor_count": 2,
            "length_scale": 1.38,
            "width_scale": 0.72,
            "height_scale": 0.34,
        },
        "cargo_rover": {
            "drive_type": "rover",
            "wheel_count": 6,
            "suspension_count": 6,
            "cargo_module_count": 2,
            "crew_bay_count": 1,
            "cargo_bay_count": 2,
            "hardpoint_count": 1,
            "module_socket_count": 4,
            "sensor_count": 1,
            "length_scale": 1.58,
            "width_scale": 0.66,
            "height_scale": 0.38,
        },
        "scout_drone": {
            "drive_type": "drone",
            "wheel_count": 0,
            "rotor_count": 4,
            "crew_bay_count": 0,
            "cargo_bay_count": 1,
            "module_socket_count": 2,
            "thruster_count": 2,
            "stabilizer_count": 2,
            "sensor_count": 3,
            "length_scale": 1.08,
            "width_scale": 0.62,
            "height_scale": 0.28,
        },
        "assault_carrier": {
            "drive_type": "tracked",
            "wheel_count": 0,
            "track_count": 2,
            "suspension_count": 4,
            "turret_count": 2,
            "cargo_module_count": 1,
            "crew_bay_count": 1,
            "cargo_bay_count": 1,
            "hardpoint_count": 8,
            "module_socket_count": 4,
            "sensor_count": 2,
            "length_scale": 1.70,
            "width_scale": 0.78,
            "height_scale": 0.44,
        },
        "aircraft_interceptor": {
            "drive_type": "aircraft",
            "wheel_count": 0,
            "wing_count": 2,
            "crew_bay_count": 1,
            "hardpoint_count": 4,
            "module_socket_count": 2,
            "thruster_count": 2,
            "stabilizer_count": 2,
            "sensor_count": 2,
            "length_scale": 1.62,
            "width_scale": 0.86,
            "height_scale": 0.30,
        },
    },
    "boat": {
        "research_vessel": {
            "boat_type": "research",
            "propulsion": "engine",
            "engine_count": 2,
            "cabin_count": 2,
            "deck_level_count": 2,
            "cargo_hold_count": 2,
            "rail_count": 4,
            "crew_bay_count": 2,
            "cargo_bay_count": 2,
            "module_socket_count": 5,
            "thruster_count": 2,
            "stabilizer_count": 2,
            "sensor_count": 4,
            "cleat_count": 8,
            "length_scale": 1.72,
            "width_scale": 0.62,
            "height_scale": 0.38,
        },
        "patrol_cutter": {
            "boat_type": "cutter",
            "propulsion": "engine",
            "engine_count": 2,
            "mast_count": 1,
            "sail_count": 0,
            "rigging_count": 1,
            "cabin_count": 1,
            "deck_level_count": 2,
            "rail_count": 4,
            "crew_bay_count": 1,
            "deck_hardpoint_count": 4,
            "module_socket_count": 3,
            "thruster_count": 2,
            "stabilizer_count": 2,
            "sensor_count": 3,
            "cleat_count": 6,
            "length_scale": 1.54,
            "width_scale": 0.54,
            "height_scale": 0.34,
        },
        "cargo_barge": {
            "boat_type": "barge",
            "propulsion": "engine",
            "engine_count": 1,
            "cabin_count": 1,
            "cargo_hold_count": 4,
            "crew_bay_count": 1,
            "cargo_bay_count": 4,
            "module_socket_count": 4,
            "sensor_count": 1,
            "cleat_count": 10,
            "rail_count": 2,
            "length_scale": 1.86,
            "width_scale": 0.72,
            "height_scale": 0.28,
        },
        "sail_sloop": {
            "boat_type": "sloop",
            "propulsion": "sail",
            "engine_count": 0,
            "mast_count": 1,
            "sail_count": 2,
            "rigging_count": 6,
            "cabin_count": 1,
            "deck_level_count": 1,
            "rail_count": 2,
            "crew_bay_count": 1,
            "cleat_count": 6,
            "length_scale": 1.44,
            "width_scale": 0.48,
            "height_scale": 0.30,
        },
        "rescue_workboat": {
            "boat_type": "workboat",
            "propulsion": "engine",
            "engine_count": 2,
            "cabin_count": 1,
            "cargo_hold_count": 1,
            "crew_bay_count": 2,
            "cargo_bay_count": 1,
            "deck_hardpoint_count": 1,
            "module_socket_count": 4,
            "thruster_count": 4,
            "stabilizer_count": 2,
            "sensor_count": 3,
            "cleat_count": 8,
            "length_scale": 1.40,
            "width_scale": 0.54,
            "height_scale": 0.34,
        },
        "submersible_scout": {
            "boat_type": "submersible",
            "propulsion": "engine",
            "engine_count": 2,
            "cabin_count": 1,
            "deck_level_count": 1,
            "crew_bay_count": 1,
            "module_socket_count": 3,
            "thruster_count": 4,
            "stabilizer_count": 4,
            "sensor_count": 4,
            "cleat_count": 0,
            "rail_count": 0,
            "length_scale": 1.34,
            "width_scale": 0.50,
            "height_scale": 0.42,
        },
    },
    "weapon": {
        "railgun_marksman": {
            "weapon_type": "railgun",
            "barrel_count": 1,
            "magazine_count": 1,
            "sight_count": 2,
            "rail_count": 4,
            "hardpoint_count": 6,
            "module_socket_count": 3,
            "muzzle_device_count": 1,
            "ammo_bay_count": 1,
            "power_cell_count": 2,
            "sling_mount_count": 2,
            "stabilizer_count": 2,
            "smart_sensors": 2,
            "length_scale": 1.58,
            "width_scale": 0.24,
            "thickness_scale": 0.13,
        },
        "breacher_shotgun": {
            "weapon_type": "shotgun",
            "barrel_count": 2,
            "magazine_count": 1,
            "sight_count": 1,
            "rail_count": 2,
            "hardpoint_count": 4,
            "module_socket_count": 2,
            "muzzle_device_count": 2,
            "ammo_bay_count": 1,
            "sling_mount_count": 2,
            "stabilizer_count": 1,
            "length_scale": 1.12,
            "width_scale": 0.28,
            "thickness_scale": 0.16,
        },
        "plasma_sidearm": {
            "weapon_type": "plasma",
            "barrel_count": 1,
            "magazine_count": 0,
            "sight_count": 1,
            "rail_count": 1,
            "hardpoint_count": 2,
            "module_socket_count": 2,
            "muzzle_device_count": 1,
            "ammo_bay_count": 1,
            "power_cell_count": 2,
            "smart_sensors": 1,
            "length_scale": 0.82,
            "width_scale": 0.18,
            "thickness_scale": 0.12,
        },
        "salvage_tool": {
            "weapon_type": "tool",
            "head_count": 2,
            "guard_count": 1,
            "rail_count": 1,
            "hardpoint_count": 4,
            "module_socket_count": 3,
            "power_cell_count": 1,
            "sling_mount_count": 1,
            "smart_sensors": 1,
            "length_scale": 1.05,
            "width_scale": 0.24,
            "thickness_scale": 0.16,
        },
        "ceremonial_blade": {
            "weapon_type": "sword",
            "blade_count": 1,
            "guard_count": 2,
            "sling_mount_count": 0,
            "hardpoint_count": 0,
            "module_socket_count": 0,
            "length_scale": 1.28,
            "width_scale": 0.20,
            "thickness_scale": 0.10,
        },
        "boarding_pike": {
            "weapon_type": "spear",
            "blade_count": 1,
            "guard_count": 1,
            "hardpoint_count": 2,
            "module_socket_count": 1,
            "sling_mount_count": 2,
            "length_scale": 1.62,
            "width_scale": 0.16,
            "thickness_scale": 0.10,
        },
    },
}


def _active_loadout(family: str, controls: dict[str, Any]) -> str:
    presets = _PROCEDURAL_LOADOUTS.get(family, {})
    for key in _FAMILY_LOADOUT_ALIASES.get(family, ("loadout", "family_loadout", "archetype")):  # no-family-dispatch: per-family control-key alias map for the procedural loadout dispatcher; migrate to declarative FamilyAlias JSON keyed under intent.loadout_keys
        value = controls.get(key)
        if value is None:
            continue
        candidate = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if candidate in presets:
            return candidate
    return ""


def _with_loadout_controls(family: str, controls: dict[str, Any]) -> dict[str, Any]:
    loadout = _active_loadout(family, controls)
    if not loadout:
        return controls
    merged = dict(_PROCEDURAL_LOADOUTS[family][loadout])  # no-family-dispatch: per-family procedural loadout lookup; migrate to declarative FamilyAlias JSON loadout_packs (companion to the _FAMILY_LOADOUT_ALIASES inline-exempt above)
    merged.update(controls)
    merged.setdefault("loadout", loadout)
    merged.setdefault("family_loadout", loadout)
    merged.setdefault(f"{family}_loadout", loadout)
    return merged


def _loadout_tags(family: str, controls: dict[str, Any]) -> list[str]:
    loadout = _active_loadout(family, controls)
    return [f"{family}_loadout", loadout] if loadout else []


def _append_structural_elements(
    components: list[Any],
    elements: list[dict[str, Any]],
    part_map: dict[str, str],
    *,
    adjacency: list[str] | None = None,
) -> None:
    for element in elements:
        role = str(element.get("part_role") or "default")
        part = part_map.get(role) or part_map.get("default")
        if not part:
            continue
        center = tuple(float(value) for value in element["center"])
        extents = tuple(float(value) for value in element["extents"])
        components.append(
            _component(
                str(element["name"]),
                str(element["component_type"]),
                part,
                center,  # type: ignore[arg-type]
                extents,  # type: ignore[arg-type]
                tags=[str(tag) for tag in element.get("tags", [])],
                adjacency=list(adjacency or []),
            )
        )


def _procedural_building_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    floors = _count(controls, "floors", "floor_count", "building_floors", default=3, minimum=1, maximum=16)
    bays = _count(controls, "bays", "window_bays", "building_bays", default=3, minimum=1, maximum=12)
    wing_count = _count(controls, "wings", "wing_count", default=0, minimum=0, maximum=4)
    tower_count = _count(controls, "towers", "tower_count", default=0, minimum=0, maximum=6)
    balcony_count = _count(controls, "balconies", "balcony_count", default=0, minimum=0, maximum=24)
    awning_count = _count(controls, "awnings", "awning_count", default=0, minimum=0, maximum=24)
    dormer_count = _count(controls, "dormers", "dormer_count", default=0, minimum=0, maximum=12)
    chimney_count = _count(controls, "chimneys", "chimney_count", default=0, minimum=0, maximum=8)
    cornice_count = _count(controls, "cornices", "cornice_count", default=2, minimum=0, maximum=8)
    roof_style = _choice(controls, "roof_style", "roof", default="flat")
    facade_style = _choice(controls, "facade_style", "architecture_style", "style", default="grid")
    entry_count = _count(controls, "entries", "entry_count", "door_count", default=1, minimum=1, maximum=6)
    storefront_count = _count(
        controls,
        "storefronts",
        "storefront_count",
        "shopfront_count",
        default=1 if facade_style in {"commercial", "market", "urban", "district", "civic"} else 0,
        minimum=0,
        maximum=18,
    )
    arcade_count = _count(
        controls,
        "arcades",
        "arcade_count",
        "ground_arcade_count",
        default=bays if facade_style in {"arcade", "classical", "gothic"} else 0,
        minimum=0,
        maximum=24,
    )
    parapet_count = _count(
        controls,
        "parapets",
        "parapet_count",
        default=1 if roof_style in {"flat", "terrace", "industrial"} else 0,
        minimum=0,
        maximum=4,
    )
    roof_equipment_count = _count(
        controls,
        "roof_equipment",
        "roof_equipment_count",
        "hvac_count",
        default=1 if floors >= 3 else 0,
        minimum=0,
        maximum=12,
    )
    signage_count = _count(
        controls,
        "signs",
        "signage",
        "signage_count",
        default=1 if storefront_count else 0,
        minimum=0,
        maximum=18,
    )
    fire_escape_count = _count(
        controls,
        "fire_escapes",
        "fire_escape_count",
        default=1 if floors >= 3 and facade_style in {"industrial", "urban", "district", "dense"} else 0,
        minimum=0,
        maximum=6,
    )
    side_window_bays = _count(
        controls,
        "side_window_bays",
        "side_bays",
        default=max(0, bays // 2 if floors >= 2 else 0),
        minimum=0,
        maximum=12,
    )
    rear_window_bays = _count(
        controls,
        "rear_window_bays",
        "rear_bays",
        default=max(0, bays // 2 if floors >= 2 else 0),
        minimum=0,
        maximum=12,
    )
    service_door_count = _count(
        controls,
        "service_doors",
        "service_door_count",
        default=1 if floors >= 2 else 0,
        minimum=0,
        maximum=6,
    )
    building_envelope_marker_count = _count(controls, "building_envelope_count", default=0, minimum=0, maximum=8)
    floor_stack_marker_count = _count(controls, "floor_stack_count", default=0, minimum=0, maximum=8)
    floor_plate_count = _count(controls, "floor_plate_count", default=floors if floor_stack_marker_count else 0, minimum=0, maximum=32)
    facade_grid_marker_count = _count(controls, "facade_grid_count", default=0, minimum=0, maximum=8)
    facade_bay_marker_count = _count(controls, "facade_bay_count", "window_bay_count", default=0, minimum=0, maximum=192)
    roof_profile_marker_count = _count(controls, "roof_profile_count", default=0, minimum=0, maximum=8)
    vertical_core_marker_count = _count(controls, "vertical_core_count", "service_core_count", default=0, minimum=0, maximum=12)
    entrance_plan_marker_count = _count(controls, "entrance_plan_count", default=0, minimum=0, maximum=8)
    width = scale * _level(controls, "width_scale", "building_width", default=1.05)
    depth = scale * _level(controls, "depth_scale", "building_depth", default=0.82)
    floor_height = scale * _level(controls, "floor_height", "floor_height_scale", default=0.30)
    total_height = floor_height * floors
    jitter = float(rng.uniform(-0.015, 0.015))

    body_part = _part_name(asset_graph, "body", "building", fallback="building_core")
    wall_part = _part_name(asset_graph, "wall", "panel", fallback=body_part)
    roof_part = _part_name(asset_graph, "roof", fallback=body_part)
    window_part = _part_name(asset_graph, "window", fallback=wall_part)
    door_part = _part_name(asset_graph, "door", fallback=wall_part)
    column_part = _part_name(asset_graph, "column", "support", fallback=wall_part)
    stair_part = _part_name(asset_graph, "stair", "stairs", fallback=wall_part)
    balcony_part = _part_name(asset_graph, "balcony", "platform", fallback=wall_part)
    awning_part = _part_name(asset_graph, "awning", "canopy", fallback=roof_part)
    cornice_part = _part_name(asset_graph, "cornice", "trim", fallback=wall_part)
    tower_part = _part_name(asset_graph, "tower", "building", fallback=body_part)
    chimney_part = _part_name(asset_graph, "chimney", "vent", fallback=roof_part)
    dormer_part = _part_name(asset_graph, "dormer", "window", fallback=window_part)
    arch_part = _part_name(asset_graph, "arch", "arcade", "column", fallback=column_part)
    parapet_part = _part_name(asset_graph, "parapet", "roof", "trim", fallback=roof_part)
    signage_part = _part_name(asset_graph, "sign", "signage", "marker", fallback=wall_part)
    equipment_part = _part_name(asset_graph, "equipment", "hvac", "vent", "machine", fallback=roof_part)
    fire_escape_part = _part_name(asset_graph, "fire_escape", "stair", "railing", fallback=stair_part)
    envelope_part = _part_name(asset_graph, "building_envelope", "envelope", "frame", fallback=wall_part)
    floor_stack_part = _part_name(asset_graph, "floor_stack", "floor_plate", "floor", fallback=wall_part)
    facade_grid_part = _part_name(asset_graph, "facade_grid", "facade", fallback=wall_part)
    facade_bay_part = _part_name(asset_graph, "facade_bay", "window_bay", fallback=window_part)
    roof_profile_part = _part_name(asset_graph, "roof_profile", "roof", fallback=roof_part)
    vertical_core_part = _part_name(asset_graph, "vertical_core", "service_core", "elevator", fallback=stair_part)
    entrance_plan_part = _part_name(asset_graph, "entrance_plan", "entry", "door", fallback=door_part)

    components = [
        _component(
            "building_core_region",
            "shell",
            body_part,
            (0.0, total_height * 0.50, 0.0),
            (width, total_height, depth),
            tags=["building", "body", "floors", f"floors_{floors}"],
        ),
        _component(
            "building_roof_region",
            "roof",
            roof_part,
            (0.0, total_height + floor_height * 0.10, 0.0),
            (width * 1.08, floor_height * 0.22, depth * 1.10),
            tags=["building", "roof", roof_style],
            adjacency=[body_part],
        ),
        _component(
            "building_door_region",
            "door",
            door_part,
            (0.0, floor_height * 0.33, depth * 0.52),
            (width * 0.20, floor_height * 0.62, depth * 0.06),
            tags=["building", "door", "entry"],
            adjacency=[body_part],
        ),
    ]
    for index in range(building_envelope_marker_count):
        inset = 1.0 + index * 0.035
        components.append(
            _component(
                f"building_envelope_control_{index:02d}_region",
                "envelope_frame",
                envelope_part,
                (0.0, total_height * 0.50, 0.0),
                (width * inset, total_height * 1.02, depth * inset),
                tags=["building", "building_envelope", "envelope_control", f"envelope_{index}", facade_style],
                adjacency=[body_part, wall_part, roof_part],
            )
        )
    floor_plate_total = max(floor_plate_count, floors if floor_stack_marker_count else 0)
    for index in range(floor_plate_total):
        floor_index = index % max(1, floors)
        y = floor_height * floor_index + floor_height * 0.04
        components.append(
            _component(
                f"floor_stack_plate_{index:02d}_region",
                "floor_plate",
                floor_stack_part,
                (0.0, y, 0.0),
                (width * 0.96, floor_height * 0.035, depth * 0.96),
                tags=["building", "floor_stack", "floor_plate", f"floor_{floor_index + 1}", f"plate_{index}"],
                adjacency=[body_part, wall_part],
            )
        )
    for index in range(facade_grid_marker_count):
        z = depth * (0.565 + index * 0.018)
        components.append(
            _component(
                f"facade_grid_control_{index:02d}_region",
                "facade_grid",
                facade_grid_part,
                (0.0, total_height * 0.52, z),
                (width * 1.02, total_height * 0.96, depth * 0.025),
                tags=["building", "facade_grid", "facade_control", f"grid_{index}", facade_style],
                adjacency=[body_part, wall_part],
            )
        )
    visible_facade_bays = min(facade_bay_marker_count, max(0, floors * bays))
    for index in range(visible_facade_bays):
        floor_index = index // max(1, bays)
        bay_index = index % max(1, bays)
        x = (bay_index - (bays - 1) / 2.0) * width * 0.72 / max(1, bays - 1)
        y = floor_height * (floor_index + 0.52)
        components.append(
            _component(
                f"facade_bay_control_{floor_index:02d}_{bay_index:02d}_region",
                "facade_bay",
                facade_bay_part,
                (x, y, depth * 0.585),
                (width * 0.14, floor_height * 0.42, depth * 0.032),
                tags=["building", "facade_bay", "window_bay", f"floor_{floor_index}", f"bay_{bay_index}", facade_style],
                adjacency=[body_part, wall_part, window_part],
            )
        )
    for index in range(roof_profile_marker_count):
        components.append(
            _component(
                f"roof_profile_control_{index:02d}_region",
                "roof_profile",
                roof_profile_part,
                (0.0, total_height + floor_height * (0.30 + index * 0.055), 0.0),
                (width * (1.12 - min(index, 4) * 0.055), floor_height * 0.12, depth * (1.14 - min(index, 4) * 0.055)),
                tags=["building", "roof_profile", "roof_control", f"profile_{index}", roof_style],
                adjacency=[roof_part, body_part],
            )
        )
    for index in range(vertical_core_marker_count):
        offset = (index - (vertical_core_marker_count - 1) / 2.0) * width * 0.18
        components.append(
            _component(
                f"vertical_core_control_{index:02d}_region",
                "vertical_core",
                vertical_core_part,
                (offset, total_height * 0.50, -depth * 0.16),
                (width * 0.10, total_height * 0.96, depth * 0.14),
                tags=["building", "vertical_core", "service_core", "stairs", "elevator", f"core_{index}"],
                adjacency=[body_part, floor_stack_part, stair_part],
            )
        )
    for index in range(entrance_plan_marker_count):
        x = (index - (entrance_plan_marker_count - 1) / 2.0) * width * 0.24
        components.append(
            _component(
                f"entrance_plan_control_{index:02d}_region",
                "entrance_plan",
                entrance_plan_part,
                (x, floor_height * 0.28, depth * 0.69),
                (width * 0.24, floor_height * 0.68, depth * 0.16),
                tags=["building", "entrance_plan", "entry_control", "door", f"entry_plan_{index}"],
                adjacency=[body_part, door_part],
            )
        )
    _append_structural_elements(
        components,
        structural_elements_for_facade(
            controls,
            family="procedural_building",
            width=width,
            depth=depth,
            height=total_height,
            floors=floors,
            bays=bays,
        ),
        {
            "wall": wall_part,
            "trim": cornice_part,
            "support": column_part,
            "roof": roof_part,
            "default": wall_part,
        },
        adjacency=[body_part, roof_part],
    )
    if roof_style in {"gable", "hip", "mansard", "shed"}:
        components.append(
            _component(
                "building_roof_ridge_region",
                "roof_ridge",
                roof_part,
                (0.0, total_height + floor_height * 0.28, 0.0),
                (width * 0.74, floor_height * 0.30, depth * 1.04),
                tags=["building", "roof", "ridge", roof_style],
                adjacency=[roof_part],
            )
        )
    elif roof_style in {"dome", "cupola"}:
        components.append(
            _component(
                "building_roof_dome_region",
                "dome",
                roof_part,
                (0.0, total_height + floor_height * 0.34, 0.0),
                (width * 0.56, floor_height * 0.48, width * 0.56),
                tags=["building", "roof", "dome", roof_style],
                adjacency=[roof_part],
                radius=width * 0.28,
                height=floor_height * 0.48,
            )
        )

    for floor_index in range(floors):
        y = floor_height * (floor_index + 0.5)
        components.append(
            _component(
                f"floor_band_{floor_index:02d}_region",
                "panel",
                wall_part,
                (0.0, y + floor_height * 0.42, depth * 0.535),
                (width * 0.96, floor_height * 0.05, depth * 0.06),
                tags=["building", "floor_band", f"floor_{floor_index}"],
                adjacency=[body_part],
            )
        )
        for bay_index in range(bays):
            x = (bay_index - (bays - 1) / 2.0) * width * 0.72 / max(1, bays - 1)
            components.append(
                _component(
                    f"window_{floor_index:02d}_{bay_index:02d}_region",
                    "window",
                    window_part,
                    (x, y + floor_height * (0.08 + jitter), depth * 0.55),
                    (width * 0.12, floor_height * 0.34, depth * 0.05),
                    tags=["building", "window", f"floor_{floor_index}", f"bay_{bay_index}"],
                    adjacency=[body_part, wall_part],
                )
            )
            if balcony_count and floor_index > 0 and (floor_index * bays + bay_index) % max(1, bays // 2 + 1) == 0:
                if sum(1 for item in components if "balcony" in item.tags) < balcony_count:
                    components.append(
                        _component(
                            f"balcony_{floor_index:02d}_{bay_index:02d}_region",
                            "balcony",
                            balcony_part,
                            (x, y - floor_height * 0.10, depth * 0.66),
                            (width * 0.18, floor_height * 0.12, depth * 0.24),
                            tags=["building", "balcony", f"floor_{floor_index}", f"bay_{bay_index}", facade_style],
                            adjacency=[body_part, window_part],
                        )
                    )
            if awning_count and floor_index == 0 and bay_index < awning_count:
                components.append(
                    _component(
                        f"awning_{bay_index:02d}_region",
                        "awning",
                        awning_part,
                        (x, y + floor_height * 0.26, depth * 0.62),
                        (width * 0.16, floor_height * 0.08, depth * 0.18),
                        tags=["building", "awning", "canopy", f"bay_{bay_index}", facade_style],
                        adjacency=[wall_part],
                    )
                )

    for side, sign in (("left", -1.0), ("right", 1.0)):
        components.append(
            _component(
                f"{side}_column_region",
                "column",
                column_part,
                (sign * width * 0.45, total_height * 0.48, depth * 0.56),
                (width * 0.07, total_height * 0.94, width * 0.07),
                tags=["building", "column", side],
                adjacency=[body_part, roof_part],
                radius=width * 0.035,
                height=total_height * 0.94,
            )
        )
    for index in range(wing_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        y = total_height * 0.38
        components.append(
            _component(
                f"{side}_building_wing_{index:02d}_region",
                "shell",
                body_part,
                (sign * width * 0.66, y, -depth * 0.04),
                (width * 0.38, total_height * 0.76, depth * 0.72),
                tags=["building", "wing", side, facade_style],
                adjacency=[body_part],
            )
        )
    tower_positions = [
        ("front_left", -0.44, 0.44),
        ("front_right", 0.44, 0.44),
        ("rear_left", -0.44, -0.44),
        ("rear_right", 0.44, -0.44),
        ("center_front", 0.0, 0.48),
        ("center_rear", 0.0, -0.48),
    ]
    for index in range(tower_count):
        label, x_factor, z_factor = tower_positions[index % len(tower_positions)]
        tower_height = total_height * (1.10 + 0.10 * (index % 3))
        tower_width = width * (0.18 if floors > 2 else 0.24)
        components.append(
            _component(
                f"building_tower_{index:02d}_{label}_region",
                "tower",
                tower_part,
                (x_factor * width, tower_height * 0.50, z_factor * depth),
                (tower_width, tower_height, tower_width),
                tags=["building", "tower", label, facade_style],
                adjacency=[body_part, roof_part],
                radius=tower_width * 0.42,
                height=tower_height,
            )
        )
    if cornice_count:
        for index in range(cornice_count):
            t = index / max(1, cornice_count - 1)
            y = floor_height * 0.18 + t * (total_height - floor_height * 0.04)
            components.append(
                _component(
                    f"cornice_band_{index:02d}_region",
                    "cornice",
                    cornice_part,
                    (0.0, y, depth * 0.56),
                    (width * 1.08, floor_height * 0.06, depth * 0.08),
                    tags=["building", "cornice", "trim", f"band_{index}", facade_style],
                    adjacency=[body_part],
                )
            )
    for index in range(dormer_count):
        x = (index - (dormer_count - 1) / 2.0) * width * 0.58 / max(1, dormer_count - 1)
        components.append(
            _component(
                f"roof_dormer_{index:02d}_region",
                "dormer",
                dormer_part,
                (x, total_height + floor_height * 0.29, depth * 0.40),
                (width * 0.14, floor_height * 0.30, depth * 0.16),
                tags=["building", "dormer", "roof_window", f"dormer_{index}", roof_style],
                adjacency=[roof_part],
            )
        )
    for index in range(chimney_count):
        x = (index - (chimney_count - 1) / 2.0) * width * 0.42 / max(1, chimney_count - 1)
        z = -depth * (0.22 + 0.10 * (index % 2))
        components.append(
            _component(
                f"chimney_{index:02d}_region",
                "chimney",
                chimney_part,
                (x, total_height + floor_height * 0.42, z),
                (width * 0.08, floor_height * 0.58, width * 0.08),
                tags=["building", "chimney", "roof_vent", f"chimney_{index}", roof_style],
                adjacency=[roof_part],
            )
        )
    components.append(
        _component(
            "front_stair_region",
            "stair",
            stair_part,
            (0.0, floor_height * 0.10, depth * 0.76),
            (width * 0.38, floor_height * 0.34, depth * 0.28),
            tags=["building", "stairs", "entry"],
            adjacency=[door_part],
        )
    )
    for index in range(1, entry_count):
        x = (index - entry_count / 2.0) * width * 0.32
        components.append(
            _component(
                f"secondary_entry_{index:02d}_region",
                "door",
                door_part,
                (x, floor_height * 0.30, depth * 0.525),
                (width * 0.15, floor_height * 0.52, depth * 0.055),
                tags=["building", "door", "entry", "secondary", f"entry_{index}", facade_style],
                adjacency=[body_part, wall_part],
            )
        )
    for index in range(storefront_count):
        x = (index - (storefront_count - 1) / 2.0) * width * 0.78 / max(1, storefront_count - 1)
        components.append(
            _component(
                f"storefront_window_{index:02d}_region",
                "window",
                window_part,
                (x, floor_height * 0.54, depth * 0.565),
                (width * 0.16, floor_height * 0.42, depth * 0.065),
                tags=["building", "storefront", "window", "ground_floor", f"storefront_{index}", facade_style],
                adjacency=[body_part, wall_part],
            )
        )
    for index in range(arcade_count):
        x = (index - (arcade_count - 1) / 2.0) * width * 0.82 / max(1, arcade_count - 1)
        components.append(
            _component(
                f"arcade_arch_{index:02d}_region",
                "arch",
                arch_part,
                (x, floor_height * 0.58, depth * 0.595),
                (width * 0.18, floor_height * 0.92, depth * 0.095),
                tags=["building", "arcade", "arch", "ground_floor", f"arcade_{index}", facade_style],
                adjacency=[body_part, column_part],
            )
        )
    for index in range(signage_count):
        x = (index - (signage_count - 1) / 2.0) * width * 0.72 / max(1, signage_count - 1)
        components.append(
            _component(
                f"facade_signage_{index:02d}_region",
                "panel",
                signage_part,
                (x, floor_height * 1.02, depth * 0.585),
                (width * 0.22, floor_height * 0.12, depth * 0.055),
                tags=["building", "signage", "facade_marker", f"sign_{index}", facade_style],
                adjacency=[wall_part],
            )
        )
    for index in range(parapet_count):
        inset = 1.0 - min(index, 3) * 0.08
        components.append(
            _component(
                f"roof_parapet_{index:02d}_region",
                "parapet",
                parapet_part,
                (0.0, total_height + floor_height * (0.20 + index * 0.06), 0.0),
                (width * 1.10 * inset, floor_height * 0.22, depth * 1.12 * inset),
                tags=["building", "roof", "parapet", f"parapet_{index}", roof_style],
                adjacency=[roof_part, body_part],
            )
        )
    for index in range(roof_equipment_count):
        cols = max(1, round(roof_equipment_count**0.5))
        col = index % cols
        row = index // cols
        rows = max(1, (roof_equipment_count + cols - 1) // cols)
        x = -width * 0.30 + width * 0.60 * (col + 0.5) / cols
        z = -depth * 0.28 + depth * 0.56 * (row + 0.5) / rows
        components.append(
            _component(
                f"roof_equipment_{index:02d}_region",
                "vent",
                equipment_part,
                (x, total_height + floor_height * 0.32, z),
                (width * 0.12, floor_height * 0.18, depth * 0.16),
                tags=["building", "roof", "equipment", "hvac", f"equipment_{index}", roof_style],
                adjacency=[roof_part],
            )
        )
    for index in range(fire_escape_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        y = total_height * (0.44 + 0.08 * (index % 3))
        z = depth * (0.24 - 0.12 * (index % 2))
        components.append(
            _component(
                f"{side}_fire_escape_stair_{index:02d}_region",
                "stair",
                fire_escape_part,
                (sign * width * 0.55, y, z),
                (width * 0.15, total_height * 0.36, depth * 0.26),
                tags=["building", "fire_escape", "stair", side, f"fire_escape_{index}", facade_style],
                adjacency=[body_part, wall_part],
            )
        )
        components.append(
            _component(
                f"{side}_fire_escape_railing_{index:02d}_region",
                "railing",
                fire_escape_part,
                (sign * width * 0.58, y + total_height * 0.10, z),
                (width * 0.045, total_height * 0.28, depth * 0.34),
                tags=["building", "fire_escape", "railing", side, f"fire_escape_{index}", facade_style],
                adjacency=[body_part, wall_part],
            )
        )
    for side, sign in (("left", -1.0), ("right", 1.0)):
        for floor_index in range(1, floors):
            for bay_index in range(side_window_bays):
                z = (bay_index - (side_window_bays - 1) / 2.0) * depth * 0.64 / max(1, side_window_bays - 1)
                components.append(
                    _component(
                        f"{side}_side_window_{floor_index:02d}_{bay_index:02d}_region",
                        "window",
                        window_part,
                        (sign * width * 0.535, floor_height * (floor_index + 0.52), z),
                        (width * 0.045, floor_height * 0.26, depth * 0.13),
                        tags=["building", "window", "side_wall", side, f"floor_{floor_index}", f"bay_{bay_index}"],
                        adjacency=[body_part, wall_part],
                    )
                )
    for floor_index in range(1, floors):
        for bay_index in range(rear_window_bays):
            x = (bay_index - (rear_window_bays - 1) / 2.0) * width * 0.66 / max(1, rear_window_bays - 1)
            components.append(
                _component(
                    f"rear_window_{floor_index:02d}_{bay_index:02d}_region",
                    "window",
                    window_part,
                    (x, floor_height * (floor_index + 0.52), -depth * 0.535),
                    (width * 0.11, floor_height * 0.25, depth * 0.045),
                    tags=["building", "window", "rear_wall", f"floor_{floor_index}", f"bay_{bay_index}"],
                    adjacency=[body_part, wall_part],
                )
            )
    for index in range(service_door_count):
        x = (index - (service_door_count - 1) / 2.0) * width * 0.42 / max(1, service_door_count - 1)
        components.append(
            _component(
                f"service_door_{index:02d}_region",
                "door",
                door_part,
                (x, floor_height * 0.30, -depth * 0.535),
                (width * 0.13, floor_height * 0.48, depth * 0.055),
                tags=["building", "door", "service", "rear_wall", f"service_{index}"],
                adjacency=[body_part, wall_part],
            )
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural building blueprint generated roof styles, wings, towers, facade bays, balconies, awnings, cornices, dormers, chimneys, entries, columns, stairs, storefronts, arcades, signage, parapets, roof equipment, fire escapes, side windows, rear windows, service doors, building envelope frames, floor stack plates, facade grid controls, vertical cores, and entrance plan controls"
        ],
    )


def _procedural_vehicle_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _with_loadout_controls("vehicle", _shape_controls(asset_graph))
    loadout_tags = _loadout_tags("vehicle", controls)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=1, maximum=24)
    scale = asset_graph.scale_cm
    drive_type = _choice(controls, "drive_type", "vehicle_type", "mobility", default="wheeled")
    wheel_count = _count(
        controls,
        "wheel_count",
        "wheels",
        default=0 if drive_type in {"drone", "vtol", "aircraft", "plane", "hover"} else 4,
        minimum=0,
        maximum=12,
    )
    track_count = _count(controls, "tracks", "track_count", default=2 if drive_type in {"tracked", "tank", "crawler"} else 0, minimum=0, maximum=4)
    suspension_count = _count(
        controls,
        "suspension",
        "suspension_count",
        default=max(2, wheel_count) if wheel_count or track_count else 0,
        minimum=0,
        maximum=12,
    )
    wing_count = _count(controls, "wings", "wing_count", default=2 if drive_type in {"aircraft", "plane"} else 0, minimum=0, maximum=6)
    rotor_count = _count(controls, "rotors", "rotor_count", default=4 if drive_type in {"drone", "vtol"} else 0, minimum=0, maximum=8)
    turret_count = _count(controls, "turrets", "turret_count", default=0, minimum=0, maximum=4)
    cargo_count = _count(controls, "cargo_modules", "cargo_module_count", "cargo_count", default=0, minimum=0, maximum=8)
    arm_count = _count(controls, "arms", "manipulator_count", "arm_count", default=0, minimum=0, maximum=6)
    crew_bay_count = _count(
        controls,
        "crew_bays",
        "crew_bay_count",
        "cockpit_count",
        default=1 if drive_type in {"aircraft", "plane", "drone", "vtol", "car", "wheeled", "tracked"} else 0,
        minimum=0,
        maximum=6,
    )
    cargo_bay_count = _count(
        controls,
        "cargo_bays",
        "cargo_bay_count",
        "payload_bays",
        default=1 if cargo_count or drive_type in {"truck", "cargo", "hauler"} else 0,
        minimum=0,
        maximum=8,
    )
    hardpoint_count = _count(
        controls,
        "hardpoints",
        "hardpoint_count",
        "weapon_mounts",
        default=max(0, turret_count * 2 + wing_count),
        minimum=0,
        maximum=24,
    )
    module_socket_count = _count(
        controls,
        "module_sockets",
        "module_socket_count",
        "equipment_slots",
        default=max(0, cargo_count + arm_count),
        minimum=0,
        maximum=24,
    )
    thruster_count = _count(
        controls,
        "thrusters",
        "thruster_count",
        "jet_count",
        default=2 if drive_type in {"aircraft", "plane", "vtol", "drone", "hover"} else 0,
        minimum=0,
        maximum=12,
    )
    stabilizer_count = _count(
        controls,
        "stabilizers",
        "stabilizer_count",
        "tail_fins",
        default=2 if drive_type in {"aircraft", "plane", "vtol", "drone"} else 0,
        minimum=0,
        maximum=8,
    )
    sensor_count = _count(
        controls,
        "sensors",
        "sensor_count",
        "antenna_count",
        default=1 if drive_type in {"drone", "vtol", "aircraft"} else 0,
        minimum=0,
        maximum=12,
    )
    axle_count = max(1, wheel_count // 2) if wheel_count else 0
    length = scale * _level(controls, "length_scale", "vehicle_length", default=1.35)
    width = scale * _level(controls, "width_scale", "vehicle_width", default=0.58)
    height = scale * _level(controls, "height_scale", "vehicle_height", default=0.34)

    chassis_part = _part_name(asset_graph, "chassis", "body", fallback="vehicle_chassis")
    cabin_part = _part_name(asset_graph, "cabin", "body", fallback=chassis_part)
    wheel_part = _part_name(asset_graph, "wheel", fallback=chassis_part)
    engine_part = _part_name(asset_graph, "engine", fallback=chassis_part)
    track_part = _part_name(asset_graph, "track", "tread", fallback=wheel_part)
    suspension_part = _part_name(asset_graph, "suspension", "axle", fallback=chassis_part)
    wing_part = _part_name(asset_graph, "wing", fallback=chassis_part)
    rotor_part = _part_name(asset_graph, "rotor", "prop", fallback=engine_part)
    cargo_part = _part_name(asset_graph, "cargo", "module", fallback=chassis_part)
    turret_part = _part_name(asset_graph, "turret", "mount", fallback=chassis_part)
    arm_part = _part_name(asset_graph, "arm", "manipulator", fallback=chassis_part)
    crew_part = _part_name(asset_graph, "crew", "cockpit", "cabin", fallback=cabin_part)
    cargo_bay_part = _part_name(asset_graph, "cargo", "bay", "payload", fallback=cargo_part)
    hardpoint_part = _part_name(asset_graph, "hardpoint", "mount", "socket", fallback=chassis_part)
    socket_part = _part_name(asset_graph, "socket", "module", "equipment", fallback=hardpoint_part)
    chock_part = _part_name(asset_graph, "wheel_chock", "wheel_stop", "parking_bay", fallback=wheel_part)
    tie_down_part = _part_name(asset_graph, "tie_down", "service_mount", "hangar_bay", fallback=hardpoint_part)
    umbilical_part = _part_name(asset_graph, "service_umbilical", "service_mount", "socket", fallback=socket_part)
    thruster_part = _part_name(asset_graph, "thruster", "jet", "engine", fallback=engine_part)
    stabilizer_part = _part_name(asset_graph, "stabilizer", "fin", "wing", fallback=wing_part)
    sensor_part = _part_name(asset_graph, "sensor", "antenna", "radar", fallback=cabin_part)

    components = [
        _component(
            "vehicle_chassis_region",
            "chassis",
            chassis_part,
            (0.0, height * 0.45, 0.0),
            (width, height, length),
            tags=["vehicle", "chassis", "body", *loadout_tags],
        ),
        _component(
            "vehicle_cabin_region",
            "cabin",
            cabin_part,
            (0.0, height * 1.02, -length * 0.08),
            (width * 0.72, height * 0.82, length * 0.34),
            tags=["vehicle", "cabin"],
            adjacency=[chassis_part],
        ),
        _component(
            "vehicle_engine_region",
            "engine",
            engine_part,
            (0.0, height * 0.48, length * 0.43),
            (width * 0.38, height * 0.44, length * 0.20),
            tags=["vehicle", "engine", "front"],
            adjacency=[chassis_part],
            radius=height * 0.16,
            height=length * 0.20,
        ),
    ]
    axle_spacing = length * 0.70 / max(1, axle_count - 1) if axle_count > 1 else 0.0
    start_z = -axle_spacing * (axle_count - 1) / 2.0
    for axle_index in range(axle_count):
        z = start_z + axle_spacing * axle_index + float(rng.uniform(-0.01, 0.01)) * length
        for side, sign in (("left", -1.0), ("right", 1.0)):
            components.append(
                _component(
                    f"{side}_wheel_{axle_index:02d}_region",
                    "wheel",
                    wheel_part,
                    (sign * width * 0.57, height * 0.18, z),
                    (width * 0.12, height * 0.44, height * 0.44),
                    tags=["vehicle", "wheel", side, f"axle_{axle_index}"],
                    adjacency=[chassis_part],
                    axis="x",
                    radius=height * 0.22,
                    height=width * 0.12,
            )
        )
    for side, sign in (("left", -1.0), ("right", 1.0)):
        if track_count:
            components.append(
                _component(
                    f"{side}_track_region",
                    "track",
                    track_part,
                    (sign * width * 0.58, height * 0.16, 0.0),
                    (width * 0.16, height * 0.34, length * 0.86),
                    tags=["vehicle", "track", "tread", side, drive_type],
                    adjacency=[chassis_part, wheel_part],
                )
            )
    for index in range(suspension_count):
        z = -length * 0.40 + length * 0.80 * (index / max(1, suspension_count - 1))
        components.append(
            _component(
                f"suspension_{index:02d}_region",
                "suspension",
                suspension_part,
                (0.0, height * 0.20, z),
                (width * 1.10, height * 0.12, length * 0.035),
                tags=["vehicle", "suspension", "axle", f"suspension_{index}", drive_type],
                adjacency=[chassis_part, wheel_part, track_part],
            )
        )
    for index in range(cargo_count):
        z = -length * 0.22 + index * length * 0.16
        components.append(
            _component(
                f"cargo_module_{index:02d}_region",
                "cargo_module",
                cargo_part,
                (0.0, height * 0.92, z),
                (width * 0.72, height * 0.36, length * 0.16),
                tags=["vehicle", "cargo", "module", f"cargo_{index}", drive_type],
                adjacency=[chassis_part, cabin_part],
            )
        )
    for index in range(turret_count):
        z = -length * 0.08 + index * length * 0.18
        components.append(
            _component(
                f"turret_{index:02d}_region",
                "turret",
                turret_part,
                (0.0, height * 1.30, z),
                (width * 0.34, height * 0.30, width * 0.34),
                tags=["vehicle", "turret", "mount", f"turret_{index}", drive_type],
                adjacency=[chassis_part, cabin_part],
                radius=width * 0.16,
                height=height * 0.30,
            )
        )
    for index in range(wing_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -length * 0.04 + (index // 2) * length * 0.16
        components.append(
            _component(
                f"{side}_wing_{index:02d}_region",
                "wing",
                wing_part,
                (sign * width * 0.78, height * 0.66, z),
                (width * 0.92, height * 0.08, length * 0.28),
                tags=["vehicle", "wing", side, f"wing_{index}", drive_type],
                adjacency=[chassis_part],
            )
        )
    rotor_positions = [
        ("front_left", -0.62, 0.36),
        ("front_right", 0.62, 0.36),
        ("rear_left", -0.62, -0.36),
        ("rear_right", 0.62, -0.36),
        ("mid_left", -0.68, 0.0),
        ("mid_right", 0.68, 0.0),
        ("nose", 0.0, 0.52),
        ("tail", 0.0, -0.52),
    ]
    for index in range(rotor_count):
        label, x_factor, z_factor = rotor_positions[index % len(rotor_positions)]
        x = x_factor * width
        z = z_factor * length
        components.append(
            _component(
                f"rotor_arm_{index:02d}_{label}_region",
                "rotor_arm",
                rotor_part,
                (x * 0.50, height * 0.92, z * 0.50),
                (max(abs(x), width * 0.24), height * 0.08, max(abs(z), length * 0.20)),
                tags=["vehicle", "rotor", "arm", label, drive_type],
                adjacency=[chassis_part],
            )
        )
        components.append(
            _component(
                f"rotor_pod_{index:02d}_{label}_region",
                "rotor_pod",
                rotor_part,
                (x, height * 1.02, z),
                (width * 0.26, height * 0.16, width * 0.26),
                tags=["vehicle", "rotor", "pod", label, drive_type],
                adjacency=[chassis_part],
                axis="y",
                radius=width * 0.13,
                height=height * 0.16,
            )
        )
    for index in range(arm_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = length * (0.10 + 0.12 * (index // 2))
        components.append(
            _component(
                f"{side}_manipulator_arm_{index:02d}_region",
                "manipulator_arm",
                arm_part,
                (sign * width * 0.54, height * 0.72, z),
                (width * 0.12, height * 0.16, length * 0.34),
                tags=["vehicle", "arm", "manipulator", side, f"arm_{index}", drive_type],
                adjacency=[chassis_part],
            )
        )
    for index in range(crew_bay_count):
        z = -length * 0.18 + index * length * 0.18
        components.append(
            _component(
                f"crew_bay_{index:02d}_region",
                "crew_bay",
                crew_part,
                (0.0, height * 1.18, z),
                (width * 0.52, height * 0.40, length * 0.18),
                tags=["vehicle", "crew", "cockpit", "bay", f"crew_bay_{index}", drive_type],
                adjacency=[chassis_part, cabin_part],
            )
        )
    for index in range(cargo_bay_count):
        z = -length * 0.30 + length * 0.60 * ((index + 0.5) / max(1, cargo_bay_count))
        components.append(
            _component(
                f"payload_bay_{index:02d}_region",
                "cargo_bay",
                cargo_bay_part,
                (0.0, height * 0.58, z),
                (width * 0.66, height * 0.30, length * 0.18),
                tags=["vehicle", "cargo", "payload", "bay", f"payload_bay_{index}", drive_type],
                adjacency=[chassis_part, cargo_part],
            )
        )
    hardpoint_positions = [
        ("left_wing", -0.82, 0.12),
        ("right_wing", 0.82, 0.12),
        ("left_side", -0.62, -0.18),
        ("right_side", 0.62, -0.18),
        ("roof_front", -0.22, 0.28),
        ("roof_rear", 0.22, -0.28),
        ("nose", 0.0, 0.50),
        ("tail", 0.0, -0.50),
    ]
    for index in range(hardpoint_count):
        label, x_factor, z_factor = hardpoint_positions[index % len(hardpoint_positions)]
        components.append(
            _component(
                f"vehicle_hardpoint_{index:02d}_{label}_region",
                "hardpoint",
                hardpoint_part,
                (x_factor * width, height * (0.86 + 0.08 * (index % 2)), z_factor * length),
                (width * 0.16, height * 0.08, length * 0.12),
                tags=["vehicle", "hardpoint", "weapon_mount", label, f"hardpoint_{index}", drive_type],
                adjacency=[chassis_part, wing_part, turret_part],
                interface_role="socket",
            )
        )
    socket_positions = [
        ("roof", 0.0, -0.12),
        ("rear_deck", 0.0, -0.40),
        ("front_deck", 0.0, 0.36),
        ("left_flank", -0.48, 0.0),
        ("right_flank", 0.48, 0.0),
        ("cargo_spine", 0.0, 0.08),
    ]
    for index in range(module_socket_count):
        label, x_factor, z_factor = socket_positions[index % len(socket_positions)]
        components.append(
            _component(
                f"vehicle_module_socket_{index:02d}_{label}_region",
                "module_socket",
                socket_part,
                (x_factor * width, height * 1.02, z_factor * length),
                (width * 0.18, height * 0.07, length * 0.12),
                tags=["vehicle", "module_socket", "equipment_slot", label, f"module_socket_{index}", drive_type],
                adjacency=[chassis_part, cargo_part, cabin_part],
                interface_role="socket",
            )
        )
    for index in range(thruster_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        row = index // 2
        z = -length * (0.48 - 0.12 * row)
        components.append(
            _component(
                f"{side}_thruster_{index:02d}_region",
                "thruster",
                thruster_part,
                (sign * width * 0.34, height * 0.50, z),
                (width * 0.18, height * 0.18, length * 0.12),
                tags=["vehicle", "thruster", "propulsion", side, f"thruster_{index}", drive_type],
                adjacency=[chassis_part, engine_part],
                axis="z",
                radius=height * 0.07,
                height=length * 0.12,
            )
        )
    for index in range(stabilizer_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        vertical = index >= 2 and index % 3 == 2
        components.append(
            _component(
                f"{side}_stabilizer_{index:02d}_region",
                "stabilizer",
                stabilizer_part,
                (sign * width * (0.48 if not vertical else 0.10), height * (0.82 if not vertical else 1.08), -length * 0.46),
                (width * (0.44 if not vertical else 0.16), height * 0.07, length * 0.16),
                tags=["vehicle", "stabilizer", "fin", side, "vertical" if vertical else "horizontal", f"stabilizer_{index}", drive_type],
                adjacency=[chassis_part, wing_part],
            )
        )
    for index in range(sensor_count):
        x = (index - (sensor_count - 1) / 2.0) * width * 0.24 / max(1, sensor_count - 1)
        z = -length * 0.10 + length * 0.12 * (index % 3)
        components.append(
            _component(
                f"vehicle_sensor_antenna_{index:02d}_region",
                "antenna",
                sensor_part,
                (x, height * 1.46, z),
                (width * 0.16, height * 0.40, width * 0.08),
                tags=["vehicle", "sensor", "antenna", "comms", f"sensor_{index}", drive_type],
                adjacency=[cabin_part, chassis_part],
                radius=width * 0.012,
                height=height * 0.40,
                interface_role="socket",
            )
        )
    if assembly_member and assembly_mode in {"parking", "hangar", "convoy"}:
        chock_count = max(2, min(8, wheel_count or track_count * 2 or 2)) if assembly_mode in {"parking", "hangar"} else 0
        for index in range(chock_count):
            side = "left" if index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            z = -length * 0.36 + length * 0.72 * ((index // 2 + 0.5) / max(1, (chock_count + 1) // 2))
            components.append(
                _component(
                    f"{assembly_mode}_wheel_chock_{index:02d}_{side}_region",
                    "wheel_chock",
                    chock_part,
                    (sign * width * 0.50, height * 0.08, z),
                    (width * 0.18, height * 0.14, length * 0.08),
                    tags=["vehicle", "assembly_member", assembly_mode, "wheel_chock", side, f"assembly_slot_{assembly_slot_count}"],
                    adjacency=[chassis_part, wheel_part, track_part],
                )
            )
        tie_count = max(2, min(6, assembly_slot_count or 2)) if assembly_mode == "hangar" else max(0, min(4, assembly_slot_count))
        for index in range(tie_count):
            side = "left" if index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            z = -length * 0.42 + length * 0.84 * ((index // 2 + 0.5) / max(1, (tie_count + 1) // 2))
            components.append(
                _component(
                    f"{assembly_mode}_tie_down_{index:02d}_{side}_region",
                    "tie_down",
                    tie_down_part,
                    (sign * width * 0.44, height * 0.34, z),
                    (width * 0.10, height * 0.08, length * 0.12),
                    tags=["vehicle", "assembly_member", assembly_mode, "tie_down", "snap_mount", side, f"tie_{index}"],
                    adjacency=[chassis_part, hardpoint_part, socket_part],
                    interface_role="socket",
                )
            )
        if assembly_mode == "hangar":
            for index in range(max(1, min(3, assembly_slot_count or 1))):
                z = -length * 0.28 + length * 0.28 * index
                components.append(
                    _component(
                        f"hangar_service_umbilical_{index:02d}_region",
                        "service_umbilical",
                        umbilical_part,
                        (width * 0.48, height * 0.70, z),
                        (width * 0.08, height * 0.12, length * 0.22),
                        tags=["vehicle", "assembly_member", "hangar", "service_umbilical", "power_coupler", f"umbilical_{index}"],
                        adjacency=[chassis_part, engine_part, socket_part],
                        interface_role="socket",
                    )
                )
        if assembly_mode == "convoy":
            for label, z in (("front", length * 0.52), ("rear", -length * 0.52)):
                components.append(
                    _component(
                        f"convoy_{label}_link_region",
                        "convoy_link",
                        tie_down_part,
                        (0.0, height * 0.36, z),
                        (width * 0.26, height * 0.10, length * 0.08),
                        tags=["vehicle", "assembly_member", "convoy", "chain_link", label],
                        adjacency=[chassis_part],
                        interface_role="socket",
                    )
                )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural vehicle blueprint generated chassis, cabin, engine, wheels, tracks, suspension, cargo modules, turrets, wings, rotors, manipulator arms, crew bays, payload bays, hardpoints, module sockets, thrusters, stabilizers, sensor antennas, and assembly-conditioned parking/hangar/convoy hardware"
        ],
    )


def _procedural_weapon_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _with_loadout_controls("weapon", _shape_controls(asset_graph))
    loadout_tags = _loadout_tags("weapon", controls)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=1, maximum=16)
    scale = asset_graph.scale_cm
    weapon_type = _choice(controls, "weapon_type", "tool_type", "archetype", default="rifle")
    blade_count = _count(controls, "blades", "blade_count", default=1 if weapon_type in {"sword", "knife", "spear", "axe"} else 0, minimum=0, maximum=4)
    barrel_count = _count(
        controls,
        "barrels",
        "barrel_count",
        default=1
        if weapon_type in {"rifle", "pistol", "launcher", "shotgun", "railgun", "laser", "plasma", "arc", "energy"}
        else 0,
        minimum=0,
        maximum=6,
    )
    magazine_count = _count(controls, "magazines", "magazine_count", default=1 if barrel_count else 0, minimum=0, maximum=4)
    sight_count = _count(controls, "sights", "sight_count", default=1 if barrel_count else 0, minimum=0, maximum=4)
    head_count = _count(controls, "heads", "head_count", "tool_head_count", default=1 if weapon_type in {"axe", "hammer", "pick"} else 0, minimum=0, maximum=4)
    guard_count = _count(controls, "guards", "guard_count", default=1 if weapon_type in {"sword", "knife"} else 0, minimum=0, maximum=4)
    rail_count = _count(
        controls,
        "rails",
        "rail_count",
        "attachment_rails",
        default=2 if barrel_count else 0,
        minimum=0,
        maximum=12,
    )
    hardpoint_count = _count(
        controls,
        "hardpoints",
        "hardpoint_count",
        "attachment_points",
        default=max(0, rail_count + sight_count),
        minimum=0,
        maximum=16,
    )
    module_socket_count = _count(
        controls,
        "module_sockets",
        "module_socket_count",
        "attachment_sockets",
        default=2 if rail_count or barrel_count else 0,
        minimum=0,
        maximum=16,
    )
    muzzle_device_count = _count(
        controls,
        "muzzle_devices",
        "muzzle_device_count",
        "compensator_count",
        default=barrel_count,
        minimum=0,
        maximum=8,
    )
    ammo_bay_count = _count(
        controls,
        "ammo_bays",
        "ammo_bay_count",
        "battery_bays",
        default=1 if barrel_count or magazine_count else 0,
        minimum=0,
        maximum=8,
    )
    power_cell_count = _count(
        controls,
        "power_cells",
        "power_cell_count",
        "energy_cells",
        default=1 if weapon_type in {"laser", "plasma", "arc", "energy"} else 0,
        minimum=0,
        maximum=8,
    )
    sling_mount_count = _count(
        controls,
        "sling_mounts",
        "sling_mount_count",
        default=2 if weapon_type in {"rifle", "launcher", "spear", "staff", "railgun"} else 0,
        minimum=0,
        maximum=6,
    )
    stabilizer_count = _count(
        controls,
        "stabilizers",
        "stabilizer_count",
        default=1 if weapon_type in {"rifle", "launcher", "railgun"} else 0,
        minimum=0,
        maximum=6,
    )
    smart_sensor_count = _count(
        controls,
        "smart_sensors",
        "sensor_count",
        "antenna_count",
        default=1 if weapon_type in {"smart", "laser", "railgun", "plasma"} else 0,
        minimum=0,
        maximum=8,
    )
    length = scale * _level(controls, "length_scale", "weapon_length", default=1.25 if barrel_count else 1.05)
    width = scale * _level(controls, "width_scale", "weapon_width", default=0.22)
    thickness = scale * _level(controls, "thickness_scale", "weapon_thickness", default=0.12)

    body_part = _part_name(asset_graph, "receiver", "body", fallback="weapon_body")
    barrel_part = _part_name(asset_graph, "barrel", fallback=body_part)
    blade_part = _part_name(asset_graph, "blade", fallback=body_part)
    tip_part = _part_name(asset_graph, "tip", "point", fallback=blade_part)
    grip_part = _part_name(asset_graph, "grip", "handle", fallback=body_part)
    guard_part = _part_name(asset_graph, "guard", fallback=grip_part)
    stock_part = _part_name(asset_graph, "stock", "butt", fallback=body_part)
    magazine_part = _part_name(asset_graph, "magazine", fallback=body_part)
    sight_part = _part_name(asset_graph, "sight", "optic", fallback=body_part)
    trigger_part = _part_name(asset_graph, "trigger", fallback=grip_part)
    head_part = _part_name(asset_graph, "head", "axe", "hammer", fallback=blade_part)
    hardpoint_part = _part_name(asset_graph, "hardpoint", "mount", "rail", fallback=body_part)
    socket_part = _part_name(asset_graph, "socket", "module", "attachment", fallback=hardpoint_part)
    rack_part = _part_name(asset_graph, "rack_clamp", "rack_socket", "weapon_mount", fallback=socket_part)
    rack_label_part = _part_name(asset_graph, "rack_label", "assembly_slot", "socket", fallback=rack_part)
    muzzle_part = _part_name(asset_graph, "muzzle", "compensator", "barrel", fallback=barrel_part)
    bay_part = _part_name(asset_graph, "bay", "ammo", "battery", fallback=magazine_part)
    power_part = _part_name(asset_graph, "power", "cell", "battery", fallback=magazine_part)
    sling_part = _part_name(asset_graph, "sling", "mount", "ring", fallback=guard_part)
    stabilizer_part = _part_name(asset_graph, "stabilizer", "fin", fallback=barrel_part)
    sensor_part = _part_name(asset_graph, "sensor", "antenna", "optic", fallback=sight_part)

    components = [
        _component(
            "weapon_body_region",
            "weapon_body",
            body_part,
            (0.0, 0.0, 0.0),
            (width, thickness, length * 0.34),
            tags=["weapon", "body", "receiver", weapon_type, *loadout_tags],
        ),
        _component(
            "weapon_grip_region",
            "grip",
            grip_part,
            (0.0, -thickness * 1.20, -length * 0.10),
            (width * 0.42, length * 0.22, thickness * 0.72),
            tags=["weapon", "grip", "handle", weapon_type],
            adjacency=[body_part],
            axis="y",
            radius=width * 0.11,
            height=length * 0.22,
            interface_role="grip",
        ),
    ]
    if barrel_count:
        barrel_spacing = width * 0.34 / max(1, barrel_count - 1) if barrel_count > 1 else 0.0
        start_x = -barrel_spacing * (barrel_count - 1) / 2.0
        for index in range(barrel_count):
            x = start_x + barrel_spacing * index
            components.append(
                _component(
                    f"weapon_barrel_{index:02d}_region",
                    "barrel",
                    barrel_part,
                    (x, thickness * 0.08, length * 0.33),
                    (width * 0.11, width * 0.11, length * 0.58),
                    tags=["weapon", "barrel", "muzzle", weapon_type, f"barrel_{index}"],
                    adjacency=[body_part],
                    axis="z",
                    radius=width * 0.055,
                    height=length * 0.58,
                )
            )
        components.append(
            _component(
                "weapon_stock_region",
                "stock",
                stock_part,
                (0.0, -thickness * 0.02, -length * 0.34),
                (width * 0.72, thickness * 1.45, length * 0.28),
                tags=["weapon", "stock", "butt", weapon_type],
                adjacency=[body_part, grip_part],
            )
        )
        components.append(
            _component(
                "weapon_trigger_region",
                "trigger",
                trigger_part,
                (0.0, -thickness * 0.54, -length * 0.02),
                (width * 0.26, thickness * 0.46, thickness * 0.18),
                tags=["weapon", "trigger", weapon_type],
                adjacency=[body_part, grip_part],
            )
        )
    for index in range(magazine_count):
        x = (index - (magazine_count - 1) / 2.0) * width * 0.28
        components.append(
            _component(
                f"weapon_magazine_{index:02d}_region",
                "magazine",
                magazine_part,
                (x, -thickness * 0.76, length * 0.04),
                (width * 0.28, thickness * 1.10, length * 0.14),
                tags=["weapon", "magazine", "ammo", weapon_type, f"magazine_{index}"],
                adjacency=[body_part],
            )
        )
    for index in range(sight_count):
        z = -length * 0.08 + index * length * 0.14
        components.append(
            _component(
                f"weapon_sight_{index:02d}_region",
                "sight",
                sight_part,
                (0.0, thickness * 0.86, z),
                (width * 0.34, thickness * 0.28, length * 0.10),
                tags=["weapon", "sight", "optic", weapon_type, f"sight_{index}"],
                adjacency=[body_part],
            )
        )
    if blade_count:
        blade_spacing = width * 0.26 / max(1, blade_count - 1) if blade_count > 1 else 0.0
        start_x = -blade_spacing * (blade_count - 1) / 2.0
        for index in range(blade_count):
            x = start_x + blade_spacing * index
            blade_length = length * (0.58 if weapon_type != "spear" else 0.30)
            z = length * 0.28 if weapon_type in {"spear", "axe", "hammer", "pick"} else length * 0.24
            components.append(
                _component(
                    f"weapon_blade_{index:02d}_region",
                    "blade",
                    blade_part,
                    (x, thickness * 0.08, z),
                    (width * (0.32 if weapon_type != "spear" else 0.18), blade_length, thickness * 0.24),
                    tags=["weapon", "blade", weapon_type, f"blade_{index}"],
                    adjacency=[body_part, guard_part],
                )
            )
            components.append(
                _component(
                    f"weapon_tip_{index:02d}_region",
                    "blade_tip",
                    tip_part,
                    (x, thickness * 0.08 + blade_length * 0.56, z),
                    (width * 0.30, length * 0.08, thickness * 0.24),
                    tags=["weapon", "tip", "point", weapon_type, f"blade_{index}"],
                    adjacency=[blade_part],
                )
            )
    for index in range(guard_count):
        components.append(
            _component(
                f"weapon_guard_{index:02d}_region",
                "guard",
                guard_part,
                (0.0, -thickness * 0.08, length * 0.02),
                (width * 1.45, thickness * 0.28, thickness * 0.34),
                tags=["weapon", "guard", "hand_stop", weapon_type, f"guard_{index}"],
                adjacency=[body_part, grip_part],
                axis="x",
                radius=thickness * 0.16,
                height=width * 1.45,
            )
        )
    for index in range(head_count):
        side = -1.0 if index % 2 == 0 else 1.0
        components.append(
            _component(
                f"weapon_tool_head_{index:02d}_region",
                "tool_head",
                head_part,
                (side * width * 0.24, thickness * 0.18, length * 0.34),
                (width * 0.58, length * 0.20, thickness * 0.42),
                tags=["weapon", "tool", "head", weapon_type, f"head_{index}"],
                adjacency=[body_part, grip_part],
            )
        )
    rail_positions = [
        ("top", 0.0, thickness * 0.68, length * 0.02),
        ("underbarrel", 0.0, -thickness * 0.62, length * 0.16),
        ("left", -width * 0.52, thickness * 0.04, length * 0.06),
        ("right", width * 0.52, thickness * 0.04, length * 0.06),
    ]
    for index in range(rail_count):
        label, x, y, z = rail_positions[index % len(rail_positions)]
        horizontal = label in {"left", "right"}
        components.append(
            _component(
                f"weapon_attachment_rail_{index:02d}_{label}_region",
                "hardpoint",
                hardpoint_part,
                (x, y, z),
                (width * (0.16 if not horizontal else 0.08), thickness * 0.18, length * 0.34),
                tags=["weapon", "attachment_rail", "hardpoint", label, weapon_type, f"rail_{index}"],
                adjacency=[body_part, barrel_part],
                interface_role="socket",
            )
        )
    hardpoint_positions = [
        ("top_front", 0.0, thickness * 0.84, length * 0.20),
        ("top_rear", 0.0, thickness * 0.84, -length * 0.08),
        ("left_side", -width * 0.58, thickness * 0.10, length * 0.06),
        ("right_side", width * 0.58, thickness * 0.10, length * 0.06),
        ("underbarrel", 0.0, -thickness * 0.74, length * 0.22),
        ("pommel", 0.0, -thickness * 0.18, -length * 0.44),
    ]
    for index in range(hardpoint_count):
        label, x, y, z = hardpoint_positions[index % len(hardpoint_positions)]
        components.append(
            _component(
                f"weapon_hardpoint_{index:02d}_{label}_region",
                "hardpoint",
                hardpoint_part,
                (x, y, z),
                (width * 0.20, thickness * 0.16, length * 0.10),
                tags=["weapon", "hardpoint", "attachment_point", label, weapon_type, f"hardpoint_{index}"],
                adjacency=[body_part, barrel_part, grip_part],
                interface_role="socket",
            )
        )
    socket_positions = [
        ("optic_socket", 0.0, thickness * 0.98, length * 0.02),
        ("under_socket", 0.0, -thickness * 0.92, length * 0.12),
        ("rear_socket", 0.0, thickness * 0.30, -length * 0.28),
        ("fore_socket", 0.0, thickness * 0.30, length * 0.30),
    ]
    for index in range(module_socket_count):
        label, x, y, z = socket_positions[index % len(socket_positions)]
        components.append(
            _component(
                f"weapon_module_socket_{index:02d}_{label}_region",
                "module_socket",
                socket_part,
                (x, y, z),
                (width * 0.22, thickness * 0.14, length * 0.11),
                tags=["weapon", "module_socket", "attachment_socket", label, weapon_type, f"socket_{index}"],
                adjacency=[body_part, hardpoint_part],
                interface_role="socket",
            )
        )
    for index in range(muzzle_device_count):
        x = (index - (muzzle_device_count - 1) / 2.0) * width * 0.18 / max(1, muzzle_device_count - 1)
        components.append(
            _component(
                f"muzzle_device_{index:02d}_region",
                "barrel",
                muzzle_part,
                (x, thickness * 0.08, length * 0.66),
                (width * 0.14, width * 0.14, length * 0.10),
                tags=["weapon", "muzzle_device", "compensator", weapon_type, f"muzzle_device_{index}"],
                adjacency=[barrel_part, body_part],
                axis="z",
                radius=width * 0.07,
                height=length * 0.10,
            )
        )
    for index in range(ammo_bay_count):
        z = -length * 0.02 + index * length * 0.10
        components.append(
            _component(
                f"ammo_bay_{index:02d}_region",
                "cargo_bay",
                bay_part,
                (0.0, -thickness * 0.38, z),
                (width * 0.48, thickness * 0.32, length * 0.12),
                tags=["weapon", "ammo_bay", "battery_bay", weapon_type, f"bay_{index}"],
                adjacency=[body_part, magazine_part],
            )
        )
    for index in range(power_cell_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_power_cell_{index:02d}_region",
                "magazine",
                power_part,
                (sign * width * 0.34, -thickness * 0.20, -length * 0.06 + index * length * 0.06),
                (width * 0.18, thickness * 0.30, length * 0.13),
                tags=["weapon", "power_cell", "energy_cell", side, weapon_type, f"power_cell_{index}"],
                adjacency=[body_part, magazine_part],
            )
        )
    for index in range(sling_mount_count):
        z = -length * 0.44 + length * 0.82 * (index / max(1, sling_mount_count - 1))
        components.append(
            _component(
                f"sling_mount_{index:02d}_region",
                "hardpoint",
                sling_part,
                (0.0, thickness * 0.28, z),
                (width * 0.20, thickness * 0.12, length * 0.055),
                tags=["weapon", "sling_mount", "carry_point", weapon_type, f"sling_{index}"],
                adjacency=[body_part, stock_part, grip_part],
                interface_role="socket",
            )
        )
    for index in range(stabilizer_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_weapon_stabilizer_{index:02d}_region",
                "stabilizer",
                stabilizer_part,
                (sign * width * 0.42, thickness * 0.06, length * 0.36),
                (width * 0.30, thickness * 0.08, length * 0.18),
                tags=["weapon", "stabilizer", "fin", side, weapon_type, f"stabilizer_{index}"],
                adjacency=[barrel_part, body_part],
            )
        )
    for index in range(smart_sensor_count):
        x = (index - (smart_sensor_count - 1) / 2.0) * width * 0.20 / max(1, smart_sensor_count - 1)
        components.append(
            _component(
                f"smart_sensor_{index:02d}_region",
                "antenna",
                sensor_part,
                (x, thickness * 1.20, length * 0.05),
                (width * 0.15, thickness * 0.50, width * 0.08),
                tags=["weapon", "smart_sensor", "antenna", "targeting", weapon_type, f"sensor_{index}"],
                adjacency=[body_part, sight_part],
                radius=width * 0.012,
                height=thickness * 0.50,
                interface_role="socket",
            )
        )
    if assembly_member and assembly_mode == "rack":
        clamp_count = max(2, min(6, assembly_slot_count or 2))
        for index in range(clamp_count):
            z = -length * 0.38 + length * 0.76 * ((index + 0.5) / clamp_count)
            side = "left" if index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            components.append(
                _component(
                    f"rack_clamp_{index:02d}_{side}_region",
                    "rack_clamp",
                    rack_part,
                    (sign * width * 0.56, thickness * 0.16, z),
                    (width * 0.12, thickness * 0.28, length * 0.10),
                    tags=["weapon", "assembly_member", "rack", "rack_clamp", side, f"clamp_{index}", weapon_type],
                    adjacency=[body_part, hardpoint_part, socket_part],
                    interface_role="socket",
                )
            )
        for index, z in enumerate((-length * 0.42, length * 0.42)):
            components.append(
                _component(
                    f"rack_index_label_{index:02d}_region",
                    "rack_label",
                    rack_label_part,
                    (0.0, thickness * 1.08, z),
                    (width * 0.44, thickness * 0.06, length * 0.08),
                    tags=["weapon", "assembly_member", "rack", "index_label", f"rack_label_{index}", weapon_type],
                    adjacency=[body_part, rack_part],
                )
            )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural weapon blueprint generated reusable ranged, blade, spear, axe, hammer, and tool-part layouts with rails, hardpoints, module sockets, muzzle devices, ammo bays, power cells, sling mounts, stabilizers, smart sensors, and rack-conditioned clamps and labels"
        ],
    )


def _procedural_machine_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    machine_type = _choice(controls, "machine_type", "mechanism_type", "archetype", default="industrial")
    arm_count = _count(controls, "arms", "arm_count", "manipulator_count", default=2, minimum=0, maximum=8)
    piston_count = _count(controls, "pistons", "piston_count", "hydraulic_count", default=max(1, arm_count), minimum=0, maximum=12)
    conveyor_count = _count(controls, "conveyors", "conveyor_count", default=1 if machine_type in {"factory", "industrial", "assembler"} else 0, minimum=0, maximum=6)
    gear_count = _count(controls, "gears", "gear_count", default=2, minimum=0, maximum=12)
    tank_count = _count(controls, "tanks", "tank_count", "vessel_count", default=0, minimum=0, maximum=8)
    crane_count = _count(controls, "cranes", "crane_count", "boom_count", default=1 if machine_type in {"crane", "loader"} else 0, minimum=0, maximum=4)
    tool_count = _count(controls, "tools", "tool_count", "tool_head_count", default=1 if arm_count else 0, minimum=0, maximum=8)
    width = scale * _level(controls, "width_scale", "machine_width", default=0.90)
    depth = scale * _level(controls, "depth_scale", "machine_depth", default=1.05)
    height = scale * _level(controls, "height_scale", "machine_height", default=0.72)

    base_part = _part_name(asset_graph, "base", "body", fallback="machine_base")
    column_part = _part_name(asset_graph, "column", "support", fallback=base_part)
    arm_part = _part_name(asset_graph, "arm", "manipulator", fallback=column_part)
    hydraulic_part = _part_name(asset_graph, "hydraulic", "piston", fallback=arm_part)
    conveyor_part = _part_name(asset_graph, "conveyor", "belt", fallback=base_part)
    gear_part = _part_name(asset_graph, "gear", "wheel", fallback=base_part)
    tank_part = _part_name(asset_graph, "tank", "vessel", fallback=base_part)
    crane_part = _part_name(asset_graph, "crane", "boom", fallback=arm_part)
    tool_part = _part_name(asset_graph, "tool", "head", fallback=arm_part)

    components = [
        _component(
            "machine_base_region",
            "machine_base",
            base_part,
            (0.0, height * 0.18, 0.0),
            (width, height * 0.36, depth),
            tags=["machine", "base", machine_type],
        ),
        _component(
            "machine_column_region",
            "machine_column",
            column_part,
            (0.0, height * 0.66, -depth * 0.22),
            (width * 0.22, height * 0.92, width * 0.22),
            tags=["machine", "column", "support", machine_type],
            adjacency=[base_part],
        ),
    ]
    for index in range(arm_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -depth * 0.12 + depth * 0.24 * (index // 2)
        components.append(
            _component(
                f"{side}_machine_arm_{index:02d}_region",
                "manipulator_arm",
                arm_part,
                (sign * width * 0.26, height * 0.86, z),
                (width * 0.12, height * 0.16, depth * 0.44),
                tags=["machine", "arm", "manipulator", side, f"arm_{index}", machine_type],
                adjacency=[column_part, base_part],
            )
        )
    for index in range(piston_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -depth * 0.28 + depth * 0.56 * (index / max(1, piston_count - 1))
        components.append(
            _component(
                f"{side}_hydraulic_{index:02d}_region",
                "hydraulic_piston",
                hydraulic_part,
                (sign * width * 0.18, height * 0.64, z),
                (width * 0.08, height * 0.42, width * 0.08),
                tags=["machine", "hydraulic", "piston", side, f"piston_{index}", machine_type],
                adjacency=[base_part, arm_part],
                axis="y",
                radius=width * 0.035,
                height=height * 0.42,
            )
        )
    for index in range(conveyor_count):
        z = -depth * 0.18 + index * depth * 0.24
        components.append(
            _component(
                f"conveyor_{index:02d}_region",
                "conveyor",
                conveyor_part,
                (0.0, height * 0.44, z),
                (width * 0.92, height * 0.18, depth * 0.20),
                tags=["machine", "conveyor", "belt", f"conveyor_{index}", machine_type],
                adjacency=[base_part],
            )
        )
    for index in range(gear_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        y = height * (0.48 + 0.12 * (index % 3))
        z = -depth * 0.34 + depth * 0.68 * ((index // 2) / max(1, (gear_count + 1) // 2 - 1))
        components.append(
            _component(
                f"{side}_gear_{index:02d}_region",
                "gear",
                gear_part,
                (sign * width * 0.50, y, z),
                (width * 0.18, width * 0.18, width * 0.08),
                tags=["machine", "gear", side, f"gear_{index}", machine_type],
                adjacency=[base_part, column_part],
                axis="x",
                radius=width * 0.09,
                height=width * 0.08,
            )
        )
    for index in range(tank_count):
        x = (index - (tank_count - 1) / 2.0) * width * 0.28
        components.append(
            _component(
                f"machine_tank_{index:02d}_region",
                "tank",
                tank_part,
                (x, height * 0.62, depth * 0.28),
                (width * 0.22, height * 0.52, width * 0.22),
                tags=["machine", "tank", "vessel", f"tank_{index}", machine_type],
                adjacency=[base_part],
                axis="y",
                radius=width * 0.11,
                height=height * 0.52,
            )
        )
    for index in range(crane_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_crane_boom_{index:02d}_region",
                "crane_boom",
                crane_part,
                (sign * width * 0.28, height * 1.08, depth * 0.20),
                (width * 0.12, height * 0.12, depth * 0.74),
                tags=["machine", "crane", "boom", side, f"crane_{index}", machine_type],
                adjacency=[column_part, arm_part],
            )
        )
    for index in range(tool_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = depth * (0.18 + 0.10 * (index // 2))
        components.append(
            _component(
                f"{side}_tool_head_{index:02d}_region",
                "tool_head",
                tool_part,
                (sign * width * 0.34, height * 0.62, z),
                (width * 0.20, height * 0.18, width * 0.16),
                tags=["machine", "tool", "head", side, f"tool_{index}", machine_type],
                adjacency=[arm_part, hydraulic_part],
            )
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural machine blueprint generated bases, columns, articulated arms, hydraulics, conveyors, gears, tanks, crane booms, and tool heads"
        ],
    )


def _procedural_boat_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _with_loadout_controls("boat", _shape_controls(asset_graph))
    loadout_tags = _loadout_tags("boat", controls)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=1, maximum=16)
    scale = asset_graph.scale_cm
    boat_type = _choice(controls, "boat_type", "hull_type", "watercraft_type", "vessel_type", default="workboat")
    propulsion = _choice(controls, "propulsion", "drive_type", default="")
    sailing_mode = boat_type in {"sailboat", "sloop", "schooner", "ketch", "cutter", "tall_ship"} or propulsion in {
        "sail",
        "hybrid_sail",
    }
    mast_count = _count(controls, "mast_count", "masts", default=1 if sailing_mode or not propulsion else 0, minimum=0, maximum=6)
    engine_count = _count(controls, "engine_count", "engines", default=0 if propulsion == "sail" else 1, minimum=0, maximum=4)
    cabin_count = _count(controls, "cabin_count", "cabins", default=1, minimum=0, maximum=4)
    deck_level_count = _count(controls, "deck_level_count", "deck_levels", default=1, minimum=1, maximum=4)
    pontoon_default = 2 if boat_type in {"catamaran", "trimaran", "pontoon", "pontoon_boat"} else 0
    outrigger_default = 2 if boat_type in {"outrigger", "canoe", "waka", "prahu"} else 0
    sail_default = mast_count if mast_count and (sailing_mode or mast_count > 0) else 0
    propeller_default = max(0, engine_count)
    cargo_default = 1 if boat_type in {"barge", "freighter", "cargo", "cargo_ship", "workboat"} else 0
    pontoon_count = _count(controls, "pontoon_count", "pontoons", "float_count", default=pontoon_default, minimum=0, maximum=4)
    outrigger_count = _count(controls, "outrigger_count", "outriggers", default=outrigger_default, minimum=0, maximum=4)
    sail_count = _count(controls, "sail_count", "sails", default=sail_default, minimum=0, maximum=8)
    rigging_count = _count(controls, "rigging_count", "rigging", "lines", default=mast_count * 2, minimum=0, maximum=16)
    rudder_count = _count(controls, "rudder_count", "rudders", default=1, minimum=0, maximum=4)
    propeller_count = _count(controls, "propeller_count", "propellers", "props", default=propeller_default, minimum=0, maximum=6)
    cargo_hold_count = _count(
        controls, "cargo_hold_count", "cargo_holds", "hold_count", default=cargo_default, minimum=0, maximum=8
    )
    anchor_count = _count(controls, "anchor_count", "anchors", default=1, minimum=0, maximum=4)
    rail_count = _count(controls, "rail_count", "rails", "railing_count", default=2, minimum=0, maximum=8)
    crew_bay_count = _count(
        controls,
        "crew_bays",
        "crew_bay_count",
        "bridge_count",
        default=1 if cabin_count else 0,
        minimum=0,
        maximum=6,
    )
    cargo_bay_count = _count(
        controls,
        "cargo_bays",
        "cargo_bay_count",
        "payload_bays",
        default=max(0, cargo_hold_count),
        minimum=0,
        maximum=12,
    )
    deck_hardpoint_count = _count(
        controls,
        "deck_hardpoints",
        "hardpoint_count",
        "weapon_mounts",
        default=2 if boat_type in {"patrol", "gunboat", "cutter"} else 0,
        minimum=0,
        maximum=16,
    )
    module_socket_count = _count(
        controls,
        "module_sockets",
        "module_socket_count",
        "mission_slots",
        default=max(0, cargo_hold_count + cabin_count),
        minimum=0,
        maximum=20,
    )
    thruster_count = _count(
        controls,
        "thrusters",
        "thruster_count",
        "bow_thrusters",
        default=2 if engine_count and boat_type in {"workboat", "tug", "patrol", "cutter"} else 0,
        minimum=0,
        maximum=8,
    )
    stabilizer_count = _count(
        controls,
        "stabilizers",
        "stabilizer_count",
        "fins",
        default=2 if boat_type in {"patrol", "cutter", "hydrofoil", "submersible"} else 0,
        minimum=0,
        maximum=8,
    )
    sensor_count = _count(
        controls,
        "sensors",
        "sensor_count",
        "antenna_count",
        default=1 if cabin_count or boat_type in {"patrol", "cutter", "research"} else 0,
        minimum=0,
        maximum=12,
    )
    cleat_count = _count(
        controls,
        "cleats",
        "cleat_count",
        "mooring_points",
        default=4,
        minimum=0,
        maximum=16,
    )
    length = scale * _level(controls, "length_scale", "boat_length", default=1.55)
    width = scale * _level(controls, "width_scale", "boat_width", default=0.56)
    height = scale * _level(controls, "height_scale", "boat_height", default=0.34)

    hull_part = _part_name(asset_graph, "hull", "body", fallback="boat_hull")
    deck_part = _part_name(asset_graph, "deck", fallback=hull_part)
    cabin_part = _part_name(asset_graph, "cabin", fallback=deck_part)
    mast_part = _part_name(asset_graph, "mast", fallback=deck_part)
    engine_part = _part_name(asset_graph, "engine", fallback=hull_part)
    pontoon_part = _part_name(asset_graph, "pontoon", "float", fallback=hull_part)
    outrigger_part = _part_name(asset_graph, "outrigger", fallback=pontoon_part)
    sail_part = _part_name(asset_graph, "sail", "canvas", fallback=mast_part)
    rigging_part = _part_name(asset_graph, "rigging", "cable", "line", fallback=mast_part)
    rudder_part = _part_name(asset_graph, "rudder", "fin", fallback=hull_part)
    propeller_part = _part_name(asset_graph, "propeller", "prop", fallback=engine_part)
    cargo_hold_part = _part_name(asset_graph, "cargo", "hold", "bay", fallback=deck_part)
    anchor_part = _part_name(asset_graph, "anchor", fallback=hull_part)
    rail_part = _part_name(asset_graph, "railing", "rail", fallback=deck_part)
    crew_part = _part_name(asset_graph, "crew", "bridge", "cabin", fallback=cabin_part)
    cargo_bay_part = _part_name(asset_graph, "cargo", "bay", "payload", fallback=cargo_hold_part)
    hardpoint_part = _part_name(asset_graph, "hardpoint", "mount", "socket", fallback=deck_part)
    socket_part = _part_name(asset_graph, "socket", "module", "mission", fallback=hardpoint_part)
    thruster_part = _part_name(asset_graph, "thruster", "engine", "prop", fallback=engine_part)
    stabilizer_part = _part_name(asset_graph, "stabilizer", "fin", "keel", fallback=hull_part)
    sensor_part = _part_name(asset_graph, "sensor", "antenna", "radar", fallback=mast_part)
    cleat_part = _part_name(asset_graph, "cleat", "mooring", "anchor", fallback=anchor_part)
    mooring_line_part = _part_name(asset_graph, "mooring_line", "mooring", "rope", fallback=cleat_part)
    fender_part = _part_name(asset_graph, "fender", "dock", "rubber", fallback=hull_part)

    components = [
        _component(
            "boat_hull_region",
            "hull",
            hull_part,
            (0.0, height * 0.28, 0.0),
            (width, height, length),
            tags=["boat", "hull", "body", boat_type, *loadout_tags],
        ),
        _component(
            "boat_deck_region",
            "deck",
            deck_part,
            (0.0, height * 0.72, -length * 0.02),
            (width * 0.82, height * 0.22, length * 0.78),
            tags=["boat", "deck", boat_type],
            adjacency=[hull_part],
        ),
    ]
    for level in range(1, deck_level_count):
        level_width = max(width * (0.72 - 0.10 * level), width * 0.34)
        level_length = max(length * (0.46 - 0.06 * level), length * 0.22)
        components.append(
            _component(
                f"boat_deck_level_{level:02d}_region",
                "deck",
                deck_part,
                (0.0, height * (0.88 + 0.16 * level), -length * (0.08 + level * 0.05)),
                (level_width, height * 0.14, level_length),
                tags=["boat", "deck", "upper_deck", f"level_{level}", boat_type],
                adjacency=[deck_part, cabin_part],
            )
        )
    cabin_spacing = length * 0.30 / max(1, cabin_count - 1) if cabin_count > 1 else 0.0
    cabin_start = -length * 0.16 - cabin_spacing * (cabin_count - 1) / 2.0
    for index in range(cabin_count):
        components.append(
            _component(
                f"boat_cabin_{index:02d}_region",
                "cabin",
                cabin_part,
                (0.0, height * (1.02 + 0.04 * min(index, 2)), cabin_start + cabin_spacing * index),
                (width * max(0.28, 0.44 - 0.04 * index), height * 0.42, length * 0.22),
                tags=["boat", "cabin", f"cabin_{index}", boat_type],
                adjacency=[deck_part],
            )
        )
    engine_spacing = width * 0.34 / max(1, engine_count - 1) if engine_count > 1 else 0.0
    engine_start = -engine_spacing * (engine_count - 1) / 2.0
    for index in range(engine_count):
        components.append(
            _component(
                f"boat_engine_{index:02d}_region",
                "engine",
                engine_part,
                (engine_start + engine_spacing * index, height * 0.42, -length * 0.56),
                (width * 0.22, height * 0.24, length * 0.18),
                tags=["boat", "engine", "stern", f"engine_{index}", boat_type],
                adjacency=[hull_part],
                radius=height * 0.10,
                height=length * 0.18,
            )
        )
    mast_spacing = length * 0.36 / max(1, mast_count - 1) if mast_count > 1 else 0.0
    start_z = -mast_spacing * (mast_count - 1) / 2.0
    mast_positions: list[float] = []
    for index in range(mast_count):
        z = start_z + mast_spacing * index + float(rng.uniform(-0.01, 0.01)) * length
        mast_positions.append(z)
        components.append(
            _component(
                f"boat_mast_{index:02d}_region",
                "mast",
                mast_part,
                (0.0, height * 1.45, z),
                (width * 0.08, height * 1.36, width * 0.08),
                tags=["boat", "mast", f"mast_{index}", boat_type],
                adjacency=[deck_part],
                radius=width * 0.026,
                height=height * 1.36,
            )
        )
    for index in range(sail_count):
        z = mast_positions[index % len(mast_positions)] if mast_positions else 0.0
        side = "port" if index % 2 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        components.append(
            _component(
                f"{side}_sail_{index:02d}_region",
                "sail",
                sail_part,
                (sign * width * 0.11, height * 1.54, z + length * 0.05),
                (width * 0.38, height * 0.92, max(length * 0.16, width * 0.20)),
                tags=["boat", "sail", "canvas", side, f"sail_{index}", boat_type],
                adjacency=[mast_part, deck_part],
            )
        )
    for index in range(rigging_count):
        z = mast_positions[index % len(mast_positions)] if mast_positions else 0.0
        side = "port" if index % 2 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        fore = "fore" if (index // 2) % 2 == 0 else "aft"
        z_offset = length * (0.24 if fore == "fore" else -0.24)
        components.append(
            _component(
                f"{side}_{fore}_rigging_{index:02d}_region",
                "rigging",
                rigging_part,
                (sign * width * 0.28, height * 1.16, z + z_offset),
                (width * 0.035, height * 1.12, length * 0.36),
                tags=["boat", "rigging", "line", side, fore, f"rigging_{index}", boat_type],
                adjacency=[mast_part, deck_part],
            )
        )
    for index in range(pontoon_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        row = index // 2
        z = (row - max(0, (pontoon_count - 1) // 2) / 2.0) * length * 0.34 if pontoon_count > 2 else 0.0
        components.append(
            _component(
                f"{side}_pontoon_{index:02d}_region",
                "pontoon",
                pontoon_part,
                (sign * width * (0.58 + 0.08 * row), height * 0.18, z),
                (width * 0.20, height * 0.32, length * 0.86),
                tags=["boat", "pontoon", "float", side, f"pontoon_{index}", boat_type],
                adjacency=[hull_part],
                radius=height * 0.16,
                height=length * 0.86,
            )
        )
    for index in range(outrigger_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        z = (-0.22 + 0.44 * ((index // 2) % 2)) * length if outrigger_count > 2 else 0.0
        components.append(
            _component(
                f"{side}_outrigger_{index:02d}_region",
                "outrigger",
                outrigger_part,
                (sign * width * 0.74, height * 0.34, z),
                (width * 0.76, height * 0.16, length * 0.52),
                tags=["boat", "outrigger", "float", side, f"outrigger_{index}", boat_type],
                adjacency=[hull_part, deck_part],
                radius=height * 0.10,
                height=length * 0.48,
            )
        )
    for index in range(cargo_hold_count):
        z = (index - (cargo_hold_count - 1) / 2.0) * length * 0.18
        components.append(
            _component(
                f"cargo_hold_{index:02d}_region",
                "cargo_hold",
                cargo_hold_part,
                (0.0, height * 0.84, z),
                (width * 0.48, height * 0.18, length * 0.17),
                tags=["boat", "cargo", "hold", "hatch", f"hold_{index}", boat_type],
                adjacency=[deck_part, hull_part],
            )
        )
    for index in range(rail_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        row = index // 2
        components.append(
            _component(
                f"{side}_deck_rail_{index:02d}_region",
                "railing",
                rail_part,
                (sign * width * 0.44, height * 1.00, -length * 0.02 + row * length * 0.16),
                (width * 0.045, height * 0.34, length * 0.62),
                tags=["boat", "rail", "railing", side, f"rail_{index}", boat_type],
                adjacency=[deck_part],
            )
        )
    for index in range(rudder_count):
        x = (index - (rudder_count - 1) / 2.0) * width * 0.20
        components.append(
            _component(
                f"rudder_{index:02d}_region",
                "rudder",
                rudder_part,
                (x, height * 0.18, -length * 0.62),
                (width * 0.12, height * 0.38, length * 0.08),
                tags=["boat", "rudder", "stern", f"rudder_{index}", boat_type],
                adjacency=[hull_part],
                radius=width * 0.022,
                height=height * 0.38,
            )
        )
    for index in range(propeller_count):
        x = (index - (propeller_count - 1) / 2.0) * width * 0.16
        components.append(
            _component(
                f"propeller_{index:02d}_region",
                "propeller",
                propeller_part,
                (x, height * 0.26, -length * 0.68),
                (width * 0.18, width * 0.18, length * 0.06),
                tags=["boat", "propeller", "prop", "stern", f"propeller_{index}", boat_type],
                adjacency=[engine_part, hull_part],
                radius=width * 0.08,
                height=length * 0.06,
            )
        )
    for index in range(anchor_count):
        side = "center" if anchor_count == 1 else ("port" if index % 2 == 0 else "starboard")
        sign = 0.0 if side == "center" else (-1.0 if side == "port" else 1.0)
        components.append(
            _component(
                f"{side}_anchor_{index:02d}_region",
                "anchor",
                anchor_part,
                (sign * width * 0.18, height * 0.48, length * 0.56),
                (width * 0.16, height * 0.22, length * 0.08),
                tags=["boat", "anchor", "bow", side, f"anchor_{index}", boat_type],
                adjacency=[hull_part, deck_part],
                radius=width * 0.035,
                height=height * 0.18,
            )
        )
    for index in range(crew_bay_count):
        z = -length * 0.16 + length * 0.22 * index
        components.append(
            _component(
                f"boat_crew_bay_{index:02d}_region",
                "crew_bay",
                crew_part,
                (0.0, height * 1.14, z),
                (width * 0.42, height * 0.34, length * 0.18),
                tags=["boat", "crew", "bridge", "bay", f"crew_bay_{index}", boat_type],
                adjacency=[deck_part, cabin_part],
            )
        )
    for index in range(cargo_bay_count):
        z = -length * 0.24 + length * 0.48 * ((index + 0.5) / max(1, cargo_bay_count))
        components.append(
            _component(
                f"boat_payload_bay_{index:02d}_region",
                "cargo_bay",
                cargo_bay_part,
                (0.0, height * 0.78, z),
                (width * 0.52, height * 0.20, length * 0.16),
                tags=["boat", "cargo", "payload", "bay", f"payload_bay_{index}", boat_type],
                adjacency=[deck_part, cargo_hold_part],
            )
        )
    hardpoint_positions = [
        ("foredeck", 0.0, 0.36),
        ("aftdeck", 0.0, -0.38),
        ("port_midship", -0.34, 0.0),
        ("starboard_midship", 0.34, 0.0),
        ("port_aft", -0.28, -0.30),
        ("starboard_aft", 0.28, -0.30),
    ]
    for index in range(deck_hardpoint_count):
        label, x_factor, z_factor = hardpoint_positions[index % len(hardpoint_positions)]
        components.append(
            _component(
                f"boat_deck_hardpoint_{index:02d}_{label}_region",
                "hardpoint",
                hardpoint_part,
                (x_factor * width, height * 1.02, z_factor * length),
                (width * 0.16, height * 0.07, length * 0.10),
                tags=["boat", "deck_hardpoint", "weapon_mount", label, f"hardpoint_{index}", boat_type],
                adjacency=[deck_part, rail_part],
                interface_role="socket",
            )
        )
    socket_positions = [
        ("mission_fore", 0.0, 0.22),
        ("mission_mid", 0.0, 0.0),
        ("mission_aft", 0.0, -0.24),
        ("port_socket", -0.28, -0.06),
        ("starboard_socket", 0.28, -0.06),
    ]
    for index in range(module_socket_count):
        label, x_factor, z_factor = socket_positions[index % len(socket_positions)]
        components.append(
            _component(
                f"boat_module_socket_{index:02d}_{label}_region",
                "module_socket",
                socket_part,
                (x_factor * width, height * 1.04, z_factor * length),
                (width * 0.18, height * 0.07, length * 0.10),
                tags=["boat", "module_socket", "mission_slot", label, f"module_socket_{index}", boat_type],
                adjacency=[deck_part, cargo_hold_part, cabin_part],
                interface_role="socket",
            )
        )
    for index in range(thruster_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        fore = index < 2
        z = length * (0.36 if fore else -0.44)
        components.append(
            _component(
                f"{side}_{'bow' if fore else 'stern'}_thruster_{index:02d}_region",
                "thruster",
                thruster_part,
                (sign * width * 0.34, height * 0.25, z),
                (width * 0.14, height * 0.14, length * 0.08),
                tags=["boat", "thruster", "propulsion", side, "bow" if fore else "stern", f"thruster_{index}", boat_type],
                adjacency=[hull_part, engine_part],
                axis="x",
                radius=height * 0.055,
                height=width * 0.14,
            )
        )
    for index in range(stabilizer_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        z = -length * 0.18 + length * 0.36 * ((index // 2) / max(1, (stabilizer_count + 1) // 2 - 1))
        components.append(
            _component(
                f"{side}_stabilizer_fin_{index:02d}_region",
                "stabilizer",
                stabilizer_part,
                (sign * width * 0.48, height * 0.16, z),
                (width * 0.18, height * 0.08, length * 0.18),
                tags=["boat", "stabilizer", "fin", side, f"stabilizer_{index}", boat_type],
                adjacency=[hull_part],
            )
        )
    for index in range(sensor_count):
        z = -length * 0.12 + length * 0.14 * (index % 3)
        x = (index - (sensor_count - 1) / 2.0) * width * 0.18 / max(1, sensor_count - 1)
        components.append(
            _component(
                f"boat_sensor_mast_{index:02d}_region",
                "antenna",
                sensor_part,
                (x, height * 1.62, z),
                (width * 0.16, height * 0.46, width * 0.08),
                tags=["boat", "sensor", "antenna", "radar", f"sensor_{index}", boat_type],
                adjacency=[cabin_part, mast_part, deck_part],
                radius=width * 0.012,
                height=height * 0.46,
                interface_role="socket",
            )
        )
    for index in range(cleat_count):
        side = "port" if index % 2 == 0 else "starboard"
        sign = -1.0 if side == "port" else 1.0
        z = -length * 0.42 + length * 0.84 * ((index // 2 + 0.5) / max(1, (cleat_count + 1) // 2))
        components.append(
            _component(
                f"{side}_mooring_cleat_{index:02d}_region",
                "hardpoint",
                cleat_part,
                (sign * width * 0.44, height * 0.98, z),
                (width * 0.12, height * 0.06, length * 0.06),
                tags=["boat", "cleat", "mooring", "tie_down", side, f"cleat_{index}", boat_type],
                adjacency=[deck_part, rail_part],
                interface_role="socket",
            )
        )
    if assembly_member and assembly_mode == "docking_bay":
        line_count = max(2, min(8, assembly_slot_count or cleat_count or 2))
        for index in range(line_count):
            side = "port" if index % 2 == 0 else "starboard"
            sign = -1.0 if side == "port" else 1.0
            z = -length * 0.42 + length * 0.84 * ((index // 2 + 0.5) / max(1, (line_count + 1) // 2))
            components.append(
                _component(
                    f"{side}_mooring_line_{index:02d}_region",
                    "mooring_line",
                    mooring_line_part,
                    (sign * width * 0.58, height * 0.88, z),
                    (width * 0.04, height * 0.06, length * 0.28),
                    tags=["boat", "assembly_member", "docking_bay", "mooring_line", side, f"line_{index}", boat_type],
                    adjacency=[hull_part, deck_part, cleat_part],
                    radius=max(width * 0.010, 0.025),
                    height=length * 0.28,
                    interface_role="socket",
                )
            )
        fender_count = max(2, min(8, line_count))
        for index in range(fender_count):
            side = "port" if index % 2 == 0 else "starboard"
            sign = -1.0 if side == "port" else 1.0
            z = -length * 0.38 + length * 0.76 * ((index // 2 + 0.5) / max(1, (fender_count + 1) // 2))
            components.append(
                _component(
                    f"{side}_dock_fender_{index:02d}_region",
                    "fender",
                    fender_part,
                    (sign * width * 0.52, height * 0.50, z),
                    (width * 0.09, height * 0.26, length * 0.09),
                    tags=["boat", "assembly_member", "docking_bay", "fender", side, f"fender_{index}", boat_type],
                    adjacency=[hull_part, cleat_part],
                    radius=max(width * 0.035, 0.04),
                    height=height * 0.24,
                )
            )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural boat blueprint generated hull variants, decks, cabins, engines, masts, sails, rigging, pontoons, outriggers, cargo holds, rails, rudders, propellers, anchors, crew bays, payload bays, deck hardpoints, mission sockets, thrusters, stabilizer fins, sensor masts, mooring cleats, and dock-conditioned mooring/fender gear"
        ],
    )


def _procedural_road_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=2, maximum=32)
    scale = asset_graph.scale_cm
    landform = str(controls.get("landform") or controls.get("environment_feature") or "").lower()
    intersection_type = str(
        controls.get("intersection_type")
        or controls.get("junction_type")
        or controls.get("network_type")
        or ""
    ).lower()
    edge_mode = landform in {"road_edge", "path", "trail"}
    intersection_mode = intersection_type in {"t", "tee", "t_junction", "cross", "four_way", "roundabout", "plaza"}
    lane_count = _count(controls, "lanes", "lane_count", "road_lanes", default=1 if edge_mode else 2, minimum=1, maximum=8)
    segment_count = _count(
        controls,
        "segments",
        "segment_count",
        "road_segments",
        default=3,
        minimum=1,
        maximum=12,
    )
    width = scale * _level(controls, "width_scale", "road_width", default=0.46 if edge_mode else 0.82)
    length = scale * _level(controls, "length_scale", "road_length", default=2.4)
    thickness = scale * _level(controls, "thickness_scale", "road_thickness", default=0.035)
    road_edge_count = _count(controls, "road_edge_count", "edge_count", default=1 if edge_mode else 0, minimum=0, maximum=8)
    if intersection_type in {"t", "tee", "t_junction"}:
        default_branches = 3
    elif intersection_type in {"cross", "four_way", "roundabout", "plaza"}:
        default_branches = 4
    else:
        default_branches = 0
    branch_count = _count(
        controls,
        "branches",
        "branch_count",
        "junction_branch_count",
        "road_branch_count",
        default=default_branches,
        minimum=0,
        maximum=8,
    )
    junction_count = _count(
        controls,
        "junctions",
        "junction_count",
        "intersection_count",
        default=1 if branch_count or intersection_mode else 0,
        minimum=0,
        maximum=6,
    )
    turnout_count = _count(
        controls,
        "turnouts",
        "turnout_count",
        "pullout_count",
        default=0 if edge_mode else max(0, junction_count - 1),
        minimum=0,
        maximum=8,
    )
    crosswalk_count = _count(
        controls,
        "crosswalks",
        "crosswalk_count",
        default=junction_count if junction_count and not edge_mode else 0,
        minimum=0,
        maximum=8,
    )
    median_count = _count(
        controls,
        "medians",
        "median_count",
        default=1 if lane_count >= 4 and not edge_mode else 0,
        minimum=0,
        maximum=8,
    )
    curb_ramp_count = _count(
        controls,
        "curb_ramps",
        "curb_ramp_count",
        default=min(24, junction_count * 4) if junction_count and not edge_mode else 0,
        minimum=0,
        maximum=32,
    )
    stop_line_count = _count(
        controls,
        "stop_lines",
        "stop_line_count",
        default=min(12, junction_count * 2) if junction_count and not edge_mode else 0,
        minimum=0,
        maximum=16,
    )
    lane_arrow_count = _count(
        controls,
        "lane_arrows",
        "lane_arrow_count",
        default=min(12, lane_count * max(1, junction_count)) if junction_count and not edge_mode else 0,
        minimum=0,
        maximum=24,
    )
    bike_lane_count = _count(
        controls,
        "bike_lanes",
        "bike_lane_count",
        default=0,
        minimum=0,
        maximum=4,
    )
    parking_bay_count = _count(
        controls,
        "parking_bays",
        "parking_bay_count",
        default=0,
        minimum=0,
        maximum=16,
    )
    streetlight_count = _count(
        controls,
        "streetlights",
        "streetlight_count",
        "lamp_post_count",
        default=2 if not edge_mode else 0,
        minimum=0,
        maximum=24,
    )
    bollard_count = _count(
        controls,
        "bollards",
        "bollard_count",
        default=min(16, curb_ramp_count) if junction_count else 0,
        minimum=0,
        maximum=32,
    )
    length / segment_count
    route_profile = path_profile_from_controls(
        controls,
        family="procedural_road",
        segment_count=segment_count,
        length=length,
        width=width,
        height=scale * 0.34,
        default_profile="straight",
    )

    road_part = _part_name(asset_graph, "road", "street", "path", fallback="road_surface")
    lane_part = _part_name(asset_graph, "lane", fallback=road_part)
    sidewalk_part = _part_name(asset_graph, "sidewalk", fallback=road_part)
    junction_part = _part_name(asset_graph, "junction", "intersection", fallback=road_part)
    crosswalk_part = _part_name(asset_graph, "crosswalk", "lane", fallback=lane_part)
    turnout_part = _part_name(asset_graph, "turnout", "shoulder", fallback=sidewalk_part)
    median_part = _part_name(asset_graph, "median", "divider", fallback=junction_part)
    ramp_part = _part_name(asset_graph, "curb", "ramp", "sidewalk", fallback=sidewalk_part)
    streetlight_part = _part_name(asset_graph, "streetlight", "lamp", "pole", fallback=sidewalk_part)
    bollard_part = _part_name(asset_graph, "bollard", "post", fallback=sidewalk_part)
    coupler_part = _part_name(asset_graph, "road_coupler", "route_socket", "connection_socket", fallback=junction_part)

    components = []
    for index, segment in enumerate(route_profile["segments"]):
        center_x, center_y, center_z = segment["center"]
        segment_width, segment_depth = segment["extents"]
        components.append(
            _component(
                f"road_segment_{index:02d}_region",
                "road",
                road_part,
                (center_x, thickness * 0.50 + center_y, center_z),
                (segment_width, thickness, segment_depth),
                tags=["road", "street", f"segment_{index}", f"lanes_{lane_count}", *segment["tags"]],
            )
        )
    for junction_index in range(junction_count):
        z = (junction_index - (junction_count - 1) / 2.0) * length * 0.38
        junction_kind = intersection_type or ("t_junction" if branch_count == 3 else "four_way")
        components.append(
            _component(
                f"road_junction_{junction_index:02d}_region",
                "road_junction",
                junction_part,
                (0.0, thickness * 1.04, z),
                (width * 1.38, thickness * 1.25, width * 1.38),
                tags=["road", "junction", "intersection", junction_kind, f"junction_{junction_index}"],
                adjacency=[road_part],
            )
        )
        if junction_kind in {"roundabout", "plaza"}:
            components.append(
                _component(
                    f"roundabout_island_{junction_index:02d}_region",
                    "roundabout",
                    junction_part,
                    (0.0, thickness * 1.90, z),
                    (width * 0.76, thickness * 1.50, width * 0.76),
                    tags=["road", "junction", "roundabout", "island", f"junction_{junction_index}"],
                    adjacency=[road_part],
                    radius=width * 0.24,
                    height=thickness * 1.50,
                )
            )
    branch_directions = [
        ("east", 1.0, 0.0),
        ("west", -1.0, 0.0),
        ("north", 0.0, 1.0),
        ("south", 0.0, -1.0),
        ("northeast", 0.72, 0.72),
        ("southwest", -0.72, -0.72),
        ("northwest", -0.72, 0.72),
        ("southeast", 0.72, -0.72),
    ]
    branch_length = scale * _level(controls, "branch_length", "road_branch_length", default=0.78)
    profile_branches = list(route_profile.get("branches", []))
    for branch_index in range(branch_count):
        if branch_index < len(profile_branches):
            branch = profile_branches[branch_index]
            direction = str(branch["direction"])
            branch_center_x, branch_center_y, branch_center_z = branch["center"]
            branch_extent_x, branch_extent_z = branch["extents"]
            center = (branch_center_x, thickness * 0.92 + branch_center_y, branch_center_z)
            extents = (branch_extent_x, thickness * 0.92, branch_extent_z)
            branch_tags = list(branch["tags"])
        else:
            direction, dx, dz = branch_directions[branch_index % len(branch_directions)]
            horizontal = abs(dx) >= abs(dz)
            center = (
                dx * (width * 0.56 + branch_length * 0.50),
                thickness * 0.92,
                dz * (width * 0.56 + branch_length * 0.50),
            )
            extents = (
                branch_length if horizontal else width * 0.72,
                thickness * 0.92,
                width * 0.72 if horizontal else branch_length,
            )
            branch_tags = []
        components.append(
            _component(
                f"road_branch_{branch_index:02d}_{direction}_region",
                "road_branch",
                road_part,
                center,
                extents,
                tags=["road", "branch", direction, f"branch_{branch_index}", f"lanes_{lane_count}", *branch_tags],
                adjacency=[road_part, junction_part],
            )
        )
    for crosswalk_index in range(crosswalk_count):
        z = (crosswalk_index - (crosswalk_count - 1) / 2.0) * max(width * 0.58, length * 0.16)
        components.append(
            _component(
                f"crosswalk_{crosswalk_index:02d}_region",
                "crosswalk",
                crosswalk_part,
                (0.0, thickness * 1.72, z),
                (width * 0.92, max(thickness * 0.18, 0.035), width * 0.24),
                tags=["road", "crosswalk", "marking", f"crosswalk_{crosswalk_index}"],
                adjacency=[road_part, junction_part],
            )
        )

    lane_spacing = width * 0.68 / lane_count
    for lane_index in range(1, lane_count):
        x = -width * 0.34 + lane_spacing * lane_index
        components.append(
            _component(
                f"lane_marker_{lane_index:02d}_region",
                "panel",
                lane_part,
                (x, thickness * 1.16, 0.0),
                (max(width * 0.012, 0.06), max(thickness * 0.16, 0.04), length * 0.92),
                tags=["road", "lane", "marker", f"lane_split_{lane_index}"],
                adjacency=[road_part],
            )
        )

    sidewalk_width = max(width * 0.16, scale * 0.08)
    for side, sign in (("left", -1.0), ("right", 1.0)):
        components.append(
            _component(
                f"{side}_sidewalk_region",
                "panel",
                sidewalk_part,
                (sign * (width * 0.50 + sidewalk_width * 0.52), thickness * 0.86, 0.0),
                (sidewalk_width, thickness * 0.70, length),
                tags=["road", "sidewalk", side],
                adjacency=[road_part],
            )
        )
    _append_structural_elements(
        components,
        structural_elements_for_path(
            controls,
            family="procedural_road",
            path_profile=route_profile,
            width=width,
            height=scale * 0.22,
            base_y=thickness,
        ),
        {
            "edge": sidewalk_part,
            "wall": sidewalk_part,
            "roof": sidewalk_part,
            "support": sidewalk_part,
            "truss": sidewalk_part,
            "default": road_part,
        },
        adjacency=[road_part],
    )
    for turnout_index in range(turnout_count):
        side = "left" if turnout_index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = (turnout_index - (turnout_count - 1) / 2.0) * length * 0.28
        components.append(
            _component(
                f"{side}_turnout_{turnout_index:02d}_region",
                "turnout",
                turnout_part,
                (sign * (width * 0.62 + sidewalk_width * 0.52), thickness * 1.05, z),
                (sidewalk_width * 1.65, thickness * 0.90, length * 0.20),
                tags=["road", "turnout", "pullout", side, f"turnout_{turnout_index}"],
                adjacency=[road_part],
            )
        )
    for edge_index in range(road_edge_count):
        side = "left" if edge_index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = (edge_index // 2 - max(0, road_edge_count - 1) / 4.0) * length * 0.18
        components.append(
            _component(
                f"{side}_road_edge_guard_{edge_index:02d}_region",
                "panel",
                sidewalk_part,
                (sign * width * 0.62, thickness * 2.2, z),
                (max(width * 0.08, 0.08), thickness * 2.2, length * 0.24),
                tags=["road", "edge", "curb", side, f"edge_{edge_index}"],
                adjacency=[road_part],
            )
        )
    for index in range(median_count):
        z = (index - (median_count - 1) / 2.0) * length * 0.44 / max(1, median_count - 1)
        components.append(
            _component(
                f"raised_median_{index:02d}_region",
                "median",
                median_part,
                (0.0, thickness * 1.22, z),
                (max(width * 0.10, 0.08), thickness * 1.28, length * 0.32),
                tags=["road", "median", "divider", f"median_{index}", f"lanes_{lane_count}"],
                adjacency=[road_part, junction_part],
            )
        )
    for index in range(stop_line_count):
        z = -length * 0.40 + length * 0.80 * ((index + 0.5) / max(1, stop_line_count))
        components.append(
            _component(
                f"stop_line_{index:02d}_region",
                "stop_line",
                lane_part,
                (0.0, thickness * 1.82, z),
                (width * 0.90, max(thickness * 0.18, 0.026), width * 0.16),
                tags=["road", "stop_line", "marking", f"stop_line_{index}"],
                adjacency=[road_part, junction_part],
            )
        )
    arrow_lane_slots = max(1, lane_count)
    for index in range(lane_arrow_count):
        lane_slot = index % arrow_lane_slots
        x = -width * 0.32 + width * 0.64 * (lane_slot + 0.5) / arrow_lane_slots
        z = -length * 0.38 + length * 0.76 * ((index // arrow_lane_slots + 0.5) / max(1, (lane_arrow_count + arrow_lane_slots - 1) // arrow_lane_slots))
        components.append(
            _component(
                f"lane_arrow_{index:02d}_region",
                "lane_arrow",
                lane_part,
                (x, thickness * 1.86, z),
                (max(width * 0.16, 0.10), max(thickness * 0.16, 0.024), max(width * 0.34, 0.18)),
                tags=["road", "lane_arrow", "direction_marking", f"lane_arrow_{index}", f"lane_{lane_slot}"],
                adjacency=[road_part, lane_part],
            )
        )
    for index in range(curb_ramp_count):
        corner = index % 4
        side_sign = -1.0 if corner in {0, 2} else 1.0
        end_sign = -1.0 if corner in {0, 1} else 1.0
        z_band = (index // 4 - max(0, curb_ramp_count - 1) / 8.0) * length * 0.18
        components.append(
            _component(
                f"curb_ramp_{index:02d}_region",
                "curb_ramp",
                ramp_part,
                (
                    side_sign * (width * 0.54 + sidewalk_width * 0.24),
                    thickness * 1.12,
                    end_sign * min(length * 0.46, width * 0.84) + z_band,
                ),
                (sidewalk_width * 0.92, thickness * 0.72, width * 0.28),
                tags=["road", "sidewalk", "curb_ramp", f"ramp_{index}", "accessible_crossing"],
                adjacency=[road_part, sidewalk_part, junction_part],
            )
        )
    for index in range(bike_lane_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_bike_lane_{index:02d}_region",
                "panel",
                lane_part,
                (sign * width * 0.39, thickness * 1.70, 0.0),
                (max(width * 0.075, 0.08), max(thickness * 0.14, 0.024), length * 0.92),
                tags=["road", "bike_lane", "lane_marking", side, f"bike_lane_{index}"],
                adjacency=[road_part, lane_part],
            )
        )
    for index in range(parking_bay_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -length * 0.42 + length * 0.84 * ((index // 2 + 0.5) / max(1, (parking_bay_count + 1) // 2))
        components.append(
            _component(
                f"{side}_parking_bay_{index:02d}_region",
                "turnout",
                turnout_part,
                (sign * (width * 0.60 + sidewalk_width * 0.70), thickness * 1.02, z),
                (sidewalk_width * 1.45, thickness * 0.82, length * 0.14),
                tags=["road", "parking_bay", "curbside", side, f"parking_{index}"],
                adjacency=[road_part, sidewalk_part],
            )
        )
    for index in range(streetlight_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        row = index // 2
        rows = max(1, (streetlight_count + 1) // 2)
        z = -length * 0.44 + length * 0.88 * ((row + 0.5) / rows)
        components.append(
            _component(
                f"{side}_streetlight_{index:02d}_region",
                "streetlight",
                streetlight_part,
                (sign * (width * 0.50 + sidewalk_width * 0.82), scale * 0.18, z),
                (sidewalk_width * 0.28, scale * 0.46, sidewalk_width * 0.28),
                tags=["road", "streetlight", "sidewalk", side, f"streetlight_{index}"],
                adjacency=[sidewalk_part, road_part],
            )
        )
    for index in range(bollard_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -length * 0.42 + length * 0.84 * ((index // 2 + 0.5) / max(1, (bollard_count + 1) // 2))
        components.append(
            _component(
                f"{side}_bollard_{index:02d}_region",
                "bollard",
                bollard_part,
                (sign * (width * 0.50 + sidewalk_width * 0.28), thickness * 2.25, z),
                (sidewalk_width * 0.24, thickness * 2.8, sidewalk_width * 0.24),
                tags=["road", "bollard", "sidewalk_edge", side, f"bollard_{index}"],
                adjacency=[sidewalk_part, road_part],
                axis="y",
                radius=sidewalk_width * 0.09,
                height=thickness * 2.8,
            )
        )
    if assembly_member and assembly_mode in {"route_network", "chain", "loop", "ring"}:
        endpoints = [("start", -length * 0.50), ("end", length * 0.50)]
        for _index, (label, z) in enumerate(endpoints):
            components.append(
                _component(
                    f"route_network_{label}_coupler_region",
                    "road_coupler",
                    coupler_part,
                    (0.0, thickness * 2.05, z),
                    (width * 0.88, max(thickness * 0.34, 0.035), max(width * 0.18, 0.12)),
                    tags=["road", "assembly_member", assembly_mode, "route_socket", "road_coupler", label, f"slot_count_{assembly_slot_count}"],
                    adjacency=[road_part, junction_part],
                    interface_role="socket",
                )
            )
        for index in range(max(1, min(6, lane_count))):
            x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, lane_count))
            components.append(
                _component(
                    f"route_alignment_mark_{index:02d}_region",
                    "route_alignment_mark",
                    lane_part,
                    (x, thickness * 2.10, 0.0),
                    (max(width * 0.055, 0.05), max(thickness * 0.18, 0.025), length * 0.16),
                    tags=["road", "assembly_member", assembly_mode, "alignment_mark", f"lane_{index}"],
                    adjacency=[road_part, lane_part],
                )
            )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural road blueprint generated segmented roadbeds, junctions, branches, crosswalks, turnouts, sidewalks, environment road-edge guards, medians, stop lines, lane arrows, curb ramps, bike lanes, parking bays, streetlights, bollards, and route-network couplers"
        ],
    )


def _procedural_bridge_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    span_count = _count(controls, "spans", "span_count", "bridge_spans", default=2, minimum=1, maximum=8)
    pier_count = _count(controls, "piers", "pier_count", default=max(2, span_count + 1), minimum=2, maximum=10)
    width = scale * _level(controls, "width_scale", "bridge_width", default=0.92)
    length = scale * _level(controls, "length_scale", "bridge_length", default=2.2)
    deck_height = scale * _level(controls, "deck_height", "height_scale", default=0.08)
    clearance = scale * _level(controls, "clearance", "bridge_clearance", default=0.36)
    route_profile = path_profile_from_controls(
        controls,
        family="procedural_bridge",
        segment_count=span_count,
        length=length,
        width=width,
        height=clearance,
        default_profile="bridge",
    )

    deck_part = _part_name(asset_graph, "bridge", "span", fallback="bridge_deck")
    rail_part = _part_name(asset_graph, "railing", fallback=deck_part)
    pier_part = _part_name(asset_graph, "pier", "column", fallback=deck_part)

    components = []
    for index, segment in enumerate(route_profile["segments"]):
        center_x, center_y, center_z = segment["center"]
        segment_width, segment_depth = segment["extents"]
        components.append(
            _component(
                f"bridge_span_{index:02d}_deck_region",
                "bridge",
                deck_part,
                (center_x, clearance + center_y, center_z),
                (segment_width, deck_height, segment_depth),
                tags=["bridge", "deck", "span", f"span_{index}", f"spans_{span_count}", *segment["tags"]],
            )
        )
        for side, sign in (("left", -1.0), ("right", 1.0)):
            components.append(
                _component(
                    f"{side}_bridge_railing_{index:02d}_region",
                    "railing",
                    rail_part,
                    (center_x + sign * segment_width * 0.48, clearance + center_y + deck_height * 1.8, center_z),
                    (width * 0.04, deck_height * 3.4, segment_depth * 0.94),
                    tags=["bridge", "railing", side, f"span_{index}", *segment["tags"]],
                    adjacency=[deck_part],
                )
            )
    _append_structural_elements(
        components,
        structural_elements_for_path(
            controls,
            family="procedural_bridge",
            path_profile=route_profile,
            width=width,
            height=clearance,
            base_y=clearance,
        ),
        {
            "edge": rail_part,
            "wall": rail_part,
            "roof": deck_part,
            "support": pier_part,
            "truss": rail_part,
            "default": deck_part,
        },
        adjacency=[deck_part],
    )

    pier_spacing = length * 0.86 / max(1, pier_count - 1)
    start_z = -pier_spacing * (pier_count - 1) / 2.0
    for index in range(pier_count):
        z = start_z + pier_spacing * index
        for side, sign in (("left", -1.0), ("right", 1.0)):
            components.append(
                _component(
                    f"{side}_bridge_pier_{index:02d}_region",
                    "column",
                    pier_part,
                    (sign * width * 0.30, clearance * 0.48, z),
                    (width * 0.10, clearance * 0.92, width * 0.10),
                    tags=["bridge", "pier", side, f"pier_{index}"],
                    adjacency=[deck_part],
                    radius=width * 0.045,
                    height=clearance * 0.92,
                )
            )

    for side, z in (("start", -length * 0.54), ("end", length * 0.54)):
        components.append(
            _component(
                f"{side}_abutment_region",
                "panel",
                deck_part,
                (0.0, clearance * 0.30, z),
                (width * 1.08, clearance * 0.58, length * 0.05),
                tags=["bridge", "abutment", side],
                adjacency=[deck_part],
            )
        )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["procedural bridge blueprint generated deck spans, railings, piers, and abutments"],
    )


def _procedural_terrain_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    landform = str(controls.get("landform") or controls.get("environment_feature") or "").lower()
    focused_landform = landform in {"terrain_patch", "ridge", "cliff", "clearing", "platform", "water"}
    patch_count = _count(
        controls,
        "terrain_patch_count",
        "terrain_tile_count",
        "patches",
        "patch_count",
        default=1,
        minimum=1,
        maximum=16,
    )
    if focused_landform:
        terrace_count = _count(
            controls,
            "terraces",
            "terrace_count",
            default=3 if landform == "terrain_patch" else 0,
            minimum=0,
            maximum=9,
        )
    else:
        terrace_count = _count(
            controls,
            "terraces",
            "terrace_count",
            "platform_count",
            default=3,
            minimum=0,
            maximum=9,
        )
    ridge_count = _count(
        controls,
        "ridges",
        "ridge_count",
        default=2 if not focused_landform else (1 if landform == "ridge" else 0),
        minimum=0,
        maximum=12,
    )
    cliff_count = _count(
        controls,
        "cliffs",
        "cliff_count",
        default=0 if not focused_landform else (1 if landform == "cliff" else 0),
        minimum=0,
        maximum=12,
    )
    clearing_count = _count(
        controls,
        "clearings",
        "clearing_count",
        default=1 if landform == "clearing" else 0,
        minimum=0,
        maximum=16,
    )
    platform_feature_count = _count(
        controls,
        "terrain_platforms",
        "platform_count",
        default=1 if landform == "platform" else 0,
        minimum=0,
        maximum=16,
    )
    water_count = _count(
        controls,
        "water_count",
        "pond_count",
        "ponds",
        default=1 if landform == "water" else 0,
        minimum=0,
        maximum=12,
    )
    path_count = _count(
        controls,
        "path_count",
        "trail_count",
        "terrain_path_count",
        default=0 if focused_landform else 1,
        minimum=0,
        maximum=8,
    )
    width = scale * _level(controls, "width_scale", "terrain_width", default=1.8)
    depth = scale * _level(controls, "depth_scale", "terrain_depth", default=1.8)
    height = scale * _level(controls, "height_scale", "terrain_height", default=0.36)

    terrain_part = _part_name(asset_graph, "terrain", "ground", fallback="terrain_patch")
    cliff_part = _part_name(asset_graph, "cliff", "ridge", fallback=terrain_part)
    path_part = _part_name(asset_graph, "path", "road", fallback=terrain_part)
    clearing_part = _part_name(asset_graph, "clearing", "terrain", fallback=terrain_part)
    water_part = _part_name(asset_graph, "water", "terrain", fallback=terrain_part)
    platform_part = _part_name(asset_graph, "platform", "terrain", fallback=terrain_part)

    components = [
        _component(
            "terrain_base_region",
            "terrain",
            terrain_part,
            (0.0, height * 0.22, 0.0),
            (width, height * 0.44, depth),
            tags=["terrain", "ground", "base"],
        )
    ]
    if patch_count > 1:
        columns = max(1, round(patch_count**0.5))
        rows = max(1, (patch_count + columns - 1) // columns)
        tile_w = width / columns
        tile_d = depth / rows
        for index in range(patch_count):
            col = index % columns
            row = index // columns
            x = -width * 0.5 + tile_w * (col + 0.5)
            z = -depth * 0.5 + tile_d * (row + 0.5)
            components.append(
                _component(
                    f"terrain_patch_tile_{index:02d}_region",
                    "terrain",
                    terrain_part,
                    (x, height * (0.34 + 0.02 * ((index + candidate_index) % 3)), z),
                    (tile_w * 0.98, height * 0.18, tile_d * 0.98),
                    tags=["terrain", "patch", "tile", f"patch_{index}"],
                    adjacency=[terrain_part],
                )
            )
    for index in range(terrace_count):
        t = index / max(1, terrace_count - 1)
        z = -depth * 0.32 + depth * 0.64 * t
        x = float(rng.uniform(-0.08, 0.08)) * width
        components.append(
            _component(
                f"terrain_terrace_{index:02d}_region",
                "terrain",
                terrain_part,
                (x, height * (0.44 + 0.18 * index), z),
                (width * (0.78 - 0.08 * t), height * 0.22, depth * 0.24),
                tags=["terrain", "platform", "terrace", f"terrace_{index}"],
                adjacency=[terrain_part],
            )
        )
    for index in range(ridge_count):
        sign = -1.0 if index % 2 == 0 else 1.0
        z = -depth * 0.22 + depth * 0.44 * (index / max(1, ridge_count - 1))
        components.append(
            _component(
                f"terrain_ridge_{index:02d}_region",
                "ridge",
                cliff_part,
                (sign * width * 0.32, height * 0.54, z),
                (width * 0.18, height * 0.54, depth * 0.34),
                tags=["terrain", "cliff", "ridge", f"ridge_{index}"],
                adjacency=[terrain_part],
            )
        )
    for index in range(cliff_count):
        sign = -1.0 if index % 2 == 0 else 1.0
        z = -depth * 0.30 + depth * 0.60 * (index / max(1, cliff_count - 1))
        components.append(
            _component(
                f"terrain_cliff_{index:02d}_region",
                "cliff",
                cliff_part,
                (sign * width * 0.42, height * 0.48, z),
                (width * 0.16, height * 0.82, depth * 0.42),
                tags=["terrain", "cliff", "face", f"cliff_{index}"],
                adjacency=[terrain_part],
            )
        )
    for index in range(clearing_count):
        angle = 2.0 * np.pi * index / max(1, clearing_count)
        radius = min(width, depth) * (0.12 if clearing_count == 1 else 0.22)
        components.append(
            _component(
                f"terrain_clearing_{index:02d}_region",
                "clearing",
                clearing_part,
                (float(np.cos(angle)) * radius, height * 0.64, float(np.sin(angle)) * radius),
                (width * 0.34, height * 0.08, depth * 0.28),
                tags=["terrain", "clearing", "open_ground", f"clearing_{index}"],
                adjacency=[terrain_part],
            )
        )
    for index in range(platform_feature_count):
        x = (index - (platform_feature_count - 1) / 2.0) * width * 0.28
        components.append(
            _component(
                f"terrain_platform_{index:02d}_region",
                "terrain_platform",
                platform_part,
                (x, height * 0.80, depth * 0.18),
                (width * 0.36, height * 0.32, depth * 0.30),
                tags=["terrain", "platform", "raised", f"platform_{index}"],
                adjacency=[terrain_part],
            )
        )
    for index in range(water_count):
        x = (index - (water_count - 1) / 2.0) * width * 0.24
        components.append(
            _component(
                f"terrain_water_{index:02d}_region",
                "water",
                water_part,
                (x, height * 0.57, -depth * 0.16),
                (width * 0.34, height * 0.08, depth * 0.28),
                tags=["terrain", "water", "basin", f"water_{index}"],
                adjacency=[terrain_part],
            )
        )
    if path_count:
        path_segment_count = max(
            path_count,
            _count(
                controls,
                "connection_segment_count",
                "route_segment_count",
                default=path_count,
                minimum=path_count,
                maximum=16,
            ),
        )
        route_profile = path_profile_from_controls(
            controls,
            family="procedural_terrain",
            segment_count=path_segment_count,
            length=depth,
            width=width * 0.20,
            height=height,
            default_profile="curve" if path_segment_count > 2 else "straight",
        )
        for index, segment in enumerate(route_profile["segments"]):
            center_x, center_y, center_z = segment["center"]
            segment_width, segment_depth = segment["extents"]
            components.append(
                _component(
                    f"terrain_path_{index:02d}_region",
                    "path",
                    path_part,
                    (center_x, height * 0.54 + center_y, center_z),
                    (segment_width, height * 0.06, segment_depth),
                    tags=["terrain", "path", "traversal", f"path_{index}", *segment["tags"]],
                    adjacency=[terrain_part],
                )
            )
        _append_structural_elements(
            components,
            structural_elements_for_path(
                controls,
                family="procedural_terrain",
                path_profile=route_profile,
                width=width * 0.20,
                height=height * 0.42,
                base_y=height * 0.52,
            ),
            {
                "edge": path_part,
                "wall": cliff_part,
                "roof": terrain_part,
                "support": platform_part,
                "truss": platform_part,
                "default": terrain_part,
            },
            adjacency=[terrain_part],
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural terrain blueprint generated biome-aware patches, terraces, ridges, cliffs, clearings, platforms, water, and traversal paths"
        ],
    )


def _procedural_city_block_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    lot_count = _count(controls, "lots", "lot_count", "building_count", default=6, minimum=2, maximum=16)
    road_lanes = _count(controls, "lanes", "road_lanes", default=2, minimum=1, maximum=6)
    width = scale * _level(controls, "width_scale", "block_width", default=2.4)
    depth = scale * _level(controls, "depth_scale", "block_depth", default=2.2)
    road_width = scale * _level(controls, "road_width", "street_width", default=0.34 + 0.08 * road_lanes)
    pad_height = scale * 0.035
    alley_count = _count(controls, "alleys", "alley_count", default=1 if lot_count >= 6 else 0, minimum=0, maximum=8)
    plaza_count = _count(controls, "plazas", "plaza_count", "courtyard_count", default=1 if lot_count >= 8 else 0, minimum=0, maximum=4)
    crosswalk_count = _count(controls, "crosswalks", "crosswalk_count", default=4, minimum=0, maximum=12)
    streetlight_count = _count(controls, "streetlights", "streetlight_count", default=4, minimum=0, maximum=24)

    block_part = _part_name(asset_graph, "block", "city", "plaza", fallback="city_block")
    road_part = _part_name(asset_graph, "road", "street", fallback=block_part)
    lot_part = _part_name(asset_graph, "lot", fallback=block_part)
    building_part = _part_name(asset_graph, "building", "tower", fallback=lot_part)
    roof_part = _part_name(asset_graph, "roof", fallback=building_part)
    sidewalk_part = _part_name(asset_graph, "sidewalk", "plaza", "urban", fallback=road_part)
    crosswalk_part = _part_name(asset_graph, "crosswalk", "lane", fallback=road_part)
    window_part = _part_name(asset_graph, "window", fallback=building_part)
    door_part = _part_name(asset_graph, "door", "entry", fallback=building_part)
    streetlight_part = _part_name(asset_graph, "streetlight", "lamp", "pole", fallback=sidewalk_part)

    components = [
        _component(
            "city_block_ground_region",
            "lot",
            block_part,
            (0.0, pad_height * 0.50, 0.0),
            (width, pad_height, depth),
            tags=["city", "block", "ground"],
        ),
        _component(
            "city_block_main_street_region",
            "road",
            road_part,
            (0.0, pad_height * 1.50, 0.0),
            (road_width, pad_height, depth * 1.04),
            tags=["city", "road", "main_street", f"lanes_{road_lanes}"],
            adjacency=[block_part],
        ),
        _component(
            "city_block_cross_street_region",
            "road",
            road_part,
            (0.0, pad_height * 1.55, 0.0),
            (width * 1.04, pad_height, road_width),
            tags=["city", "road", "cross_street", f"lanes_{road_lanes}"],
            adjacency=[block_part],
        ),
    ]

    columns = max(1, round(lot_count**0.5))
    rows = max(1, (lot_count + columns - 1) // columns)
    lot_w = (width - road_width * 1.4) / max(1, columns)
    lot_d = (depth - road_width * 1.4) / max(1, rows)
    index = 0
    for row in range(rows):
        for column in range(columns):
            if index >= lot_count:
                break
            x_side = -1.0 if column < columns / 2.0 else 1.0
            z_side = -1.0 if row < rows / 2.0 else 1.0
            local_x = (column - (columns - 1) / 2.0) * lot_w + x_side * road_width * 0.42
            local_z = (row - (rows - 1) / 2.0) * lot_d + z_side * road_width * 0.42
            tower_height = scale * (0.22 + 0.04 * ((index + candidate_index) % 5))
            components.extend(
                [
                    _component(
                        f"city_lot_{index:02d}_region",
                        "lot",
                        lot_part,
                        (local_x, pad_height * 2.20, local_z),
                        (lot_w * 0.78, pad_height * 0.74, lot_d * 0.78),
                        tags=["city", "lot", f"lot_{index}"],
                        adjacency=[block_part, road_part],
                    ),
                    _component(
                        f"city_building_{index:02d}_region",
                        "shell",
                        building_part,
                        (local_x, pad_height * 2.70 + tower_height * 0.50, local_z),
                        (lot_w * 0.45, tower_height, lot_d * 0.44),
                        tags=["city", "building", f"lot_{index}"],
                        adjacency=[lot_part],
                    ),
                    _component(
                        f"city_roof_{index:02d}_region",
                        "roof",
                        roof_part,
                        (local_x, pad_height * 2.90 + tower_height, local_z),
                        (lot_w * 0.50, tower_height * 0.14, lot_d * 0.49),
                        tags=["city", "building", "roof", f"lot_{index}"],
                        adjacency=[building_part],
                    ),
                ]
            )
            components.append(
                _component(
                    f"city_entry_{index:02d}_region",
                    "door",
                    door_part,
                    (local_x, pad_height * 2.72 + tower_height * 0.18, local_z + lot_d * 0.23),
                    (lot_w * 0.12, tower_height * 0.28, lot_d * 0.035),
                    tags=["city", "building", "entry", "door", f"lot_{index}"],
                    adjacency=[building_part, lot_part],
                )
            )
            for window_index in range(2):
                x = local_x + (window_index - 0.5) * lot_w * 0.18
                components.append(
                    _component(
                        f"city_window_{index:02d}_{window_index:02d}_region",
                        "window",
                        window_part,
                        (x, pad_height * 2.74 + tower_height * 0.55, local_z + lot_d * 0.225),
                        (lot_w * 0.10, tower_height * 0.20, lot_d * 0.035),
                        tags=["city", "building", "window", f"lot_{index}", f"window_{window_index}"],
                        adjacency=[building_part],
                    )
                )
            index += 1

    sidewalk_width = max(road_width * 0.34, scale * 0.08)
    for side, sign in (("west", -1.0), ("east", 1.0)):
        components.append(
            _component(
                f"city_{side}_sidewalk_region",
                "urban_base",
                sidewalk_part,
                (sign * road_width * 0.74, pad_height * 2.04, 0.0),
                (sidewalk_width, pad_height * 0.70, depth * 0.98),
                tags=["city", "sidewalk", side],
                adjacency=[road_part, block_part],
            )
        )
    for side, sign in (("south", -1.0), ("north", 1.0)):
        components.append(
            _component(
                f"city_{side}_sidewalk_region",
                "urban_base",
                sidewalk_part,
                (0.0, pad_height * 2.05, sign * road_width * 0.74),
                (width * 0.98, pad_height * 0.70, sidewalk_width),
                tags=["city", "sidewalk", side],
                adjacency=[road_part, block_part],
            )
        )
    for index in range(alley_count):
        vertical = index % 2 == 0
        offset = (index // 2 - max(0, alley_count - 1) / 4.0) * (width if vertical else depth) * 0.18
        components.append(
            _component(
                f"city_alley_{index:02d}_region",
                "road_branch",
                road_part,
                (offset if vertical else 0.0, pad_height * 2.10, 0.0 if vertical else offset),
                (road_width * 0.38 if vertical else width * 0.70, pad_height * 0.60, depth * 0.80 if vertical else road_width * 0.38),
                tags=["city", "alley", "service_route", f"alley_{index}", "vertical" if vertical else "horizontal"],
                adjacency=[road_part, lot_part],
            )
        )
    for index in range(plaza_count):
        x = -width * 0.18 + width * 0.36 * ((index + 0.5) / max(1, plaza_count))
        z = depth * 0.18 * (-1.0 if index % 2 else 1.0)
        components.append(
            _component(
                f"city_plaza_{index:02d}_region",
                "urban_base",
                sidewalk_part,
                (x, pad_height * 2.20, z),
                (width * 0.20, pad_height * 0.72, depth * 0.18),
                tags=["city", "plaza", "courtyard", f"plaza_{index}"],
                adjacency=[block_part, lot_part, road_part],
            )
        )
    for index in range(crosswalk_count):
        horizontal = index % 2 == 0
        z = (-0.5 if index < 2 else 0.5) * road_width * 1.24 if horizontal else 0.0
        x = 0.0 if horizontal else (-0.5 if index < 2 else 0.5) * road_width * 1.24
        components.append(
            _component(
                f"city_crosswalk_{index:02d}_region",
                "crosswalk",
                crosswalk_part,
                (x, pad_height * 2.58, z),
                (width * 0.26 if horizontal else road_width * 0.58, pad_height * 0.36, road_width * 0.58 if horizontal else depth * 0.26),
                tags=["city", "crosswalk", "intersection", f"crosswalk_{index}"],
                adjacency=[road_part],
            )
        )
    for index in range(streetlight_count):
        side = "east" if index % 2 == 0 else "west"
        sign = 1.0 if side == "east" else -1.0
        z = -depth * 0.42 + depth * 0.84 * ((index // 2 + 0.5) / max(1, (streetlight_count + 1) // 2))
        components.append(
            _component(
                f"city_streetlight_{index:02d}_region",
                "streetlight",
                streetlight_part,
                (sign * road_width * 1.02, scale * 0.16, z),
                (sidewalk_width * 0.35, scale * 0.38, sidewalk_width * 0.35),
                tags=["city", "streetlight", "sidewalk", side, f"streetlight_{index}"],
                adjacency=[road_part, sidewalk_part],
            )
        )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural city block blueprint generated street grid, lots, building masses, roofs, entries, windows, sidewalks, alleys, plazas, crosswalks, and streetlights"
        ],
    )


def _procedural_interior_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    bay_count = _count(controls, "bays", "wall_bays", "interior_bays", default=3, minimum=1, maximum=8)
    column_count = _count(controls, "columns", "support_count", default=2, minimum=0, maximum=8)
    room_count = _count(controls, "rooms", "room_count", default=1, minimum=1, maximum=12)
    door_opening_control_count = _count(controls, "door_opening_count", "opening_count", "doorway_count", default=0, minimum=0, maximum=24)
    corridor_link_control_count = _count(controls, "corridor_link_count", "corridor_count", default=0, minimum=0, maximum=12)
    wall_run_control_count = _count(controls, "wall_run_count", "wall_count", default=0, minimum=0, maximum=24)
    room_socket_control_count = _count(controls, "room_socket_count", "socket_count", default=0, minimum=0, maximum=32)
    fixture_socket_control_count = _count(controls, "fixture_socket_count", "socket_count", default=0, minimum=0, maximum=32)
    corridor_count = _count(controls, "corridors", "corridor_count", "corridor_link_count", default=max(corridor_link_control_count, 1 if room_count > 1 else 0), minimum=0, maximum=12)
    partition_count = _count(controls, "partitions", "partition_count", "interior_partitions", "wall_run_count", default=max(wall_run_control_count, room_count - 1), minimum=0, maximum=24)
    light_count = _count(controls, "lights", "ceiling_lights", "light_count", default=max(1, room_count), minimum=0, maximum=24)
    stair_core_count = _count(controls, "stair_cores", "stair_core_count", default=0, minimum=0, maximum=4)
    alcove_count = _count(controls, "alcoves", "alcove_count", default=0, minimum=0, maximum=12)
    room_layout = _choice(controls, "room_layout", "layout", default="linear")
    room_role = _choice(controls, "room_role", "furniture_type", "archetype", default="room")
    door_count = _count(controls, "doors", "door_count", "entries", "entry_count", "door_opening_count", default=max(door_opening_control_count, 1 if room_role not in {"empty"} else 0), minimum=0, maximum=24)
    window_count = _count(controls, "windows", "window_count", default=max(1, (bay_count + 1) // 2) if room_role not in {"corridor", "hall", "empty", "stair_core"} else 0, minimum=0, maximum=16)
    furniture_cluster_count = _count(
        controls,
        "furniture_clusters",
        "furniture_cluster_count",
        "furniture_count",
        default=1 if room_role not in {"corridor", "hall", "empty"} else 0,
        minimum=0,
        maximum=24,
    )
    table_count = _count(
        controls,
        "tables",
        "table_count",
        "desk_count",
        default=furniture_cluster_count if room_role in {"office", "dining", "workshop", "classroom", "room"} else 0,
        minimum=0,
        maximum=24,
    )
    chair_count = _count(
        controls,
        "chairs",
        "chair_count",
        "seat_count",
        default=table_count * 2 if table_count else furniture_cluster_count,
        minimum=0,
        maximum=48,
    )
    bed_count = _count(
        controls,
        "beds",
        "bed_count",
        "bunk_count",
        default=max(1, furniture_cluster_count) if room_role in {"bedroom", "barracks", "lodging"} else 0,
        minimum=0,
        maximum=16,
    )
    shelf_count = _count(
        controls,
        "shelves",
        "shelf_count",
        "rack_count",
        default=1 if room_role in {"storage", "library", "office", "workshop"} else 0,
        minimum=0,
        maximum=24,
    )
    cabinet_count = _count(
        controls,
        "cabinets",
        "cabinet_count",
        "locker_count",
        default=1 if room_role in {"kitchen", "storage", "workshop", "office"} else 0,
        minimum=0,
        maximum=24,
    )
    counter_count = _count(
        controls,
        "counters",
        "counter_count",
        "workbench_count",
        default=1 if room_role in {"kitchen", "lab", "workshop", "shop"} else 0,
        minimum=0,
        maximum=16,
    )
    lamp_count = _count(
        controls,
        "lamps",
        "lamp_count",
        "floor_lamp_count",
        default=max(0, furniture_cluster_count - 1),
        minimum=0,
        maximum=24,
    )
    width = scale * _level(controls, "width_scale", "room_width", default=1.35)
    depth = scale * _level(controls, "depth_scale", "room_depth", default=1.12)
    height = scale * _level(controls, "height_scale", "room_height", default=0.70)

    room_part = _part_name(asset_graph, "room", "interior", fallback="room_shell")
    wall_part = _part_name(asset_graph, "wall", "panel", fallback=room_part)
    door_part = _part_name(asset_graph, "door", fallback=wall_part)
    window_part = _part_name(asset_graph, "window", fallback=wall_part)
    column_part = _part_name(asset_graph, "column", "support", fallback=wall_part)
    corridor_part = _part_name(asset_graph, "corridor", "floor", fallback=room_part)
    partition_part = _part_name(asset_graph, "partition", "wall", fallback=wall_part)
    light_part = _part_name(asset_graph, "light", "ceiling", fallback=wall_part)
    stair_part = _part_name(asset_graph, "stair", "stairs", fallback=wall_part)
    alcove_part = _part_name(asset_graph, "alcove", "room", fallback=room_part)
    furniture_part = _part_name(asset_graph, "furniture", "prop", fallback=room_part)
    socket_part = _part_name(asset_graph, "socket", "anchor", fallback=furniture_part)
    table_part = _part_name(asset_graph, "table", "desk", fallback=furniture_part)
    chair_part = _part_name(asset_graph, "chair", "seat", fallback=furniture_part)
    bed_part = _part_name(asset_graph, "bed", "bunk", fallback=furniture_part)
    shelf_part = _part_name(asset_graph, "shelf", "rack", fallback=furniture_part)
    cabinet_part = _part_name(asset_graph, "cabinet", "locker", fallback=furniture_part)
    counter_part = _part_name(asset_graph, "counter", "workbench", fallback=furniture_part)
    lamp_part = _part_name(asset_graph, "lamp", "light", fallback=light_part)

    components = [
        _component(
            "interior_room_region",
            "room",
            room_part,
            (0.0, height * 0.50, 0.0),
            (width, height, depth),
            tags=["room", "interior", "shell"],
        ),
    ]
    for index in range(door_count):
        side = ("front", "back", "left", "right")[index % 4]
        offset = (index // 4 - max(0, (door_count - 1) // 4) / 2.0) * width * 0.18
        if side == "front":
            center = (offset, height * 0.32, depth * 0.50)
            extents = (width * 0.18, height * 0.48, depth * 0.05)
        elif side == "back":
            center = (offset, height * 0.32, -depth * 0.50)
            extents = (width * 0.18, height * 0.48, depth * 0.05)
        elif side == "left":
            center = (-width * 0.50, height * 0.32, offset)
            extents = (width * 0.05, height * 0.48, depth * 0.18)
        else:
            center = (width * 0.50, height * 0.32, offset)
            extents = (width * 0.05, height * 0.48, depth * 0.18)
        components.append(
            _component(
                f"interior_door_{index:02d}_region",
                "door",
                door_part,
                center,
                extents,
                tags=["room", "door", "entry", side, f"door_{index}"],
                adjacency=[room_part],
            )
        )
    if room_count > 1:
        columns = room_count if room_layout in {"linear", "hall"} else max(1, round(room_count**0.5))
        rows = max(1, (room_count + columns - 1) // columns)
        cell_w = width / columns
        cell_d = depth / rows
        for index in range(room_count):
            col = index % columns
            row = index // columns
            x = -width * 0.5 + cell_w * (col + 0.5)
            z = -depth * 0.5 + cell_d * (row + 0.5)
            components.append(
                _component(
                    f"interior_room_cell_{index:02d}_region",
                    "room_cell",
                    room_part,
                    (x, height * 0.26, z),
                    (cell_w * 0.92, height * 0.18, cell_d * 0.92),
                    tags=["room", "cell", "floor_zone", f"room_{index}", room_layout],
                    adjacency=[room_part],
                )
            )
    if corridor_count:
        corridor_segment_count = max(
            corridor_count,
            _count(
                controls,
                "connection_segment_count",
                "route_segment_count",
                default=corridor_count,
                minimum=corridor_count,
                maximum=18,
            ),
        )
        corridor_profile = path_profile_from_controls(
            controls,
            family="procedural_interior",
            segment_count=corridor_segment_count,
            length=depth * 0.92,
            width=width * 0.22,
            height=height,
            default_profile="straight" if room_layout in {"vertical", "stacked"} else "s_curve" if room_layout == "connected_route" else "straight",
        )
        for index, segment in enumerate(corridor_profile["segments"]):
            center_x, center_y, center_z = segment["center"]
            segment_width, segment_depth = segment["extents"]
            components.append(
                _component(
                    f"interior_corridor_{index:02d}_region",
                    "corridor",
                    corridor_part,
                    (center_x, height * 0.18 + center_y, center_z),
                    (segment_width, height * 0.12, segment_depth),
                    tags=["room", "corridor", "circulation", f"corridor_{index}", room_layout, *segment["tags"]],
                    adjacency=[room_part],
                )
            )
        _append_structural_elements(
            components,
            structural_elements_for_path(
                controls,
                family="procedural_interior",
                path_profile=corridor_profile,
                width=width * 0.22,
                height=height * 0.52,
                base_y=height * 0.18,
            ),
            {
                "edge": partition_part,
                "wall": partition_part,
                "roof": wall_part,
                "support": column_part,
                "truss": wall_part,
                "default": room_part,
            },
            adjacency=[room_part],
        )
    for index in range(partition_count):
        t = (index + 1) / (partition_count + 1)
        vertical = index % 2 == 0
        x = -width * 0.38 + width * 0.76 * t if vertical else 0.0
        z = 0.0 if vertical else -depth * 0.38 + depth * 0.76 * t
        components.append(
            _component(
                f"interior_partition_{index:02d}_region",
                "partition",
                partition_part,
                (x, height * 0.48, z),
                (width * 0.035 if vertical else width * 0.76, height * 0.78, depth * 0.72 if vertical else depth * 0.035),
                tags=["room", "partition", "wall", f"partition_{index}", "vertical" if vertical else "horizontal"],
                adjacency=[room_part],
            )
        )
        components.append(
            _component(
                f"interior_partition_door_{index:02d}_region",
                "door",
                door_part,
                (x, height * 0.32, z + (depth * 0.20 if vertical else 0.0)),
                (width * 0.10 if vertical else width * 0.16, height * 0.40, depth * 0.035 if not vertical else depth * 0.08),
                tags=["room", "door", "partition_opening", f"partition_{index}"],
                adjacency=[partition_part],
            )
        )
    bay_spacing = width * 0.74 / max(1, bay_count - 1)
    start_x = -bay_spacing * (bay_count - 1) / 2.0
    for index in range(bay_count):
        x = start_x + bay_spacing * index
        components.append(
            _component(
                f"interior_wall_bay_{index:02d}_region",
                "panel",
                wall_part,
                (x, height * 0.60, -depth * 0.505),
                (width * 0.12, height * 0.52, depth * 0.05),
                tags=["room", "wall", "bay", f"bay_{index}"],
                adjacency=[room_part],
            )
        )
        if index < min(window_count, bay_count):
            components.append(
                _component(
                    f"interior_window_{index:02d}_region",
                    "window",
                    window_part,
                    (x, height * 0.64, -depth * 0.53),
                    (width * 0.11, height * 0.28, depth * 0.045),
                    tags=["room", "window", f"bay_{index}"],
                    adjacency=[room_part, wall_part],
                )
            )
    extra_window_count = max(0, window_count - bay_count)
    for index in range(extra_window_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -depth * 0.30 + depth * 0.60 * ((index // 2) + 0.5) / max(1, (extra_window_count + 1) // 2)
        components.append(
            _component(
                f"interior_side_window_{index:02d}_region",
                "window",
                window_part,
                (sign * width * 0.53, height * 0.64, z),
                (width * 0.045, height * 0.26, depth * 0.12),
                tags=["room", "window", "side_wall", side, f"window_{bay_count + index}"],
                adjacency=[room_part, wall_part],
            )
        )

    column_spacing = width * 0.56 / max(1, column_count - 1) if column_count > 1 else 0.0
    start_column_x = -column_spacing * (column_count - 1) / 2.0
    for index in range(column_count):
        x = start_column_x + column_spacing * index
        components.append(
            _component(
                f"interior_column_{index:02d}_region",
                "column",
                column_part,
                (x, height * 0.48, depth * 0.08),
                (width * 0.055, height * 0.86, width * 0.055),
                tags=["room", "column", "support", f"column_{index}"],
                adjacency=[room_part],
                radius=width * 0.026,
                height=height * 0.86,
            )
        )

    for index in range(light_count):
        columns = max(1, round(light_count**0.5))
        col = index % columns
        row = index // columns
        rows = max(1, (light_count + columns - 1) // columns)
        x = -width * 0.34 + width * 0.68 * (col + 0.5) / columns
        z = -depth * 0.34 + depth * 0.68 * (row + 0.5) / rows
        components.append(
            _component(
                f"ceiling_light_{index:02d}_region",
                "ceiling_light",
                light_part,
                (x, height * 0.94, z),
                (width * 0.10, height * 0.045, width * 0.10),
                tags=["room", "ceiling", "light", "emissive", f"light_{index}"],
                adjacency=[room_part],
            )
        )
    for index in range(furniture_cluster_count):
        columns = max(1, round(furniture_cluster_count**0.5))
        col = index % columns
        row = index // columns
        rows = max(1, (furniture_cluster_count + columns - 1) // columns)
        x = -width * 0.28 + width * 0.56 * (col + 0.5) / columns
        z = -depth * 0.24 + depth * 0.48 * (row + 0.5) / rows
        components.append(
            _component(
                f"furniture_cluster_{index:02d}_region",
                "furniture_base",
                furniture_part,
                (x, height * 0.13, z),
                (width * 0.18, height * 0.09, depth * 0.16),
                tags=["room", "furniture", "cluster", room_role, f"cluster_{index}"],
                adjacency=[room_part],
            )
        )
    for index in range(table_count):
        columns = max(1, round(table_count**0.5))
        col = index % columns
        row = index // columns
        rows = max(1, (table_count + columns - 1) // columns)
        x = -width * 0.26 + width * 0.52 * (col + 0.5) / columns
        z = -depth * 0.20 + depth * 0.40 * (row + 0.5) / rows
        components.append(
            _component(
                f"table_{index:02d}_region",
                "table_top",
                table_part,
                (x, height * 0.28, z),
                (width * 0.20, height * 0.09, depth * 0.15),
                tags=["room", "furniture", "table", room_role, f"table_{index}"],
                adjacency=[room_part, furniture_part],
            )
        )
    for index in range(chair_count):
        ring = index // max(1, table_count or furniture_cluster_count or 1)
        slot = index % max(1, table_count or furniture_cluster_count or 1)
        total_slots = max(1, table_count or furniture_cluster_count or chair_count)
        x = -width * 0.30 + width * 0.60 * ((slot + 0.5) / total_slots)
        z = depth * (0.06 if ring % 2 == 0 else -0.06)
        components.append(
            _component(
                f"chair_seat_{index:02d}_region",
                "chair_seat",
                chair_part,
                (x, height * 0.20, z),
                (width * 0.09, height * 0.08, depth * 0.08),
                tags=["room", "furniture", "chair", "seat", room_role, f"chair_{index}"],
                adjacency=[room_part, table_part],
            )
        )
        components.append(
            _component(
                f"chair_back_{index:02d}_region",
                "chair_back",
                chair_part,
                (x, height * 0.32, z - depth * 0.045),
                (width * 0.09, height * 0.18, depth * 0.035),
                tags=["room", "furniture", "chair", "back", room_role, f"chair_{index}"],
                adjacency=[room_part, table_part],
            )
        )
    for index in range(bed_count):
        x = -width * 0.28 + width * 0.56 * ((index + 0.5) / max(1, bed_count))
        components.append(
            _component(
                f"bed_{index:02d}_region",
                "bed_frame",
                bed_part,
                (x, height * 0.19, -depth * 0.22),
                (width * 0.22, height * 0.12, depth * 0.26),
                tags=["room", "furniture", "bed", room_role, f"bed_{index}"],
                adjacency=[room_part],
            )
        )
    for index in range(shelf_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, shelf_count))
        components.append(
            _component(
                f"shelf_{index:02d}_region",
                "shelf_unit",
                shelf_part,
                (x, height * 0.44, -depth * 0.47),
                (width * 0.16, height * 0.52, depth * 0.06),
                tags=["room", "furniture", "shelf", room_role, f"shelf_{index}"],
                adjacency=[room_part, wall_part],
            )
        )
    for index in range(cabinet_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, cabinet_count))
        components.append(
            _component(
                f"cabinet_{index:02d}_region",
                "cabinet_body",
                cabinet_part,
                (x, height * 0.28, depth * 0.42),
                (width * 0.14, height * 0.36, depth * 0.08),
                tags=["room", "furniture", "cabinet", room_role, f"cabinet_{index}"],
                adjacency=[room_part, wall_part],
            )
        )
    for index in range(counter_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, counter_count))
        components.append(
            _component(
                f"counter_{index:02d}_region",
                "counter_top",
                counter_part,
                (x, height * 0.31, depth * 0.34),
                (width * 0.22, height * 0.10, depth * 0.10),
                tags=["room", "furniture", "counter", room_role, f"counter_{index}"],
                adjacency=[room_part, wall_part],
            )
        )
    for index in range(lamp_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, lamp_count))
        z = depth * (0.32 if index % 2 == 0 else -0.32)
        components.append(
            _component(
                f"floor_lamp_{index:02d}_region",
                "lamp",
                lamp_part,
                (x, height * 0.34, z),
                (width * 0.08, height * 0.34, width * 0.08),
                tags=["room", "furniture", "lamp", "emissive", room_role, f"lamp_{index}"],
                adjacency=[room_part],
            )
        )
    for index in range(stair_core_count):
        x = -width * 0.34 + index * width * 0.24
        components.append(
            _component(
                f"interior_stair_core_{index:02d}_region",
                "stair_core",
                stair_part,
                (x, height * 0.38, depth * 0.18),
                (width * 0.22, height * 0.58, depth * 0.30),
                tags=["room", "stair", "stairs", "core", f"stair_core_{index}"],
                adjacency=[room_part],
            )
        )
    for index in range(alcove_count):
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        z = -depth * 0.26 + depth * 0.52 * ((index // 2) / max(1, (alcove_count + 1) // 2 - 1))
        components.append(
            _component(
                f"{side}_alcove_{index:02d}_region",
                "alcove",
                alcove_part,
                (sign * width * 0.50, height * 0.44, z),
                (width * 0.18, height * 0.50, depth * 0.20),
                tags=["room", "alcove", side, f"alcove_{index}"],
                adjacency=[room_part],
            )
        )
    interior_socket_total = room_socket_control_count + fixture_socket_control_count
    for index in range(interior_socket_total):
        is_fixture = index >= room_socket_control_count
        local_index = index - room_socket_control_count if is_fixture else index
        side = ("front", "right", "back", "left")[index % 4]
        if side == "front":
            x = -width * 0.36 + width * 0.72 * ((index // 4 + 0.5) / max(1, (interior_socket_total + 3) // 4))
            z = depth * 0.48
        elif side == "back":
            x = -width * 0.36 + width * 0.72 * ((index // 4 + 0.5) / max(1, (interior_socket_total + 3) // 4))
            z = -depth * 0.48
        elif side == "left":
            x = -width * 0.48
            z = -depth * 0.34 + depth * 0.68 * ((index // 4 + 0.5) / max(1, (interior_socket_total + 3) // 4))
        else:
            x = width * 0.48
            z = -depth * 0.34 + depth * 0.68 * ((index // 4 + 0.5) / max(1, (interior_socket_total + 3) // 4))
        socket_kind = "fixture_socket" if is_fixture else "room_socket"
        components.append(
            _component(
                f"interior_{socket_kind}_{local_index:02d}_region",
                "socket",
                socket_part,
                (x, height * (0.18 if is_fixture else 0.08), z),
                (width * 0.055, height * 0.045, depth * 0.055),
                tags=["room", "socket", socket_kind, side, room_role, f"{socket_kind}_{local_index}"],
                adjacency=[room_part, furniture_part],
            )
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural interior blueprint generated room cells, corridors, controlled perimeter doors/windows, partitions, partition doors, ceiling lights, stair cores, alcoves, wall bays, supports, room-role furniture layouts, and interior attach sockets"
        ],
    )


def _procedural_furniture_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=1, maximum=24)
    scale = asset_graph.scale_cm
    furniture_type = _choice(
        controls,
        "furniture_type",
        "packed_item",
        "item_type",
        "fixture_type",
        "room_role",
        "furnishing_type",
        "archetype",
        default="room_kit",
    )
    style = _choice(controls, "furniture_style", "style", "decor_style", default="utility")
    kit_like = furniture_type in {"room_kit", "suite", "set", "furnishing_kit"}
    chair_like = {"chair", "seat", "stool"}
    table_like = {"table", "desk", "workstation", "terminal"}
    bed_like = {"bedroom", "bed", "bunk", "medical_bed"}
    shelf_like = {"library", "storage", "workshop", "shelf", "rack", "tool_rack"}
    cabinet_like = {"kitchen", "storage", "workshop", "cabinet", "locker"}
    counter_like = {"kitchen", "bar", "workshop", "counter", "workbench", "lab_bench"}
    appliance_like = {"kitchen", "laundry", "lab", "appliance", "sink", "toilet", "shower"}
    lamp_like = {"lamp", "light", "office", "bedroom", "lounge", "terminal"}
    chair_default = 4 if furniture_type in {"dining", "cafeteria"} else 2 if kit_like or furniture_type in {"lounge", "office"} else 1 if furniture_type in chair_like else 0
    table_default = 1 if kit_like or furniture_type in {"dining", "office", "workshop", "lounge"} | table_like else 0
    bed_default = 1 if furniture_type in bed_like else 0
    shelf_default = 2 if furniture_type in {"library", "storage", "workshop"} else 1 if kit_like or furniture_type in shelf_like else 0
    cabinet_default = 2 if furniture_type in {"kitchen", "storage", "workshop"} else 1 if kit_like or furniture_type in cabinet_like else 0
    counter_default = 2 if furniture_type in {"kitchen", "bar", "workshop"} else 1 if furniture_type in counter_like else 0
    appliance_default = 2 if furniture_type in {"kitchen", "laundry", "lab"} else 1 if furniture_type in appliance_like else 0
    lamp_default = 2 if kit_like or furniture_type in {"office", "bedroom", "lounge"} else 1 if furniture_type in lamp_like else 0

    chair_count = _count(controls, "chair_count", "chairs", "seat_count", default=chair_default, minimum=0, maximum=12)
    table_count = _count(controls, "table_count", "tables", "desk_count", default=table_default, minimum=0, maximum=6)
    bed_count = _count(controls, "bed_count", "beds", "bunk_count", default=bed_default, minimum=0, maximum=4)
    shelf_count = _count(controls, "shelf_count", "shelves", "rack_count", default=shelf_default, minimum=0, maximum=10)
    cabinet_count = _count(controls, "cabinet_count", "cabinets", "locker_count", default=cabinet_default, minimum=0, maximum=10)
    drawer_count = _count(controls, "drawer_count", "drawers", default=max(0, cabinet_count * 2), minimum=0, maximum=32)
    cushion_count = _count(
        controls,
        "cushion_count",
        "cushions",
        "pillow_count",
        default=max(chair_count, bed_count * 2),
        minimum=0,
        maximum=24,
    )
    counter_count = _count(controls, "counter_count", "counters", "workbench_count", default=counter_default, minimum=0, maximum=8)
    appliance_count = _count(controls, "appliance_count", "appliances", "machine_count", default=appliance_default, minimum=0, maximum=8)
    lamp_count = _count(controls, "lamp_count", "lamps", "light_count", default=lamp_default, minimum=0, maximum=12)
    surface_layer_count = _count(controls, "surface_layer_count", "content_finish_preset_count", default=0, minimum=0, maximum=24)
    material_zone_count = _count(controls, "material_zone_count", "content_material_zone_count", "content_surface_zone_count", default=0, minimum=0, maximum=32)
    decal_count = _count(controls, "decal_count", "content_marking_set_count", "content_decal_count", default=0, minimum=0, maximum=48)
    wear_pattern_count = _count(controls, "wear_pattern_count", "content_wear_profile_count", default=0, minimum=0, maximum=48)
    leg_density = _count(controls, "leg_count", "legs", default=4, minimum=0, maximum=8)
    loose_cushion_count = max(0, cushion_count - chair_count - bed_count)
    width = scale * _level(controls, "width_scale", "furniture_width", default=1.10)
    depth = scale * _level(controls, "depth_scale", "furniture_depth", default=0.82)
    height = scale * _level(controls, "height_scale", "furniture_height", default=0.72)

    base_part = _part_name(asset_graph, "furniture", "base", fallback="furniture_base")
    seat_part = _part_name(asset_graph, "seat", "chair", fallback=base_part)
    back_part = _part_name(asset_graph, "back", "chair", fallback=seat_part)
    leg_part = _part_name(asset_graph, "leg", "support", fallback=base_part)
    table_part = _part_name(asset_graph, "table", "desk", fallback=base_part)
    bed_part = _part_name(asset_graph, "bed", "mattress", fallback=base_part)
    shelf_part = _part_name(asset_graph, "shelf", "rack", fallback=base_part)
    cabinet_part = _part_name(asset_graph, "cabinet", "locker", fallback=shelf_part)
    drawer_part = _part_name(asset_graph, "drawer", fallback=cabinet_part)
    cushion_part = _part_name(asset_graph, "cushion", "pillow", "upholstery", fallback=seat_part)
    counter_part = _part_name(asset_graph, "counter", "workbench", fallback=table_part)
    appliance_part = _part_name(asset_graph, "appliance", "fixture", fallback=cabinet_part)
    lamp_part = _part_name(asset_graph, "lamp", "light", fallback=base_part)
    surface_layer_part = _part_name(asset_graph, "surface_layer", "finish_layer", "paint_layer", fallback=base_part)
    material_zone_part = _part_name(asset_graph, "material_zone", "content_zone", "surface_zone", fallback=surface_layer_part)
    decal_part = _part_name(asset_graph, "decal", "marking", "label", fallback=surface_layer_part)
    wear_part = _part_name(asset_graph, "wear_pattern", "wear", "scuff", fallback=decal_part)
    floor_pad_part = _part_name(asset_graph, "floor_pad", "floor_grid", "furniture_anchor", fallback=base_part)
    bracket_part = _part_name(asset_graph, "wall_bracket", "wall_mount", "furniture_anchor", fallback=shelf_part)

    components = [
        _component(
            "furniture_layout_base_region",
            "furniture_base",
            base_part,
            (0.0, height * 0.04, 0.0),
            (width, height * 0.08, depth),
            tags=["furniture", "layout", "base", furniture_type, style],
        )
    ]

    group_count = max(
        1,
        chair_count
        + table_count
        + bed_count
        + shelf_count
        + cabinet_count
        + counter_count
        + appliance_count
        + lamp_count
        + loose_cushion_count,
    )
    columns = max(1, round(group_count**0.5))
    rows = max(1, (group_count + columns - 1) // columns)
    cell_w = width / max(1, columns)
    cell_d = depth / max(1, rows)
    slot_index = 0

    def slot() -> tuple[float, float]:
        nonlocal slot_index
        col = slot_index % columns
        row = slot_index // columns
        slot_index += 1
        jitter_x = float(rng.uniform(-0.025, 0.025)) * cell_w
        jitter_z = float(rng.uniform(-0.025, 0.025)) * cell_d
        return (
            -width * 0.50 + cell_w * (col + 0.5) + jitter_x,
            -depth * 0.50 + cell_d * (row + 0.5) + jitter_z,
        )

    def add_leg_set(
        *,
        prefix: str,
        part: str,
        x: float,
        z: float,
        footprint_w: float,
        footprint_d: float,
        leg_h: float,
        parent: str,
        max_legs: int | None = None,
    ) -> None:
        count = min(max_legs or leg_density, leg_density)
        positions = [
            (-0.42, -0.42),
            (0.42, -0.42),
            (-0.42, 0.42),
            (0.42, 0.42),
            (0.0, -0.42),
            (0.0, 0.42),
            (-0.42, 0.0),
            (0.42, 0.0),
        ]
        for leg_index, (px, pz) in enumerate(positions[:count]):
            components.append(
                _component(
                    f"{prefix}_leg_{leg_index:02d}_region",
                    "furniture_leg",
                    part,
                    (x + px * footprint_w, leg_h * 0.50, z + pz * footprint_d),
                    (max(footprint_w * 0.08, width * 0.020), leg_h, max(footprint_d * 0.08, width * 0.020)),
                    tags=["furniture", "leg", "support", prefix, f"leg_{leg_index}", furniture_type, style],
                    adjacency=[parent, base_part],
                    radius=max(footprint_w, footprint_d) * 0.022,
                    height=leg_h,
                )
            )

    for index in range(chair_count):
        x, z = slot()
        seat_w = cell_w * 0.46
        seat_d = cell_d * 0.42
        seat_h = height * 0.32
        seat_name = f"chair_{index:02d}_seat_region"
        components.append(
            _component(
                seat_name,
                "chair_seat",
                seat_part,
                (x, seat_h, z),
                (seat_w, height * 0.10, seat_d),
                tags=["furniture", "chair", "seat", f"chair_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )
        components.append(
            _component(
                f"chair_{index:02d}_back_region",
                "chair_back",
                back_part,
                (x, height * 0.58, z - seat_d * 0.42),
                (seat_w, height * 0.46, max(seat_d * 0.12, depth * 0.025)),
                tags=["furniture", "chair", "back", f"chair_{index}", furniture_type, style],
                adjacency=[seat_part],
            )
        )
        add_leg_set(prefix=f"chair_{index:02d}", part=leg_part, x=x, z=z, footprint_w=seat_w, footprint_d=seat_d, leg_h=seat_h, parent=seat_part, max_legs=4)

    for index in range(table_count):
        x, z = slot()
        top_w = cell_w * 0.76
        top_d = cell_d * 0.56
        top_y = height * 0.46
        components.append(
            _component(
                f"table_{index:02d}_top_region",
                "table_top",
                table_part,
                (x, top_y, z),
                (top_w, height * 0.10, top_d),
                tags=["furniture", "table", "desk", "top", f"table_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )
        add_leg_set(prefix=f"table_{index:02d}", part=leg_part, x=x, z=z, footprint_w=top_w, footprint_d=top_d, leg_h=top_y, parent=table_part, max_legs=4)

    for index in range(bed_count):
        x, z = slot()
        bed_w = cell_w * 0.82
        bed_d = cell_d * 0.78
        components.append(
            _component(
                f"bed_{index:02d}_base_region",
                "bed_frame",
                bed_part,
                (x, height * 0.22, z),
                (bed_w, height * 0.22, bed_d),
                tags=["furniture", "bed", "frame", f"bed_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )
        components.append(
            _component(
                f"bed_{index:02d}_mattress_region",
                "cushion",
                cushion_part,
                (x, height * 0.38, z),
                (bed_w * 0.92, height * 0.14, bed_d * 0.86),
                tags=["furniture", "bed", "mattress", "cushion", f"bed_{index}", furniture_type, style],
                adjacency=[bed_part],
            )
        )
        components.append(
            _component(
                f"bed_{index:02d}_headboard_region",
                "chair_back",
                bed_part,
                (x, height * 0.58, z - bed_d * 0.46),
                (bed_w, height * 0.46, max(bed_d * 0.08, depth * 0.025)),
                tags=["furniture", "bed", "headboard", f"bed_{index}", furniture_type, style],
                adjacency=[bed_part],
            )
        )

    for index in range(shelf_count):
        x, z = slot()
        components.append(
            _component(
                f"shelf_{index:02d}_unit_region",
                "shelf_unit",
                shelf_part,
                (x, height * 0.48, z),
                (cell_w * 0.56, height * 0.82, cell_d * 0.28),
                tags=["furniture", "shelf", "rack", f"shelf_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )

    for index in range(cabinet_count):
        x, z = slot()
        cabinet_w = cell_w * 0.58
        cabinet_d = cell_d * 0.42
        components.append(
            _component(
                f"cabinet_{index:02d}_body_region",
                "cabinet_body",
                cabinet_part,
                (x, height * 0.38, z),
                (cabinet_w, height * 0.62, cabinet_d),
                tags=["furniture", "cabinet", "locker", f"cabinet_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )
        per_cabinet = max(1, (drawer_count + max(1, cabinet_count) - 1) // max(1, cabinet_count))
        for drawer_index in range(per_cabinet):
            if index * per_cabinet + drawer_index >= drawer_count:
                break
            y = height * (0.18 + 0.12 * drawer_index)
            components.append(
                _component(
                    f"cabinet_{index:02d}_drawer_{drawer_index:02d}_region",
                    "drawer",
                    drawer_part,
                    (x, y, z + cabinet_d * 0.50),
                    (cabinet_w * 0.78, height * 0.08, max(cabinet_d * 0.08, depth * 0.020)),
                    tags=["furniture", "cabinet", "drawer", f"cabinet_{index}", f"drawer_{drawer_index}", furniture_type, style],
                    adjacency=[cabinet_part],
                )
            )

    for index in range(counter_count):
        x, z = slot()
        counter_w = cell_w * 0.90
        counter_d = cell_d * 0.46
        components.append(
            _component(
                f"counter_{index:02d}_top_region",
                "counter_top",
                counter_part,
                (x, height * 0.52, z),
                (counter_w, height * 0.10, counter_d),
                tags=["furniture", "counter", "workbench", "top", f"counter_{index}", furniture_type, style],
                adjacency=[base_part],
            )
        )
        components.append(
            _component(
                f"counter_{index:02d}_base_region",
                "cabinet_body",
                cabinet_part,
                (x, height * 0.30, z),
                (counter_w * 0.84, height * 0.42, counter_d * 0.80),
                tags=["furniture", "counter", "cabinet", "base", f"counter_{index}", furniture_type, style],
                adjacency=[counter_part],
            )
        )

    for index in range(appliance_count):
        x, z = slot()
        components.append(
            _component(
                f"appliance_{index:02d}_body_region",
                "appliance_body",
                appliance_part,
                (x, height * 0.38, z),
                (cell_w * 0.44, height * 0.58, cell_d * 0.38),
                tags=["furniture", "appliance", "fixture", f"appliance_{index}", furniture_type, style],
                adjacency=[base_part, counter_part],
            )
        )

    for index in range(lamp_count):
        x, z = slot()
        components.append(
            _component(
                f"lamp_{index:02d}_region",
                "lamp",
                lamp_part,
                (x, height * 0.52, z),
                (cell_w * 0.22, height * 0.62, cell_w * 0.22),
                tags=["furniture", "lamp", "light", "emissive", f"lamp_{index}", furniture_type, style],
                adjacency=[base_part],
                radius=cell_w * 0.07,
                height=height * 0.62,
            )
        )

    for index in range(loose_cushion_count):
        x, z = slot()
        components.append(
            _component(
                f"loose_cushion_{index:02d}_region",
                "cushion",
                cushion_part,
                (x, height * 0.24, z),
                (cell_w * 0.34, height * 0.12, cell_d * 0.28),
                tags=["furniture", "cushion", "pillow", f"cushion_{index}", furniture_type, style],
                adjacency=[base_part, seat_part],
            )
        )
    for index in range(surface_layer_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, surface_layer_count))
        z = depth * 0.48
        components.append(
            _component(
                f"content_surface_layer_{index:02d}_region",
                "surface_layer_marker",
                surface_layer_part,
                (x, height * 0.66, z),
                (width * 0.060, height * 0.018, depth * 0.035),
                tags=["furniture", "surface", "content_finish", "surface_layer", f"surface_layer_{index}", furniture_type, style],
                adjacency=[base_part, material_zone_part],
            )
        )
    for index in range(material_zone_count):
        x = -width * 0.44 + width * 0.88 * ((index + 0.5) / max(1, material_zone_count))
        z = depth * 0.40
        components.append(
            _component(
                f"content_material_zone_{index:02d}_region",
                "material_zone_marker",
                material_zone_part,
                (x, height * 0.69, z),
                (width * 0.052, height * 0.020, depth * 0.036),
                tags=["furniture", "surface", "content_zone", "material_zone", f"material_zone_{index}", furniture_type, style],
                adjacency=[surface_layer_part, base_part],
            )
        )
    for index in range(decal_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, decal_count))
        z = -depth * 0.50
        components.append(
            _component(
                f"content_decal_{index:02d}_region",
                "decal_marker",
                decal_part,
                (x, height * 0.71, z),
                (width * 0.036, height * 0.010, depth * 0.024),
                tags=["furniture", "surface", "content_marking", "decal", f"decal_{index}", furniture_type, style],
                adjacency=[surface_layer_part, material_zone_part],
            )
        )
    for index in range(wear_pattern_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, wear_pattern_count))
        z = -depth * 0.42 + float(np.sin(index * 1.7)) * depth * 0.035
        components.append(
            _component(
                f"content_wear_{index:02d}_region",
                "wear_pattern_marker",
                wear_part,
                (x, height * 0.73, z),
                (width * 0.040, height * 0.010, depth * 0.012),
                tags=["furniture", "surface", "content_wear", "wear_pattern", f"wear_{index}", furniture_type, style],
                adjacency=[surface_layer_part, decal_part],
            )
        )
    if assembly_member and assembly_mode == "room_layout":
        pad_count = max(1, min(8, assembly_slot_count or 1))
        for index in range(pad_count):
            x = -width * 0.38 + width * 0.76 * ((index + 0.5) / pad_count)
            z = depth * (0.42 if index % 2 else -0.42)
            components.append(
                _component(
                    f"room_layout_floor_pad_{index:02d}_region",
                    "floor_pad",
                    floor_pad_part,
                    (x, height * 0.075, z),
                    (width * 0.18, height * 0.045, depth * 0.13),
                    tags=["furniture", "assembly_member", "room_layout", "floor_pad", "furniture_anchor", f"pad_{index}", furniture_type, style],
                    adjacency=[base_part, leg_part],
                    interface_role="socket",
                )
            )
        wall_brackets = max(1, min(6, shelf_count + cabinet_count + lamp_count))
        for index in range(wall_brackets):
            x = -width * 0.40 + width * 0.80 * ((index + 0.5) / wall_brackets)
            z = -depth * 0.50
            components.append(
                _component(
                    f"room_layout_wall_bracket_{index:02d}_region",
                    "wall_bracket",
                    bracket_part,
                    (x, height * 0.62, z),
                    (width * 0.16, height * 0.20, depth * 0.045),
                    tags=["furniture", "assembly_member", "room_layout", "wall_bracket", "wall_mount", f"bracket_{index}", furniture_type, style],
                    adjacency=[base_part, shelf_part, cabinet_part, lamp_part],
                    interface_role="socket",
                )
            )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural furniture blueprint generated room kits with chairs, tables, beds, shelves, cabinets, drawers, cushions, counters, appliances, lamps, support legs, and room-layout floor/wall anchoring hardware"
        ],
    )


def _procedural_foliage_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    foliage_type = _choice(
        controls,
        "foliage_type",
        "plant_type",
        "nature_type",
        "archetype",
        default="woodland_kit",
    )
    biome = _choice(controls, "biome", "habitat", "environment_style", default="temperate")
    kit_like = foliage_type in {"woodland_kit", "forest_kit", "nature_kit", "garden_kit", "biome_kit"}
    tree_like = foliage_type in {"tree", "oak", "pine", "palm", "dead_tree", "stump"} or kit_like
    desert_like = biome in {"desert", "arid", "badlands"} or foliage_type in {"cactus", "succulent"}
    wet_like = biome in {"wetland", "swamp", "jungle", "rainforest"}
    trunk_count = _count(controls, "trunk_count", "trunks", "tree_count", default=2 if kit_like else 1 if tree_like else 0, minimum=0, maximum=12)
    branch_count = _count(controls, "branch_count", "branches", default=max(0, trunk_count * 4), minimum=0, maximum=48)
    root_count = _count(controls, "root_count", "roots", default=max(0, trunk_count * 3), minimum=0, maximum=36)
    canopy_count = _count(controls, "canopy_count", "canopies", "leaf_cluster_count", default=max(0, trunk_count), minimum=0, maximum=16)
    leaf_cluster_count = _count(
        controls,
        "leaf_cluster_count",
        "leaf_clusters",
        "leaves",
        default=max(0, canopy_count * (3 if wet_like else 2)),
        minimum=0,
        maximum=48,
    )
    bush_count = _count(controls, "bush_count", "bushes", "shrub_count", default=2 if kit_like else 1 if foliage_type in {"bush", "shrub"} else 0, minimum=0, maximum=24)
    grass_count = _count(controls, "grass_count", "grass_clumps", "grass_clump_count", default=8 if kit_like else 3 if foliage_type in {"grass", "meadow"} else 0, minimum=0, maximum=64)
    rock_count = _count(controls, "rock_count", "rocks", "stone_count", default=4 if kit_like or desert_like else 1 if foliage_type in {"rock", "boulder"} else 0, minimum=0, maximum=32)
    mushroom_count = _count(controls, "mushroom_count", "mushrooms", "fungi_count", default=4 if biome in {"forest", "wetland", "swamp"} else 0, minimum=0, maximum=32)
    log_count = _count(controls, "log_count", "logs", "fallen_log_count", default=1 if kit_like else 0, minimum=0, maximum=12)
    vine_count = _count(controls, "vine_count", "vines", default=4 if wet_like else 0, minimum=0, maximum=32)
    flower_count = _count(controls, "flower_count", "flowers", "blossom_count", default=6 if biome in {"meadow", "garden", "forest"} else 0, minimum=0, maximum=64)
    planter_count = _count(controls, "planter_count", "planters", "pot_count", default=1 if foliage_type in {"planter", "potted", "garden"} else 0, minimum=0, maximum=12)
    width = scale * _level(controls, "width_scale", "foliage_width", default=1.15)
    depth = scale * _level(controls, "depth_scale", "foliage_depth", default=0.94)
    height = scale * _level(controls, "height_scale", "foliage_height", default=1.10)

    ground_part = _part_name(asset_graph, "ground", "base", "terrain", fallback="foliage_base")
    trunk_part = _part_name(asset_graph, "trunk", "bark", "tree", fallback=ground_part)
    branch_part = _part_name(asset_graph, "branch", "limb", fallback=trunk_part)
    root_part = _part_name(asset_graph, "root", fallback=trunk_part)
    canopy_part = _part_name(asset_graph, "canopy", "leaf", "leaves", fallback=trunk_part)
    bush_part = _part_name(asset_graph, "bush", "shrub", fallback=canopy_part)
    grass_part = _part_name(asset_graph, "grass", "reed", fallback=ground_part)
    rock_part = _part_name(asset_graph, "rock", "stone", "boulder", fallback=ground_part)
    mushroom_part = _part_name(asset_graph, "mushroom", "fungus", fallback=ground_part)
    log_part = _part_name(asset_graph, "log", "fallen", fallback=trunk_part)
    vine_part = _part_name(asset_graph, "vine", "creeper", fallback=branch_part)
    flower_part = _part_name(asset_graph, "flower", "blossom", "petal", fallback=grass_part)
    planter_part = _part_name(asset_graph, "planter", "pot", fallback=ground_part)

    components = [
        _component(
            "foliage_ground_patch_region",
            "foliage_ground",
            ground_part,
            (0.0, height * 0.025, 0.0),
            (width, height * 0.05, depth),
            tags=["foliage", "nature", "ground", "patch", foliage_type, biome],
        )
    ]

    positions: list[tuple[float, float]] = []
    feature_count = max(1, trunk_count + bush_count + grass_count + rock_count + mushroom_count + log_count + planter_count)
    columns = max(1, round(feature_count**0.5))
    rows = max(1, (feature_count + columns - 1) // columns)
    cell_w = width / max(1, columns)
    cell_d = depth / max(1, rows)
    cursor = 0

    def slot(*, spread: float = 0.82) -> tuple[float, float]:
        nonlocal cursor
        col = cursor % columns
        row = cursor // columns
        cursor += 1
        jitter_x = float(rng.uniform(-0.22, 0.22)) * cell_w
        jitter_z = float(rng.uniform(-0.22, 0.22)) * cell_d
        return (
            (-width * 0.50 + cell_w * (col + 0.5) + jitter_x) * spread,
            (-depth * 0.50 + cell_d * (row + 0.5) + jitter_z) * spread,
        )

    for index in range(trunk_count):
        x, z = slot(spread=0.68)
        positions.append((x, z))
        trunk_h = height * (0.52 + 0.10 * (index % 3))
        trunk_radius = max(width * (0.035 + 0.012 * (index % 2)), 0.08)
        components.append(
            _component(
                f"tree_trunk_{index:02d}_region",
                "tree_trunk",
                trunk_part,
                (x, trunk_h * 0.50 + height * 0.04, z),
                (trunk_radius * 2.0, trunk_h, trunk_radius * 2.0),
                tags=["foliage", "tree", "trunk", "bark", f"trunk_{index}", foliage_type, biome],
                adjacency=[ground_part],
                radius=trunk_radius,
                height=trunk_h,
            )
        )
    for index in range(root_count):
        x, z = positions[index % len(positions)] if positions else slot(spread=0.72)
        angle = float(rng.uniform(0.0, 1.0)) * 6.283185307179586 + index * 0.73
        dx = float(np.cos(angle)) * width * 0.07
        dz = float(np.sin(angle)) * depth * 0.07
        components.append(
            _component(
                f"root_{index:02d}_region",
                "root",
                root_part,
                (x + dx, height * 0.08, z + dz),
                (width * 0.16, height * 0.05, depth * 0.045),
                tags=["foliage", "tree", "root", f"root_{index}", foliage_type, biome],
                adjacency=[trunk_part, ground_part],
                radius=max(width * 0.018, 0.04),
                height=max(width * 0.16, depth * 0.10),
            )
        )
    for index in range(branch_count):
        x, z = positions[index % len(positions)] if positions else slot(spread=0.68)
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        tier = (index // max(1, trunk_count)) % 4
        branch_y = height * (0.38 + 0.10 * tier)
        components.append(
            _component(
                f"{side}_branch_{index:02d}_region",
                "tree_branch",
                branch_part,
                (x + sign * width * (0.06 + 0.02 * tier), branch_y, z + float(rng.uniform(-0.04, 0.04)) * depth),
                (width * (0.20 + 0.02 * tier), height * 0.05, depth * 0.07),
                tags=["foliage", "tree", "branch", side, f"branch_{index}", foliage_type, biome],
                adjacency=[trunk_part, canopy_part],
                radius=max(width * 0.018, 0.035),
                height=width * (0.20 + 0.02 * tier),
                axis="x",
            )
        )
    for index in range(canopy_count):
        x, z = positions[index % len(positions)] if positions else slot(spread=0.60)
        components.append(
            _component(
                f"canopy_{index:02d}_region",
                "leaf_cluster",
                canopy_part,
                (x, height * (0.70 + 0.06 * (index % 2)), z),
                (width * 0.34, height * 0.28, depth * 0.32),
                tags=["foliage", "tree", "canopy", "leaf", f"canopy_{index}", foliage_type, biome],
                adjacency=[trunk_part, branch_part],
                radius=width * 0.16,
                height=height * 0.26,
            )
        )
    for index in range(leaf_cluster_count):
        x, z = positions[index % len(positions)] if positions else slot(spread=0.64)
        offset_x = float(rng.uniform(-0.16, 0.16)) * width
        offset_z = float(rng.uniform(-0.14, 0.14)) * depth
        components.append(
            _component(
                f"leaf_cluster_{index:02d}_region",
                "leaf_cluster",
                canopy_part,
                (x + offset_x, height * (0.58 + float(rng.uniform(0.0, 0.18))), z + offset_z),
                (width * 0.18, height * 0.16, depth * 0.18),
                tags=["foliage", "leaf", "cluster", f"leaf_cluster_{index}", foliage_type, biome],
                adjacency=[branch_part, canopy_part],
                radius=width * 0.08,
                height=height * 0.12,
            )
        )
    for index in range(bush_count):
        x, z = slot(spread=0.84)
        components.append(
            _component(
                f"bush_{index:02d}_region",
                "bush",
                bush_part,
                (x, height * 0.20, z),
                (width * 0.22, height * 0.28, depth * 0.22),
                tags=["foliage", "bush", "shrub", f"bush_{index}", foliage_type, biome],
                adjacency=[ground_part],
                radius=width * 0.11,
                height=height * 0.24,
            )
        )
    for index in range(grass_count):
        x, z = slot(spread=0.92)
        components.append(
            _component(
                f"grass_clump_{index:02d}_region",
                "grass_clump",
                grass_part,
                (x, height * 0.11, z),
                (width * 0.11, height * 0.22, depth * 0.09),
                tags=["foliage", "grass", "clump", f"grass_{index}", foliage_type, biome],
                adjacency=[ground_part],
            )
        )
    for index in range(rock_count):
        x, z = slot(spread=0.90)
        components.append(
            _component(
                f"rock_{index:02d}_region",
                "natural_rock",
                rock_part,
                (x, height * 0.09, z),
                (width * (0.14 + 0.03 * (index % 3)), height * 0.16, depth * (0.12 + 0.02 * (index % 2))),
                tags=["foliage", "rock", "stone", f"rock_{index}", foliage_type, biome],
                adjacency=[ground_part],
            )
        )
    for index in range(mushroom_count):
        x, z = slot(spread=0.86)
        components.append(
            _component(
                f"mushroom_{index:02d}_region",
                "mushroom",
                mushroom_part,
                (x, height * 0.12, z),
                (width * 0.08, height * 0.20, width * 0.08),
                tags=["foliage", "mushroom", "fungus", f"mushroom_{index}", foliage_type, biome],
                adjacency=[ground_part],
                radius=width * 0.035,
                height=height * 0.18,
            )
        )
    for index in range(log_count):
        x, z = slot(spread=0.82)
        components.append(
            _component(
                f"fallen_log_{index:02d}_region",
                "fallen_log",
                log_part,
                (x, height * 0.12, z),
                (width * 0.38, height * 0.12, depth * 0.12),
                tags=["foliage", "log", "fallen", "bark", f"log_{index}", foliage_type, biome],
                adjacency=[ground_part],
                radius=height * 0.055,
                height=width * 0.38,
                axis="x",
            )
        )
    for index in range(vine_count):
        x, z = positions[index % len(positions)] if positions else slot(spread=0.74)
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_vine_{index:02d}_region",
                "vine",
                vine_part,
                (x + sign * width * 0.10, height * 0.40, z + float(rng.uniform(-0.08, 0.08)) * depth),
                (width * 0.05, height * 0.62, depth * 0.06),
                tags=["foliage", "vine", "creeper", side, f"vine_{index}", foliage_type, biome],
                adjacency=[branch_part, canopy_part, ground_part],
                radius=width * 0.012,
                height=height * 0.62,
            )
        )
    for index in range(flower_count):
        x, z = slot(spread=0.94)
        components.append(
            _component(
                f"flower_{index:02d}_region",
                "flower",
                flower_part,
                (x, height * 0.14, z),
                (width * 0.07, height * 0.22, width * 0.07),
                tags=["foliage", "flower", "blossom", "petal", f"flower_{index}", foliage_type, biome],
                adjacency=[ground_part, grass_part],
                radius=width * 0.025,
                height=height * 0.18,
            )
        )
    for index in range(planter_count):
        x, z = slot(spread=0.74)
        components.append(
            _component(
                f"planter_{index:02d}_region",
                "planter",
                planter_part,
                (x, height * 0.16, z),
                (width * 0.22, height * 0.24, depth * 0.22),
                tags=["foliage", "planter", "pot", f"planter_{index}", foliage_type, biome],
                adjacency=[ground_part, grass_part],
                radius=width * 0.10,
                height=height * 0.22,
            )
        )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural foliage blueprint generated terrain patches, trunks, roots, branches, canopies, leaf clusters, bushes, grass clumps, rocks, mushrooms, logs, vines, flowers, and planters"
        ],
    )


def _procedural_urban_prop_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    urban_type = _choice(
        controls,
        "urban_prop_type",
        "street_prop_type",
        "set_dressing_type",
        "archetype",
        default="street_kit",
    )
    district_style = _choice(
        controls,
        "district_style",
        "urban_style",
        "civic_style",
        "style",
        default="civic",
    )
    kit_like = urban_type in {
        "street_kit",
        "urban_kit",
        "set_dressing",
        "civic_kit",
        "market_kit",
        "alley_kit",
        "plaza_kit",
    }
    market_like = urban_type in {"market", "market_kit", "vendor", "stall", "kiosk"}
    traffic_like = urban_type in {"traffic", "roadside", "barrier", "construction", "checkpoint"}
    fence_count = _count(
        controls,
        "fence_count",
        "fences",
        default=3 if kit_like else 1 if urban_type in {"fence", "perimeter", "gate"} else 0,
        minimum=0,
        maximum=24,
    )
    gate_count = _count(
        controls,
        "gate_count",
        "gates",
        default=1 if urban_type in {"gate", "perimeter", "checkpoint"} else 0,
        minimum=0,
        maximum=8,
    )
    sign_count = _count(
        controls,
        "sign_count",
        "signs",
        "signage_count",
        default=2 if kit_like or traffic_like else 1 if urban_type in {"sign", "signage"} else 0,
        minimum=0,
        maximum=24,
    )
    streetlight_count = _count(
        controls,
        "streetlight_count",
        "streetlights",
        "lamp_post_count",
        default=2 if kit_like else 1 if urban_type in {"streetlight", "streetlamp", "lamp_post"} else 0,
        minimum=0,
        maximum=16,
    )
    bench_count = _count(
        controls,
        "bench_count",
        "benches",
        default=2 if kit_like and not traffic_like else 1 if urban_type in {"bench", "plaza"} else 0,
        minimum=0,
        maximum=24,
    )
    bin_count = _count(
        controls,
        "bin_count",
        "trash_bin_count",
        "bins",
        default=2 if kit_like else 1 if urban_type in {"bin", "trash_bin", "waste"} else 0,
        minimum=0,
        maximum=16,
    )
    pole_count = _count(
        controls,
        "pole_count",
        "utility_pole_count",
        "poles",
        default=1 if kit_like or urban_type in {"utility", "utility_pole"} else 0,
        minimum=0,
        maximum=16,
    )
    cable_count = _count(
        controls,
        "cable_count",
        "cables",
        "wire_count",
        default=2 if pole_count else 0,
        minimum=0,
        maximum=24,
    )
    kiosk_count = _count(
        controls,
        "kiosk_count",
        "kiosks",
        default=1 if market_like or urban_type == "plaza_kit" else 0,
        minimum=0,
        maximum=8,
    )
    stall_count = _count(
        controls,
        "stall_count",
        "market_stall_count",
        "stalls",
        default=2 if market_like else 0,
        minimum=0,
        maximum=16,
    )
    barrier_count = _count(
        controls,
        "barrier_count",
        "barriers",
        default=3 if traffic_like else 1 if kit_like else 0,
        minimum=0,
        maximum=24,
    )
    crate_count = _count(
        controls,
        "street_crate_count",
        "crate_count",
        "crates",
        default=3 if market_like or urban_type in {"alley_kit", "loading"} else 0,
        minimum=0,
        maximum=32,
    )
    bollard_count = _count(
        controls,
        "bollard_count",
        "bollards",
        default=4 if traffic_like or urban_type in {"plaza_kit", "sidewalk"} else 0,
        minimum=0,
        maximum=32,
    )
    width = scale * _level(controls, "width_scale", "urban_width", "street_prop_width", default=1.20)
    depth = scale * _level(controls, "depth_scale", "urban_depth", "street_prop_depth", default=0.82)
    height = scale * _level(controls, "height_scale", "urban_height", "street_prop_height", default=0.74)

    base_part = _part_name(asset_graph, "urban_base", "base", "sidewalk", "body", fallback="urban_base")
    fence_part = _part_name(asset_graph, "fence", "rail", fallback=base_part)
    gate_part = _part_name(asset_graph, "gate", fallback=fence_part)
    sign_part = _part_name(asset_graph, "sign", "signage", fallback=base_part)
    streetlight_part = _part_name(asset_graph, "streetlight", "streetlamp", "lamp", "light", fallback=base_part)
    bench_part = _part_name(asset_graph, "bench", "seat", fallback=base_part)
    bin_part = _part_name(asset_graph, "trash_bin", "bin", "waste", fallback=base_part)
    pole_part = _part_name(asset_graph, "utility_pole", "pole", fallback=base_part)
    cable_part = _part_name(asset_graph, "cable", "wire", fallback=pole_part)
    kiosk_part = _part_name(asset_graph, "kiosk", fallback=base_part)
    stall_part = _part_name(asset_graph, "stall", "market", fallback=kiosk_part)
    barrier_part = _part_name(asset_graph, "barrier", "barricade", fallback=base_part)
    crate_part = _part_name(asset_graph, "street_crate", "crate", fallback=base_part)
    bollard_part = _part_name(asset_graph, "bollard", fallback=barrier_part)

    components = [
        _component(
            "urban_base_region",
            "urban_base",
            base_part,
            (0.0, height * 0.025, 0.0),
            (width, height * 0.05, depth),
            tags=["urban", "street", "base", "set_dressing", urban_type, district_style],
        )
    ]

    feature_count = max(
        1,
        fence_count
        + gate_count
        + sign_count
        + streetlight_count
        + bench_count
        + bin_count
        + pole_count
        + kiosk_count
        + stall_count
        + barrier_count
        + crate_count
        + bollard_count,
    )
    columns = max(2, round(feature_count**0.5))
    rows = max(1, (feature_count + columns - 1) // columns)
    cell_w = width / max(1, columns)
    cell_d = depth / max(1, rows)
    cursor = 0

    def slot(*, spread: float = 0.86) -> tuple[float, float]:
        nonlocal cursor
        col = cursor % columns
        row = cursor // columns
        cursor += 1
        jitter_x = float(rng.uniform(-0.18, 0.18)) * cell_w
        jitter_z = float(rng.uniform(-0.18, 0.18)) * cell_d
        return (
            (-width * 0.50 + cell_w * (col + 0.5) + jitter_x) * spread,
            (-depth * 0.50 + cell_d * (row + 0.5) + jitter_z) * spread,
        )

    for index in range(fence_count):
        x = (-width * 0.42 + width * 0.84 * (index / max(1, fence_count - 1))) if fence_count > 1 else 0.0
        z = -depth * 0.43
        components.append(
            _component(
                f"fence_{index:02d}_segment_region",
                "fence_segment",
                fence_part,
                (x, height * 0.26, z),
                (max(cell_w * 0.72, width * 0.12), height * 0.42, depth * 0.055),
                tags=["urban", "fence", "rail", f"fence_{index}", urban_type, district_style],
                adjacency=[base_part],
            )
        )
    for index in range(gate_count):
        x = (-width * 0.18 + index * width * 0.36 / max(1, gate_count - 1)) if gate_count > 1 else 0.0
        components.append(
            _component(
                f"gate_{index:02d}_panel_region",
                "gate_panel",
                gate_part,
                (x, height * 0.28, depth * 0.42),
                (width * 0.24, height * 0.46, depth * 0.06),
                tags=["urban", "gate", "frame", "entry", f"gate_{index}", urban_type, district_style],
                adjacency=[base_part, fence_part],
            )
        )
    for index in range(sign_count):
        x, z = slot(spread=0.82)
        components.append(
            _component(
                f"sign_{index:02d}_post_region",
                "sign_post",
                sign_part,
                (x, height * 0.48, z),
                (width * 0.12, height * 0.82, width * 0.075),
                tags=["urban", "sign", "signage", "post", f"sign_{index}", urban_type, district_style],
                adjacency=[base_part],
                radius=max(width * 0.010, 0.035),
                height=height * 0.72,
            )
        )
    for index in range(streetlight_count):
        x, z = slot(spread=0.90)
        components.append(
            _component(
                f"streetlight_{index:02d}_region",
                "streetlight",
                streetlight_part,
                (x, height * 0.62, z),
                (width * 0.15, height * 1.16, width * 0.15),
                tags=["urban", "streetlight", "streetlamp", "light", "emissive", f"streetlight_{index}", urban_type, district_style],
                adjacency=[base_part],
                radius=max(width * 0.012, 0.035),
                height=height * 1.08,
            )
        )
    for index in range(bench_count):
        x, z = slot(spread=0.84)
        components.append(
            _component(
                f"bench_{index:02d}_region",
                "street_bench",
                bench_part,
                (x, height * 0.16, z),
                (cell_w * 0.62, height * 0.24, cell_d * 0.24),
                tags=["urban", "bench", "seat", f"bench_{index}", urban_type, district_style],
                adjacency=[base_part],
            )
        )
    for index in range(bin_count):
        x, z = slot(spread=0.88)
        components.append(
            _component(
                f"trash_bin_{index:02d}_region",
                "trash_bin",
                bin_part,
                (x, height * 0.18, z),
                (width * 0.12, height * 0.30, width * 0.12),
                tags=["urban", "trash_bin", "bin", "waste", f"bin_{index}", urban_type, district_style],
                adjacency=[base_part],
                radius=max(width * 0.045, 0.05),
                height=height * 0.28,
            )
        )
    pole_positions: list[tuple[float, float]] = []
    for index in range(pole_count):
        x = (-width * 0.40 + width * 0.80 * (index / max(1, pole_count - 1))) if pole_count > 1 else -width * 0.34
        z = depth * (0.30 if index % 2 == 0 else -0.18)
        pole_positions.append((x, z))
        components.append(
            _component(
                f"utility_pole_{index:02d}_region",
                "utility_pole",
                pole_part,
                (x, height * 0.58, z),
                (width * 0.10, height * 1.10, width * 0.10),
                tags=["urban", "utility", "pole", f"pole_{index}", urban_type, district_style],
                adjacency=[base_part],
                radius=max(width * 0.018, 0.045),
                height=height * 1.04,
            )
        )
    for index in range(cable_count):
        if len(pole_positions) >= 2:
            left = pole_positions[index % len(pole_positions)]
            right = pole_positions[(index + 1) % len(pole_positions)]
            center_x = (left[0] + right[0]) * 0.5
            center_z = (left[1] + right[1]) * 0.5
            span = max(abs(left[0] - right[0]), width * 0.28)
        else:
            center_x = 0.0
            center_z = depth * 0.30
            span = width * 0.72
        components.append(
            _component(
                f"cable_{index:02d}_span_region",
                "cable_span",
                cable_part,
                (center_x, height * (0.90 - 0.035 * (index % 3)), center_z),
                (span, height * 0.035, depth * 0.045),
                tags=["urban", "cable", "wire", "utility", f"cable_{index}", urban_type, district_style],
                adjacency=[pole_part],
                radius=max(height * 0.010, 0.018),
                height=span,
                axis="x",
            )
        )
    for index in range(kiosk_count):
        x, z = slot(spread=0.74)
        components.append(
            _component(
                f"kiosk_{index:02d}_body_region",
                "kiosk_body",
                kiosk_part,
                (x, height * 0.34, z),
                (cell_w * 0.62, height * 0.62, cell_d * 0.48),
                tags=["urban", "kiosk", "vendor", "window", f"kiosk_{index}", urban_type, district_style],
                adjacency=[base_part],
            )
        )
    for index in range(stall_count):
        x, z = slot(spread=0.80)
        components.append(
            _component(
                f"market_stall_{index:02d}_region",
                "market_stall",
                stall_part,
                (x, height * 0.30, z),
                (cell_w * 0.70, height * 0.58, cell_d * 0.44),
                tags=["urban", "market", "stall", "vendor", "canopy", f"stall_{index}", urban_type, district_style],
                adjacency=[base_part],
            )
        )
    for index in range(barrier_count):
        x, z = slot(spread=0.92)
        components.append(
            _component(
                f"barrier_{index:02d}_region",
                "street_barrier",
                barrier_part,
                (x, height * 0.12, z),
                (cell_w * 0.46, height * 0.20, cell_d * 0.16),
                tags=["urban", "barrier", "barricade", "warning", f"barrier_{index}", urban_type, district_style],
                adjacency=[base_part],
            )
        )
    for index in range(crate_count):
        x, z = slot(spread=0.88)
        components.append(
            _component(
                f"street_crate_{index:02d}_region",
                "street_crate",
                crate_part,
                (x, height * 0.11, z),
                (cell_w * 0.24, height * 0.18, cell_d * 0.22),
                tags=["urban", "street_crate", "crate", "cargo", f"crate_{index}", urban_type, district_style],
                adjacency=[base_part, kiosk_part, stall_part],
            )
        )
    for index in range(bollard_count):
        x, z = slot(spread=0.94)
        components.append(
            _component(
                f"bollard_{index:02d}_region",
                "bollard",
                bollard_part,
                (x, height * 0.16, z),
                (width * 0.08, height * 0.30, width * 0.08),
                tags=["urban", "bollard", "barrier", f"bollard_{index}", urban_type, district_style],
                adjacency=[base_part],
                radius=max(width * 0.024, 0.04),
                height=height * 0.28,
            )
        )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural urban prop blueprint generated street kits with fences, gates, signs, streetlights, benches, bins, utility poles, cable spans, kiosks, market stalls, barriers, crates, and bollards"
        ],
    )


def _procedural_infrastructure_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    infrastructure_type = _choice(
        controls,
        "infrastructure_type",
        "utility_type",
        "service_type",
        "network_type",
        "archetype",
        default="utility_network",
    )
    service_type = _choice(controls, "service_type", "utility_type", "network_service", default="mixed")
    assembly_mode = _choice(controls, "assembly_mode", "assembly_type", "assembly_layout", default="")
    assembly_slot_count = _count(
        controls,
        "assembly_slot_count",
        "assembly_count",
        "slot_count",
        "module_socket_count",
        default=1 if assembly_mode or controls.get("assembly_anchor") else 0,
        minimum=0,
        maximum=64,
    )
    network_like = infrastructure_type in {
        "utility_network",
        "service_network",
        "infrastructure_kit",
        "factory_service",
        "street_services",
        "maintenance_corridor",
        "equipment_rack",
        "machine_line",
        "utility_run",
    }
    water_like = service_type in {"water", "sewer", "storm", "drainage"} or infrastructure_type in {
        "waterworks",
        "drainage",
        "sewer",
    }
    power_like = service_type in {"power", "electrical", "data", "telecom"} or infrastructure_type in {
        "substation",
        "power_grid",
        "data_trunk",
    }
    pipe_count = _count(
        controls,
        "pipe_count",
        "pipes",
        default=3 if network_like or water_like else 1 if infrastructure_type in {"pipe", "pipeline"} else 0,
        minimum=0,
        maximum=32,
    )
    duct_count = _count(
        controls,
        "duct_count",
        "ducts",
        default=2 if network_like else 1 if infrastructure_type in {"duct", "ventilation"} else 0,
        minimum=0,
        maximum=24,
    )
    conduit_count = _count(
        controls,
        "conduit_count",
        "conduits",
        "overhead_conduit_count",
        default=2 if network_like or power_like else 0,
        minimum=0,
        maximum=24,
    )
    drain_count = _count(
        controls,
        "drain_count",
        "drains",
        "channel_count",
        default=2 if water_like else 1 if infrastructure_type in {"drain", "storm_drain"} else 0,
        minimum=0,
        maximum=16,
    )
    hydrant_count = _count(
        controls,
        "hydrant_count",
        "hydrants",
        default=1 if water_like or infrastructure_type in {"hydrant", "waterworks"} else 0,
        minimum=0,
        maximum=8,
    )
    transformer_count = _count(
        controls,
        "transformer_count",
        "transformers",
        default=1 if power_like or infrastructure_type in {"substation", "transformer"} else 0,
        minimum=0,
        maximum=8,
    )
    junction_box_count = _count(
        controls,
        "junction_box_count",
        "junction_boxes",
        "service_box_count",
        default=2 if network_like or power_like else 1 if infrastructure_type in {"junction_box", "service_box"} else 0,
        minimum=0,
        maximum=24,
    )
    valve_count = _count(
        controls,
        "valve_count",
        "valves",
        default=max(1, pipe_count // 2) if pipe_count else 0,
        minimum=0,
        maximum=24,
    )
    manhole_count = _count(
        controls,
        "manhole_count",
        "manholes",
        default=1 if network_like or water_like else 0,
        minimum=0,
        maximum=12,
    )
    rail_count = _count(
        controls,
        "service_rail_count",
        "rail_count",
        "rails",
        default=2 if network_like else 0,
        minimum=0,
        maximum=16,
    )
    support_count = _count(
        controls,
        "support_count",
        "supports",
        "bracket_count",
        default=max(2, (pipe_count + duct_count + conduit_count) // 2) if network_like else 0,
        minimum=0,
        maximum=32,
    )
    cable_tray_count = _count(
        controls,
        "cable_tray_count",
        "cable_trays",
        "tray_count",
        default=1 if power_like or infrastructure_type in {"data_trunk", "factory_service"} else 0,
        minimum=0,
        maximum=12,
    )
    width = scale * _level(controls, "width_scale", "infrastructure_width", "network_width", default=1.35)
    depth = scale * _level(controls, "depth_scale", "infrastructure_depth", "network_depth", default=0.78)
    height = scale * _level(controls, "height_scale", "infrastructure_height", "network_height", default=0.62)
    network_segment_count = _count(
        controls,
        "connection_segment_count",
        "route_segment_count",
        "network_segment_count",
        default=1,
        minimum=1,
        maximum=16,
    )
    network_profile = path_profile_from_controls(
        controls,
        family="procedural_infrastructure",
        segment_count=network_segment_count,
        length=width * 0.84,
        width=depth * 0.18,
        height=height,
        default_profile="straight" if network_segment_count == 1 else "s_curve",
    )

    base_part = _part_name(asset_graph, "infrastructure_base", "service_base", "base", "body", fallback="infrastructure_base")
    pipe_part = _part_name(asset_graph, "pipe", "pipeline", fallback=base_part)
    duct_part = _part_name(asset_graph, "duct", "vent", fallback=base_part)
    conduit_part = _part_name(asset_graph, "conduit", "overhead_conduit", "cable", fallback=pipe_part)
    drain_part = _part_name(asset_graph, "drain", "channel", "storm_drain", fallback=base_part)
    hydrant_part = _part_name(asset_graph, "hydrant", "fire_hydrant", fallback=pipe_part)
    transformer_part = _part_name(asset_graph, "transformer", "substation", fallback=base_part)
    junction_part = _part_name(asset_graph, "junction_box", "service_box", "box", fallback=base_part)
    valve_part = _part_name(asset_graph, "valve", "valve_wheel", fallback=pipe_part)
    manhole_part = _part_name(asset_graph, "manhole", "cover", fallback=drain_part)
    rail_part = _part_name(asset_graph, "service_rail", "rail", fallback=base_part)
    support_part = _part_name(asset_graph, "support", "bracket", fallback=base_part)
    tray_part = _part_name(asset_graph, "cable_tray", "tray", fallback=conduit_part)
    assembly_slot_part = _part_name(asset_graph, "assembly_slot", "module_socket", "socket", fallback=rail_part)
    rack_part = _part_name(asset_graph, "rack", "rack_socket", "weapon_mount", fallback=assembly_slot_part)
    mooring_part = _part_name(asset_graph, "mooring", "cleat", "dock", fallback=assembly_slot_part)
    parking_part = _part_name(asset_graph, "parking_bay", "hangar_bay", "apron", fallback=base_part)

    components = [
        _component(
            "infrastructure_base_region",
            "infrastructure_base",
            base_part,
            (0.0, height * 0.025, 0.0),
            (width, height * 0.05, depth),
            tags=["infrastructure", "utility", "network", "base", infrastructure_type, service_type],
        )
    ]

    lanes = max(1, pipe_count + duct_count + conduit_count + rail_count + cable_tray_count)
    lane_spacing = depth * 0.70 / max(1, lanes - 1) if lanes > 1 else 0.0
    lane_start = -lane_spacing * (lanes - 1) / 2.0
    lane_index = 0

    def lane_z() -> float:
        nonlocal lane_index
        z = lane_start + lane_spacing * lane_index
        lane_index += 1
        return z

    for index in range(pipe_count):
        z = lane_z() if index < lanes else -depth * 0.30 + depth * 0.60 * (index / max(1, pipe_count - 1))
        y = height * (0.18 + 0.06 * (index % 3))
        for segment in network_profile["segments"]:
            center_x, center_y, center_z = segment["center"]
            _segment_width, segment_length = segment["extents"]
            segment_index = int(segment["index"])
            components.append(
                _component(
                    f"pipe_run_{index:02d}_{segment_index:02d}_region",
                    "pipe_run",
                    pipe_part,
                    (center_z, y + center_y, z + center_x),
                    (segment_length, height * 0.12, height * 0.12),
                    tags=[
                        "infrastructure",
                        "utility",
                        "pipe",
                        "run",
                        f"pipe_{index}",
                        infrastructure_type,
                        service_type,
                        *segment["tags"],
                    ],
                    adjacency=[base_part, junction_part],
                    radius=max(height * (0.040 + 0.010 * (index % 3)), 0.045),
                    height=segment_length,
                    axis="x",
                )
            )
    _append_structural_elements(
        components,
        structural_elements_for_path(
            controls,
            family="procedural_infrastructure",
            path_profile=network_profile,
            width=depth * 0.28,
            height=height * 0.54,
            base_y=height * 0.08,
        ),
        {
            "edge": base_part,
            "wall": base_part,
            "roof": tray_part,
            "support": support_part,
            "truss": support_part,
            "default": base_part,
        },
        adjacency=[base_part, pipe_part, conduit_part],
    )
    for index in range(duct_count):
        z = lane_z() if lane_index < lanes else depth * 0.24
        components.append(
            _component(
                f"duct_run_{index:02d}_region",
                "duct_run",
                duct_part,
                (0.0, height * (0.34 + 0.04 * (index % 2)), z),
                (width * 0.70, height * 0.16, depth * 0.10),
                tags=["infrastructure", "utility", "duct", "ventilation", f"duct_{index}", infrastructure_type, service_type],
                adjacency=[base_part, support_part],
            )
        )
    for index in range(conduit_count):
        z = lane_z() if lane_index < lanes else depth * 0.32
        components.append(
            _component(
                f"overhead_conduit_{index:02d}_region",
                "overhead_conduit",
                conduit_part,
                (0.0, height * (0.58 + 0.04 * (index % 2)), z),
                (width * 0.76, height * 0.08, height * 0.08),
                tags=["infrastructure", "utility", "conduit", "cable", "overhead", f"conduit_{index}", infrastructure_type, service_type],
                adjacency=[support_part, junction_part],
                radius=max(height * 0.026, 0.035),
                height=width * 0.76,
                axis="x",
            )
        )
    for index in range(rail_count):
        z = lane_z() if lane_index < lanes else -depth * 0.34
        components.append(
            _component(
                f"service_rail_{index:02d}_region",
                "service_rail",
                rail_part,
                (0.0, height * 0.42, z),
                (width * 0.82, height * 0.10, depth * 0.08),
                tags=["infrastructure", "service_rail", "mount", "rail", f"rail_{index}", infrastructure_type, service_type],
                adjacency=[base_part, support_part],
            )
        )
    for index in range(cable_tray_count):
        z = lane_z() if lane_index < lanes else depth * 0.0
        components.append(
            _component(
                f"cable_tray_{index:02d}_region",
                "cable_tray",
                tray_part,
                (0.0, height * 0.50, z),
                (width * 0.68, height * 0.12, depth * 0.16),
                tags=["infrastructure", "cable_tray", "data", "power", f"tray_{index}", infrastructure_type, service_type],
                adjacency=[support_part, conduit_part],
            )
        )

    feature_count = max(1, drain_count + hydrant_count + transformer_count + junction_box_count + valve_count + manhole_count)
    columns = max(2, round(feature_count**0.5))
    rows = max(1, (feature_count + columns - 1) // columns)
    cell_w = width / max(1, columns)
    cell_d = depth / max(1, rows)
    cursor = 0

    def slot(*, spread: float = 0.86) -> tuple[float, float]:
        nonlocal cursor
        col = cursor % columns
        row = cursor // columns
        cursor += 1
        jitter_x = float(rng.uniform(-0.16, 0.16)) * cell_w
        jitter_z = float(rng.uniform(-0.16, 0.16)) * cell_d
        return (
            (-width * 0.50 + cell_w * (col + 0.5) + jitter_x) * spread,
            (-depth * 0.50 + cell_d * (row + 0.5) + jitter_z) * spread,
        )

    for index in range(support_count):
        x = -width * 0.42 + width * 0.84 * (index / max(1, support_count - 1))
        components.append(
            _component(
                f"support_bracket_{index:02d}_region",
                "support_bracket",
                support_part,
                (x, height * 0.30, depth * (0.34 if index % 2 else -0.34)),
                (width * 0.055, height * 0.44, depth * 0.10),
                tags=["infrastructure", "support", "bracket", f"support_{index}", infrastructure_type, service_type],
                adjacency=[base_part, pipe_part, duct_part, conduit_part],
            )
        )
    for index in range(drain_count):
        x, z = slot(spread=0.90)
        components.append(
            _component(
                f"drain_channel_{index:02d}_region",
                "drain_channel",
                drain_part,
                (x, height * 0.06, z),
                (cell_w * 0.64, height * 0.08, cell_d * 0.24),
                tags=["infrastructure", "drain", "channel", "storm", f"drain_{index}", infrastructure_type, service_type],
                adjacency=[base_part, pipe_part],
            )
        )
    for index in range(hydrant_count):
        x, z = slot(spread=0.82)
        components.append(
            _component(
                f"hydrant_{index:02d}_region",
                "fire_hydrant",
                hydrant_part,
                (x, height * 0.20, z),
                (width * 0.12, height * 0.36, width * 0.12),
                tags=["infrastructure", "hydrant", "water", f"hydrant_{index}", infrastructure_type, service_type],
                adjacency=[base_part, pipe_part],
                radius=max(width * 0.030, 0.04),
                height=height * 0.34,
            )
        )
    for index in range(transformer_count):
        x, z = slot(spread=0.74)
        components.append(
            _component(
                f"transformer_{index:02d}_box_region",
                "transformer_box",
                transformer_part,
                (x, height * 0.28, z),
                (cell_w * 0.46, height * 0.48, cell_d * 0.38),
                tags=["infrastructure", "transformer", "substation", "power", f"transformer_{index}", infrastructure_type, service_type],
                adjacency=[base_part, conduit_part, junction_part],
            )
        )
    for index in range(junction_box_count):
        x, z = slot(spread=0.88)
        components.append(
            _component(
                f"junction_box_{index:02d}_region",
                "junction_box",
                junction_part,
                (x, height * 0.24, z),
                (cell_w * 0.30, height * 0.34, cell_d * 0.26),
                tags=["infrastructure", "junction_box", "service_box", "utility", f"junction_{index}", infrastructure_type, service_type],
                adjacency=[base_part, pipe_part, conduit_part],
            )
        )
    for index in range(valve_count):
        x, z = slot(spread=0.86)
        components.append(
            _component(
                f"valve_{index:02d}_wheel_region",
                "valve_wheel",
                valve_part,
                (x, height * 0.32, z),
                (width * 0.12, height * 0.20, width * 0.12),
                tags=["infrastructure", "valve", "wheel", "control", f"valve_{index}", infrastructure_type, service_type],
                adjacency=[pipe_part, junction_part],
                radius=max(width * 0.045, 0.05),
                height=max(height * 0.025, 0.035),
                axis="z",
            )
        )
    for index in range(manhole_count):
        x, z = slot(spread=0.92)
        components.append(
            _component(
                f"manhole_{index:02d}_cover_region",
                "manhole_cover",
                manhole_part,
                (x, height * 0.08, z),
                (width * 0.16, height * 0.055, width * 0.16),
                tags=["infrastructure", "manhole", "cover", "access", f"manhole_{index}", infrastructure_type, service_type],
                adjacency=[base_part, drain_part],
                radius=max(width * 0.070, 0.06),
                height=max(height * 0.035, 0.035),
            )
        )

    if assembly_mode and assembly_slot_count:
        assembly_socket_values = controls.get("assembly_sockets")
        if isinstance(assembly_socket_values, list):
            socket_labels = [str(item).strip().lower().replace("-", "_").replace(" ", "_") for item in assembly_socket_values if item]
        elif isinstance(assembly_socket_values, str):
            socket_labels = [assembly_socket_values.strip().lower().replace("-", "_").replace(" ", "_")]
        else:
            socket_labels = []
        if not socket_labels:
            socket_labels = {
                "rack": ["rack_socket", "weapon_mount", "tool_mount"],
                "docking_bay": ["mooring", "deck_mount", "stern_mount"],
                "parking": ["parking_bay", "service_mount"],
                "hangar": ["hangar_bay", "service_mount", "tie_down"],
                "machine_line": ["base_mount", "service_mount", "conveyor_start", "conveyor_end"],
                "site_plan": ["lot_socket", "road_socket", "entry_socket"],
                "terrain_cluster": ["terrain_anchor", "root_socket"],
            }.get(assembly_mode, ["assembly_slot"])

        columns = 1 if assembly_mode == "rack" else max(1, round(assembly_slot_count**0.5))
        rows = max(1, (assembly_slot_count + columns - 1) // columns)
        cell_w = width * 0.82 / max(1, columns)
        cell_d = depth * 0.76 / max(1, rows)
        frame_part = rack_part if assembly_mode == "rack" else mooring_part if assembly_mode == "docking_bay" else parking_part
        components.append(
            _component(
                f"assembly_{assembly_mode}_frame_region",
                "assembly_anchor",
                frame_part,
                (0.0, height * (0.40 if assembly_mode == "rack" else 0.09), 0.0),
                (
                    width * (0.16 if assembly_mode == "rack" else 0.88),
                    height * (0.76 if assembly_mode == "rack" else 0.10),
                    depth * (0.88 if assembly_mode == "rack" else 0.82),
                ),
                tags=["infrastructure", "assembly", "assembly_anchor", assembly_mode, service_type],
                adjacency=[base_part, rail_part, support_part],
            )
        )
        for index in range(assembly_slot_count):
            col = index % columns
            row = index // columns
            socket_label = socket_labels[index % len(socket_labels)]
            x = -width * 0.41 + cell_w * (col + 0.5)
            z = -depth * 0.38 + cell_d * (row + 0.5)
            y = height * 0.13
            extents = (cell_w * 0.56, height * 0.08, cell_d * 0.44)
            part = assembly_slot_part
            component_type = "assembly_slot"
            if assembly_mode == "rack":
                x = 0.0
                z = -depth * 0.36 + depth * 0.72 * ((index + 0.5) / max(1, assembly_slot_count))
                y = height * (0.24 + 0.08 * (index % 4))
                extents = (width * 0.14, height * 0.16, max(depth * 0.08, 0.08))
                part = rack_part
                component_type = "rack_socket"
            elif assembly_mode == "docking_bay":
                part = mooring_part
                component_type = "mooring"
                extents = (cell_w * 0.46, height * 0.12, max(cell_d * 0.20, 0.10))
            elif assembly_mode in {"parking", "hangar"}:
                part = parking_part
                component_type = "hangar_bay" if assembly_mode == "hangar" else "parking_bay"
                extents = (cell_w * 0.72, height * 0.06, cell_d * 0.58)
            elif assembly_mode == "machine_line":
                component_type = "base_mount"
                extents = (cell_w * 0.58, height * 0.10, cell_d * 0.42)
            components.append(
                _component(
                    f"assembly_{assembly_mode}_{index:02d}_{socket_label}_region",
                    component_type,
                    part,
                    (x, y, z),
                    extents,
                    tags=[
                        "infrastructure",
                        "assembly",
                        "assembly_slot",
                        assembly_mode,
                        socket_label,
                        f"assembly_slot_{index}",
                        service_type,
                    ],
                    adjacency=[base_part, frame_part, rail_part],
                    interface_role="socket",
                )
            )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural infrastructure blueprint generated utility networks with pipe runs, ducts, conduits, drains, hydrants, transformers, junction boxes, valves, manholes, service rails, support brackets, cable trays, and socket-addressed assembly anchors"
        ],
    )


def _procedural_access_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    assembly_mode = _assembly_mode(controls)
    assembly_member = _assembly_member(controls)
    assembly_slot_count = _assembly_count(controls, default=2, maximum=32)
    scale = asset_graph.scale_cm
    access_type = _choice(
        controls,
        "access_type",
        "traversal_type",
        "maintenance_access_type",
        "archetype",
        default="maintenance_access",
    )
    access_style = _choice(controls, "access_style", "industrial_style", "style", default="industrial")
    kit_like = access_type in {
        "access_kit",
        "maintenance_access",
        "maintenance_network",
        "factory_access",
        "traversal_kit",
        "service_walkway",
        "industrial_access",
    }
    vertical_like = access_type in {"tower_access", "shaft_access", "ladder_access", "elevator", "scaffold"}
    tunnel_like = access_type in {"tunnel", "underpass", "service_tunnel", "maintenance_corridor"}
    catwalk_count = _count(
        controls,
        "catwalk_count",
        "catwalks",
        default=2 if kit_like else 1 if access_type in {"catwalk", "service_walkway"} else 0,
        minimum=0,
        maximum=24,
    )
    walkway_count = _count(
        controls,
        "walkway_count",
        "walkways",
        "span_count",
        default=1 if kit_like else 1 if access_type in {"walkway", "bridge_walkway"} else 0,
        minimum=0,
        maximum=16,
    )
    ladder_count = _count(
        controls,
        "ladder_count",
        "ladders",
        default=2 if kit_like or vertical_like else 1 if access_type == "ladder" else 0,
        minimum=0,
        maximum=16,
    )
    ramp_count = _count(
        controls,
        "ramp_count",
        "ramps",
        default=1 if kit_like else 1 if access_type == "ramp" else 0,
        minimum=0,
        maximum=12,
    )
    gantry_count = _count(
        controls,
        "gantry_count",
        "gantries",
        default=1 if kit_like or access_type == "gantry" else 0,
        minimum=0,
        maximum=12,
    )
    elevator_count = _count(
        controls,
        "elevator_count",
        "elevators",
        "lift_count",
        default=1 if vertical_like and access_type in {"elevator", "shaft_access", "tower_access"} else 0,
        minimum=0,
        maximum=6,
    )
    platform_count = _count(
        controls,
        "platform_count",
        "platforms",
        "maintenance_platform_count",
        default=2 if kit_like or vertical_like else 1 if access_type == "platform" else 0,
        minimum=0,
        maximum=24,
    )
    tunnel_count = _count(
        controls,
        "tunnel_count",
        "tunnels",
        default=2 if tunnel_like else 0,
        minimum=0,
        maximum=12,
    )
    scaffold_count = _count(
        controls,
        "scaffold_count",
        "scaffolds",
        "scaffold_frame_count",
        default=2 if vertical_like or access_type == "scaffold" else 0,
        minimum=0,
        maximum=20,
    )
    guardrail_count = _count(
        controls,
        "guardrail_count",
        "guardrails",
        default=max(2, catwalk_count + walkway_count + platform_count + ramp_count) if kit_like else 0,
        minimum=0,
        maximum=48,
    )
    safety_gate_count = _count(
        controls,
        "safety_gate_count",
        "safety_gates",
        "gate_count",
        default=1 if kit_like or vertical_like else 0,
        minimum=0,
        maximum=16,
    )
    support_count = _count(
        controls,
        "support_count",
        "supports",
        "column_count",
        default=max(2, catwalk_count + walkway_count + gantry_count + platform_count) if kit_like else 0,
        minimum=0,
        maximum=48,
    )
    access_sequence_marker_count = _count(controls, "access_sequence_count", "access_transition_count", "entry_sequence_count", default=1 if access_type == "access_sequence" else 0, minimum=0, maximum=24)
    public_entry_marker_count = _count(controls, "public_entry_count", "entry_count", "entries", default=1 if access_type == "public_entry" else 0, minimum=0, maximum=32)
    service_entry_marker_count = _count(controls, "service_entry_count", "service_door_count", default=1 if access_type == "service_entry" else 0, minimum=0, maximum=24)
    threshold_transition_marker_count = _count(controls, "threshold_transition_count", "threshold_count", "door_opening_count", default=1 if access_type == "threshold_transition" else 0, minimum=0, maximum=48)
    entry_lobby_marker_count = _count(controls, "entry_lobby_count", "lobby_count", default=1 if access_type == "entry_lobby" else 0, minimum=0, maximum=16)
    access_checkpoint_marker_count = _count(controls, "access_checkpoint_count", "checkpoint_count", "security_gate_count", default=1 if access_type == "access_checkpoint" else 0, minimum=0, maximum=24)
    loading_path_marker_count = _count(controls, "loading_path_count", "loading_route_count", "loading_count", default=1 if access_type == "loading_path" else 0, minimum=0, maximum=24)
    wayfinding_node_marker_count = _count(controls, "wayfinding_node_count", "signage_count", "map_marker_count", default=1 if access_type == "wayfinding_node" else 0, minimum=0, maximum=48)
    circulation_core_marker_count = _count(controls, "circulation_core_count", "circulation_count", default=1 if access_type == "circulation_core" else 0, minimum=0, maximum=16)
    stair_run_marker_count = _count(controls, "stair_run_count", "stair_count", "stairs", default=1 if access_type == "stair_run" else 0, minimum=0, maximum=32)
    elevator_bank_marker_count = _count(controls, "elevator_bank_count", "elevator_count", "lift_count", default=1 if access_type == "elevator_bank" else 0, minimum=0, maximum=16)
    egress_route_marker_count = _count(controls, "egress_route_count", "exit_route_count", "egress_count", default=1 if access_type == "egress_route" else 0, minimum=0, maximum=32)
    emergency_exit_marker_count = _count(controls, "emergency_exit_count", "exit_count", default=1 if access_type == "emergency_exit" else 0, minimum=0, maximum=32)
    corridor_spine_marker_count = _count(controls, "corridor_spine_count", "corridor_count", "corridor_link_count", default=1 if access_type == "corridor_spine" else 0, minimum=0, maximum=48)
    floor_transition_marker_count = _count(controls, "floor_transition_count", "transition_count", "vertical_route_count", default=1 if access_type == "floor_transition" else 0, minimum=0, maximum=64)
    public_circulation_marker_count = _count(controls, "public_circulation_count", "public_route_count", default=1 if access_type == "public_circulation" else 0, minimum=0, maximum=24)
    service_circulation_marker_count = _count(controls, "service_circulation_count", "service_route_count", default=1 if access_type == "service_circulation" else 0, minimum=0, maximum=24)
    stair_detail_marker_count = _count(controls, "stair_detail_count", default=1 if access_type == "stair_detail" else 0, minimum=0, maximum=32)
    tread_pattern_marker_count = _count(controls, "tread_pattern_count", default=1 if access_type == "tread_pattern" else 0, minimum=0, maximum=64)
    landing_platform_marker_count = _count(controls, "landing_platform_count", "landing_count", default=1 if access_type == "landing_platform" else 0, minimum=0, maximum=64)
    handrail_run_marker_count = _count(controls, "handrail_run_count", "handrail_count", default=1 if access_type == "handrail_run" else 0, minimum=0, maximum=96)
    corridor_shell_marker_count = _count(controls, "corridor_shell_count", default=1 if access_type == "corridor_shell" else 0, minimum=0, maximum=48)
    door_rhythm_marker_count = _count(controls, "door_rhythm_count", "door_bay_count", default=1 if access_type == "door_rhythm" else 0, minimum=0, maximum=96)
    ceiling_service_grid_marker_count = _count(controls, "ceiling_service_grid_count", "ceiling_grid_count", default=1 if access_type == "ceiling_service_grid" else 0, minimum=0, maximum=64)
    egress_surface_plan_marker_count = _count(controls, "egress_surface_plan_count", "egress_surface_count", default=1 if access_type == "egress_surface_plan" else 0, minimum=0, maximum=48)
    room_route_binding_marker_count = _count(controls, "room_route_binding_count", "room_connection_count", default=1 if access_type == "room_route_binding" else 0, minimum=0, maximum=96)
    if access_sequence_marker_count or public_entry_marker_count or service_entry_marker_count or loading_path_marker_count:
        walkway_count = max(walkway_count, access_sequence_marker_count + public_entry_marker_count)
        platform_count = max(platform_count, public_entry_marker_count + service_entry_marker_count + entry_lobby_marker_count)
    if threshold_transition_marker_count or access_checkpoint_marker_count:
        safety_gate_count = max(safety_gate_count, threshold_transition_marker_count + access_checkpoint_marker_count)
        guardrail_count = max(guardrail_count, access_checkpoint_marker_count * 2)
    if circulation_core_marker_count or stair_run_marker_count or elevator_bank_marker_count or floor_transition_marker_count:
        platform_count = max(platform_count, circulation_core_marker_count + floor_transition_marker_count + stair_run_marker_count)
        ladder_count = max(ladder_count, stair_run_marker_count)
        elevator_count = max(elevator_count, elevator_bank_marker_count)
        safety_gate_count = max(safety_gate_count, floor_transition_marker_count + emergency_exit_marker_count)
    if egress_route_marker_count or corridor_spine_marker_count or public_circulation_marker_count or service_circulation_marker_count:
        walkway_count = max(walkway_count, egress_route_marker_count + corridor_spine_marker_count + public_circulation_marker_count + service_circulation_marker_count)
        guardrail_count = max(guardrail_count, egress_route_marker_count + corridor_spine_marker_count)
    if stair_detail_marker_count or tread_pattern_marker_count or landing_platform_marker_count or handrail_run_marker_count:
        ladder_count = max(ladder_count, stair_detail_marker_count + tread_pattern_marker_count)
        platform_count = max(platform_count, landing_platform_marker_count + stair_detail_marker_count)
        guardrail_count = max(guardrail_count, handrail_run_marker_count + stair_detail_marker_count * 2)
        safety_gate_count = max(safety_gate_count, landing_platform_marker_count)
    if corridor_shell_marker_count or door_rhythm_marker_count or ceiling_service_grid_marker_count or room_route_binding_marker_count:
        walkway_count = max(walkway_count, corridor_shell_marker_count + room_route_binding_marker_count)
        tunnel_count = max(tunnel_count, corridor_shell_marker_count)
        guardrail_count = max(guardrail_count, door_rhythm_marker_count)
        support_count = max(support_count, ceiling_service_grid_marker_count)
    if egress_surface_plan_marker_count:
        safety_gate_count = max(safety_gate_count, egress_surface_plan_marker_count)
    width = scale * _level(controls, "width_scale", "access_width", "traversal_width", default=1.22)
    depth = scale * _level(controls, "depth_scale", "access_depth", "traversal_depth", default=0.76)
    height = scale * _level(controls, "height_scale", "access_height", "traversal_height", default=0.82)

    base_part = _part_name(asset_graph, "access_base", "base", "floor", "body", fallback="access_base")
    catwalk_part = _part_name(asset_graph, "catwalk", "deck", fallback=base_part)
    walkway_part = _part_name(asset_graph, "walkway", "span", fallback=catwalk_part)
    ladder_part = _part_name(asset_graph, "ladder", fallback=base_part)
    ramp_part = _part_name(asset_graph, "ramp", fallback=catwalk_part)
    gantry_part = _part_name(asset_graph, "gantry", "frame", fallback=base_part)
    elevator_part = _part_name(asset_graph, "elevator", "lift", "shaft", fallback=gantry_part)
    platform_part = _part_name(asset_graph, "platform", "maintenance_platform", fallback=catwalk_part)
    tunnel_part = _part_name(asset_graph, "tunnel", "corridor", fallback=base_part)
    scaffold_part = _part_name(asset_graph, "scaffold", "scaffold_frame", fallback=gantry_part)
    guardrail_part = _part_name(asset_graph, "guardrail", "railing", "rail", fallback=catwalk_part)
    gate_part = _part_name(asset_graph, "safety_gate", "gate", fallback=guardrail_part)
    support_part = _part_name(asset_graph, "support", "column", "bracket", fallback=base_part)
    coupler_part = _part_name(asset_graph, "access_coupler", "route_socket", "connection_socket", fallback=platform_part)
    entry_part = _part_name(asset_graph, "public_entry", "entry", "door", fallback=gate_part)
    service_entry_part = _part_name(asset_graph, "service_entry", "service_door", "dock_entry", fallback=gate_part)
    threshold_part = _part_name(asset_graph, "threshold_transition", "threshold", "door_opening", fallback=walkway_part)
    lobby_part = _part_name(asset_graph, "entry_lobby", "lobby", "arrival_pad", fallback=platform_part)
    checkpoint_part = _part_name(asset_graph, "access_checkpoint", "checkpoint", "security_gate", fallback=gate_part)
    loading_path_part = _part_name(asset_graph, "loading_path", "loading_route", "cargo_path", fallback=walkway_part)
    wayfinding_part = _part_name(asset_graph, "wayfinding_node", "signage", "map_marker", fallback=gate_part)
    circulation_core_part = _part_name(asset_graph, "circulation_core", "vertical_access", "circulation", fallback=platform_part)
    stair_run_part = _part_name(asset_graph, "stair_run", "stair", "stairs", fallback=ladder_part)
    elevator_bank_part = _part_name(asset_graph, "elevator_bank", "elevator", "lift_bank", fallback=elevator_part)
    egress_route_part = _part_name(asset_graph, "egress_route", "exit_route", "escape_route", fallback=walkway_part)
    emergency_exit_part = _part_name(asset_graph, "emergency_exit", "exit_door", "panic_bar", fallback=gate_part)
    corridor_spine_part = _part_name(asset_graph, "corridor_spine", "corridor", "hallway", fallback=walkway_part)
    floor_transition_part = _part_name(asset_graph, "floor_transition", "landing", "floor_link", fallback=platform_part)
    public_circulation_part = _part_name(asset_graph, "public_circulation", "public_route", "visitor_path", fallback=walkway_part)
    service_circulation_part = _part_name(asset_graph, "service_circulation", "service_route", "back_of_house", fallback=walkway_part)
    stair_detail_part = _part_name(asset_graph, "stair_detail", "stair", "tread", fallback=stair_run_part)
    tread_pattern_part = _part_name(asset_graph, "tread_pattern", "tread", "riser", fallback=stair_detail_part)
    landing_platform_part = _part_name(asset_graph, "landing_platform", "landing", "platform", fallback=floor_transition_part)
    handrail_run_part = _part_name(asset_graph, "handrail_run", "handrail", "guardrail", "rail", fallback=guardrail_part)
    corridor_shell_part = _part_name(asset_graph, "corridor_shell", "corridor_wall", "hallway_shell", fallback=corridor_spine_part)
    door_rhythm_part = _part_name(asset_graph, "door_rhythm", "door_bay", "door_opening", fallback=entry_part)
    ceiling_service_grid_part = _part_name(asset_graph, "ceiling_service_grid", "ceiling_grid", "service_grid", fallback=gantry_part)
    egress_surface_plan_part = _part_name(asset_graph, "egress_surface_plan", "exit_marking", "surface_marking", fallback=wayfinding_part)
    room_route_binding_part = _part_name(asset_graph, "room_route_binding", "room_socket", "room_connection", fallback=coupler_part)

    components = [
        _component(
            "access_base_region",
            "access_base",
            base_part,
            (0.0, height * 0.025, 0.0),
            (width, height * 0.05, depth),
            tags=["access", "traversal", "maintenance", "base", access_type, access_style],
        )
    ]
    access_transition_specs = [
        (access_sequence_marker_count, "access_sequence", "sequence", walkway_part, height * 0.16, width * 0.88, height * 0.08, depth * 0.18, [entry_part, threshold_part, lobby_part]),
        (public_entry_marker_count, "public_entry", "entry", entry_part, height * 0.34, width * 0.18, height * 0.58, depth * 0.08, [threshold_part, gate_part, wayfinding_part]),
        (service_entry_marker_count, "service_entry", "service_entry", service_entry_part, height * 0.30, width * 0.22, height * 0.46, depth * 0.10, [loading_path_part, platform_part]),
        (threshold_transition_marker_count, "threshold_transition", "threshold", threshold_part, height * 0.13, width * 0.22, height * 0.055, depth * 0.16, [entry_part, walkway_part]),
        (entry_lobby_marker_count, "entry_lobby", "lobby", lobby_part, height * 0.18, width * 0.42, height * 0.10, depth * 0.34, [threshold_part, wayfinding_part]),
        (access_checkpoint_marker_count, "access_checkpoint", "checkpoint", checkpoint_part, height * 0.38, width * 0.20, height * 0.50, depth * 0.08, [gate_part, guardrail_part]),
        (loading_path_marker_count, "loading_path", "loading", loading_path_part, height * 0.14, width * 0.64, height * 0.07, depth * 0.16, [service_entry_part, platform_part]),
        (wayfinding_node_marker_count, "wayfinding_node", "wayfinding", wayfinding_part, height * 0.42, width * 0.12, height * 0.44, depth * 0.055, [entry_part, lobby_part]),
    ]
    for spec_index, (count, construct_name, marker, part, y, sx, sy, sz, adjacency) in enumerate(access_transition_specs):
        for index in range(count):
            x = -width * 0.46 + width * 0.92 * ((index + 0.5) / max(1, count))
            z = -depth * 0.42 + depth * 0.84 * ((spec_index + 0.5) / len(access_transition_specs))
            components.append(
                _component(
                    f"access_transition_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["access", "access_transition", construct_name, marker, access_type, access_style, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )
    circulation_specs = [
        (circulation_core_marker_count, "circulation_core", "core", circulation_core_part, height * 0.48, width * 0.28, height * 0.88, depth * 0.22, [stair_run_part, elevator_bank_part, corridor_spine_part]),
        (stair_run_marker_count, "stair_run", "stair", stair_run_part, height * 0.44, width * 0.20, height * 0.74, depth * 0.16, [floor_transition_part, guardrail_part]),
        (elevator_bank_marker_count, "elevator_bank", "elevator", elevator_bank_part, height * 0.50, width * 0.18, height * 0.92, depth * 0.18, [floor_transition_part, gate_part]),
        (egress_route_marker_count, "egress_route", "egress", egress_route_part, height * 0.20, width * 0.74, height * 0.08, depth * 0.14, [corridor_spine_part, emergency_exit_part]),
        (emergency_exit_marker_count, "emergency_exit", "exit", emergency_exit_part, height * 0.36, width * 0.18, height * 0.52, depth * 0.07, [egress_route_part, gate_part]),
        (corridor_spine_marker_count, "corridor_spine", "corridor", corridor_spine_part, height * 0.18, width * 0.82, height * 0.07, depth * 0.16, [wayfinding_part, floor_transition_part]),
        (floor_transition_marker_count, "floor_transition", "landing", floor_transition_part, height * 0.30, width * 0.30, height * 0.08, depth * 0.24, [stair_run_part, elevator_bank_part]),
        (public_circulation_marker_count, "public_circulation", "public", public_circulation_part, height * 0.16, width * 0.76, height * 0.07, depth * 0.14, [entry_part, wayfinding_part]),
        (service_circulation_marker_count, "service_circulation", "service", service_circulation_part, height * 0.14, width * 0.70, height * 0.07, depth * 0.13, [service_entry_part, loading_path_part]),
    ]
    for spec_index, (count, construct_name, marker, part, y, sx, sy, sz, adjacency) in enumerate(circulation_specs):
        for index in range(count):
            x = -width * 0.46 + width * 0.92 * ((index + 0.5) / max(1, count))
            z = depth * 0.48 + depth * 0.92 * ((spec_index + 0.5) / len(circulation_specs))
            components.append(
                _component(
                    f"access_circulation_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["access", "circulation_egress", construct_name, marker, access_type, access_style, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )
    circulation_detail_specs = [
        (stair_detail_marker_count, "stair_detail", "detail", stair_detail_part, height * 0.48, width * 0.24, height * 0.62, depth * 0.16, [tread_pattern_part, landing_platform_part, handrail_run_part]),
        (tread_pattern_marker_count, "tread_pattern", "tread", tread_pattern_part, height * 0.26, width * 0.34, height * 0.045, depth * 0.12, [stair_detail_part, landing_platform_part]),
        (landing_platform_marker_count, "landing_platform", "landing", landing_platform_part, height * 0.32, width * 0.28, height * 0.07, depth * 0.20, [stair_detail_part, floor_transition_part]),
        (handrail_run_marker_count, "handrail_run", "handrail", handrail_run_part, height * 0.58, width * 0.34, height * 0.08, depth * 0.055, [stair_detail_part, guardrail_part]),
        (corridor_shell_marker_count, "corridor_shell", "shell", corridor_shell_part, height * 0.38, width * 0.72, height * 0.38, depth * 0.18, [corridor_spine_part, door_rhythm_part, ceiling_service_grid_part]),
        (door_rhythm_marker_count, "door_rhythm", "door_bay", door_rhythm_part, height * 0.34, width * 0.14, height * 0.46, depth * 0.06, [corridor_shell_part, room_route_binding_part]),
        (ceiling_service_grid_marker_count, "ceiling_service_grid", "ceiling_grid", ceiling_service_grid_part, height * 0.66, width * 0.62, height * 0.055, depth * 0.12, [corridor_shell_part, support_part]),
        (egress_surface_plan_marker_count, "egress_surface_plan", "egress_surface", egress_surface_plan_part, height * 0.17, width * 0.52, height * 0.035, depth * 0.10, [egress_route_part, emergency_exit_part, wayfinding_part]),
        (room_route_binding_marker_count, "room_route_binding", "room_binding", room_route_binding_part, height * 0.25, width * 0.18, height * 0.10, depth * 0.10, [corridor_spine_part, door_rhythm_part, coupler_part]),
    ]
    for spec_index, (count, construct_name, marker, part, y, sx, sy, sz, adjacency) in enumerate(circulation_detail_specs):
        for index in range(count):
            x = -width * 0.48 + width * 0.96 * ((index + 0.5) / max(1, count))
            z = depth * 1.38 + depth * 0.96 * ((spec_index + 0.5) / len(circulation_detail_specs))
            components.append(
                _component(
                    f"access_circulation_detail_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["access", "circulation_detail", construct_name, marker, access_type, access_style, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    path_count = max(1, catwalk_count + walkway_count + ramp_count + tunnel_count)
    path_segment_count = max(
        path_count,
        _count(
            controls,
            "connection_segment_count",
            "route_segment_count",
            default=path_count,
            minimum=path_count,
            maximum=24,
        ),
    )
    access_profile = path_profile_from_controls(
        controls,
        family="procedural_access",
        segment_count=path_segment_count,
        length=depth * 0.88,
        width=width * 0.22,
        height=height,
        default_profile="elevated" if support_count or gantry_count else "straight",
    )
    path_segments = list(access_profile["segments"])
    path_index = 0

    def path_point() -> tuple[float, float, float, list[str]]:
        nonlocal path_index
        segment = path_segments[path_index % len(path_segments)]
        path_index += 1
        x, y, z = segment["center"]
        return x, y, z, list(segment["tags"])

    for index in range(catwalk_count):
        x, path_y, z, path_tags = path_point()
        y = height * (0.34 + 0.05 * (index % 2)) + path_y
        components.append(
            _component(
                f"catwalk_{index:02d}_deck_region",
                "catwalk_deck",
                catwalk_part,
                (x, y, z),
                (width * 0.78, height * 0.10, depth * 0.16),
                tags=["access", "catwalk", "deck", "grated", f"catwalk_{index}", access_type, access_style, *path_tags],
                adjacency=[base_part, guardrail_part, support_part],
            )
        )
    for index in range(walkway_count):
        x, path_y, z, path_tags = path_point()
        components.append(
            _component(
                f"walkway_{index:02d}_span_region",
                "walkway_span",
                walkway_part,
                (x, height * 0.42 + path_y, z),
                (width * 0.86, height * 0.12, depth * 0.18),
                tags=["access", "walkway", "span", "bridgeable", f"walkway_{index}", access_type, access_style, *path_tags],
                adjacency=[base_part, guardrail_part, support_part],
            )
        )
    for index in range(ramp_count):
        path_x, path_y, z, path_tags = path_point()
        x = path_x + ((-width * 0.18 + index * width * 0.36 / max(1, ramp_count - 1)) if ramp_count > 1 else -width * 0.18)
        components.append(
            _component(
                f"ramp_{index:02d}_region",
                "access_ramp",
                ramp_part,
                (x, height * 0.20 + path_y, z),
                (width * 0.42, height * 0.24, depth * 0.20),
                tags=["access", "ramp", "traversal", f"ramp_{index}", access_type, access_style, *path_tags],
                adjacency=[base_part, catwalk_part, platform_part],
            )
        )
    for index in range(tunnel_count):
        x, path_y, z, path_tags = path_point()
        components.append(
            _component(
                f"tunnel_{index:02d}_segment_region",
                "tunnel_segment",
                tunnel_part,
                (x, height * 0.28 + path_y, z),
                (width * 0.72, height * 0.48, depth * 0.26),
                tags=["access", "tunnel", "corridor", "covered", f"tunnel_{index}", access_type, access_style, *path_tags],
                adjacency=[base_part, platform_part],
            )
        )
    _append_structural_elements(
        components,
        structural_elements_for_path(
            controls,
            family="procedural_access",
            path_profile=access_profile,
            width=width * 0.82,
            height=height * 0.58,
            base_y=height * 0.22,
        ),
        {
            "edge": guardrail_part,
            "wall": tunnel_part,
            "roof": gantry_part,
            "support": support_part,
            "truss": gantry_part,
            "default": base_part,
        },
        adjacency=[base_part, catwalk_part, walkway_part, support_part],
    )

    feature_count = max(1, ladder_count + gantry_count + elevator_count + platform_count + scaffold_count + safety_gate_count)
    columns = max(2, round(feature_count**0.5))
    rows = max(1, (feature_count + columns - 1) // columns)
    cell_w = width / max(1, columns)
    cell_d = depth / max(1, rows)
    cursor = 0

    def slot(*, spread: float = 0.84) -> tuple[float, float]:
        nonlocal cursor
        col = cursor % columns
        row = cursor // columns
        cursor += 1
        jitter_x = float(rng.uniform(-0.15, 0.15)) * cell_w
        jitter_z = float(rng.uniform(-0.15, 0.15)) * cell_d
        return (
            (-width * 0.50 + cell_w * (col + 0.5) + jitter_x) * spread,
            (-depth * 0.50 + cell_d * (row + 0.5) + jitter_z) * spread,
        )

    for index in range(support_count):
        x = -width * 0.42 + width * 0.84 * (index / max(1, support_count - 1))
        z = depth * (0.32 if index % 2 else -0.32)
        components.append(
            _component(
                f"access_support_{index:02d}_region",
                "access_support",
                support_part,
                (x, height * 0.28, z),
                (width * 0.08, height * 0.54, width * 0.08),
                tags=["access", "support", "column", f"support_{index}", access_type, access_style],
                adjacency=[base_part, catwalk_part, walkway_part, platform_part],
                radius=max(width * 0.020, 0.04),
                height=height * 0.52,
            )
        )
    for index in range(guardrail_count):
        x = -width * 0.42 + width * 0.84 * (index / max(1, guardrail_count - 1))
        side = "left" if index % 2 == 0 else "right"
        sign = -1.0 if side == "left" else 1.0
        components.append(
            _component(
                f"{side}_guardrail_{index:02d}_region",
                "guardrail",
                guardrail_part,
                (x, height * 0.52, sign * depth * 0.36),
                (max(width * 0.22, cell_w * 0.62), height * 0.34, depth * 0.055),
                tags=["access", "guardrail", "rail", side, f"guardrail_{index}", access_type, access_style],
                adjacency=[catwalk_part, walkway_part, platform_part],
            )
        )
    for index in range(ladder_count):
        x, z = slot(spread=0.78)
        components.append(
            _component(
                f"ladder_{index:02d}_region",
                "access_ladder",
                ladder_part,
                (x, height * 0.42, z),
                (width * 0.16, height * 0.78, depth * 0.08),
                tags=["access", "ladder", "vertical", f"ladder_{index}", access_type, access_style],
                adjacency=[base_part, platform_part, catwalk_part],
            )
        )
    for index in range(gantry_count):
        x, z = slot(spread=0.78)
        components.append(
            _component(
                f"gantry_{index:02d}_frame_region",
                "gantry_frame",
                gantry_part,
                (x, height * 0.46, z),
                (cell_w * 0.68, height * 0.82, cell_d * 0.38),
                tags=["access", "gantry", "frame", f"gantry_{index}", access_type, access_style],
                adjacency=[base_part, catwalk_part, support_part],
            )
        )
    for index in range(elevator_count):
        x, z = slot(spread=0.72)
        components.append(
            _component(
                f"elevator_{index:02d}_shaft_region",
                "elevator_shaft",
                elevator_part,
                (x, height * 0.54, z),
                (cell_w * 0.42, height * 0.96, cell_d * 0.34),
                tags=["access", "elevator", "lift", "shaft", f"elevator_{index}", access_type, access_style],
                adjacency=[base_part, platform_part, gantry_part],
            )
        )
    for index in range(platform_count):
        x, z = slot(spread=0.80)
        components.append(
            _component(
                f"platform_{index:02d}_region",
                "access_platform",
                platform_part,
                (x, height * (0.34 + 0.06 * (index % 3)), z),
                (cell_w * 0.58, height * 0.12, cell_d * 0.44),
                tags=["access", "platform", "maintenance_platform", f"platform_{index}", access_type, access_style],
                adjacency=[base_part, catwalk_part, ladder_part, guardrail_part],
            )
        )
    for index in range(scaffold_count):
        x, z = slot(spread=0.86)
        components.append(
            _component(
                f"scaffold_{index:02d}_frame_region",
                "scaffold_frame",
                scaffold_part,
                (x, height * 0.44, z),
                (cell_w * 0.46, height * 0.78, cell_d * 0.34),
                tags=["access", "scaffold", "frame", f"scaffold_{index}", access_type, access_style],
                adjacency=[base_part, platform_part, support_part],
            )
        )
    for index in range(safety_gate_count):
        x, z = slot(spread=0.88)
        components.append(
            _component(
                f"safety_gate_{index:02d}_region",
                "safety_gate",
                gate_part,
                (x, height * 0.36, z),
                (cell_w * 0.30, height * 0.52, depth * 0.06),
                tags=["access", "safety_gate", "gate", "barrier", f"gate_{index}", access_type, access_style],
                adjacency=[guardrail_part, platform_part, ladder_part],
            )
        )
    if assembly_member and assembly_mode in {"access_chain", "chain", "loop", "ring"}:
        for _index, (label, z) in enumerate((("start", -depth * 0.48), ("end", depth * 0.48))):
            components.append(
                _component(
                    f"access_chain_{label}_coupler_region",
                    "access_coupler",
                    coupler_part,
                    (0.0, height * 0.42, z),
                    (width * 0.42, height * 0.18, depth * 0.10),
                    tags=["access", "assembly_member", assembly_mode, "access_coupler", "walkway_socket", label, f"slot_count_{assembly_slot_count}"],
                    adjacency=[base_part, catwalk_part, walkway_part, platform_part],
                    interface_role="socket",
                )
            )
        brace_count = max(2, min(8, assembly_slot_count or 2))
        for index in range(brace_count):
            side = "left" if index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            z = -depth * 0.36 + depth * 0.72 * ((index // 2 + 0.5) / max(1, (brace_count + 1) // 2))
            components.append(
                _component(
                    f"access_chain_alignment_brace_{index:02d}_{side}_region",
                    "alignment_brace",
                    support_part,
                    (sign * width * 0.44, height * 0.32, z),
                    (width * 0.07, height * 0.34, depth * 0.08),
                    tags=["access", "assembly_member", assembly_mode, "alignment_brace", side, f"brace_{index}"],
                    adjacency=[base_part, support_part, guardrail_part],
                )
            )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural access blueprint generated traversal systems with catwalks, walkways, ladders, ramps, gantries, elevator shafts, platforms, tunnel segments, scaffold frames, guardrails, support columns, safety gates, and access-chain couplers"
        ],
    )


def _procedural_setpiece_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    controls = _shape_controls(asset_graph)
    scale = asset_graph.scale_cm
    archetype = _choice(controls, "object_archetype", "archetype", "setpiece", default="compound")
    layout = _choice(controls, "setpiece_layout", "layout", default="compound_cluster")
    density = max(0.1, min(1.4, _level(controls, "setpiece_density", "density", default=0.64)))
    structure_count = _count(controls, "structure_count", "building_count", default=3, minimum=1, maximum=8)
    road_segment_count = _count(controls, "road_segment_count", "segments", "road_segments", default=2, minimum=0, maximum=12)
    branch_count = _count(controls, "branch_count", "branches", default=1, minimum=0, maximum=8)
    access_count = _count(controls, "access_count", "walkway_count", "catwalk_count", default=2, minimum=0, maximum=10)
    infrastructure_count = _count(controls, "infrastructure_count", "pipe_count", "conduit_count", default=2, minimum=0, maximum=12)
    prop_count = _count(controls, "prop_count", "street_crate_count", "stall_count", "kiosk_count", default=4, minimum=0, maximum=24)
    actor_marker_count = _count(
        controls,
        "actor_count",
        "npc_count",
        "agent_count",
        default=max(1, prop_count) if archetype in {"actor", "agent", "npc", "actor_group", "crowd"} else 0,
        minimum=0,
        maximum=128,
    )
    spawn_marker_count = _count(
        controls,
        "spawn_point_count",
        "nests",
        "nest_count",
        default=max(1, prop_count) if archetype in {"ecology", "spawn_ecology"} else 0,
        minimum=0,
        maximum=64,
    )
    behavior_node_count = _count(
        controls,
        "faction_count",
        "loop_count",
        default=max(1, structure_count) if archetype in {"behavior_graph", "faction_behavior"} else 0,
        minimum=0,
        maximum=48,
    )
    state_node_count = _count(
        controls,
        "state_count",
        "state_node_count",
        "transition_count",
        default=max(2, structure_count) if archetype in {"state_machine", "scene_mutation", "state_logic"} else 0,
        minimum=0,
        maximum=64,
    )
    event_marker_count = _count(
        controls,
        "event_count",
        "channel_count",
        "signal_count",
        default=max(1, prop_count) if archetype in {"event", "event_emitter", "alert_network"} else 0,
        minimum=0,
        maximum=64,
    )
    trigger_marker_count = _count(
        controls,
        "trigger_count",
        "condition_count",
        "sensor_count",
        default=max(1, prop_count) if archetype in {"conditional_spawn", "trigger_volume", "alert_network"} else 0,
        minimum=0,
        maximum=64,
    )
    animation_marker_count = _count(
        controls,
        "timeline_count",
        "clip_count",
        "beat_count",
        "pose_count",
        default=max(1, prop_count) if archetype in {"timeline", "sequencer", "animation_clip", "action", "action_timeline"} else 0,
        minimum=0,
        maximum=96,
    )
    moving_part_marker_count = _count(
        controls,
        "moving_part_count",
        "animated_part_count",
        "phase_count",
        default=max(1, prop_count) if archetype in {"moving_part", "door_action", "gate_action", "machine_cycle"} else 0,
        minimum=0,
        maximum=64,
    )
    effect_marker_count = _count(
        controls,
        "vfx_count",
        "effect_count",
        "sound_count",
        default=max(1, prop_count) if archetype in {"vfx_emitter", "sound_cue", "action"} else 0,
        minimum=0,
        maximum=64,
    )
    physics_body_marker_count = _count(
        controls,
        "physics_body_count",
        "rigid_body_count",
        "collider_count",
        default=max(1, prop_count) if archetype in {"physics_body", "breakable_part", "debris_field", "destruction_event"} else 0,
        minimum=0,
        maximum=128,
    )
    physics_joint_marker_count = _count(
        controls,
        "physics_joint_count",
        "joint_count",
        "hinge_count",
        "constraint_count",
        default=max(1, prop_count) if archetype in {"physics_joint", "hinge_joint", "physics_constraint"} else 0,
        minimum=0,
        maximum=96,
    )
    debris_marker_count = _count(
        controls,
        "debris_count",
        "fragment_count",
        default=max(1, prop_count) if archetype in {"debris_field", "breakable_part", "destruction_event"} else 0,
        minimum=0,
        maximum=160,
    )
    flexible_marker_count = _count(
        controls,
        "rope_count",
        "cable_count",
        "segment_count",
        default=max(2, prop_count) if archetype in {"rope", "cable", "cloth_flag"} else 0,
        minimum=0,
        maximum=128,
    )
    force_field_marker_count = _count(
        controls,
        "force_field_count",
        "field_count",
        default=max(1, prop_count) if archetype in {"force_field", "destruction_event"} else 0,
        minimum=0,
        maximum=32,
    )
    surface_layer_marker_count = _count(
        controls,
        "surface_layer_count",
        "material_layer_count",
        "layer_count",
        default=max(1, prop_count) if archetype in {"surface_layer", "material_zone"} else 0,
        minimum=0,
        maximum=96,
    )
    material_zone_marker_count = _count(
        controls,
        "material_zone_count",
        "zone_count",
        "material_slot_count",
        default=max(1, surface_layer_marker_count) if archetype in {"material_zone", "surface_layer"} else 0,
        minimum=0,
        maximum=128,
    )
    decal_marker_count = _count(
        controls,
        "decal_count",
        "marking_count",
        "story_mark_count",
        default=max(1, prop_count) if archetype == "decal" else 0,
        minimum=0,
        maximum=160,
    )
    wear_marker_count = _count(
        controls,
        "wear_pattern_count",
        "wear_count",
        "scratch_count",
        "chip_count",
        default=max(1, prop_count) if archetype == "wear_pattern" else 0,
        minimum=0,
        maximum=160,
    )
    damage_surface_marker_count = _count(
        controls,
        "damage_surface_count",
        "damage_mark_count",
        "crack_count",
        "scorch_count",
        "dent_count",
        default=max(1, prop_count) if archetype == "damage_surface" else 0,
        minimum=0,
        maximum=192,
    )
    surface_transition_marker_count = _count(
        controls,
        "surface_transition_count",
        "transition_band_count",
        "band_count",
        default=max(1, prop_count) if archetype == "surface_transition" else 0,
        minimum=0,
        maximum=96,
    )
    weather_marker_count = _count(
        controls,
        "weather_system_count",
        "weather_count",
        "environment_effect_count",
        default=max(1, prop_count) if archetype in {"weather_system", "environment_effect"} else 0,
        minimum=0,
        maximum=96,
    )
    atmosphere_marker_count = _count(
        controls,
        "atmosphere_count",
        "sky_layer_count",
        default=max(1, weather_marker_count) if archetype in {"atmosphere", "weather_system", "time_of_day"} else 0,
        minimum=0,
        maximum=64,
    )
    wind_marker_count = _count(
        controls,
        "wind_zone_count",
        "gust_count",
        default=max(1, prop_count) if archetype in {"wind_zone", "weather_system"} else 0,
        minimum=0,
        maximum=96,
    )
    liquid_marker_count = _count(
        controls,
        "liquid_body_count",
        "puddle_count",
        "wetness_zone_count",
        default=max(1, prop_count) if archetype in {"liquid_body", "puddle_field", "wetness_zone"} else 0,
        minimum=0,
        maximum=160,
    )
    fire_marker_count = _count(
        controls,
        "fire_source_count",
        "fire_count",
        "heat_haze_count",
        default=max(1, prop_count) if archetype in {"fire_source", "heat_haze"} else 0,
        minimum=0,
        maximum=96,
    )
    smoke_marker_count = _count(
        controls,
        "smoke_emitter_count",
        "smoke_count",
        "mist_volume_count",
        "mist_count",
        default=max(1, prop_count) if archetype in {"smoke_emitter", "mist_volume", "weather_system"} else 0,
        minimum=0,
        maximum=128,
    )
    time_marker_count = _count(
        controls,
        "time_of_day_count",
        "lighting_state_count",
        default=max(1, prop_count) if archetype == "time_of_day" else 0,
        minimum=0,
        maximum=24,
    )
    shot_marker_count = _count(
        controls,
        "shot_count",
        "camera_count",
        default=max(1, prop_count) if archetype in {"shot", "shot_sequence", "presentation_rig"} else 0,
        minimum=0,
        maximum=96,
    )
    camera_rail_marker_count = _count(
        controls,
        "camera_rail_count",
        "camera_path_count",
        default=max(1, prop_count) if archetype == "camera_rail" else 0,
        minimum=0,
        maximum=64,
    )
    focal_marker_count = _count(
        controls,
        "look_at_target_count",
        "focal_zone_count",
        "focus_pull_count",
        "composition_guide_count",
        default=max(1, prop_count) if archetype in {"look_at_target", "focal_zone", "focus_pull", "composition_guide"} else 0,
        minimum=0,
        maximum=96,
    )
    camera_volume_marker_count = _count(
        controls,
        "camera_volume_count",
        "presentation_rig_count",
        "orbit_camera_count",
        "inspection_camera_count",
        default=max(1, prop_count) if archetype in {"camera_volume", "presentation_rig", "orbit_camera", "inspection_camera"} else 0,
        minimum=0,
        maximum=64,
    )
    cutscene_marker_count = _count(
        controls,
        "cutscene_beat_count",
        "shot_sequence_count",
        default=max(1, prop_count) if archetype in {"cutscene_beat", "shot_sequence"} else 0,
        minimum=0,
        maximum=96,
    )
    ambient_marker_count = _count(
        controls,
        "ambient_bed_count",
        "ambient_count",
        "audio_count",
        default=max(1, prop_count) if archetype == "ambient_bed" else 0,
        minimum=0,
        maximum=96,
    )
    sound_zone_marker_count = _count(
        controls,
        "sound_zone_count",
        "sound_count",
        default=max(1, prop_count) if archetype == "sound_zone" else 0,
        minimum=0,
        maximum=128,
    )
    reverb_marker_count = _count(
        controls,
        "reverb_space_count",
        "audio_count",
        default=max(1, prop_count) if archetype == "reverb_space" else 0,
        minimum=0,
        maximum=64,
    )
    occlusion_marker_count = _count(
        controls,
        "acoustic_occluder_count",
        "occluder_count",
        default=max(1, prop_count) if archetype == "acoustic_occluder" else 0,
        minimum=0,
        maximum=64,
    )
    propagation_marker_count = _count(
        controls,
        "sound_propagation_count",
        "propagation_count",
        default=max(1, prop_count) if archetype == "sound_propagation" else 0,
        minimum=0,
        maximum=64,
    )
    music_marker_count = _count(
        controls,
        "music_state_count",
        "music_transition_count",
        "stinger_count",
        default=max(1, prop_count) if archetype in {"music_state", "music_transition", "stinger"} else 0,
        minimum=0,
        maximum=96,
    )
    foley_marker_count = _count(
        controls,
        "foley_emitter_count",
        "foley_count",
        default=max(1, prop_count) if archetype == "foley_emitter" else 0,
        minimum=0,
        maximum=96,
    )
    listener_marker_count = _count(
        controls,
        "listener_zone_count",
        "audio_bus_count",
        default=max(1, prop_count) if archetype in {"listener_zone", "audio_bus"} else 0,
        minimum=0,
        maximum=64,
    )
    acoustic_material_marker_count = _count(
        controls,
        "acoustic_material_count",
        "acoustic_surface_count",
        default=max(1, prop_count) if archetype == "acoustic_material" else 0,
        minimum=0,
        maximum=96,
    )
    prompt_marker_count = _count(
        controls,
        "interaction_prompt_count",
        "prompt_count",
        default=max(1, prop_count) if archetype == "interaction_prompt" else 0,
        minimum=0,
        maximum=128,
    )
    interaction_zone_marker_count = _count(
        controls,
        "interaction_zone_count",
        "interaction_count",
        default=max(1, prop_count) if archetype == "interaction_zone" else 0,
        minimum=0,
        maximum=128,
    )
    usable_marker_count = _count(
        controls,
        "usable_count",
        "affordance_count",
        default=max(1, prop_count) if archetype in {"usable", "affordance"} else 0,
        minimum=0,
        maximum=128,
    )
    pickup_marker_count = _count(
        controls,
        "pickup_count",
        "item_count",
        default=max(1, prop_count) if archetype == "pickup" else 0,
        minimum=0,
        maximum=128,
    )
    inspect_marker_count = _count(
        controls,
        "inspect_point_count",
        "inspect_count",
        default=max(1, prop_count) if archetype == "inspect_point" else 0,
        minimum=0,
        maximum=128,
    )
    terminal_marker_count = _count(
        controls,
        "terminal_count",
        "terminal_marker_count",
        default=max(1, prop_count) if archetype == "terminal" else 0,
        minimum=0,
        maximum=64,
    )
    control_panel_marker_count = _count(
        controls,
        "control_panel_count",
        "button_count",
        "switch_count",
        "lever_count",
        default=max(1, prop_count) if archetype in {"control_panel", "switch", "lever", "button"} else 0,
        minimum=0,
        maximum=128,
    )
    door_lock_marker_count = _count(
        controls,
        "door_lock_count",
        "lock_count",
        default=max(1, prop_count) if archetype == "door_lock" else 0,
        minimum=0,
        maximum=64,
    )
    quest_ui_marker_count = _count(
        controls,
        "quest_marker_count",
        "objective_marker_count",
        default=max(1, prop_count) if archetype == "quest_marker" else 0,
        minimum=0,
        maximum=96,
    )
    signage_marker_count = _count(
        controls,
        "signage_count",
        "sign_count",
        default=max(1, prop_count) if archetype == "signage" else 0,
        minimum=0,
        maximum=128,
    )
    map_ui_marker_count = _count(
        controls,
        "map_marker_count",
        "map_pin_count",
        default=max(1, prop_count) if archetype == "map_marker" else 0,
        minimum=0,
        maximum=128,
    )
    hud_marker_count = _count(
        controls,
        "diegetic_hud_count",
        "ui_anchor_count",
        default=max(1, prop_count) if archetype in {"diegetic_hud", "ui_anchor"} else 0,
        minimum=0,
        maximum=96,
    )
    mission_marker_count = _count(
        controls,
        "mission_count",
        "quest_count",
        default=max(1, prop_count) if archetype == "mission" else 0,
        minimum=0,
        maximum=64,
    )
    objective_chain_marker_count = _count(
        controls,
        "objective_chain_count",
        "objective_count",
        default=max(1, prop_count) if archetype == "objective_chain" else 0,
        minimum=0,
        maximum=128,
    )
    condition_marker_count = _count(
        controls,
        "success_condition_count",
        "failure_condition_count",
        "condition_count",
        default=max(1, prop_count) if archetype in {"success_condition", "failure_condition", "gameplay_rule"} else 0,
        minimum=0,
        maximum=128,
    )
    reward_marker_count = _count(
        controls,
        "reward_table_count",
        "reward_count",
        default=max(1, prop_count) if archetype == "reward_table" else 0,
        minimum=0,
        maximum=96,
    )
    loot_marker_count = _count(
        controls,
        "loot_table_count",
        "loot_count",
        default=max(1, prop_count) if archetype == "loot_table" else 0,
        minimum=0,
        maximum=128,
    )
    inventory_slot_marker_count = _count(
        controls,
        "inventory_slot_count",
        "slot_count",
        default=max(1, prop_count) if archetype == "inventory_slot" else 0,
        minimum=0,
        maximum=128,
    )
    crafting_marker_count = _count(
        controls,
        "crafting_station_count",
        "recipe_count",
        default=max(1, prop_count) if archetype in {"crafting_station", "recipe"} else 0,
        minimum=0,
        maximum=96,
    )
    shop_marker_count = _count(
        controls,
        "shop_count",
        "vendor_count",
        default=max(1, prop_count) if archetype in {"shop", "vendor"} else 0,
        minimum=0,
        maximum=96,
    )
    currency_marker_count = _count(
        controls,
        "currency_count",
        "currency_marker_count",
        default=max(1, prop_count) if archetype == "currency" else 0,
        minimum=0,
        maximum=128,
    )
    reputation_marker_count = _count(
        controls,
        "reputation_rule_count",
        "reputation_count",
        default=max(1, prop_count) if archetype == "reputation_rule" else 0,
        minimum=0,
        maximum=96,
    )
    unlock_marker_count = _count(
        controls,
        "unlock_rule_count",
        "unlock_count",
        default=max(1, prop_count) if archetype == "unlock_rule" else 0,
        minimum=0,
        maximum=96,
    )
    progression_marker_count = _count(
        controls,
        "progression_track_count",
        "level_count",
        default=max(1, prop_count) if archetype == "progression_track" else 0,
        minimum=0,
        maximum=96,
    )
    director_marker_count = _count(
        controls,
        "director_count",
        "encounter_director_count",
        default=max(1, prop_count) if archetype in {"director", "encounter_director"} else 0,
        minimum=0,
        maximum=64,
    )
    director_intent_marker_count = _count(
        controls,
        "director_intent_count",
        "intent_count",
        default=max(1, prop_count) if archetype == "director_intent" else 0,
        minimum=0,
        maximum=128,
    )
    pacing_marker_count = _count(
        controls,
        "pacing_curve_count",
        "encounter_beat_count",
        default=max(1, prop_count) if archetype in {"pacing_curve", "encounter_beat"} else 0,
        minimum=0,
        maximum=128,
    )
    threat_budget_marker_count = _count(
        controls,
        "threat_budget_count",
        "spawn_budget_count",
        default=max(1, prop_count) if archetype in {"threat_budget", "spawn_budget"} else 0,
        minimum=0,
        maximum=96,
    )
    spawn_wave_marker_count = _count(
        controls,
        "spawn_wave_count",
        "wave_count",
        default=max(1, prop_count) if archetype == "spawn_wave" else 0,
        minimum=0,
        maximum=128,
    )
    phase_marker_count = _count(
        controls,
        "combat_phase_count",
        "stealth_phase_count",
        "phase_count",
        default=max(1, prop_count) if archetype in {"combat_phase", "stealth_phase"} else 0,
        minimum=0,
        maximum=96,
    )
    escalation_marker_count = _count(
        controls,
        "escalation_rule_count",
        "adaptive_difficulty_count",
        default=max(1, prop_count) if archetype in {"escalation_rule", "adaptive_difficulty"} else 0,
        minimum=0,
        maximum=96,
    )
    director_signal_marker_count = _count(
        controls,
        "director_signal_count",
        "signal_count",
        default=max(1, prop_count) if archetype == "director_signal" else 0,
        minimum=0,
        maximum=128,
    )
    threat_zone_marker_count = _count(
        controls,
        "threat_zone_count",
        "threat_count",
        default=max(1, prop_count) if archetype == "threat_zone" else 0,
        minimum=0,
        maximum=96,
    )
    reinforcement_route_marker_count = _count(
        controls,
        "reinforcement_route_count",
        "reinforcement_count",
        default=max(1, prop_count) if archetype == "reinforcement_route" else 0,
        minimum=0,
        maximum=96,
    )
    simulation_layer_marker_count = _count(
        controls,
        "simulation_layer_count",
        "simulation_count",
        default=max(1, prop_count) if archetype == "simulation_layer" else 0,
        minimum=0,
        maximum=96,
    )
    field_marker_count = _count(
        controls,
        "field_count",
        "heat_field_count",
        "noise_field_count",
        "visibility_field_count",
        default=max(1, prop_count) if archetype in {"heat_field", "noise_field", "visibility_field"} else 0,
        minimum=0,
        maximum=128,
    )
    resource_flow_marker_count = _count(
        controls,
        "resource_flow_count",
        "flow_count",
        default=max(1, prop_count) if archetype == "resource_flow" else 0,
        minimum=0,
        maximum=96,
    )
    faction_pressure_marker_count = _count(
        controls,
        "faction_pressure_count",
        "pressure_count",
        default=max(1, prop_count) if archetype == "faction_pressure" else 0,
        minimum=0,
        maximum=96,
    )
    territory_marker_count = _count(
        controls,
        "territory_influence_count",
        "territory_count",
        default=max(1, prop_count) if archetype == "territory_influence" else 0,
        minimum=0,
        maximum=96,
    )
    alarm_grid_marker_count = _count(
        controls,
        "alarm_grid_count",
        "alarm_count",
        default=max(1, prop_count) if archetype == "alarm_grid" else 0,
        minimum=0,
        maximum=96,
    )
    patrol_density_marker_count = _count(
        controls,
        "patrol_density_count",
        "patrol_count",
        default=max(1, prop_count) if archetype == "patrol_density" else 0,
        minimum=0,
        maximum=96,
    )
    hazard_field_marker_count = _count(
        controls,
        "hazard_field_count",
        "hazard_count",
        default=max(1, prop_count) if archetype == "hazard_field" else 0,
        minimum=0,
        maximum=96,
    )
    sensor_grid_marker_count = _count(
        controls,
        "sensor_grid_count",
        "sensor_count",
        default=max(1, prop_count) if archetype == "sensor_grid" else 0,
        minimum=0,
        maximum=128,
    )
    cover_map_marker_count = _count(
        controls,
        "cover_map_count",
        "cover_count",
        default=max(1, prop_count) if archetype == "cover_map" else 0,
        minimum=0,
        maximum=96,
    )
    flow_gate_marker_count = _count(
        controls,
        "flow_gate_count",
        "gate_count",
        default=max(1, prop_count) if archetype == "flow_gate" else 0,
        minimum=0,
        maximum=96,
    )
    world_metric_marker_count = _count(
        controls,
        "world_metric_count",
        "metric_count",
        default=max(1, prop_count) if archetype == "world_metric" else 0,
        minimum=0,
        maximum=128,
    )
    simulation_probe_marker_count = _count(
        controls,
        "simulation_probe_count",
        "probe_count",
        default=max(1, prop_count) if archetype == "simulation_probe" else 0,
        minimum=0,
        maximum=128,
    )
    culture_system_marker_count = _count(
        controls,
        "culture_system_count",
        "culture_count",
        default=max(1, prop_count) if archetype == "culture_system" else 0,
        minimum=0,
        maximum=96,
    )
    law_code_marker_count = _count(
        controls,
        "law_code_count",
        "law_count",
        default=max(1, prop_count) if archetype == "law_code" else 0,
        minimum=0,
        maximum=96,
    )
    policy_rule_marker_count = _count(
        controls,
        "policy_rule_count",
        "policy_count",
        default=max(1, prop_count) if archetype == "policy_rule" else 0,
        minimum=0,
        maximum=128,
    )
    economy_model_marker_count = _count(
        controls,
        "economy_model_count",
        "economy_count",
        default=max(1, prop_count) if archetype == "economy_model" else 0,
        minimum=0,
        maximum=96,
    )
    trade_policy_marker_count = _count(
        controls,
        "trade_policy_count",
        "trade_count",
        default=max(1, prop_count) if archetype == "trade_policy" else 0,
        minimum=0,
        maximum=96,
    )
    diplomacy_state_marker_count = _count(
        controls,
        "diplomacy_state_count",
        "diplomacy_count",
        default=max(1, prop_count) if archetype == "diplomacy_state" else 0,
        minimum=0,
        maximum=96,
    )
    social_graph_marker_count = _count(
        controls,
        "social_graph_count",
        "social_count",
        default=max(1, prop_count) if archetype == "social_graph" else 0,
        minimum=0,
        maximum=96,
    )
    social_relation_marker_count = _count(
        controls,
        "social_relation_count",
        "relation_count",
        default=max(1, prop_count) if archetype == "social_relation" else 0,
        minimum=0,
        maximum=128,
    )
    population_group_marker_count = _count(
        controls,
        "population_group_count",
        "group_count",
        default=max(1, prop_count) if archetype == "population_group" else 0,
        minimum=0,
        maximum=128,
    )
    labor_system_marker_count = _count(
        controls,
        "labor_system_count",
        "labor_count",
        default=max(1, prop_count) if archetype == "labor_system" else 0,
        minimum=0,
        maximum=96,
    )
    ritual_calendar_marker_count = _count(
        controls,
        "ritual_calendar_count",
        "ritual_count",
        default=max(1, prop_count) if archetype == "ritual_calendar" else 0,
        minimum=0,
        maximum=96,
    )
    festival_marker_count = _count(
        controls,
        "festival_count",
        "event_count",
        default=max(1, prop_count) if archetype == "festival" else 0,
        minimum=0,
        maximum=96,
    )
    belief_system_marker_count = _count(
        controls,
        "belief_system_count",
        "belief_count",
        default=max(1, prop_count) if archetype == "belief_system" else 0,
        minimum=0,
        maximum=96,
    )
    cultural_marker_marker_count = _count(
        controls,
        "cultural_marker_count",
        "marker_count",
        default=max(1, prop_count) if archetype == "cultural_marker" else 0,
        minimum=0,
        maximum=128,
    )
    civic_institution_marker_count = _count(
        controls,
        "civic_institution_count",
        "institution_count",
        default=max(1, prop_count) if archetype == "civic_institution" else 0,
        minimum=0,
        maximum=96,
    )
    biome_system_marker_count = _count(
        controls,
        "biome_system_count",
        "biome_count",
        "ecology_count",
        default=max(1, prop_count) if archetype == "biome_system" else 0,
        minimum=0,
        maximum=96,
    )
    habitat_zone_marker_count = _count(
        controls,
        "habitat_zone_count",
        "habitat_count",
        default=max(1, prop_count) if archetype == "habitat_zone" else 0,
        minimum=0,
        maximum=128,
    )
    species_population_marker_count = _count(
        controls,
        "species_population_count",
        "species_count",
        "population_count",
        default=max(1, prop_count) if archetype == "species_population" else 0,
        minimum=0,
        maximum=128,
    )
    food_web_marker_count = _count(
        controls,
        "food_web_count",
        "web_count",
        default=max(1, prop_count) if archetype == "food_web" else 0,
        minimum=0,
        maximum=96,
    )
    predator_prey_link_marker_count = _count(
        controls,
        "predator_prey_link_count",
        "food_web_link_count",
        default=max(1, prop_count) if archetype == "predator_prey_link" else 0,
        minimum=0,
        maximum=128,
    )
    migration_route_marker_count = _count(
        controls,
        "migration_route_count",
        "migration_count",
        default=max(1, prop_count) if archetype == "migration_route" else 0,
        minimum=0,
        maximum=96,
    )
    nesting_site_marker_count = _count(
        controls,
        "nesting_site_count",
        "nest_count",
        default=max(1, prop_count) if archetype == "nesting_site" else 0,
        minimum=0,
        maximum=128,
    )
    resource_patch_marker_count = _count(
        controls,
        "resource_patch_count",
        "patch_count",
        "resource_count",
        default=max(1, prop_count) if archetype == "resource_patch" else 0,
        minimum=0,
        maximum=128,
    )
    resource_regeneration_marker_count = _count(
        controls,
        "resource_regeneration_count",
        "regeneration_count",
        default=max(1, prop_count) if archetype == "resource_regeneration" else 0,
        minimum=0,
        maximum=128,
    )
    growth_cycle_marker_count = _count(
        controls,
        "growth_cycle_count",
        "growth_count",
        "cycle_count",
        default=max(1, prop_count) if archetype == "growth_cycle" else 0,
        minimum=0,
        maximum=128,
    )
    weather_ecology_link_marker_count = _count(
        controls,
        "weather_ecology_link_count",
        "weather_link_count",
        default=max(1, prop_count) if archetype == "weather_ecology_link" else 0,
        minimum=0,
        maximum=96,
    )
    ecological_pressure_marker_count = _count(
        controls,
        "ecological_pressure_count",
        "pressure_count",
        default=max(1, prop_count) if archetype == "ecological_pressure" else 0,
        minimum=0,
        maximum=96,
    )
    land_use_plan_marker_count = _count(
        controls,
        "land_use_plan_count",
        "land_use_count",
        default=max(1, prop_count) if archetype == "land_use_plan" else 0,
        minimum=0,
        maximum=96,
    )
    farm_plot_marker_count = _count(
        controls,
        "farm_plot_count",
        "farm_count",
        "crop_count",
        default=max(1, prop_count) if archetype == "farm_plot" else 0,
        minimum=0,
        maximum=128,
    )
    hunting_ground_marker_count = _count(
        controls,
        "hunting_ground_count",
        "hunting_count",
        default=max(1, prop_count) if archetype == "hunting_ground" else 0,
        minimum=0,
        maximum=96,
    )
    fishing_ground_marker_count = _count(
        controls,
        "fishing_ground_count",
        "fishing_count",
        default=max(1, prop_count) if archetype == "fishing_ground" else 0,
        minimum=0,
        maximum=96,
    )
    grazing_range_marker_count = _count(
        controls,
        "grazing_range_count",
        "grazing_count",
        "livestock_count",
        default=max(1, prop_count) if archetype == "grazing_range" else 0,
        minimum=0,
        maximum=96,
    )
    extraction_site_marker_count = _count(
        controls,
        "extraction_site_count",
        "extraction_count",
        default=max(1, prop_count) if archetype == "extraction_site" else 0,
        minimum=0,
        maximum=96,
    )
    pollution_source_marker_count = _count(
        controls,
        "pollution_source_count",
        "pollution_count",
        default=max(1, prop_count) if archetype == "pollution_source" else 0,
        minimum=0,
        maximum=96,
    )
    conservation_zone_marker_count = _count(
        controls,
        "conservation_zone_count",
        "conservation_count",
        default=max(1, prop_count) if archetype == "conservation_zone" else 0,
        minimum=0,
        maximum=96,
    )
    restoration_project_marker_count = _count(
        controls,
        "restoration_project_count",
        "restoration_count",
        default=max(1, prop_count) if archetype == "restoration_project" else 0,
        minimum=0,
        maximum=96,
    )
    scarcity_loop_marker_count = _count(
        controls,
        "scarcity_loop_count",
        "scarcity_count",
        default=max(1, prop_count) if archetype == "scarcity_loop" else 0,
        minimum=0,
        maximum=96,
    )
    settlement_pressure_marker_count = _count(
        controls,
        "settlement_pressure_count",
        "pressure_count",
        default=max(1, prop_count) if archetype == "settlement_pressure" else 0,
        minimum=0,
        maximum=96,
    )
    resource_claim_marker_count = _count(
        controls,
        "resource_claim_count",
        "claim_count",
        default=max(1, prop_count) if archetype == "resource_claim" else 0,
        minimum=0,
        maximum=128,
    )
    harvest_cycle_marker_count = _count(
        controls,
        "harvest_cycle_count",
        "harvest_count",
        default=max(1, prop_count) if archetype == "harvest_cycle" else 0,
        minimum=0,
        maximum=128,
    )
    carrying_capacity_rule_marker_count = _count(
        controls,
        "carrying_capacity_rule_count",
        "capacity_rule_count",
        default=max(1, prop_count) if archetype == "carrying_capacity_rule" else 0,
        minimum=0,
        maximum=96,
    )
    biome_impact_marker_count = _count(
        controls,
        "biome_impact_count",
        "impact_count",
        default=max(1, prop_count) if archetype == "biome_impact" else 0,
        minimum=0,
        maximum=96,
    )
    supply_chain_marker_count = _count(
        controls,
        "supply_chain_count",
        "chain_count",
        "logistics_count",
        default=max(1, prop_count) if archetype == "supply_chain" else 0,
        minimum=0,
        maximum=96,
    )
    logistics_hub_marker_count = _count(
        controls,
        "logistics_hub_count",
        "hub_count",
        default=max(1, prop_count) if archetype == "logistics_hub" else 0,
        minimum=0,
        maximum=96,
    )
    storage_depot_marker_count = _count(
        controls,
        "storage_depot_count",
        "depot_count",
        "storage_count",
        default=max(1, prop_count) if archetype == "storage_depot" else 0,
        minimum=0,
        maximum=128,
    )
    stockpile_marker_count = _count(
        controls,
        "stockpile_count",
        "inventory_count",
        default=max(1, prop_count) if archetype == "stockpile" else 0,
        minimum=0,
        maximum=128,
    )
    input_buffer_marker_count = _count(
        controls,
        "input_buffer_count",
        "buffer_count",
        default=max(1, prop_count) if archetype == "input_buffer" else 0,
        minimum=0,
        maximum=128,
    )
    output_buffer_marker_count = _count(
        controls,
        "output_buffer_count",
        "buffer_count",
        default=max(1, prop_count) if archetype == "output_buffer" else 0,
        minimum=0,
        maximum=128,
    )
    processing_stage_marker_count = _count(
        controls,
        "processing_stage_count",
        "processing_count",
        "stage_count",
        default=max(1, prop_count) if archetype == "processing_stage" else 0,
        minimum=0,
        maximum=128,
    )
    refinery_stage_marker_count = _count(
        controls,
        "refinery_stage_count",
        "refinery_count",
        default=max(1, prop_count) if archetype == "refinery_stage" else 0,
        minimum=0,
        maximum=96,
    )
    workshop_stage_marker_count = _count(
        controls,
        "workshop_stage_count",
        "workshop_count",
        default=max(1, prop_count) if archetype == "workshop_stage" else 0,
        minimum=0,
        maximum=96,
    )
    assembly_stage_marker_count = _count(
        controls,
        "assembly_stage_count",
        "assembly_count",
        default=max(1, prop_count) if archetype == "assembly_stage" else 0,
        minimum=0,
        maximum=96,
    )
    market_node_marker_count = _count(
        controls,
        "market_node_count",
        "market_count",
        default=max(1, prop_count) if archetype == "market_node" else 0,
        minimum=0,
        maximum=96,
    )
    demand_sink_marker_count = _count(
        controls,
        "demand_sink_count",
        "demand_count",
        default=max(1, prop_count) if archetype == "demand_sink" else 0,
        minimum=0,
        maximum=96,
    )
    supply_route_marker_count = _count(
        controls,
        "supply_route_count",
        "route_count",
        default=max(1, prop_count) if archetype == "supply_route" else 0,
        minimum=0,
        maximum=128,
    )
    transport_leg_marker_count = _count(
        controls,
        "transport_leg_count",
        "transport_count",
        default=max(1, prop_count) if archetype == "transport_leg" else 0,
        minimum=0,
        maximum=128,
    )
    bottleneck_marker_count = _count(
        controls,
        "bottleneck_count",
        "constraint_count",
        default=max(1, prop_count) if archetype == "bottleneck" else 0,
        minimum=0,
        maximum=96,
    )
    throughput_rule_marker_count = _count(
        controls,
        "throughput_rule_count",
        "throughput_count",
        default=max(1, prop_count) if archetype == "throughput_rule" else 0,
        minimum=0,
        maximum=96,
    )
    failure_mode_marker_count = _count(
        controls,
        "failure_mode_count",
        "failure_count",
        default=max(1, prop_count) if archetype == "failure_mode" else 0,
        minimum=0,
        maximum=96,
    )
    production_strategy_marker_count = _count(
        controls,
        "production_strategy_count",
        "strategy_count",
        default=max(1, prop_count) if archetype == "production_strategy" else 0,
        minimum=0,
        maximum=96,
    )
    production_priority_marker_count = _count(
        controls,
        "production_priority_count",
        "priority_count",
        default=max(1, prop_count) if archetype == "production_priority" else 0,
        minimum=0,
        maximum=96,
    )
    quota_rule_marker_count = _count(
        controls,
        "quota_rule_count",
        "quota_count",
        default=max(1, prop_count) if archetype == "quota_rule" else 0,
        minimum=0,
        maximum=128,
    )
    allocation_rule_marker_count = _count(
        controls,
        "allocation_rule_count",
        "allocation_count",
        default=max(1, prop_count) if archetype == "allocation_rule" else 0,
        minimum=0,
        maximum=128,
    )
    rationing_policy_marker_count = _count(
        controls,
        "rationing_policy_count",
        "rationing_count",
        default=max(1, prop_count) if archetype == "rationing_policy" else 0,
        minimum=0,
        maximum=96,
    )
    strategic_reserve_marker_count = _count(
        controls,
        "strategic_reserve_count",
        "reserve_count",
        default=max(1, prop_count) if archetype == "strategic_reserve" else 0,
        minimum=0,
        maximum=96,
    )
    trade_embargo_marker_count = _count(
        controls,
        "trade_embargo_count",
        "embargo_count",
        default=max(1, prop_count) if archetype == "trade_embargo" else 0,
        minimum=0,
        maximum=96,
    )
    sabotage_target_marker_count = _count(
        controls,
        "sabotage_target_count",
        "sabotage_count",
        default=max(1, prop_count) if archetype == "sabotage_target" else 0,
        minimum=0,
        maximum=96,
    )
    maintenance_plan_marker_count = _count(
        controls,
        "maintenance_plan_count",
        "maintenance_count",
        default=max(1, prop_count) if archetype == "maintenance_plan" else 0,
        minimum=0,
        maximum=96,
    )
    repair_schedule_marker_count = _count(
        controls,
        "repair_schedule_count",
        "repair_count",
        default=max(1, prop_count) if archetype == "repair_schedule" else 0,
        minimum=0,
        maximum=96,
    )
    mobilization_order_marker_count = _count(
        controls,
        "mobilization_order_count",
        "mobilization_count",
        default=max(1, prop_count) if archetype == "mobilization_order" else 0,
        minimum=0,
        maximum=96,
    )
    production_mode_marker_count = _count(
        controls,
        "production_mode_count",
        "mode_count",
        default=max(1, prop_count) if archetype == "production_mode" else 0,
        minimum=0,
        maximum=96,
    )
    wartime_production_marker_count = _count(
        controls,
        "wartime_production_count",
        "wartime_count",
        default=max(1, prop_count) if archetype == "wartime_production" else 0,
        minimum=0,
        maximum=96,
    )
    peacetime_production_marker_count = _count(
        controls,
        "peacetime_production_count",
        "peacetime_count",
        default=max(1, prop_count) if archetype == "peacetime_production" else 0,
        minimum=0,
        maximum=96,
    )
    procurement_contract_marker_count = _count(
        controls,
        "procurement_contract_count",
        "procurement_count",
        "contract_count",
        default=max(1, prop_count) if archetype == "procurement_contract" else 0,
        minimum=0,
        maximum=96,
    )
    readiness_level_marker_count = _count(
        controls,
        "readiness_level_count",
        "readiness_count",
        default=max(1, prop_count) if archetype == "readiness_level" else 0,
        minimum=0,
        maximum=96,
    )
    conflict_system_marker_count = _count(
        controls,
        "conflict_system_count",
        "conflict_count",
        default=max(1, prop_count) if archetype == "conflict_system" else 0,
        minimum=0,
        maximum=96,
    )
    strategic_objective_marker_count = _count(
        controls,
        "strategic_objective_count",
        "objective_count",
        default=max(1, prop_count) if archetype == "strategic_objective" else 0,
        minimum=0,
        maximum=96,
    )
    war_plan_marker_count = _count(
        controls,
        "war_plan_count",
        default=max(1, prop_count) if archetype == "war_plan" else 0,
        minimum=0,
        maximum=96,
    )
    battlefront_marker_count = _count(
        controls,
        "battlefront_count",
        "front_count",
        default=max(1, prop_count) if archetype == "battlefront" else 0,
        minimum=0,
        maximum=128,
    )
    escalation_ladder_marker_count = _count(
        controls,
        "escalation_ladder_count",
        "escalation_count",
        default=max(1, prop_count) if archetype == "escalation_ladder" else 0,
        minimum=0,
        maximum=96,
    )
    treaty_marker_count = _count(
        controls,
        "treaty_count",
        default=max(1, prop_count) if archetype == "treaty" else 0,
        minimum=0,
        maximum=96,
    )
    ceasefire_marker_count = _count(
        controls,
        "ceasefire_count",
        default=max(1, prop_count) if archetype == "ceasefire" else 0,
        minimum=0,
        maximum=96,
    )
    alliance_marker_count = _count(
        controls,
        "alliance_count",
        default=max(1, prop_count) if archetype == "alliance" else 0,
        minimum=0,
        maximum=96,
    )
    rival_claim_marker_count = _count(
        controls,
        "rival_claim_count",
        default=max(1, prop_count) if archetype == "rival_claim" else 0,
        minimum=0,
        maximum=96,
    )
    diplomatic_demand_marker_count = _count(
        controls,
        "diplomatic_demand_count",
        default=max(1, prop_count) if archetype == "diplomatic_demand" else 0,
        minimum=0,
        maximum=96,
    )
    negotiation_channel_marker_count = _count(
        controls,
        "negotiation_channel_count",
        default=max(1, prop_count) if archetype == "negotiation_channel" else 0,
        minimum=0,
        maximum=96,
    )
    sanction_marker_count = _count(
        controls,
        "sanction_count",
        "sanctions_count",
        default=max(1, prop_count) if archetype == "sanction" else 0,
        minimum=0,
        maximum=96,
    )
    espionage_cell_marker_count = _count(
        controls,
        "espionage_cell_count",
        "espionage_count",
        default=max(1, prop_count) if archetype == "espionage_cell" else 0,
        minimum=0,
        maximum=96,
    )
    covert_operation_marker_count = _count(
        controls,
        "covert_operation_count",
        "covert_count",
        default=max(1, prop_count) if archetype == "covert_operation" else 0,
        minimum=0,
        maximum=96,
    )
    disaster_response_marker_count = _count(
        controls,
        "disaster_response_count",
        "disaster_count",
        default=max(1, prop_count) if archetype == "disaster_response" else 0,
        minimum=0,
        maximum=96,
    )
    emergency_order_marker_count = _count(
        controls,
        "emergency_order_count",
        "emergency_count",
        default=max(1, prop_count) if archetype == "emergency_order" else 0,
        minimum=0,
        maximum=96,
    )
    faction_ai_marker_count = _count(controls, "faction_ai_count", "ai_count", default=max(1, prop_count) if archetype == "faction_ai" else 0, minimum=0, maximum=96)
    doctrine_model_marker_count = _count(controls, "doctrine_model_count", "doctrine_count", default=max(1, prop_count) if archetype == "doctrine_model" else 0, minimum=0, maximum=96)
    goal_stack_marker_count = _count(controls, "goal_stack_count", "goal_count", default=max(1, prop_count) if archetype == "goal_stack" else 0, minimum=0, maximum=96)
    threat_model_marker_count = _count(controls, "threat_model_count", "threat_count", default=max(1, prop_count) if archetype == "threat_model" else 0, minimum=0, maximum=96)
    perception_feed_marker_count = _count(controls, "perception_feed_count", "perception_count", default=max(1, prop_count) if archetype == "perception_feed" else 0, minimum=0, maximum=96)
    decision_rule_marker_count = _count(controls, "decision_rule_count", "decision_count", default=max(1, prop_count) if archetype == "decision_rule" else 0, minimum=0, maximum=128)
    policy_selector_marker_count = _count(controls, "policy_selector_count", "selector_count", default=max(1, prop_count) if archetype == "policy_selector" else 0, minimum=0, maximum=96)
    action_option_marker_count = _count(controls, "action_option_count", "option_count", default=max(1, prop_count) if archetype == "action_option" else 0, minimum=0, maximum=128)
    response_plan_marker_count = _count(controls, "response_plan_count", "response_count", default=max(1, prop_count) if archetype == "response_plan" else 0, minimum=0, maximum=96)
    escalation_choice_marker_count = _count(controls, "escalation_choice_count", "escalation_count", default=max(1, prop_count) if archetype == "escalation_choice" else 0, minimum=0, maximum=96)
    deescalation_choice_marker_count = _count(controls, "deescalation_choice_count", "deescalation_count", default=max(1, prop_count) if archetype == "deescalation_choice" else 0, minimum=0, maximum=96)
    resource_strategy_marker_count = _count(controls, "resource_strategy_count", "resource_count", default=max(1, prop_count) if archetype == "resource_strategy" else 0, minimum=0, maximum=96)
    logistics_priority_marker_count = _count(controls, "logistics_priority_count", "logistics_count", default=max(1, prop_count) if archetype == "logistics_priority" else 0, minimum=0, maximum=96)
    diplomatic_posture_marker_count = _count(controls, "diplomatic_posture_count", "diplomacy_count", default=max(1, prop_count) if archetype == "diplomatic_posture" else 0, minimum=0, maximum=96)
    contingency_plan_marker_count = _count(controls, "contingency_plan_count", "contingency_count", default=max(1, prop_count) if archetype == "contingency_plan" else 0, minimum=0, maximum=96)
    adaptive_order_marker_count = _count(controls, "adaptive_order_count", "adaptive_count", default=max(1, prop_count) if archetype == "adaptive_order" else 0, minimum=0, maximum=96)
    operational_plan_marker_count = _count(controls, "operational_plan_count", "operational_count", default=max(1, prop_count) if archetype == "operational_plan" else 0, minimum=0, maximum=96)
    order_queue_marker_count = _count(controls, "order_queue_count", "queue_count", "order_count", default=max(1, prop_count) if archetype == "order_queue" else 0, minimum=0, maximum=96)
    world_order_marker_count = _count(controls, "world_order_count", "order_count", default=max(1, prop_count) if archetype == "world_order" else 0, minimum=0, maximum=128)
    patrol_order_marker_count = _count(controls, "patrol_order_count", default=max(1, prop_count) if archetype == "patrol_order" else 0, minimum=0, maximum=96)
    convoy_order_marker_count = _count(controls, "convoy_order_count", "convoy_count", default=max(1, prop_count) if archetype == "convoy_order" else 0, minimum=0, maximum=96)
    construction_order_marker_count = _count(controls, "construction_order_count", "construction_count", default=max(1, prop_count) if archetype == "construction_order" else 0, minimum=0, maximum=96)
    repair_order_marker_count = _count(controls, "repair_order_count", default=max(1, prop_count) if archetype == "repair_order" else 0, minimum=0, maximum=96)
    relief_order_marker_count = _count(controls, "relief_order_count", "relief_count", default=max(1, prop_count) if archetype == "relief_order" else 0, minimum=0, maximum=96)
    mission_order_marker_count = _count(controls, "mission_order_count", "mission_count", default=max(1, prop_count) if archetype == "mission_order" else 0, minimum=0, maximum=96)
    scheduled_action_marker_count = _count(controls, "scheduled_action_count", "schedule_count", default=max(1, prop_count) if archetype == "scheduled_action" else 0, minimum=0, maximum=128)
    task_assignment_marker_count = _count(controls, "task_assignment_count", "assignment_count", default=max(1, prop_count) if archetype == "task_assignment" else 0, minimum=0, maximum=128)
    crew_roster_marker_count = _count(controls, "crew_roster_count", "crew_count", default=max(1, prop_count) if archetype == "crew_roster" else 0, minimum=0, maximum=96)
    convoy_route_marker_count = _count(controls, "convoy_route_count", default=max(1, prop_count) if archetype == "convoy_route" else 0, minimum=0, maximum=128)
    construction_queue_marker_count = _count(controls, "construction_queue_count", default=max(1, prop_count) if archetype == "construction_queue" else 0, minimum=0, maximum=96)
    repair_crew_marker_count = _count(controls, "repair_crew_count", default=max(1, prop_count) if archetype == "repair_crew" else 0, minimum=0, maximum=96)
    relief_team_marker_count = _count(controls, "relief_team_count", "team_count", default=max(1, prop_count) if archetype == "relief_team" else 0, minimum=0, maximum=96)
    settlement_evolution_marker_count = _count(controls, "settlement_evolution_count", "evolution_count", default=max(1, prop_count) if archetype == "settlement_evolution" else 0, minimum=0, maximum=96)
    growth_phase_marker_count = _count(controls, "growth_phase_count", "growth_count", "phase_count", default=max(1, prop_count) if archetype == "growth_phase" else 0, minimum=0, maximum=128)
    expansion_zone_marker_count = _count(controls, "expansion_zone_count", "expansion_count", "zone_count", default=max(1, prop_count) if archetype == "expansion_zone" else 0, minimum=0, maximum=96)
    construction_stage_marker_count = _count(controls, "construction_stage_count", "stage_count", default=max(1, prop_count) if archetype == "construction_stage" else 0, minimum=0, maximum=128)
    upgrade_plan_marker_count = _count(controls, "upgrade_plan_count", "upgrade_count", default=max(1, prop_count) if archetype == "upgrade_plan" else 0, minimum=0, maximum=96)
    district_upgrade_marker_count = _count(controls, "district_upgrade_count", default=max(1, prop_count) if archetype == "district_upgrade" else 0, minimum=0, maximum=96)
    building_upgrade_marker_count = _count(controls, "building_upgrade_count", default=max(1, prop_count) if archetype == "building_upgrade" else 0, minimum=0, maximum=96)
    infrastructure_upgrade_marker_count = _count(controls, "infrastructure_upgrade_count", default=max(1, prop_count) if archetype == "infrastructure_upgrade" else 0, minimum=0, maximum=96)
    material_delivery_marker_count = _count(controls, "material_delivery_count", "delivery_count", default=max(1, prop_count) if archetype == "material_delivery" else 0, minimum=0, maximum=128)
    staffing_plan_marker_count = _count(controls, "staffing_plan_count", "staffing_count", default=max(1, prop_count) if archetype == "staffing_plan" else 0, minimum=0, maximum=96)
    occupancy_plan_marker_count = _count(controls, "occupancy_plan_count", "occupancy_count", default=max(1, prop_count) if archetype == "occupancy_plan" else 0, minimum=0, maximum=96)
    worksite_marker_count = _count(controls, "worksite_count", default=max(1, prop_count) if archetype == "worksite" else 0, minimum=0, maximum=96)
    build_permit_marker_count = _count(controls, "build_permit_count", "permit_count", default=max(1, prop_count) if archetype == "build_permit" else 0, minimum=0, maximum=96)
    damage_repair_plan_marker_count = _count(controls, "damage_repair_plan_count", default=max(1, prop_count) if archetype == "damage_repair_plan" else 0, minimum=0, maximum=96)
    demolition_plan_marker_count = _count(controls, "demolition_plan_count", "demolition_count", default=max(1, prop_count) if archetype == "demolition_plan" else 0, minimum=0, maximum=96)
    renovation_project_marker_count = _count(controls, "renovation_project_count", "renovation_count", default=max(1, prop_count) if archetype == "renovation_project" else 0, minimum=0, maximum=96)
    city_plan_marker_count = _count(controls, "city_plan_count", "city_planning_count", default=max(1, prop_count) if archetype == "city_plan" else 0, minimum=0, maximum=96)
    zoning_rule_marker_count = _count(controls, "zoning_rule_count", "zoning_count", default=max(1, prop_count) if archetype == "zoning_rule" else 0, minimum=0, maximum=128)
    zoning_district_marker_count = _count(controls, "zoning_district_count", "zoning_count", default=max(1, prop_count) if archetype == "zoning_district" else 0, minimum=0, maximum=96)
    parcel_grid_marker_count = _count(controls, "parcel_grid_count", default=max(1, prop_count) if archetype == "parcel_grid" else 0, minimum=0, maximum=96)
    land_parcel_marker_count = _count(controls, "land_parcel_count", "parcel_count", "lot_count", default=max(1, prop_count) if archetype == "land_parcel" else 0, minimum=0, maximum=160)
    parcel_subdivision_marker_count = _count(controls, "parcel_subdivision_count", "subdivision_count", default=max(1, prop_count) if archetype == "parcel_subdivision" else 0, minimum=0, maximum=96)
    block_plan_marker_count = _count(controls, "block_plan_count", "block_count", default=max(1, prop_count) if archetype == "block_plan" else 0, minimum=0, maximum=96)
    street_hierarchy_marker_count = _count(controls, "street_hierarchy_count", "street_count", "road_count", default=max(1, prop_count) if archetype == "street_hierarchy" else 0, minimum=0, maximum=128)
    transit_node_marker_count = _count(controls, "transit_node_count", "transit_count", default=max(1, prop_count) if archetype == "transit_node" else 0, minimum=0, maximum=96)
    civic_service_plan_marker_count = _count(controls, "civic_service_plan_count", "service_plan_count", "civic_count", default=max(1, prop_count) if archetype == "civic_service_plan" else 0, minimum=0, maximum=96)
    service_coverage_marker_count = _count(controls, "service_coverage_count", "coverage_count", default=max(1, prop_count) if archetype == "service_coverage" else 0, minimum=0, maximum=128)
    utility_corridor_marker_count = _count(controls, "utility_corridor_count", "corridor_count", "utility_count", default=max(1, prop_count) if archetype == "utility_corridor" else 0, minimum=0, maximum=128)
    district_site_plan_marker_count = _count(controls, "district_site_plan_count", "district_site_count", default=max(1, prop_count) if archetype == "district_site_plan" else 0, minimum=0, maximum=32)
    street_crossing_marker_count = _count(controls, "street_crossing_count", "crossing_count", default=max(1, prop_count) if archetype == "street_crossing" else 0, minimum=0, maximum=96)
    perimeter_plan_marker_count = _count(controls, "perimeter_plan_count", default=max(1, prop_count) if archetype == "perimeter_plan" else 0, minimum=0, maximum=32)
    security_gate_marker_count = _count(controls, "security_gate_count", "gate_count", default=max(1, prop_count) if archetype == "security_gate" else 0, minimum=0, maximum=64)
    landscape_zone_marker_count = _count(controls, "landscape_zone_count", "landscape_count", "green_count", default=max(1, prop_count) if archetype == "landscape_zone" else 0, minimum=0, maximum=96)
    traffic_flow_marker_count = _count(controls, "traffic_flow_count", "traffic_count", default=max(1, prop_count) if archetype == "traffic_flow" else 0, minimum=0, maximum=96)
    service_flow_marker_count = _count(controls, "service_flow_count", "service_route_count", "utility_route_count", default=max(1, prop_count) if archetype == "service_flow" else 0, minimum=0, maximum=96)
    power_grid_marker_count = _count(controls, "power_grid_count", "power_count", "grid_count", default=max(1, prop_count) if archetype == "power_grid" else 0, minimum=0, maximum=96)
    substation_marker_count = _count(controls, "substation_count", "power_node_count", default=max(1, prop_count) if archetype == "substation" else 0, minimum=0, maximum=96)
    transformer_bank_marker_count = _count(controls, "transformer_bank_count", "transformer_count", default=max(1, prop_count) if archetype == "transformer_bank" else 0, minimum=0, maximum=96)
    power_line_marker_count = _count(controls, "power_line_count", "line_count", default=max(1, prop_count) if archetype == "power_line" else 0, minimum=0, maximum=128)
    water_network_marker_count = _count(controls, "water_network_count", "water_count", default=max(1, prop_count) if archetype == "water_network" else 0, minimum=0, maximum=96)
    pump_station_marker_count = _count(controls, "pump_station_count", "pump_count", default=max(1, prop_count) if archetype == "pump_station" else 0, minimum=0, maximum=96)
    water_tower_marker_count = _count(controls, "water_tower_count", "storage_count", default=max(1, prop_count) if archetype == "water_tower" else 0, minimum=0, maximum=96)
    sewer_network_marker_count = _count(controls, "sewer_network_count", "sewer_count", "drain_count", default=max(1, prop_count) if archetype == "sewer_network" else 0, minimum=0, maximum=96)
    treatment_plant_marker_count = _count(controls, "treatment_plant_count", "treatment_count", "plant_count", default=max(1, prop_count) if archetype == "treatment_plant" else 0, minimum=0, maximum=96)
    data_network_marker_count = _count(controls, "data_network_count", "data_count", default=max(1, prop_count) if archetype == "data_network" else 0, minimum=0, maximum=96)
    data_hub_marker_count = _count(controls, "data_hub_count", "hub_count", default=max(1, prop_count) if archetype == "data_hub" else 0, minimum=0, maximum=96)
    fiber_line_marker_count = _count(controls, "fiber_line_count", "fiber_count", default=max(1, prop_count) if archetype == "fiber_line" else 0, minimum=0, maximum=128)
    transit_line_marker_count = _count(controls, "transit_line_count", "transit_count", "line_count", default=max(1, prop_count) if archetype == "transit_line" else 0, minimum=0, maximum=96)
    transit_station_marker_count = _count(controls, "transit_station_count", "station_count", "transit_node_count", default=max(1, prop_count) if archetype == "transit_station" else 0, minimum=0, maximum=128)
    service_connection_marker_count = _count(controls, "service_connection_count", "connection_count", "service_tap_count", default=max(1, prop_count) if archetype == "service_connection" else 0, minimum=0, maximum=160)
    maintenance_access_marker_count = _count(controls, "maintenance_access_count", "access_count", "walkway_count", default=max(1, prop_count) if archetype == "maintenance_access" else 0, minimum=0, maximum=128)
    building_service_plan_marker_count = _count(controls, "building_service_plan_count", "building_service_count", default=max(1, prop_count) if archetype == "building_service_plan" else 0, minimum=0, maximum=96)
    service_core_marker_count = _count(controls, "service_core_count", "core_count", default=max(1, prop_count) if archetype == "service_core" else 0, minimum=0, maximum=96)
    utility_room_marker_count = _count(controls, "utility_room_count", default=max(1, prop_count) if archetype == "utility_room" else 0, minimum=0, maximum=96)
    mechanical_room_marker_count = _count(controls, "mechanical_room_count", "mechanical_count", default=max(1, prop_count) if archetype == "mechanical_room" else 0, minimum=0, maximum=96)
    electrical_panel_marker_count = _count(controls, "electrical_panel_count", "panel_count", "circuit_count", default=max(1, prop_count) if archetype == "electrical_panel" else 0, minimum=0, maximum=128)
    meter_bank_marker_count = _count(controls, "meter_bank_count", "meter_count", default=max(1, prop_count) if archetype == "meter_bank" else 0, minimum=0, maximum=96)
    plumbing_stack_marker_count = _count(controls, "plumbing_stack_count", "riser_count", "pipe_count", default=max(1, prop_count) if archetype == "plumbing_stack" else 0, minimum=0, maximum=128)
    hvac_system_marker_count = _count(controls, "hvac_system_count", "hvac_count", default=max(1, prop_count) if archetype == "hvac_system" else 0, minimum=0, maximum=96)
    ventilation_duct_marker_count = _count(controls, "ventilation_duct_count", "duct_count", default=max(1, prop_count) if archetype == "ventilation_duct" else 0, minimum=0, maximum=128)
    elevator_core_marker_count = _count(controls, "elevator_core_count", "elevator_count", default=max(1, prop_count) if archetype == "elevator_core" else 0, minimum=0, maximum=96)
    service_elevator_marker_count = _count(controls, "service_elevator_count", "elevator_count", "lift_count", default=max(1, prop_count) if archetype == "service_elevator" else 0, minimum=0, maximum=96)
    service_shaft_marker_count = _count(controls, "service_shaft_count", "shaft_count", default=max(1, prop_count) if archetype == "service_shaft" else 0, minimum=0, maximum=96)
    fire_suppression_marker_count = _count(controls, "fire_suppression_count", "sprinkler_zone_count", default=max(1, prop_count) if archetype == "fire_suppression" else 0, minimum=0, maximum=96)
    sprinkler_zone_marker_count = _count(controls, "sprinkler_zone_count", "sprinkler_count", default=max(1, prop_count) if archetype == "sprinkler_zone" else 0, minimum=0, maximum=128)
    waste_chute_marker_count = _count(controls, "waste_chute_count", "chute_count", default=max(1, prop_count) if archetype == "waste_chute" else 0, minimum=0, maximum=96)
    loading_dock_marker_count = _count(controls, "loading_dock_count", "dock_count", "dock_bay_count", default=max(1, prop_count) if archetype == "loading_dock" else 0, minimum=0, maximum=96)
    site_compound_marker_count = _count(controls, "site_compound_count", default=max(1, prop_count) if archetype == "site_compound" else 0, minimum=0, maximum=16)
    building_lot_marker_count = _count(controls, "building_lot_count", "site_building_count", default=max(1, structure_count) if archetype == "building_lot" else 0, minimum=0, maximum=64)
    courtyard_plan_marker_count = _count(controls, "courtyard_plan_count", "courtyard_count", default=max(1, prop_count) if archetype == "courtyard_plan" else 0, minimum=0, maximum=32)
    pedestrian_path_marker_count = _count(controls, "pedestrian_path_count", "site_route_count", "walkway_count", default=max(1, access_count) if archetype == "pedestrian_path" else 0, minimum=0, maximum=96)
    service_alley_marker_count = _count(controls, "service_alley_count", "alley_count", default=max(1, infrastructure_count) if archetype == "service_alley" else 0, minimum=0, maximum=64)
    parking_zone_marker_count = _count(controls, "parking_zone_count", "parking_count", default=max(1, prop_count) if archetype == "parking_zone" else 0, minimum=0, maximum=32)
    parking_bay_marker_count = _count(controls, "parking_bay_count", "parking_bays", default=0, minimum=0, maximum=160)
    loading_zone_marker_count = _count(controls, "loading_zone_count", "loading_count", default=max(1, prop_count) if archetype == "loading_zone" else 0, minimum=0, maximum=32)
    exterior_utility_marker_count = _count(controls, "exterior_utility_count", "utility_count", default=max(1, infrastructure_count) if archetype == "exterior_utility" else 0, minimum=0, maximum=64)
    room_program_marker_count = _count(controls, "room_program_count", "functional_room_count", default=max(1, prop_count) if archetype == "room_program" else 0, minimum=0, maximum=96)
    bathroom_marker_count = _count(controls, "bathroom_count", "wet_room_count", default=max(1, prop_count) if archetype == "bathroom" else 0, minimum=0, maximum=96)
    kitchen_marker_count = _count(controls, "kitchen_count", "galley_count", default=max(1, prop_count) if archetype == "kitchen" else 0, minimum=0, maximum=96)
    lab_room_marker_count = _count(controls, "lab_room_count", "lab_count", default=max(1, prop_count) if archetype == "lab_room" else 0, minimum=0, maximum=96)
    med_bay_marker_count = _count(controls, "med_bay_count", "medical_bay_count", default=max(1, prop_count) if archetype == "med_bay" else 0, minimum=0, maximum=96)
    workshop_room_marker_count = _count(controls, "workshop_room_count", "workshop_count", default=max(1, prop_count) if archetype == "workshop_room" else 0, minimum=0, maximum=96)
    control_room_marker_count = _count(controls, "control_room_count", "operations_room_count", default=max(1, prop_count) if archetype == "control_room" else 0, minimum=0, maximum=96)
    storage_room_marker_count = _count(controls, "storage_room_count", default=max(1, prop_count) if archetype == "storage_room" else 0, minimum=0, maximum=96)
    office_room_marker_count = _count(controls, "office_room_count", "office_count", default=max(1, prop_count) if archetype == "office_room" else 0, minimum=0, maximum=96)
    bedroom_marker_count = _count(controls, "bedroom_count", "sleeping_room_count", default=max(1, prop_count) if archetype == "bedroom" else 0, minimum=0, maximum=96)
    fixture_cluster_marker_count = _count(controls, "fixture_cluster_count", "fixture_count", default=max(1, prop_count) if archetype == "fixture_cluster" else 0, minimum=0, maximum=128)
    appliance_bank_marker_count = _count(controls, "appliance_bank_count", "appliance_count", default=max(1, prop_count) if archetype == "appliance_bank" else 0, minimum=0, maximum=128)
    workstation_cluster_marker_count = _count(controls, "workstation_cluster_count", "workstation_count", default=max(1, prop_count) if archetype == "workstation_cluster" else 0, minimum=0, maximum=128)
    cabinet_wall_marker_count = _count(controls, "cabinet_wall_count", "cabinet_count", default=max(1, prop_count) if archetype == "cabinet_wall" else 0, minimum=0, maximum=128)
    counter_run_marker_count = _count(controls, "counter_run_count", "counter_count", default=max(1, prop_count) if archetype == "counter_run" else 0, minimum=0, maximum=128)
    sanitary_fixture_marker_count = _count(controls, "sanitary_fixture_count", "fixture_count", "sink_count", default=max(1, prop_count) if archetype == "sanitary_fixture" else 0, minimum=0, maximum=128)
    lab_bench_marker_count = _count(controls, "lab_bench_count", "bench_count", "counter_count", default=max(1, prop_count) if archetype == "lab_bench" else 0, minimum=0, maximum=128)
    medical_bed_marker_count = _count(controls, "medical_bed_count", "bed_count", default=max(1, prop_count) if archetype == "medical_bed" else 0, minimum=0, maximum=128)
    tool_rack_marker_count = _count(controls, "tool_rack_count", "rack_count", "tool_count", default=max(1, prop_count) if archetype == "tool_rack" else 0, minimum=0, maximum=128)
    room_adjacency_marker_count = _count(controls, "room_adjacency_count", "adjacency_pair_count", default=max(1, prop_count) if archetype == "room_adjacency" else 0, minimum=0, maximum=96)
    room_connection_marker_count = _count(controls, "room_connection_count", "connection_count", default=max(1, prop_count) if archetype == "room_connection" else 0, minimum=0, maximum=128)
    door_opening_marker_count = _count(controls, "door_opening_count", "opening_count", "door_count", default=max(1, prop_count) if archetype == "door_opening" else 0, minimum=0, maximum=128)
    corridor_link_marker_count = _count(controls, "corridor_link_count", "corridor_count", "route_count", default=max(1, prop_count) if archetype == "corridor_link" else 0, minimum=0, maximum=128)
    wall_run_marker_count = _count(controls, "wall_run_count", "wall_count", "partition_count", default=max(1, prop_count) if archetype == "wall_run" else 0, minimum=0, maximum=128)
    room_socket_marker_count = _count(controls, "room_socket_count", "socket_count", default=max(1, prop_count) if archetype == "room_socket" else 0, minimum=0, maximum=128)
    fixture_socket_marker_count = _count(controls, "fixture_socket_count", "socket_count", "fixture_count", default=max(1, prop_count) if archetype == "fixture_socket" else 0, minimum=0, maximum=128)
    socket_binding_marker_count = _count(controls, "socket_binding_count", "binding_count", default=max(1, prop_count) if archetype == "socket_binding" else 0, minimum=0, maximum=128)
    fixture_placement_marker_count = _count(controls, "fixture_placement_count", "fixture_count", "placement_count", default=max(1, prop_count) if archetype == "fixture_placement" else 0, minimum=0, maximum=128)
    furniture_placement_marker_count = _count(controls, "furniture_placement_count", "furniture_count", "placement_count", default=max(1, prop_count) if archetype == "furniture_placement" else 0, minimum=0, maximum=128)
    service_placement_marker_count = _count(controls, "service_placement_count", "service_connection_count", "placement_count", default=max(1, prop_count) if archetype == "service_placement" else 0, minimum=0, maximum=128)
    wall_attachment_marker_count = _count(controls, "wall_attachment_count", "attach_count", default=max(1, prop_count) if archetype == "wall_attachment" else 0, minimum=0, maximum=128)
    anchor_rule_marker_count = _count(controls, "anchor_rule_count", "anchor_count", default=max(1, prop_count) if archetype == "anchor_rule" else 0, minimum=0, maximum=128)
    placement_constraint_marker_count = _count(controls, "placement_constraint_count", "constraint_count", default=max(1, prop_count) if archetype == "placement_constraint" else 0, minimum=0, maximum=128)
    auto_layout_marker_count = _count(controls, "auto_layout_count", default=max(1, prop_count) if archetype == "auto_layout" else 0, minimum=0, maximum=96)
    room_layout_plan_marker_count = _count(controls, "room_layout_plan_count", "room_layout_count", default=max(1, prop_count) if archetype == "room_layout_plan" else 0, minimum=0, maximum=96)
    fixture_layout_marker_count = _count(controls, "fixture_layout_count", default=max(1, prop_count) if archetype == "fixture_layout" else 0, minimum=0, maximum=128)
    furniture_layout_marker_count = _count(controls, "furniture_layout_count", default=max(1, prop_count) if archetype == "furniture_layout" else 0, minimum=0, maximum=128)
    service_layout_marker_count = _count(controls, "service_layout_count", default=max(1, prop_count) if archetype == "service_layout" else 0, minimum=0, maximum=128)
    wall_fixture_layout_marker_count = _count(controls, "wall_fixture_layout_count", "wall_layout_count", default=max(1, prop_count) if archetype == "wall_fixture_layout" else 0, minimum=0, maximum=128)
    layout_zone_marker_count = _count(controls, "layout_zone_count", "zone_count", default=0, minimum=0, maximum=128)
    layout_socket_marker_count = _count(controls, "layout_socket_count", "socket_count", default=0, minimum=0, maximum=192)
    auto_placed_marker_count = _count(controls, "auto_placed_count", "placement_count", default=0, minimum=0, maximum=192)
    layout_solver_marker_count = _count(controls, "layout_solver_count", default=max(1, prop_count) if archetype == "layout_solver" else 0, minimum=0, maximum=96)
    room_bounds_marker_count = _count(controls, "room_bounds_count", "bounds_count", default=max(1, prop_count) if archetype == "room_bounds" else 0, minimum=0, maximum=96)
    wall_side_rule_marker_count = _count(controls, "wall_side_rule_count", "wall_rule_count", default=max(1, prop_count) if archetype == "wall_side_rule" else 0, minimum=0, maximum=96)
    socket_priority_marker_count = _count(controls, "socket_priority_count", "priority_count", default=max(1, prop_count) if archetype == "socket_priority" else 0, minimum=0, maximum=128)
    clearance_zone_marker_count = _count(controls, "clearance_zone_count", "clearance_count", default=max(1, prop_count) if archetype == "clearance_zone" else 0, minimum=0, maximum=128)
    layout_slot_marker_count = _count(controls, "layout_slot_count", "slot_count", default=max(1, prop_count) if archetype == "layout_slot" else 0, minimum=0, maximum=192)
    resolved_slot_marker_count = _count(controls, "resolved_slot_count", default=0, minimum=0, maximum=192)
    blocked_slot_marker_count = _count(controls, "blocked_slot_count", default=0, minimum=0, maximum=128)
    priority_socket_marker_count = _count(controls, "priority_socket_count", default=0, minimum=0, maximum=128)
    footprint_packer_marker_count = _count(controls, "footprint_packer_count", default=max(1, prop_count) if archetype == "footprint_packer" else 0, minimum=0, maximum=96)
    placement_footprint_marker_count = _count(controls, "placement_footprint_count", "footprint_count", default=max(1, prop_count) if archetype == "placement_footprint" else 0, minimum=0, maximum=160)
    occupancy_grid_marker_count = _count(controls, "occupancy_grid_count", "grid_count", default=max(1, prop_count) if archetype == "occupancy_grid" else 0, minimum=0, maximum=96)
    fit_profile_marker_count = _count(controls, "fit_profile_count", "fit_count", default=max(1, prop_count) if archetype == "fit_profile" else 0, minimum=0, maximum=128)
    collision_rule_marker_count = _count(controls, "collision_rule_count", "collision_count", default=max(1, prop_count) if archetype == "collision_rule" else 0, minimum=0, maximum=128)
    service_reach_marker_count = _count(controls, "service_reach_count", "service_count", default=max(1, prop_count) if archetype == "service_reach" else 0, minimum=0, maximum=128)
    occupied_cell_marker_count = _count(controls, "occupied_cell_count", "blocked_cell_count", default=0, minimum=0, maximum=192)
    free_cell_marker_count = _count(controls, "free_cell_count", "available_cell_count", default=0, minimum=0, maximum=192)
    packed_item_marker_count = _count(controls, "packed_item_count", "packed_count", default=0, minimum=0, maximum=192)
    collision_pair_marker_count = _count(controls, "collision_pair_count", default=0, minimum=0, maximum=128)
    room_packing_solver_marker_count = _count(controls, "room_packing_solver_count", default=max(1, prop_count) if archetype == "room_packing_solver" else 0, minimum=0, maximum=96)
    packing_slot_marker_count = _count(controls, "packing_slot_count", default=max(1, prop_count) if archetype == "packing_slot" else 0, minimum=0, maximum=192)
    packed_transform_marker_count = _count(controls, "packed_transform_count", "resolved_transform_count", default=max(1, prop_count) if archetype == "packed_transform" else 0, minimum=0, maximum=192)
    clearance_reservation_marker_count = _count(controls, "clearance_reservation_count", default=max(1, prop_count) if archetype == "clearance_reservation" else 0, minimum=0, maximum=128)
    service_anchor_map_marker_count = _count(controls, "service_anchor_map_count", default=max(1, prop_count) if archetype == "service_anchor_map" else 0, minimum=0, maximum=96)
    service_anchor_marker_count = _count(controls, "service_anchor_count", default=0, minimum=0, maximum=128)
    room_content_plan_marker_count = _count(controls, "room_content_plan_count", default=max(1, prop_count) if archetype == "room_content_plan" else 0, minimum=0, maximum=96)
    content_family_binding_marker_count = _count(controls, "content_family_binding_count", default=max(1, prop_count) if archetype == "content_family_binding" else 0, minimum=0, maximum=128)
    furniture_asset_marker_count = _count(controls, "furniture_asset_count", default=max(1, prop_count) if archetype == "furniture_asset" else 0, minimum=0, maximum=128)
    fixture_asset_marker_count = _count(controls, "fixture_asset_count", default=max(1, prop_count) if archetype == "fixture_asset" else 0, minimum=0, maximum=128)
    packed_child_asset_marker_count = _count(controls, "packed_child_asset_count", "generated_child_asset_count", default=max(1, prop_count) if archetype == "packed_child_asset" else 0, minimum=0, maximum=192)
    content_surface_plan_marker_count = _count(controls, "content_surface_plan_count", default=max(1, prop_count) if archetype == "content_surface_plan" else 0, minimum=0, maximum=96)
    content_material_zone_marker_count = _count(controls, "content_material_zone_count", "content_surface_zone_count", default=max(1, prop_count) if archetype == "content_material_zone" else 0, minimum=0, maximum=160)
    content_finish_preset_marker_count = _count(controls, "content_finish_preset_count", default=max(1, prop_count) if archetype == "content_finish_preset" else 0, minimum=0, maximum=96)
    content_wear_profile_marker_count = _count(controls, "content_wear_profile_count", default=max(1, prop_count) if archetype == "content_wear_profile" else 0, minimum=0, maximum=128)
    content_marking_set_marker_count = _count(controls, "content_marking_set_count", "content_decal_count", default=max(1, prop_count) if archetype == "content_marking_set" else 0, minimum=0, maximum=128)
    room_pack_preset_marker_count = _count(controls, "room_pack_preset_count", default=max(1, prop_count) if archetype == "room_pack_preset" else 0, minimum=0, maximum=96)
    footprint_size_preset_marker_count = _count(controls, "footprint_size_preset_count", default=max(1, prop_count) if archetype == "footprint_size_preset" else 0, minimum=0, maximum=96)
    packing_policy_preset_marker_count = _count(controls, "packing_policy_preset_count", default=max(1, prop_count) if archetype == "packing_policy_preset" else 0, minimum=0, maximum=96)
    clearance_preset_marker_count = _count(controls, "clearance_preset_count", default=max(1, prop_count) if archetype == "clearance_preset" else 0, minimum=0, maximum=96)
    service_reach_preset_marker_count = _count(controls, "service_reach_preset_count", default=max(1, prop_count) if archetype == "service_reach_preset" else 0, minimum=0, maximum=96)
    role_item_set_marker_count = _count(controls, "role_item_set_count", default=max(1, prop_count) if archetype == "role_item_set" else 0, minimum=0, maximum=96)
    preset_item_marker_count = _count(controls, "preset_item_count", default=0, minimum=0, maximum=192)
    role_preset_marker_count = _count(controls, "role_preset_count", default=0, minimum=0, maximum=96)
    policy_rule_marker_count = _count(controls, "policy_rule_count", default=0, minimum=0, maximum=128)
    public_space_plan_marker_count = _count(controls, "public_space_plan_count", "public_space_count", "park_count", default=max(1, prop_count) if archetype == "public_space_plan" else 0, minimum=0, maximum=96)
    growth_boundary_marker_count = _count(controls, "growth_boundary_count", "boundary_count", default=max(1, prop_count) if archetype == "growth_boundary" else 0, minimum=0, maximum=96)
    district_dependency_marker_count = _count(controls, "district_dependency_count", "dependency_count", default=max(1, prop_count) if archetype == "district_dependency" else 0, minimum=0, maximum=128)
    development_pressure_marker_count = _count(controls, "development_pressure_count", "pressure_count", default=max(1, prop_count) if archetype == "development_pressure" else 0, minimum=0, maximum=128)
    climate_zone_marker_count = _count(controls, "climate_zone_count", "climate_count", default=max(1, prop_count) if archetype == "climate_zone" else 0, minimum=0, maximum=96)
    climate_risk_map_marker_count = _count(controls, "climate_risk_map_count", "risk_map_count", default=max(1, prop_count) if archetype == "climate_risk_map" else 0, minimum=0, maximum=96)
    flood_risk_marker_count = _count(controls, "flood_risk_count", "flood_count", default=max(1, prop_count) if archetype == "flood_risk" else 0, minimum=0, maximum=96)
    fire_risk_marker_count = _count(controls, "fire_risk_count", "fire_count", default=max(1, prop_count) if archetype == "fire_risk" else 0, minimum=0, maximum=96)
    heat_risk_marker_count = _count(controls, "heat_risk_count", "heat_count", default=max(1, prop_count) if archetype == "heat_risk" else 0, minimum=0, maximum=96)
    resource_constraint_marker_count = _count(controls, "resource_constraint_count", "constraint_count", default=max(1, prop_count) if archetype == "resource_constraint" else 0, minimum=0, maximum=128)
    protected_land_marker_count = _count(controls, "protected_land_count", "protected_count", default=max(1, prop_count) if archetype == "protected_land" else 0, minimum=0, maximum=96)
    green_infrastructure_marker_count = _count(controls, "green_infrastructure_count", "green_count", default=max(1, prop_count) if archetype == "green_infrastructure" else 0, minimum=0, maximum=96)
    stormwater_system_marker_count = _count(controls, "stormwater_system_count", "stormwater_count", default=max(1, prop_count) if archetype == "stormwater_system" else 0, minimum=0, maximum=96)
    cooling_corridor_marker_count = _count(controls, "cooling_corridor_count", "cooling_count", default=max(1, prop_count) if archetype == "cooling_corridor" else 0, minimum=0, maximum=96)
    evacuation_route_marker_count = _count(controls, "evacuation_route_count", "evacuation_count", default=max(1, prop_count) if archetype == "evacuation_route" else 0, minimum=0, maximum=128)
    emergency_shelter_marker_count = _count(controls, "emergency_shelter_count", "shelter_count", default=max(1, prop_count) if archetype == "emergency_shelter" else 0, minimum=0, maximum=96)
    resilience_plan_marker_count = _count(controls, "resilience_plan_count", "resilience_count", default=max(1, prop_count) if archetype == "resilience_plan" else 0, minimum=0, maximum=96)
    climate_adaptation_marker_count = _count(controls, "climate_adaptation_count", "adaptation_count", default=max(1, prop_count) if archetype == "climate_adaptation" else 0, minimum=0, maximum=96)
    transit_oriented_growth_marker_count = _count(controls, "transit_oriented_growth_count", "transit_growth_count", default=max(1, prop_count) if archetype == "transit_oriented_growth" else 0, minimum=0, maximum=96)
    risk_mitigation_marker_count = _count(controls, "risk_mitigation_count", "mitigation_count", default=max(1, prop_count) if archetype == "risk_mitigation" else 0, minimum=0, maximum=128)
    perimeter_count = _count(controls, "perimeter_count", "fence_count", "wall_count", default=4 if archetype in {"outpost", "fortress"} else 0, minimum=0, maximum=16)
    gate_count = _count(controls, "gate_count", "gates", default=1 if perimeter_count else 0, minimum=0, maximum=6)
    tower_count = _count(controls, "tower_count", "towers", default=2 if archetype in {"outpost", "fortress", "temple"} else 0, minimum=0, maximum=8)
    dock_count = _count(controls, "dock_count", "pier_count", "piers", default=3 if archetype == "harbor" else 0, minimum=0, maximum=8)
    vehicle_count = _count(controls, "vehicle_count", "vehicles", default=1 if archetype in {"outpost", "hangar"} else 0, minimum=0, maximum=6)
    boat_count = _count(controls, "boat_count", "boats", default=3 if archetype == "harbor" else 0, minimum=0, maximum=8)
    machine_count = _count(controls, "machine_count", "machines", default=3 if archetype == "factory" else 0, minimum=0, maximum=8)
    conveyor_count = _count(controls, "conveyor_count", "conveyors", default=2 if archetype == "factory" else 0, minimum=0, maximum=8)
    interior_count = _count(controls, "interior_module_count", "interior_count", "room_count", default=1 if archetype in {"fortress", "temple"} else 0, minimum=0, maximum=8)
    furniture_count = _count(controls, "furniture_cluster_count", "furniture_count", default=2 if archetype == "market" else 0, minimum=0, maximum=12)
    foliage_count = _count(controls, "foliage_cluster_count", "foliage_count", default=2 if archetype == "temple" else 0, minimum=0, maximum=10)
    child_socket_count = _count(controls, "child_socket_count", "module_socket_count", default=max(1, vehicle_count + boat_count + machine_count + interior_count), minimum=0, maximum=16)
    apron_count = _count(controls, "apron_count", "runway_count", default=1 if archetype == "hangar" else 0, minimum=0, maximum=4)
    column_count = _count(controls, "column_count", "columns", default=8 if archetype == "temple" else 0, minimum=0, maximum=24)
    raw_child_module_layout = asset_graph.authoring.get("child_module_layout", {})
    child_module_layout = raw_child_module_layout if isinstance(raw_child_module_layout, dict) else {}
    child_module_slots = [
        dict(slot)
        for slot in child_module_layout.get("slots", [])
        if isinstance(slot, dict)
    ]
    child_slots_by_kind: dict[str, list[dict[str, Any]]] = {}
    for slot in child_module_slots:
        child_slots_by_kind.setdefault(str(slot.get("kind") or "generic"), []).append(slot)
    width = scale * _level(controls, "width_scale", "setpiece_width", default=2.20)
    depth = scale * _level(controls, "depth_scale", "setpiece_depth", default=1.75)
    height = scale * _level(controls, "height_scale", "setpiece_height", default=0.86)
    building_h = height * (0.58 + density * 0.20)
    route_width = width * 0.14

    base_part = _part_name(asset_graph, "setpiece", "base", "terrain", fallback="setpiece_base")
    terrain_part = _part_name(asset_graph, "terrain", "ground", fallback=base_part)
    building_part = _part_name(asset_graph, "building", "primary", "body", fallback="primary_building")
    secondary_part = _part_name(asset_graph, "secondary", "building", "warehouse", fallback=building_part)
    courtyard_part = _part_name(asset_graph, "courtyard", "lot", fallback=base_part)
    road_part = _part_name(asset_graph, "road", "route", "street", fallback="road_spine")
    access_part = _part_name(asset_graph, "access", "walkway", "catwalk", fallback="access_route")
    door_part = _part_name(asset_graph, "door", "opening", "threshold", fallback=access_part)
    utility_part = _part_name(asset_graph, "utility", "pipe", "infrastructure", fallback="utility_run")
    prop_part = _part_name(asset_graph, "prop", "stall", "crate", "market", fallback="prop_cluster")
    actor_body_part = _part_name(asset_graph, "actor", "npc", "body", fallback=prop_part)
    actor_head_part = _part_name(asset_graph, "head", "face", "sensor", fallback=actor_body_part)
    actor_pack_part = _part_name(asset_graph, "pack", "loadout", "inventory", fallback=actor_body_part)
    behavior_node_part = _part_name(asset_graph, "behavior", "signal", "node", fallback=prop_part)
    spawn_marker_part = _part_name(asset_graph, "spawn", "nest", "ecology", fallback=prop_part)
    event_marker_part = _part_name(asset_graph, "event", "signal", "emitter", fallback=behavior_node_part)
    trigger_marker_part = _part_name(asset_graph, "trigger", "sensor", "volume", fallback=event_marker_part)
    state_node_part = _part_name(asset_graph, "state", "logic", "node", fallback=behavior_node_part)
    animation_marker_part = _part_name(asset_graph, "animation", "timeline", "keyframe", fallback=state_node_part)
    moving_part_marker_part = _part_name(asset_graph, "moving_part", "animated_part", "hinge", fallback=access_part)
    effect_marker_part = _part_name(asset_graph, "vfx", "sound", "cue", "effect", fallback=event_marker_part)
    physics_body_part = _part_name(asset_graph, "physics_body", "rigid_body", "collider", fallback=prop_part)
    physics_joint_part = _part_name(asset_graph, "physics_joint", "hinge_joint", "constraint", fallback=moving_part_marker_part)
    debris_part = _part_name(asset_graph, "debris", "fragment", "shard", fallback=prop_part)
    flexible_part = _part_name(asset_graph, "rope", "cable", "cloth", fallback=utility_part)
    force_field_part = _part_name(asset_graph, "force_field", "field", "impulse", fallback=effect_marker_part)
    surface_layer_part = _part_name(asset_graph, "surface_layer", "material_layer", "paint_layer", fallback=prop_part)
    material_zone_part = _part_name(asset_graph, "material_zone", "zone", "material_slot", fallback=surface_layer_part)
    decal_part = _part_name(asset_graph, "decal", "marking", "story_mark", fallback=effect_marker_part)
    wear_part = _part_name(asset_graph, "wear_pattern", "wear", "scratch", fallback=decal_part)
    damage_surface_part = _part_name(asset_graph, "damage_surface", "crack", "scorch", fallback=wear_part)
    surface_transition_part = _part_name(asset_graph, "surface_transition", "transition_band", "exposed_edge", fallback=surface_layer_part)
    weather_part = _part_name(asset_graph, "weather_system", "weather", "environment_effect", fallback=effect_marker_part)
    atmosphere_part = _part_name(asset_graph, "atmosphere", "sky", "cloud", fallback=weather_part)
    wind_part = _part_name(asset_graph, "wind_zone", "gust", "flow", fallback=weather_part)
    liquid_part = _part_name(asset_graph, "liquid_body", "puddle", "wetness", fallback=surface_layer_part)
    fire_part = _part_name(asset_graph, "fire_source", "flame", "ember", fallback=effect_marker_part)
    smoke_part = _part_name(asset_graph, "smoke_emitter", "mist", "fog", fallback=atmosphere_part)
    time_part = _part_name(asset_graph, "time_of_day", "sun", "moon", fallback=atmosphere_part)
    shot_part = _part_name(asset_graph, "shot", "camera", "frustum", fallback=effect_marker_part)
    camera_rail_part = _part_name(asset_graph, "camera_rail", "camera_path", "dolly", fallback=access_part)
    focal_part = _part_name(asset_graph, "look_at_target", "focal_zone", "focus", fallback=shot_part)
    camera_volume_part = _part_name(asset_graph, "camera_volume", "presentation_rig", "orbit_camera", fallback=shot_part)
    cutscene_part = _part_name(asset_graph, "cutscene_beat", "shot_sequence", "timeline", fallback=animation_marker_part)
    ambient_part = _part_name(asset_graph, "ambient_bed", "ambience", "soundscape", fallback=effect_marker_part)
    sound_zone_part = _part_name(asset_graph, "sound_zone", "sound", "audio", fallback=ambient_part)
    reverb_part = _part_name(asset_graph, "reverb_space", "reverb", "room_tone", fallback=sound_zone_part)
    occluder_part = _part_name(asset_graph, "acoustic_occluder", "occluder", "sound_blocker", fallback=surface_layer_part)
    propagation_part = _part_name(asset_graph, "sound_propagation", "propagation", "audio_ray", fallback=sound_zone_part)
    music_part = _part_name(asset_graph, "music_state", "music_transition", "stinger", fallback=cutscene_part)
    foley_part = _part_name(asset_graph, "foley_emitter", "foley", "footstep", fallback=sound_zone_part)
    listener_part = _part_name(asset_graph, "listener_zone", "audio_bus", "mix_bus", fallback=sound_zone_part)
    acoustic_material_part = _part_name(asset_graph, "acoustic_material", "absorption", "reflection", fallback=material_zone_part)
    interaction_prompt_part = _part_name(asset_graph, "interaction_prompt", "prompt", "label", fallback=effect_marker_part)
    interaction_zone_part = _part_name(asset_graph, "interaction_zone", "trigger", "range", fallback=trigger_marker_part)
    usable_part = _part_name(asset_graph, "usable", "affordance", "interaction", fallback=prop_part)
    pickup_part = _part_name(asset_graph, "pickup", "item", "loot", fallback=prop_part)
    inspect_part = _part_name(asset_graph, "inspect_point", "inspect", "lore", fallback=interaction_prompt_part)
    terminal_part = _part_name(asset_graph, "terminal", "screen", "console", fallback=effect_marker_part)
    control_panel_part = _part_name(asset_graph, "control_panel", "panel", "console", fallback=terminal_part)
    control_input_part = _part_name(asset_graph, "button", "switch", "lever", fallback=control_panel_part)
    door_lock_part = _part_name(asset_graph, "door_lock", "lock", "keypad", fallback=control_input_part)
    quest_marker_part = _part_name(asset_graph, "quest_marker", "objective", "marker", fallback=effect_marker_part)
    signage_ui_part = _part_name(asset_graph, "signage", "sign", "wayfinding", fallback=quest_marker_part)
    map_marker_part = _part_name(asset_graph, "map_marker", "map_pin", "waypoint", fallback=quest_marker_part)
    hud_part = _part_name(asset_graph, "diegetic_hud", "hud", "status_display", fallback=terminal_part)
    ui_anchor_part = _part_name(asset_graph, "ui_anchor", "anchor", "widget", fallback=hud_part)
    mission_part = _part_name(asset_graph, "mission", "quest", "briefing", fallback=quest_marker_part)
    objective_chain_part = _part_name(asset_graph, "objective_chain", "objective", "task", fallback=mission_part)
    condition_part = _part_name(asset_graph, "success_condition", "failure_condition", "gameplay_rule", fallback=state_node_part)
    reward_part = _part_name(asset_graph, "reward_table", "reward", "prize", fallback=pickup_part)
    loot_table_part = _part_name(asset_graph, "loot_table", "loot", "drop_table", fallback=reward_part)
    inventory_slot_part = _part_name(asset_graph, "inventory_slot", "slot", "item_slot", fallback=pickup_part)
    crafting_part = _part_name(asset_graph, "crafting_station", "recipe", "workbench", fallback=control_panel_part)
    shop_part = _part_name(asset_graph, "shop", "vendor", "storefront", fallback=signage_ui_part)
    currency_part = _part_name(asset_graph, "currency", "coin", "credits", fallback=reward_part)
    reputation_part = _part_name(asset_graph, "reputation_rule", "faction_reputation", "standing", fallback=quest_marker_part)
    unlock_part = _part_name(asset_graph, "unlock_rule", "unlock", "progress_gate", fallback=door_lock_part)
    progression_part = _part_name(asset_graph, "progression_track", "level", "rank", fallback=quest_marker_part)
    director_part = _part_name(asset_graph, "director", "encounter_director", "ai_director", fallback=mission_part)
    director_intent_part = _part_name(asset_graph, "director_intent", "intent", "director_goal", fallback=director_part)
    pacing_part = _part_name(asset_graph, "pacing_curve", "encounter_beat", "beat", fallback=director_part)
    threat_budget_part = _part_name(asset_graph, "threat_budget", "spawn_budget", "threat", fallback=condition_part)
    spawn_wave_part = _part_name(asset_graph, "spawn_wave", "wave", "spawn", fallback=spawn_marker_part)
    phase_part = _part_name(asset_graph, "combat_phase", "stealth_phase", "phase", fallback=event_marker_part)
    escalation_part = _part_name(asset_graph, "escalation_rule", "adaptive_difficulty", "difficulty", fallback=condition_part)
    director_signal_part = _part_name(asset_graph, "director_signal", "signal", "cue", fallback=event_marker_part)
    threat_zone_part = _part_name(asset_graph, "threat_zone", "threat", "danger_zone", fallback=interaction_zone_part)
    reinforcement_route_part = _part_name(asset_graph, "reinforcement_route", "reinforcement", "spawn_route", fallback=road_part)
    simulation_layer_part = _part_name(asset_graph, "simulation_layer", "world_simulation", "sim_core", fallback=state_node_part)
    field_part = _part_name(asset_graph, "heat_field", "noise_field", "visibility_field", "field", fallback=simulation_layer_part)
    resource_flow_part = _part_name(asset_graph, "resource_flow", "flow", "resource", fallback=utility_part)
    faction_pressure_part = _part_name(asset_graph, "faction_pressure", "pressure", "influence", fallback=condition_part)
    territory_part = _part_name(asset_graph, "territory_influence", "territory", "claim", fallback=faction_pressure_part)
    alarm_grid_part = _part_name(asset_graph, "alarm_grid", "alarm", "security_grid", fallback=director_signal_part)
    patrol_density_part = _part_name(asset_graph, "patrol_density", "patrol", "density", fallback=reinforcement_route_part)
    hazard_field_part = _part_name(asset_graph, "hazard_field", "hazard", "danger_field", fallback=threat_zone_part)
    sensor_grid_part = _part_name(asset_graph, "sensor_grid", "sensor", "coverage", fallback=alarm_grid_part)
    cover_map_part = _part_name(asset_graph, "cover_map", "cover", "occlusion", fallback=threat_zone_part)
    flow_gate_part = _part_name(asset_graph, "flow_gate", "sluice", "valve", fallback=resource_flow_part)
    world_metric_part = _part_name(asset_graph, "world_metric", "metric", "readout", fallback=state_node_part)
    simulation_probe_part = _part_name(asset_graph, "simulation_probe", "probe", "sample", fallback=world_metric_part)
    culture_system_part = _part_name(asset_graph, "culture_system", "culture", "civilization", fallback=state_node_part)
    law_code_part = _part_name(asset_graph, "law_code", "law", "code", fallback=condition_part)
    policy_rule_part = _part_name(asset_graph, "policy_rule", "policy", "edict", fallback=law_code_part)
    economy_model_part = _part_name(asset_graph, "economy_model", "economy", "market", fallback=shop_part)
    trade_policy_part = _part_name(asset_graph, "trade_policy", "trade", "tariff", fallback=economy_model_part)
    diplomacy_state_part = _part_name(asset_graph, "diplomacy_state", "diplomacy", "treaty", fallback=reputation_part)
    social_graph_part = _part_name(asset_graph, "social_graph", "society", "network", fallback=culture_system_part)
    social_relation_part = _part_name(asset_graph, "social_relation", "relationship", "tie", fallback=social_graph_part)
    population_group_part = _part_name(asset_graph, "population_group", "population", "group", fallback=social_graph_part)
    labor_system_part = _part_name(asset_graph, "labor_system", "labor", "job", fallback=economy_model_part)
    ritual_calendar_part = _part_name(asset_graph, "ritual_calendar", "ritual", "calendar", fallback=culture_system_part)
    festival_part = _part_name(asset_graph, "festival", "celebration", "event", fallback=ritual_calendar_part)
    belief_system_part = _part_name(asset_graph, "belief_system", "belief", "doctrine", fallback=culture_system_part)
    cultural_marker_part = _part_name(asset_graph, "cultural_marker", "symbol", "marker", fallback=belief_system_part)
    civic_institution_part = _part_name(asset_graph, "civic_institution", "institution", "civic", fallback=building_part)
    biome_system_part = _part_name(asset_graph, "biome_system", "biome", "ecology", fallback=terrain_part)
    habitat_zone_part = _part_name(asset_graph, "habitat_zone", "habitat", "zone", fallback=terrain_part)
    species_population_part = _part_name(asset_graph, "species_population", "species", "wildlife", fallback=spawn_marker_part)
    food_web_part = _part_name(asset_graph, "food_web", "food_chain", "ecology_web", fallback=state_node_part)
    predator_prey_link_part = _part_name(asset_graph, "predator_prey_link", "predator", "prey", fallback=world_metric_part)
    migration_route_part = _part_name(asset_graph, "migration_route", "migration", "wildlife_route", fallback=road_part)
    nesting_site_part = _part_name(asset_graph, "nesting_site", "nest", "den", fallback=spawn_marker_part)
    resource_patch_part = _part_name(asset_graph, "resource_patch", "forage", "resource_node", fallback=terrain_part)
    resource_regeneration_part = _part_name(asset_graph, "resource_regeneration", "regeneration", "renewable", fallback=resource_flow_part)
    growth_cycle_part = _part_name(asset_graph, "growth_cycle", "growth", "season", fallback=state_node_part)
    weather_ecology_link_part = _part_name(asset_graph, "weather_ecology_link", "weather_link", "ecology_weather", fallback=weather_part)
    ecological_pressure_part = _part_name(asset_graph, "ecological_pressure", "pressure", "ecology_hazard", fallback=hazard_field_part)
    land_use_plan_part = _part_name(asset_graph, "land_use_plan", "land_use", "settlement_plan", fallback=culture_system_part)
    farm_plot_part = _part_name(asset_graph, "farm_plot", "farm", "crop", fallback=resource_patch_part)
    hunting_ground_part = _part_name(asset_graph, "hunting_ground", "hunting", "game", fallback=habitat_zone_part)
    fishing_ground_part = _part_name(asset_graph, "fishing_ground", "fishing", "fishery", fallback=liquid_part)
    grazing_range_part = _part_name(asset_graph, "grazing_range", "grazing", "pasture", fallback=habitat_zone_part)
    extraction_site_part = _part_name(asset_graph, "extraction_site", "mine", "logging", "quarry", fallback=resource_patch_part)
    pollution_source_part = _part_name(asset_graph, "pollution_source", "pollution", "waste", fallback=ecological_pressure_part)
    conservation_zone_part = _part_name(asset_graph, "conservation_zone", "reserve", "protected", fallback=habitat_zone_part)
    restoration_project_part = _part_name(asset_graph, "restoration_project", "restoration", "rewilding", fallback=conservation_zone_part)
    scarcity_loop_part = _part_name(asset_graph, "scarcity_loop", "scarcity", "deficit", fallback=world_metric_part)
    settlement_pressure_part = _part_name(asset_graph, "settlement_pressure", "settlement", "pressure", fallback=culture_system_part)
    resource_claim_part = _part_name(asset_graph, "resource_claim", "claim", "territory_claim", fallback=territory_part)
    harvest_cycle_part = _part_name(asset_graph, "harvest_cycle", "harvest", "yield", fallback=growth_cycle_part)
    carrying_capacity_rule_part = _part_name(asset_graph, "carrying_capacity_rule", "carrying_capacity", "capacity_rule", fallback=world_metric_part)
    biome_impact_part = _part_name(asset_graph, "biome_impact", "impact", "ecology_impact", fallback=ecological_pressure_part)
    supply_chain_part = _part_name(asset_graph, "supply_chain", "supply", "chain", fallback=resource_flow_part)
    logistics_hub_part = _part_name(asset_graph, "logistics_hub", "hub", "warehouse", fallback=supply_chain_part)
    storage_depot_part = _part_name(asset_graph, "storage_depot", "depot", "storage", fallback=logistics_hub_part)
    stockpile_part = _part_name(asset_graph, "stockpile", "inventory", "stock", fallback=storage_depot_part)
    input_buffer_part = _part_name(asset_graph, "input_buffer", "input", "buffer", fallback=stockpile_part)
    output_buffer_part = _part_name(asset_graph, "output_buffer", "output", "buffer", fallback=stockpile_part)
    processing_stage_part = _part_name(asset_graph, "processing_stage", "processor", "process", fallback=utility_part)
    refinery_stage_part = _part_name(asset_graph, "refinery_stage", "refinery", "smelter", fallback=processing_stage_part)
    workshop_stage_part = _part_name(asset_graph, "workshop_stage", "workshop", "fabricator", fallback=processing_stage_part)
    assembly_stage_part = _part_name(asset_graph, "assembly_stage", "assembly", "assembler", fallback=processing_stage_part)
    market_node_part = _part_name(asset_graph, "market_node", "market", "exchange", fallback=shop_part)
    demand_sink_part = _part_name(asset_graph, "demand_sink", "demand", "consumer", fallback=market_node_part)
    supply_route_part = _part_name(asset_graph, "supply_route", "supply_route", "logistics_route", fallback=road_part)
    transport_leg_part = _part_name(asset_graph, "transport_leg", "transport", "leg", fallback=supply_route_part)
    bottleneck_part = _part_name(asset_graph, "bottleneck", "constraint", "choke", fallback=world_metric_part)
    throughput_rule_part = _part_name(asset_graph, "throughput_rule", "throughput", "rule", fallback=world_metric_part)
    failure_mode_part = _part_name(asset_graph, "failure_mode", "failure", "fault", fallback=condition_part)
    production_strategy_part = _part_name(asset_graph, "production_strategy", "strategy", "industrial_plan", fallback=supply_chain_part)
    production_priority_part = _part_name(asset_graph, "production_priority", "priority", "priority_marker", fallback=production_strategy_part)
    quota_rule_part = _part_name(asset_graph, "quota_rule", "quota", "quota_marker", fallback=throughput_rule_part)
    allocation_rule_part = _part_name(asset_graph, "allocation_rule", "allocation", "allocator", fallback=quota_rule_part)
    rationing_policy_part = _part_name(asset_graph, "rationing_policy", "rationing", "ration", fallback=scarcity_loop_part)
    strategic_reserve_part = _part_name(asset_graph, "strategic_reserve", "reserve", "war_stock", fallback=stockpile_part)
    trade_embargo_part = _part_name(asset_graph, "trade_embargo", "embargo", "blockade", fallback=diplomacy_state_part)
    sabotage_target_part = _part_name(asset_graph, "sabotage_target", "sabotage", "target", fallback=failure_mode_part)
    maintenance_plan_part = _part_name(asset_graph, "maintenance_plan", "maintenance", "service_plan", fallback=failure_mode_part)
    repair_schedule_part = _part_name(asset_graph, "repair_schedule", "repair", "schedule", fallback=maintenance_plan_part)
    mobilization_order_part = _part_name(asset_graph, "mobilization_order", "mobilization", "war_order", fallback=production_strategy_part)
    production_mode_part = _part_name(asset_graph, "production_mode", "mode", "production_state", fallback=state_node_part)
    wartime_production_part = _part_name(asset_graph, "wartime_production", "wartime", "military_output", fallback=production_mode_part)
    peacetime_production_part = _part_name(asset_graph, "peacetime_production", "peacetime", "civilian_output", fallback=production_mode_part)
    procurement_contract_part = _part_name(asset_graph, "procurement_contract", "procurement", "contract", fallback=market_node_part)
    readiness_level_part = _part_name(asset_graph, "readiness_level", "readiness", "readiness_meter", fallback=world_metric_part)
    conflict_system_part = _part_name(asset_graph, "conflict_system", "conflict", "war_room", fallback=production_strategy_part)
    strategic_objective_part = _part_name(asset_graph, "strategic_objective", "objective", "campaign_goal", fallback=quest_marker_part)
    war_plan_part = _part_name(asset_graph, "war_plan", "campaign", "war_plan", fallback=conflict_system_part)
    battlefront_part = _part_name(asset_graph, "battlefront", "front", "theater", fallback=territory_part)
    escalation_ladder_part = _part_name(asset_graph, "escalation_ladder", "escalation", "pressure_ladder", fallback=director_part)
    treaty_part = _part_name(asset_graph, "treaty", "accord", "pact", fallback=diplomacy_state_part)
    ceasefire_part = _part_name(asset_graph, "ceasefire", "truce", "armistice", fallback=treaty_part)
    alliance_part = _part_name(asset_graph, "alliance", "coalition", "pact", fallback=treaty_part)
    rival_claim_part = _part_name(asset_graph, "rival_claim", "claim", "contested_claim", fallback=resource_claim_part)
    diplomatic_demand_part = _part_name(asset_graph, "diplomatic_demand", "demand", "ultimatum", fallback=condition_part)
    negotiation_channel_part = _part_name(asset_graph, "negotiation_channel", "envoy", "channel", fallback=social_relation_part)
    sanction_part = _part_name(asset_graph, "sanction", "sanction", "restriction", fallback=trade_embargo_part)
    espionage_cell_part = _part_name(asset_graph, "espionage_cell", "spy_cell", "intelligence", fallback=sensor_grid_part)
    covert_operation_part = _part_name(asset_graph, "covert_operation", "covert", "operation", fallback=sabotage_target_part)
    emergency_order_part = _part_name(asset_graph, "emergency_order", "emergency", "order", fallback=policy_rule_part)
    disaster_response_part = _part_name(asset_graph, "disaster_response", "relief", "response", fallback=emergency_order_part)
    faction_ai_part = _part_name(asset_graph, "faction_ai", "ai", "command_brain", fallback=conflict_system_part)
    doctrine_model_part = _part_name(asset_graph, "doctrine_model", "doctrine", "rulebook", fallback=faction_ai_part)
    goal_stack_part = _part_name(asset_graph, "goal_stack", "goal", "priority_stack", fallback=strategic_objective_part)
    threat_model_part = _part_name(asset_graph, "threat_model", "threat", "threat_table", fallback=world_metric_part)
    perception_feed_part = _part_name(asset_graph, "perception_feed", "perception", "signal_feed", fallback=sensor_grid_part)
    decision_rule_part = _part_name(asset_graph, "decision_rule", "decision", "rule", fallback=policy_rule_part)
    policy_selector_part = _part_name(asset_graph, "policy_selector", "selector", "policy_picker", fallback=decision_rule_part)
    action_option_part = _part_name(asset_graph, "action_option", "option", "choice", fallback=interaction_zone_part)
    response_plan_part = _part_name(asset_graph, "response_plan", "response", "plan", fallback=war_plan_part)
    escalation_choice_part = _part_name(asset_graph, "escalation_choice", "escalation_choice", "escalate", fallback=escalation_ladder_part)
    deescalation_choice_part = _part_name(asset_graph, "deescalation_choice", "deescalation_choice", "deescalate", fallback=negotiation_channel_part)
    resource_strategy_part = _part_name(asset_graph, "resource_strategy", "resource_strategy", "resource_plan", fallback=production_strategy_part)
    logistics_priority_part = _part_name(asset_graph, "logistics_priority", "logistics_priority", "supply_priority", fallback=logistics_hub_part)
    diplomatic_posture_part = _part_name(asset_graph, "diplomatic_posture", "posture", "stance", fallback=diplomacy_state_part)
    contingency_plan_part = _part_name(asset_graph, "contingency_plan", "contingency", "fallback_plan", fallback=emergency_order_part)
    adaptive_order_part = _part_name(asset_graph, "adaptive_order", "adaptive", "order", fallback=policy_rule_part)
    operational_plan_part = _part_name(asset_graph, "operational_plan", "operations", "ops_plan", fallback=faction_ai_part)
    order_queue_part = _part_name(asset_graph, "order_queue", "queue", "order_stack", fallback=operational_plan_part)
    world_order_part = _part_name(asset_graph, "world_order", "order", "command", fallback=order_queue_part)
    patrol_order_part = _part_name(asset_graph, "patrol_order", "patrol_order", "patrol", fallback=patrol_density_part)
    convoy_order_part = _part_name(asset_graph, "convoy_order", "convoy_order", "convoy", fallback=supply_route_part)
    construction_queue_part = _part_name(asset_graph, "construction_queue", "construction_queue", "build_queue", fallback=order_queue_part)
    construction_order_part = _part_name(asset_graph, "construction_order", "construction_order", "build_order", fallback=construction_queue_part)
    repair_order_part = _part_name(asset_graph, "repair_order", "repair_order", "repair", fallback=repair_schedule_part)
    relief_order_part = _part_name(asset_graph, "relief_order", "relief_order", "relief", fallback=disaster_response_part)
    mission_order_part = _part_name(asset_graph, "mission_order", "mission_order", "mission", fallback=mission_part)
    scheduled_action_part = _part_name(asset_graph, "scheduled_action", "scheduled", "timer", fallback=event_marker_part)
    task_assignment_part = _part_name(asset_graph, "task_assignment", "assignment", "task", fallback=quest_marker_part)
    crew_roster_part = _part_name(asset_graph, "crew_roster", "crew", "roster", fallback=labor_system_part)
    convoy_route_part = _part_name(asset_graph, "convoy_route", "convoy_route", "route", fallback=supply_route_part)
    repair_crew_part = _part_name(asset_graph, "repair_crew", "repair_crew", "maintenance_team", fallback=repair_order_part)
    relief_team_part = _part_name(asset_graph, "relief_team", "relief_team", "aid_team", fallback=relief_order_part)
    settlement_evolution_part = _part_name(asset_graph, "settlement_evolution", "evolution", "growth_plan", fallback=operational_plan_part)
    growth_phase_part = _part_name(asset_graph, "growth_phase", "phase", "milestone", fallback=scheduled_action_part)
    expansion_zone_part = _part_name(asset_graph, "expansion_zone", "zone", "district_pad", fallback=base_part)
    construction_stage_part = _part_name(asset_graph, "construction_stage", "stage", "build_stage", fallback=construction_order_part)
    upgrade_plan_part = _part_name(asset_graph, "upgrade_plan", "upgrade", "improvement_plan", fallback=construction_queue_part)
    district_upgrade_part = _part_name(asset_graph, "district_upgrade", "district_upgrade", "district", fallback=building_part)
    building_upgrade_part = _part_name(asset_graph, "building_upgrade", "building_upgrade", "building", fallback=building_part)
    infrastructure_upgrade_part = _part_name(asset_graph, "infrastructure_upgrade", "infrastructure_upgrade", "utility_upgrade", fallback=utility_part)
    material_delivery_part = _part_name(asset_graph, "material_delivery", "delivery", "materials", fallback=convoy_order_part)
    staffing_plan_part = _part_name(asset_graph, "staffing_plan", "staffing", "crew_plan", fallback=crew_roster_part)
    occupancy_plan_part = _part_name(asset_graph, "occupancy_plan", "occupancy", "population", fallback=population_group_part)
    worksite_part = _part_name(asset_graph, "worksite", "site", "construction_site", fallback=construction_order_part)
    build_permit_part = _part_name(asset_graph, "build_permit", "permit", "inspection", fallback=policy_rule_part)
    damage_repair_plan_part = _part_name(asset_graph, "damage_repair_plan", "damage_repair", "repair_plan", fallback=repair_order_part)
    demolition_plan_part = _part_name(asset_graph, "demolition_plan", "demolition", "clearance", fallback=debris_part)
    renovation_project_part = _part_name(asset_graph, "renovation_project", "renovation", "retrofit", fallback=building_upgrade_part)
    city_plan_part = _part_name(asset_graph, "city_plan", "city", "planning_board", fallback=settlement_evolution_part)
    zoning_rule_part = _part_name(asset_graph, "zoning_rule", "zoning", "policy_grid", fallback=policy_rule_part)
    zoning_district_part = _part_name(asset_graph, "zoning_district", "zone", "district", fallback=district_upgrade_part)
    parcel_grid_part = _part_name(asset_graph, "parcel_grid", "parcel_grid", "lot_grid", fallback=base_part)
    land_parcel_part = _part_name(asset_graph, "land_parcel", "parcel", "lot", fallback=building_part)
    parcel_subdivision_part = _part_name(asset_graph, "parcel_subdivision", "subdivision", "lot_split", fallback=parcel_grid_part)
    block_plan_part = _part_name(asset_graph, "block_plan", "block", "city_block", fallback=base_part)
    street_hierarchy_part = _part_name(asset_graph, "street_hierarchy", "street", "road_hierarchy", fallback=road_part)
    transit_node_part = _part_name(asset_graph, "transit_node", "transit", "station", fallback=access_part)
    civic_service_plan_part = _part_name(asset_graph, "civic_service_plan", "civic_service", "services", fallback=utility_part)
    service_coverage_part = _part_name(asset_graph, "service_coverage", "coverage", "service_radius", fallback=world_metric_part)
    utility_corridor_part = _part_name(asset_graph, "utility_corridor", "utility_corridor", "utility_spine", fallback=utility_part)
    district_site_plan_part = _part_name(asset_graph, "district_site_plan", "district_site", "district", fallback=city_plan_part)
    street_crossing_part = _part_name(asset_graph, "street_crossing", "crossing", "crosswalk", fallback=road_part)
    perimeter_plan_part = _part_name(asset_graph, "perimeter_plan", "perimeter", "boundary", fallback=base_part)
    security_gate_part = _part_name(asset_graph, "security_gate", "gate", "access_control", fallback=access_part)
    landscape_zone_part = _part_name(asset_graph, "landscape_zone", "landscape", "green_zone", fallback=courtyard_part)
    traffic_flow_part = _part_name(asset_graph, "traffic_flow", "traffic", "route_flow", fallback=street_hierarchy_part)
    service_flow_part = _part_name(asset_graph, "service_flow", "service_route", "utility_flow", fallback=utility_corridor_part)
    power_grid_part = _part_name(asset_graph, "power_grid", "power", "grid", fallback=utility_corridor_part)
    substation_part = _part_name(asset_graph, "substation", "power_node", "transformer", fallback=power_grid_part)
    transformer_bank_part = _part_name(asset_graph, "transformer_bank", "transformer", "transformers", fallback=substation_part)
    power_line_part = _part_name(asset_graph, "power_line", "power_cable", "conduit", fallback=power_grid_part)
    water_network_part = _part_name(asset_graph, "water_network", "water", "pipe", fallback=utility_corridor_part)
    pump_station_part = _part_name(asset_graph, "pump_station", "pump", "valve", fallback=water_network_part)
    water_tower_part = _part_name(asset_graph, "water_tower", "water_storage", "tank", fallback=water_network_part)
    sewer_network_part = _part_name(asset_graph, "sewer_network", "sewer", "drain", fallback=utility_corridor_part)
    treatment_plant_part = _part_name(asset_graph, "treatment_plant", "treatment", "filter", fallback=sewer_network_part)
    data_network_part = _part_name(asset_graph, "data_network", "data", "telecom", fallback=utility_corridor_part)
    data_hub_part = _part_name(asset_graph, "data_hub", "data_hub", "server", fallback=data_network_part)
    fiber_line_part = _part_name(asset_graph, "fiber_line", "fiber", "signal", fallback=data_network_part)
    transit_line_part = _part_name(asset_graph, "transit_line", "transit", "track", fallback=transit_node_part)
    transit_station_part = _part_name(asset_graph, "transit_station", "station", "platform", fallback=transit_node_part)
    service_connection_part = _part_name(asset_graph, "service_connection", "service_tap", "junction", fallback=utility_corridor_part)
    maintenance_access_part = _part_name(asset_graph, "maintenance_access", "access", "walkway", fallback=access_part)
    building_service_plan_part = _part_name(asset_graph, "building_service_plan", "building_services", "service_plan", fallback=utility_corridor_part)
    service_core_part = _part_name(asset_graph, "service_core", "service_core", "utility_core", fallback=building_service_plan_part)
    utility_room_part = _part_name(asset_graph, "utility_room", "utility_room", "utility", fallback=service_core_part)
    mechanical_room_part = _part_name(asset_graph, "mechanical_room", "mechanical", "plant_room", fallback=utility_room_part)
    electrical_panel_part = _part_name(asset_graph, "electrical_panel", "panel", "breaker", fallback=power_grid_part)
    meter_bank_part = _part_name(asset_graph, "meter_bank", "meter", "utility_meter", fallback=electrical_panel_part)
    plumbing_stack_part = _part_name(asset_graph, "plumbing_stack", "riser", "plumbing", fallback=water_network_part)
    hvac_system_part = _part_name(asset_graph, "hvac_system", "hvac", "air_handler", fallback=mechanical_room_part)
    ventilation_duct_part = _part_name(asset_graph, "ventilation_duct", "duct", "vent", fallback=hvac_system_part)
    elevator_core_part = _part_name(asset_graph, "elevator_core", "elevator", "shaft", fallback=maintenance_access_part)
    service_elevator_part = _part_name(asset_graph, "service_elevator", "service_lift", "lift", fallback=elevator_core_part)
    service_shaft_part = _part_name(asset_graph, "service_shaft", "shaft", "riser", fallback=service_core_part)
    fire_suppression_part = _part_name(asset_graph, "fire_suppression", "fire_safety", "sprinkler", fallback=plumbing_stack_part)
    sprinkler_zone_part = _part_name(asset_graph, "sprinkler_zone", "sprinkler", "fire_zone", fallback=fire_suppression_part)
    waste_chute_part = _part_name(asset_graph, "waste_chute", "chute", "waste", fallback=sewer_network_part)
    loading_dock_part = _part_name(asset_graph, "loading_dock", "dock", "bay", fallback=maintenance_access_part)
    site_compound_part = _part_name(asset_graph, "site_compound", "compound", "site", fallback=base_part)
    building_lot_part = _part_name(asset_graph, "building_lot", "lot", "building_pad", fallback=building_part)
    courtyard_plan_part = _part_name(asset_graph, "courtyard_plan", "courtyard", "public_space", fallback=courtyard_part)
    pedestrian_path_part = _part_name(asset_graph, "pedestrian_path", "walkway", "path", fallback=access_part)
    service_alley_part = _part_name(asset_graph, "service_alley", "service_lane", "alley", fallback=maintenance_access_part)
    parking_zone_part = _part_name(asset_graph, "parking_zone", "parking", "vehicle_bay", fallback=base_part)
    parking_bay_part = _part_name(asset_graph, "parking_bay", "vehicle_space", "bay", fallback=parking_zone_part)
    loading_zone_part = _part_name(asset_graph, "loading_zone", "loading", "dock_zone", fallback=loading_dock_part)
    exterior_utility_part = _part_name(asset_graph, "exterior_utility", "utility_spine", "service_run", fallback=utility_corridor_part)
    public_space_plan_part = _part_name(asset_graph, "public_space_plan", "public_space", "park", fallback=courtyard_part)
    growth_boundary_part = _part_name(asset_graph, "growth_boundary", "boundary", "growth_edge", fallback=base_part)
    district_dependency_part = _part_name(asset_graph, "district_dependency", "dependency", "link", fallback=resource_flow_part)
    development_pressure_part = _part_name(asset_graph, "development_pressure", "pressure", "demand", fallback=settlement_pressure_part)
    climate_zone_part = _part_name(asset_graph, "climate_zone", "climate", "biome_zone", fallback=biome_system_part)
    climate_risk_map_part = _part_name(asset_graph, "climate_risk_map", "risk_map", "hazard_map", fallback=hazard_field_part)
    flood_risk_part = _part_name(asset_graph, "flood_risk", "flood", "floodplain", fallback=liquid_part)
    fire_risk_part = _part_name(asset_graph, "fire_risk", "fire", "wildfire", fallback=fire_part)
    heat_risk_part = _part_name(asset_graph, "heat_risk", "heat", "heat_island", fallback=weather_part)
    resource_constraint_part = _part_name(asset_graph, "resource_constraint", "constraint", "resource_limit", fallback=scarcity_loop_part)
    protected_land_part = _part_name(asset_graph, "protected_land", "protected", "conservation", fallback=conservation_zone_part)
    green_infrastructure_part = _part_name(asset_graph, "green_infrastructure", "green", "greenway", fallback=protected_land_part)
    stormwater_system_part = _part_name(asset_graph, "stormwater_system", "stormwater", "water_system", fallback=utility_part)
    cooling_corridor_part = _part_name(asset_graph, "cooling_corridor", "cooling", "shade_corridor", fallback=street_hierarchy_part)
    evacuation_route_part = _part_name(asset_graph, "evacuation_route", "evacuation", "escape_route", fallback=street_hierarchy_part)
    emergency_shelter_part = _part_name(asset_graph, "emergency_shelter", "shelter", "safe_hub", fallback=building_part)
    resilience_plan_part = _part_name(asset_graph, "resilience_plan", "resilience", "adaptation_plan", fallback=city_plan_part)
    climate_adaptation_part = _part_name(asset_graph, "climate_adaptation", "adaptation", "retrofit", fallback=green_infrastructure_part)
    transit_oriented_growth_part = _part_name(asset_graph, "transit_oriented_growth", "transit_growth", "tod", fallback=transit_node_part)
    risk_mitigation_part = _part_name(asset_graph, "risk_mitigation", "mitigation", "risk_control", fallback=climate_risk_map_part)
    perimeter_part = _part_name(asset_graph, "perimeter", "fence", "wall", fallback="perimeter_segment")
    gate_part = _part_name(asset_graph, "gate", "gatehouse", fallback="gatehouse")
    tower_part = _part_name(asset_graph, "tower", "watchtower", fallback="watchtower")
    dock_part = _part_name(asset_graph, "dock", "deck", fallback="dock")
    apron_part = _part_name(asset_graph, "apron", "runway", fallback="apron")
    ritual_part = _part_name(asset_graph, "ritual", "temple", "column", fallback="ritual_axis")
    vehicle_chassis_part = _part_name(asset_graph, "vehicle", "chassis", fallback="vehicle_chassis")
    vehicle_cabin_part = _part_name(asset_graph, "vehicle", "cabin", fallback=vehicle_chassis_part)
    vehicle_wheel_part = _part_name(asset_graph, "vehicle", "wheel", fallback=vehicle_chassis_part)
    vehicle_rotor_part = _part_name(asset_graph, "vehicle", "rotor", fallback=vehicle_chassis_part)
    vehicle_cargo_part = _part_name(asset_graph, "vehicle", "cargo", fallback=vehicle_chassis_part)
    vehicle_turret_part = _part_name(asset_graph, "vehicle", "turret", fallback=vehicle_chassis_part)
    boat_hull_part = _part_name(asset_graph, "boat", "hull", fallback="boat_hull")
    boat_deck_part = _part_name(asset_graph, "boat", "deck", fallback=boat_hull_part)
    boat_pontoon_part = _part_name(asset_graph, "boat", "pontoon", "float", fallback=boat_hull_part)
    boat_sail_part = _part_name(asset_graph, "boat", "sail", "canvas", fallback=boat_deck_part)
    boat_cargo_part = _part_name(asset_graph, "boat", "cargo", "hold", fallback=boat_deck_part)
    machine_base_part = _part_name(asset_graph, "machine", "base", fallback="machine_base")
    machine_conveyor_part = _part_name(asset_graph, "machine", "conveyor", fallback=machine_base_part)
    machine_hydraulic_part = _part_name(asset_graph, "machine", "hydraulic", "piston", fallback=machine_base_part)
    machine_crane_part = _part_name(asset_graph, "machine", "crane", "boom", fallback=machine_base_part)
    interior_part = _part_name(asset_graph, "interior", "room", fallback="interior_room")
    interior_light_part = _part_name(asset_graph, "interior", "light", fallback=interior_part)
    interior_alcove_part = _part_name(asset_graph, "interior", "alcove", fallback=interior_part)
    furniture_part = _part_name(asset_graph, "furniture", fallback="furniture_cluster")
    furniture_seat_part = _part_name(asset_graph, "furniture", "seat", "chair", fallback=furniture_part)
    furniture_shelf_part = _part_name(asset_graph, "furniture", "shelf", fallback=furniture_part)
    furniture_lamp_part = _part_name(asset_graph, "furniture", "lamp", fallback=furniture_part)
    functional_room_part = _part_name(asset_graph, "room_program", "functional_room", "room", fallback=interior_part)
    bathroom_part = _part_name(asset_graph, "bathroom", "wet_room", "plumbing_fixture", fallback=plumbing_stack_part)
    kitchen_part = _part_name(asset_graph, "kitchen", "galley", "counter", fallback=functional_room_part)
    lab_room_part = _part_name(asset_graph, "lab_room", "laboratory", "lab", fallback=functional_room_part)
    med_bay_part = _part_name(asset_graph, "med_bay", "medical_bay", "clinic", fallback=functional_room_part)
    workshop_room_part = _part_name(asset_graph, "workshop_room", "workshop", "workbench", fallback=functional_room_part)
    control_room_part = _part_name(asset_graph, "control_room", "operations_room", "control_panel", fallback=functional_room_part)
    storage_room_part = _part_name(asset_graph, "storage_room", "storage", "cabinet", fallback=functional_room_part)
    office_room_part = _part_name(asset_graph, "office_room", "office", "desk", fallback=functional_room_part)
    bedroom_part = _part_name(asset_graph, "bedroom", "bed", "sleeping_room", fallback=functional_room_part)
    fixture_cluster_part = _part_name(asset_graph, "fixture_cluster", "fixture", "furniture", fallback=furniture_part)
    appliance_bank_part = _part_name(asset_graph, "appliance_bank", "appliance", "fixture", fallback=fixture_cluster_part)
    workstation_cluster_part = _part_name(asset_graph, "workstation_cluster", "workstation", "desk", fallback=fixture_cluster_part)
    cabinet_wall_part = _part_name(asset_graph, "cabinet_wall", "cabinet", "locker", fallback=fixture_cluster_part)
    counter_run_part = _part_name(asset_graph, "counter_run", "counter", "workbench", fallback=fixture_cluster_part)
    sanitary_fixture_part = _part_name(asset_graph, "sanitary_fixture", "sink", "plumbing_fixture", fallback=bathroom_part)
    lab_bench_part = _part_name(asset_graph, "lab_bench", "bench", "lab", fallback=counter_run_part)
    medical_bed_part = _part_name(asset_graph, "medical_bed", "bed", "stretcher", fallback=bedroom_part)
    tool_rack_part = _part_name(asset_graph, "tool_rack", "rack", "tool", fallback=cabinet_wall_part)
    room_adjacency_part = _part_name(asset_graph, "room_adjacency", "adjacency", "layout_link", fallback=functional_room_part)
    room_connection_part = _part_name(asset_graph, "room_connection", "room_link", "connection", fallback=room_adjacency_part)
    door_opening_part = _part_name(asset_graph, "door_opening", "door", "opening", fallback=door_part)
    corridor_link_part = _part_name(asset_graph, "corridor_link", "corridor", "route", fallback=access_part)
    wall_run_part = _part_name(asset_graph, "wall_run", "wall", "partition", fallback=interior_part)
    room_socket_part = _part_name(asset_graph, "room_socket", "socket", "anchor", fallback=functional_room_part)
    fixture_socket_part = _part_name(asset_graph, "fixture_socket", "fixture_anchor", "socket", fallback=fixture_cluster_part)
    socket_binding_part = _part_name(asset_graph, "socket_binding", "binding", "snap", fallback=room_socket_part)
    fixture_placement_part = _part_name(asset_graph, "fixture_placement", "fixture", "placement", fallback=fixture_cluster_part)
    furniture_placement_part = _part_name(asset_graph, "furniture_placement", "furniture", "placement", fallback=fixture_cluster_part)
    service_placement_part = _part_name(asset_graph, "service_placement", "service_tap", "placement", fallback=service_connection_part)
    wall_attachment_part = _part_name(asset_graph, "wall_attachment", "attachment", "wall_mount", fallback=wall_run_part)
    anchor_rule_part = _part_name(asset_graph, "anchor_rule", "anchor", "rule", fallback=room_socket_part)
    placement_constraint_part = _part_name(asset_graph, "placement_constraint", "constraint", "clearance", fallback=anchor_rule_part)
    auto_layout_part = _part_name(asset_graph, "auto_layout", "layout_automation", "layout", fallback=placement_constraint_part)
    room_layout_plan_part = _part_name(asset_graph, "room_layout_plan", "room_layout", "layout_plan", fallback=room_adjacency_part)
    fixture_layout_part = _part_name(asset_graph, "fixture_layout", "fixture_layout", "fixture_plan", fallback=fixture_placement_part)
    furniture_layout_part = _part_name(asset_graph, "furniture_layout", "furniture_layout", "furniture_plan", fallback=furniture_placement_part)
    service_layout_part = _part_name(asset_graph, "service_layout", "service_layout", "service_plan", fallback=service_placement_part)
    wall_fixture_layout_part = _part_name(asset_graph, "wall_fixture_layout", "wall_fixture_layout", "wall_layout", fallback=wall_attachment_part)
    layout_zone_part = _part_name(asset_graph, "layout_zone", "zone", "room_zone", fallback=room_layout_plan_part)
    layout_socket_part = _part_name(asset_graph, "layout_socket", "socket", "slot", fallback=fixture_socket_part)
    auto_placed_part = _part_name(asset_graph, "auto_placed", "placed_object", "placement", fallback=fixture_placement_part)
    layout_solver_part = _part_name(asset_graph, "layout_solver", "resolver", "solver", fallback=auto_layout_part)
    room_bounds_part = _part_name(asset_graph, "room_bounds", "bounds", "room_footprint", fallback=room_layout_plan_part)
    wall_side_rule_part = _part_name(asset_graph, "wall_side_rule", "wall_rule", "wall_side", fallback=wall_run_part)
    socket_priority_part = _part_name(asset_graph, "socket_priority", "priority_socket", "priority", fallback=room_socket_part)
    clearance_zone_part = _part_name(asset_graph, "clearance_zone", "clearance", "buffer", fallback=placement_constraint_part)
    layout_slot_part = _part_name(asset_graph, "layout_slot", "slot", "placement_slot", fallback=layout_socket_part)
    resolved_slot_part = _part_name(asset_graph, "resolved_slot", "slot", "resolved", fallback=layout_slot_part)
    blocked_slot_part = _part_name(asset_graph, "blocked_slot", "blocked", "clearance", fallback=clearance_zone_part)
    priority_socket_part = _part_name(asset_graph, "priority_socket", "socket_priority", "priority", fallback=socket_priority_part)
    footprint_packer_part = _part_name(asset_graph, "footprint_packer", "footprint", "packer", fallback=layout_solver_part)
    placement_footprint_part = _part_name(asset_graph, "placement_footprint", "footprint", "occupied_area", fallback=fixture_placement_part)
    occupancy_grid_part = _part_name(asset_graph, "occupancy_grid", "grid", "cell_map", fallback=layout_zone_part)
    fit_profile_part = _part_name(asset_graph, "fit_profile", "fit", "score", fallback=socket_priority_part)
    collision_rule_part = _part_name(asset_graph, "collision_rule", "collision", "keepout", fallback=clearance_zone_part)
    service_reach_part = _part_name(asset_graph, "service_reach", "service_radius", "reach", fallback=service_placement_part)
    occupied_cell_part = _part_name(asset_graph, "occupied_cell", "blocked_cell", "occupied", fallback=blocked_slot_part)
    free_cell_part = _part_name(asset_graph, "free_cell", "available_cell", "free", fallback=layout_slot_part)
    packed_item_part = _part_name(asset_graph, "packed_item", "packed", "placed_object", fallback=placement_footprint_part)
    collision_pair_part = _part_name(asset_graph, "collision_pair", "collision", "pair", fallback=collision_rule_part)
    room_packing_solver_part = _part_name(asset_graph, "room_packing_solver", "packing_solver", "transform_solver", fallback=footprint_packer_part)
    packing_slot_part = _part_name(asset_graph, "packing_slot", "slot", "transform_slot", fallback=layout_slot_part)
    packed_transform_part = _part_name(asset_graph, "packed_transform", "resolved_transform", "placed_item", fallback=packed_item_part)
    clearance_reservation_part = _part_name(asset_graph, "clearance_reservation", "reserved_clearance", "clearance", fallback=clearance_zone_part)
    service_anchor_map_part = _part_name(asset_graph, "service_anchor_map", "service_anchor", "service_map", fallback=service_reach_part)
    service_anchor_part = _part_name(asset_graph, "service_anchor", "service_socket", "anchor", fallback=service_placement_part)
    room_content_plan_part = _part_name(asset_graph, "room_content_plan", "content_plan", "room_content", fallback=room_packing_solver_part)
    content_family_binding_part = _part_name(asset_graph, "content_family_binding", "family_binding", "asset_family", fallback=packed_item_part)
    furniture_asset_part = _part_name(asset_graph, "furniture_asset", "furniture", "generated_furniture", fallback=packed_transform_part)
    fixture_asset_part = _part_name(asset_graph, "fixture_asset", "fixture", "generated_fixture", fallback=packed_transform_part)
    packed_child_asset_part = _part_name(asset_graph, "packed_child_asset", "child_asset", "generated_child", fallback=packed_transform_part)
    content_surface_plan_part = _part_name(asset_graph, "content_surface_plan", "content_surface", "surface_plan", fallback=surface_layer_part)
    content_material_zone_part = _part_name(asset_graph, "content_material_zone", "content_zone", "material_zone", fallback=material_zone_part)
    content_finish_preset_part = _part_name(asset_graph, "content_finish_preset", "finish_preset", "surface_finish", fallback=surface_layer_part)
    content_wear_profile_part = _part_name(asset_graph, "content_wear_profile", "content_wear", "wear_profile", fallback=wear_part)
    content_marking_set_part = _part_name(asset_graph, "content_marking_set", "content_marking", "decal_set", fallback=decal_part)
    room_pack_preset_part = _part_name(asset_graph, "room_pack_preset", "room_preset", "pack_preset", fallback=footprint_packer_part)
    footprint_size_preset_part = _part_name(asset_graph, "footprint_size_preset", "size_preset", "footprint", fallback=placement_footprint_part)
    packing_policy_preset_part = _part_name(asset_graph, "packing_policy_preset", "packing_policy", "policy", fallback=fit_profile_part)
    clearance_preset_part = _part_name(asset_graph, "clearance_preset", "clearance_profile", "clearance", fallback=clearance_zone_part)
    service_reach_preset_part = _part_name(asset_graph, "service_reach_preset", "service_profile", "service_reach", fallback=service_reach_part)
    role_item_set_part = _part_name(asset_graph, "role_item_set", "item_set", "preset_items", fallback=packed_item_part)
    preset_item_part = _part_name(asset_graph, "preset_item", "role_item", "item", fallback=packed_item_part)
    role_preset_part = _part_name(asset_graph, "role_preset", "preset", "role", fallback=room_pack_preset_part)
    policy_rule_part = _part_name(asset_graph, "policy_rule", "packing_rule", "rule", fallback=packing_policy_preset_part)
    foliage_part = _part_name(asset_graph, "foliage", fallback="foliage_cluster")
    foliage_bush_part = _part_name(asset_graph, "foliage", "bush", fallback=foliage_part)
    foliage_grass_part = _part_name(asset_graph, "foliage", "grass", fallback=foliage_part)
    foliage_rock_part = _part_name(asset_graph, "foliage", "rock", fallback=foliage_part)
    foliage_flower_part = _part_name(asset_graph, "foliage", "flower", fallback=foliage_part)
    socket_part = _part_name(asset_graph, "module", "socket", fallback="module_socket")

    components = [
        _component(
            "setpiece_ground_region",
            "terrain",
            terrain_part,
            (0.0, -height * 0.035, 0.0),
            (width, height * 0.07, depth),
            tags=["setpiece", "terrain", "ground", archetype, layout],
        ),
        _component(
            "setpiece_foundation_pad_region",
            "lot",
            base_part,
            (0.0, height * 0.025, 0.0),
            (width * 0.86, height * 0.06, depth * 0.74),
            tags=["setpiece", "base", "foundation", archetype, layout],
            adjacency=[terrain_part],
        ),
        _component(
            "setpiece_courtyard_region",
            "lot",
            courtyard_part,
            (0.0, height * 0.065, depth * 0.08),
            (width * 0.36, height * 0.04, depth * 0.26),
            tags=["setpiece", "courtyard", "assembly_space", archetype, layout],
            adjacency=[base_part, road_part],
        ),
    ]

    for index in range(site_compound_marker_count):
        inset = max(0.64, 0.96 - index * 0.045)
        components.append(
            _component(
                f"setpiece_site_compound_{index:02d}_boundary_region",
                "site_compound_boundary",
                site_compound_part,
                (0.0, height * 0.090, 0.0),
                (width * inset, height * 0.025, depth * inset),
                tags=["setpiece", "site_layout", "site_compound", "compound_boundary", archetype, layout, f"site_compound_{index}"],
                adjacency=[terrain_part, base_part, courtyard_part],
            )
        )

    if building_lot_marker_count:
        columns = max(1, min(4, int(np.ceil(building_lot_marker_count**0.5))))
        rows = max(1, (building_lot_marker_count + columns - 1) // columns)
        for index in range(building_lot_marker_count):
            column = index % columns
            row = index // columns
            x = -width * 0.30 + width * 0.60 * ((column + 0.5) / max(1, columns))
            z = -depth * 0.18 + depth * 0.36 * ((row + 0.5) / max(1, rows))
            components.append(
                _component(
                    f"setpiece_building_lot_{index:02d}_pad_region",
                    "building_lot_pad",
                    building_lot_part,
                    (x, height * 0.115, z),
                    (width * 0.16, height * 0.035, depth * 0.14),
                    tags=["setpiece", "site_layout", "building_lot", "lot_pad", archetype, layout, f"building_lot_{index}"],
                    adjacency=[site_compound_part, building_part, base_part],
                )
            )

    for index in range(courtyard_plan_marker_count):
        z = depth * (0.02 - index * 0.08)
        components.append(
            _component(
                f"setpiece_courtyard_plan_{index:02d}_reserve_region",
                "courtyard_plan_reserve",
                courtyard_plan_part,
                (0.0, height * 0.125, z),
                (width * 0.32, height * 0.020, depth * 0.20),
                tags=["setpiece", "site_layout", "courtyard_plan", "public_space", archetype, layout, f"courtyard_plan_{index}"],
                adjacency=[courtyard_part, pedestrian_path_part],
            )
        )

    for index in range(pedestrian_path_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, pedestrian_path_marker_count))
        components.append(
            _component(
                f"setpiece_pedestrian_path_{index:02d}_walk_region",
                "pedestrian_path_strip",
                pedestrian_path_part,
                (x, height * 0.140, depth * 0.34),
                (width * 0.070, height * 0.018, depth * 0.44),
                tags=["setpiece", "site_layout", "pedestrian_path", "walkway", archetype, layout, f"pedestrian_path_{index}"],
                adjacency=[courtyard_plan_part, access_part],
            )
        )

    for index in range(service_alley_marker_count):
        x = width * 0.34 - width * 0.68 * ((index + 0.5) / max(1, service_alley_marker_count))
        components.append(
            _component(
                f"setpiece_service_alley_{index:02d}_lane_region",
                "service_alley_lane",
                service_alley_part,
                (x, height * 0.135, -depth * 0.38),
                (width * 0.090, height * 0.022, depth * 0.36),
                tags=["setpiece", "site_layout", "service_alley", "service_lane", archetype, layout, f"service_alley_{index}"],
                adjacency=[loading_zone_part, exterior_utility_part, maintenance_access_part],
            )
        )

    for index in range(parking_zone_marker_count):
        z = -depth * 0.16 + depth * 0.18 * ((index + 0.5) / max(1, parking_zone_marker_count))
        components.append(
            _component(
                f"setpiece_parking_zone_{index:02d}_apron_region",
                "parking_zone_apron",
                parking_zone_part,
                (-width * 0.36, height * 0.120, z),
                (width * 0.20, height * 0.024, depth * 0.18),
                tags=["setpiece", "site_layout", "parking_zone", "vehicle_apron", archetype, layout, f"parking_zone_{index}"],
                adjacency=[base_part, pedestrian_path_part, road_part],
            )
        )

    if parking_bay_marker_count:
        columns = 2
        rows = max(1, (parking_bay_marker_count + columns - 1) // columns)
        for index in range(parking_bay_marker_count):
            column = index % columns
            row = index // columns
            x = -width * 0.41 + width * 0.10 * ((column + 0.5) / max(1, columns))
            z = -depth * 0.26 + depth * 0.26 * ((row + 0.5) / max(1, rows))
            components.append(
                _component(
                    f"setpiece_parking_bay_{index:02d}_stall_region",
                    "parking_bay_stall",
                    parking_bay_part,
                    (x, height * 0.150, z),
                    (width * 0.040, height * 0.016, depth * 0.052),
                    tags=["setpiece", "site_layout", "parking_bay", "vehicle_stall", archetype, layout, f"parking_bay_{index}"],
                    adjacency=[parking_zone_part, road_part],
                )
            )

    for index in range(loading_zone_marker_count):
        z = -depth * 0.20 + depth * 0.20 * ((index + 0.5) / max(1, loading_zone_marker_count))
        components.append(
            _component(
                f"setpiece_loading_zone_{index:02d}_dock_apron_region",
                "loading_zone_apron",
                loading_zone_part,
                (width * 0.36, height * 0.135, z),
                (width * 0.18, height * 0.026, depth * 0.16),
                tags=["setpiece", "site_layout", "loading_zone", "dock_apron", archetype, layout, f"loading_zone_{index}"],
                adjacency=[loading_dock_part, service_alley_part, road_part],
            )
        )

    for index in range(exterior_utility_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, exterior_utility_marker_count))
        components.append(
            _component(
                f"setpiece_exterior_utility_{index:02d}_spine_region",
                "exterior_utility_spine",
                exterior_utility_part,
                (x, height * 0.155, -depth * 0.48),
                (width * 0.075, height * 0.030, depth * 0.035),
                tags=["setpiece", "site_layout", "exterior_utility", "utility_spine", archetype, layout, f"exterior_utility_{index}"],
                adjacency=[utility_corridor_part, service_connection_part, service_alley_part],
            )
        )

    if actor_marker_count:
        columns = max(1, min(12, round(actor_marker_count**0.5)))
        rows = max(1, (actor_marker_count + columns - 1) // columns)
        for index in range(actor_marker_count):
            column = index % columns
            row = index // columns
            x = -width * 0.26 + width * 0.52 * ((column + 0.5) / max(1, columns) - 0.5)
            z = -depth * 0.18 + depth * 0.36 * ((row + 0.5) / max(1, rows) - 0.5)
            components.append(
                _component(
                    f"setpiece_actor_{index:02d}_body_region",
                    "actor_body",
                    actor_body_part,
                    (x, height * 0.34, z),
                    (width * 0.035, height * 0.42, depth * 0.035),
                    tags=["setpiece", "actor", "npc", archetype, layout, f"actor_{index}"],
                    adjacency=[base_part, courtyard_part],
                )
            )
            components.append(
                _component(
                    f"setpiece_actor_{index:02d}_head_region",
                    "actor_head",
                    actor_head_part,
                    (x, height * 0.62, z),
                    (width * 0.045, height * 0.09, depth * 0.045),
                    tags=["setpiece", "actor", "head", archetype, layout, f"actor_{index}"],
                    adjacency=[actor_body_part],
                )
            )
            if index % 2 == 0:
                components.append(
                    _component(
                        f"setpiece_actor_{index:02d}_loadout_region",
                        "actor_loadout",
                        actor_pack_part,
                        (x, height * 0.36, z - depth * 0.035),
                        (width * 0.028, height * 0.18, depth * 0.022),
                        tags=["setpiece", "actor", "loadout", archetype, layout, f"actor_{index}"],
                        adjacency=[actor_body_part],
                    )
                )

    for index in range(spawn_marker_count):
        angle = (2.0 * np.pi * index) / max(1, spawn_marker_count)
        x = np.cos(angle) * width * 0.28
        z = np.sin(angle) * depth * 0.22
        components.append(
            _component(
                f"setpiece_spawn_{index:02d}_nest_region",
                "spawn_nest",
                spawn_marker_part,
                (x, height * 0.10, z),
                (width * 0.075, height * 0.08, depth * 0.075),
                tags=["setpiece", "spawn", "ecology", archetype, layout, f"spawn_{index}"],
                adjacency=[terrain_part, base_part],
            )
        )

    for index in range(behavior_node_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, behavior_node_count))
        z = depth * 0.30
        components.append(
            _component(
                f"setpiece_behavior_node_{index:02d}_region",
                "behavior_node",
                behavior_node_part,
                (x, height * 0.20, z),
                (width * 0.055, height * 0.28, depth * 0.04),
                tags=["setpiece", "behavior", "simulation_node", archetype, layout, f"behavior_node_{index}"],
                adjacency=[courtyard_part, road_part],
            )
        )

    for index in range(state_node_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, state_node_count))
        z = -depth * 0.32
        components.append(
            _component(
                f"setpiece_state_node_{index:02d}_region",
                "state_node",
                state_node_part,
                (x, height * 0.18, z),
                (width * 0.050, height * 0.24, depth * 0.035),
                tags=["setpiece", "stateful", "state_node", archetype, layout, f"state_node_{index}"],
                adjacency=[courtyard_part, road_part],
            )
        )
        if index > 0:
            components.append(
                _component(
                    f"setpiece_state_link_{index:02d}_region",
                    "state_link",
                    state_node_part,
                    (x - width * 0.60 / max(1, state_node_count) * 0.5, height * 0.12, z),
                    (width * 0.035, height * 0.035, depth * 0.020),
                    tags=["setpiece", "stateful", "state_transition", archetype, layout, f"state_link_{index}"],
                    adjacency=[state_node_part],
                )
            )

    for index in range(event_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, event_marker_count))
        z = depth * 0.40
        components.append(
            _component(
                f"setpiece_event_marker_{index:02d}_region",
                "event_marker",
                event_marker_part,
                (x, height * 0.22, z),
                (width * 0.045, height * 0.30, depth * 0.035),
                tags=["setpiece", "stateful", "event", "signal", archetype, layout, f"event_{index}"],
                adjacency=[road_part, courtyard_part],
            )
        )

    for index in range(trigger_marker_count):
        angle = (2.0 * np.pi * index) / max(1, trigger_marker_count)
        x = np.cos(angle) * width * 0.35
        z = np.sin(angle) * depth * 0.30
        components.append(
            _component(
                f"setpiece_trigger_volume_{index:02d}_region",
                "trigger_volume",
                trigger_marker_part,
                (x, height * 0.08, z),
                (width * 0.085, height * 0.045, depth * 0.085),
                tags=["setpiece", "stateful", "trigger_volume", archetype, layout, f"trigger_{index}"],
                adjacency=[terrain_part, road_part],
            )
        )

    for index in range(animation_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, animation_marker_count))
        z = -depth * 0.42
        components.append(
            _component(
                f"setpiece_animation_key_{index:02d}_region",
                "animation_key",
                animation_marker_part,
                (x, height * 0.16, z),
                (width * 0.042, height * 0.18, depth * 0.030),
                tags=["setpiece", "animation", "timeline", "keyframe", archetype, layout, f"animation_key_{index}"],
                adjacency=[state_node_part, road_part],
            )
        )
        if index > 0:
            components.append(
                _component(
                    f"setpiece_animation_span_{index:02d}_region",
                    "animation_span",
                    animation_marker_part,
                    (x - width * 0.76 / max(1, animation_marker_count) * 0.5, height * 0.10, z),
                    (width * 0.040, height * 0.025, depth * 0.018),
                    tags=["setpiece", "animation", "timeline_span", archetype, layout, f"animation_span_{index}"],
                    adjacency=[animation_marker_part],
                )
            )

    for index in range(moving_part_marker_count):
        x = -width * 0.25 + width * 0.50 * ((index + 0.5) / max(1, moving_part_marker_count))
        z = depth * 0.02
        components.append(
            _component(
                f"setpiece_moving_part_{index:02d}_hinge_region",
                "moving_part_hinge",
                moving_part_marker_part,
                (x, height * 0.24, z),
                (width * 0.060, height * 0.12, depth * 0.025),
                tags=["setpiece", "animation", "moving_part", "hinge", archetype, layout, f"moving_part_{index}"],
                adjacency=[access_part, utility_part],
            )
        )
        components.append(
            _component(
                f"setpiece_moving_part_{index:02d}_travel_region",
                "moving_part_travel",
                moving_part_marker_part,
                (x + width * 0.045, height * 0.24, z),
                (width * 0.070, height * 0.030, depth * 0.018),
                tags=["setpiece", "animation", "motion_path", archetype, layout, f"moving_part_{index}"],
                adjacency=[moving_part_marker_part, road_part],
            )
        )

    for index in range(effect_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, effect_marker_count))
        z = depth * 0.46
        components.append(
            _component(
                f"setpiece_effect_cue_{index:02d}_region",
                "effect_cue",
                effect_marker_part,
                (x, height * 0.36, z),
                (width * 0.040, height * 0.18, depth * 0.040),
                tags=["setpiece", "animation", "effect", "cue", archetype, layout, f"effect_cue_{index}"],
                adjacency=[event_marker_part, utility_part],
            )
        )

    for index in range(physics_body_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, physics_body_marker_count))
        z = -depth * 0.02
        components.append(
            _component(
                f"setpiece_physics_body_{index:02d}_region",
                "physics_body_marker",
                physics_body_part,
                (x, height * 0.18, z),
                (width * 0.055, height * 0.12, depth * 0.045),
                tags=["setpiece", "physics", "rigid_body", "collider", archetype, layout, f"physics_body_{index}"],
                adjacency=[base_part, prop_part],
            )
        )

    for index in range(physics_joint_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, physics_joint_marker_count))
        z = depth * 0.12
        components.append(
            _component(
                f"setpiece_physics_joint_{index:02d}_region",
                "physics_joint_marker",
                physics_joint_part,
                (x, height * 0.28, z),
                (width * 0.040, height * 0.10, depth * 0.035),
                tags=["setpiece", "physics", "joint", "hinge", archetype, layout, f"physics_joint_{index}"],
                adjacency=[physics_body_part, moving_part_marker_part],
            )
        )

    for index in range(debris_marker_count):
        angle = (2.0 * np.pi * index) / max(1, debris_marker_count)
        radius_x = width * (0.12 + 0.22 * ((index % 5) / 4.0 if debris_marker_count > 1 else 0.5))
        radius_z = depth * (0.10 + 0.18 * ((index % 7) / 6.0 if debris_marker_count > 1 else 0.5))
        components.append(
            _component(
                f"setpiece_debris_{index:02d}_fragment_region",
                "debris_fragment",
                debris_part,
                (np.cos(angle) * radius_x, height * 0.08, np.sin(angle) * radius_z),
                (width * 0.030, height * 0.035, depth * 0.030),
                tags=["setpiece", "destruction", "debris", "fragment", archetype, layout, f"debris_{index}"],
                adjacency=[terrain_part, physics_body_part],
            )
        )

    for index in range(flexible_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, flexible_marker_count))
        z = depth * 0.24 + np.sin(index / max(1, flexible_marker_count - 1) * np.pi) * depth * 0.05
        components.append(
            _component(
                f"setpiece_flexible_{index:02d}_segment_region",
                "flexible_segment",
                flexible_part,
                (x, height * 0.34, z),
                (width * 0.052, height * 0.020, depth * 0.020),
                tags=["setpiece", "physics", "rope", "cable", "cloth", archetype, layout, f"flexible_{index}"],
                adjacency=[utility_part, physics_joint_part],
            )
        )

    for index in range(force_field_marker_count):
        angle = (2.0 * np.pi * index) / max(1, force_field_marker_count)
        components.append(
            _component(
                f"setpiece_force_field_{index:02d}_region",
                "force_field_marker",
                force_field_part,
                (np.cos(angle) * width * 0.18, height * 0.30, np.sin(angle) * depth * 0.18),
                (width * 0.075, height * 0.16, depth * 0.075),
                tags=["setpiece", "physics", "force_field", "impulse", archetype, layout, f"force_field_{index}"],
                adjacency=[effect_marker_part, physics_body_part],
            )
        )

    for index in range(surface_layer_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, surface_layer_marker_count))
        z = -depth * 0.48
        components.append(
            _component(
                f"setpiece_surface_layer_{index:02d}_sample_region",
                "surface_layer_marker",
                surface_layer_part,
                (x, height * 0.11, z),
                (width * 0.070, height * 0.025, depth * 0.050),
                tags=["setpiece", "surface", "material_layer", "paint_stack", archetype, layout, f"surface_layer_{index}"],
                adjacency=[base_part, material_zone_part],
            )
        )

    for index in range(material_zone_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, material_zone_marker_count))
        z = -depth * 0.56
        components.append(
            _component(
                f"setpiece_material_zone_{index:02d}_region",
                "material_zone_marker",
                material_zone_part,
                (x, height * 0.135, z),
                (width * 0.052, height * 0.035, depth * 0.052),
                tags=["setpiece", "surface", "material_zone", "zone_mask", archetype, layout, f"material_zone_{index}"],
                adjacency=[surface_layer_part, base_part],
            )
        )

    for index in range(decal_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, decal_marker_count))
        z = depth * 0.54
        components.append(
            _component(
                f"setpiece_decal_{index:02d}_mark_region",
                "decal_marker",
                decal_part,
                (x, height * 0.38, z),
                (width * 0.038, height * 0.012, depth * 0.028),
                tags=["setpiece", "surface", "decal", "marking", archetype, layout, f"decal_{index}"],
                adjacency=[effect_marker_part, surface_layer_part],
            )
        )

    for index in range(wear_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, wear_marker_count))
        z = -depth * 0.40 + np.sin(index * 1.3) * depth * 0.035
        components.append(
            _component(
                f"setpiece_wear_{index:02d}_scratch_region",
                "wear_pattern_marker",
                wear_part,
                (x, height * 0.18, z),
                (width * 0.040, height * 0.012, depth * 0.010),
                tags=["setpiece", "surface", "wear", "scratch", "edge_wear", archetype, layout, f"wear_{index}"],
                adjacency=[surface_layer_part, material_zone_part],
            )
        )

    for index in range(damage_surface_marker_count):
        angle = (2.0 * np.pi * index) / max(1, damage_surface_marker_count)
        radius_x = width * (0.10 + 0.18 * ((index % 6) / 5.0 if damage_surface_marker_count > 1 else 0.5))
        radius_z = depth * (0.08 + 0.16 * ((index % 5) / 4.0 if damage_surface_marker_count > 1 else 0.5))
        components.append(
            _component(
                f"setpiece_damage_surface_{index:02d}_mark_region",
                "damage_surface_marker",
                damage_surface_part,
                (np.cos(angle) * radius_x, height * 0.205, np.sin(angle) * radius_z),
                (width * 0.044, height * 0.018, depth * 0.014),
                tags=["setpiece", "surface", "damage", "crack", "scorch", archetype, layout, f"damage_surface_{index}"],
                adjacency=[debris_part, wear_part],
            )
        )

    for index in range(surface_transition_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, surface_transition_marker_count))
        z = -depth * 0.52 + depth * 0.035 * ((index % 3) - 1)
        components.append(
            _component(
                f"setpiece_surface_transition_{index:02d}_band_region",
                "surface_transition_marker",
                surface_transition_part,
                (x, height * 0.155, z),
                (width * 0.060, height * 0.016, depth * 0.018),
                tags=["setpiece", "surface", "transition", "exposed_edge", archetype, layout, f"surface_transition_{index}"],
                adjacency=[surface_layer_part, material_zone_part],
            )
        )

    for index in range(weather_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, weather_marker_count))
        z = depth * 0.58
        components.append(
            _component(
                f"setpiece_weather_{index:02d}_effect_region",
                "weather_effect_marker",
                weather_part,
                (x, height * 0.62, z),
                (width * 0.060, height * 0.20, depth * 0.040),
                tags=["setpiece", "environment", "weather", "effect", archetype, layout, f"weather_{index}"],
                adjacency=[atmosphere_part, effect_marker_part],
            )
        )

    for index in range(atmosphere_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, atmosphere_marker_count))
        z = depth * 0.62
        components.append(
            _component(
                f"setpiece_atmosphere_{index:02d}_layer_region",
                "atmosphere_marker",
                atmosphere_part,
                (x, height * 0.78, z),
                (width * 0.090, height * 0.055, depth * 0.030),
                tags=["setpiece", "environment", "atmosphere", "sky", "cloud", archetype, layout, f"atmosphere_{index}"],
                adjacency=[weather_part, time_part],
            )
        )

    for index in range(wind_marker_count):
        x = -width * 0.45 + width * 0.90 * ((index + 0.5) / max(1, wind_marker_count))
        z = depth * 0.34 + np.sin(index * 1.1) * depth * 0.04
        components.append(
            _component(
                f"setpiece_wind_{index:02d}_gust_region",
                "wind_zone_marker",
                wind_part,
                (x, height * 0.52, z),
                (width * 0.080, height * 0.020, depth * 0.016),
                tags=["setpiece", "environment", "wind", "gust", "flow", archetype, layout, f"wind_{index}"],
                adjacency=[weather_part, flexible_part],
            )
        )

    for index in range(liquid_marker_count):
        angle = (2.0 * np.pi * index) / max(1, liquid_marker_count)
        radius_x = width * (0.10 + 0.20 * ((index % 7) / 6.0 if liquid_marker_count > 1 else 0.5))
        radius_z = depth * (0.08 + 0.18 * ((index % 5) / 4.0 if liquid_marker_count > 1 else 0.5))
        components.append(
            _component(
                f"setpiece_liquid_{index:02d}_wet_region",
                "liquid_body_marker",
                liquid_part,
                (np.cos(angle) * radius_x, height * 0.065, np.sin(angle) * radius_z),
                (width * 0.060, height * 0.010, depth * 0.045),
                tags=["setpiece", "environment", "liquid", "puddle", "wetness", archetype, layout, f"liquid_{index}"],
                adjacency=[terrain_part, surface_layer_part],
            )
        )

    for index in range(fire_marker_count):
        x = -width * 0.24 + width * 0.48 * ((index + 0.5) / max(1, fire_marker_count))
        z = depth * 0.16
        components.append(
            _component(
                f"setpiece_fire_{index:02d}_source_region",
                "fire_source_marker",
                fire_part,
                (x, height * 0.35, z),
                (width * 0.045, height * 0.18, depth * 0.045),
                tags=["setpiece", "environment", "fire", "heat", "emissive", archetype, layout, f"fire_{index}"],
                adjacency=[smoke_part, effect_marker_part],
            )
        )

    for index in range(smoke_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, smoke_marker_count))
        z = depth * 0.24 + np.sin(index * 0.9) * depth * 0.06
        components.append(
            _component(
                f"setpiece_smoke_{index:02d}_volume_region",
                "smoke_mist_marker",
                smoke_part,
                (x, height * 0.66, z),
                (width * 0.070, height * 0.14, depth * 0.050),
                tags=["setpiece", "environment", "smoke", "mist", "fog", archetype, layout, f"smoke_{index}"],
                adjacency=[fire_part, atmosphere_part],
            )
        )

    for index in range(time_marker_count):
        x = -width * 0.18 + width * 0.36 * ((index + 0.5) / max(1, time_marker_count))
        z = depth * 0.64
        components.append(
            _component(
                f"setpiece_time_of_day_{index:02d}_light_region",
                "time_of_day_marker",
                time_part,
                (x, height * 0.86, z),
                (width * 0.045, height * 0.045, depth * 0.045),
                tags=["setpiece", "environment", "time_of_day", "lighting", archetype, layout, f"time_{index}"],
                adjacency=[atmosphere_part, effect_marker_part],
            )
        )

    for index in range(shot_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, shot_marker_count))
        z = -depth * 0.62
        components.append(
            _component(
                f"setpiece_shot_{index:02d}_frustum_region",
                "shot_camera_marker",
                shot_part,
                (x, height * 0.48, z),
                (width * 0.045, height * 0.075, depth * 0.055),
                tags=["setpiece", "camera", "shot", "frustum", archetype, layout, f"shot_{index}"],
                adjacency=[focal_part, camera_volume_part],
            )
        )

    for index in range(camera_rail_marker_count):
        x = -width * 0.44 + width * 0.88 * ((index + 0.5) / max(1, camera_rail_marker_count))
        z = -depth * 0.68
        components.append(
            _component(
                f"setpiece_camera_rail_{index:02d}_path_region",
                "camera_rail_marker",
                camera_rail_part,
                (x, height * 0.22, z),
                (width * 0.080, height * 0.018, depth * 0.016),
                tags=["setpiece", "camera", "rail", "dolly", "path", archetype, layout, f"camera_rail_{index}"],
                adjacency=[shot_part, access_part],
            )
        )

    for index in range(focal_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, focal_marker_count))
        z = -depth * 0.18 + np.sin(index * 1.4) * depth * 0.05
        components.append(
            _component(
                f"setpiece_focal_{index:02d}_target_region",
                "focal_target_marker",
                focal_part,
                (x, height * 0.34, z),
                (width * 0.034, height * 0.034, depth * 0.034),
                tags=["setpiece", "camera", "focus", "look_at_target", archetype, layout, f"focal_{index}"],
                adjacency=[shot_part, courtyard_part],
            )
        )

    for index in range(camera_volume_marker_count):
        x = -width * 0.24 + width * 0.48 * ((index + 0.5) / max(1, camera_volume_marker_count))
        z = -depth * 0.30
        components.append(
            _component(
                f"setpiece_camera_volume_{index:02d}_region",
                "camera_volume_marker",
                camera_volume_part,
                (x, height * 0.42, z),
                (width * 0.085, height * 0.12, depth * 0.060),
                tags=["setpiece", "camera", "volume", "presentation", archetype, layout, f"camera_volume_{index}"],
                adjacency=[shot_part, focal_part],
            )
        )

    for index in range(cutscene_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, cutscene_marker_count))
        z = -depth * 0.72
        components.append(
            _component(
                f"setpiece_cutscene_{index:02d}_beat_region",
                "cutscene_beat_marker",
                cutscene_part,
                (x, height * 0.26, z),
                (width * 0.040, height * 0.070, depth * 0.024),
                tags=["setpiece", "camera", "cutscene", "shot_sequence", archetype, layout, f"cutscene_{index}"],
                adjacency=[animation_marker_part, shot_part],
            )
        )

    for index in range(ambient_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, ambient_marker_count))
        z = depth * 0.72
        components.append(
            _component(
                f"setpiece_ambient_bed_{index:02d}_soundscape_region",
                "ambient_bed_marker",
                ambient_part,
                (x, height * 0.18, z),
                (width * 0.120, height * 0.035, depth * 0.090),
                tags=["setpiece", "audio", "ambient_bed", "soundscape", archetype, layout, f"ambient_{index}"],
                adjacency=[sound_zone_part, atmosphere_part],
            )
        )

    for index in range(sound_zone_marker_count):
        angle = (2.0 * np.pi * index) / max(1, sound_zone_marker_count)
        x = np.cos(angle) * width * 0.36
        z = np.sin(angle) * depth * 0.36
        components.append(
            _component(
                f"setpiece_sound_zone_{index:02d}_attenuation_region",
                "sound_zone_marker",
                sound_zone_part,
                (x, height * 0.20, z),
                (width * 0.070, height * 0.070, depth * 0.070),
                tags=["setpiece", "audio", "sound_zone", "attenuation", archetype, layout, f"sound_zone_{index}"],
                adjacency=[ambient_part, listener_part],
            )
        )

    for index in range(reverb_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, reverb_marker_count))
        z = depth * 0.44
        components.append(
            _component(
                f"setpiece_reverb_space_{index:02d}_volume_region",
                "reverb_space_marker",
                reverb_part,
                (x, height * 0.34, z),
                (width * 0.090, height * 0.12, depth * 0.070),
                tags=["setpiece", "audio", "reverb_space", "room_tone", archetype, layout, f"reverb_{index}"],
                adjacency=[acoustic_material_part, sound_zone_part],
            )
        )

    for index in range(occlusion_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, occlusion_marker_count))
        z = depth * 0.28
        components.append(
            _component(
                f"setpiece_acoustic_occluder_{index:02d}_barrier_region",
                "acoustic_occluder_marker",
                occluder_part,
                (x, height * 0.30, z),
                (width * 0.080, height * 0.16, depth * 0.020),
                tags=["setpiece", "audio", "acoustic_occluder", "occlusion", archetype, layout, f"occluder_{index}"],
                adjacency=[surface_layer_part, reverb_part],
            )
        )

    for index in range(propagation_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, propagation_marker_count))
        z = depth * 0.18 + np.sin(index * 1.1) * depth * 0.06
        components.append(
            _component(
                f"setpiece_sound_propagation_{index:02d}_ray_region",
                "sound_propagation_marker",
                propagation_part,
                (x, height * 0.24, z),
                (width * 0.075, height * 0.025, depth * 0.018),
                tags=["setpiece", "audio", "sound_propagation", "raycast", archetype, layout, f"propagation_{index}"],
                adjacency=[sound_zone_part, occluder_part],
            )
        )

    for index in range(music_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, music_marker_count))
        z = -depth * 0.80
        components.append(
            _component(
                f"setpiece_music_state_{index:02d}_mix_node",
                "music_state_marker",
                music_part,
                (x, height * 0.30, z),
                (width * 0.045, height * 0.075, depth * 0.030),
                tags=["setpiece", "audio", "music_state", "transition", "stinger", archetype, layout, f"music_{index}"],
                adjacency=[cutscene_part, listener_part],
            )
        )

    for index in range(foley_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, foley_marker_count))
        z = -depth * 0.08
        components.append(
            _component(
                f"setpiece_foley_emitter_{index:02d}_event_region",
                "foley_emitter_marker",
                foley_part,
                (x, height * 0.16, z),
                (width * 0.038, height * 0.045, depth * 0.038),
                tags=["setpiece", "audio", "foley_emitter", "event", archetype, layout, f"foley_{index}"],
                adjacency=[sound_zone_part, acoustic_material_part],
            )
        )

    for index in range(listener_marker_count):
        x = -width * 0.24 + width * 0.48 * ((index + 0.5) / max(1, listener_marker_count))
        z = depth * 0.06
        components.append(
            _component(
                f"setpiece_listener_zone_{index:02d}_blend_region",
                "listener_zone_marker",
                listener_part,
                (x, height * 0.26, z),
                (width * 0.060, height * 0.080, depth * 0.050),
                tags=["setpiece", "audio", "listener_zone", "audio_bus", "mix", archetype, layout, f"listener_{index}"],
                adjacency=[sound_zone_part, reverb_part],
            )
        )

    for index in range(acoustic_material_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, acoustic_material_marker_count))
        z = depth * 0.34
        components.append(
            _component(
                f"setpiece_acoustic_material_{index:02d}_surface_region",
                "acoustic_material_marker",
                acoustic_material_part,
                (x, height * 0.12, z),
                (width * 0.055, height * 0.018, depth * 0.045),
                tags=["setpiece", "audio", "acoustic_material", "absorption", "reflection", archetype, layout, f"acoustic_material_{index}"],
                adjacency=[material_zone_part, occluder_part],
            )
        )

    for index in range(prompt_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, prompt_marker_count))
        z = -depth * 0.42
        components.append(
            _component(
                f"setpiece_interaction_prompt_{index:02d}_label_region",
                "interaction_prompt_marker",
                interaction_prompt_part,
                (x, height * 0.48, z),
                (width * 0.050, height * 0.030, depth * 0.014),
                tags=["setpiece", "interaction", "prompt", "label", archetype, layout, f"prompt_{index}"],
                adjacency=[usable_part, ui_anchor_part],
            )
        )

    for index in range(interaction_zone_marker_count):
        angle = (2.0 * np.pi * index) / max(1, interaction_zone_marker_count)
        x = np.cos(angle) * width * 0.30
        z = -depth * 0.20 + np.sin(angle) * depth * 0.20
        components.append(
            _component(
                f"setpiece_interaction_zone_{index:02d}_range_region",
                "interaction_zone_marker",
                interaction_zone_part,
                (x, height * 0.08, z),
                (width * 0.080, height * 0.018, depth * 0.080),
                tags=["setpiece", "interaction", "zone", "range", archetype, layout, f"interaction_zone_{index}"],
                adjacency=[trigger_marker_part, interaction_prompt_part],
            )
        )

    for index in range(usable_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, usable_marker_count))
        z = -depth * 0.34
        components.append(
            _component(
                f"setpiece_usable_{index:02d}_affordance_region",
                "usable_affordance_marker",
                usable_part,
                (x, height * 0.20, z),
                (width * 0.042, height * 0.060, depth * 0.042),
                tags=["setpiece", "interaction", "usable", "affordance", archetype, layout, f"usable_{index}"],
                adjacency=[interaction_zone_part, interaction_prompt_part],
            )
        )

    for index in range(pickup_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, pickup_marker_count))
        z = -depth * 0.04
        components.append(
            _component(
                f"setpiece_pickup_{index:02d}_item_region",
                "pickup_marker",
                pickup_part,
                (x, height * 0.13, z),
                (width * 0.034, height * 0.040, depth * 0.034),
                tags=["setpiece", "interaction", "pickup", "item", archetype, layout, f"pickup_{index}"],
                adjacency=[usable_part, inspect_part],
            )
        )

    for index in range(inspect_marker_count):
        x = -width * 0.28 + width * 0.56 * ((index + 0.5) / max(1, inspect_marker_count))
        z = depth * 0.10
        components.append(
            _component(
                f"setpiece_inspect_point_{index:02d}_lore_region",
                "inspect_point_marker",
                inspect_part,
                (x, height * 0.36, z),
                (width * 0.036, height * 0.036, depth * 0.018),
                tags=["setpiece", "interaction", "inspect_point", "lore", archetype, layout, f"inspect_{index}"],
                adjacency=[interaction_prompt_part, ui_anchor_part],
            )
        )

    for index in range(terminal_marker_count):
        x = -width * 0.26 + width * 0.52 * ((index + 0.5) / max(1, terminal_marker_count))
        z = depth * 0.26
        components.append(
            _component(
                f"setpiece_terminal_{index:02d}_screen_region",
                "terminal_marker",
                terminal_part,
                (x, height * 0.34, z),
                (width * 0.060, height * 0.100, depth * 0.020),
                tags=["setpiece", "interaction", "terminal", "screen", "diegetic_ui", archetype, layout, f"terminal_{index}"],
                adjacency=[control_panel_part, hud_part],
            )
        )

    for index in range(control_panel_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, control_panel_marker_count))
        z = depth * 0.18
        components.append(
            _component(
                f"setpiece_control_panel_{index:02d}_input_region",
                "control_panel_marker",
                control_panel_part,
                (x, height * 0.28, z),
                (width * 0.050, height * 0.080, depth * 0.024),
                tags=["setpiece", "interaction", "control_panel", "button", "switch", "lever", archetype, layout, f"control_{index}"],
                adjacency=[control_input_part, terminal_part],
            )
        )
        components.append(
            _component(
                f"setpiece_control_input_{index:02d}_button_region",
                "control_input_marker",
                control_input_part,
                (x + width * 0.040, height * 0.24, z - depth * 0.018),
                (width * 0.018, height * 0.030, depth * 0.018),
                tags=["setpiece", "interaction", "button", "switch", "lever", archetype, layout, f"input_{index}"],
                adjacency=[control_panel_part, event_marker_part],
            )
        )

    for index in range(door_lock_marker_count):
        x = -width * 0.22 + width * 0.44 * ((index + 0.5) / max(1, door_lock_marker_count))
        z = depth * 0.02
        components.append(
            _component(
                f"setpiece_door_lock_{index:02d}_keypad_region",
                "door_lock_marker",
                door_lock_part,
                (x, height * 0.30, z),
                (width * 0.030, height * 0.080, depth * 0.018),
                tags=["setpiece", "interaction", "door_lock", "keypad", archetype, layout, f"door_lock_{index}"],
                adjacency=[control_input_part, gate_part],
            )
        )

    for index in range(quest_ui_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, quest_ui_marker_count))
        z = -depth * 0.56
        components.append(
            _component(
                f"setpiece_quest_marker_{index:02d}_objective_region",
                "quest_marker",
                quest_marker_part,
                (x, height * 0.58, z),
                (width * 0.036, height * 0.070, depth * 0.020),
                tags=["setpiece", "interaction", "quest_marker", "objective", archetype, layout, f"quest_marker_{index}"],
                adjacency=[map_marker_part, ui_anchor_part],
            )
        )

    for index in range(signage_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, signage_marker_count))
        z = -depth * 0.48
        components.append(
            _component(
                f"setpiece_signage_{index:02d}_wayfinding_region",
                "signage_marker",
                signage_ui_part,
                (x, height * 0.42, z),
                (width * 0.070, height * 0.050, depth * 0.016),
                tags=["setpiece", "interaction", "signage", "wayfinding", archetype, layout, f"signage_{index}"],
                adjacency=[inspect_part, map_marker_part],
            )
        )

    for index in range(map_ui_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, map_ui_marker_count))
        z = -depth * 0.66
        components.append(
            _component(
                f"setpiece_map_marker_{index:02d}_waypoint_region",
                "map_marker",
                map_marker_part,
                (x, height * 0.50, z),
                (width * 0.034, height * 0.055, depth * 0.024),
                tags=["setpiece", "interaction", "map_marker", "waypoint", archetype, layout, f"map_marker_{index}"],
                adjacency=[quest_marker_part, road_part],
            )
        )

    for index in range(hud_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, hud_marker_count))
        z = -depth * 0.76
        components.append(
            _component(
                f"setpiece_diegetic_hud_{index:02d}_anchor_region",
                "diegetic_hud_marker",
                hud_part,
                (x, height * 0.64, z),
                (width * 0.055, height * 0.070, depth * 0.018),
                tags=["setpiece", "interaction", "diegetic_hud", "ui_anchor", archetype, layout, f"hud_{index}"],
                adjacency=[ui_anchor_part, terminal_part],
            )
        )
        components.append(
            _component(
                f"setpiece_ui_anchor_{index:02d}_widget_region",
                "ui_anchor_marker",
                ui_anchor_part,
                (x + width * 0.040, height * 0.58, z),
                (width * 0.026, height * 0.036, depth * 0.014),
                tags=["setpiece", "interaction", "ui_anchor", "widget", archetype, layout, f"ui_anchor_{index}"],
                adjacency=[hud_part, interaction_prompt_part],
            )
        )

    for index in range(mission_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, mission_marker_count))
        z = -depth * 0.86
        components.append(
            _component(
                f"setpiece_mission_{index:02d}_briefing_region",
                "mission_marker",
                mission_part,
                (x, height * 0.50, z),
                (width * 0.070, height * 0.065, depth * 0.020),
                tags=["setpiece", "gameplay", "mission", "quest", archetype, layout, f"mission_{index}"],
                adjacency=[objective_chain_part, reward_part],
            )
        )

    for index in range(objective_chain_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, objective_chain_marker_count))
        z = -depth * 0.90
        components.append(
            _component(
                f"setpiece_objective_chain_{index:02d}_task_region",
                "objective_chain_marker",
                objective_chain_part,
                (x, height * 0.42, z),
                (width * 0.048, height * 0.044, depth * 0.018),
                tags=["setpiece", "gameplay", "objective_chain", "task", archetype, layout, f"objective_{index}"],
                adjacency=[mission_part, quest_marker_part],
            )
        )

    for index in range(condition_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, condition_marker_count))
        z = -depth * 0.82 + np.sin(index * 1.2) * depth * 0.035
        components.append(
            _component(
                f"setpiece_gameplay_condition_{index:02d}_rule_region",
                "gameplay_condition_marker",
                condition_part,
                (x, height * 0.36, z),
                (width * 0.040, height * 0.038, depth * 0.018),
                tags=["setpiece", "gameplay", "condition", "success", "failure", archetype, layout, f"condition_{index}"],
                adjacency=[state_node_part, mission_part],
            )
        )

    for index in range(reward_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, reward_marker_count))
        z = -depth * 0.70
        components.append(
            _component(
                f"setpiece_reward_table_{index:02d}_reward_region",
                "reward_table_marker",
                reward_part,
                (x, height * 0.24, z),
                (width * 0.052, height * 0.045, depth * 0.040),
                tags=["setpiece", "gameplay", "reward_table", "reward", archetype, layout, f"reward_{index}"],
                adjacency=[loot_table_part, currency_part],
            )
        )

    for index in range(loot_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, loot_marker_count))
        z = -depth * 0.60
        components.append(
            _component(
                f"setpiece_loot_table_{index:02d}_drop_region",
                "loot_table_marker",
                loot_table_part,
                (x, height * 0.18, z),
                (width * 0.040, height * 0.035, depth * 0.040),
                tags=["setpiece", "gameplay", "loot_table", "loot", archetype, layout, f"loot_{index}"],
                adjacency=[reward_part, inventory_slot_part],
            )
        )

    for index in range(inventory_slot_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, inventory_slot_marker_count))
        z = -depth * 0.52
        components.append(
            _component(
                f"setpiece_inventory_slot_{index:02d}_slot_region",
                "inventory_slot_marker",
                inventory_slot_part,
                (x, height * 0.16, z),
                (width * 0.032, height * 0.032, depth * 0.032),
                tags=["setpiece", "gameplay", "inventory_slot", "item", archetype, layout, f"inventory_slot_{index}"],
                adjacency=[pickup_part, loot_table_part],
            )
        )

    for index in range(crafting_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, crafting_marker_count))
        z = depth * 0.52
        components.append(
            _component(
                f"setpiece_crafting_station_{index:02d}_recipe_region",
                "crafting_station_marker",
                crafting_part,
                (x, height * 0.28, z),
                (width * 0.065, height * 0.075, depth * 0.040),
                tags=["setpiece", "gameplay", "crafting_station", "recipe", archetype, layout, f"crafting_{index}"],
                adjacency=[control_panel_part, inventory_slot_part],
            )
        )

    for index in range(shop_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, shop_marker_count))
        z = depth * 0.62
        components.append(
            _component(
                f"setpiece_shop_{index:02d}_vendor_region",
                "shop_vendor_marker",
                shop_part,
                (x, height * 0.30, z),
                (width * 0.070, height * 0.090, depth * 0.045),
                tags=["setpiece", "gameplay", "shop", "vendor", "economy", archetype, layout, f"shop_{index}"],
                adjacency=[signage_ui_part, currency_part],
            )
        )

    for index in range(currency_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, currency_marker_count))
        z = depth * 0.70
        components.append(
            _component(
                f"setpiece_currency_{index:02d}_wallet_region",
                "currency_marker",
                currency_part,
                (x, height * 0.14, z),
                (width * 0.026, height * 0.026, depth * 0.026),
                tags=["setpiece", "gameplay", "currency", "economy", archetype, layout, f"currency_{index}"],
                adjacency=[reward_part, shop_part],
            )
        )

    for index in range(reputation_marker_count):
        x = -width * 0.28 + width * 0.56 * ((index + 0.5) / max(1, reputation_marker_count))
        z = depth * 0.78
        components.append(
            _component(
                f"setpiece_reputation_rule_{index:02d}_faction_region",
                "reputation_rule_marker",
                reputation_part,
                (x, height * 0.46, z),
                (width * 0.044, height * 0.054, depth * 0.020),
                tags=["setpiece", "gameplay", "reputation_rule", "faction", archetype, layout, f"reputation_{index}"],
                adjacency=[quest_marker_part, unlock_part],
            )
        )

    for index in range(unlock_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, unlock_marker_count))
        z = depth * 0.84
        components.append(
            _component(
                f"setpiece_unlock_rule_{index:02d}_gate_region",
                "unlock_rule_marker",
                unlock_part,
                (x, height * 0.34, z),
                (width * 0.042, height * 0.070, depth * 0.024),
                tags=["setpiece", "gameplay", "unlock_rule", "progression", archetype, layout, f"unlock_{index}"],
                adjacency=[door_lock_part, progression_part],
            )
        )

    for index in range(progression_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, progression_marker_count))
        z = depth * 0.90
        components.append(
            _component(
                f"setpiece_progression_track_{index:02d}_level_region",
                "progression_track_marker",
                progression_part,
                (x, height * 0.54, z),
                (width * 0.045, height * 0.080, depth * 0.020),
                tags=["setpiece", "gameplay", "progression_track", "level", archetype, layout, f"progression_{index}"],
                adjacency=[unlock_part, reward_part],
            )
        )

    for index in range(director_marker_count):
        x = -width * 0.32 + width * 0.64 * ((index + 0.5) / max(1, director_marker_count))
        z = -depth * 0.94
        components.append(
            _component(
                f"setpiece_director_{index:02d}_brain_region",
                "director_marker",
                director_part,
                (x, height * 0.62, z),
                (width * 0.070, height * 0.070, depth * 0.024),
                tags=["setpiece", "director", "encounter_director", "ai", archetype, layout, f"director_{index}"],
                adjacency=[pacing_part, threat_budget_part],
            )
        )

    for index in range(director_intent_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, director_intent_marker_count))
        z = -depth * 0.96
        components.append(
            _component(
                f"setpiece_director_intent_{index:02d}_goal_region",
                "director_intent_marker",
                director_intent_part,
                (x, height * 0.52, z),
                (width * 0.038, height * 0.048, depth * 0.018),
                tags=["setpiece", "director", "intent", "ai", archetype, layout, f"director_intent_{index}"],
                adjacency=[director_part, director_signal_part],
            )
        )

    for index in range(pacing_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, pacing_marker_count))
        z = -depth * 1.00
        components.append(
            _component(
                f"setpiece_pacing_curve_{index:02d}_beat_region",
                "pacing_curve_marker",
                pacing_part,
                (x, height * 0.44, z),
                (width * 0.050, height * 0.030, depth * 0.018),
                tags=["setpiece", "director", "pacing_curve", "encounter_beat", archetype, layout, f"pacing_{index}"],
                adjacency=[director_part, phase_part],
            )
        )

    for index in range(threat_budget_marker_count):
        x = -width * 0.30 + width * 0.60 * ((index + 0.5) / max(1, threat_budget_marker_count))
        z = -depth * 0.88
        components.append(
            _component(
                f"setpiece_threat_budget_{index:02d}_budget_region",
                "threat_budget_marker",
                threat_budget_part,
                (x, height * 0.36, z),
                (width * 0.052, height * 0.048, depth * 0.024),
                tags=["setpiece", "director", "threat_budget", "spawn_budget", archetype, layout, f"threat_budget_{index}"],
                adjacency=[spawn_wave_part, threat_zone_part],
            )
        )

    for index in range(spawn_wave_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, spawn_wave_marker_count))
        z = -depth * 0.34
        components.append(
            _component(
                f"setpiece_spawn_wave_{index:02d}_queue_region",
                "spawn_wave_marker",
                spawn_wave_part,
                (x, height * 0.22, z),
                (width * 0.052, height * 0.052, depth * 0.038),
                tags=["setpiece", "director", "spawn_wave", "spawn", archetype, layout, f"spawn_wave_{index}"],
                adjacency=[spawn_marker_part, reinforcement_route_part],
            )
        )

    for index in range(phase_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, phase_marker_count))
        z = -depth * 0.28
        components.append(
            _component(
                f"setpiece_director_phase_{index:02d}_state_region",
                "director_phase_marker",
                phase_part,
                (x, height * 0.32, z),
                (width * 0.058, height * 0.055, depth * 0.026),
                tags=["setpiece", "director", "combat_phase", "stealth_phase", archetype, layout, f"phase_{index}"],
                adjacency=[pacing_part, director_signal_part],
            )
        )

    for index in range(escalation_marker_count):
        x = -width * 0.28 + width * 0.56 * ((index + 0.5) / max(1, escalation_marker_count))
        z = -depth * 0.22
        components.append(
            _component(
                f"setpiece_escalation_rule_{index:02d}_difficulty_region",
                "escalation_rule_marker",
                escalation_part,
                (x, height * 0.40, z),
                (width * 0.045, height * 0.052, depth * 0.020),
                tags=["setpiece", "director", "escalation_rule", "adaptive_difficulty", archetype, layout, f"escalation_{index}"],
                adjacency=[condition_part, threat_budget_part],
            )
        )

    for index in range(director_signal_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, director_signal_marker_count))
        z = -depth * 0.16
        components.append(
            _component(
                f"setpiece_director_signal_{index:02d}_cue_region",
                "director_signal_marker",
                director_signal_part,
                (x, height * 0.30, z),
                (width * 0.034, height * 0.038, depth * 0.020),
                tags=["setpiece", "director", "director_signal", "cue", archetype, layout, f"director_signal_{index}"],
                adjacency=[event_marker_part, phase_part],
            )
        )

    for index in range(threat_zone_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, threat_zone_marker_count))
        z = -depth * 0.10
        components.append(
            _component(
                f"setpiece_threat_zone_{index:02d}_pressure_region",
                "threat_zone_marker",
                threat_zone_part,
                (x, height * 0.12, z),
                (width * 0.085, height * 0.022, depth * 0.085),
                tags=["setpiece", "director", "threat_zone", "pressure", archetype, layout, f"threat_zone_{index}"],
                adjacency=[spawn_wave_part, interaction_zone_part],
            )
        )

    for index in range(reinforcement_route_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, reinforcement_route_marker_count))
        z = -depth * 0.02
        components.append(
            _component(
                f"setpiece_reinforcement_route_{index:02d}_path_region",
                "reinforcement_route_marker",
                reinforcement_route_part,
                (x, height * 0.10, z),
                (width * 0.090, height * 0.020, depth * 0.020),
                tags=["setpiece", "director", "reinforcement_route", "spawn_route", archetype, layout, f"reinforcement_route_{index}"],
                adjacency=[road_part, spawn_wave_part],
            )
        )

    for index in range(simulation_layer_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, simulation_layer_marker_count))
        z = depth * 0.02
        components.append(
            _component(
                f"setpiece_simulation_layer_{index:02d}_world_state_region",
                "simulation_layer_marker",
                simulation_layer_part,
                (x, height * 0.56, z),
                (width * 0.070, height * 0.040, depth * 0.036),
                tags=["setpiece", "simulation_layer", "world_simulation", "systemic", archetype, layout, f"simulation_layer_{index}"],
                adjacency=[world_metric_part, field_part],
            )
        )

    for index in range(field_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, field_marker_count))
        z = depth * 0.10
        components.append(
            _component(
                f"setpiece_simulation_field_{index:02d}_sample_region",
                "simulation_field_marker",
                field_part,
                (x, height * 0.22, z),
                (width * 0.060, height * 0.020, depth * 0.060),
                tags=["setpiece", "simulation", "heat_field", "noise_field", "visibility_field", archetype, layout, f"field_{index}"],
                adjacency=[simulation_layer_part, simulation_probe_part],
            )
        )

    for index in range(resource_flow_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, resource_flow_marker_count))
        z = depth * 0.18
        components.append(
            _component(
                f"setpiece_resource_flow_{index:02d}_channel_region",
                "resource_flow_marker",
                resource_flow_part,
                (x, height * 0.12, z),
                (width * 0.090, height * 0.026, depth * 0.020),
                tags=["setpiece", "simulation", "resource_flow", "flow", archetype, layout, f"resource_flow_{index}"],
                adjacency=[simulation_layer_part, flow_gate_part],
            )
        )

    for index in range(faction_pressure_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, faction_pressure_marker_count))
        z = depth * 0.24
        components.append(
            _component(
                f"setpiece_faction_pressure_{index:02d}_influence_region",
                "faction_pressure_marker",
                faction_pressure_part,
                (x, height * 0.34, z),
                (width * 0.048, height * 0.044, depth * 0.026),
                tags=["setpiece", "simulation", "faction_pressure", "pressure", archetype, layout, f"faction_pressure_{index}"],
                adjacency=[world_metric_part, territory_part],
            )
        )

    for index in range(territory_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, territory_marker_count))
        z = depth * 0.30
        components.append(
            _component(
                f"setpiece_territory_influence_{index:02d}_claim_region",
                "territory_influence_marker",
                territory_part,
                (x, height * 0.20, z),
                (width * 0.070, height * 0.018, depth * 0.050),
                tags=["setpiece", "simulation", "territory_influence", "claim", archetype, layout, f"territory_{index}"],
                adjacency=[faction_pressure_part, world_metric_part],
            )
        )

    for index in range(alarm_grid_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, alarm_grid_marker_count))
        z = depth * 0.36
        components.append(
            _component(
                f"setpiece_alarm_grid_{index:02d}_security_region",
                "alarm_grid_marker",
                alarm_grid_part,
                (x, height * 0.48, z),
                (width * 0.050, height * 0.050, depth * 0.024),
                tags=["setpiece", "simulation", "alarm_grid", "security", archetype, layout, f"alarm_grid_{index}"],
                adjacency=[director_signal_part, sensor_grid_part],
            )
        )

    for index in range(patrol_density_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, patrol_density_marker_count))
        z = depth * 0.42
        components.append(
            _component(
                f"setpiece_patrol_density_{index:02d}_route_region",
                "patrol_density_marker",
                patrol_density_part,
                (x, height * 0.12, z),
                (width * 0.085, height * 0.018, depth * 0.018),
                tags=["setpiece", "simulation", "patrol_density", "route_density", archetype, layout, f"patrol_density_{index}"],
                adjacency=[reinforcement_route_part, sensor_grid_part],
            )
        )

    for index in range(hazard_field_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, hazard_field_marker_count))
        z = depth * 0.48
        components.append(
            _component(
                f"setpiece_hazard_field_{index:02d}_risk_region",
                "hazard_field_marker",
                hazard_field_part,
                (x, height * 0.16, z),
                (width * 0.070, height * 0.020, depth * 0.070),
                tags=["setpiece", "simulation", "hazard_field", "risk", archetype, layout, f"hazard_field_{index}"],
                adjacency=[threat_zone_part, simulation_probe_part],
            )
        )

    for index in range(sensor_grid_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, sensor_grid_marker_count))
        z = depth * 0.54
        components.append(
            _component(
                f"setpiece_sensor_grid_{index:02d}_coverage_region",
                "sensor_grid_marker",
                sensor_grid_part,
                (x, height * 0.26, z),
                (width * 0.038, height * 0.044, depth * 0.026),
                tags=["setpiece", "simulation", "sensor_grid", "coverage", archetype, layout, f"sensor_grid_{index}"],
                adjacency=[alarm_grid_part, simulation_probe_part],
            )
        )

    for index in range(cover_map_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, cover_map_marker_count))
        z = depth * 0.60
        components.append(
            _component(
                f"setpiece_cover_map_{index:02d}_occlusion_region",
                "cover_map_marker",
                cover_map_part,
                (x, height * 0.10, z),
                (width * 0.075, height * 0.018, depth * 0.045),
                tags=["setpiece", "simulation", "cover_map", "occlusion", archetype, layout, f"cover_map_{index}"],
                adjacency=[threat_zone_part, sensor_grid_part],
            )
        )

    for index in range(flow_gate_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, flow_gate_marker_count))
        z = depth * 0.66
        components.append(
            _component(
                f"setpiece_flow_gate_{index:02d}_control_region",
                "flow_gate_marker",
                flow_gate_part,
                (x, height * 0.30, z),
                (width * 0.040, height * 0.044, depth * 0.020),
                tags=["setpiece", "simulation", "flow_gate", "resource_control", archetype, layout, f"flow_gate_{index}"],
                adjacency=[resource_flow_part, control_input_part],
            )
        )

    for index in range(world_metric_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, world_metric_marker_count))
        z = depth * 0.72
        components.append(
            _component(
                f"setpiece_world_metric_{index:02d}_readout_region",
                "world_metric_marker",
                world_metric_part,
                (x, height * 0.40, z),
                (width * 0.042, height * 0.040, depth * 0.018),
                tags=["setpiece", "simulation", "world_metric", "readout", archetype, layout, f"world_metric_{index}"],
                adjacency=[simulation_layer_part, simulation_probe_part],
            )
        )

    for index in range(simulation_probe_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, simulation_probe_marker_count))
        z = depth * 0.78
        components.append(
            _component(
                f"setpiece_simulation_probe_{index:02d}_query_region",
                "simulation_probe_marker",
                simulation_probe_part,
                (x, height * 0.28, z),
                (width * 0.030, height * 0.036, depth * 0.018),
                tags=["setpiece", "simulation", "simulation_probe", "query", archetype, layout, f"simulation_probe_{index}"],
                adjacency=[world_metric_part, field_part],
            )
        )

    for index in range(culture_system_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, culture_system_marker_count))
        z = depth * 0.84
        components.append(
            _component(
                f"setpiece_culture_system_{index:02d}_identity_region",
                "culture_system_marker",
                culture_system_part,
                (x, height * 0.58, z),
                (width * 0.070, height * 0.050, depth * 0.032),
                tags=["setpiece", "culture", "culture_system", "civilization", archetype, layout, f"culture_system_{index}"],
                adjacency=[law_code_part, social_graph_part],
            )
        )

    for index in range(law_code_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, law_code_marker_count))
        z = depth * 0.90
        components.append(
            _component(
                f"setpiece_law_code_{index:02d}_governance_region",
                "law_code_marker",
                law_code_part,
                (x, height * 0.46, z),
                (width * 0.050, height * 0.046, depth * 0.020),
                tags=["setpiece", "culture", "law_code", "governance", archetype, layout, f"law_code_{index}"],
                adjacency=[culture_system_part, policy_rule_part],
            )
        )

    for index in range(policy_rule_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, policy_rule_marker_count))
        z = depth * 0.96
        components.append(
            _component(
                f"setpiece_policy_rule_{index:02d}_edict_region",
                "policy_rule_marker",
                policy_rule_part,
                (x, height * 0.36, z),
                (width * 0.036, height * 0.038, depth * 0.018),
                tags=["setpiece", "culture", "policy_rule", "edict", archetype, layout, f"policy_rule_{index}"],
                adjacency=[law_code_part, civic_institution_part],
            )
        )

    for index in range(economy_model_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, economy_model_marker_count))
        z = depth * 1.02
        components.append(
            _component(
                f"setpiece_economy_model_{index:02d}_market_region",
                "economy_model_marker",
                economy_model_part,
                (x, height * 0.42, z),
                (width * 0.062, height * 0.042, depth * 0.032),
                tags=["setpiece", "culture", "economy_model", "market", archetype, layout, f"economy_model_{index}"],
                adjacency=[trade_policy_part, labor_system_part],
            )
        )

    for index in range(trade_policy_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, trade_policy_marker_count))
        z = depth * 1.08
        components.append(
            _component(
                f"setpiece_trade_policy_{index:02d}_exchange_region",
                "trade_policy_marker",
                trade_policy_part,
                (x, height * 0.30, z),
                (width * 0.055, height * 0.030, depth * 0.018),
                tags=["setpiece", "culture", "trade_policy", "exchange", archetype, layout, f"trade_policy_{index}"],
                adjacency=[economy_model_part, resource_flow_part],
            )
        )

    for index in range(diplomacy_state_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, diplomacy_state_marker_count))
        z = depth * 1.14
        components.append(
            _component(
                f"setpiece_diplomacy_state_{index:02d}_treaty_region",
                "diplomacy_state_marker",
                diplomacy_state_part,
                (x, height * 0.50, z),
                (width * 0.050, height * 0.044, depth * 0.022),
                tags=["setpiece", "culture", "diplomacy_state", "treaty", archetype, layout, f"diplomacy_state_{index}"],
                adjacency=[social_relation_part, reputation_part],
            )
        )

    for index in range(social_graph_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, social_graph_marker_count))
        z = depth * 1.20
        components.append(
            _component(
                f"setpiece_social_graph_{index:02d}_network_region",
                "social_graph_marker",
                social_graph_part,
                (x, height * 0.32, z),
                (width * 0.060, height * 0.028, depth * 0.060),
                tags=["setpiece", "culture", "social_graph", "network", archetype, layout, f"social_graph_{index}"],
                adjacency=[population_group_part, social_relation_part],
            )
        )

    for index in range(social_relation_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, social_relation_marker_count))
        z = depth * 1.26
        components.append(
            _component(
                f"setpiece_social_relation_{index:02d}_tie_region",
                "social_relation_marker",
                social_relation_part,
                (x, height * 0.24, z),
                (width * 0.034, height * 0.030, depth * 0.018),
                tags=["setpiece", "culture", "social_relation", "tie", archetype, layout, f"social_relation_{index}"],
                adjacency=[social_graph_part, diplomacy_state_part],
            )
        )

    for index in range(population_group_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, population_group_marker_count))
        z = depth * 1.32
        components.append(
            _component(
                f"setpiece_population_group_{index:02d}_class_region",
                "population_group_marker",
                population_group_part,
                (x, height * 0.26, z),
                (width * 0.052, height * 0.036, depth * 0.026),
                tags=["setpiece", "culture", "population_group", "class", archetype, layout, f"population_group_{index}"],
                adjacency=[social_graph_part, labor_system_part],
            )
        )

    for index in range(labor_system_marker_count):
        x = -width * 0.38 + width * 0.76 * ((index + 0.5) / max(1, labor_system_marker_count))
        z = depth * 1.38
        components.append(
            _component(
                f"setpiece_labor_system_{index:02d}_work_region",
                "labor_system_marker",
                labor_system_part,
                (x, height * 0.22, z),
                (width * 0.060, height * 0.028, depth * 0.024),
                tags=["setpiece", "culture", "labor_system", "work", archetype, layout, f"labor_system_{index}"],
                adjacency=[economy_model_part, population_group_part],
            )
        )

    for index in range(ritual_calendar_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, ritual_calendar_marker_count))
        z = depth * 1.44
        components.append(
            _component(
                f"setpiece_ritual_calendar_{index:02d}_season_region",
                "ritual_calendar_marker",
                ritual_calendar_part,
                (x, height * 0.44, z),
                (width * 0.050, height * 0.040, depth * 0.032),
                tags=["setpiece", "culture", "ritual_calendar", "season", archetype, layout, f"ritual_calendar_{index}"],
                adjacency=[belief_system_part, festival_part],
            )
        )

    for index in range(festival_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, festival_marker_count))
        z = depth * 1.50
        components.append(
            _component(
                f"setpiece_festival_{index:02d}_gathering_region",
                "festival_marker",
                festival_part,
                (x, height * 0.34, z),
                (width * 0.070, height * 0.034, depth * 0.040),
                tags=["setpiece", "culture", "festival", "gathering", archetype, layout, f"festival_{index}"],
                adjacency=[ritual_calendar_part, event_marker_part],
            )
        )

    for index in range(belief_system_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, belief_system_marker_count))
        z = depth * 1.56
        components.append(
            _component(
                f"setpiece_belief_system_{index:02d}_doctrine_region",
                "belief_system_marker",
                belief_system_part,
                (x, height * 0.48, z),
                (width * 0.048, height * 0.045, depth * 0.024),
                tags=["setpiece", "culture", "belief_system", "doctrine", archetype, layout, f"belief_system_{index}"],
                adjacency=[culture_system_part, cultural_marker_part],
            )
        )

    for index in range(cultural_marker_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, cultural_marker_marker_count))
        z = depth * 1.62
        components.append(
            _component(
                f"setpiece_cultural_marker_{index:02d}_symbol_region",
                "cultural_marker_marker",
                cultural_marker_part,
                (x, height * 0.38, z),
                (width * 0.030, height * 0.038, depth * 0.018),
                tags=["setpiece", "culture", "cultural_marker", "symbol", archetype, layout, f"cultural_marker_{index}"],
                adjacency=[belief_system_part, signage_ui_part],
            )
        )

    for index in range(civic_institution_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, civic_institution_marker_count))
        z = depth * 1.68
        components.append(
            _component(
                f"setpiece_civic_institution_{index:02d}_hall_region",
                "civic_institution_marker",
                civic_institution_part,
                (x, height * 0.48, z),
                (width * 0.060, height * 0.070, depth * 0.040),
                tags=["setpiece", "culture", "civic_institution", "civic", archetype, layout, f"civic_institution_{index}"],
                adjacency=[law_code_part, mission_part],
            )
        )

    for index in range(biome_system_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, biome_system_marker_count))
        z = depth * 1.74
        components.append(
            _component(
                f"setpiece_biome_system_{index:02d}_living_region",
                "biome_system_marker",
                biome_system_part,
                (x, height * 0.22, z),
                (width * 0.090, height * 0.036, depth * 0.060),
                tags=["setpiece", "ecology", "biome_system", "living_biome", archetype, layout, f"biome_system_{index}"],
                adjacency=[terrain_part, habitat_zone_part],
            )
        )

    for index in range(habitat_zone_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, habitat_zone_marker_count))
        z = depth * 1.80
        components.append(
            _component(
                f"setpiece_habitat_zone_{index:02d}_zone_region",
                "habitat_zone_marker",
                habitat_zone_part,
                (x, height * 0.14, z),
                (width * 0.080, height * 0.022, depth * 0.050),
                tags=["setpiece", "ecology", "habitat_zone", "habitat", archetype, layout, f"habitat_zone_{index}"],
                adjacency=[biome_system_part, resource_patch_part],
            )
        )

    for index in range(species_population_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, species_population_marker_count))
        z = depth * 1.86
        components.append(
            _component(
                f"setpiece_species_population_{index:02d}_population_region",
                "species_population_marker",
                species_population_part,
                (x, height * 0.28, z),
                (width * 0.040, height * 0.048, depth * 0.026),
                tags=["setpiece", "ecology", "species_population", "wildlife", archetype, layout, f"species_population_{index}"],
                adjacency=[habitat_zone_part, nesting_site_part],
            )
        )

    for index in range(food_web_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, food_web_marker_count))
        z = depth * 1.92
        components.append(
            _component(
                f"setpiece_food_web_{index:02d}_web_region",
                "food_web_marker",
                food_web_part,
                (x, height * 0.30, z),
                (width * 0.070, height * 0.030, depth * 0.050),
                tags=["setpiece", "ecology", "food_web", "food_chain", archetype, layout, f"food_web_{index}"],
                adjacency=[species_population_part, predator_prey_link_part],
            )
        )

    for index in range(predator_prey_link_marker_count):
        x = -width * 0.44 + width * 0.88 * ((index + 0.5) / max(1, predator_prey_link_marker_count))
        z = depth * 1.98
        components.append(
            _component(
                f"setpiece_predator_prey_link_{index:02d}_pressure_region",
                "predator_prey_link_marker",
                predator_prey_link_part,
                (x, height * 0.24, z),
                (width * 0.034, height * 0.030, depth * 0.018),
                tags=["setpiece", "ecology", "predator_prey_link", "predation", archetype, layout, f"predator_prey_link_{index}"],
                adjacency=[food_web_part, world_metric_part],
            )
        )

    for index in range(migration_route_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, migration_route_marker_count))
        z = depth * 2.04
        components.append(
            _component(
                f"setpiece_migration_route_{index:02d}_path_region",
                "migration_route_marker",
                migration_route_part,
                (x, height * 0.12, z),
                (width * 0.120, height * 0.018, depth * 0.020),
                tags=["setpiece", "ecology", "migration_route", "wildlife_path", archetype, layout, f"migration_route_{index}"],
                adjacency=[habitat_zone_part, road_part],
            )
        )

    for index in range(nesting_site_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, nesting_site_marker_count))
        z = depth * 2.10
        components.append(
            _component(
                f"setpiece_nesting_site_{index:02d}_spawn_region",
                "nesting_site_marker",
                nesting_site_part,
                (x, height * 0.20, z),
                (width * 0.044, height * 0.032, depth * 0.030),
                tags=["setpiece", "ecology", "nesting_site", "spawn", archetype, layout, f"nesting_site_{index}"],
                adjacency=[species_population_part, spawn_marker_part],
            )
        )

    for index in range(resource_patch_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, resource_patch_marker_count))
        z = depth * 2.16
        components.append(
            _component(
                f"setpiece_resource_patch_{index:02d}_resource_region",
                "resource_patch_marker",
                resource_patch_part,
                (x, height * 0.12, z),
                (width * 0.060, height * 0.024, depth * 0.038),
                tags=["setpiece", "ecology", "resource_patch", "renewable_resource", archetype, layout, f"resource_patch_{index}"],
                adjacency=[habitat_zone_part, resource_regeneration_part],
            )
        )

    for index in range(resource_regeneration_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, resource_regeneration_marker_count))
        z = depth * 2.22
        components.append(
            _component(
                f"setpiece_resource_regeneration_{index:02d}_renewal_region",
                "resource_regeneration_marker",
                resource_regeneration_part,
                (x, height * 0.26, z),
                (width * 0.044, height * 0.034, depth * 0.022),
                tags=["setpiece", "ecology", "resource_regeneration", "renewal", archetype, layout, f"resource_regeneration_{index}"],
                adjacency=[resource_patch_part, growth_cycle_part],
            )
        )

    for index in range(growth_cycle_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, growth_cycle_marker_count))
        z = depth * 2.28
        components.append(
            _component(
                f"setpiece_growth_cycle_{index:02d}_season_region",
                "growth_cycle_marker",
                growth_cycle_part,
                (x, height * 0.34, z),
                (width * 0.040, height * 0.036, depth * 0.024),
                tags=["setpiece", "ecology", "growth_cycle", "seasonal", archetype, layout, f"growth_cycle_{index}"],
                adjacency=[resource_regeneration_part, world_metric_part],
            )
        )

    for index in range(weather_ecology_link_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, weather_ecology_link_marker_count))
        z = depth * 2.34
        components.append(
            _component(
                f"setpiece_weather_ecology_link_{index:02d}_weather_region",
                "weather_ecology_link_marker",
                weather_ecology_link_part,
                (x, height * 0.38, z),
                (width * 0.050, height * 0.040, depth * 0.026),
                tags=["setpiece", "ecology", "weather_ecology_link", "weather_coupling", archetype, layout, f"weather_ecology_link_{index}"],
                adjacency=[weather_part, biome_system_part],
            )
        )

    for index in range(ecological_pressure_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, ecological_pressure_marker_count))
        z = depth * 2.40
        components.append(
            _component(
                f"setpiece_ecological_pressure_{index:02d}_stress_region",
                "ecological_pressure_marker",
                ecological_pressure_part,
                (x, height * 0.30, z),
                (width * 0.052, height * 0.040, depth * 0.030),
                tags=["setpiece", "ecology", "ecological_pressure", "stress", archetype, layout, f"ecological_pressure_{index}"],
                adjacency=[hazard_field_part, biome_system_part],
            )
        )

    for index in range(land_use_plan_marker_count):
        x = -width * 0.34 + width * 0.68 * ((index + 0.5) / max(1, land_use_plan_marker_count))
        z = depth * 2.46
        components.append(
            _component(
                f"setpiece_land_use_plan_{index:02d}_plan_region",
                "land_use_plan_marker",
                land_use_plan_part,
                (x, height * 0.42, z),
                (width * 0.070, height * 0.042, depth * 0.040),
                tags=["setpiece", "civil_ecology", "land_use_plan", "settlement_biome", archetype, layout, f"land_use_plan_{index}"],
                adjacency=[culture_system_part, biome_system_part],
            )
        )

    for index in range(farm_plot_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, farm_plot_marker_count))
        z = depth * 2.52
        components.append(
            _component(
                f"setpiece_farm_plot_{index:02d}_crop_region",
                "farm_plot_marker",
                farm_plot_part,
                (x, height * 0.12, z),
                (width * 0.070, height * 0.020, depth * 0.042),
                tags=["setpiece", "civil_ecology", "farm_plot", "agriculture", archetype, layout, f"farm_plot_{index}"],
                adjacency=[land_use_plan_part, harvest_cycle_part],
            )
        )

    for index in range(hunting_ground_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, hunting_ground_marker_count))
        z = depth * 2.58
        components.append(
            _component(
                f"setpiece_hunting_ground_{index:02d}_game_region",
                "hunting_ground_marker",
                hunting_ground_part,
                (x, height * 0.18, z),
                (width * 0.064, height * 0.026, depth * 0.040),
                tags=["setpiece", "civil_ecology", "hunting_ground", "game", archetype, layout, f"hunting_ground_{index}"],
                adjacency=[species_population_part, carrying_capacity_rule_part],
            )
        )

    for index in range(fishing_ground_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, fishing_ground_marker_count))
        z = depth * 2.64
        components.append(
            _component(
                f"setpiece_fishing_ground_{index:02d}_water_region",
                "fishing_ground_marker",
                fishing_ground_part,
                (x, height * 0.10, z),
                (width * 0.068, height * 0.020, depth * 0.042),
                tags=["setpiece", "civil_ecology", "fishing_ground", "fishery", archetype, layout, f"fishing_ground_{index}"],
                adjacency=[liquid_part, species_population_part],
            )
        )

    for index in range(grazing_range_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, grazing_range_marker_count))
        z = depth * 2.70
        components.append(
            _component(
                f"setpiece_grazing_range_{index:02d}_pasture_region",
                "grazing_range_marker",
                grazing_range_part,
                (x, height * 0.12, z),
                (width * 0.070, height * 0.020, depth * 0.044),
                tags=["setpiece", "civil_ecology", "grazing_range", "pasture", archetype, layout, f"grazing_range_{index}"],
                adjacency=[habitat_zone_part, species_population_part],
            )
        )

    for index in range(extraction_site_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, extraction_site_marker_count))
        z = depth * 2.76
        components.append(
            _component(
                f"setpiece_extraction_site_{index:02d}_resource_region",
                "extraction_site_marker",
                extraction_site_part,
                (x, height * 0.26, z),
                (width * 0.060, height * 0.040, depth * 0.034),
                tags=["setpiece", "civil_ecology", "extraction_site", "resource_extraction", archetype, layout, f"extraction_site_{index}"],
                adjacency=[resource_claim_part, resource_flow_part],
            )
        )

    for index in range(pollution_source_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, pollution_source_marker_count))
        z = depth * 2.82
        components.append(
            _component(
                f"setpiece_pollution_source_{index:02d}_emitter_region",
                "pollution_source_marker",
                pollution_source_part,
                (x, height * 0.30, z),
                (width * 0.046, height * 0.044, depth * 0.026),
                tags=["setpiece", "civil_ecology", "pollution_source", "emitter", archetype, layout, f"pollution_source_{index}"],
                adjacency=[ecological_pressure_part, hazard_field_part],
            )
        )

    for index in range(conservation_zone_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, conservation_zone_marker_count))
        z = depth * 2.88
        components.append(
            _component(
                f"setpiece_conservation_zone_{index:02d}_reserve_region",
                "conservation_zone_marker",
                conservation_zone_part,
                (x, height * 0.16, z),
                (width * 0.074, height * 0.022, depth * 0.050),
                tags=["setpiece", "civil_ecology", "conservation_zone", "reserve", archetype, layout, f"conservation_zone_{index}"],
                adjacency=[habitat_zone_part, restoration_project_part],
            )
        )

    for index in range(restoration_project_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, restoration_project_marker_count))
        z = depth * 2.94
        components.append(
            _component(
                f"setpiece_restoration_project_{index:02d}_rewild_region",
                "restoration_project_marker",
                restoration_project_part,
                (x, height * 0.24, z),
                (width * 0.054, height * 0.034, depth * 0.032),
                tags=["setpiece", "civil_ecology", "restoration_project", "rewilding", archetype, layout, f"restoration_project_{index}"],
                adjacency=[conservation_zone_part, resource_regeneration_part],
            )
        )

    for index in range(scarcity_loop_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, scarcity_loop_marker_count))
        z = depth * 3.00
        components.append(
            _component(
                f"setpiece_scarcity_loop_{index:02d}_deficit_region",
                "scarcity_loop_marker",
                scarcity_loop_part,
                (x, height * 0.38, z),
                (width * 0.050, height * 0.040, depth * 0.026),
                tags=["setpiece", "civil_ecology", "scarcity_loop", "deficit", archetype, layout, f"scarcity_loop_{index}"],
                adjacency=[resource_claim_part, world_metric_part],
            )
        )

    for index in range(settlement_pressure_marker_count):
        x = -width * 0.36 + width * 0.72 * ((index + 0.5) / max(1, settlement_pressure_marker_count))
        z = depth * 3.06
        components.append(
            _component(
                f"setpiece_settlement_pressure_{index:02d}_demand_region",
                "settlement_pressure_marker",
                settlement_pressure_part,
                (x, height * 0.42, z),
                (width * 0.052, height * 0.042, depth * 0.030),
                tags=["setpiece", "civil_ecology", "settlement_pressure", "demand", archetype, layout, f"settlement_pressure_{index}"],
                adjacency=[culture_system_part, ecological_pressure_part],
            )
        )

    for index in range(resource_claim_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, resource_claim_marker_count))
        z = depth * 3.12
        components.append(
            _component(
                f"setpiece_resource_claim_{index:02d}_claim_region",
                "resource_claim_marker",
                resource_claim_part,
                (x, height * 0.32, z),
                (width * 0.040, height * 0.036, depth * 0.022),
                tags=["setpiece", "civil_ecology", "resource_claim", "territory", archetype, layout, f"resource_claim_{index}"],
                adjacency=[territory_part, resource_flow_part],
            )
        )

    for index in range(harvest_cycle_marker_count):
        x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, harvest_cycle_marker_count))
        z = depth * 3.18
        components.append(
            _component(
                f"setpiece_harvest_cycle_{index:02d}_yield_region",
                "harvest_cycle_marker",
                harvest_cycle_part,
                (x, height * 0.26, z),
                (width * 0.042, height * 0.034, depth * 0.024),
                tags=["setpiece", "civil_ecology", "harvest_cycle", "yield", archetype, layout, f"harvest_cycle_{index}"],
                adjacency=[farm_plot_part, growth_cycle_part],
            )
        )

    for index in range(carrying_capacity_rule_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, carrying_capacity_rule_marker_count))
        z = depth * 3.24
        components.append(
            _component(
                f"setpiece_carrying_capacity_rule_{index:02d}_capacity_region",
                "carrying_capacity_rule_marker",
                carrying_capacity_rule_part,
                (x, height * 0.34, z),
                (width * 0.038, height * 0.036, depth * 0.022),
                tags=["setpiece", "civil_ecology", "carrying_capacity_rule", "capacity", archetype, layout, f"carrying_capacity_rule_{index}"],
                adjacency=[world_metric_part, species_population_part],
            )
        )

    for index in range(biome_impact_marker_count):
        x = -width * 0.40 + width * 0.80 * ((index + 0.5) / max(1, biome_impact_marker_count))
        z = depth * 3.30
        components.append(
            _component(
                f"setpiece_biome_impact_{index:02d}_impact_region",
                "biome_impact_marker",
                biome_impact_part,
                (x, height * 0.34, z),
                (width * 0.048, height * 0.038, depth * 0.026),
                tags=["setpiece", "civil_ecology", "biome_impact", "impact", archetype, layout, f"biome_impact_{index}"],
                adjacency=[biome_system_part, ecological_pressure_part],
            )
        )

    logistics_marker_specs = [
        (supply_chain_marker_count, "supply_chain", "chain", supply_chain_part, depth * 3.36, height * 0.42, width * 0.070, height * 0.040, depth * 0.036, [storage_depot_part, processing_stage_part]),
        (logistics_hub_marker_count, "logistics_hub", "hub", logistics_hub_part, depth * 3.42, height * 0.38, width * 0.060, height * 0.046, depth * 0.034, [storage_depot_part, supply_route_part]),
        (storage_depot_marker_count, "storage_depot", "depot", storage_depot_part, depth * 3.48, height * 0.34, width * 0.058, height * 0.042, depth * 0.036, [logistics_hub_part, stockpile_part]),
        (stockpile_marker_count, "stockpile", "stock", stockpile_part, depth * 3.54, height * 0.20, width * 0.046, height * 0.028, depth * 0.028, [storage_depot_part, world_metric_part]),
        (input_buffer_marker_count, "input_buffer", "input", input_buffer_part, depth * 3.60, height * 0.24, width * 0.036, height * 0.030, depth * 0.022, [processing_stage_part, stockpile_part]),
        (output_buffer_marker_count, "output_buffer", "output", output_buffer_part, depth * 3.66, height * 0.24, width * 0.036, height * 0.030, depth * 0.022, [processing_stage_part, stockpile_part]),
        (processing_stage_marker_count, "processing_stage", "processor", processing_stage_part, depth * 3.72, height * 0.36, width * 0.050, height * 0.050, depth * 0.030, [input_buffer_part, output_buffer_part]),
        (refinery_stage_marker_count, "refinery_stage", "refinery", refinery_stage_part, depth * 3.78, height * 0.40, width * 0.054, height * 0.054, depth * 0.032, [processing_stage_part, resource_flow_part]),
        (workshop_stage_marker_count, "workshop_stage", "workshop", workshop_stage_part, depth * 3.84, height * 0.38, width * 0.052, height * 0.048, depth * 0.032, [processing_stage_part, output_buffer_part]),
        (assembly_stage_marker_count, "assembly_stage", "assembly", assembly_stage_part, depth * 3.90, height * 0.42, width * 0.056, height * 0.052, depth * 0.034, [workshop_stage_part, output_buffer_part]),
        (market_node_marker_count, "market_node", "market", market_node_part, depth * 3.96, height * 0.36, width * 0.058, height * 0.044, depth * 0.034, [stockpile_part, demand_sink_part]),
        (demand_sink_marker_count, "demand_sink", "demand", demand_sink_part, depth * 4.02, height * 0.30, width * 0.040, height * 0.034, depth * 0.024, [market_node_part, world_metric_part]),
        (supply_route_marker_count, "supply_route", "route", supply_route_part, depth * 4.08, height * 0.12, width * 0.110, height * 0.018, depth * 0.018, [resource_flow_part, transport_leg_part]),
        (transport_leg_marker_count, "transport_leg", "leg", transport_leg_part, depth * 4.14, height * 0.14, width * 0.082, height * 0.018, depth * 0.018, [supply_route_part, resource_flow_part]),
        (bottleneck_marker_count, "bottleneck", "constraint", bottleneck_part, depth * 4.20, height * 0.32, width * 0.040, height * 0.038, depth * 0.024, [throughput_rule_part, world_metric_part]),
        (throughput_rule_marker_count, "throughput_rule", "throughput", throughput_rule_part, depth * 4.26, height * 0.34, width * 0.038, height * 0.036, depth * 0.022, [bottleneck_part, world_metric_part]),
        (failure_mode_marker_count, "failure_mode", "failure", failure_mode_part, depth * 4.32, height * 0.34, width * 0.040, height * 0.038, depth * 0.024, [condition_part, world_metric_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in logistics_marker_specs:
        for index in range(count):
            x = -width * 0.42 + width * 0.84 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "logistics", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    strategy_marker_specs = [
        (production_strategy_marker_count, "production_strategy", "strategy", production_strategy_part, depth * 4.38, height * 0.42, width * 0.070, height * 0.044, depth * 0.036, [production_priority_part, supply_chain_part]),
        (production_priority_marker_count, "production_priority", "priority", production_priority_part, depth * 4.44, height * 0.38, width * 0.054, height * 0.040, depth * 0.030, [quota_rule_part, allocation_rule_part]),
        (quota_rule_marker_count, "quota_rule", "quota", quota_rule_part, depth * 4.50, height * 0.34, width * 0.042, height * 0.036, depth * 0.024, [throughput_rule_part, world_metric_part]),
        (allocation_rule_marker_count, "allocation_rule", "allocation", allocation_rule_part, depth * 4.56, height * 0.34, width * 0.042, height * 0.036, depth * 0.024, [resource_flow_part, quota_rule_part]),
        (rationing_policy_marker_count, "rationing_policy", "ration", rationing_policy_part, depth * 4.62, height * 0.36, width * 0.046, height * 0.038, depth * 0.026, [scarcity_loop_part, quota_rule_part]),
        (strategic_reserve_marker_count, "strategic_reserve", "reserve", strategic_reserve_part, depth * 4.68, height * 0.30, width * 0.060, height * 0.036, depth * 0.034, [stockpile_part, readiness_level_part]),
        (trade_embargo_marker_count, "trade_embargo", "embargo", trade_embargo_part, depth * 4.74, height * 0.36, width * 0.046, height * 0.038, depth * 0.026, [diplomacy_state_part, bottleneck_part]),
        (sabotage_target_marker_count, "sabotage_target", "sabotage", sabotage_target_part, depth * 4.80, height * 0.36, width * 0.044, height * 0.040, depth * 0.026, [failure_mode_part, bottleneck_part]),
        (maintenance_plan_marker_count, "maintenance_plan", "maintenance", maintenance_plan_part, depth * 4.86, height * 0.34, width * 0.050, height * 0.038, depth * 0.028, [repair_schedule_part, failure_mode_part]),
        (repair_schedule_marker_count, "repair_schedule", "repair", repair_schedule_part, depth * 4.92, height * 0.32, width * 0.040, height * 0.034, depth * 0.024, [maintenance_plan_part, world_metric_part]),
        (mobilization_order_marker_count, "mobilization_order", "mobilization", mobilization_order_part, depth * 4.98, height * 0.40, width * 0.056, height * 0.046, depth * 0.032, [wartime_production_part, readiness_level_part]),
        (production_mode_marker_count, "production_mode", "mode", production_mode_part, depth * 5.04, height * 0.34, width * 0.044, height * 0.036, depth * 0.026, [production_strategy_part, readiness_level_part]),
        (wartime_production_marker_count, "wartime_production", "wartime", wartime_production_part, depth * 5.10, height * 0.42, width * 0.060, height * 0.048, depth * 0.034, [strategic_reserve_part, quota_rule_part]),
        (peacetime_production_marker_count, "peacetime_production", "peacetime", peacetime_production_part, depth * 5.16, height * 0.38, width * 0.058, height * 0.044, depth * 0.032, [market_node_part, maintenance_plan_part]),
        (procurement_contract_marker_count, "procurement_contract", "procurement", procurement_contract_part, depth * 5.22, height * 0.34, width * 0.048, height * 0.038, depth * 0.026, [market_node_part, resource_claim_part]),
        (readiness_level_marker_count, "readiness_level", "readiness", readiness_level_part, depth * 5.28, height * 0.36, width * 0.042, height * 0.036, depth * 0.024, [world_metric_part, production_strategy_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in strategy_marker_specs:
        for index in range(count):
            x = -width * 0.44 + width * 0.88 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "production_strategy", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    conflict_marker_specs = [
        (conflict_system_marker_count, "conflict_system", "conflict", conflict_system_part, depth * 5.34, height * 0.44, width * 0.072, height * 0.046, depth * 0.038, [strategic_objective_part, battlefront_part]),
        (strategic_objective_marker_count, "strategic_objective", "objective", strategic_objective_part, depth * 5.40, height * 0.38, width * 0.050, height * 0.040, depth * 0.028, [war_plan_part, production_strategy_part]),
        (war_plan_marker_count, "war_plan", "campaign", war_plan_part, depth * 5.46, height * 0.42, width * 0.060, height * 0.046, depth * 0.034, [battlefront_part, mobilization_order_part]),
        (battlefront_marker_count, "battlefront", "front", battlefront_part, depth * 5.52, height * 0.30, width * 0.070, height * 0.030, depth * 0.024, [territory_part, supply_route_part]),
        (escalation_ladder_marker_count, "escalation_ladder", "escalation", escalation_ladder_part, depth * 5.58, height * 0.38, width * 0.046, height * 0.040, depth * 0.026, [diplomatic_demand_part, sanction_part]),
        (treaty_marker_count, "treaty", "treaty", treaty_part, depth * 5.64, height * 0.34, width * 0.050, height * 0.036, depth * 0.026, [diplomacy_state_part, trade_policy_part]),
        (ceasefire_marker_count, "ceasefire", "ceasefire", ceasefire_part, depth * 5.70, height * 0.34, width * 0.048, height * 0.036, depth * 0.026, [treaty_part, negotiation_channel_part]),
        (alliance_marker_count, "alliance", "alliance", alliance_part, depth * 5.76, height * 0.38, width * 0.056, height * 0.040, depth * 0.030, [diplomacy_state_part, supply_chain_part]),
        (rival_claim_marker_count, "rival_claim", "claim", rival_claim_part, depth * 5.82, height * 0.34, width * 0.046, height * 0.036, depth * 0.026, [resource_claim_part, diplomatic_demand_part]),
        (diplomatic_demand_marker_count, "diplomatic_demand", "demand", diplomatic_demand_part, depth * 5.88, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [negotiation_channel_part, sanction_part]),
        (negotiation_channel_marker_count, "negotiation_channel", "envoy", negotiation_channel_part, depth * 5.94, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [diplomacy_state_part, social_relation_part]),
        (sanction_marker_count, "sanction", "sanction", sanction_part, depth * 6.00, height * 0.34, width * 0.046, height * 0.038, depth * 0.026, [trade_embargo_part, bottleneck_part]),
        (espionage_cell_marker_count, "espionage_cell", "spy", espionage_cell_part, depth * 6.06, height * 0.36, width * 0.046, height * 0.040, depth * 0.026, [covert_operation_part, sensor_grid_part]),
        (covert_operation_marker_count, "covert_operation", "covert", covert_operation_part, depth * 6.12, height * 0.36, width * 0.044, height * 0.040, depth * 0.026, [sabotage_target_part, failure_mode_part]),
        (disaster_response_marker_count, "disaster_response", "relief", disaster_response_part, depth * 6.18, height * 0.40, width * 0.058, height * 0.044, depth * 0.032, [emergency_order_part, supply_chain_part]),
        (emergency_order_marker_count, "emergency_order", "emergency", emergency_order_part, depth * 6.24, height * 0.36, width * 0.044, height * 0.038, depth * 0.026, [policy_rule_part, readiness_level_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in conflict_marker_specs:
        for index in range(count):
            x = -width * 0.46 + width * 0.92 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "conflict_diplomacy", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    ai_marker_specs = [
        (faction_ai_marker_count, "faction_ai", "ai", faction_ai_part, depth * 6.30, height * 0.44, width * 0.072, height * 0.046, depth * 0.038, [doctrine_model_part, policy_selector_part]),
        (doctrine_model_marker_count, "doctrine_model", "doctrine", doctrine_model_part, depth * 6.36, height * 0.38, width * 0.050, height * 0.040, depth * 0.028, [decision_rule_part, diplomatic_posture_part]),
        (goal_stack_marker_count, "goal_stack", "goals", goal_stack_part, depth * 6.42, height * 0.38, width * 0.050, height * 0.040, depth * 0.028, [strategic_objective_part, world_metric_part]),
        (threat_model_marker_count, "threat_model", "threat", threat_model_part, depth * 6.48, height * 0.36, width * 0.048, height * 0.038, depth * 0.026, [perception_feed_part, escalation_choice_part]),
        (perception_feed_marker_count, "perception_feed", "signal", perception_feed_part, depth * 6.54, height * 0.34, width * 0.046, height * 0.036, depth * 0.024, [sensor_grid_part, simulation_probe_part]),
        (decision_rule_marker_count, "decision_rule", "rule", decision_rule_part, depth * 6.60, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [policy_selector_part, action_option_part]),
        (policy_selector_marker_count, "policy_selector", "selector", policy_selector_part, depth * 6.66, height * 0.36, width * 0.048, height * 0.038, depth * 0.026, [action_option_part, response_plan_part]),
        (action_option_marker_count, "action_option", "option", action_option_part, depth * 6.72, height * 0.34, width * 0.042, height * 0.036, depth * 0.024, [adaptive_order_part, world_metric_part]),
        (response_plan_marker_count, "response_plan", "response", response_plan_part, depth * 6.78, height * 0.40, width * 0.058, height * 0.044, depth * 0.032, [escalation_choice_part, resource_strategy_part]),
        (escalation_choice_marker_count, "escalation_choice", "escalate", escalation_choice_part, depth * 6.84, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [escalation_ladder_part, mobilization_order_part]),
        (deescalation_choice_marker_count, "deescalation_choice", "deescalate", deescalation_choice_part, depth * 6.90, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [negotiation_channel_part, ceasefire_part]),
        (resource_strategy_marker_count, "resource_strategy", "resources", resource_strategy_part, depth * 6.96, height * 0.40, width * 0.058, height * 0.044, depth * 0.032, [production_strategy_part, resource_claim_part]),
        (logistics_priority_marker_count, "logistics_priority", "logistics", logistics_priority_part, depth * 7.02, height * 0.36, width * 0.050, height * 0.038, depth * 0.026, [supply_chain_part, supply_route_part]),
        (diplomatic_posture_marker_count, "diplomatic_posture", "posture", diplomatic_posture_part, depth * 7.08, height * 0.34, width * 0.046, height * 0.036, depth * 0.024, [diplomacy_state_part, negotiation_channel_part]),
        (contingency_plan_marker_count, "contingency_plan", "contingency", contingency_plan_part, depth * 7.14, height * 0.40, width * 0.056, height * 0.044, depth * 0.030, [emergency_order_part, disaster_response_part]),
        (adaptive_order_marker_count, "adaptive_order", "adaptive", adaptive_order_part, depth * 7.20, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [policy_rule_part, world_metric_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in ai_marker_specs:
        for index in range(count):
            x = -width * 0.48 + width * 0.96 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "faction_ai", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    operational_marker_specs = [
        (operational_plan_marker_count, "operational_plan", "ops", operational_plan_part, depth * 7.26, height * 0.44, width * 0.072, height * 0.046, depth * 0.038, [order_queue_part, scheduled_action_part]),
        (order_queue_marker_count, "order_queue", "queue", order_queue_part, depth * 7.32, height * 0.38, width * 0.056, height * 0.040, depth * 0.030, [world_order_part, scheduled_action_part]),
        (world_order_marker_count, "world_order", "order", world_order_part, depth * 7.38, height * 0.34, width * 0.044, height * 0.036, depth * 0.024, [scheduled_action_part, task_assignment_part]),
        (patrol_order_marker_count, "patrol_order", "patrol", patrol_order_part, depth * 7.44, height * 0.24, width * 0.070, height * 0.024, depth * 0.020, [patrol_density_part, road_part]),
        (convoy_order_marker_count, "convoy_order", "convoy", convoy_order_part, depth * 7.50, height * 0.24, width * 0.078, height * 0.024, depth * 0.022, [convoy_route_part, supply_chain_part]),
        (construction_order_marker_count, "construction_order", "build", construction_order_part, depth * 7.56, height * 0.36, width * 0.048, height * 0.038, depth * 0.026, [construction_queue_part, resource_flow_part]),
        (repair_order_marker_count, "repair_order", "repair", repair_order_part, depth * 7.62, height * 0.36, width * 0.046, height * 0.038, depth * 0.026, [repair_crew_part, repair_schedule_part]),
        (relief_order_marker_count, "relief_order", "relief", relief_order_part, depth * 7.68, height * 0.36, width * 0.046, height * 0.038, depth * 0.026, [relief_team_part, disaster_response_part]),
        (mission_order_marker_count, "mission_order", "mission", mission_order_part, depth * 7.74, height * 0.36, width * 0.048, height * 0.038, depth * 0.026, [mission_part, task_assignment_part]),
        (scheduled_action_marker_count, "scheduled_action", "schedule", scheduled_action_part, depth * 7.80, height * 0.32, width * 0.042, height * 0.034, depth * 0.022, [event_marker_part, world_metric_part]),
        (task_assignment_marker_count, "task_assignment", "task", task_assignment_part, depth * 7.86, height * 0.32, width * 0.042, height * 0.034, depth * 0.022, [crew_roster_part, world_metric_part]),
        (crew_roster_marker_count, "crew_roster", "crew", crew_roster_part, depth * 7.92, height * 0.34, width * 0.050, height * 0.036, depth * 0.026, [labor_system_part, population_group_part]),
        (convoy_route_marker_count, "convoy_route", "route", convoy_route_part, depth * 7.98, height * 0.18, width * 0.088, height * 0.020, depth * 0.018, [supply_route_part, transport_leg_part]),
        (construction_queue_marker_count, "construction_queue", "build_queue", construction_queue_part, depth * 8.04, height * 0.36, width * 0.050, height * 0.038, depth * 0.026, [construction_order_part, throughput_rule_part]),
        (repair_crew_marker_count, "repair_crew", "repair_crew", repair_crew_part, depth * 8.10, height * 0.34, width * 0.046, height * 0.036, depth * 0.024, [repair_order_part, maintenance_plan_part]),
        (relief_team_marker_count, "relief_team", "relief_team", relief_team_part, depth * 8.16, height * 0.34, width * 0.046, height * 0.036, depth * 0.024, [relief_order_part, supply_chain_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in operational_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "operational_execution", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    evolution_marker_specs = [
        (settlement_evolution_marker_count, "settlement_evolution", "evolution", settlement_evolution_part, depth * 8.22, height * 0.46, width * 0.078, height * 0.048, depth * 0.040, [growth_phase_part, expansion_zone_part]),
        (growth_phase_marker_count, "growth_phase", "phase", growth_phase_part, depth * 8.28, height * 0.36, width * 0.050, height * 0.038, depth * 0.026, [construction_stage_part, scheduled_action_part]),
        (expansion_zone_marker_count, "expansion_zone", "zone", expansion_zone_part, depth * 8.34, height * 0.26, width * 0.084, height * 0.026, depth * 0.026, [district_upgrade_part, road_part]),
        (construction_stage_marker_count, "construction_stage", "stage", construction_stage_part, depth * 8.40, height * 0.36, width * 0.046, height * 0.038, depth * 0.026, [worksite_part, material_delivery_part]),
        (upgrade_plan_marker_count, "upgrade_plan", "upgrade", upgrade_plan_part, depth * 8.46, height * 0.38, width * 0.054, height * 0.040, depth * 0.030, [district_upgrade_part, building_upgrade_part]),
        (district_upgrade_marker_count, "district_upgrade", "district", district_upgrade_part, depth * 8.52, height * 0.36, width * 0.052, height * 0.038, depth * 0.028, [construction_queue_part, infrastructure_upgrade_part]),
        (building_upgrade_marker_count, "building_upgrade", "building", building_upgrade_part, depth * 8.58, height * 0.40, width * 0.056, height * 0.044, depth * 0.032, [construction_order_part, occupancy_plan_part]),
        (infrastructure_upgrade_marker_count, "infrastructure_upgrade", "utility", infrastructure_upgrade_part, depth * 8.64, height * 0.34, width * 0.060, height * 0.034, depth * 0.028, [resource_flow_part, utility_part]),
        (material_delivery_marker_count, "material_delivery", "delivery", material_delivery_part, depth * 8.70, height * 0.22, width * 0.086, height * 0.024, depth * 0.020, [convoy_order_part, stockpile_part]),
        (staffing_plan_marker_count, "staffing_plan", "staff", staffing_plan_part, depth * 8.76, height * 0.34, width * 0.048, height * 0.036, depth * 0.026, [crew_roster_part, labor_system_part]),
        (occupancy_plan_marker_count, "occupancy_plan", "occupancy", occupancy_plan_part, depth * 8.82, height * 0.34, width * 0.050, height * 0.036, depth * 0.026, [population_group_part, building_part]),
        (worksite_marker_count, "worksite", "site", worksite_part, depth * 8.88, height * 0.34, width * 0.052, height * 0.036, depth * 0.028, [construction_order_part, crew_roster_part]),
        (build_permit_marker_count, "build_permit", "permit", build_permit_part, depth * 8.94, height * 0.32, width * 0.044, height * 0.034, depth * 0.024, [policy_rule_part, scheduled_action_part]),
        (damage_repair_plan_marker_count, "damage_repair_plan", "repair_plan", damage_repair_plan_part, depth * 9.00, height * 0.36, width * 0.050, height * 0.038, depth * 0.028, [repair_order_part, repair_crew_part]),
        (demolition_plan_marker_count, "demolition_plan", "demolition", demolition_plan_part, depth * 9.06, height * 0.34, width * 0.050, height * 0.036, depth * 0.030, [debris_part, construction_queue_part]),
        (renovation_project_marker_count, "renovation_project", "renovation", renovation_project_part, depth * 9.12, height * 0.38, width * 0.054, height * 0.040, depth * 0.030, [building_upgrade_part, material_delivery_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in evolution_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "settlement_evolution", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    city_marker_specs = [
        (city_plan_marker_count, "city_plan", "city", city_plan_part, depth * 9.18, height * 0.48, width * 0.082, height * 0.050, depth * 0.042, [zoning_rule_part, parcel_grid_part]),
        (zoning_rule_marker_count, "zoning_rule", "zoning", zoning_rule_part, depth * 9.24, height * 0.34, width * 0.046, height * 0.036, depth * 0.024, [policy_rule_part, zoning_district_part]),
        (zoning_district_marker_count, "zoning_district", "zone", zoning_district_part, depth * 9.30, height * 0.32, width * 0.064, height * 0.032, depth * 0.028, [district_upgrade_part, development_pressure_part]),
        (parcel_grid_marker_count, "parcel_grid", "parcel_grid", parcel_grid_part, depth * 9.36, height * 0.28, width * 0.082, height * 0.026, depth * 0.028, [land_parcel_part, street_hierarchy_part]),
        (land_parcel_marker_count, "land_parcel", "parcel", land_parcel_part, depth * 9.42, height * 0.30, width * 0.040, height * 0.030, depth * 0.024, [zoning_rule_part, build_permit_part]),
        (parcel_subdivision_marker_count, "parcel_subdivision", "subdivision", parcel_subdivision_part, depth * 9.48, height * 0.32, width * 0.058, height * 0.032, depth * 0.026, [land_parcel_part, block_plan_part]),
        (block_plan_marker_count, "block_plan", "block", block_plan_part, depth * 9.54, height * 0.34, width * 0.064, height * 0.036, depth * 0.030, [parcel_grid_part, public_space_plan_part]),
        (street_hierarchy_marker_count, "street_hierarchy", "street", street_hierarchy_part, depth * 9.60, height * 0.20, width * 0.092, height * 0.020, depth * 0.018, [road_part, transit_node_part]),
        (transit_node_marker_count, "transit_node", "transit", transit_node_part, depth * 9.66, height * 0.34, width * 0.044, height * 0.038, depth * 0.026, [street_hierarchy_part, service_coverage_part]),
        (civic_service_plan_marker_count, "civic_service_plan", "civic", civic_service_plan_part, depth * 9.72, height * 0.38, width * 0.056, height * 0.040, depth * 0.030, [service_coverage_part, utility_corridor_part]),
        (service_coverage_marker_count, "service_coverage", "coverage", service_coverage_part, depth * 9.78, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [service_coverage_part, resource_flow_part]),
        (utility_corridor_marker_count, "utility_corridor", "utility", utility_corridor_part, depth * 9.84, height * 0.22, width * 0.088, height * 0.022, depth * 0.020, [utility_part, resource_flow_part]),
        (district_site_plan_marker_count, "district_site_plan", "district_site", district_site_plan_part, depth * 9.90, height * 0.36, width * 0.094, height * 0.034, depth * 0.042, [block_plan_part, site_compound_part]),
        (street_crossing_marker_count, "street_crossing", "crossing", street_crossing_part, depth * 9.96, height * 0.18, width * 0.062, height * 0.014, depth * 0.030, [street_hierarchy_part, pedestrian_path_part]),
        (perimeter_plan_marker_count, "perimeter_plan", "perimeter", perimeter_plan_part, depth * 10.02, height * 0.24, width * 0.092, height * 0.018, depth * 0.018, [district_site_plan_part, security_gate_part]),
        (security_gate_marker_count, "security_gate", "gate", security_gate_part, depth * 10.08, height * 0.32, width * 0.038, height * 0.050, depth * 0.026, [perimeter_plan_part, access_part]),
        (landscape_zone_marker_count, "landscape_zone", "landscape", landscape_zone_part, depth * 10.10, height * 0.16, width * 0.064, height * 0.014, depth * 0.040, [public_space_plan_part, growth_boundary_part]),
        (traffic_flow_marker_count, "traffic_flow", "traffic", traffic_flow_part, depth * 10.12, height * 0.18, width * 0.088, height * 0.014, depth * 0.018, [street_hierarchy_part, street_crossing_part]),
        (service_flow_marker_count, "service_flow", "service_flow", service_flow_part, depth * 10.14, height * 0.20, width * 0.084, height * 0.018, depth * 0.018, [utility_corridor_part, service_connection_part]),
        (public_space_plan_marker_count, "public_space_plan", "park", public_space_plan_part, depth * 10.16, height * 0.30, width * 0.060, height * 0.030, depth * 0.032, [service_coverage_part, courtyard_part]),
        (growth_boundary_marker_count, "growth_boundary", "boundary", growth_boundary_part, depth * 10.18, height * 0.24, width * 0.090, height * 0.022, depth * 0.022, [zoning_rule_part, settlement_pressure_part]),
        (district_dependency_marker_count, "district_dependency", "dependency", district_dependency_part, depth * 10.20, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [service_coverage_part, resource_flow_part]),
        (development_pressure_marker_count, "development_pressure", "pressure", development_pressure_part, depth * 10.22, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [settlement_pressure_part, build_permit_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in city_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "city_planning", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    resilience_marker_specs = [
        (resilience_plan_marker_count, "resilience_plan", "resilience", resilience_plan_part, depth * 10.14, height * 0.48, width * 0.082, height * 0.050, depth * 0.042, [climate_risk_map_part, green_infrastructure_part]),
        (climate_zone_marker_count, "climate_zone", "climate", climate_zone_part, depth * 10.20, height * 0.36, width * 0.060, height * 0.036, depth * 0.028, [biome_system_part, weather_part]),
        (climate_risk_map_marker_count, "climate_risk_map", "risk_map", climate_risk_map_part, depth * 10.26, height * 0.34, width * 0.052, height * 0.034, depth * 0.026, [flood_risk_part, risk_mitigation_part]),
        (flood_risk_marker_count, "flood_risk", "flood", flood_risk_part, depth * 10.32, height * 0.28, width * 0.064, height * 0.026, depth * 0.030, [stormwater_system_part, evacuation_route_part]),
        (fire_risk_marker_count, "fire_risk", "fire", fire_risk_part, depth * 10.38, height * 0.32, width * 0.048, height * 0.034, depth * 0.028, [protected_land_part, evacuation_route_part]),
        (heat_risk_marker_count, "heat_risk", "heat", heat_risk_part, depth * 10.44, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [cooling_corridor_part, green_infrastructure_part]),
        (resource_constraint_marker_count, "resource_constraint", "constraint", resource_constraint_part, depth * 10.50, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [scarcity_loop_part, resource_claim_part]),
        (protected_land_marker_count, "protected_land", "protected", protected_land_part, depth * 10.56, height * 0.30, width * 0.064, height * 0.030, depth * 0.030, [conservation_zone_part, zoning_rule_part]),
        (green_infrastructure_marker_count, "green_infrastructure", "green", green_infrastructure_part, depth * 10.62, height * 0.32, width * 0.062, height * 0.032, depth * 0.030, [protected_land_part, stormwater_system_part]),
        (stormwater_system_marker_count, "stormwater_system", "stormwater", stormwater_system_part, depth * 10.68, height * 0.24, width * 0.082, height * 0.024, depth * 0.022, [utility_part, resource_flow_part]),
        (cooling_corridor_marker_count, "cooling_corridor", "cooling", cooling_corridor_part, depth * 10.74, height * 0.22, width * 0.086, height * 0.022, depth * 0.020, [street_hierarchy_part, public_space_plan_part]),
        (evacuation_route_marker_count, "evacuation_route", "evacuation", evacuation_route_part, depth * 10.80, height * 0.20, width * 0.090, height * 0.020, depth * 0.018, [street_hierarchy_part, emergency_shelter_part]),
        (emergency_shelter_marker_count, "emergency_shelter", "shelter", emergency_shelter_part, depth * 10.86, height * 0.38, width * 0.054, height * 0.042, depth * 0.030, [occupancy_plan_part, service_coverage_part]),
        (climate_adaptation_marker_count, "climate_adaptation", "adaptation", climate_adaptation_part, depth * 10.92, height * 0.36, width * 0.052, height * 0.038, depth * 0.028, [green_infrastructure_part, risk_mitigation_part]),
        (transit_oriented_growth_marker_count, "transit_oriented_growth", "tod", transit_oriented_growth_part, depth * 10.98, height * 0.36, width * 0.056, height * 0.038, depth * 0.030, [transit_node_part, zoning_district_part]),
        (risk_mitigation_marker_count, "risk_mitigation", "mitigation", risk_mitigation_part, depth * 11.04, height * 0.34, width * 0.048, height * 0.034, depth * 0.026, [climate_adaptation_part, world_metric_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in resilience_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "climate_resilience", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    infrastructure_network_marker_specs = [
        (power_grid_marker_count, "power_grid", "grid", power_grid_part, depth * 11.10, height * 0.44, width * 0.086, height * 0.044, depth * 0.036, [substation_part, power_line_part]),
        (substation_marker_count, "substation", "substation", substation_part, depth * 11.16, height * 0.38, width * 0.056, height * 0.044, depth * 0.032, [transformer_bank_part, power_line_part]),
        (transformer_bank_marker_count, "transformer_bank", "transformer", transformer_bank_part, depth * 11.22, height * 0.36, width * 0.048, height * 0.038, depth * 0.028, [substation_part, service_connection_part]),
        (power_line_marker_count, "power_line", "power_line", power_line_part, depth * 11.28, height * 0.22, width * 0.096, height * 0.020, depth * 0.018, [power_grid_part, service_connection_part]),
        (water_network_marker_count, "water_network", "water", water_network_part, depth * 11.34, height * 0.30, width * 0.086, height * 0.026, depth * 0.026, [pump_station_part, water_tower_part]),
        (pump_station_marker_count, "pump_station", "pump", pump_station_part, depth * 11.40, height * 0.34, width * 0.052, height * 0.038, depth * 0.030, [water_network_part, service_connection_part]),
        (water_tower_marker_count, "water_tower", "tower", water_tower_part, depth * 11.46, height * 0.46, width * 0.046, height * 0.070, depth * 0.034, [water_network_part, service_connection_part]),
        (sewer_network_marker_count, "sewer_network", "sewer", sewer_network_part, depth * 11.52, height * 0.22, width * 0.090, height * 0.022, depth * 0.026, [treatment_plant_part, service_connection_part]),
        (treatment_plant_marker_count, "treatment_plant", "treatment", treatment_plant_part, depth * 11.58, height * 0.36, width * 0.058, height * 0.040, depth * 0.034, [sewer_network_part, water_network_part]),
        (data_network_marker_count, "data_network", "data", data_network_part, depth * 11.64, height * 0.34, width * 0.080, height * 0.028, depth * 0.026, [data_hub_part, fiber_line_part]),
        (data_hub_marker_count, "data_hub", "hub", data_hub_part, depth * 11.70, height * 0.38, width * 0.052, height * 0.040, depth * 0.030, [data_network_part, service_connection_part]),
        (fiber_line_marker_count, "fiber_line", "fiber", fiber_line_part, depth * 11.76, height * 0.24, width * 0.096, height * 0.018, depth * 0.018, [data_hub_part, service_connection_part]),
        (transit_line_marker_count, "transit_line", "transit_line", transit_line_part, depth * 11.82, height * 0.26, width * 0.100, height * 0.022, depth * 0.024, [transit_station_part, service_connection_part]),
        (transit_station_marker_count, "transit_station", "station", transit_station_part, depth * 11.88, height * 0.38, width * 0.056, height * 0.042, depth * 0.032, [transit_line_part, service_coverage_part]),
        (service_connection_marker_count, "service_connection", "tap", service_connection_part, depth * 11.94, height * 0.30, width * 0.040, height * 0.030, depth * 0.024, [utility_corridor_part, resource_flow_part]),
        (maintenance_access_marker_count, "maintenance_access", "access", maintenance_access_part, depth * 12.00, height * 0.24, width * 0.088, height * 0.020, depth * 0.022, [service_connection_part, access_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in infrastructure_network_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "infrastructure_network", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    building_service_marker_specs = [
        (building_service_plan_marker_count, "building_service_plan", "service_plan", building_service_plan_part, depth * 12.06, height * 0.46, width * 0.080, height * 0.048, depth * 0.038, [service_core_part, utility_room_part]),
        (service_core_marker_count, "service_core", "core", service_core_part, depth * 12.12, height * 0.52, width * 0.046, height * 0.082, depth * 0.034, [electrical_panel_part, plumbing_stack_part]),
        (utility_room_marker_count, "utility_room", "utility_room", utility_room_part, depth * 12.18, height * 0.34, width * 0.058, height * 0.038, depth * 0.032, [meter_bank_part, service_connection_part]),
        (mechanical_room_marker_count, "mechanical_room", "mechanical", mechanical_room_part, depth * 12.24, height * 0.38, width * 0.062, height * 0.042, depth * 0.034, [hvac_system_part, electrical_panel_part]),
        (electrical_panel_marker_count, "electrical_panel", "panel", electrical_panel_part, depth * 12.30, height * 0.36, width * 0.036, height * 0.040, depth * 0.022, [power_grid_part, service_connection_part]),
        (meter_bank_marker_count, "meter_bank", "meter", meter_bank_part, depth * 12.36, height * 0.34, width * 0.040, height * 0.034, depth * 0.024, [electrical_panel_part, water_network_part]),
        (plumbing_stack_marker_count, "plumbing_stack", "plumbing", plumbing_stack_part, depth * 12.42, height * 0.42, width * 0.038, height * 0.070, depth * 0.024, [water_network_part, sewer_network_part]),
        (hvac_system_marker_count, "hvac_system", "hvac", hvac_system_part, depth * 12.48, height * 0.38, width * 0.058, height * 0.038, depth * 0.032, [mechanical_room_part, ventilation_duct_part]),
        (ventilation_duct_marker_count, "ventilation_duct", "duct", ventilation_duct_part, depth * 12.54, height * 0.30, width * 0.090, height * 0.022, depth * 0.020, [hvac_system_part, service_shaft_part]),
        (elevator_core_marker_count, "elevator_core", "elevator_core", elevator_core_part, depth * 12.60, height * 0.48, width * 0.044, height * 0.074, depth * 0.034, [service_elevator_part, service_shaft_part]),
        (service_elevator_marker_count, "service_elevator", "service_lift", service_elevator_part, depth * 12.66, height * 0.42, width * 0.042, height * 0.062, depth * 0.030, [elevator_core_part, loading_dock_part]),
        (service_shaft_marker_count, "service_shaft", "shaft", service_shaft_part, depth * 12.72, height * 0.46, width * 0.036, height * 0.074, depth * 0.026, [plumbing_stack_part, ventilation_duct_part]),
        (fire_suppression_marker_count, "fire_suppression", "fire", fire_suppression_part, depth * 12.78, height * 0.34, width * 0.052, height * 0.034, depth * 0.030, [sprinkler_zone_part, plumbing_stack_part]),
        (sprinkler_zone_marker_count, "sprinkler_zone", "sprinkler", sprinkler_zone_part, depth * 12.84, height * 0.30, width * 0.046, height * 0.028, depth * 0.026, [fire_suppression_part, water_network_part]),
        (waste_chute_marker_count, "waste_chute", "chute", waste_chute_part, depth * 12.90, height * 0.40, width * 0.036, height * 0.064, depth * 0.026, [sewer_network_part, maintenance_access_part]),
        (loading_dock_marker_count, "loading_dock", "dock", loading_dock_part, depth * 12.96, height * 0.26, width * 0.082, height * 0.024, depth * 0.040, [service_connection_part, maintenance_access_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in building_service_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "building_services", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    functional_interior_marker_specs = [
        (room_program_marker_count, "room_program", "program", functional_room_part, depth * 13.02, height * 0.34, width * 0.090, height * 0.040, depth * 0.038, [interior_part, service_core_part]),
        (bathroom_marker_count, "bathroom", "wet_room", bathroom_part, depth * 13.08, height * 0.30, width * 0.056, height * 0.034, depth * 0.030, [sanitary_fixture_part, plumbing_stack_part]),
        (kitchen_marker_count, "kitchen", "kitchen", kitchen_part, depth * 13.14, height * 0.32, width * 0.068, height * 0.034, depth * 0.032, [counter_run_part, appliance_bank_part]),
        (lab_room_marker_count, "lab_room", "lab", lab_room_part, depth * 13.20, height * 0.34, width * 0.070, height * 0.038, depth * 0.032, [lab_bench_part, service_connection_part]),
        (med_bay_marker_count, "med_bay", "medical", med_bay_part, depth * 13.26, height * 0.32, width * 0.064, height * 0.036, depth * 0.032, [medical_bed_part, sanitary_fixture_part]),
        (workshop_room_marker_count, "workshop_room", "workshop", workshop_room_part, depth * 13.32, height * 0.34, width * 0.070, height * 0.038, depth * 0.034, [workstation_cluster_part, tool_rack_part]),
        (control_room_marker_count, "control_room", "control", control_room_part, depth * 13.38, height * 0.36, width * 0.068, height * 0.040, depth * 0.032, [control_panel_part, workstation_cluster_part]),
        (storage_room_marker_count, "storage_room", "storage", storage_room_part, depth * 13.44, height * 0.30, width * 0.060, height * 0.034, depth * 0.032, [cabinet_wall_part, tool_rack_part]),
        (office_room_marker_count, "office_room", "office", office_room_part, depth * 13.50, height * 0.32, width * 0.062, height * 0.034, depth * 0.030, [workstation_cluster_part, cabinet_wall_part]),
        (bedroom_marker_count, "bedroom", "bedroom", bedroom_part, depth * 13.56, height * 0.30, width * 0.058, height * 0.034, depth * 0.030, [medical_bed_part, fixture_cluster_part]),
        (fixture_cluster_marker_count, "fixture_cluster", "fixtures", fixture_cluster_part, depth * 13.62, height * 0.28, width * 0.050, height * 0.030, depth * 0.026, [furniture_part, service_connection_part]),
        (appliance_bank_marker_count, "appliance_bank", "appliances", appliance_bank_part, depth * 13.68, height * 0.30, width * 0.054, height * 0.032, depth * 0.028, [counter_run_part, service_connection_part]),
        (workstation_cluster_marker_count, "workstation_cluster", "workstations", workstation_cluster_part, depth * 13.74, height * 0.30, width * 0.060, height * 0.032, depth * 0.030, [terminal_part, service_connection_part]),
        (cabinet_wall_marker_count, "cabinet_wall", "cabinets", cabinet_wall_part, depth * 13.80, height * 0.34, width * 0.062, height * 0.050, depth * 0.018, [furniture_shelf_part, world_metric_part]),
        (counter_run_marker_count, "counter_run", "counter", counter_run_part, depth * 13.86, height * 0.26, width * 0.070, height * 0.024, depth * 0.024, [furniture_part, service_connection_part]),
        (sanitary_fixture_marker_count, "sanitary_fixture", "sanitary", sanitary_fixture_part, depth * 13.92, height * 0.28, width * 0.038, height * 0.032, depth * 0.024, [plumbing_stack_part, resource_flow_part]),
        (lab_bench_marker_count, "lab_bench", "bench", lab_bench_part, depth * 13.98, height * 0.30, width * 0.056, height * 0.030, depth * 0.026, [service_connection_part, world_metric_part]),
        (medical_bed_marker_count, "medical_bed", "bed", medical_bed_part, depth * 14.04, height * 0.28, width * 0.052, height * 0.028, depth * 0.030, [service_connection_part, interior_light_part]),
        (tool_rack_marker_count, "tool_rack", "tools", tool_rack_part, depth * 14.10, height * 0.32, width * 0.046, height * 0.046, depth * 0.020, [furniture_shelf_part, interaction_prompt_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in functional_interior_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "functional_interiors", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    interior_composition_marker_specs = [
        (room_adjacency_marker_count, "room_adjacency", "adjacency", room_adjacency_part, depth * 14.16, height * 0.22, width * 0.082, height * 0.024, depth * 0.024, [room_connection_part, functional_room_part]),
        (room_connection_marker_count, "room_connection", "connection", room_connection_part, depth * 14.22, height * 0.24, width * 0.066, height * 0.026, depth * 0.026, [door_opening_part, corridor_link_part]),
        (door_opening_marker_count, "door_opening", "opening", door_opening_part, depth * 14.28, height * 0.30, width * 0.040, height * 0.052, depth * 0.018, [wall_run_part, access_part]),
        (corridor_link_marker_count, "corridor_link", "corridor", corridor_link_part, depth * 14.34, height * 0.16, width * 0.088, height * 0.018, depth * 0.022, [room_socket_part, access_part]),
        (wall_run_marker_count, "wall_run", "wall", wall_run_part, depth * 14.40, height * 0.34, width * 0.082, height * 0.052, depth * 0.016, [door_opening_part, fixture_socket_part]),
        (room_socket_marker_count, "room_socket", "room_socket", room_socket_part, depth * 14.46, height * 0.20, width * 0.034, height * 0.024, depth * 0.024, [functional_room_part, fixture_socket_part]),
        (fixture_socket_marker_count, "fixture_socket", "fixture_socket", fixture_socket_part, depth * 14.52, height * 0.24, width * 0.030, height * 0.026, depth * 0.022, [fixture_cluster_part, room_socket_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in interior_composition_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "interior_composition", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    placement_constraint_marker_specs = [
        (socket_binding_marker_count, "socket_binding", "binding", socket_binding_part, depth * 14.58, height * 0.22, width * 0.036, height * 0.024, depth * 0.024, [room_socket_part, fixture_socket_part]),
        (fixture_placement_marker_count, "fixture_placement", "fixture_place", fixture_placement_part, depth * 14.64, height * 0.26, width * 0.044, height * 0.028, depth * 0.026, [fixture_socket_part, fixture_cluster_part]),
        (furniture_placement_marker_count, "furniture_placement", "furniture_place", furniture_placement_part, depth * 14.70, height * 0.26, width * 0.046, height * 0.028, depth * 0.028, [fixture_socket_part, furniture_part]),
        (service_placement_marker_count, "service_placement", "service_place", service_placement_part, depth * 14.76, height * 0.24, width * 0.040, height * 0.026, depth * 0.024, [service_connection_part, fixture_socket_part]),
        (wall_attachment_marker_count, "wall_attachment", "wall_attach", wall_attachment_part, depth * 14.82, height * 0.32, width * 0.046, height * 0.044, depth * 0.016, [wall_run_part, fixture_socket_part]),
        (anchor_rule_marker_count, "anchor_rule", "anchor", anchor_rule_part, depth * 14.88, height * 0.24, width * 0.034, height * 0.026, depth * 0.024, [room_socket_part, world_metric_part]),
        (placement_constraint_marker_count, "placement_constraint", "constraint", placement_constraint_part, depth * 14.94, height * 0.22, width * 0.050, height * 0.024, depth * 0.024, [anchor_rule_part, world_metric_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in placement_constraint_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "placement_constraints", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    auto_layout_marker_specs = [
        (auto_layout_marker_count, "auto_layout", "auto_layout", auto_layout_part, depth * 15.00, height * 0.30, width * 0.060, height * 0.032, depth * 0.028, [room_layout_plan_part, placement_constraint_part]),
        (room_layout_plan_marker_count, "room_layout_plan", "room_plan", room_layout_plan_part, depth * 15.06, height * 0.28, width * 0.056, height * 0.030, depth * 0.026, [room_socket_part, wall_run_part]),
        (fixture_layout_marker_count, "fixture_layout", "fixture_plan", fixture_layout_part, depth * 15.12, height * 0.26, width * 0.048, height * 0.028, depth * 0.026, [fixture_placement_part, fixture_socket_part]),
        (furniture_layout_marker_count, "furniture_layout", "furniture_plan", furniture_layout_part, depth * 15.18, height * 0.26, width * 0.048, height * 0.028, depth * 0.026, [furniture_placement_part, fixture_socket_part]),
        (service_layout_marker_count, "service_layout", "service_plan", service_layout_part, depth * 15.24, height * 0.24, width * 0.044, height * 0.026, depth * 0.024, [service_placement_part, service_connection_part]),
        (wall_fixture_layout_marker_count, "wall_fixture_layout", "wall_fixture_plan", wall_fixture_layout_part, depth * 15.30, height * 0.30, width * 0.050, height * 0.034, depth * 0.016, [wall_attachment_part, wall_run_part]),
        (layout_zone_marker_count, "layout_zone", "zone", layout_zone_part, depth * 15.36, height * 0.18, width * 0.034, height * 0.020, depth * 0.022, [room_layout_plan_part, room_socket_part]),
        (layout_socket_marker_count, "layout_socket", "slot", layout_socket_part, depth * 15.42, height * 0.20, width * 0.026, height * 0.020, depth * 0.020, [room_socket_part, fixture_socket_part]),
        (auto_placed_marker_count, "auto_placed", "placed", auto_placed_part, depth * 15.48, height * 0.22, width * 0.032, height * 0.024, depth * 0.022, [socket_binding_part, fixture_placement_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in auto_layout_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "auto_layout", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    layout_resolution_marker_specs = [
        (layout_solver_marker_count, "layout_solver", "solver", layout_solver_part, depth * 15.54, height * 0.32, width * 0.062, height * 0.034, depth * 0.030, [auto_layout_part, room_bounds_part]),
        (room_bounds_marker_count, "room_bounds", "bounds", room_bounds_part, depth * 15.60, height * 0.18, width * 0.070, height * 0.018, depth * 0.040, [wall_run_part, layout_zone_part]),
        (wall_side_rule_marker_count, "wall_side_rule", "wall_rule", wall_side_rule_part, depth * 15.66, height * 0.28, width * 0.048, height * 0.030, depth * 0.018, [wall_run_part, socket_priority_part]),
        (socket_priority_marker_count, "socket_priority", "priority", socket_priority_part, depth * 15.72, height * 0.24, width * 0.032, height * 0.026, depth * 0.022, [room_socket_part, world_metric_part]),
        (clearance_zone_marker_count, "clearance_zone", "clearance", clearance_zone_part, depth * 15.78, height * 0.16, width * 0.044, height * 0.014, depth * 0.032, [placement_constraint_part, world_metric_part]),
        (layout_slot_marker_count, "layout_slot", "slot", layout_slot_part, depth * 15.84, height * 0.20, width * 0.026, height * 0.020, depth * 0.020, [room_socket_part, fixture_socket_part]),
        (resolved_slot_marker_count, "resolved_slot", "resolved", resolved_slot_part, depth * 15.90, height * 0.22, width * 0.028, height * 0.022, depth * 0.022, [layout_slot_part, socket_binding_part]),
        (blocked_slot_marker_count, "blocked_slot", "blocked", blocked_slot_part, depth * 15.96, height * 0.12, width * 0.030, height * 0.012, depth * 0.030, [clearance_zone_part, placement_constraint_part]),
        (priority_socket_marker_count, "priority_socket", "priority_socket", priority_socket_part, depth * 16.02, height * 0.24, width * 0.030, height * 0.024, depth * 0.022, [socket_priority_part, room_socket_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in layout_resolution_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "layout_resolution", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    footprint_packing_marker_specs = [
        (footprint_packer_marker_count, "footprint_packer", "packer", footprint_packer_part, depth * 16.08, height * 0.32, width * 0.064, height * 0.034, depth * 0.030, [layout_solver_part, placement_footprint_part]),
        (placement_footprint_marker_count, "placement_footprint", "footprint", placement_footprint_part, depth * 16.14, height * 0.22, width * 0.038, height * 0.022, depth * 0.032, [layout_slot_part, clearance_zone_part]),
        (occupancy_grid_marker_count, "occupancy_grid", "grid", occupancy_grid_part, depth * 16.20, height * 0.16, width * 0.060, height * 0.014, depth * 0.044, [layout_slot_part, free_cell_part]),
        (fit_profile_marker_count, "fit_profile", "fit", fit_profile_part, depth * 16.26, height * 0.24, width * 0.034, height * 0.026, depth * 0.022, [socket_priority_part, placement_constraint_part]),
        (collision_rule_marker_count, "collision_rule", "collision", collision_rule_part, depth * 16.32, height * 0.16, width * 0.040, height * 0.014, depth * 0.032, [clearance_zone_part, placement_constraint_part]),
        (service_reach_marker_count, "service_reach", "service_reach", service_reach_part, depth * 16.38, height * 0.24, width * 0.040, height * 0.024, depth * 0.026, [service_placement_part, socket_priority_part]),
        (occupied_cell_marker_count, "occupied_cell", "occupied", occupied_cell_part, depth * 16.44, height * 0.13, width * 0.022, height * 0.012, depth * 0.022, [occupancy_grid_part, blocked_slot_part]),
        (free_cell_marker_count, "free_cell", "free", free_cell_part, depth * 16.50, height * 0.18, width * 0.022, height * 0.014, depth * 0.022, [occupancy_grid_part, layout_slot_part]),
        (packed_item_marker_count, "packed_item", "packed", packed_item_part, depth * 16.56, height * 0.24, width * 0.032, height * 0.024, depth * 0.026, [placement_footprint_part, socket_binding_part]),
        (collision_pair_marker_count, "collision_pair", "collision_pair", collision_pair_part, depth * 16.62, height * 0.15, width * 0.030, height * 0.012, depth * 0.026, [collision_rule_part, clearance_zone_part]),
        (room_packing_solver_marker_count, "room_packing_solver", "transform_solver", room_packing_solver_part, depth * 16.64, height * 0.30, width * 0.060, height * 0.032, depth * 0.030, [footprint_packer_part, packing_slot_part]),
        (packing_slot_marker_count, "packing_slot", "packing_slot", packing_slot_part, depth * 16.65, height * 0.20, width * 0.026, height * 0.020, depth * 0.022, [layout_slot_part, packed_transform_part]),
        (packed_transform_marker_count, "packed_transform", "packed_transform", packed_transform_part, depth * 16.66, height * 0.24, width * 0.030, height * 0.024, depth * 0.026, [packing_slot_part, placement_footprint_part]),
        (clearance_reservation_marker_count, "clearance_reservation", "clearance_reservation", clearance_reservation_part, depth * 16.67, height * 0.16, width * 0.036, height * 0.014, depth * 0.030, [packed_transform_part, clearance_zone_part]),
        (service_anchor_map_marker_count, "service_anchor_map", "service_anchor_map", service_anchor_map_part, depth * 16.675, height * 0.24, width * 0.040, height * 0.024, depth * 0.026, [service_reach_part, service_anchor_part]),
        (service_anchor_marker_count, "service_anchor", "service_anchor", service_anchor_part, depth * 16.677, height * 0.20, width * 0.024, height * 0.020, depth * 0.022, [service_anchor_map_part, service_placement_part]),
        (room_content_plan_marker_count, "room_content_plan", "content_plan", room_content_plan_part, depth * 16.682, height * 0.30, width * 0.060, height * 0.032, depth * 0.030, [room_packing_solver_part, packed_child_asset_part]),
        (content_family_binding_marker_count, "content_family_binding", "family_binding", content_family_binding_part, depth * 16.686, height * 0.24, width * 0.034, height * 0.022, depth * 0.024, [room_content_plan_part, furniture_asset_part]),
        (furniture_asset_marker_count, "furniture_asset", "furniture_asset", furniture_asset_part, depth * 16.690, height * 0.26, width * 0.034, height * 0.026, depth * 0.026, [packed_transform_part, placement_footprint_part]),
        (fixture_asset_marker_count, "fixture_asset", "fixture_asset", fixture_asset_part, depth * 16.694, height * 0.26, width * 0.034, height * 0.026, depth * 0.026, [packed_transform_part, service_anchor_map_part]),
        (packed_child_asset_marker_count, "packed_child_asset", "child_asset", packed_child_asset_part, depth * 16.698, height * 0.24, width * 0.030, height * 0.024, depth * 0.024, [furniture_asset_part, fixture_asset_part]),
        (content_surface_plan_marker_count, "content_surface_plan", "surface_plan", content_surface_plan_part, depth * 16.702, height * 0.24, width * 0.040, height * 0.024, depth * 0.024, [packed_child_asset_part, content_material_zone_part]),
        (content_material_zone_marker_count, "content_material_zone", "content_zone", content_material_zone_part, depth * 16.706, height * 0.20, width * 0.030, height * 0.020, depth * 0.022, [content_surface_plan_part, material_zone_part]),
        (content_finish_preset_marker_count, "content_finish_preset", "finish_preset", content_finish_preset_part, depth * 16.710, height * 0.22, width * 0.034, height * 0.022, depth * 0.022, [content_surface_plan_part, surface_layer_part]),
        (content_wear_profile_marker_count, "content_wear_profile", "wear_profile", content_wear_profile_part, depth * 16.714, height * 0.18, width * 0.034, height * 0.014, depth * 0.024, [content_surface_plan_part, wear_part]),
        (content_marking_set_marker_count, "content_marking_set", "marking_set", content_marking_set_part, depth * 16.718, height * 0.20, width * 0.030, height * 0.016, depth * 0.022, [content_surface_plan_part, decal_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in footprint_packing_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "footprint_packing", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    role_pack_marker_specs = [
        (room_pack_preset_marker_count, "room_pack_preset", "room_preset", room_pack_preset_part, depth * 16.68, height * 0.32, width * 0.066, height * 0.034, depth * 0.030, [footprint_packer_part, role_item_set_part]),
        (footprint_size_preset_marker_count, "footprint_size_preset", "size_preset", footprint_size_preset_part, depth * 16.74, height * 0.24, width * 0.046, height * 0.026, depth * 0.026, [placement_footprint_part, preset_item_part]),
        (packing_policy_preset_marker_count, "packing_policy_preset", "policy_preset", packing_policy_preset_part, depth * 16.80, height * 0.24, width * 0.044, height * 0.026, depth * 0.026, [fit_profile_part, collision_rule_part]),
        (clearance_preset_marker_count, "clearance_preset", "clearance_preset", clearance_preset_part, depth * 16.86, height * 0.18, width * 0.044, height * 0.016, depth * 0.032, [clearance_zone_part, collision_rule_part]),
        (service_reach_preset_marker_count, "service_reach_preset", "service_preset", service_reach_preset_part, depth * 16.92, height * 0.24, width * 0.044, height * 0.024, depth * 0.026, [service_reach_part, service_placement_part]),
        (role_item_set_marker_count, "role_item_set", "item_set", role_item_set_part, depth * 16.98, height * 0.22, width * 0.050, height * 0.022, depth * 0.026, [preset_item_part, placement_footprint_part]),
        (preset_item_marker_count, "preset_item", "preset_item", preset_item_part, depth * 17.04, height * 0.22, width * 0.028, height * 0.022, depth * 0.022, [role_item_set_part, placement_footprint_part]),
        (role_preset_marker_count, "role_preset", "role", role_preset_part, depth * 17.10, height * 0.28, width * 0.034, height * 0.026, depth * 0.024, [room_pack_preset_part, footprint_packer_part]),
        (policy_rule_marker_count, "policy_rule", "policy_rule", policy_rule_part, depth * 17.16, height * 0.20, width * 0.028, height * 0.020, depth * 0.020, [packing_policy_preset_part, fit_profile_part]),
    ]
    for count, construct_name, marker, part, z, y, sx, sy, sz, adjacency in role_pack_marker_specs:
        for index in range(count):
            x = -width * 0.50 + width * 1.00 * ((index + 0.5) / max(1, count))
            components.append(
                _component(
                    f"setpiece_{construct_name}_{index:02d}_{marker}_region",
                    f"{construct_name}_marker",
                    part,
                    (x, y, z),
                    (sx, sy, sz),
                    tags=["setpiece", "role_pack_preset", construct_name, marker, archetype, layout, f"{construct_name}_{index}"],
                    adjacency=adjacency,
                )
            )

    route_profile = path_profile_from_controls(
        controls,
        family="procedural_setpiece",
        segment_count=max(1, road_segment_count),
        length=depth * 0.92,
        width=route_width,
        height=height,
        default_profile="network" if branch_count else "straight",
    )
    for segment in route_profile["segments"][:road_segment_count or 1]:
        index = int(segment["index"])
        x, y, z = segment["center"]
        seg_width, seg_depth = segment["extents"]
        components.append(
            _component(
                f"setpiece_route_{index:02d}_region",
                "road",
                road_part,
                (x, height * 0.075 + y, z),
                (max(seg_width, route_width), height * 0.045, seg_depth),
                tags=["setpiece", "road", "route", archetype, layout, *list(segment.get("tags", []))],
                adjacency=[base_part, courtyard_part],
            )
        )
    for branch in route_profile["branches"][:branch_count]:
        index = int(branch["index"])
        x, y, z = branch["center"]
        branch_width, branch_depth = branch["extents"]
        components.append(
            _component(
                f"setpiece_branch_route_{index:02d}_region",
                "road_branch",
                road_part,
                (x, height * 0.078 + y, z),
                (branch_width, height * 0.04, branch_depth),
                tags=["setpiece", "road", "branch", archetype, layout, *list(branch.get("tags", []))],
                adjacency=[base_part, road_part],
            )
        )
    _append_structural_elements(
        components,
        structural_elements_for_path(
            controls,
            family="procedural_setpiece",
            path_profile=route_profile,
            width=route_width * 1.6,
            height=height * 0.34,
            base_y=height * 0.08,
            limit=road_segment_count or 1,
        ),
        {
            "edge": perimeter_part,
            "wall": perimeter_part,
            "roof": access_part,
            "support": tower_part,
            "truss": access_part,
            "default": base_part,
        },
        adjacency=[base_part, road_part],
    )

    structure_slots = [
        (-0.30, -0.20),
        (0.32, -0.24),
        (-0.36, 0.28),
        (0.36, 0.25),
        (0.0, -0.38),
        (0.0, 0.40),
        (-0.50, 0.0),
        (0.50, 0.0),
    ]
    for index in range(structure_count):
        sx, sz = structure_slots[index % len(structure_slots)]
        part = building_part if index == 0 else secondary_part
        local_h = building_h * (1.18 if index == 0 else 0.72 + 0.08 * (index % 3))
        local_w = width * (0.24 if index == 0 else 0.18)
        local_d = depth * (0.20 if index == 0 else 0.16)
        components.append(
            _component(
                f"setpiece_structure_{index:02d}_region",
                "shell",
                part,
                (sx * width, local_h * 0.52, sz * depth),
                (local_w, local_h, local_d),
                tags=["setpiece", "building", "structure", archetype, layout, f"structure_{index}"],
                adjacency=[base_part, courtyard_part, road_part],
            )
        )
        components.append(
            _component(
                f"setpiece_structure_{index:02d}_roof_region",
                "roof",
                part,
                (sx * width, local_h + height * 0.045, sz * depth),
                (local_w * 1.10, height * 0.07, local_d * 1.12),
                tags=["setpiece", "roof", "building", archetype, layout, f"structure_{index}"],
                adjacency=[part],
            )
        )

    _append_structural_elements(
        components,
        structural_elements_for_facade(
            controls,
            family="procedural_setpiece",
            width=width * 0.30,
            depth=depth * 0.22,
            height=building_h,
            floors=max(1, _count(controls, "floor_count", "floors", default=2, minimum=1, maximum=8)),
            bays=max(2, _count(controls, "bay_count", "bays", default=4, minimum=1, maximum=10)),
        ),
        {
            "wall": building_part,
            "trim": secondary_part,
            "support": ritual_part if archetype == "temple" else perimeter_part,
            "roof": building_part,
            "default": building_part,
        },
        adjacency=[building_part],
    )

    for index in range(tower_count):
        angle = (index / max(1, tower_count)) * np.pi * 2.0
        x = np.cos(angle) * width * 0.43
        z = np.sin(angle) * depth * 0.36
        tower_h = height * (0.78 + 0.10 * (index % 2))
        components.append(
            _component(
                f"setpiece_tower_{index:02d}_region",
                "tower",
                tower_part,
                (float(x), tower_h * 0.52, float(z)),
                (width * 0.095, tower_h, width * 0.095),
                tags=["setpiece", "tower", "watchtower", archetype, layout, f"tower_{index}"],
                adjacency=[base_part, perimeter_part, building_part],
                radius=width * 0.045,
                height=tower_h,
            )
        )

    for index in range(perimeter_count):
        t = index / max(1, perimeter_count)
        side = index % 4
        if side == 0:
            x, z, extents = -width * 0.46 + width * 0.92 * t, depth * 0.47, (width * 0.18, height * 0.24, depth * 0.035)
        elif side == 1:
            x, z, extents = width * 0.47, -depth * 0.46 + depth * 0.92 * t, (width * 0.035, height * 0.24, depth * 0.18)
        elif side == 2:
            x, z, extents = width * 0.46 - width * 0.92 * t, -depth * 0.47, (width * 0.18, height * 0.24, depth * 0.035)
        else:
            x, z, extents = -width * 0.47, depth * 0.46 - depth * 0.92 * t, (width * 0.035, height * 0.24, depth * 0.18)
        components.append(
            _component(
                f"setpiece_perimeter_{index:02d}_region",
                "fence_segment",
                perimeter_part,
                (x, height * 0.18, z),
                extents,
                tags=["setpiece", "perimeter", "fence", archetype, layout, f"perimeter_{index}"],
                adjacency=[base_part, gate_part],
            )
        )
    for index in range(gate_count):
        x = (-0.22 + 0.44 * (index / max(1, gate_count - 1))) * width if gate_count > 1 else 0.0
        components.append(
            _component(
                f"setpiece_gate_{index:02d}_region",
                "gate_panel",
                gate_part,
                (x, height * 0.20, depth * 0.50),
                (width * 0.18, height * 0.34, depth * 0.045),
                tags=["setpiece", "gate", "entry", archetype, layout, f"gate_{index}"],
                adjacency=[perimeter_part, road_part],
            )
        )

    for index in range(access_count):
        x = -width * 0.34 + width * 0.68 * (index / max(1, access_count - 1)) if access_count > 1 else -width * 0.22
        z = depth * (-0.10 + 0.10 * (index % 3))
        component_type = "catwalk_deck" if index % 2 == 0 else "walkway_span"
        components.append(
            _component(
                f"setpiece_access_{index:02d}_region",
                component_type,
                access_part,
                (x, height * (0.30 + 0.04 * (index % 2)), z),
                (width * 0.24, height * 0.08, depth * 0.13),
                tags=["setpiece", "access", "walkway", archetype, layout, f"access_{index}"],
                adjacency=[building_part, road_part, utility_part],
            )
        )

    for index in range(infrastructure_count):
        x = -width * 0.42 + width * 0.84 * (index / max(1, infrastructure_count - 1)) if infrastructure_count > 1 else width * 0.22
        z = -depth * 0.42 + depth * 0.84 * ((index * 2 % max(1, infrastructure_count)) / max(1, infrastructure_count - 1)) if infrastructure_count > 1 else -depth * 0.24
        component_type = "pipe_run" if index % 3 == 0 else "overhead_conduit" if index % 3 == 1 else "junction_box"
        components.append(
            _component(
                f"setpiece_utility_{index:02d}_region",
                component_type,
                utility_part,
                (x, height * (0.20 if component_type == "junction_box" else 0.36), z),
                (width * (0.22 if component_type != "junction_box" else 0.12), height * 0.12, depth * 0.10),
                tags=["setpiece", "utility", "infrastructure", archetype, layout, f"utility_{index}"],
                adjacency=[base_part, building_part, access_part],
                radius=max(width * 0.018, 0.035),
                height=width * 0.22,
                axis="x",
            )
        )

    for index in range(prop_count):
        x = float(rng.uniform(-0.42, 0.42)) * width
        z = float(rng.uniform(-0.34, 0.34)) * depth
        component_type = "market_stall" if archetype == "market" and index % 2 == 0 else "street_crate" if index % 3 == 0 else "sign_post" if index % 3 == 1 else "streetlight"
        components.append(
            _component(
                f"setpiece_prop_{index:02d}_region",
                component_type,
                prop_part,
                (x, height * (0.18 if component_type != "streetlight" else 0.36), z),
                (width * 0.11, height * (0.22 if component_type != "streetlight" else 0.56), depth * 0.08),
                tags=["setpiece", "prop", component_type, archetype, layout, f"prop_{index}"],
                adjacency=[base_part, road_part, courtyard_part],
            )
        )

    for index in range(dock_count):
        x = -width * 0.34 + width * 0.68 * (index / max(1, dock_count - 1)) if dock_count > 1 else 0.0
        z = depth * (0.46 + 0.04 * (index % 2))
        components.append(
            _component(
                f"setpiece_dock_{index:02d}_region",
                "deck",
                dock_part,
                (x, height * 0.11, z),
                (width * 0.18, height * 0.08, depth * 0.26),
                tags=["setpiece", "dock", "pier", "waterfront", archetype, layout, f"dock_{index}"],
                adjacency=[base_part, road_part],
            )
        )
        components.append(
            _component(
                f"setpiece_dock_railing_{index:02d}_region",
                "railing",
                dock_part,
                (x, height * 0.26, z + depth * 0.12),
                (width * 0.17, height * 0.24, depth * 0.025),
                tags=["setpiece", "dock", "railing", archetype, layout, f"dock_{index}"],
                adjacency=[dock_part],
            )
        )

    for index in range(apron_count):
        z = -depth * (0.44 - 0.10 * index)
        components.append(
            _component(
                f"setpiece_apron_{index:02d}_region",
                "road",
                apron_part,
                (0.0, height * 0.08, z),
                (width * 0.72, height * 0.04, depth * 0.12),
                tags=["setpiece", "apron", "runway", archetype, layout, f"apron_{index}"],
                adjacency=[base_part, road_part],
            )
        )

    for index in range(column_count):
        angle = (index / max(1, column_count)) * np.pi * 2.0
        x = np.cos(angle) * width * 0.22
        z = np.sin(angle) * depth * 0.16
        components.append(
            _component(
                f"setpiece_ritual_column_{index:02d}_region",
                "column",
                ritual_part,
                (float(x), height * 0.30, float(z)),
                (width * 0.055, height * 0.54, width * 0.055),
                tags=["setpiece", "temple", "column", "ritual", archetype, layout, f"column_{index}"],
                adjacency=[courtyard_part, building_part],
                radius=width * 0.024,
                height=height * 0.54,
            )
        )
    if archetype == "temple":
        components.extend(
            [
                _component(
                    "setpiece_processional_stair_region",
                    "stair",
                    ritual_part,
                    (0.0, height * 0.12, depth * 0.30),
                    (width * 0.38, height * 0.18, depth * 0.16),
                    tags=["setpiece", "temple", "stair", "processional", archetype, layout],
                    adjacency=[courtyard_part, building_part],
                ),
                _component(
                    "setpiece_sanctuary_dome_region",
                    "dome",
                    ritual_part,
                    (0.0, building_h + height * 0.18, -depth * 0.22),
                    (width * 0.24, height * 0.28, width * 0.24),
                    tags=["setpiece", "temple", "dome", "sanctuary", archetype, layout],
                    adjacency=[building_part],
                    radius=width * 0.12,
                    height=height * 0.28,
                ),
            ]
        )

    def child_slot_entry(kind: str, index: int) -> dict[str, Any] | None:
        slots = child_slots_by_kind.get(kind, [])
        if index < len(slots):
            return slots[index]
        return None

    def child_slot(
        index: int,
        total: int,
        *,
        radius_x: float = 0.34,
        radius_z: float = 0.26,
        kind: str | None = None,
    ) -> tuple[float, float]:
        slot = child_slot_entry(kind, index) if kind else None
        position = slot.get("normalized_position") if isinstance(slot, dict) else None
        if isinstance(position, list | tuple) and len(position) >= 3:
            return float(position[0]) * width, float(position[2]) * depth
        if total <= 1:
            return width * 0.18, -depth * 0.18
        angle = (index / total) * np.pi * 2.0 + np.pi * 0.18
        return float(np.cos(angle) * width * radius_x), float(np.sin(angle) * depth * radius_z)

    def child_slot_id(kind: str, index: int) -> str:
        slot = child_slot_entry(kind, index)
        return str(slot.get("id") or f"{kind}_{index:02d}") if slot else f"{kind}_{index:02d}"

    def tag_token(value: Any) -> str:
        return str(value or "").strip().lower().replace(".", "_").replace("-", "_").replace(" ", "_")

    def child_slot_module(kind: str, index: int) -> dict[str, Any]:
        slot = child_slot_entry(kind, index)
        module = slot.get("module") if isinstance(slot, dict) else {}
        return dict(module) if isinstance(module, dict) else {}

    def child_module_controls(kind: str, index: int) -> dict[str, Any]:
        controls_payload = child_slot_module(kind, index).get("controls", {})
        return dict(controls_payload) if isinstance(controls_payload, dict) else {}

    def child_module_count(kind: str, index: int, *keys: str, default: int, minimum: int = 0, maximum: int = 12) -> int:
        module_controls = child_module_controls(kind, index)
        return _count(module_controls, *keys, default=default, minimum=minimum, maximum=maximum)

    def child_slot_tags(kind: str, index: int, *roles: str) -> list[str]:
        slot = child_slot_entry(kind, index)
        if not slot:
            return [f"{kind}_{index}", *roles]
        module = slot.get("module") if isinstance(slot.get("module"), dict) else {}
        tags = [
            f"slot_{slot.get('id')}",
            f"module_slot_{slot.get('id')}",
            f"socket_{slot.get('socket')}",
            f"anchor_{slot.get('anchor')}",
            f"module_instance_{tag_token(module.get('instance_id'))}" if module else "",
            f"module_template_{tag_token(module.get('template'))}" if module else "",
            f"module_family_{tag_token(module.get('family'))}" if module else "",
            f"module_archetype_{tag_token(module.get('archetype'))}" if module else "",
            "socket_addressed",
            *[str(tag) for tag in slot.get("tags", [])],
            *([str(tag) for tag in module.get("tags", [])] if module else []),
            *([f"module_component_{tag_token(component)}" for component in module.get("components", [])] if module else []),
            *roles,
        ]
        return list(dict.fromkeys(tag for tag in tags if tag))

    for index in range(vehicle_count):
        x, z = child_slot(index, max(1, vehicle_count), radius_x=0.30, radius_z=0.30, kind="vehicle")
        slot_id = child_slot_id("vehicle", index)
        vehicle_controls = child_module_controls("vehicle", index)
        drive_type = _choice(vehicle_controls, "drive_type", "vehicle_drive", default="wheeled")
        wheel_count = child_module_count("vehicle", index, "wheel_count", "wheels", default=0 if drive_type in {"rotor", "hover", "vtol"} else 4, maximum=8)
        rotor_count = child_module_count("vehicle", index, "rotor_count", "rotors", default=4 if drive_type in {"rotor", "vtol"} else 0, maximum=8)
        vehicle_cargo_count = child_module_count("vehicle", index, "cargo_module_count", "cargo_modules", "cargo_count", default=0, maximum=4)
        vehicle_turret_count = child_module_count("vehicle", index, "turret_count", "turrets", default=0, maximum=3)
        local_w = width * 0.18
        local_l = depth * 0.18
        local_h = height * 0.18
        components.extend(
            [
                _component(
                    f"setpiece_child_vehicle_{slot_id}_chassis_region",
                    "chassis",
                    vehicle_chassis_part,
                    (x, height * 0.16, z),
                    (local_w, local_h, local_l),
                    tags=["setpiece", "child_module", "vehicle", archetype, layout, *child_slot_tags("vehicle", index, "chassis")],
                    adjacency=[base_part, road_part, socket_part],
                ),
                _component(
                    f"setpiece_child_vehicle_{slot_id}_cabin_region",
                    "cabin",
                    vehicle_cabin_part,
                    (x, height * 0.29, z - local_l * 0.10),
                    (local_w * 0.64, local_h * 0.88, local_l * 0.42),
                    tags=["setpiece", "child_module", "vehicle", "cabin", archetype, layout, *child_slot_tags("vehicle", index, "cabin")],
                    adjacency=[vehicle_chassis_part],
                ),
            ]
        )
        axle_count = max(1, (wheel_count + 1) // 2)
        for wheel_index in range(wheel_count):
            side = "left" if wheel_index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            axle = wheel_index // 2
            longitudinal = 0.0 if axle_count <= 1 else -0.34 + 0.68 * (axle / max(1, axle_count - 1))
            components.append(
                _component(
                    f"setpiece_child_vehicle_{slot_id}_{side}_wheel_{axle:02d}_region",
                    "wheel",
                    vehicle_wheel_part,
                    (x + sign * local_w * 0.58, height * 0.11, z + longitudinal * local_l),
                    (local_w * 0.13, local_h * 0.58, local_h * 0.58),
                    tags=["setpiece", "child_module", "vehicle", "wheel", side, drive_type, archetype, layout, *child_slot_tags("vehicle", index, f"wheel_{wheel_index}")],
                    adjacency=[vehicle_chassis_part],
                    axis="x",
                    radius=local_h * 0.29,
                    height=local_w * 0.13,
                )
            )
        for rotor_index in range(rotor_count):
            angle = (rotor_index / max(1, rotor_count)) * np.pi * 2.0 + np.pi * 0.25
            components.append(
                _component(
                    f"setpiece_child_vehicle_{slot_id}_rotor_{rotor_index:02d}_region",
                    "rotor_pod",
                    vehicle_rotor_part,
                    (
                        x + float(np.cos(angle)) * local_w * 0.74,
                        height * 0.27,
                        z + float(np.sin(angle)) * local_l * 0.74,
                    ),
                    (local_h * 0.54, local_h * 0.22, local_h * 0.54),
                    tags=["setpiece", "child_module", "vehicle", "rotor", drive_type, archetype, layout, *child_slot_tags("vehicle", index, f"rotor_{rotor_index}")],
                    adjacency=[vehicle_chassis_part],
                    axis="y",
                    radius=local_h * 0.30,
                    height=local_h * 0.20,
                )
            )
        for cargo_index in range(vehicle_cargo_count):
            cargo_z = z + (0.22 + 0.18 * cargo_index) * local_l
            components.append(
                _component(
                    f"setpiece_child_vehicle_{slot_id}_cargo_{cargo_index:02d}_region",
                    "cargo_module",
                    vehicle_cargo_part,
                    (x, height * 0.25, cargo_z),
                    (local_w * 0.72, local_h * 0.78, local_l * 0.36),
                    tags=["setpiece", "child_module", "vehicle", "cargo", archetype, layout, *child_slot_tags("vehicle", index, f"cargo_{cargo_index}")],
                    adjacency=[vehicle_chassis_part],
                )
            )
        for turret_index in range(vehicle_turret_count):
            components.append(
                _component(
                    f"setpiece_child_vehicle_{slot_id}_turret_{turret_index:02d}_region",
                    "turret",
                    vehicle_turret_part,
                    (x, height * 0.38, z - local_l * 0.10),
                    (local_w * 0.42, local_h * 0.40, local_w * 0.42),
                    tags=["setpiece", "child_module", "vehicle", "turret", archetype, layout, *child_slot_tags("vehicle", index, f"turret_{turret_index}")],
                    adjacency=[vehicle_chassis_part],
                    axis="y",
                    radius=local_w * 0.20,
                    height=local_h * 0.42,
                )
            )

    for index in range(boat_count):
        slot = child_slot_entry("boat", index)
        if slot:
            x, z = child_slot(index, max(1, boat_count), radius_x=0.34, radius_z=0.34, kind="boat")
        else:
            x = -width * 0.34 + width * 0.68 * (index / max(1, boat_count - 1)) if boat_count > 1 else 0.0
            z = depth * (0.56 + 0.03 * (index % 2))
        slot_id = child_slot_id("boat", index)
        boat_pontoon_count = child_module_count("boat", index, "pontoon_count", "pontoons", "float_count", default=0, maximum=4)
        boat_sail_count = child_module_count("boat", index, "sail_count", "sails", default=0, maximum=4)
        boat_cargo_count = child_module_count("boat", index, "cargo_hold_count", "cargo_holds", "cargo_count", default=0, maximum=4)
        local_w = width * 0.16
        local_l = depth * 0.22
        local_h = height * 0.16
        components.extend(
            [
                _component(
                    f"setpiece_child_boat_{slot_id}_hull_region",
                    "hull",
                    boat_hull_part,
                    (x, height * 0.12, z),
                    (local_w, local_h, local_l),
                    tags=["setpiece", "child_module", "boat", "hull", archetype, layout, *child_slot_tags("boat", index, "moored")],
                    adjacency=[dock_part, base_part, socket_part],
                ),
                _component(
                    f"setpiece_child_boat_{slot_id}_deck_region",
                    "deck",
                    boat_deck_part,
                    (x, height * 0.22, z),
                    (local_w * 0.78, local_h * 0.32, local_l * 0.72),
                    tags=["setpiece", "child_module", "boat", "deck", archetype, layout, *child_slot_tags("boat", index, "deck")],
                    adjacency=[boat_hull_part, dock_part],
                ),
            ]
        )
        for pontoon_index in range(boat_pontoon_count):
            side = "left" if pontoon_index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            row = pontoon_index // 2
            components.append(
                _component(
                    f"setpiece_child_boat_{slot_id}_{side}_pontoon_{row:02d}_region",
                    "pontoon",
                    boat_pontoon_part,
                    (x + sign * local_w * 0.56, height * 0.10, z + (row - 0.25) * local_l * 0.28),
                    (local_w * 0.20, local_h * 0.46, local_l * 0.72),
                    tags=["setpiece", "child_module", "boat", "pontoon", side, archetype, layout, *child_slot_tags("boat", index, f"pontoon_{pontoon_index}")],
                    adjacency=[boat_hull_part, dock_part],
                    axis="z",
                    radius=local_w * 0.10,
                    height=local_l * 0.72,
                )
            )
        for sail_index in range(boat_sail_count):
            sail_x = x + (sail_index - max(0, boat_sail_count - 1) / 2.0) * local_w * 0.28
            components.append(
                _component(
                    f"setpiece_child_boat_{slot_id}_sail_{sail_index:02d}_region",
                    "sail",
                    boat_sail_part,
                    (sail_x, height * 0.34, z),
                    (local_w * 0.36, local_h * 1.40, local_l * 0.08),
                    tags=["setpiece", "child_module", "boat", "sail", archetype, layout, *child_slot_tags("boat", index, f"sail_{sail_index}")],
                    adjacency=[boat_deck_part],
                )
            )
        for cargo_index in range(boat_cargo_count):
            components.append(
                _component(
                    f"setpiece_child_boat_{slot_id}_cargo_hold_{cargo_index:02d}_region",
                    "cargo_hold",
                    boat_cargo_part,
                    (x, height * 0.20, z + (-0.22 + 0.22 * cargo_index) * local_l),
                    (local_w * 0.54, local_h * 0.46, local_l * 0.28),
                    tags=["setpiece", "child_module", "boat", "cargo_hold", archetype, layout, *child_slot_tags("boat", index, f"cargo_hold_{cargo_index}")],
                    adjacency=[boat_deck_part],
                )
            )

    for index in range(machine_count):
        x, z = child_slot(index, max(1, machine_count), radius_x=0.22, radius_z=0.22, kind="machine")
        slot_id = child_slot_id("machine", index)
        hydraulic_count = child_module_count("machine", index, "hydraulic_count", "piston_count", "pistons", default=0, maximum=6)
        crane_count = child_module_count("machine", index, "crane_boom_count", "crane_count", "boom_count", default=0, maximum=3)
        local_w = width * 0.14
        local_d = depth * 0.12
        local_h = height * 0.22
        components.append(
            _component(
                f"setpiece_child_machine_{slot_id}_base_region",
                "machine_base",
                machine_base_part,
                (x, height * 0.18, z),
                (local_w, local_h, local_d),
                tags=["setpiece", "child_module", "machine", archetype, layout, *child_slot_tags("machine", index, "machine_pad")],
                adjacency=[base_part, utility_part, socket_part],
            )
        )
        for piston_index in range(hydraulic_count):
            side = "left" if piston_index % 2 == 0 else "right"
            sign = -1.0 if side == "left" else 1.0
            components.append(
                _component(
                    f"setpiece_child_machine_{slot_id}_{side}_hydraulic_{piston_index:02d}_region",
                    "hydraulic_piston",
                    machine_hydraulic_part,
                    (
                        x + sign * local_w * 0.44,
                        height * (0.23 + 0.03 * (piston_index // 2)),
                        z - local_d * 0.10,
                    ),
                    (local_w * 0.12, local_h * 0.80, local_w * 0.12),
                    tags=["setpiece", "child_module", "machine", "hydraulic", side, archetype, layout, *child_slot_tags("machine", index, f"piston_{piston_index}")],
                    adjacency=[machine_base_part],
                    axis="y",
                    radius=local_w * 0.05,
                    height=local_h * 0.80,
                )
            )
        for crane_index in range(crane_count):
            components.append(
                _component(
                    f"setpiece_child_machine_{slot_id}_crane_boom_{crane_index:02d}_region",
                    "crane_boom",
                    machine_crane_part,
                    (x + local_w * 0.18, height * 0.40, z + local_d * (0.20 + 0.12 * crane_index)),
                    (local_w * 0.22, local_h * 0.18, local_d * 1.35),
                    tags=["setpiece", "child_module", "machine", "crane", "boom", archetype, layout, *child_slot_tags("machine", index, f"crane_{crane_index}")],
                    adjacency=[machine_base_part, utility_part],
                )
            )
    for index in range(conveyor_count):
        machine_slot_index = index % max(1, machine_count)
        machine_slot = child_slot_entry("machine", machine_slot_index)
        if machine_slot:
            x, z = child_slot(machine_slot_index, max(1, machine_count), radius_x=0.22, radius_z=0.22, kind="machine")
            x += width * 0.08 * (-1.0 if index % 2 else 1.0)
            z -= depth * 0.08
        else:
            x = -width * 0.28 + width * 0.56 * (index / max(1, conveyor_count - 1)) if conveyor_count > 1 else 0.0
            z = -depth * (0.20 + 0.03 * (index % 2))
        components.append(
            _component(
                f"setpiece_child_conveyor_{index:02d}_region",
                "conveyor",
                machine_conveyor_part,
                (x, height * 0.18, z),
                (width * 0.26, height * 0.13, depth * 0.075),
                tags=["setpiece", "child_module", "machine", "conveyor", archetype, layout, *child_slot_tags("machine", machine_slot_index, f"conveyor_{index}")],
                adjacency=[machine_base_part, utility_part, road_part],
            )
        )

    for index in range(interior_count):
        x, z = child_slot(index, max(1, interior_count), radius_x=0.18, radius_z=0.18, kind="interior")
        slot_id = child_slot_id("interior", index)
        ceiling_light_count = child_module_count("interior", index, "ceiling_light_count", "light_count", default=0, maximum=4)
        alcove_count = child_module_count("interior", index, "alcove_count", "alcoves", default=0, maximum=4)
        components.extend(
            [
                _component(
                    f"setpiece_child_interior_{slot_id}_room_region",
                    "room_cell",
                    interior_part,
                    (x, height * 0.22, z),
                    (width * 0.18, height * 0.32, depth * 0.16),
                    tags=["setpiece", "child_module", "interior", "room", archetype, layout, *child_slot_tags("interior", index, "room_cell")],
                    adjacency=[building_part, courtyard_part, socket_part],
                ),
                _component(
                    f"setpiece_child_interior_{slot_id}_partition_region",
                    "partition",
                    interior_part,
                    (x, height * 0.25, z + depth * 0.055),
                    (width * 0.14, height * 0.24, depth * 0.025),
                    tags=["setpiece", "child_module", "interior", "partition", archetype, layout, *child_slot_tags("interior", index, "partition")],
                    adjacency=[interior_part],
                ),
            ]
        )
        for light_index in range(ceiling_light_count):
            components.append(
                _component(
                    f"setpiece_child_interior_{slot_id}_ceiling_light_{light_index:02d}_region",
                    "ceiling_light",
                    interior_light_part,
                    (
                        x + (light_index - max(0, ceiling_light_count - 1) / 2.0) * width * 0.045,
                        height * 0.39,
                        z,
                    ),
                    (width * 0.055, height * 0.035, depth * 0.035),
                    tags=["setpiece", "child_module", "interior", "ceiling_light", archetype, layout, *child_slot_tags("interior", index, f"light_{light_index}")],
                    adjacency=[interior_part],
                )
            )
        for alcove_index in range(alcove_count):
            side = -1.0 if alcove_index % 2 == 0 else 1.0
            components.append(
                _component(
                    f"setpiece_child_interior_{slot_id}_alcove_{alcove_index:02d}_region",
                    "alcove",
                    interior_alcove_part,
                    (x + side * width * 0.095, height * 0.22, z + depth * 0.035 * (alcove_index // 2)),
                    (width * 0.055, height * 0.22, depth * 0.055),
                    tags=["setpiece", "child_module", "interior", "alcove", archetype, layout, *child_slot_tags("interior", index, f"alcove_{alcove_index}")],
                    adjacency=[interior_part],
                )
            )

    for index in range(furniture_count):
        slot = child_slot_entry("furniture", index)
        if slot:
            x, z = child_slot(index, max(1, furniture_count), radius_x=0.28, radius_z=0.22, kind="furniture")
        else:
            x = float(rng.uniform(-0.28, 0.28)) * width
            z = float(rng.uniform(-0.22, 0.22)) * depth
        slot_id = child_slot_id("furniture", index)
        module_chair_count = child_module_count("furniture", index, "chair_count", "chairs", "seat_count", default=0, maximum=6)
        shelf_count = child_module_count("furniture", index, "shelf_count", "shelves", default=0, maximum=3)
        lamp_count = child_module_count("furniture", index, "lamp_count", "lamps", default=0, maximum=3)
        components.extend(
            [
                _component(
                    f"setpiece_child_furniture_{slot_id}_base_region",
                    "furniture_base",
                    furniture_part,
                    (x, height * 0.12, z),
                    (width * 0.10, height * 0.10, depth * 0.075),
                    tags=["setpiece", "child_module", "furniture", archetype, layout, *child_slot_tags("furniture", index, "furniture_anchor")],
                    adjacency=[courtyard_part, prop_part, socket_part],
                ),
                _component(
                    f"setpiece_child_furniture_{slot_id}_surface_region",
                    "table_top",
                    furniture_part,
                    (x, height * 0.20, z),
                    (width * 0.12, height * 0.05, depth * 0.09),
                    tags=["setpiece", "child_module", "furniture", "surface", archetype, layout, *child_slot_tags("furniture", index, "surface")],
                    adjacency=[furniture_part],
                ),
            ]
        )
        for chair_index in range(module_chair_count):
            angle = (chair_index / max(1, module_chair_count)) * np.pi * 2.0
            chair_x = x + float(np.cos(angle)) * width * 0.075
            chair_z = z + float(np.sin(angle)) * depth * 0.055
            components.extend(
                [
                    _component(
                        f"setpiece_child_furniture_{slot_id}_chair_{chair_index:02d}_seat_region",
                        "chair_seat",
                        furniture_seat_part,
                        (chair_x, height * 0.135, chair_z),
                        (width * 0.045, height * 0.045, depth * 0.040),
                        tags=["setpiece", "child_module", "furniture", "chair", "seat", archetype, layout, *child_slot_tags("furniture", index, f"chair_{chair_index}")],
                        adjacency=[furniture_part],
                    ),
                    _component(
                        f"setpiece_child_furniture_{slot_id}_chair_{chair_index:02d}_back_region",
                        "chair_back",
                        furniture_seat_part,
                        (chair_x, height * 0.18, chair_z - depth * 0.018),
                        (width * 0.045, height * 0.075, depth * 0.015),
                        tags=["setpiece", "child_module", "furniture", "chair", "back", archetype, layout, *child_slot_tags("furniture", index, f"chair_{chair_index}_back")],
                        adjacency=[furniture_seat_part],
                    ),
                ]
            )
        for shelf_index in range(shelf_count):
            components.append(
                _component(
                    f"setpiece_child_furniture_{slot_id}_shelf_{shelf_index:02d}_region",
                    "shelf_unit",
                    furniture_shelf_part,
                    (x - width * 0.08 + shelf_index * width * 0.06, height * 0.20, z + depth * 0.08),
                    (width * 0.055, height * 0.16, depth * 0.035),
                    tags=["setpiece", "child_module", "furniture", "shelf", archetype, layout, *child_slot_tags("furniture", index, f"shelf_{shelf_index}")],
                    adjacency=[furniture_part],
                )
            )
        for lamp_index in range(lamp_count):
            components.append(
                _component(
                    f"setpiece_child_furniture_{slot_id}_lamp_{lamp_index:02d}_region",
                    "lamp",
                    furniture_lamp_part,
                    (x + width * 0.06 * (lamp_index + 1), height * 0.25, z - depth * 0.05),
                    (width * 0.030, height * 0.15, width * 0.030),
                    tags=["setpiece", "child_module", "furniture", "lamp", archetype, layout, *child_slot_tags("furniture", index, f"lamp_{lamp_index}")],
                    adjacency=[furniture_part],
                    axis="y",
                    radius=width * 0.014,
                    height=height * 0.15,
                )
            )

    for index in range(foliage_count):
        x, z = child_slot(index, max(1, foliage_count), radius_x=0.40, radius_z=0.34, kind="foliage")
        slot_id = child_slot_id("foliage", index)
        bush_count = child_module_count("foliage", index, "bush_count", "bushes", default=0, maximum=5)
        grass_count = child_module_count("foliage", index, "grass_count", "grass_clump_count", default=0, maximum=8)
        rock_count = child_module_count("foliage", index, "rock_count", "rocks", default=0, maximum=6)
        flower_count = child_module_count("foliage", index, "flower_count", "flowers", default=0, maximum=8)
        components.extend(
            [
                _component(
                    f"setpiece_child_foliage_{slot_id}_ground_region",
                    "foliage_ground",
                    foliage_part,
                    (x, height * 0.08, z),
                    (width * 0.13, height * 0.045, depth * 0.11),
                    tags=["setpiece", "child_module", "foliage", "ground", archetype, layout, *child_slot_tags("foliage", index, "terrain_anchor")],
                    adjacency=[terrain_part, socket_part],
                ),
                _component(
                    f"setpiece_child_foliage_{slot_id}_trunk_region",
                    "tree_trunk",
                    foliage_part,
                    (x, height * 0.24, z),
                    (width * 0.035, height * 0.30, width * 0.035),
                    tags=["setpiece", "child_module", "foliage", "tree", archetype, layout, *child_slot_tags("foliage", index, "tree")],
                    adjacency=[foliage_part],
                    radius=width * 0.018,
                    height=height * 0.30,
                ),
                _component(
                    f"setpiece_child_foliage_{slot_id}_canopy_region",
                    "leaf_cluster",
                    foliage_part,
                    (x, height * 0.42, z),
                    (width * 0.10, height * 0.16, width * 0.10),
                    tags=["setpiece", "child_module", "foliage", "canopy", archetype, layout, *child_slot_tags("foliage", index, "canopy")],
                    adjacency=[foliage_part],
                ),
            ]
        )
        for bush_index in range(bush_count):
            angle = (bush_index / max(1, bush_count)) * np.pi * 2.0
            components.append(
                _component(
                    f"setpiece_child_foliage_{slot_id}_bush_{bush_index:02d}_region",
                    "bush",
                    foliage_bush_part,
                    (
                        x + float(np.cos(angle)) * width * 0.060,
                        height * 0.16,
                        z + float(np.sin(angle)) * depth * 0.045,
                    ),
                    (width * 0.060, height * 0.11, width * 0.060),
                    tags=["setpiece", "child_module", "foliage", "bush", archetype, layout, *child_slot_tags("foliage", index, f"bush_{bush_index}")],
                    adjacency=[foliage_part],
                    radius=width * 0.030,
                    height=height * 0.11,
                )
            )
        for grass_index in range(grass_count):
            offset_x = (-0.06 + 0.04 * (grass_index % 4)) * width
            offset_z = (-0.04 + 0.035 * (grass_index // 4)) * depth
            components.append(
                _component(
                    f"setpiece_child_foliage_{slot_id}_grass_{grass_index:02d}_region",
                    "grass_clump",
                    foliage_grass_part,
                    (x + offset_x, height * 0.11, z + offset_z),
                    (width * 0.035, height * 0.065, width * 0.035),
                    tags=["setpiece", "child_module", "foliage", "grass", archetype, layout, *child_slot_tags("foliage", index, f"grass_{grass_index}")],
                    adjacency=[foliage_part],
                )
            )
        for rock_index in range(rock_count):
            components.append(
                _component(
                    f"setpiece_child_foliage_{slot_id}_rock_{rock_index:02d}_region",
                    "natural_rock",
                    foliage_rock_part,
                    (x + (-0.06 + 0.06 * (rock_index % 3)) * width, height * 0.11, z + depth * 0.05),
                    (width * 0.040, height * 0.070, width * 0.045),
                    tags=["setpiece", "child_module", "foliage", "rock", archetype, layout, *child_slot_tags("foliage", index, f"rock_{rock_index}")],
                    adjacency=[foliage_part],
                )
            )
        for flower_index in range(flower_count):
            components.append(
                _component(
                    f"setpiece_child_foliage_{slot_id}_flower_{flower_index:02d}_region",
                    "flower",
                    foliage_flower_part,
                    (x + (-0.05 + 0.025 * (flower_index % 5)) * width, height * 0.13, z - depth * 0.05),
                    (width * 0.018, height * 0.080, width * 0.018),
                    tags=["setpiece", "child_module", "foliage", "flower", archetype, layout, *child_slot_tags("foliage", index, f"flower_{flower_index}")],
                    adjacency=[foliage_part],
                    axis="y",
                    radius=width * 0.008,
                    height=height * 0.08,
                )
            )

    socket_slots = child_module_slots[:child_socket_count] if child_module_slots else []
    socket_entries: list[dict[str, Any] | None] = [*socket_slots, *([None] * max(0, child_socket_count - len(socket_slots)))]
    for index, slot in enumerate(socket_entries):
        if slot:
            position = slot.get("normalized_position")
            x, z = (
                (float(position[0]) * width, float(position[2]) * depth)
                if isinstance(position, list | tuple) and len(position) >= 3
                else child_slot(index, max(1, child_socket_count), radius_x=0.44, radius_z=0.38)
            )
            socket_id = str(slot.get("id") or f"socket_{index:02d}")
            socket_module = slot.get("module") if isinstance(slot.get("module"), dict) else {}
            socket_tags = [
                f"slot_{socket_id}",
                f"module_slot_{socket_id}",
                f"socket_{slot.get('socket')}",
                f"anchor_{slot.get('anchor')}",
                str(slot.get("kind") or "generic"),
                str(slot.get("mount") or "module_mount"),
                f"module_instance_{tag_token(socket_module.get('instance_id'))}" if socket_module else "",
                f"module_template_{tag_token(socket_module.get('template'))}" if socket_module else "",
                f"module_family_{tag_token(socket_module.get('family'))}" if socket_module else "",
                "socket_addressed",
            ]
        else:
            x, z = child_slot(index, max(1, child_socket_count), radius_x=0.44, radius_z=0.38)
            socket_id = f"socket_{index:02d}"
            socket_tags = [f"child_socket_{index}"]
        components.append(
            _component(
                f"setpiece_child_socket_{socket_id}_region",
                "socket_plate",
                socket_part,
                (x, height * 0.095, z),
                (width * 0.08, height * 0.025, depth * 0.055),
                tags=["setpiece", "child_module", "socket", "attachment", archetype, layout, *socket_tags],
                adjacency=[base_part, road_part, access_part, utility_part],
                interface_role="socket",
            )
        )

    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=[
            "procedural setpiece blueprint generated multi-system archetypes with terrain pads, structures, route spines, access spans, utilities, perimeter elements, props, docks, aprons, ritual/courtyard features, nested child modules, and socket markers"
        ],
    )
