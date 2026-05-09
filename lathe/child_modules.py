"""Child-module slot planning for procedural assemblies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SETPIECE_CHILD_MODULE_KINDS = (
    "building",
    "road",
    "terrain",
    "infrastructure",
    "vehicle",
    "boat",
    "machine",
    "interior",
    "furniture",
    "foliage",
)

_COUNT_KEYS: dict[str, tuple[str, ...]] = {
    "building": ("building_slot_count", "building_count", "buildings", "structure_count"),
    "road": ("road_slot_count", "road_count", "roads", "route_count", "routes"),
    "terrain": ("terrain_slot_count", "terrain_patch_count", "terrain_count", "landform_count"),
    "infrastructure": ("infrastructure_slot_count", "infrastructure_count", "utility_count", "service_count"),
    "vehicle": ("vehicle_slot_count", "vehicle_count", "vehicles"),
    "boat": ("boat_slot_count", "boat_count", "boats"),
    "machine": ("machine_slot_count", "machine_count", "machines"),
    "interior": ("interior_slot_count", "interior_module_count", "interior_count", "room_count"),
    "furniture": ("furniture_slot_count", "furniture_cluster_count", "furniture_count"),
    "foliage": ("foliage_slot_count", "foliage_cluster_count", "foliage_count"),
}

_SUPPORTS: dict[str, tuple[str, ...]] = {
    "building": ("procedural_building", "building", "structure", "tower", "facade"),
    "road": ("procedural_road", "road", "route", "street", "path"),
    "terrain": ("procedural_terrain", "terrain", "landform", "ground", "hill"),
    "infrastructure": ("procedural_infrastructure", "infrastructure", "utility", "pipe", "power", "service"),
    "vehicle": ("procedural_vehicle", "vehicle", "rover", "drone", "car", "truck"),
    "boat": ("procedural_boat", "boat", "ship", "watercraft", "barge"),
    "machine": ("procedural_machine", "machine", "conveyor", "crane", "assembler"),
    "interior": ("procedural_interior", "room", "interior", "corridor", "chamber"),
    "furniture": ("procedural_furniture", "furniture", "table", "chair", "counter", "fixture"),
    "foliage": ("procedural_foliage", "foliage", "tree", "plant", "rock", "garden"),
    "generic": ("module", "kit_part", "prop", "attachment"),
}

_MOUNT_KIND: dict[str, str] = {
    "building": "building_pad",
    "road": "road_coupler",
    "terrain": "terrain_anchor",
    "infrastructure": "utility_junction",
    "vehicle": "parking_bay",
    "boat": "mooring",
    "machine": "machine_pad",
    "interior": "room_entry",
    "furniture": "furniture_anchor",
    "foliage": "terrain_anchor",
    "generic": "module_mount",
}

_CLEARANCE: dict[str, float] = {
    "building": 0.20,
    "road": 0.06,
    "terrain": 0.04,
    "infrastructure": 0.14,
    "vehicle": 0.18,
    "boat": 0.22,
    "machine": 0.16,
    "interior": 0.14,
    "furniture": 0.08,
    "foliage": 0.10,
    "generic": 0.12,
}

_FAMILY_BY_KIND: dict[str, str] = {
    "building": "procedural_building",
    "road": "procedural_road",
    "terrain": "procedural_terrain",
    "infrastructure": "procedural_infrastructure",
    "vehicle": "procedural_vehicle",
    "boat": "procedural_boat",
    "machine": "procedural_machine",
    "interior": "procedural_interior",
    "furniture": "procedural_furniture",
    "foliage": "procedural_foliage",
    "generic": "procedural_urban_prop",
}

_MODULE_LIBRARY: dict[str, tuple[dict[str, Any], ...]] = {
    "building": (
        {
            "template": "workshop_block",
            "family": "procedural_building",
            "archetype": "workshop",
            "controls": {"building_type": "workshop", "floor_count": 2, "facade_bay_count": 3},
            "components": ("building_body", "roof", "entry_door"),
            "tags": ("workshop", "building", "industrial"),
        },
        {
            "template": "watchtower",
            "family": "procedural_building",
            "archetype": "tower",
            "controls": {"building_type": "tower", "floor_count": 3, "tower_count": 1},
            "components": ("tower_body", "roof", "balcony"),
            "tags": ("watchtower", "building", "vertical"),
        },
    ),
    "road": (
        {
            "template": "service_lane",
            "family": "procedural_road",
            "archetype": "lane",
            "controls": {"road_type": "service_lane", "lane_count": 1, "road_segment_count": 1},
            "components": ("road_deck", "road_edge", "marker"),
            "tags": ("road", "service_lane", "route"),
        },
        {
            "template": "street_spine",
            "family": "procedural_road",
            "archetype": "street",
            "controls": {"road_type": "street", "lane_count": 2, "road_segment_count": 2},
            "components": ("road_deck", "curb", "crosswalk"),
            "tags": ("road", "street", "urban"),
        },
    ),
    "terrain": (
        {
            "template": "raised_ground_patch",
            "family": "procedural_terrain",
            "archetype": "ground_patch",
            "controls": {"terrain_type": "ground_patch", "terrain_patch_count": 1, "rock_count": 2},
            "components": ("terrain_patch", "rock", "ground_detail"),
            "tags": ("terrain", "ground", "landform"),
        },
        {
            "template": "rocky_mound",
            "family": "procedural_terrain",
            "archetype": "mound",
            "controls": {"terrain_type": "mound", "terrain_patch_count": 1, "rock_count": 4},
            "components": ("terrain_patch", "natural_rock", "slope"),
            "tags": ("terrain", "mound", "rocky"),
        },
    ),
    "infrastructure": (
        {
            "template": "utility_node",
            "family": "procedural_infrastructure",
            "archetype": "utility",
            "controls": {"infrastructure_type": "utility_node", "pipe_count": 2, "junction_count": 1},
            "components": ("junction_box", "pipe_run", "service_rail"),
            "tags": ("infrastructure", "utility", "service"),
        },
        {
            "template": "power_node",
            "family": "procedural_infrastructure",
            "archetype": "power",
            "controls": {"infrastructure_type": "power", "transformer_count": 1, "cable_count": 2},
            "components": ("transformer_box", "cable_span", "support_bracket"),
            "tags": ("infrastructure", "power", "utility"),
        },
    ),
    "vehicle": (
        {
            "template": "utility_rover",
            "family": "procedural_vehicle",
            "archetype": "rover",
            "controls": {"vehicle_type": "rover", "drive_type": "wheeled", "wheel_count": 4, "cargo_module_count": 1},
            "components": ("chassis", "cabin", "wheel", "cargo_module"),
            "tags": ("utility", "rover", "wheeled"),
        },
        {
            "template": "cargo_tug",
            "family": "procedural_vehicle",
            "archetype": "tug",
            "controls": {"vehicle_type": "truck", "drive_type": "wheeled", "wheel_count": 6, "cargo_module_count": 2},
            "components": ("chassis", "cabin", "wheel", "cargo_module"),
            "tags": ("cargo", "tug", "wheeled"),
        },
        {
            "template": "patrol_drone",
            "family": "procedural_vehicle",
            "archetype": "drone",
            "controls": {"vehicle_type": "drone", "drive_type": "rotor", "rotor_count": 4, "wheel_count": 0},
            "components": ("chassis", "cabin", "rotor_pod"),
            "tags": ("patrol", "drone", "rotor"),
        },
    ),
    "boat": (
        {
            "template": "work_skiff",
            "family": "procedural_boat",
            "archetype": "skiff",
            "controls": {"boat_type": "skiff", "propulsion": "engine", "engine_count": 1, "rail_count": 1},
            "components": ("hull", "deck", "engine"),
            "tags": ("workboat", "skiff", "engine"),
        },
        {
            "template": "cargo_barge",
            "family": "procedural_boat",
            "archetype": "barge",
            "controls": {"boat_type": "barge", "cargo_hold_count": 2, "rail_count": 2},
            "components": ("hull", "deck", "cargo_hold"),
            "tags": ("cargo", "barge", "harbor"),
        },
        {
            "template": "pontoon_ferry",
            "family": "procedural_boat",
            "archetype": "pontoon",
            "controls": {"boat_type": "pontoon", "pontoon_count": 2, "rail_count": 2},
            "components": ("hull", "deck", "pontoon"),
            "tags": ("ferry", "pontoon", "float"),
        },
    ),
    "machine": (
        {
            "template": "assembler_station",
            "family": "procedural_machine",
            "archetype": "assembler",
            "controls": {"machine_type": "assembler", "arm_count": 1, "hydraulic_count": 2, "conveyor_count": 1},
            "components": ("machine_base", "hydraulic_piston", "conveyor"),
            "tags": ("assembler", "factory", "hydraulic"),
        },
        {
            "template": "gantry_crane",
            "family": "procedural_machine",
            "archetype": "crane",
            "controls": {"machine_type": "crane", "crane_boom_count": 1, "hydraulic_count": 2},
            "components": ("machine_base", "crane_boom", "hydraulic_piston"),
            "tags": ("crane", "gantry", "yard"),
        },
        {
            "template": "conveyor_loader",
            "family": "procedural_machine",
            "archetype": "loader",
            "controls": {"machine_type": "loader", "conveyor_count": 2, "gear_count": 2},
            "components": ("machine_base", "conveyor", "gear"),
            "tags": ("loader", "conveyor", "factory"),
        },
    ),
    "interior": (
        {
            "template": "control_room_pod",
            "family": "procedural_interior",
            "archetype": "control_room",
            "controls": {"room_layout": "control_room", "ceiling_light_count": 2, "partition_count": 2},
            "components": ("room_cell", "partition", "ceiling_light"),
            "tags": ("control_room", "interior", "room"),
        },
        {
            "template": "barracks_room",
            "family": "procedural_interior",
            "archetype": "barracks",
            "controls": {"room_layout": "barracks", "alcove_count": 2, "partition_count": 1},
            "components": ("room_cell", "partition", "alcove"),
            "tags": ("barracks", "interior", "room"),
        },
    ),
    "furniture": (
        {
            "template": "market_table_set",
            "family": "procedural_furniture",
            "archetype": "market_table",
            "controls": {"furniture_type": "market", "table_count": 1, "chair_count": 2},
            "components": ("furniture_base", "table_top", "chair_seat", "chair_back"),
            "tags": ("market", "table_set", "furniture"),
        },
        {
            "template": "workstation_cluster",
            "family": "procedural_furniture",
            "archetype": "workstation",
            "controls": {"furniture_type": "workshop", "table_count": 1, "shelf_count": 1, "lamp_count": 1},
            "components": ("furniture_base", "table_top", "shelf_unit", "lamp"),
            "tags": ("workstation", "workshop", "furniture"),
        },
    ),
    "foliage": (
        {
            "template": "tree_cluster",
            "family": "procedural_foliage",
            "archetype": "tree_cluster",
            "controls": {"foliage_type": "tree", "tree_count": 1, "bush_count": 2, "grass_count": 3},
            "components": ("foliage_ground", "tree_trunk", "leaf_cluster", "bush", "grass_clump"),
            "tags": ("tree_cluster", "greenery", "foliage"),
        },
        {
            "template": "rock_garden",
            "family": "procedural_foliage",
            "archetype": "rock_garden",
            "controls": {"foliage_type": "garden", "rock_count": 3, "flower_count": 2},
            "components": ("foliage_ground", "natural_rock", "flower"),
            "tags": ("rock_garden", "landscape", "foliage"),
        },
    ),
    "generic": (
        {
            "template": "kit_attachment",
            "family": "procedural_urban_prop",
            "archetype": "attachment",
            "controls": {"urban_prop_type": "kit_attachment", "street_crate_count": 1},
            "components": ("socket_plate", "street_crate"),
            "tags": ("generic", "attachment", "kit"),
        },
    ),
}

_ARCHETYPE_TEMPLATE_HINTS: dict[str, dict[str, str]] = {
    "outpost": {"building": "watchtower", "vehicle": "utility_rover", "interior": "barracks_room"},
    "market": {"building": "workshop_block", "road": "street_spine", "furniture": "market_table_set", "foliage": "tree_cluster"},
    "factory": {"building": "workshop_block", "infrastructure": "utility_node", "machine": "assembler_station", "interior": "control_room_pod"},
    "harbor": {"road": "service_lane", "boat": "work_skiff", "machine": "gantry_crane"},
    "hangar": {"building": "workshop_block", "vehicle": "cargo_tug", "machine": "conveyor_loader"},
    "temple": {"building": "watchtower", "interior": "control_room_pod", "furniture": "market_table_set", "foliage": "rock_garden"},
}


def child_module_layout_from_authoring(
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None,
    connections: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Derive socket-addressable child-module slots from high-level controls."""
    controls = dict(shape_controls or {})
    if family != "procedural_setpiece":
        return {
            "shape_controls": controls,
            "slots": [],
            "connections": [],
            "sockets": [],
            "anchors": [],
            "summary": _summary([], connections),
        }

    slots: list[dict[str, Any]] = []
    for kind in SETPIECE_CHILD_MODULE_KINDS:
        count = _count(controls, *_COUNT_KEYS[kind], default=0, minimum=0, maximum=24)
        for index in range(count):
            slots.append(_slot(kind, index, count, controls=controls))

    authored_socket_count = _count(
        controls,
        "child_socket_count",
        "module_socket_count",
        "socket_slot_count",
        default=max(1, len(slots)),
        minimum=0,
        maximum=32,
    )
    generic_count = max(0, authored_socket_count - len(slots))
    for index in range(generic_count):
        slots.append(_slot("generic", index, max(1, generic_count), controls=controls))

    sockets = [str(slot["socket"]) for slot in slots]
    anchors = [str(slot["anchor"]) for slot in slots]
    module_slots = [str(slot["id"]) for slot in slots]
    module_kinds = [str(slot["kind"]) for slot in slots]
    module_instances = [str(slot["module"]["instance_id"]) for slot in slots if isinstance(slot.get("module"), dict)]
    module_templates = [str(slot["module"]["template"]) for slot in slots if isinstance(slot.get("module"), dict)]
    module_families = [str(slot["module"]["family"]) for slot in slots if isinstance(slot.get("module"), dict)]
    controls["child_module_count"] = len([slot for slot in slots if slot["kind"] != "generic"])
    controls["module_slot_count"] = len(slots)
    controls["child_socket_count"] = len(slots)
    controls["module_socket_count"] = len(slots)
    if module_slots:
        controls["child_module_slots"] = module_slots
        controls["child_module_slot_kinds"] = module_kinds
        controls["module_sockets"] = sockets
        controls["module_anchors"] = anchors
    if module_instances:
        controls["child_module_instances"] = module_instances
        controls["child_module_templates"] = module_templates
        controls["child_module_families"] = module_families
    for kind in SETPIECE_CHILD_MODULE_KINDS:
        kind_slots = [str(slot["id"]) for slot in slots if slot["kind"] == kind]
        kind_instances = [
            str(slot["module"]["instance_id"])
            for slot in slots
            if slot["kind"] == kind and isinstance(slot.get("module"), dict)
        ]
        kind_templates = [
            str(slot["module"]["template"])
            for slot in slots
            if slot["kind"] == kind and isinstance(slot.get("module"), dict)
        ]
        controls[f"{kind}_slot_count"] = len(kind_slots)
        if kind_slots:
            controls[f"{kind}_slots"] = kind_slots
        if kind_instances:
            controls[f"{kind}_module_instances"] = kind_instances
            controls[f"{kind}_module_templates"] = kind_templates

    generated_connections = [_connection_for_slot(slot) for slot in slots]
    return {
        "shape_controls": controls,
        "slots": slots,
        "instances": [dict(slot["module"]) for slot in slots if isinstance(slot.get("module"), dict)],
        "connections": generated_connections,
        "sockets": sockets,
        "anchors": anchors,
        "summary": _summary(slots, connections),
    }


def _count(
    controls: Mapping[str, Any],
    *keys: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    for key in keys:
        if key not in controls:
            continue
        value = controls.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return min(maximum, max(minimum, 1 if value else minimum))
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return min(maximum, max(minimum, len(value)))
        try:
            return min(maximum, max(minimum, int(round(float(value)))))
        except (TypeError, ValueError):
            continue
    return min(maximum, max(minimum, default))


def _slot(kind: str, index: int, count: int, *, controls: Mapping[str, Any]) -> dict[str, Any]:
    slot_id = f"{kind}_{index:02d}"
    position = _authored_slot_position(kind, index, slot_id, controls) or _position(kind, index, count)
    facing_degrees = _authored_slot_facing(kind, index, slot_id, controls, default=_facing_degrees(kind, position))
    clearance = _authored_slot_clearance(kind, index, slot_id, controls, default=_CLEARANCE.get(kind, _CLEARANCE["generic"]))
    module = _module_instance(kind, index, slot_id, controls)
    return {
        "id": slot_id,
        "kind": kind,
        "socket": f"module_socket_{slot_id}",
        "anchor": f"{kind}_mount_{index:02d}",
        "mount": _MOUNT_KIND.get(kind, _MOUNT_KIND["generic"]),
        "supports": list(_SUPPORTS.get(kind, _SUPPORTS["generic"])),
        "clearance": clearance,
        "priority": index,
        "normalized_position": position,
        "facing_degrees": facing_degrees,
        "snap_grid": "setpiece_child_module_grid",
        "module": module,
        "tags": _dedupe(
            [
                "child_module",
                "module_slot",
                kind,
                _MOUNT_KIND.get(kind, "module_mount"),
                str(module.get("template") or ""),
                str(module.get("archetype") or ""),
            ]
        ),
    }


def _connection_for_slot(slot: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(slot.get("kind") or "generic")
    return {
        "id": f"{slot['socket']}_to_{slot['anchor']}",
        "source": slot["socket"],
        "target": slot["anchor"],
        "relation": "attached_to",
        "socket_type": kind,
        "compat_kind": kind,
        "clearance": slot.get("clearance", _CLEARANCE["generic"]),
        "snap_grid": slot.get("snap_grid", "setpiece_child_module_grid"),
        "priority": slot.get("priority", 0),
        "metadata": {
            "slot_id": slot["id"],
            "slot_kind": kind,
            "mount": slot.get("mount", "module_mount"),
            "module_instance_id": slot.get("module", {}).get("instance_id")
            if isinstance(slot.get("module"), Mapping)
            else "",
            "module_template": slot.get("module", {}).get("template") if isinstance(slot.get("module"), Mapping) else "",
            "module_family": slot.get("module", {}).get("family") if isinstance(slot.get("module"), Mapping) else "",
            "supports": list(slot.get("supports") or []),
            "normalized_position": list(slot.get("normalized_position") or [0.0, 0.0, 0.0]),
            "facing_degrees": slot.get("facing_degrees", 0.0),
        },
    }


def _authored_slot_position(
    kind: str,
    index: int,
    slot_id: str,
    controls: Mapping[str, Any],
) -> list[float] | None:
    for key in _slot_control_keys(kind, index, slot_id, "position"):
        position = _vector3_control(controls.get(key))
        if position is not None:
            return position
    for mapping_key in ("slot_positions", "module_positions", "child_module_positions"):
        mapping = controls.get(mapping_key)
        if not isinstance(mapping, Mapping):
            continue
        for candidate in _slot_candidates(kind, index, slot_id):
            position = _vector3_control(mapping.get(candidate))
            if position is not None:
                return position
    return None


def _authored_slot_facing(
    kind: str,
    index: int,
    slot_id: str,
    controls: Mapping[str, Any],
    *,
    default: float,
) -> float:
    for key in (*_slot_control_keys(kind, index, slot_id, "facing_degrees"), *_slot_control_keys(kind, index, slot_id, "facing")):
        value = _float_control(controls.get(key))
        if value is not None:
            return round(value, 6)
    for mapping_key in ("slot_facing", "slot_facings", "module_facing", "child_module_facing"):
        mapping = controls.get(mapping_key)
        if not isinstance(mapping, Mapping):
            continue
        for candidate in _slot_candidates(kind, index, slot_id):
            value = _float_control(mapping.get(candidate))
            if value is not None:
                return round(value, 6)
    return default


def _authored_slot_clearance(
    kind: str,
    index: int,
    slot_id: str,
    controls: Mapping[str, Any],
    *,
    default: float,
) -> float:
    for key in _slot_control_keys(kind, index, slot_id, "clearance"):
        value = _float_control(controls.get(key))
        if value is not None:
            return round(max(0.0, value), 6)
    for mapping_key in ("slot_clearances", "module_clearances", "child_module_clearances"):
        mapping = controls.get(mapping_key)
        if not isinstance(mapping, Mapping):
            continue
        for candidate in _slot_candidates(kind, index, slot_id):
            value = _float_control(mapping.get(candidate))
            if value is not None:
                return round(max(0.0, value), 6)
    return default


def _slot_control_keys(kind: str, index: int, slot_id: str, field: str) -> tuple[str, ...]:
    return (
        f"{slot_id}_{field}",
        f"{kind}_{index}_{field}",
        f"{kind}_slot_{index:02d}_{field}",
        f"{kind}_slot_{index}_{field}",
        f"{kind}_{field}",
    )


def _vector3_control(value: Any) -> list[float] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and len(value) >= 3:
        try:
            return [round(float(value[0]), 6), round(float(value[1]), 6), round(float(value[2]), 6)]
        except (TypeError, ValueError):
            return None
    return None


def _float_control(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _module_instance(kind: str, index: int, slot_id: str, controls: Mapping[str, Any]) -> dict[str, Any]:
    template = _template_for_slot(kind, index, controls)
    module = dict(template)
    template_id = str(module.get("template") or f"{kind}_module")
    family = str(module.get("family") or _FAMILY_BY_KIND.get(kind, "procedural_urban_prop"))
    module_controls = dict(module.get("controls") or {})
    module_controls.update(_authored_module_control_overrides(kind, index, controls))
    return {
        "instance_id": f"{slot_id}_{template_id}",
        "slot_id": slot_id,
        "kind": kind,
        "template": template_id,
        "family": family,
        "archetype": str(module.get("archetype") or template_id),
        "blueprint_id": _blueprint_for_family(family),
        "controls": module_controls,
        "components": [str(item) for item in module.get("components", [])],
        "tags": _dedupe([kind, template_id, *[str(item) for item in module.get("tags", [])]]),
    }


def _template_for_slot(kind: str, index: int, controls: Mapping[str, Any]) -> dict[str, Any]:
    template_id = _authored_template_id(kind, index, controls)
    if not template_id:
        archetype = _token(controls.get("object_archetype") or controls.get("archetype") or controls.get("setpiece"))
        template_id = _ARCHETYPE_TEMPLATE_HINTS.get(archetype, {}).get(kind, "")
    library = _MODULE_LIBRARY.get(kind) or _MODULE_LIBRARY["generic"]
    if template_id:
        for template in library:
            if _token(template.get("template")) == _token(template_id) or _token(template.get("archetype")) == _token(template_id):
                return dict(template)
        return _custom_template(kind, template_id)
    return dict(library[index % len(library)])


def _authored_template_id(kind: str, index: int, controls: Mapping[str, Any]) -> str:
    slot_id = f"{kind}_{index:02d}"
    mapped = _mapped_template_id(kind, index, slot_id, controls)
    if mapped:
        return mapped
    indexed_keys = (
        f"{kind}_{index:02d}_module",
        f"{kind}_{index}_module",
        f"{kind}_slot_{index:02d}_module",
        f"{kind}_slot_{index}_module",
    )
    for key in indexed_keys:
        value = controls.get(key)
        if value:
            return _token(value)
    list_keys = (f"{kind}_modules", f"{kind}_module_templates", f"{kind}_templates")
    for key in list_keys:
        values = _string_sequence(controls.get(key))
        if values and index < len(values):
            return _token(values[index])
    for key in (f"{kind}_module", f"{kind}_template", f"{kind}_archetype", "child_module_template"):
        value = controls.get(key)
        if value:
            return _token(value)
    return ""


def _authored_module_control_overrides(kind: str, index: int, controls: Mapping[str, Any]) -> dict[str, Any]:
    slot_id = f"{kind}_{index:02d}"
    prefix_candidates = (
        f"{slot_id}_module_",
        f"{kind}_{index}_module_",
        f"{kind}_slot_{index:02d}_module_",
        f"{kind}_slot_{index}_module_",
        f"{kind}_module_",
    )
    out: dict[str, Any] = {}
    for key, value in controls.items():
        for prefix in prefix_candidates:
            if isinstance(key, str) and key.startswith(prefix):
                target_key = key.removeprefix(prefix)
                if target_key and target_key not in {"template", "archetype"} and isinstance(
                    value, str | int | float | bool
                ):
                    out[target_key] = value
    _merge_mapped_module_controls(out, kind=kind, index=index, slot_id=slot_id, controls=controls)
    return out


def _mapped_template_id(kind: str, index: int, slot_id: str, controls: Mapping[str, Any]) -> str:
    for key in ("child_modules", "module_overrides", "slot_modules", "module_templates"):
        mapping = controls.get(key)
        if not isinstance(mapping, Mapping):
            continue
        for candidate in _slot_candidates(kind, index, slot_id):
            if candidate not in mapping:
                continue
            template = _template_from_value(mapping[candidate])
            if template:
                return template
    return ""


def _merge_mapped_module_controls(
    out: dict[str, Any],
    *,
    kind: str,
    index: int,
    slot_id: str,
    controls: Mapping[str, Any],
) -> None:
    candidates = _slot_candidates(kind, index, slot_id)
    for key in ("child_module_controls", "module_controls", "slot_controls"):
        mapping = controls.get(key)
        if not isinstance(mapping, Mapping):
            continue
        for candidate in candidates:
            payload = mapping.get(candidate)
            if isinstance(payload, Mapping):
                for raw_field, value in payload.items():
                    field = _token(raw_field)
                    if field and field not in {"module", "template", "archetype"} and isinstance(
                        value, str | int | float | bool
                    ):
                        out[field] = value
        for raw_key, value in mapping.items():
            if not isinstance(raw_key, str) or not isinstance(value, str | int | float | bool):
                continue
            key_text = _token(raw_key)
            for candidate in candidates:
                prefix = f"{candidate}_"
                if key_text.startswith(prefix):
                    field = key_text.removeprefix(prefix)
                    if field and field not in {"module", "template", "archetype"}:
                        out[field] = value
                    break


def _slot_candidates(kind: str, index: int, slot_id: str) -> tuple[str, ...]:
    return (
        slot_id,
        f"{kind}_{index}",
        f"{kind}_slot_{index:02d}",
        f"{kind}_slot_{index}",
        kind,
    )


def _template_from_value(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("module", "template", "archetype"):
            item = value.get(key)
            if item:
                return _token(item)
        return ""
    return _token(value) if value else ""


def _custom_template(kind: str, template_id: str) -> dict[str, Any]:
    family = _FAMILY_BY_KIND.get(kind, "procedural_urban_prop")
    return {
        "template": template_id,
        "family": family,
        "archetype": template_id,
        "controls": {f"{kind}_type": template_id},
        "components": (),
        "tags": ("authored", template_id),
    }


def _blueprint_for_family(family: str) -> str:
    return {
        "procedural_vehicle": "lathe.blueprint.procedural_vehicle_v1",
        "procedural_boat": "lathe.blueprint.procedural_boat_v1",
        "procedural_machine": "lathe.blueprint.procedural_machine_v1",
        "procedural_interior": "lathe.blueprint.procedural_interior_v1",
        "procedural_furniture": "lathe.blueprint.procedural_furniture_v1",
        "procedural_foliage": "lathe.blueprint.procedural_foliage_v1",
        "procedural_urban_prop": "lathe.blueprint.procedural_urban_prop_v1",
    }.get(family, "lathe.blueprint.procedural_urban_prop_v1")


def _position(kind: str, index: int, count: int) -> list[float]:
    if kind == "vehicle":
        return _linear(index, count, -0.32, 0.32, -0.31, wiggle=0.05)
    if kind == "boat":
        return _linear(index, count, -0.34, 0.34, 0.54, wiggle=0.03)
    if kind == "machine":
        return _linear(index, count, -0.26, 0.26, -0.14, wiggle=-0.04)
    if kind == "interior":
        return _linear(index, count, -0.18, 0.18, 0.02, wiggle=0.035)
    if kind == "furniture":
        return _grid(index, count, -0.22, 0.22, -0.02, 0.24)
    if kind == "foliage":
        return _radial(index, count, 0.40, 0.34, angle_offset=0.10)
    return _radial(index, count, 0.44, 0.38, angle_offset=0.18)


def _linear(index: int, count: int, start: float, end: float, z: float, *, wiggle: float = 0.0) -> list[float]:
    x = (start + end) / 2.0 if count <= 1 else start + (end - start) * (index / max(1, count - 1))
    lane_z = z + (wiggle if index % 2 else 0.0)
    return [round(x, 6), 0.0, round(lane_z, 6)]


def _grid(index: int, count: int, x0: float, x1: float, z0: float, z1: float) -> list[float]:
    columns = 1 if count <= 1 else min(3, max(2, count))
    rows = max(1, (count + columns - 1) // columns)
    column = index % columns
    row = index // columns
    x = (x0 + x1) / 2.0 if columns <= 1 else x0 + (x1 - x0) * (column / max(1, columns - 1))
    z = (z0 + z1) / 2.0 if rows <= 1 else z0 + (z1 - z0) * (row / max(1, rows - 1))
    return [round(x, 6), 0.0, round(z, 6)]


def _radial(index: int, count: int, radius_x: float, radius_z: float, *, angle_offset: float) -> list[float]:
    if count <= 1:
        return [round(radius_x * 0.45, 6), 0.0, round(-radius_z * 0.45, 6)]
    import math

    angle = (index / count) * math.pi * 2.0 + math.pi * angle_offset
    return [round(math.cos(angle) * radius_x, 6), 0.0, round(math.sin(angle) * radius_z, 6)]


def _facing_degrees(kind: str, position: Sequence[float]) -> float:
    if kind == "boat":
        return 180.0
    if kind == "vehicle":
        return 0.0
    if kind == "machine":
        return 90.0
    if len(position) >= 3:
        import math

        angle = math.degrees(math.atan2(float(position[0]), float(position[2]) or 0.000001))
        return round(angle, 6)
    return 0.0


def _string_sequence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_token(item) for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [_token(item) for item in value if item is not None and str(item).strip()]
    return [_token(value)]


def _token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _summary(slots: Sequence[Mapping[str, Any]], connections: Sequence[Any] | None) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_template: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for slot in slots:
        kind = str(slot.get("kind") or "generic")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        module = slot.get("module")
        if isinstance(module, Mapping):
            template = str(module.get("template") or "")
            family = str(module.get("family") or "")
            if template:
                by_template[template] = by_template.get(template, 0) + 1
            if family:
                by_family[family] = by_family.get(family, 0) + 1
    return {
        "slot_count": len(slots),
        "module_slot_count": len(slots),
        "child_module_count": len([slot for slot in slots if slot.get("kind") != "generic"]),
        "socket_count": len(slots),
        "anchor_count": len(slots),
        "connection_count": len(slots),
        "authored_connection_count": len(connections or []),
        "kinds": dict(sorted(by_kind.items())),
        "templates": dict(sorted(by_template.items())),
        "families": dict(sorted(by_family.items())),
        "slot_ids": [str(slot.get("id")) for slot in slots],
        "instance_ids": [
            str(slot.get("module", {}).get("instance_id"))
            for slot in slots
            if isinstance(slot.get("module"), Mapping)
        ],
    }


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
