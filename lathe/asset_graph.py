"""Asset-graph construction for the shape stage.

Turns the resolved intent into the component/join graph consumed by
the assembly kernel and scaffold compiler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from lathe.child_modules import child_module_layout_from_authoring
from lathe.connection_layout import connection_layout_from_authoring
from lathe.creative_grammar import creative_grammar_from_asset
from lathe.interface_connections import coerce_interface_connection
from lathe.interface_entries import interface_entry_id
from lathe.nested_assets import nested_assets_from_child_layout
from lathe.object_grammar import object_grammar_from_asset


def _token_set(value: str | None) -> set[str]:
    if not value:
        return set()
    lowered = value.lower().replace("-", "_").replace(" ", "_")
    return {token for token in lowered.split("_") if token}


def _interface_ids(entries: list[Any], *, prefix: str) -> list[str]:
    return [interface_entry_id(item, f"{prefix}_{idx}") for idx, item in enumerate(entries)]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _dedupe_connection_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for value in values:
        key = (
            str(value.get("id") or ""),
            str(value.get("source") or ""),
            str(value.get("target") or ""),
            str(value.get("relation") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def infer_asset_family(asset: dict[str, Any]) -> str:
    """Infer asset family.

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    resolved_family = asset.get("assembly", {}).get("resolved_family", {})
    explicit_family = (
        resolved_family.get("values", {}).get("runtime_family")
        or resolved_family.get("values", {}).get("family_key")
        or asset.get("assembly", {}).get("runtime_family")
        or asset.get("assembly", {}).get("family_key")
        or asset.get("assembly", {}).get("family")
    )
    if explicit_family:
        return str(explicit_family)

    role = str(asset.get("intent", {}).get("role", "")).lower()
    parts = [str(item).lower() for item in asset.get("intent", {}).get("parts", [])]
    kind = str(asset.get("kind", ""))
    tokens = _token_set(role) | {token for part in parts for token in _token_set(part)}

    if {"chest", "loot"} & tokens or {"lid_panel", "front_hatch", "lock_plate"} <= set(parts):
        return "brassbound_chest"
    if (
        "drone" in tokens
        or sum(1 for part in parts if "rotor" in part or "prop" in part or "fan" in part) >= 4
    ):
        if {
            "vehicle",
            "vtol",
            "scout",
            "patrol",
            "payload",
            "hardpoint",
            "thruster",
            "stabilizer",
            "module",
            "socket",
        } & tokens:
            return "procedural_vehicle"
        return "courier_drone"
    if {
        "outpost",
        "watchpost",
        "checkpoint",
        "compound",
        "camp",
        "market",
        "marketplace",
        "bazaar",
        "fortress",
        "citadel",
        "stronghold",
        "castle",
        "factory",
        "foundry",
        "refinery",
        "harbor",
        "harbour",
        "dockyard",
        "marina",
        "shipyard",
        "hangar",
        "airfield",
        "airbase",
        "temple",
        "shrine",
        "sanctuary",
        "monastery",
    } & tokens:
        return "procedural_setpiece"
    if {"city", "block", "district", "neighborhood", "plaza"} & tokens:
        return "procedural_city_block"
    if (
        {"curb", "median", "crosswalk", "bollard", "parking", "bike", "lane", "sidewalk"} & tokens
        or {"curb", "ramp"} <= tokens
        or {"lane", "arrow"} <= tokens
        or {"stop", "line"} <= tokens
        or {"parking", "bay"} <= tokens
        or {"bike", "lane"} <= tokens
    ):
        return "procedural_road"
    if (
        {
            "access",
            "traversal",
            "catwalk",
            "walkway",
            "ladder",
            "ramp",
            "gantry",
            "elevator",
            "lift",
            "scaffold",
            "scaffolding",
            "guardrail",
            "underpass",
        }
        & tokens
        or {"maintenance", "platform"} <= tokens
        or {"maintenance", "access"} <= tokens
        or {"service", "walkway"} <= tokens
        or {"access", "platform"} <= tokens
        or {"safety", "gate"} <= tokens
        or {"elevator", "shaft"} <= tokens
        or {"tunnel", "segment"} <= tokens
    ):
        return "procedural_access"
    if (
        {
            "infrastructure",
            "waterworks",
            "pipeline",
            "sewer",
            "drainage",
            "drain",
            "hydrant",
            "transformer",
            "substation",
            "conduit",
            "manhole",
            "valve",
            "duct",
            "cable_tray",
        }
        & tokens
        or {"utility", "network"} <= tokens
        or {"service", "network"} <= tokens
        or {"service", "run"} <= tokens
        or {"junction", "box"} <= tokens
        or {"fire", "hydrant"} <= tokens
        or {"overhead", "conduit"} <= tokens
        or {"cable", "tray"} <= tokens
    ):
        return "procedural_infrastructure"
    if {"cable", "span"} <= tokens:
        return "procedural_urban_prop"
    if {"bridge", "overpass", "causeway", "viaduct", "span"} & tokens:
        return "procedural_bridge"
    if {
        "road",
        "street",
        "path",
        "lane",
        "highway",
        "sidewalk",
        "junction",
        "intersection",
        "roundabout",
        "median",
        "curb",
        "crosswalk",
        "bollard",
        "parking",
        "bike",
    } & tokens:
        return "procedural_road"
    if {
        "building",
        "house",
        "tower",
        "architecture",
        "facade",
        "balcony",
        "dormer",
        "chimney",
        "storefront",
        "shopfront",
        "arcade",
        "arch",
        "parapet",
        "fire",
        "hvac",
        "signage",
    } & tokens or {
        "floor",
        "wall",
        "roof",
        "window",
        "building_body",
        "storefront",
        "parapet",
        "arch",
    } & set(parts):
        return "procedural_building"
    if (
        {
            "urban",
            "civic",
            "set_dressing",
            "streetlight",
            "streetlamp",
            "lamp_post",
            "signage",
            "fence",
            "gate",
            "bollard",
            "barricade",
            "kiosk",
            "stall",
            "vendor",
            "trash_bin",
            "utility_pole",
            "cable_span",
        }
        & tokens
        or {"street", "prop"} <= tokens
        or {"street", "furniture"} <= tokens
        or {"street", "bench"} <= tokens
        or {"street", "sign"} <= tokens
        or {"street", "crate"} <= tokens
        or {"set", "dressing"} <= tokens
        or {"market", "stall"} <= tokens
        or {"utility", "pole"} <= tokens
        or {"lamp", "post"} <= tokens
        or {"trash", "bin"} <= tokens
    ):
        return "procedural_urban_prop"
    if {"service", "cabinet"} <= tokens:
        return "service_cabinet"
    if {
        "foliage",
        "nature",
        "natural",
        "tree",
        "forest",
        "plant",
        "planting",
        "trunk",
        "bark",
        "branch",
        "limb",
        "root",
        "canopy",
        "leaf",
        "leaves",
        "bush",
        "shrub",
        "grass",
        "reed",
        "rock",
        "stone",
        "boulder",
        "mushroom",
        "fungus",
        "log",
        "vine",
        "flower",
        "blossom",
        "petal",
        "planter",
        "pot",
    } & tokens:
        return "procedural_foliage"
    if {"terrain", "landscape", "ground", "cliff", "mesa", "ridge", "hill", "platform"} & tokens:
        return "procedural_terrain"
    if {
        "furniture",
        "furnishing",
        "chair",
        "seat",
        "table",
        "desk",
        "bed",
        "bunk",
        "shelf",
        "shelves",
        "rack",
        "cabinet",
        "locker",
        "drawer",
        "cushion",
        "pillow",
        "sofa",
        "bench",
        "counter",
        "workbench",
        "appliance",
        "fixture",
        "lamp",
    } & tokens:
        return "procedural_furniture"
    if {"room", "interior", "corridor", "hallway", "chamber", "partition", "alcove"} & tokens:
        return "procedural_interior"
    if {
        "boat",
        "ship",
        "vessel",
        "watercraft",
        "sailboat",
        "catamaran",
        "trimaran",
        "barge",
        "ferry",
        "yacht",
        "skiff",
        "workboat",
        "cutter",
        "sloop",
        "schooner",
        "ketch",
        "research",
        "rescue",
        "submarine",
        "submersible",
        "hull",
        "deck",
        "bridge",
        "mast",
        "sail",
        "pontoon",
        "outrigger",
        "rudder",
        "propeller",
        "keel",
        "cleat",
        "mooring",
        "mission",
    } & tokens:
        return "procedural_boat"
    if {
        "vehicle",
        "car",
        "truck",
        "rover",
        "aircraft",
        "interceptor",
        "plane",
        "vtol",
        "hover",
        "chassis",
        "wheel",
        "wheels",
        "cabin",
        "cockpit",
        "payload",
        "track",
        "tread",
        "turret",
        "thruster",
        "stabilizer",
        "sensor",
        "antenna",
    } & tokens:
        return "procedural_vehicle"
    if {"machine", "machinery", "factory", "conveyor", "gear", "piston", "hydraulic", "crane", "industrial", "assembler"} & tokens:
        return "procedural_machine"
    if kind == "env_module" and {"wall", "screen", "vent", "mount"} & tokens:
        return "sci_fi_wall_panel"
    if "crate" in tokens:
        return "industrial_crate"
    if {
        "weapon",
        "rifle",
        "pistol",
        "gun",
        "shotgun",
        "railgun",
        "marksman",
        "breacher",
        "sidearm",
        "plasma",
        "laser",
        "launcher",
        "spear",
        "pike",
        "axe",
        "hammer",
        "pick",
        "staff",
        "tool",
        "barrel",
        "magazine",
        "trigger",
        "muzzle",
        "compensator",
        "ammo",
        "battery",
        "power",
        "sling",
        "smart",
        "salvage",
        "ceremonial",
    } & tokens:
        return "procedural_weapon"
    if {"sword", "longsword"} & tokens:
        return "hero_sword"
    if "door" in tokens:
        return "mechanical_door"
    if {"console", "terminal"} & tokens:
        return "console_terminal"
    if {"panel", "screen", "vent"} & tokens or (kind == "env_module" and {"wall", "screen", "vent"} & tokens):
        return "sci_fi_wall_panel"
    if kind == "env_module":
        return "env_module_generic"
    if kind == "mechanical_assembly":
        return "mechanical_assembly_generic"
    return "hard_surface_prop_generic"


def infer_blueprint_id(asset: dict[str, Any]) -> str:
    """Infer blueprint id.

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    resolved_family = asset.get("assembly", {}).get("resolved_family", {})
    explicit_blueprint = resolved_family.get("values", {}).get("blueprint_id")
    if explicit_blueprint:
        return str(explicit_blueprint)
    family = infer_asset_family(asset)
    return {
        "brassbound_chest": "lathe.blueprint.hard_surface_chest_v1",
        "courier_drone": "lathe.blueprint.mechanical_quad_drone_v1",
        "sci_fi_wall_panel": "lathe.blueprint.env_wall_panel_v1",
        "industrial_crate": "lathe.blueprint.hard_surface_crate_v1",
        "hero_sword": "lathe.blueprint.hero_sword_v1",
        "mechanical_door": "lathe.blueprint.env_mechanical_door_v1",
        "console_terminal": "lathe.blueprint.hard_surface_console_terminal_v1",
        "service_cabinet": "lathe.blueprint.hard_surface_service_cabinet_v1",
        "control_pedestal": "lathe.blueprint.hard_surface_control_pedestal_v1",
        "supply_container": "lathe.blueprint.hard_surface_supply_container_v1",
        "procedural_building": "lathe.blueprint.procedural_building_v1",
        "procedural_vehicle": "lathe.blueprint.procedural_vehicle_v1",
        "procedural_weapon": "lathe.blueprint.procedural_weapon_v1",
        "procedural_boat": "lathe.blueprint.procedural_boat_v1",
        "procedural_machine": "lathe.blueprint.procedural_machine_v1",
        "procedural_furniture": "lathe.blueprint.procedural_furniture_v1",
        "procedural_foliage": "lathe.blueprint.procedural_foliage_v1",
        "procedural_infrastructure": "lathe.blueprint.procedural_infrastructure_v1",
        "procedural_access": "lathe.blueprint.procedural_access_v1",
        "procedural_urban_prop": "lathe.blueprint.procedural_urban_prop_v1",
        "procedural_setpiece": "lathe.blueprint.procedural_setpiece_v1",
        "procedural_road": "lathe.blueprint.procedural_road_v1",
        "procedural_bridge": "lathe.blueprint.procedural_bridge_v1",
        "procedural_terrain": "lathe.blueprint.procedural_terrain_v1",
        "procedural_city_block": "lathe.blueprint.procedural_city_block_v1",
        "procedural_interior": "lathe.blueprint.procedural_interior_v1",
        "env_module_generic": "lathe.blueprint.env_module_generic_v1",
        "mechanical_assembly_generic": "lathe.blueprint.mechanical_assembly_generic_v1",
        "hard_surface_prop_generic": "lathe.blueprint.hard_surface_prop_generic_v1",
    }[family]


def _default_parts_for_family(family: str) -> list[str]:
    if family == "procedural_setpiece":
        return [
            "setpiece_base",
            "terrain_patch",
            "primary_building",
            "secondary_building",
            "courtyard",
            "road_spine",
            "access_route",
            "utility_run",
            "prop_cluster",
            "perimeter_segment",
            "gatehouse",
            "watchtower",
            "dock",
            "apron",
            "ritual_axis",
            "vehicle_chassis",
            "vehicle_cabin",
            "vehicle_wheel",
            "vehicle_rotor",
            "vehicle_cargo_module",
            "vehicle_turret",
            "vehicle_payload_bay",
            "vehicle_hardpoint",
            "vehicle_module_socket",
            "vehicle_thruster",
            "vehicle_sensor",
            "boat_hull",
            "boat_deck",
            "boat_pontoon",
            "boat_sail",
            "boat_cargo_hold",
            "boat_mission_socket",
            "boat_deck_hardpoint",
            "boat_thruster",
            "boat_sensor",
            "boat_cleat",
            "machine_base",
            "machine_conveyor",
            "machine_hydraulic",
            "machine_crane",
            "interior_room",
            "interior_light",
            "interior_alcove",
            "furniture_cluster",
            "furniture_seat",
            "furniture_shelf",
            "furniture_lamp",
            "foliage_cluster",
            "foliage_bush",
            "foliage_grass",
            "foliage_rock",
            "foliage_flower",
            "module_socket",
        ]
    return []


def _part_tags(name: str) -> list[str]:
    lname = name.lower()
    tags: set[str] = set()
    for token in (
        "body",
        "shell",
        "lid",
        "hatch",
        "door",
        "hinge",
        "lock",
        "latch",
        "plate",
        "handle",
        "foot",
        "leg",
        "stand",
        "panel",
        "screen",
        "frame",
        "bezel",
        "vent",
        "grille",
        "rotor",
        "cargo",
        "sensor",
        "camera",
        "anchor",
        "socket",
        "module",
        "subassembly",
        "child",
        "nested",
        "mount",
        "console",
        "threshold",
        "blade",
        "fuller",
        "tip",
        "guard",
        "crossguard",
        "grip",
        "pommel",
        "sword",
        "weapon",
        "rifle",
        "pistol",
        "gun",
        "launcher",
        "spear",
        "axe",
        "hammer",
        "pick",
        "staff",
        "tool",
        "receiver",
        "barrel",
        "muzzle",
        "stock",
        "butt",
        "magazine",
        "ammo",
        "sight",
        "optic",
        "trigger",
        "head",
        "building",
        "floor",
        "wall",
        "roof",
        "window",
        "facade",
        "column",
        "stair",
        "stairs",
        "balcony",
        "awning",
        "cornice",
        "tower",
        "chimney",
        "dormer",
        "arch",
        "arcade",
        "storefront",
        "shopfront",
        "parapet",
        "fire_escape",
        "escape",
        "hvac",
        "equipment",
        "vehicle",
        "chassis",
        "wheel",
        "cabin",
        "crew",
        "cockpit",
        "payload",
        "bay",
        "track",
        "tread",
        "suspension",
        "axle",
        "turret",
        "wing",
        "cargo",
        "arm",
        "manipulator",
        "machine",
        "machinery",
        "gear",
        "piston",
        "hydraulic",
        "conveyor",
        "belt",
        "tank",
        "vessel",
        "crane",
        "boom",
        "boat",
        "ship",
        "watercraft",
        "hull",
        "keel",
        "deck",
        "mast",
        "sail",
        "canvas",
        "rigging",
        "cable",
        "line",
        "pontoon",
        "float",
        "outrigger",
        "rudder",
        "propeller",
        "prop",
        "hold",
        "rail",
        "cleat",
        "mooring",
        "engine",
        "hardpoint",
        "socket",
        "thruster",
        "stabilizer",
        "fin",
        "sensor",
        "antenna",
        "radar",
        "mission",
        "equipment",
        "power",
        "cell",
        "battery",
        "ammo",
        "sling",
        "compensator",
        "urban",
        "civic",
        "set_dressing",
        "base",
        "fence",
        "gate",
        "sign",
        "signage",
        "streetlight",
        "streetlamp",
        "bollard",
        "barrier",
        "barricade",
        "trash",
        "bin",
        "utility",
        "pole",
        "wire",
        "kiosk",
        "stall",
        "vendor",
        "infrastructure",
        "utility",
        "network",
        "service",
        "pipe",
        "pipeline",
        "duct",
        "drain",
        "channel",
        "hydrant",
        "transformer",
        "substation",
        "conduit",
        "manhole",
        "cover",
        "valve",
        "junction",
        "box",
        "tray",
        "access",
        "traversal",
        "catwalk",
        "walkway",
        "ladder",
        "ramp",
        "gantry",
        "elevator",
        "lift",
        "shaft",
        "platform",
        "tunnel",
        "scaffold",
        "scaffolding",
        "guardrail",
        "safety",
        "road",
        "street",
        "path",
        "lane",
        "sidewalk",
        "median",
        "curb",
        "stop",
        "arrow",
        "junction",
        "intersection",
        "branch",
        "crosswalk",
        "parking",
        "bike",
        "turnout",
        "roundabout",
        "bridge",
        "span",
        "railing",
        "pier",
        "terrain",
        "ground",
        "cliff",
        "ridge",
        "platform",
        "city",
        "block",
        "lot",
        "plaza",
        "room",
        "interior",
        "corridor",
        "partition",
        "alcove",
        "furniture",
        "furnishing",
        "chair",
        "seat",
        "table",
        "desk",
        "bed",
        "bunk",
        "shelf",
        "rack",
        "cabinet",
        "locker",
        "drawer",
        "cushion",
        "pillow",
        "sofa",
        "bench",
        "counter",
        "workbench",
        "appliance",
        "fixture",
        "lamp",
        "back",
        "upholstery",
        "ceiling",
        "light",
        "foliage",
        "nature",
        "tree",
        "plant",
        "trunk",
        "bark",
        "branch",
        "limb",
        "root",
        "canopy",
        "leaf",
        "leaves",
        "bush",
        "shrub",
        "grass",
        "reed",
        "rock",
        "stone",
        "boulder",
        "mushroom",
        "fungus",
        "log",
        "vine",
        "flower",
        "blossom",
        "petal",
        "planter",
        "pot",
        "setpiece",
        "outpost",
        "watchpost",
        "checkpoint",
        "compound",
        "market",
        "bazaar",
        "fortress",
        "citadel",
        "factory",
        "foundry",
        "harbor",
        "harbour",
        "dock",
        "dockyard",
        "hangar",
        "airfield",
        "temple",
        "shrine",
        "sanctuary",
        "courtyard",
        "perimeter",
        "warehouse",
        "apron",
    ):
        if token in lname:
            tags.add(token)
    if lname.endswith("_l") or "_l" in lname or lname.endswith(" left"):
        tags.add("left")
    if lname.endswith("_r") or "_r" in lname or lname.endswith(" right"):
        tags.add("right")
    if lname.endswith("_fl") or "_fl" in lname:
        tags.update({"front", "left"})
    if lname.endswith("_fr") or "_fr" in lname:
        tags.update({"front", "right"})
    if lname.endswith("_rl") or "_rl" in lname:
        tags.update({"rear", "left"})
    if lname.endswith("_rr") or "_rr" in lname:
        tags.update({"rear", "right"})
    if "top" in lname:
        tags.add("top")
    if "bottom" in lname:
        tags.add("bottom")
    return sorted(tags)


def _symmetry_mate(name: str, part_names: set[str]) -> str | None:
    candidates = [
        (name.replace("_l", "_r"), "_l"),
        (name.replace("_r", "_l"), "_r"),
        (name.replace("_fl", "_fr"), "_fl"),
        (name.replace("_fr", "_fl"), "_fr"),
        (name.replace("_rl", "_rr"), "_rl"),
        (name.replace("_rr", "_rl"), "_rr"),
    ]
    for candidate, token in candidates:
        if token in name and candidate in part_names:
            return candidate
    return None


def _assembly_role(tags: list[str]) -> str | None:
    ordered_roles = [
        "body",
        "shell",
        "panel",
        "frame",
        "lid",
        "door",
        "hinge",
        "lock",
        "latch",
        "handle",
        "foot",
        "stand",
        "leg",
        "vent",
        "grille",
        "screen",
        "bezel",
        "rotor",
        "anchor",
        "socket",
        "module",
        "subassembly",
        "child",
        "nested",
        "threshold",
        "blade",
        "fuller",
        "tip",
        "guard",
        "grip",
        "pommel",
        "receiver",
        "barrel",
        "muzzle",
        "stock",
        "magazine",
        "sight",
        "trigger",
        "head",
        "building",
        "floor",
        "wall",
        "roof",
        "window",
        "column",
        "stair",
        "arch",
        "parapet",
        "storefront",
        "fire_escape",
        "equipment",
        "vehicle",
        "chassis",
        "wheel",
        "cabin",
        "crew",
        "cockpit",
        "payload",
        "bay",
        "track",
        "suspension",
        "turret",
        "wing",
        "cargo",
        "arm",
        "machine",
        "gear",
        "piston",
        "conveyor",
        "tank",
        "crane",
        "boat",
        "hull",
        "keel",
        "deck",
        "mast",
        "sail",
        "rigging",
        "cable",
        "pontoon",
        "float",
        "outrigger",
        "rudder",
        "propeller",
        "prop",
        "hold",
        "rail",
        "cleat",
        "mooring",
        "engine",
        "hardpoint",
        "socket",
        "thruster",
        "stabilizer",
        "fin",
        "sensor",
        "antenna",
        "radar",
        "mission",
        "equipment",
        "power",
        "cell",
        "battery",
        "ammo",
        "sling",
        "compensator",
        "urban",
        "fence",
        "gate",
        "sign",
        "signage",
        "streetlight",
        "streetlamp",
        "bollard",
        "barrier",
        "barricade",
        "trash",
        "bin",
        "utility",
        "pole",
        "wire",
        "kiosk",
        "stall",
        "vendor",
        "infrastructure",
        "utility",
        "network",
        "service",
        "pipe",
        "pipeline",
        "duct",
        "drain",
        "channel",
        "hydrant",
        "transformer",
        "substation",
        "conduit",
        "manhole",
        "cover",
        "valve",
        "junction",
        "box",
        "tray",
        "access",
        "traversal",
        "catwalk",
        "walkway",
        "ladder",
        "ramp",
        "gantry",
        "elevator",
        "lift",
        "shaft",
        "platform",
        "tunnel",
        "scaffold",
        "scaffolding",
        "guardrail",
        "safety",
        "road",
        "street",
        "path",
        "lane",
        "sidewalk",
        "median",
        "curb",
        "stop",
        "arrow",
        "junction",
        "intersection",
        "crosswalk",
        "parking",
        "bike",
        "bridge",
        "span",
        "railing",
        "pier",
        "terrain",
        "ground",
        "cliff",
        "ridge",
        "platform",
        "city",
        "block",
        "lot",
        "plaza",
        "room",
        "interior",
        "corridor",
        "partition",
        "alcove",
        "furniture",
        "chair",
        "seat",
        "table",
        "desk",
        "bed",
        "shelf",
        "rack",
        "cabinet",
        "drawer",
        "cushion",
        "counter",
        "workbench",
        "appliance",
        "lamp",
        "back",
        "light",
        "foliage",
        "tree",
        "plant",
        "trunk",
        "branch",
        "root",
        "canopy",
        "leaf",
        "bush",
        "grass",
        "rock",
        "stone",
        "mushroom",
        "log",
        "vine",
        "flower",
        "planter",
        "setpiece",
        "outpost",
        "market",
        "fortress",
        "factory",
        "harbor",
        "dock",
        "hangar",
        "temple",
        "courtyard",
        "perimeter",
        "warehouse",
        "apron",
    ]
    for role in ordered_roles:
        if role in tags:
            return role
    return None


def _infer_part_graph(parts: list[PartNode]) -> list[dict[str, str]]:
    part_names = {part.name for part in parts}
    edges: set[tuple[str, str]] = set()

    def connect(left: str, right: str) -> None:
        if left not in part_names or right not in part_names or left == right:
            return
        edges.add(tuple(sorted((left, right))))

    body_name = next(
        (part.name for part in parts if part.assembly_role in {"body", "shell"}),
        parts[0].name if parts else None,
    )
    for part in parts:
        if body_name and part.name != body_name:
            connect(body_name, part.name)

    tag_pairs = [
        ("lid", "lock"),
        ("door", "lock"),
        ("door", "handle"),
        ("screen", "frame"),
        ("screen", "bezel"),
        ("panel", "frame"),
        ("vent", "panel"),
        ("rotor", "body"),
        ("foot", "body"),
        ("stand", "body"),
        ("leg", "body"),
        ("anchor", "body"),
        ("socket", "body"),
        ("threshold", "door"),
        ("blade", "guard"),
        ("blade", "fuller"),
        ("blade", "tip"),
        ("guard", "grip"),
        ("grip", "pommel"),
        ("receiver", "barrel"),
        ("receiver", "stock"),
        ("receiver", "magazine"),
        ("receiver", "trigger"),
        ("receiver", "sight"),
        ("barrel", "muzzle"),
        ("barrel", "compensator"),
        ("weapon", "hardpoint"),
        ("weapon", "socket"),
        ("weapon", "rail"),
        ("weapon", "ammo"),
        ("weapon", "battery"),
        ("weapon", "power"),
        ("weapon", "sling"),
        ("weapon", "sensor"),
        ("grip", "trigger"),
        ("handle", "head"),
        ("floor", "wall"),
        ("wall", "roof"),
        ("wall", "window"),
        ("wall", "arch"),
        ("wall", "storefront"),
        ("roof", "parapet"),
        ("roof", "hvac"),
        ("roof", "equipment"),
        ("building", "signage"),
        ("building", "fire_escape"),
        ("building", "escape"),
        ("door", "floor"),
        ("chassis", "wheel"),
        ("chassis", "cabin"),
        ("chassis", "track"),
        ("chassis", "suspension"),
        ("chassis", "turret"),
        ("chassis", "cargo"),
        ("chassis", "wing"),
        ("chassis", "arm"),
        ("chassis", "crew"),
        ("chassis", "cockpit"),
        ("chassis", "payload"),
        ("chassis", "bay"),
        ("chassis", "hardpoint"),
        ("chassis", "socket"),
        ("chassis", "thruster"),
        ("chassis", "stabilizer"),
        ("chassis", "sensor"),
        ("chassis", "antenna"),
        ("machine", "arm"),
        ("machine", "gear"),
        ("machine", "piston"),
        ("machine", "conveyor"),
        ("machine", "tank"),
        ("machine", "crane"),
        ("hull", "deck"),
        ("deck", "mast"),
        ("mast", "sail"),
        ("mast", "rigging"),
        ("hull", "pontoon"),
        ("hull", "outrigger"),
        ("hull", "rudder"),
        ("deck", "cargo"),
        ("deck", "railing"),
        ("deck", "hardpoint"),
        ("deck", "socket"),
        ("deck", "cleat"),
        ("deck", "crew"),
        ("hull", "thruster"),
        ("hull", "stabilizer"),
        ("cabin", "sensor"),
        ("cabin", "antenna"),
        ("hull", "anchor"),
        ("hull", "engine"),
        ("engine", "propeller"),
        ("engine", "prop"),
        ("urban", "fence"),
        ("urban", "gate"),
        ("urban", "sign"),
        ("urban", "streetlight"),
        ("urban", "bench"),
        ("urban", "bin"),
        ("urban", "pole"),
        ("pole", "wire"),
        ("pole", "cable"),
        ("urban", "kiosk"),
        ("urban", "stall"),
        ("urban", "barrier"),
        ("urban", "bollard"),
        ("urban", "crate"),
        ("gate", "fence"),
        ("stall", "sign"),
        ("kiosk", "sign"),
        ("infrastructure", "pipe"),
        ("infrastructure", "duct"),
        ("infrastructure", "conduit"),
        ("infrastructure", "drain"),
        ("infrastructure", "hydrant"),
        ("infrastructure", "transformer"),
        ("infrastructure", "junction"),
        ("infrastructure", "valve"),
        ("infrastructure", "manhole"),
        ("infrastructure", "rail"),
        ("infrastructure", "support"),
        ("infrastructure", "tray"),
        ("pipe", "valve"),
        ("pipe", "hydrant"),
        ("pipe", "junction"),
        ("conduit", "junction"),
        ("conduit", "transformer"),
        ("conduit", "tray"),
        ("drain", "manhole"),
        ("access", "catwalk"),
        ("access", "walkway"),
        ("access", "ladder"),
        ("access", "ramp"),
        ("access", "gantry"),
        ("access", "elevator"),
        ("access", "platform"),
        ("access", "tunnel"),
        ("access", "scaffold"),
        ("catwalk", "guardrail"),
        ("walkway", "guardrail"),
        ("platform", "guardrail"),
        ("platform", "ladder"),
        ("platform", "ramp"),
        ("gantry", "support"),
        ("scaffold", "platform"),
        ("elevator", "shaft"),
        ("safety", "gate"),
        ("road", "sidewalk"),
        ("road", "lane"),
        ("road", "median"),
        ("road", "curb"),
        ("road", "junction"),
        ("road", "intersection"),
        ("road", "crosswalk"),
        ("road", "parking"),
        ("road", "bike"),
        ("lane", "arrow"),
        ("lane", "stop"),
        ("bridge", "railing"),
        ("bridge", "pier"),
        ("terrain", "cliff"),
        ("terrain", "platform"),
        ("block", "lot"),
        ("block", "road"),
        ("setpiece", "terrain"),
        ("setpiece", "building"),
        ("setpiece", "road"),
        ("setpiece", "access"),
        ("setpiece", "infrastructure"),
        ("setpiece", "urban"),
        ("outpost", "tower"),
        ("outpost", "gate"),
        ("market", "stall"),
        ("market", "kiosk"),
        ("fortress", "tower"),
        ("fortress", "gate"),
        ("factory", "machine"),
        ("factory", "conveyor"),
        ("harbor", "dock"),
        ("harbor", "deck"),
        ("hangar", "apron"),
        ("hangar", "road"),
        ("temple", "column"),
        ("temple", "courtyard"),
        ("room", "wall"),
        ("room", "door"),
        ("interior", "floor"),
        ("furniture", "chair"),
        ("furniture", "table"),
        ("furniture", "bed"),
        ("furniture", "shelf"),
        ("furniture", "cabinet"),
        ("furniture", "counter"),
        ("furniture", "appliance"),
        ("chair", "seat"),
        ("chair", "back"),
        ("chair", "leg"),
        ("table", "leg"),
        ("bed", "cushion"),
        ("cabinet", "drawer"),
        ("counter", "cabinet"),
        ("lamp", "light"),
        ("tree", "trunk"),
        ("trunk", "branch"),
        ("trunk", "root"),
        ("branch", "leaf"),
        ("branch", "canopy"),
        ("foliage", "tree"),
        ("foliage", "bush"),
        ("foliage", "grass"),
        ("foliage", "rock"),
        ("foliage", "mushroom"),
        ("foliage", "log"),
        ("foliage", "vine"),
        ("foliage", "flower"),
        ("planter", "plant"),
    ]
    for left_tag, right_tag in tag_pairs:
        left_parts = [part.name for part in parts if left_tag in part.tags]
        right_parts = [part.name for part in parts if right_tag in part.tags]
        for left_name in left_parts:
            for right_name in right_parts:
                connect(left_name, right_name)

    return [{"from": left, "to": right} for left, right in sorted(edges)]


@dataclass
class PartNode:
    """PartNode."""

    name: str
    tags: list[str] = field(default_factory=list)
    symmetry_mate: str | None = None
    articulation: str | None = None
    interface_role: str | None = None
    assembly_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class AssetGraph:
    """AssetGraph."""

    name: str
    kind: str
    family: str
    blueprint_id: str
    role: str
    scale_cm: float
    symmetry_axis: str | None
    validation_threshold: float
    critic_name: str | None
    parts: list[PartNode]
    joints: list[str]
    sockets: list[str]
    anchors: list[str]
    connections: list[dict[str, Any]]
    connection_layout: dict[str, Any]
    materials: list[str]
    styles: list[str]
    interactions: list[str]
    part_graph: list[dict[str, str]]
    semantic_requirements: dict[str, Any]
    authoring: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        payload = asdict(self)
        payload["parts"] = [part.to_dict() for part in self.parts]
        return payload


def _scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    scale = intent.get("scale")
    if isinstance(scale, dict) and scale.get("type") == "unit":
        value = float(scale["value"])
        unit = scale["unit"]
        if unit == "mm":
            return value / 10.0
        if unit == "cm":
            return value
        if unit == "m":
            return value * 100.0
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def build_asset_graph(asset: dict[str, Any]) -> AssetGraph:
    """Build asset graph.

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    family = infer_asset_family(asset)
    blueprint_id = infer_blueprint_id(asset)
    part_names = _dedupe(
        [str(item) for item in asset.get("intent", {}).get("parts", [])]
        + _default_parts_for_family(family)
    )
    resolved_components = list(asset.get("assembly", {}).get("resolved_components", []))
    component_by_part: dict[str, dict[str, Any]] = {}
    for component in resolved_components:
        values = component.get("values", {})
        part_name = values.get("part")
        if part_name:
            component_by_part[str(part_name)] = component
    part_name_set = set(part_names)
    parts: list[PartNode] = []
    for name in part_names:
        component = component_by_part.get(name, {})
        component_values = component.get("values", {})
        component_tags = list(component_values.get("tags", []))
        component_type = component.get("geometry", {}).get("component_type") or component_values.get(
            "component_type"
        )
        tags = sorted(
            set(_part_tags(name) + component_tags + ([str(component_type)] if component_type else []))
        )
        articulation = component_values.get("articulation") or (
            "hinge" if any(tag in tags for tag in ("lid", "door", "hatch")) else None
        )
        interface_role = component_values.get("interface_role") or (
            "grip"
            if "handle" in tags
            else "support"
            if any(tag in tags for tag in ("foot", "leg", "stand"))
            else None
        )
        parts.append(
            PartNode(
                name=name,
                tags=tags,
                symmetry_mate=_symmetry_mate(name, part_name_set),
                articulation=articulation,
                interface_role=interface_role,
                assembly_role=str(component_type) if component_type else _assembly_role(tags),
            )
        )
    symmetry_axis = asset.get("build", {}).get("shape", {}).get("symmetry")
    if symmetry_axis in {"auto", None, ""}:
        symmetry_axis = "x"

    semantic_requirements = {
        "minimum_part_coverage": 0.75,
        "minimum_silhouette_fidelity": 0.72,
        "minimum_structural_richness": 0.55,
        "minimum_symmetry_score": 0.60,
        "minimum_interface_score": 0.60,
        "minimum_adjacency_score": 0.58,
        "maximum_fragmentation_penalty": 0.45,
        "minimum_detail_density": 0.58,
        "minimum_silhouette_complexity": 0.58,
        "minimum_edge_readability": 0.55,
        "minimum_attachment_integration_quality": 0.58,
        "minimum_support_plausibility": 0.52,
        "minimum_feature_coherence": 0.56,
        "minimum_geometry_integration_quality": 0.0,
        "minimum_surface_authoring_quality": 0.0,
        "maximum_primitive_likeness_penalty": 0.44,
        "maximum_assembled_primitives_penalty": 0.42,
    }
    if family == "brassbound_chest":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.85,
                "minimum_silhouette_fidelity": 0.82,
                "minimum_structural_richness": 0.68,
                "minimum_symmetry_score": 0.78,
                "minimum_interface_score": 0.70,
                "minimum_adjacency_score": 0.72,
                "maximum_fragmentation_penalty": 0.22,
                "minimum_detail_density": 0.76,
                "minimum_silhouette_complexity": 0.72,
                "minimum_edge_readability": 0.72,
                "minimum_attachment_integration_quality": 0.74,
                "minimum_support_plausibility": 0.68,
                "minimum_feature_coherence": 0.74,
                "minimum_geometry_integration_quality": 0.85,
                "minimum_surface_authoring_quality": 0.70,
                "maximum_primitive_likeness_penalty": 0.18,
                "maximum_assembled_primitives_penalty": 0.20,
            }
        )
    elif family == "courier_drone":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.90,
                "minimum_silhouette_fidelity": 0.80,
                "minimum_structural_richness": 0.72,
                "minimum_symmetry_score": 0.82,
                "minimum_interface_score": 0.68,
                "minimum_adjacency_score": 0.74,
                "maximum_fragmentation_penalty": 0.20,
                "minimum_detail_density": 0.74,
                "minimum_silhouette_complexity": 0.70,
                "minimum_edge_readability": 0.70,
                "minimum_attachment_integration_quality": 0.76,
                "minimum_support_plausibility": 0.64,
                "minimum_feature_coherence": 0.72,
                "minimum_geometry_integration_quality": 0.85,
                "minimum_surface_authoring_quality": 0.70,
                "maximum_primitive_likeness_penalty": 0.18,
                "maximum_assembled_primitives_penalty": 0.18,
            }
        )
    elif family == "sci_fi_wall_panel":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.80,
                "minimum_silhouette_fidelity": 0.76,
                "minimum_structural_richness": 0.62,
                "minimum_symmetry_score": 0.55,
                "minimum_interface_score": 0.64,
                "minimum_adjacency_score": 0.66,
                "maximum_fragmentation_penalty": 0.26,
                "minimum_detail_density": 0.68,
                "minimum_silhouette_complexity": 0.70,
                "minimum_edge_readability": 0.66,
                "minimum_attachment_integration_quality": 0.68,
                "minimum_support_plausibility": 0.58,
                "minimum_feature_coherence": 0.68,
                "maximum_primitive_likeness_penalty": 0.24,
                "maximum_assembled_primitives_penalty": 0.26,
            }
        )
    elif family in {
        "industrial_crate",
        "hero_sword",
        "mechanical_door",
        "console_terminal",
        "service_cabinet",
        "control_pedestal",
        "supply_container",
        "procedural_building",
        "procedural_vehicle",
        "procedural_weapon",
        "procedural_boat",
        "procedural_machine",
        "procedural_furniture",
        "procedural_foliage",
        "procedural_infrastructure",
        "procedural_access",
        "procedural_urban_prop",
        "procedural_setpiece",
        "procedural_road",
        "procedural_bridge",
        "procedural_terrain",
        "procedural_city_block",
        "procedural_interior",
    }:
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.84,
                "minimum_silhouette_fidelity": 0.78,
                "minimum_structural_richness": 0.66,
                "minimum_symmetry_score": 0.62,
                "minimum_interface_score": 0.64,
                "minimum_adjacency_score": 0.68,
                "maximum_fragmentation_penalty": 0.24,
                "minimum_detail_density": 0.70,
                "minimum_silhouette_complexity": 0.68,
                "minimum_edge_readability": 0.66,
                "minimum_attachment_integration_quality": 0.70,
                "minimum_support_plausibility": 0.60,
                "minimum_feature_coherence": 0.68,
                "minimum_geometry_integration_quality": 0.80
                if family
                in {
                    "console_terminal",
                    "control_pedestal",
                    "procedural_building",
                    "procedural_vehicle",
                    "procedural_weapon",
                    "procedural_boat",
                    "procedural_machine",
                    "procedural_furniture",
                    "procedural_foliage",
                    "procedural_infrastructure",
                    "procedural_access",
                    "procedural_urban_prop",
                    "procedural_setpiece",
                    "procedural_road",
                    "procedural_bridge",
                    "procedural_terrain",
                    "procedural_city_block",
                    "procedural_interior",
                }
                else 0.78,
                "minimum_surface_authoring_quality": 0.72
                if family in {"console_terminal", "mechanical_door", "control_pedestal"}
                else 0.70,
                "maximum_primitive_likeness_penalty": 0.22,
                "maximum_assembled_primitives_penalty": 0.24,
            }
        )
        if family in {
            "procedural_building",
            "procedural_vehicle",
            "procedural_weapon",
            "procedural_boat",
            "procedural_machine",
            "procedural_furniture",
            "procedural_foliage",
            "procedural_infrastructure",
            "procedural_access",
            "procedural_urban_prop",
            "procedural_setpiece",
            "procedural_road",
            "procedural_bridge",
            "procedural_terrain",
            "procedural_city_block",
            "procedural_interior",
        }:
            semantic_requirements.update(
                {
                    "minimum_structural_richness": 0.72,
                    "minimum_detail_density": 0.72,
                    "minimum_adjacency_score": 0.72,
                    "minimum_feature_coherence": 0.72,
                }
            )
        if family == "service_cabinet":
            semantic_requirements.update(
                {
                    "minimum_symmetry_score": 0.50,
                    "minimum_adjacency_score": 0.66,
                }
            )
        if family == "control_pedestal":
            semantic_requirements.update(
                {
                    "minimum_silhouette_fidelity": 0.75,
                }
            )
        if family == "hero_sword":
            semantic_requirements.update(
                {
                    "minimum_part_coverage": 0.90,
                    "minimum_silhouette_fidelity": 0.80,
                    "minimum_symmetry_score": 0.70,
                    "minimum_interface_score": 0.66,
                    "minimum_detail_density": 0.62,
                    "minimum_silhouette_complexity": 0.62,
                    "minimum_feature_coherence": 0.66,
                    "maximum_primitive_likeness_penalty": 0.24,
                    "maximum_assembled_primitives_penalty": 0.26,
                }
            )

    space_spec = asset.get("space", {})
    objectives = list(space_spec.get("objectives", []))
    search_best_of = int(space_spec.get("select", {}).get("best_of", 0) or 0)
    feature_density = str(asset.get("features", {}).get("density", "") or "")
    semantic_requirements["language_feature_density"] = feature_density
    semantic_requirements["language_search_best_of"] = search_best_of

    interfaces = asset.get("build", {}).get("interfaces", {})
    sockets = _interface_ids(interfaces.get("sockets", []) or [], prefix="socket")
    anchor_ids = _dedupe(
        [
            *_interface_ids(interfaces.get("anchors", []) or [], prefix="anchor"),
            *_interface_ids(interfaces.get("pivots", []) or [], prefix="pivot"),
        ]
    )
    connections = [
        coerce_interface_connection(entry, f"connection_{idx}")
        for idx, entry in enumerate(interfaces.get("connections", []) or [])
    ]
    raw_shape_controls = asset.get("build", {}).get("shape", {})
    base_shape_controls = raw_shape_controls if isinstance(raw_shape_controls, dict) else {}
    creative_grammar = creative_grammar_from_asset(
        asset,
        family=family,
        shape_controls=base_shape_controls,
    )
    creative_shape_controls = dict(creative_grammar.get("shape_controls") or base_shape_controls)
    object_grammar = object_grammar_from_asset(
        asset,
        family=family,
        shape_controls=base_shape_controls,
    )
    object_shape_controls = dict(creative_shape_controls)
    object_shape_controls.update(dict(object_grammar.get("shape_controls") or {}))
    child_module_layout = child_module_layout_from_authoring(
        family=family,
        shape_controls=object_shape_controls,
        connections=connections,
    )
    child_shape_controls = dict(child_module_layout.get("shape_controls") or object_shape_controls)
    sockets = _dedupe([*sockets, *[str(item) for item in child_module_layout.get("sockets", [])]])
    anchor_ids = _dedupe([*anchor_ids, *[str(item) for item in child_module_layout.get("anchors", [])]])
    child_connections = _dedupe_connection_dicts([
        *connections,
        *[
            dict(connection)
            for connection in child_module_layout.get("connections", [])
            if isinstance(connection, dict)
        ],
    ])
    connection_layout = connection_layout_from_authoring(
        family=family,
        shape_controls=child_shape_controls,
        connections=child_connections,
        sockets=sockets,
        anchors=anchor_ids,
    )
    shape_controls = dict(connection_layout.get("shape_controls") or child_shape_controls)
    if connection_layout.get("connections"):
        connections = _dedupe_connection_dicts(
            [dict(connection) for connection in connection_layout.get("connections", [])]
        )
    nested_assets = nested_assets_from_child_layout(
        parent_asset_name=str(asset["name"]),
        parent_family=family,
        parent_kind=str(asset.get("kind") or ""),
        child_module_layout=child_module_layout,
        parent_materials=[str(item) for item in asset.get("intent", {}).get("materials", [])],
        parent_styles=[str(item) for item in asset.get("intent", {}).get("style", [])],
        parent_surface=asset.get("surface", {}) if isinstance(asset.get("surface"), dict) else {},
    )
    nested_summary = nested_assets.get("summary", {}) if isinstance(nested_assets.get("summary"), dict) else {}
    if nested_summary.get("nested_asset_count"):
        shape_controls["nested_asset_count"] = int(nested_summary.get("nested_asset_count") or 0)
        shape_controls["nested_asset_names"] = list(nested_summary.get("asset_names") or [])
        shape_controls["nested_asset_families"] = sorted(dict(nested_summary.get("families") or {}).keys())

    return AssetGraph(
        name=asset["name"],
        kind=str(asset.get("kind")),
        family=family,
        blueprint_id=blueprint_id,
        role=str(asset.get("intent", {}).get("role", "")),
        scale_cm=_scale_cm(asset),
        symmetry_axis=str(symmetry_axis) if symmetry_axis else None,
        validation_threshold=float(asset.get("validate", {}).get("threshold", 0.80)),
        critic_name=asset.get("validate", {}).get("score"),
        parts=parts,
        joints=[str(item) for item in asset.get("build", {}).get("rig", {}).get("joints", [])],
        sockets=sockets,
        anchors=anchor_ids,
        connections=connections,
        connection_layout=connection_layout,
        materials=[str(item) for item in asset.get("intent", {}).get("materials", [])],
        styles=[str(item) for item in asset.get("intent", {}).get("style", [])],
        interactions=[str(item) for item in asset.get("intent", {}).get("interactions", [])],
        part_graph=_infer_part_graph(parts),
        semantic_requirements=semantic_requirements,
        authoring={
            "family_ref": asset.get("assembly", {}).get("family", ""),
            "from_family": asset.get("from", ""),
            "kit_ref": asset.get("assembly", {}).get("kit", ""),
            "resolved_kit": asset.get("assembly", {}).get("resolved_kit", {}),
            "resolved_family": asset.get("assembly", {}).get("resolved_family", {}),
            "components": resolved_components,
            "traits": asset.get("assembly", {}).get("resolved_traits", []),
            "mechanisms": asset.get("assembly", {}).get("resolved_mechanisms", []),
            "source_surface": asset.get("surface", {}),
            "surface_program": asset.get("surface", {}).get("program", ""),
            "surface_patterns": asset.get("surface", {}).get("patterns", []),
            "build_surface": asset.get("build", {}).get("surface", {}),
            "optimize": asset.get("build", {}).get("optimize", {}),
            "physics": asset.get("build", {}).get("physics", {}),
            "package": asset.get("package", {}),
            "space": space_spec,
            "shape_controls": shape_controls,
            "connection_layout": connection_layout,
            "creative_grammar": creative_grammar,
            "object_grammar": object_grammar,
            "child_module_layout": child_module_layout,
            "nested_assets": nested_assets,
            "feature_allow": asset.get("features", {}).get("allow", []),
            "feature_density": feature_density,
            "experimental": asset.get("experimental", {}),
            "repair_policy": asset.get("repair_policy", {}),
            "fit": asset.get("fit", {}),
            "transfer": asset.get("transfer", {}),
            "reuse": asset.get("reuse", {}),
            "constraints": asset.get("constraints", {}),
            "ingest": asset.get("ingest", {}),
            "assembly_rules": asset.get("assembly_rules", {}),
            "shape_mode": asset.get("build", {}).get("shape", {}).get("mode", "generate"),
            "objectives": objectives,
            "self_reliant_target": family
            in {
                "brassbound_chest",
                "industrial_crate",
                "mechanical_door",
                "console_terminal",
                "service_cabinet",
                "control_pedestal",
                "supply_container",
                "sci_fi_wall_panel",
                "courier_drone",
                "hero_sword",
                "procedural_building",
                "procedural_vehicle",
                "procedural_weapon",
                "procedural_boat",
                "procedural_machine",
                "procedural_furniture",
                "procedural_foliage",
                "procedural_infrastructure",
                "procedural_access",
                "procedural_urban_prop",
                "procedural_setpiece",
                "procedural_road",
                "procedural_bridge",
                "procedural_terrain",
                "procedural_city_block",
                "procedural_interior",
            },
        },
    )
