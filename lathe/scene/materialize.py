"""Scene-to-asset source materialization helpers for Wonder readiness."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from ..checker import check_program
from ..child_modules import child_module_layout_from_authoring
from ..connection_layout import connection_layout_from_authoring
from ..creative_grammar import creative_grammar_for_scene
from ..asset_graph import build_asset_graph
from ..core.errors import BuildError
from ..nested_assembly import nested_assembly_manifest
from ..nested_assets import nested_asset_manifest_for_signature
from ..object_grammar import object_grammar_for_scene
from ..parser import LatheParseError, PromptInjectionError, parse_file
from ..planner import build_plan
from ..resolver import ResolutionError
from ..surface_grammar import merge_surface_grammar, surface_grammar_for_controls
from .graph import load_and_check_scene_graph
from .io import write_json_atomic, write_text_atomic
from .planner import plan_scene, validate_scene_plan_payload

SCENE_MATERIALIZATION_VERSION = "lathe.scene_materialization_manifest.v1"
SCENE_MATERIALIZATION_CONTRACT = "scene_materialization_manifest"
SCENE_MATERIALIZATION_SCHEMA_FILENAME = "scene_materialization_manifest.schema.json"

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NON_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_ARCHITECTURE_TOKENS = {
    "arch",
    "architecture",
    "appliance",
    "bridge",
    "building",
    "city",
    "block",
    "bed",
    "cabinet",
    "ceiling",
    "chair",
    "column",
    "counter",
    "desk",
    "drawer",
    "environment",
    "floor",
    "furniture",
    "furnishing",
    "ground",
    "interior",
    "lane",
    "lamp",
    "platform",
    "road",
    "shelf",
    "sidewalk",
    "table",
    "railing",
    "rib",
    "room",
    "shell",
    "span",
    "stair",
    "street",
    "structure",
    "terrain",
    "tunnel",
    "wall",
    "window",
    "outpost",
    "market",
    "fortress",
    "factory",
    "harbor",
    "harbour",
    "dockyard",
    "district",
    "hangar",
    "airfield",
    "temple",
    "shrine",
    "sanctuary",
    "setpiece",
    "street_grid",
    "room_cluster",
}
_MECHANICAL_TOKENS = {
    "airlock",
    "door",
    "gear",
    "hinge",
    "lock",
    "machine",
    "mechanical",
    "mechanism",
    "motor",
    "portal",
}
_VEHICLE_TOKENS = {
    "vehicle",
    "car",
    "truck",
    "rover",
    "drone",
    "aircraft",
    "interceptor",
    "plane",
    "vtol",
    "hover",
    "chassis",
    "wheel",
    "track",
    "turret",
    "thruster",
    "stabilizer",
    "hardpoint",
    "payload",
}
_BOAT_TOKENS = {
    "boat",
    "ship",
    "vessel",
    "watercraft",
    "sailboat",
    "barge",
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
    "mast",
    "sail",
    "pontoon",
    "outrigger",
    "rudder",
    "propeller",
    "cleat",
    "mooring",
}
_WEAPON_TOKENS = {
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
    "tool",
    "barrel",
    "muzzle",
    "magazine",
    "ammo",
    "power",
    "sling",
    "salvage",
    "ceremonial",
}
_GENERATED_SOURCE_ERRORS = (
    LatheParseError,
    PromptInjectionError,
    ResolutionError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)
_PROCEDURAL_FAMILY_PARTS: dict[str, tuple[str, ...]] = {
    "procedural_building": (
        "building_body",
        "floor_band",
        "wall_panel",
        "window_bay",
        "entry_door",
        "roof",
        "column",
        "stair",
        "balcony",
        "awning",
        "cornice",
        "tower",
        "chimney",
        "dormer",
        "arch",
        "parapet",
        "signage",
        "roof_equipment",
        "fire_escape",
        "service_door",
    ),
    "procedural_vehicle": (
        "chassis",
        "cabin",
        "wheel",
        "engine",
        "track",
        "suspension",
        "cargo_module",
        "turret",
        "wing",
        "rotor",
        "manipulator_arm",
        "crew_bay",
        "cargo_bay",
        "hardpoint",
        "module_socket",
        "thruster",
        "stabilizer",
        "sensor",
        "antenna",
    ),
    "procedural_weapon": (
        "weapon_body",
        "barrel",
        "blade",
        "tip",
        "grip",
        "guard",
        "stock",
        "magazine",
        "sight",
        "trigger",
        "tool_head",
        "attachment_rail",
        "hardpoint",
        "module_socket",
        "muzzle_device",
        "ammo_bay",
        "power_cell",
        "sling_mount",
        "stabilizer",
        "sensor",
    ),
    "procedural_boat": (
        "hull",
        "deck",
        "cabin",
        "mast",
        "engine",
        "sail",
        "rigging",
        "pontoon",
        "outrigger",
        "cargo_hold",
        "railing",
        "rudder",
        "propeller",
        "anchor",
        "crew_bay",
        "cargo_bay",
        "hardpoint",
        "module_socket",
        "thruster",
        "stabilizer",
        "sensor",
        "cleat",
    ),
    "procedural_machine": ("machine_base", "machine_column", "manipulator_arm", "hydraulic_piston", "conveyor", "gear", "tank", "crane_boom", "tool_head"),
    "procedural_road": (
        "road_surface",
        "lane_marker",
        "sidewalk",
        "junction",
        "branch",
        "crosswalk",
        "turnout",
        "median",
        "curb_ramp",
        "stop_line",
        "lane_arrow",
        "bike_lane",
        "parking_bay",
        "streetlight",
        "bollard",
    ),
    "procedural_bridge": ("bridge_deck", "railing", "pier", "abutment"),
    "procedural_terrain": ("terrain_patch", "terrace", "ridge", "cliff", "path"),
    "procedural_city_block": (
        "city_block",
        "street",
        "lot",
        "building",
        "roof",
        "sidewalk",
        "alley",
        "plaza",
        "crosswalk",
        "streetlight",
        "window",
        "door",
    ),
    "procedural_interior": (
        "room_shell",
        "wall_panel",
        "door",
        "window",
        "column",
        "corridor",
        "partition",
        "ceiling_light",
        "stair_core",
        "alcove",
        "furniture_base",
        "table_top",
        "chair_seat",
        "chair_back",
        "bed_frame",
        "shelf_unit",
        "cabinet_body",
        "counter_top",
        "lamp",
    ),
    "procedural_furniture": (
        "furniture_base",
        "chair_seat",
        "chair_back",
        "furniture_leg",
        "table_top",
        "bed_frame",
        "shelf_unit",
        "cabinet_body",
        "drawer",
        "cushion",
        "counter_top",
        "appliance_body",
        "lamp",
    ),
    "procedural_foliage": (
        "foliage_ground",
        "tree_trunk",
        "root",
        "tree_branch",
        "leaf_cluster",
        "bush",
        "grass_clump",
        "natural_rock",
        "mushroom",
        "fallen_log",
        "vine",
        "flower",
        "planter",
    ),
    "procedural_urban_prop": (
        "urban_base",
        "fence_segment",
        "gate_panel",
        "sign_post",
        "streetlight",
        "street_bench",
        "trash_bin",
        "utility_pole",
        "cable_span",
        "kiosk_body",
        "market_stall",
        "street_barrier",
        "street_crate",
        "bollard",
    ),
    "procedural_infrastructure": (
        "infrastructure_base",
        "pipe_run",
        "duct_run",
        "drain_channel",
        "fire_hydrant",
        "transformer_box",
        "service_rail",
        "overhead_conduit",
        "junction_box",
        "valve_wheel",
        "manhole_cover",
        "support_bracket",
        "cable_tray",
    ),
    "procedural_access": (
        "access_base",
        "catwalk_deck",
        "walkway_span",
        "guardrail",
        "access_ladder",
        "access_ramp",
        "gantry_frame",
        "elevator_shaft",
        "access_platform",
        "tunnel_segment",
        "scaffold_frame",
        "safety_gate",
        "access_support",
    ),
    "procedural_setpiece": (
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
        "vehicle_payload_bay",
        "vehicle_hardpoint",
        "vehicle_module_socket",
        "vehicle_thruster",
        "vehicle_sensor",
        "boat_hull",
        "boat_deck",
        "boat_mission_socket",
        "boat_deck_hardpoint",
        "boat_thruster",
        "boat_sensor",
        "boat_cleat",
        "machine_base",
        "machine_conveyor",
        "interior_room",
        "furniture_cluster",
        "foliage_cluster",
        "module_socket",
    ),
}
_ROOM_CONTENT_ITEM_PARTS: dict[str, tuple[str, ...]] = {
    "counter": ("counter_top", "cabinet_body", "furniture_leg"),
    "cabinet": ("cabinet_body", "drawer", "shelf_unit"),
    "appliance": ("appliance_body", "cabinet_body"),
    "sink": ("appliance_body", "counter_top", "service_connection"),
    "toilet": ("appliance_body", "service_connection"),
    "shower": ("appliance_body", "service_connection", "wall_panel"),
    "lab_bench": ("counter_top", "cabinet_body", "service_connection"),
    "medical_bed": ("bed_frame", "cushion", "service_connection"),
    "workstation": ("table_top", "chair_seat", "lamp"),
    "terminal": ("table_top", "appliance_body", "lamp"),
    "tool_rack": ("shelf_unit", "wall_bracket", "drawer"),
    "rack": ("shelf_unit", "wall_bracket"),
    "bed": ("bed_frame", "cushion"),
    "lamp": ("lamp", "furniture_leg"),
}
_PROCEDURAL_CONTROL_ALIASES: dict[str, tuple[str, ...]] = {
    "archetype": ("archetype", "object_archetype"),
    "loadout": ("loadout", "family_loadout", "vehicle_loadout", "boat_loadout", "weapon_loadout"),
    "family_loadout": ("family_loadout", "loadout"),
    "vehicle_loadout": ("vehicle_loadout", "vehicle_archetype", "loadout", "family_loadout"),
    "vehicle_archetype": ("vehicle_archetype", "vehicle_loadout", "archetype"),
    "boat_loadout": ("boat_loadout", "boat_archetype", "vessel_loadout", "loadout", "family_loadout"),
    "boat_archetype": ("boat_archetype", "boat_loadout", "vessel_archetype", "archetype"),
    "vessel_loadout": ("vessel_loadout", "boat_loadout", "family_loadout"),
    "vessel_archetype": ("vessel_archetype", "boat_archetype", "archetype"),
    "weapon_loadout": ("weapon_loadout", "weapon_archetype", "tool_loadout", "loadout", "family_loadout"),
    "weapon_archetype": ("weapon_archetype", "weapon_loadout", "tool_archetype", "archetype"),
    "tool_loadout": ("tool_loadout", "weapon_loadout", "family_loadout"),
    "tool_archetype": ("tool_archetype", "weapon_archetype", "archetype"),
    "lanes": ("lanes", "lane_count", "road_lanes"),
    "lane_count": ("lane_count", "lanes", "road_lanes"),
    "spans": ("span_count", "spans", "bridge_spans"),
    "span_count": ("span_count", "spans", "bridge_spans"),
    "piers": ("pier_count", "piers"),
    "pier_count": ("pier_count", "piers"),
    "floors": ("floors", "floor_count", "building_floors"),
    "floor_count": ("floors", "floor_count", "building_floors"),
    "wings": ("wings", "wing_count"),
    "wing_count": ("wing_count", "wings"),
    "towers": ("towers", "tower_count"),
    "tower_count": ("tower_count", "towers"),
    "balconies": ("balconies", "balcony_count"),
    "balcony_count": ("balcony_count", "balconies"),
    "awnings": ("awnings", "awning_count"),
    "awning_count": ("awning_count", "awnings"),
    "dormers": ("dormers", "dormer_count"),
    "dormer_count": ("dormer_count", "dormers"),
    "chimneys": ("chimneys", "chimney_count"),
    "chimney_count": ("chimney_count", "chimneys"),
    "cornices": ("cornices", "cornice_count"),
    "cornice_count": ("cornice_count", "cornices"),
    "entries": ("entry_count", "entries", "door_count"),
    "entry_count": ("entry_count", "entries", "door_count"),
    "doors": ("door_count", "doors", "entry_count", "entries"),
    "door_count": ("door_count", "doors", "entry_count", "entries"),
    "windows": ("window_count", "windows", "window_bays", "bays"),
    "window_count": ("window_count", "windows", "window_bays", "bays"),
    "storefronts": ("storefront_count", "storefronts", "shopfront_count"),
    "storefront_count": ("storefront_count", "storefronts", "shopfront_count"),
    "shopfront_count": ("shopfront_count", "storefront_count", "storefronts"),
    "arcades": ("arcade_count", "arcades", "ground_arcade_count"),
    "arcade_count": ("arcade_count", "arcades", "ground_arcade_count"),
    "ground_arcade_count": ("ground_arcade_count", "arcade_count", "arcades"),
    "parapets": ("parapet_count", "parapets"),
    "parapet_count": ("parapet_count", "parapets"),
    "roof_equipment": ("roof_equipment_count", "roof_equipment", "hvac_count"),
    "roof_equipment_count": ("roof_equipment_count", "roof_equipment", "hvac_count"),
    "hvac_count": ("hvac_count", "roof_equipment_count", "roof_equipment"),
    "signage": ("signage_count", "signage", "sign_count", "signs"),
    "signage_count": ("signage_count", "signage", "sign_count", "signs"),
    "fire_escapes": ("fire_escape_count", "fire_escapes"),
    "fire_escape_count": ("fire_escape_count", "fire_escapes"),
    "side_window_bays": ("side_window_bays", "side_bays"),
    "side_bays": ("side_bays", "side_window_bays"),
    "rear_window_bays": ("rear_window_bays", "rear_bays"),
    "rear_bays": ("rear_bays", "rear_window_bays"),
    "service_doors": ("service_door_count", "service_doors"),
    "service_door_count": ("service_door_count", "service_doors"),
    "roof_style": ("roof_style",),
    "facade_style": ("facade_style", "architecture_style"),
    "rooms": ("rooms", "room_count"),
    "room_count": ("room_count", "rooms"),
    "corridors": ("corridors", "corridor_count"),
    "corridor_count": ("corridor_count", "corridors"),
    "partitions": ("partitions", "partition_count", "interior_partitions"),
    "partition_count": ("partition_count", "partitions", "interior_partitions"),
    "ceiling_lights": ("ceiling_lights", "light_count"),
    "light_count": ("light_count", "ceiling_lights"),
    "stair_cores": ("stair_cores", "stair_core_count"),
    "stair_core_count": ("stair_core_count", "stair_cores"),
    "stairs": ("stair_core_count", "stair_count", "stairs", "stair_cores"),
    "stair_count": ("stair_core_count", "stair_count", "stairs", "stair_cores"),
    "alcoves": ("alcoves", "alcove_count"),
    "alcove_count": ("alcove_count", "alcoves"),
    "room_layout": ("room_layout",),
    "furniture_type": ("furniture_type", "room_role", "furnishing_type", "archetype"),
    "furnishing_type": ("furnishing_type", "furniture_type", "room_role", "archetype"),
    "room_role": ("room_role", "furniture_type", "furnishing_type", "archetype"),
    "furniture_style": ("furniture_style", "decor_style", "style"),
    "chairs": ("chair_count", "chairs", "seat_count"),
    "chair_count": ("chair_count", "chairs", "seat_count"),
    "tables": ("table_count", "tables", "desk_count"),
    "table_count": ("table_count", "tables", "desk_count"),
    "beds": ("bed_count", "beds", "bunk_count"),
    "bed_count": ("bed_count", "beds", "bunk_count"),
    "shelves": ("shelf_count", "shelves", "rack_count"),
    "shelf_count": ("shelf_count", "shelves", "rack_count"),
    "cabinets": ("cabinet_count", "cabinets", "locker_count"),
    "cabinet_count": ("cabinet_count", "cabinets", "locker_count"),
    "drawers": ("drawer_count", "drawers"),
    "drawer_count": ("drawer_count", "drawers"),
    "cushions": ("cushion_count", "cushions", "pillow_count"),
    "cushion_count": ("cushion_count", "cushions", "pillow_count"),
    "counters": ("counter_count", "counters", "workbench_count"),
    "counter_count": ("counter_count", "counters", "workbench_count"),
    "appliances": ("appliance_count", "appliances", "fixture_count"),
    "appliance_count": ("appliance_count", "appliances", "fixture_count"),
    "fixtures": ("fixture_count", "fixtures"),
    "fixture_count": ("fixture_count", "fixtures"),
    "workstations": ("workstation_count", "workstations", "desk_count"),
    "workstation_count": ("workstation_count", "workstations", "desk_count"),
    "sinks": ("sink_count", "sinks"),
    "sink_count": ("sink_count", "sinks"),
    "toilets": ("toilet_count", "toilets"),
    "toilet_count": ("toilet_count", "toilets"),
    "showers": ("shower_count", "showers"),
    "shower_count": ("shower_count", "showers"),
    "tools": ("tool_count", "tools"),
    "tool_count": ("tool_count", "tools"),
    "racks": ("rack_count", "racks", "shelf_count"),
    "rack_count": ("rack_count", "racks", "shelf_count"),
    "work_surface_count": ("work_surface_count", "counter_count", "counters"),
    "cleanliness": ("cleanliness",),
    "sterility": ("sterility",),
    "privacy": ("privacy",),
    "room_programs": ("room_programs", "room_roles", "room_types"),
    "room_roles": ("room_roles", "room_programs", "room_types"),
    "room_adjacencies": ("room_adjacencies", "adjacent_rooms", "room_pairs"),
    "room_connections": ("room_connections", "connected_rooms", "room_pairs"),
    "adjacent_rooms": ("adjacent_rooms", "room_pairs", "connected_rooms"),
    "connected_rooms": ("connected_rooms", "room_pairs", "adjacent_rooms"),
    "room_pairs": ("room_pairs", "adjacent_rooms", "connected_rooms"),
    "from_room": ("from_room", "source_room", "room_a"),
    "to_room": ("to_room", "target_room", "room_b"),
    "source_room": ("source_room", "from_room", "room_a"),
    "target_room": ("target_room", "to_room", "room_b"),
    "connection_type": ("connection_type", "access_type", "traversal_type"),
    "wall_side": ("wall_side", "side"),
    "opening_width": ("opening_width", "door_width"),
    "threshold_depth": ("threshold_depth", "threshold"),
    "doorway_count": ("doorway_count", "door_opening_count", "door_count"),
    "corridor_width": ("corridor_width", "route_width"),
    "corridor_length": ("corridor_length", "connection_length"),
    "wall_length": ("wall_length", "length"),
    "wall_thickness": ("wall_thickness", "thickness"),
    "socket_role": ("socket_role", "socket_type"),
    "socket_target": ("socket_target", "target"),
    "socket_tags": ("socket_tags", "composition_sockets"),
    "attach_tags": ("attach_tags", "composition_anchors"),
    "attach_family": ("attach_family", "family"),
    "attach_count": ("attach_count", "socket_count"),
    "placement_mode": ("placement_mode", "mode"),
    "placement_rule": ("placement_rule", "constraint_type"),
    "placement_target": ("placement_target", "target_socket", "socket_target"),
    "target_socket": ("target_socket", "socket_target", "placement_target"),
    "source_object": ("source_object", "placed_object"),
    "placed_object": ("placed_object", "source_object"),
    "placed_family": ("placed_family", "fixture_type", "furniture_type"),
    "fixture_type": ("fixture_type", "furniture_type", "placed_family"),
    "snap_mode": ("snap_mode", "placement_mode"),
    "snap_strength": ("snap_strength",),
    "clearance": ("clearance", "clearance_radius"),
    "clearance_radius": ("clearance_radius", "clearance"),
    "orientation": ("orientation", "facing"),
    "offset": ("offset",),
    "offset_x": ("offset_x",),
    "offset_y": ("offset_y",),
    "offset_z": ("offset_z",),
    "anchor_priority": ("anchor_priority", "priority"),
    "allow_rotation": ("allow_rotation",),
    "align_to_wall": ("align_to_wall",),
    "placement_group": ("placement_group", "group"),
    "layout_strategy": ("layout_strategy", "strategy"),
    "layout_density": ("layout_density", "density"),
    "layout_zones": ("layout_zones", "zones"),
    "layout_slots": ("layout_slots", "slot_count", "socket_count"),
    "auto_place": ("auto_place",),
    "auto_place_doors": ("auto_place_doors",),
    "auto_place_services": ("auto_place_services",),
    "auto_place_fixtures": ("auto_place_fixtures",),
    "auto_place_furniture": ("auto_place_furniture",),
    "fixture_types": ("fixture_types", "fixtures", "fixture_families"),
    "furniture_types": ("furniture_types", "furniture", "furnishings"),
    "wall_fixture_types": ("wall_fixture_types", "wall_fixtures", "wall_attachments"),
    "service_types": ("service_types", "services", "utilities"),
    "door_policy": ("door_policy",),
    "socket_policy": ("socket_policy",),
    "anchor_policy": ("anchor_policy",),
    "placement_rules": ("placement_rules", "rules"),
    "placement_constraints": ("placement_constraints", "constraints"),
    "room_width": ("room_width", "width"),
    "room_depth": ("room_depth", "depth"),
    "room_height": ("room_height", "height"),
    "floor_area": ("floor_area",),
    "usable_area": ("usable_area",),
    "wall_sides": ("wall_sides", "walls"),
    "preferred_walls": ("preferred_walls", "wall_sides"),
    "blocked_walls": ("blocked_walls", "avoid_walls"),
    "chosen_wall_side": ("chosen_wall_side", "wall_side"),
    "wall_side_weights": ("wall_side_weights",),
    "socket_priority": ("socket_priority", "priority"),
    "socket_weights": ("socket_weights",),
    "priority_rules": ("priority_rules", "placement_rules"),
    "clearance_policy": ("clearance_policy",),
    "clearance_targets": ("clearance_targets",),
    "clearance_zones": ("clearance_zones",),
    "layout_axis": ("layout_axis", "axis"),
    "slot_spacing": ("slot_spacing", "spacing"),
    "slot_capacity": ("slot_capacity", "capacity"),
    "slot_index": ("slot_index", "index"),
    "slot_kind": ("slot_kind", "slot_type"),
    "resolved_slots": ("resolved_slots",),
    "blocked_slots": ("blocked_slots",),
    "footprint_width": ("footprint_width", "width"),
    "footprint_depth": ("footprint_depth", "depth"),
    "footprint_height": ("footprint_height", "height"),
    "footprint_shape": ("footprint_shape", "shape"),
    "footprint_padding": ("footprint_padding", "padding"),
    "footprint_rotation": ("footprint_rotation", "rotation_degrees"),
    "grid_rows": ("grid_rows", "rows"),
    "grid_columns": ("grid_columns", "columns"),
    "cell_size": ("cell_size",),
    "occupied_cells": ("occupied_cells", "blocked_cells"),
    "free_cells": ("free_cells", "available_cells"),
    "packed_items": ("packed_items", "items"),
    "fit_score": ("fit_score",),
    "fit_policy": ("fit_policy",),
    "can_rotate": ("can_rotate",),
    "allow_overlap": ("allow_overlap",),
    "collision_policy": ("collision_policy",),
    "collision_pairs": ("collision_pairs",),
    "service_radius": ("service_radius",),
    "required_services": ("required_services", "services", "service_types"),
    "service_targets": ("service_targets", "service_taps"),
    "max_service_distance": ("max_service_distance", "service_radius"),
    "reach_score": ("reach_score",),
    "packing_axis": ("packing_axis", "layout_axis", "axis"),
    "packing_origin": ("packing_origin", "origin"),
    "packing_spacing": ("packing_spacing", "slot_spacing", "spacing"),
    "packing_slots": ("packing_slots",),
    "slot_positions": ("slot_positions",),
    "packed_positions": ("packed_positions",),
    "packed_transforms": ("packed_transforms",),
    "resolved_transforms": ("resolved_transforms", "packed_transforms"),
    "transform_policy": ("transform_policy", "packing_strategy"),
    "clearance_reservations": ("clearance_reservations", "clearance_targets"),
    "service_anchor_map": ("service_anchor_map",),
    "service_anchors": ("service_anchors", "required_services", "services"),
    "parent_object": ("parent_object", "parent"),
    "child_objects": ("child_objects", "packed_items", "items"),
    "packed_item": ("packed_item", "item_type", "fixture_type", "furniture_type"),
    "slot_id": ("slot_id", "target_socket"),
    "resolved_position": ("resolved_position", "position"),
    "resolved_rotation": ("resolved_rotation", "rotation"),
    "room_packing_result": ("room_packing_result",),
    "room_content_plan": ("room_content_plan",),
    "content_family_binding": ("content_family_binding",),
    "content_family": ("content_family", "source_family"),
    "content_asset_type": ("content_asset_type", "packed_item", "item_type"),
    "content_surface_plan": ("content_surface_plan",),
    "content_surface_profile": ("content_surface_profile", "surface_profile"),
    "content_surface_zones": ("content_surface_zones", "surface_zones", "zones"),
    "content_finish_layers": ("content_finish_layers", "finish_layers", "material_layers"),
    "content_markings": ("content_markings", "markings", "story_decals"),
    "content_wear": ("content_wear", "wear", "patterns"),
    "content_material_profile": ("content_material_profile", "material_profile"),
    "generated_child_asset": ("generated_child_asset",),
    "generated_child_assets": ("generated_child_assets", "child_objects", "packed_items"),
    "content_asset_controls": ("content_asset_controls",),
    "preset_role": ("preset_role", "room_role", "role"),
    "role_preset": ("role_preset", "preset_role"),
    "preset_items": ("preset_items", "packed_items", "items"),
    "item_footprints": ("item_footprints", "default_footprints"),
    "default_footprints": ("default_footprints", "item_footprints"),
    "packing_policy": ("packing_policy", "packing_strategy"),
    "packing_density": ("packing_density", "layout_density"),
    "clearance_profile": ("clearance_profile", "clearance_policy"),
    "service_profile": ("service_profile", "service_type"),
    "role_services": ("role_services", "required_services", "services"),
    "role_clearances": ("role_clearances", "clearance_targets", "clearance_zones"),
    "role_footprints": ("role_footprints", "item_footprints"),
    "role_packing_rules": ("role_packing_rules", "priority_rules"),
    "required_clearance": ("required_clearance", "clearance_radius"),
    "preferred_item_order": ("preferred_item_order", "preset_items"),
    "building_envelope": ("building_envelope",),
    "floor_stack": ("floor_stack",),
    "facade_grid": ("facade_grid",),
    "facade_bay": ("facade_bay",),
    "roof_profile": ("roof_profile",),
    "vertical_core": ("vertical_core",),
    "entrance_plan": ("entrance_plan",),
    "building_envelope_profile": ("building_envelope_profile", "building_type", "envelope_type"),
    "building_program": ("building_program", "program"),
    "floor_roles": ("floor_roles", "room_roles", "program_roles"),
    "floor_plan": ("floor_plan",),
    "floor_heights": ("floor_heights",),
    "facade_sides": ("facade_sides", "wall_sides"),
    "facade_bays": ("facade_bays",),
    "facade_pattern": ("facade_pattern", "facade_style", "architecture_style"),
    "roof_pitch": ("roof_pitch", "pitch"),
    "vertical_core_types": ("vertical_core_types", "core_types"),
    "entrance_locations": ("entrance_locations", "entries"),
    "building_envelope_controls": ("building_envelope_controls",),
    "lamps": ("lamp_count", "lamps", "light_count"),
    "lamp_count": ("lamp_count", "lamps", "light_count"),
    "legs": ("leg_count", "legs"),
    "leg_count": ("leg_count", "legs"),
    "foliage_type": ("foliage_type", "plant_type", "nature_type", "archetype"),
    "plant_type": ("plant_type", "foliage_type", "nature_type", "archetype"),
    "nature_type": ("nature_type", "foliage_type", "plant_type", "archetype"),
    "trunks": ("trunk_count", "trunks", "tree_count"),
    "trunk_count": ("trunk_count", "trunks", "tree_count"),
    "tree_count": ("tree_count", "trunk_count", "trunks"),
    "branches": ("branch_count", "branches"),
    "branch_count": ("branch_count", "branches"),
    "roots": ("root_count", "roots"),
    "root_count": ("root_count", "roots"),
    "canopies": ("canopy_count", "canopies", "leaf_cluster_count"),
    "canopy_count": ("canopy_count", "canopies", "leaf_cluster_count"),
    "leaf_clusters": ("leaf_cluster_count", "leaf_clusters", "leaves"),
    "leaf_cluster_count": ("leaf_cluster_count", "leaf_clusters", "leaves"),
    "bushes": ("bush_count", "bushes", "shrub_count"),
    "bush_count": ("bush_count", "bushes", "shrub_count"),
    "grass": ("grass_count", "grass_clumps", "grass_clump_count"),
    "grass_count": ("grass_count", "grass_clumps", "grass_clump_count"),
    "rocks": ("rock_count", "rocks", "stone_count"),
    "rock_count": ("rock_count", "rocks", "stone_count"),
    "mushrooms": ("mushroom_count", "mushrooms", "fungi_count"),
    "mushroom_count": ("mushroom_count", "mushrooms", "fungi_count"),
    "logs": ("log_count", "logs", "fallen_log_count"),
    "log_count": ("log_count", "logs", "fallen_log_count"),
    "vines": ("vine_count", "vines"),
    "vine_count": ("vine_count", "vines"),
    "flowers": ("flower_count", "flowers", "blossom_count"),
    "flower_count": ("flower_count", "flowers", "blossom_count"),
    "planters": ("planter_count", "planters", "pot_count"),
    "planter_count": ("planter_count", "planters", "pot_count"),
    "urban_prop_type": ("urban_prop_type", "street_prop_type", "set_dressing_type", "archetype"),
    "street_prop_type": ("street_prop_type", "urban_prop_type", "set_dressing_type", "archetype"),
    "set_dressing_type": ("set_dressing_type", "urban_prop_type", "street_prop_type", "archetype"),
    "urban_style": ("urban_style", "district_style", "civic_style", "style"),
    "district_style": ("district_style", "urban_style", "civic_style", "style"),
    "fences": ("fence_count", "fences"),
    "fence_count": ("fence_count", "fences"),
    "gates": ("gate_count", "gates"),
    "gate_count": ("gate_count", "gates"),
    "signs": ("sign_count", "signs", "signage_count"),
    "sign_count": ("sign_count", "signs", "signage_count"),
    "streetlights": ("streetlight_count", "streetlights", "lamp_post_count"),
    "streetlight_count": ("streetlight_count", "streetlights", "lamp_post_count"),
    "lamp_posts": ("lamp_post_count", "lamp_posts", "streetlight_count"),
    "lamp_post_count": ("lamp_post_count", "lamp_posts", "streetlight_count"),
    "benches": ("bench_count", "benches"),
    "bench_count": ("bench_count", "benches"),
    "bins": ("bin_count", "bins", "trash_bin_count"),
    "bin_count": ("bin_count", "bins", "trash_bin_count"),
    "trash_bins": ("trash_bin_count", "trash_bins", "bin_count"),
    "trash_bin_count": ("trash_bin_count", "trash_bins", "bin_count"),
    "poles": ("pole_count", "poles", "utility_pole_count"),
    "pole_count": ("pole_count", "poles", "utility_pole_count"),
    "utility_poles": ("utility_pole_count", "utility_poles", "pole_count"),
    "utility_pole_count": ("utility_pole_count", "utility_poles", "pole_count"),
    "cables": ("cable_count", "cables", "wire_count"),
    "cable_count": ("cable_count", "cables", "wire_count"),
    "wires": ("wire_count", "wires", "cable_count"),
    "wire_count": ("wire_count", "wires", "cable_count"),
    "kiosks": ("kiosk_count", "kiosks"),
    "kiosk_count": ("kiosk_count", "kiosks"),
    "stalls": ("stall_count", "stalls", "market_stall_count"),
    "stall_count": ("stall_count", "stalls", "market_stall_count"),
    "barriers": ("barrier_count", "barriers", "barricade_count"),
    "barrier_count": ("barrier_count", "barriers", "barricade_count"),
    "street_crates": ("street_crate_count", "street_crates", "crate_count"),
    "street_crate_count": ("street_crate_count", "street_crates", "crate_count"),
    "bollards": ("bollard_count", "bollards"),
    "bollard_count": ("bollard_count", "bollards"),
    "infrastructure_type": ("infrastructure_type", "utility_type", "service_type", "network_type", "archetype"),
    "utility_type": ("utility_type", "infrastructure_type", "service_type", "network_type", "archetype"),
    "service_type": ("service_type", "utility_type", "network_service", "infrastructure_type"),
    "network_type": ("network_type", "infrastructure_type", "utility_type", "service_type"),
    "pipes": ("pipe_count", "pipes"),
    "pipe_count": ("pipe_count", "pipes"),
    "ducts": ("duct_count", "ducts"),
    "duct_count": ("duct_count", "ducts"),
    "conduits": ("conduit_count", "conduits", "overhead_conduit_count"),
    "conduit_count": ("conduit_count", "conduits", "overhead_conduit_count"),
    "overhead_conduits": ("overhead_conduit_count", "overhead_conduits", "conduit_count"),
    "overhead_conduit_count": ("overhead_conduit_count", "overhead_conduits", "conduit_count"),
    "drains": ("drain_count", "drains", "channel_count"),
    "drain_count": ("drain_count", "drains", "channel_count"),
    "hydrants": ("hydrant_count", "hydrants"),
    "hydrant_count": ("hydrant_count", "hydrants"),
    "transformers": ("transformer_count", "transformers"),
    "transformer_count": ("transformer_count", "transformers"),
    "junction_boxes": ("junction_box_count", "junction_boxes", "service_box_count"),
    "junction_box_count": ("junction_box_count", "junction_boxes", "service_box_count"),
    "service_boxes": ("service_box_count", "service_boxes", "junction_box_count"),
    "service_box_count": ("service_box_count", "service_boxes", "junction_box_count"),
    "valves": ("valve_count", "valves"),
    "valve_count": ("valve_count", "valves"),
    "manholes": ("manhole_count", "manholes"),
    "manhole_count": ("manhole_count", "manholes"),
    "service_rails": ("service_rail_count", "service_rails", "rail_count"),
    "service_rail_count": ("service_rail_count", "service_rails", "rail_count"),
    "supports": ("support_count", "supports", "bracket_count"),
    "support_count": ("support_count", "supports", "bracket_count"),
    "cable_trays": ("cable_tray_count", "cable_trays", "tray_count"),
    "cable_tray_count": ("cable_tray_count", "cable_trays", "tray_count"),
    "access_type": ("access_type", "traversal_type", "maintenance_access_type", "archetype"),
    "traversal_type": ("traversal_type", "access_type", "maintenance_access_type", "archetype"),
    "maintenance_access_type": ("maintenance_access_type", "access_type", "traversal_type", "archetype"),
    "access_style": ("access_style", "industrial_style", "style"),
    "catwalks": ("catwalk_count", "catwalks"),
    "catwalk_count": ("catwalk_count", "catwalks"),
    "walkways": ("walkway_count", "walkways", "span_count"),
    "walkway_count": ("walkway_count", "walkways", "span_count"),
    "ladders": ("ladder_count", "ladders"),
    "ladder_count": ("ladder_count", "ladders"),
    "ramps": ("ramp_count", "ramps"),
    "ramp_count": ("ramp_count", "ramps"),
    "gantries": ("gantry_count", "gantries"),
    "gantry_count": ("gantry_count", "gantries"),
    "elevators": ("elevator_count", "elevators", "lift_count"),
    "elevator_count": ("elevator_count", "elevators", "lift_count"),
    "lifts": ("lift_count", "lifts", "elevator_count"),
    "lift_count": ("lift_count", "lifts", "elevator_count"),
    "platforms": ("platform_count", "platforms", "maintenance_platform_count"),
    "maintenance_platform_count": ("maintenance_platform_count", "platform_count", "platforms"),
    "tunnels": ("tunnel_count", "tunnels"),
    "tunnel_count": ("tunnel_count", "tunnels"),
    "scaffolds": ("scaffold_count", "scaffolds", "scaffold_frame_count"),
    "scaffold_count": ("scaffold_count", "scaffolds", "scaffold_frame_count"),
    "guardrails": ("guardrail_count", "guardrails"),
    "guardrail_count": ("guardrail_count", "guardrails"),
    "safety_gates": ("safety_gate_count", "safety_gates", "gate_count"),
    "safety_gate_count": ("safety_gate_count", "safety_gates", "gate_count"),
    "lots": ("lot_count", "lots", "building_count"),
    "lot_count": ("lot_count", "lots", "building_count"),
    "bays": ("bays", "window_bays", "wall_bays", "interior_bays"),
    "bay_count": ("bays", "window_bays", "wall_bays", "interior_bays"),
    "terraces": ("terrace_count", "terraces", "platform_count"),
    "terrace_count": ("terrace_count", "terraces", "platform_count"),
    "masts": ("mast_count", "masts"),
    "mast_count": ("mast_count", "masts"),
    "boat_type": ("boat_type", "hull_type", "watercraft_type", "vessel_type"),
    "hull_type": ("hull_type", "boat_type", "watercraft_type", "vessel_type"),
    "watercraft_type": ("watercraft_type", "boat_type", "hull_type", "vessel_type"),
    "propulsion": ("propulsion", "drive_type"),
    "engines": ("engine_count", "engines"),
    "engine_count": ("engine_count", "engines"),
    "cabins": ("cabin_count", "cabins"),
    "cabin_count": ("cabin_count", "cabins"),
    "deck_levels": ("deck_level_count", "deck_levels"),
    "deck_level_count": ("deck_level_count", "deck_levels"),
    "sails": ("sail_count", "sails"),
    "sail_count": ("sail_count", "sails"),
    "rigging": ("rigging_count", "rigging", "lines"),
    "rigging_count": ("rigging_count", "rigging", "lines"),
    "pontoons": ("pontoon_count", "pontoons", "float_count"),
    "pontoon_count": ("pontoon_count", "pontoons", "float_count"),
    "outriggers": ("outrigger_count", "outriggers"),
    "outrigger_count": ("outrigger_count", "outriggers"),
    "rudders": ("rudder_count", "rudders"),
    "rudder_count": ("rudder_count", "rudders"),
    "propellers": ("propeller_count", "propellers", "props"),
    "propeller_count": ("propeller_count", "propellers", "props"),
    "cargo_holds": ("cargo_hold_count", "cargo_holds", "hold_count"),
    "cargo_hold_count": ("cargo_hold_count", "cargo_holds", "hold_count"),
    "anchors": ("anchor_count", "anchors"),
    "anchor_count": ("anchor_count", "anchors"),
    "rails": ("rail_count", "rails", "railing_count"),
    "rail_count": ("rail_count", "rails", "railing_count"),
    "crew_bays": ("crew_bay_count", "crew_bays", "cockpit_count", "bridge_count"),
    "crew_bay_count": ("crew_bay_count", "crew_bays", "cockpit_count", "bridge_count"),
    "cockpit_count": ("cockpit_count", "crew_bay_count", "crew_bays"),
    "bridge_count": ("bridge_count", "crew_bay_count", "crew_bays"),
    "cargo_bays": ("cargo_bay_count", "cargo_bays", "payload_bays"),
    "cargo_bay_count": ("cargo_bay_count", "cargo_bays", "payload_bays"),
    "payload_bays": ("cargo_bay_count", "cargo_bays", "payload_bays"),
    "hardpoints": ("hardpoint_count", "hardpoints", "weapon_mounts", "attachment_points"),
    "hardpoint_count": ("hardpoint_count", "hardpoints", "weapon_mounts", "attachment_points"),
    "weapon_mounts": ("weapon_mounts", "hardpoint_count", "hardpoints"),
    "module_sockets": ("module_socket_count", "module_sockets", "equipment_slots", "mission_slots", "attachment_sockets"),
    "module_socket_count": ("module_socket_count", "module_sockets", "equipment_slots", "mission_slots", "attachment_sockets"),
    "equipment_slots": ("equipment_slots", "module_socket_count", "module_sockets"),
    "mission_slots": ("mission_slots", "module_socket_count", "module_sockets"),
    "thrusters": ("thruster_count", "thrusters", "jet_count", "bow_thrusters"),
    "thruster_count": ("thruster_count", "thrusters", "jet_count", "bow_thrusters"),
    "stabilizers": ("stabilizer_count", "stabilizers", "tail_fins", "fins"),
    "stabilizer_count": ("stabilizer_count", "stabilizers", "tail_fins", "fins"),
    "sensors": ("sensor_count", "sensors", "antenna_count", "smart_sensors"),
    "sensor_count": ("sensor_count", "sensors", "antenna_count", "smart_sensors"),
    "antenna_count": ("antenna_count", "sensor_count", "sensors"),
    "deck_hardpoints": ("deck_hardpoint_count", "deck_hardpoints", "hardpoint_count"),
    "deck_hardpoint_count": ("deck_hardpoint_count", "deck_hardpoints", "hardpoint_count"),
    "cleats": ("cleat_count", "cleats", "mooring_points"),
    "cleat_count": ("cleat_count", "cleats", "mooring_points"),
    "mooring_points": ("mooring_points", "cleat_count", "cleats"),
    "wheels": ("wheel_count", "wheels"),
    "wheel_count": ("wheel_count", "wheels"),
    "drive_type": ("drive_type", "vehicle_type", "mobility"),
    "vehicle_type": ("vehicle_type", "drive_type", "mobility"),
    "tracks": ("track_count", "tracks"),
    "track_count": ("track_count", "tracks"),
    "suspension": ("suspension_count", "suspension"),
    "suspension_count": ("suspension_count", "suspension"),
    "rotors": ("rotor_count", "rotors"),
    "rotor_count": ("rotor_count", "rotors"),
    "turrets": ("turret_count", "turrets"),
    "turret_count": ("turret_count", "turrets"),
    "cargo_modules": ("cargo_module_count", "cargo_modules", "cargo_count"),
    "cargo_module_count": ("cargo_module_count", "cargo_modules", "cargo_count"),
    "arms": ("arm_count", "arms", "manipulator_count"),
    "arm_count": ("arm_count", "arms", "manipulator_count"),
    "machine_type": ("machine_type", "mechanism_type", "archetype"),
    "conveyors": ("conveyor_count", "conveyors"),
    "conveyor_count": ("conveyor_count", "conveyors"),
    "gears": ("gear_count", "gears"),
    "gear_count": ("gear_count", "gears"),
    "pistons": ("piston_count", "hydraulic_count", "pistons"),
    "piston_count": ("piston_count", "hydraulic_count", "pistons"),
    "tanks": ("tank_count", "vessel_count", "tanks"),
    "tank_count": ("tank_count", "vessel_count", "tanks"),
    "cranes": ("crane_count", "boom_count", "cranes"),
    "crane_count": ("crane_count", "boom_count", "cranes"),
    "weapon_type": ("weapon_type", "tool_type", "archetype"),
    "tool_type": ("tool_type", "weapon_type", "archetype"),
    "barrels": ("barrel_count", "barrels"),
    "barrel_count": ("barrel_count", "barrels"),
    "blades": ("blade_count", "blades"),
    "blade_count": ("blade_count", "blades"),
    "magazines": ("magazine_count", "magazines"),
    "magazine_count": ("magazine_count", "magazines"),
    "sights": ("sight_count", "sights"),
    "sight_count": ("sight_count", "sights"),
    "heads": ("head_count", "tool_head_count", "heads"),
    "head_count": ("head_count", "tool_head_count", "heads"),
    "guards": ("guard_count", "guards"),
    "guard_count": ("guard_count", "guards"),
    "attachment_rails": ("rail_count", "attachment_rails", "rails"),
    "attachment_points": ("hardpoint_count", "attachment_points", "hardpoints"),
    "muzzle_devices": ("muzzle_device_count", "muzzle_devices", "compensator_count"),
    "muzzle_device_count": ("muzzle_device_count", "muzzle_devices", "compensator_count"),
    "compensator_count": ("compensator_count", "muzzle_device_count", "muzzle_devices"),
    "ammo_bays": ("ammo_bay_count", "ammo_bays", "battery_bays"),
    "ammo_bay_count": ("ammo_bay_count", "ammo_bays", "battery_bays"),
    "battery_bays": ("battery_bays", "ammo_bay_count", "ammo_bays"),
    "power_cells": ("power_cell_count", "power_cells", "energy_cells"),
    "power_cell_count": ("power_cell_count", "power_cells", "energy_cells"),
    "energy_cells": ("energy_cells", "power_cell_count", "power_cells"),
    "sling_mounts": ("sling_mount_count", "sling_mounts"),
    "sling_mount_count": ("sling_mount_count", "sling_mounts"),
    "smart_sensors": ("smart_sensors", "sensor_count", "antenna_count"),
    "kit_count": ("kit_count", "module_count", "part_count"),
    "kit_sequence_index": ("kit_sequence_index",),
    "generator_count": ("generator_count", "variant_count", "generated_part_count"),
    "generator_index": ("generator_index", "variant_index"),
    "selection_constraint_count": ("selection_constraint_count", "constraint_count"),
    "scatter_count": ("scatter_count", "dressing_count", "environment_prop_count"),
    "scatter_index": ("scatter_index", "dressing_index", "environment_prop_index"),
    "scatter_pattern": ("scatter_pattern", "environment_pattern"),
    "scatter_seed": ("scatter_seed",),
    "biome_density": ("biome_density", "scatter_density", "environment_density"),
    "environment_count": ("environment_count", "world_feature_count"),
    "environment_index": ("environment_index", "world_feature_index"),
    "environment_feature": ("environment_feature", "landform"),
    "environment_feature_count": ("environment_feature_count", "landform_instance_count"),
    "environment_feature_index": ("environment_feature_index", "landform_instance_index"),
    "environment_pattern": ("environment_pattern", "terrain_pattern"),
    "environment_total_feature_count": ("environment_total_feature_count", "world_structure_count"),
    "environment_feature_kind_count": ("environment_feature_kind_count", "landform_kind_count"),
    "terrain_patch_count": ("terrain_patch_count", "terrain_tile_count"),
    "ridge_count": ("ridge_count",),
    "cliff_count": ("cliff_count",),
    "clearing_count": ("clearing_count",),
    "platform_count": ("platform_count",),
    "water_count": ("water_count",),
    "path_count": ("path_count", "trail_count"),
    "road_edge_count": ("road_edge_count",),
    "junction_count": ("junction_count", "intersection_count"),
    "intersection_count": ("intersection_count", "junction_count"),
    "branch_count": ("branch_count", "junction_branch_count", "road_branch_count"),
    "crosswalk_count": ("crosswalk_count",),
    "turnout_count": ("turnout_count", "pullout_count"),
    "medians": ("median_count", "medians"),
    "median_count": ("median_count", "medians"),
    "curb_ramps": ("curb_ramp_count", "curb_ramps"),
    "curb_ramp_count": ("curb_ramp_count", "curb_ramps"),
    "stop_lines": ("stop_line_count", "stop_lines"),
    "stop_line_count": ("stop_line_count", "stop_lines"),
    "lane_arrows": ("lane_arrow_count", "lane_arrows"),
    "lane_arrow_count": ("lane_arrow_count", "lane_arrows"),
    "bike_lanes": ("bike_lane_count", "bike_lanes"),
    "bike_lane_count": ("bike_lane_count", "bike_lanes"),
    "parking_bays": ("parking_bay_count", "parking_bays"),
    "parking_bay_count": ("parking_bay_count", "parking_bays"),
    "site_compound": ("site_compound",),
    "building_lot": ("building_lot",),
    "courtyard_plan": ("courtyard_plan",),
    "pedestrian_path": ("pedestrian_path",),
    "service_alley": ("service_alley",),
    "parking_zone": ("parking_zone",),
    "loading_zone": ("loading_zone",),
    "exterior_utility": ("exterior_utility",),
    "site_layout_profile": ("site_layout_profile", "site_type", "compound_type"),
    "site_buildings": ("site_buildings", "buildings", "building_types"),
    "building_lots": ("building_lots", "lots"),
    "courtyard_program": ("courtyard_program", "courtyards", "public_spaces"),
    "pedestrian_paths": ("pedestrian_paths", "paths", "walkways"),
    "service_alleys": ("service_alleys", "alleys", "service_routes"),
    "parking_zones": ("parking_zones", "parking"),
    "loading_zones": ("loading_zones", "loading"),
    "exterior_utilities": ("exterior_utilities", "utilities", "services"),
    "site_access_points": ("site_access_points", "access_points", "entries"),
    "site_utility_map": ("site_utility_map",),
    "site_compound_controls": ("site_compound_controls",),
    "alleys": ("alley_count", "alleys"),
    "alley_count": ("alley_count", "alleys"),
    "plazas": ("plaza_count", "plazas", "courtyard_count"),
    "plaza_count": ("plaza_count", "plazas", "courtyard_count"),
    "courtyard_count": ("courtyard_count", "plaza_count", "plazas"),
    "intersection_type": ("intersection_type", "junction_type", "network_type"),
    "landmark_count": ("landmark_count",),
    "placement_count": ("placement_count", "placement_instance_count"),
    "placement_index": ("placement_index",),
    "placement_rows": ("placement_rows", "placement_row_count"),
    "placement_columns": ("placement_columns", "placement_column_count"),
    "placement_elevation": ("placement_elevation",),
    "object_archetype": ("object_archetype", "archetype", "setpiece"),
    "setpiece": ("object_archetype", "archetype", "setpiece"),
    "setpiece_layout": ("setpiece_layout",),
    "setpiece_density": ("setpiece_density", "density"),
    "structure_count": ("structure_count", "building_count"),
    "building_count": ("building_count", "structure_count"),
    "road_segments": ("road_segment_count", "segments"),
    "road_segment_count": ("road_segment_count", "segments"),
    "access_count": ("access_count", "catwalk_count", "walkway_count"),
    "infrastructure_count": ("infrastructure_count", "pipe_count", "conduit_count"),
    "prop_count": ("prop_count", "scatter_count", "street_crate_count"),
    "actor_count": ("actor_count", "npc_count", "agent_count", "prop_count"),
    "npc_count": ("npc_count", "actor_count", "agent_count", "prop_count"),
    "agent_count": ("agent_count", "actor_count", "npc_count", "prop_count"),
    "spawn_point_count": ("spawn_point_count", "nest_count", "nests", "prop_count"),
    "population_per_spawn": ("population_per_spawn", "spawn_population"),
    "species_count": ("species_count", "spawn_species_count"),
    "faction_count": ("faction_count", "structure_count"),
    "loop_count": ("loop_count", "road_segment_count", "segments"),
    "event_count": ("event_count", "signal_count", "prop_count"),
    "channel_count": ("channel_count", "junction_box_count", "signal_count"),
    "state_count": ("state_count", "structure_count", "state_node_count"),
    "transition_count": ("transition_count", "road_segment_count", "connection_segment_count"),
    "condition_count": ("condition_count", "trigger_count", "sensor_count"),
    "trigger_count": ("trigger_count", "sensor_count", "platform_count"),
    "mutation_count": ("mutation_count", "structure_count", "prop_count"),
    "responder_count": ("responder_count", "actor_count", "npc_count"),
    "timeline_count": ("timeline_count", "sequence_count", "structure_count"),
    "clip_count": ("clip_count", "animation_clip_count", "beat_count", "prop_count"),
    "beat_count": ("beat_count", "clip_count", "animation_clip_count", "prop_count"),
    "pose_count": ("pose_count", "keyframe_count", "state_count"),
    "keyframe_count": ("keyframe_count", "pose_count", "state_count"),
    "moving_part_count": ("moving_part_count", "animated_part_count", "module_socket_count"),
    "animated_part_count": ("animated_part_count", "moving_part_count", "module_socket_count"),
    "phase_count": ("phase_count", "machine_phase_count", "clip_count"),
    "vfx_count": ("vfx_count", "effect_count", "light_count"),
    "sound_count": ("sound_count", "cue_count", "prop_count"),
    "physics_body_count": ("physics_body_count", "rigid_body_count", "body_count", "prop_count"),
    "rigid_body_count": ("rigid_body_count", "physics_body_count", "body_count"),
    "collider_count": ("collider_count", "colliders", "module_socket_count"),
    "joint_count": ("joint_count", "physics_joint_count", "hinge_count", "module_socket_count"),
    "physics_joint_count": ("physics_joint_count", "joint_count", "hinge_count"),
    "hinge_count": ("hinge_count", "joint_count", "physics_joint_count"),
    "constraint_count": ("constraint_count", "physics_constraint_count", "support_count"),
    "damage_state_count": ("damage_state_count", "state_count"),
    "debris_count": ("debris_count", "fragment_count", "prop_count"),
    "fragment_count": ("fragment_count", "debris_count", "prop_count"),
    "rope_count": ("rope_count", "cable_count", "support_count"),
    "cloth_panel_count": ("cloth_panel_count", "fabric_panel_count", "prop_count"),
    "force_field_count": ("force_field_count", "field_count", "vfx_count", "sensor_count"),
    "surface_layer_count": ("surface_layer_count", "layer_count", "material_layer_count"),
    "material_zone_count": ("material_zone_count", "zone_count", "material_slot_count"),
    "decal_count": ("decal_count", "marking_count", "story_mark_count"),
    "wear_pattern_count": ("wear_pattern_count", "wear_count", "scratch_count", "chip_count"),
    "damage_surface_count": ("damage_surface_count", "damage_mark_count", "crack_count", "scorch_count", "dent_count"),
    "crack_count": ("crack_count", "damage_surface_count"),
    "scratch_count": ("scratch_count", "wear_pattern_count", "damage_surface_count"),
    "scorch_count": ("scorch_count", "damage_surface_count"),
    "dent_count": ("dent_count", "damage_surface_count"),
    "surface_transition_count": ("surface_transition_count", "transition_band_count", "band_count"),
    "weather_system_count": ("weather_system_count", "weather_count", "environment_effect_count"),
    "weather_count": ("weather_count", "weather_system_count", "environment_effect_count"),
    "atmosphere_count": ("atmosphere_count", "sky_layer_count", "weather_system_count"),
    "wind_zone_count": ("wind_zone_count", "gust_count", "weather_system_count"),
    "liquid_body_count": ("liquid_body_count", "water_body_count", "puddle_count"),
    "puddle_count": ("puddle_count", "liquid_body_count", "wetness_zone_count"),
    "fire_source_count": ("fire_source_count", "fire_count", "light_count"),
    "fire_count": ("fire_count", "fire_source_count", "light_count"),
    "smoke_emitter_count": ("smoke_emitter_count", "smoke_count", "mist_volume_count"),
    "smoke_count": ("smoke_count", "smoke_emitter_count"),
    "mist_volume_count": ("mist_volume_count", "mist_count", "fog_volume_count"),
    "mist_count": ("mist_count", "mist_volume_count"),
    "wetness_zone_count": ("wetness_zone_count", "wet_surface_count", "puddle_count"),
    "heat_haze_count": ("heat_haze_count", "heat_count", "fire_source_count"),
    "time_of_day_count": ("time_of_day_count", "lighting_state_count", "atmosphere_count"),
    "environment_effect_count": ("environment_effect_count", "weather_count", "vfx_count"),
    "shot_count": ("shot_count", "camera_count", "cutscene_beat_count"),
    "shot_sequence_count": ("shot_sequence_count", "sequence_count", "timeline_count"),
    "camera_rail_count": ("camera_rail_count", "camera_path_count", "rail_count"),
    "camera_path_count": ("camera_path_count", "camera_rail_count", "path_count"),
    "look_at_target_count": ("look_at_target_count", "focus_target_count", "target_count"),
    "focal_zone_count": ("focal_zone_count", "focus_zone_count", "camera_volume_count"),
    "cutscene_beat_count": ("cutscene_beat_count", "beat_count", "shot_count"),
    "orbit_camera_count": ("orbit_camera_count", "camera_count"),
    "inspection_camera_count": ("inspection_camera_count", "camera_count"),
    "focus_pull_count": ("focus_pull_count", "focal_zone_count"),
    "camera_volume_count": ("camera_volume_count", "focal_zone_count"),
    "presentation_rig_count": ("presentation_rig_count", "camera_count", "shot_count"),
    "composition_guide_count": ("composition_guide_count", "focal_zone_count"),
    "camera_count": ("camera_count", "shot_count", "orbit_camera_count", "inspection_camera_count"),
    "ambient_bed_count": ("ambient_bed_count", "audio_count", "sound_count"),
    "sound_zone_count": ("sound_zone_count", "audio_count", "sound_count"),
    "reverb_space_count": ("reverb_space_count", "audio_count"),
    "acoustic_occluder_count": ("acoustic_occluder_count", "audio_count"),
    "sound_propagation_count": ("sound_propagation_count", "audio_count", "sound_count"),
    "music_state_count": ("music_state_count", "audio_count"),
    "music_transition_count": ("music_transition_count", "audio_count"),
    "stinger_count": ("stinger_count", "audio_count", "sound_count"),
    "foley_emitter_count": ("foley_emitter_count", "audio_count", "sound_count"),
    "audio_bus_count": ("audio_bus_count", "audio_count"),
    "listener_zone_count": ("listener_zone_count", "audio_count"),
    "acoustic_material_count": ("acoustic_material_count", "audio_count", "material_zone_count"),
    "audio_count": ("audio_count", "sound_count"),
    "interaction_prompt_count": ("interaction_prompt_count", "interaction_count"),
    "interaction_zone_count": ("interaction_zone_count", "interaction_count", "trigger_count"),
    "affordance_count": ("affordance_count", "interaction_count"),
    "usable_count": ("usable_count", "interaction_count"),
    "pickup_count": ("pickup_count", "interaction_count", "prop_count"),
    "inspect_point_count": ("inspect_point_count", "interaction_count"),
    "terminal_count": ("terminal_count", "interaction_count", "control_panel_count"),
    "control_panel_count": ("control_panel_count", "interaction_count", "button_count"),
    "switch_count": ("switch_count", "interaction_count", "button_count"),
    "lever_count": ("lever_count", "interaction_count", "button_count"),
    "button_count": ("button_count", "interaction_count"),
    "door_lock_count": ("door_lock_count", "interaction_count", "gate_count"),
    "quest_marker_count": ("quest_marker_count", "interaction_count", "map_marker_count"),
    "map_marker_count": ("map_marker_count", "interaction_count"),
    "diegetic_hud_count": ("diegetic_hud_count", "interaction_count", "ui_anchor_count"),
    "ui_anchor_count": ("ui_anchor_count", "interaction_count"),
    "interaction_count": ("interaction_count", "affordance_count"),
    "mission_count": ("mission_count", "quest_count", "objective_chain_count"),
    "objective_chain_count": ("objective_chain_count", "mission_count", "objective_count"),
    "success_condition_count": ("success_condition_count", "condition_count", "mission_count"),
    "failure_condition_count": ("failure_condition_count", "condition_count", "mission_count"),
    "reward_table_count": ("reward_table_count", "reward_count", "loot_table_count"),
    "loot_table_count": ("loot_table_count", "loot_count", "reward_table_count"),
    "inventory_slot_count": ("inventory_slot_count", "slot_count", "item_count"),
    "crafting_station_count": ("crafting_station_count", "recipe_count", "interaction_count"),
    "recipe_count": ("recipe_count", "crafting_station_count"),
    "shop_count": ("shop_count", "vendor_count", "stock_count"),
    "vendor_count": ("vendor_count", "shop_count", "npc_count"),
    "currency_count": ("currency_count", "reward_table_count", "economy_count"),
    "reputation_rule_count": ("reputation_rule_count", "faction_count"),
    "unlock_rule_count": ("unlock_rule_count", "progression_track_count"),
    "progression_track_count": ("progression_track_count", "level_count", "unlock_rule_count"),
    "gameplay_rule_count": ("gameplay_rule_count", "mission_count", "condition_count"),
    "director_count": ("director_count", "encounter_director_count"),
    "encounter_director_count": ("encounter_director_count", "director_count", "encounter_count"),
    "director_intent_count": ("director_intent_count", "director_count"),
    "pacing_curve_count": ("pacing_curve_count", "director_count", "encounter_beat_count"),
    "threat_budget_count": ("threat_budget_count", "director_count", "spawn_budget_count"),
    "spawn_wave_count": ("spawn_wave_count", "wave_count", "spawn_point_count"),
    "spawn_budget_count": ("spawn_budget_count", "threat_budget_count"),
    "combat_phase_count": ("combat_phase_count", "phase_count", "encounter_count"),
    "stealth_phase_count": ("stealth_phase_count", "phase_count", "encounter_count"),
    "escalation_rule_count": ("escalation_rule_count", "director_count", "gameplay_rule_count"),
    "adaptive_difficulty_count": ("adaptive_difficulty_count", "director_count", "difficulty_count"),
    "encounter_beat_count": ("encounter_beat_count", "beat_count", "pacing_curve_count"),
    "director_signal_count": ("director_signal_count", "signal_count", "event_count"),
    "threat_zone_count": ("threat_zone_count", "control_zone_count", "spawn_point_count"),
    "reinforcement_route_count": ("reinforcement_route_count", "route_count", "road_segment_count"),
    "simulation_layer_count": ("simulation_layer_count", "simulation_count", "field_count"),
    "simulation_count": ("simulation_count", "simulation_layer_count"),
    "field_count": ("field_count", "heat_field_count", "noise_field_count", "visibility_field_count"),
    "heat_field_count": ("heat_field_count", "field_count", "simulation_count"),
    "noise_field_count": ("noise_field_count", "field_count", "simulation_count"),
    "visibility_field_count": ("visibility_field_count", "field_count", "simulation_count"),
    "resource_flow_count": ("resource_flow_count", "flow_count", "field_count"),
    "faction_pressure_count": ("faction_pressure_count", "pressure_count", "faction_count"),
    "territory_influence_count": ("territory_influence_count", "territory_count", "control_zone_count"),
    "alarm_grid_count": ("alarm_grid_count", "sensor_grid_count", "director_signal_count"),
    "patrol_density_count": ("patrol_density_count", "patrol_count", "reinforcement_route_count"),
    "hazard_field_count": ("hazard_field_count", "hazard_count", "field_count"),
    "sensor_grid_count": ("sensor_grid_count", "sensor_count", "field_count"),
    "cover_map_count": ("cover_map_count", "cover_count", "field_count"),
    "flow_gate_count": ("flow_gate_count", "gate_count", "resource_flow_count"),
    "world_metric_count": ("world_metric_count", "metric_count", "simulation_count"),
    "metric_count": ("metric_count", "world_metric_count"),
    "simulation_probe_count": ("simulation_probe_count", "probe_count", "sample_count"),
    "probe_count": ("probe_count", "simulation_probe_count"),
    "culture_system_count": ("culture_system_count", "culture_count"),
    "culture_count": ("culture_count", "culture_system_count"),
    "law_code_count": ("law_code_count", "law_count", "policy_rule_count"),
    "policy_rule_count": ("policy_rule_count", "policy_count", "law_code_count"),
    "economy_model_count": ("economy_model_count", "economy_count", "trade_policy_count"),
    "trade_policy_count": ("trade_policy_count", "trade_count", "economy_model_count"),
    "diplomacy_state_count": ("diplomacy_state_count", "diplomacy_count", "social_relation_count"),
    "social_graph_count": ("social_graph_count", "social_relation_count"),
    "social_relation_count": ("social_relation_count", "relation_count", "social_graph_count"),
    "population_group_count": ("population_group_count", "group_count", "population_count"),
    "labor_system_count": ("labor_system_count", "labor_count", "job_count"),
    "ritual_calendar_count": ("ritual_calendar_count", "ritual_count", "festival_count"),
    "festival_count": ("festival_count", "ritual_count", "event_count"),
    "belief_system_count": ("belief_system_count", "belief_count", "cultural_marker_count"),
    "cultural_marker_count": ("cultural_marker_count", "marker_count", "symbol_count"),
    "civic_institution_count": ("civic_institution_count", "institution_count", "civic_count"),
    "culture_type": ("culture_type", "culture"),
    "laws": ("laws", "law_codes"),
    "policies": ("policies", "policy"),
    "economy_type": ("economy_type", "economy"),
    "trade_goods": ("trade_goods", "goods", "resources"),
    "partners": ("partners", "factions"),
    "relation_strength": ("relation_strength", "social_weight"),
    "population_groups": ("population_groups", "groups", "classes"),
    "jobs": ("jobs", "labor_roles"),
    "rituals": ("rituals", "calendar_events"),
    "festivals": ("festivals", "celebrations"),
    "beliefs": ("beliefs", "doctrines"),
    "markers": ("markers", "symbols"),
    "institutions": ("institutions", "civic_institutions"),
    "legitimacy": ("legitimacy",),
    "cohesion": ("cohesion",),
    "unrest": ("unrest",),
    "prosperity": ("prosperity",),
    "biome_system_count": ("biome_system_count", "biome_count", "ecology_count"),
    "biome_count": ("biome_count", "biome_system_count"),
    "habitat_zone_count": ("habitat_zone_count", "habitat_count"),
    "species_population_count": ("species_population_count", "species_count", "population_count"),
    "food_web_count": ("food_web_count", "ecology_count"),
    "predator_prey_link_count": ("predator_prey_link_count", "food_web_link_count"),
    "migration_route_count": ("migration_route_count", "migration_count", "route_count"),
    "nesting_site_count": ("nesting_site_count", "nest_count", "spawn_point_count"),
    "resource_patch_count": ("resource_patch_count", "patch_count", "resource_count"),
    "resource_regeneration_count": ("resource_regeneration_count", "regeneration_count", "growth_count"),
    "growth_cycle_count": ("growth_cycle_count", "growth_count", "cycle_count"),
    "weather_ecology_link_count": ("weather_ecology_link_count", "weather_link_count", "weather_system_count"),
    "ecological_pressure_count": ("ecological_pressure_count", "pressure_count", "hazard_field_count"),
    "ecology_type": ("ecology_type", "biome_type", "habitat"),
    "biome_type": ("biome_type", "ecology_type", "biome"),
    "habitats": ("habitats", "habitat_zones", "zones"),
    "species": ("species", "fauna", "creatures"),
    "flora": ("flora", "producers"),
    "producers": ("producers", "flora"),
    "predators": ("predators", "hunters"),
    "prey": ("prey", "grazers"),
    "resources": ("resources", "resource_patches", "food_sources"),
    "regeneration_rate": ("regeneration_rate", "rate"),
    "carrying_capacity": ("carrying_capacity", "capacity"),
    "birth_rate": ("birth_rate",),
    "mortality_rate": ("mortality_rate",),
    "migration_season": ("migration_season", "season"),
    "growth_stages": ("growth_stages", "stages"),
    "cycle_duration": ("cycle_duration", "duration"),
    "weather_sensitivity": ("weather_sensitivity", "sensitivity"),
    "pressure_type": ("pressure_type", "pressure"),
    "pressure_sources": ("pressure_sources", "sources", "causes"),
    "land_use_plan_count": ("land_use_plan_count", "land_use_count"),
    "land_use_count": ("land_use_count", "land_use_plan_count"),
    "farm_plot_count": ("farm_plot_count", "farm_count", "crop_count"),
    "hunting_ground_count": ("hunting_ground_count", "hunting_count"),
    "fishing_ground_count": ("fishing_ground_count", "fishing_count"),
    "grazing_range_count": ("grazing_range_count", "grazing_count", "livestock_count"),
    "extraction_site_count": ("extraction_site_count", "extraction_count"),
    "pollution_source_count": ("pollution_source_count", "pollution_count", "ecological_pressure_count"),
    "conservation_zone_count": ("conservation_zone_count", "conservation_count"),
    "restoration_project_count": ("restoration_project_count", "restoration_count"),
    "scarcity_loop_count": ("scarcity_loop_count", "scarcity_count"),
    "settlement_pressure_count": ("settlement_pressure_count", "pressure_count"),
    "resource_claim_count": ("resource_claim_count", "claim_count"),
    "harvest_cycle_count": ("harvest_cycle_count", "harvest_count", "growth_cycle_count"),
    "carrying_capacity_rule_count": ("carrying_capacity_rule_count", "capacity_rule_count", "world_metric_count"),
    "biome_impact_count": ("biome_impact_count", "impact_count", "ecological_pressure_count"),
    "land_uses": ("land_uses", "uses", "programs"),
    "crops": ("crops", "crop_types", "food_crops"),
    "livestock": ("livestock", "herds", "grazers"),
    "yield_rate": ("yield_rate",),
    "harvest_rate": ("harvest_rate",),
    "extraction_rate": ("extraction_rate", "rate"),
    "pollution_rate": ("pollution_rate", "rate"),
    "mitigation": ("mitigation",),
    "protections": ("protections", "conservation_targets", "protected_species"),
    "scarcity": ("scarcity", "deficit"),
    "demand": ("demand",),
    "supply": ("supply",),
    "resource_claims": ("resource_claims", "resources"),
    "land_owner": ("land_owner", "owner", "faction"),
    "settlement": ("settlement", "settlement_name"),
    "biome": ("biome", "biome_type"),
    "impact_type": ("impact_type", "impact"),
    "impact_score": ("impact_score", "impact"),
    "supply_chain_count": ("supply_chain_count", "chain_count", "logistics_count"),
    "logistics_hub_count": ("logistics_hub_count", "hub_count"),
    "storage_depot_count": ("storage_depot_count", "depot_count", "storage_count"),
    "stockpile_count": ("stockpile_count", "inventory_count"),
    "input_buffer_count": ("input_buffer_count", "buffer_count"),
    "output_buffer_count": ("output_buffer_count", "buffer_count"),
    "processing_stage_count": ("processing_stage_count", "processing_count", "stage_count"),
    "refinery_stage_count": ("refinery_stage_count", "refinery_count"),
    "workshop_stage_count": ("workshop_stage_count", "workshop_count"),
    "assembly_stage_count": ("assembly_stage_count", "assembly_count"),
    "market_node_count": ("market_node_count", "market_count"),
    "demand_sink_count": ("demand_sink_count", "demand_count"),
    "supply_route_count": ("supply_route_count", "route_count"),
    "transport_leg_count": ("transport_leg_count", "transport_count"),
    "bottleneck_count": ("bottleneck_count", "constraint_count"),
    "throughput_rule_count": ("throughput_rule_count", "throughput_count"),
    "failure_mode_count": ("failure_mode_count", "failure_count"),
    "production_strategy_count": ("production_strategy_count", "strategy_count"),
    "production_priority_count": ("production_priority_count", "priority_count"),
    "quota_rule_count": ("quota_rule_count", "quota_count"),
    "allocation_rule_count": ("allocation_rule_count", "allocation_count"),
    "rationing_policy_count": ("rationing_policy_count", "rationing_count", "scarcity_loop_count"),
    "strategic_reserve_count": ("strategic_reserve_count", "reserve_count", "stockpile_count"),
    "trade_embargo_count": ("trade_embargo_count", "embargo_count", "diplomacy_state_count"),
    "sabotage_target_count": ("sabotage_target_count", "sabotage_count", "failure_mode_count"),
    "maintenance_plan_count": ("maintenance_plan_count", "maintenance_count"),
    "repair_schedule_count": ("repair_schedule_count", "repair_count", "world_metric_count"),
    "mobilization_order_count": ("mobilization_order_count", "mobilization_count"),
    "production_mode_count": ("production_mode_count", "mode_count"),
    "wartime_production_count": ("wartime_production_count", "wartime_count"),
    "peacetime_production_count": ("peacetime_production_count", "peacetime_count"),
    "procurement_contract_count": ("procurement_contract_count", "procurement_count", "contract_count"),
    "readiness_level_count": ("readiness_level_count", "readiness_count", "world_metric_count"),
    "conflict_system_count": ("conflict_system_count", "conflict_count"),
    "strategic_objective_count": ("strategic_objective_count", "objective_count"),
    "war_plan_count": ("war_plan_count", "conflict_count"),
    "battlefront_count": ("battlefront_count", "front_count"),
    "escalation_ladder_count": ("escalation_ladder_count", "escalation_count"),
    "treaty_count": ("treaty_count", "diplomacy_count"),
    "ceasefire_count": ("ceasefire_count", "treaty_count"),
    "alliance_count": ("alliance_count", "diplomacy_count"),
    "rival_claim_count": ("rival_claim_count", "resource_claim_count"),
    "diplomatic_demand_count": ("diplomatic_demand_count", "demand_count"),
    "negotiation_channel_count": ("negotiation_channel_count", "diplomacy_count"),
    "sanction_count": ("sanction_count", "sanctions_count", "trade_embargo_count"),
    "espionage_cell_count": ("espionage_cell_count", "espionage_count"),
    "covert_operation_count": ("covert_operation_count", "covert_count", "sabotage_target_count"),
    "disaster_response_count": ("disaster_response_count", "disaster_count"),
    "emergency_order_count": ("emergency_order_count", "emergency_count", "policy_rule_count"),
    "faction_ai_count": ("faction_ai_count", "ai_count"),
    "doctrine_model_count": ("doctrine_model_count", "doctrine_count"),
    "goal_stack_count": ("goal_stack_count", "goal_count", "strategic_objective_count"),
    "threat_model_count": ("threat_model_count", "threat_count"),
    "perception_feed_count": ("perception_feed_count", "perception_count", "sensor_grid_count"),
    "decision_rule_count": ("decision_rule_count", "decision_count", "policy_rule_count"),
    "policy_selector_count": ("policy_selector_count", "selector_count", "policy_count"),
    "action_option_count": ("action_option_count", "option_count"),
    "response_plan_count": ("response_plan_count", "response_count"),
    "escalation_choice_count": ("escalation_choice_count", "escalation_count"),
    "deescalation_choice_count": ("deescalation_choice_count", "deescalation_count"),
    "resource_strategy_count": ("resource_strategy_count", "resource_count", "production_strategy_count"),
    "logistics_priority_count": ("logistics_priority_count", "logistics_count", "supply_chain_count"),
    "diplomatic_posture_count": ("diplomatic_posture_count", "diplomacy_count"),
    "contingency_plan_count": ("contingency_plan_count", "contingency_count"),
    "adaptive_order_count": ("adaptive_order_count", "adaptive_count"),
    "operational_plan_count": ("operational_plan_count", "operational_count"),
    "order_queue_count": ("order_queue_count", "queue_count", "order_count"),
    "world_order_count": ("world_order_count", "order_count"),
    "patrol_order_count": ("patrol_order_count", "patrol_count"),
    "convoy_order_count": ("convoy_order_count", "convoy_count"),
    "construction_order_count": ("construction_order_count", "construction_count"),
    "repair_order_count": ("repair_order_count", "repair_count"),
    "relief_order_count": ("relief_order_count", "relief_count"),
    "mission_order_count": ("mission_order_count", "mission_count"),
    "scheduled_action_count": ("scheduled_action_count", "schedule_count", "timer_count"),
    "task_assignment_count": ("task_assignment_count", "assignment_count"),
    "crew_roster_count": ("crew_roster_count", "crew_count"),
    "convoy_route_count": ("convoy_route_count", "route_count", "supply_route_count"),
    "construction_queue_count": ("construction_queue_count", "queue_count"),
    "repair_crew_count": ("repair_crew_count", "crew_count", "repair_count"),
    "relief_team_count": ("relief_team_count", "team_count", "relief_count"),
    "settlement_evolution_count": ("settlement_evolution_count", "evolution_count"),
    "growth_phase_count": ("growth_phase_count", "growth_count", "phase_count"),
    "expansion_zone_count": ("expansion_zone_count", "expansion_count", "zone_count"),
    "construction_stage_count": ("construction_stage_count", "stage_count"),
    "upgrade_plan_count": ("upgrade_plan_count", "upgrade_count"),
    "district_upgrade_count": ("district_upgrade_count", "upgrade_count"),
    "building_upgrade_count": ("building_upgrade_count", "upgrade_count"),
    "infrastructure_upgrade_count": ("infrastructure_upgrade_count", "upgrade_count"),
    "material_delivery_count": ("material_delivery_count", "delivery_count"),
    "staffing_plan_count": ("staffing_plan_count", "staffing_count"),
    "occupancy_plan_count": ("occupancy_plan_count", "occupancy_count"),
    "worksite_count": ("worksite_count",),
    "build_permit_count": ("build_permit_count", "permit_count"),
    "damage_repair_plan_count": ("damage_repair_plan_count", "repair_count"),
    "demolition_plan_count": ("demolition_plan_count", "demolition_count"),
    "renovation_project_count": ("renovation_project_count", "renovation_count"),
    "city_plan_count": ("city_plan_count", "city_planning_count"),
    "zoning_rule_count": ("zoning_rule_count", "zoning_count"),
    "zoning_district_count": ("zoning_district_count", "zoning_count", "district_count"),
    "parcel_grid_count": ("parcel_grid_count", "parcel_count"),
    "land_parcel_count": ("land_parcel_count", "parcel_count", "lot_count"),
    "parcel_subdivision_count": ("parcel_subdivision_count", "subdivision_count"),
    "block_plan_count": ("block_plan_count", "block_count"),
    "street_hierarchy_count": ("street_hierarchy_count", "street_count", "road_count"),
    "transit_node_count": ("transit_node_count", "transit_count"),
    "civic_service_plan_count": ("civic_service_plan_count", "service_plan_count", "civic_count"),
    "service_coverage_count": ("service_coverage_count", "coverage_count"),
    "utility_corridor_count": ("utility_corridor_count", "corridor_count", "utility_count"),
    "district_site_plan_count": ("district_site_plan_count", "district_site_count"),
    "street_crossing_count": ("street_crossing_count", "crossing_count", "crosswalk_count"),
    "perimeter_plan_count": ("perimeter_plan_count", "perimeter_count"),
    "security_gate_count": ("security_gate_count", "gate_count"),
    "landscape_zone_count": ("landscape_zone_count", "landscape_count", "green_count"),
    "traffic_flow_count": ("traffic_flow_count", "traffic_count", "route_count"),
    "service_flow_count": ("service_flow_count", "service_route_count", "utility_route_count"),
    "access_sequence_count": ("access_sequence_count", "access_transition_count", "entry_sequence_count"),
    "public_entry_count": ("public_entry_count", "entry_count", "entries"),
    "service_entry_count": ("service_entry_count", "service_door_count", "service_entries"),
    "threshold_transition_count": ("threshold_transition_count", "threshold_count", "door_opening_count"),
    "entry_lobby_count": ("entry_lobby_count", "lobby_count", "room_program_count"),
    "access_checkpoint_count": ("access_checkpoint_count", "checkpoint_count", "security_gate_count"),
    "loading_path_count": ("loading_path_count", "loading_route_count", "loading_count"),
    "wayfinding_node_count": ("wayfinding_node_count", "signage_count", "map_marker_count"),
    "circulation_core_count": ("circulation_core_count", "circulation_count", "vertical_access_count"),
    "stair_run_count": ("stair_run_count", "stair_count", "stairs"),
    "elevator_bank_count": ("elevator_bank_count", "elevator_count", "lift_count"),
    "egress_route_count": ("egress_route_count", "exit_route_count", "egress_count"),
    "emergency_exit_count": ("emergency_exit_count", "exit_count", "door_opening_count"),
    "corridor_spine_count": ("corridor_spine_count", "corridor_count", "corridor_link_count"),
    "floor_transition_count": ("floor_transition_count", "transition_count", "vertical_route_count"),
    "public_circulation_count": ("public_circulation_count", "public_route_count"),
    "service_circulation_count": ("service_circulation_count", "service_route_count"),
    "stair_detail_count": ("stair_detail_count",),
    "tread_pattern_count": ("tread_pattern_count", "tread_pattern"),
    "landing_platform_count": ("landing_platform_count", "landing_count", "platform_count"),
    "handrail_run_count": ("handrail_run_count", "handrail_count", "guardrail_count"),
    "corridor_shell_count": ("corridor_shell_count",),
    "door_rhythm_count": ("door_rhythm_count", "door_bay_count"),
    "ceiling_service_grid_count": ("ceiling_service_grid_count", "ceiling_grid_count", "service_connection_count"),
    "egress_surface_plan_count": ("egress_surface_plan_count", "egress_surface_count"),
    "room_route_binding_count": ("room_route_binding_count", "room_connection_count"),
    "power_grid_count": ("power_grid_count", "power_count", "grid_count"),
    "substation_count": ("substation_count", "power_node_count"),
    "transformer_bank_count": ("transformer_bank_count", "transformer_count"),
    "power_line_count": ("power_line_count", "line_count"),
    "water_network_count": ("water_network_count", "water_count"),
    "pump_station_count": ("pump_station_count", "pump_count"),
    "water_tower_count": ("water_tower_count", "tower_count", "storage_count"),
    "sewer_network_count": ("sewer_network_count", "sewer_count", "drain_count"),
    "treatment_plant_count": ("treatment_plant_count", "treatment_count", "plant_count"),
    "data_network_count": ("data_network_count", "data_count"),
    "data_hub_count": ("data_hub_count", "hub_count"),
    "fiber_line_count": ("fiber_line_count", "fiber_count", "line_count"),
    "transit_line_count": ("transit_line_count", "transit_count", "line_count"),
    "transit_station_count": ("transit_station_count", "station_count", "transit_node_count"),
    "service_connection_count": ("service_connection_count", "connection_count", "service_tap_count"),
    "maintenance_access_count": ("maintenance_access_count", "access_count", "walkway_count"),
    "building_service_plan_count": ("building_service_plan_count", "building_service_count", "service_plan_count"),
    "service_core_count": ("service_core_count", "core_count"),
    "utility_room_count": ("utility_room_count", "utility_count"),
    "mechanical_room_count": ("mechanical_room_count", "mechanical_count"),
    "electrical_panel_count": ("electrical_panel_count", "panel_count"),
    "meter_bank_count": ("meter_bank_count", "meter_count"),
    "plumbing_stack_count": ("plumbing_stack_count", "riser_count", "pipe_count"),
    "hvac_system_count": ("hvac_system_count", "hvac_count"),
    "ventilation_duct_count": ("ventilation_duct_count", "duct_count"),
    "elevator_core_count": ("elevator_core_count", "elevator_count"),
    "service_elevator_count": ("service_elevator_count", "elevator_count", "lift_count"),
    "service_shaft_count": ("service_shaft_count", "shaft_count"),
    "fire_suppression_count": ("fire_suppression_count", "sprinkler_zone_count"),
    "sprinkler_zone_count": ("sprinkler_zone_count", "sprinkler_count"),
    "waste_chute_count": ("waste_chute_count", "chute_count"),
    "loading_dock_count": ("loading_dock_count", "dock_count", "dock_bay_count"),
    "room_program_count": ("room_program_count", "room_count", "functional_room_count"),
    "bathroom_count": ("bathroom_count", "wet_room_count"),
    "kitchen_count": ("kitchen_count", "galley_count"),
    "lab_room_count": ("lab_room_count", "lab_count"),
    "med_bay_count": ("med_bay_count", "medical_bay_count"),
    "workshop_room_count": ("workshop_room_count", "workshop_count"),
    "control_room_count": ("control_room_count", "operations_room_count"),
    "storage_room_count": ("storage_room_count", "storage_count"),
    "office_room_count": ("office_room_count", "office_count"),
    "bedroom_count": ("bedroom_count", "sleeping_room_count"),
    "fixture_cluster_count": ("fixture_cluster_count", "fixture_count"),
    "appliance_bank_count": ("appliance_bank_count", "appliance_count"),
    "workstation_cluster_count": ("workstation_cluster_count", "workstation_count"),
    "cabinet_wall_count": ("cabinet_wall_count", "cabinet_count"),
    "counter_run_count": ("counter_run_count", "counter_count"),
    "sanitary_fixture_count": ("sanitary_fixture_count", "fixture_count", "sink_count"),
    "lab_bench_count": ("lab_bench_count", "bench_count", "counter_count"),
    "medical_bed_count": ("medical_bed_count", "bed_count"),
    "tool_rack_count": ("tool_rack_count", "rack_count", "tool_count"),
    "room_adjacency_count": ("room_adjacency_count", "adjacency_pair_count"),
    "room_connection_count": ("room_connection_count", "connection_count"),
    "door_opening_count": ("door_opening_count", "opening_count", "door_count"),
    "corridor_link_count": ("corridor_link_count", "corridor_count", "route_count"),
    "wall_run_count": ("wall_run_count", "wall_count", "partition_count"),
    "room_socket_count": ("room_socket_count", "socket_count"),
    "fixture_socket_count": ("fixture_socket_count", "socket_count", "fixture_count"),
    "socket_binding_count": ("socket_binding_count", "binding_count"),
    "fixture_placement_count": ("fixture_placement_count", "fixture_count", "placement_count"),
    "furniture_placement_count": ("furniture_placement_count", "furniture_count", "placement_count"),
    "service_placement_count": ("service_placement_count", "service_connection_count", "placement_count"),
    "wall_attachment_count": ("wall_attachment_count", "attach_count"),
    "anchor_rule_count": ("anchor_rule_count", "anchor_count"),
    "placement_constraint_count": ("placement_constraint_count", "constraint_count"),
    "auto_layout_count": ("auto_layout_count",),
    "room_layout_plan_count": ("room_layout_plan_count", "room_layout_count"),
    "fixture_layout_count": ("fixture_layout_count",),
    "furniture_layout_count": ("furniture_layout_count",),
    "service_layout_count": ("service_layout_count",),
    "wall_fixture_layout_count": ("wall_fixture_layout_count", "wall_layout_count"),
    "layout_zone_count": ("layout_zone_count", "zone_count"),
    "layout_socket_count": ("layout_socket_count", "socket_count"),
    "auto_placed_count": ("auto_placed_count", "placement_count"),
    "layout_solver_count": ("layout_solver_count",),
    "room_bounds_count": ("room_bounds_count", "bounds_count"),
    "wall_side_rule_count": ("wall_side_rule_count", "wall_rule_count"),
    "socket_priority_count": ("socket_priority_count", "priority_count"),
    "clearance_zone_count": ("clearance_zone_count", "clearance_count"),
    "layout_slot_count": ("layout_slot_count", "slot_count"),
    "resolved_slot_count": ("resolved_slot_count",),
    "blocked_slot_count": ("blocked_slot_count",),
    "wall_side_count": ("wall_side_count", "wall_count"),
    "priority_socket_count": ("priority_socket_count",),
    "footprint_packer_count": ("footprint_packer_count",),
    "placement_footprint_count": ("placement_footprint_count", "footprint_count"),
    "occupancy_grid_count": ("occupancy_grid_count", "grid_count"),
    "fit_profile_count": ("fit_profile_count", "fit_count"),
    "collision_rule_count": ("collision_rule_count", "collision_count"),
    "service_reach_count": ("service_reach_count", "service_count"),
    "footprint_count": ("footprint_count", "placement_footprint_count"),
    "occupied_cell_count": ("occupied_cell_count", "blocked_cell_count"),
    "free_cell_count": ("free_cell_count", "available_cell_count"),
    "packed_item_count": ("packed_item_count", "packed_count"),
    "collision_pair_count": ("collision_pair_count",),
    "room_packing_solver_count": ("room_packing_solver_count",),
    "packing_slot_count": ("packing_slot_count",),
    "packed_transform_count": ("packed_transform_count", "resolved_transform_count"),
    "clearance_reservation_count": ("clearance_reservation_count",),
    "service_anchor_map_count": ("service_anchor_map_count",),
    "resolved_transform_count": ("resolved_transform_count", "packed_transform_count"),
    "blocked_transform_count": ("blocked_transform_count",),
    "service_anchor_count": ("service_anchor_count",),
    "room_content_plan_count": ("room_content_plan_count",),
    "content_family_binding_count": ("content_family_binding_count",),
    "furniture_asset_count": ("furniture_asset_count",),
    "fixture_asset_count": ("fixture_asset_count",),
    "packed_child_asset_count": ("packed_child_asset_count",),
    "generated_child_asset_count": ("generated_child_asset_count",),
    "content_family_count": ("content_family_count",),
    "content_surface_plan_count": ("content_surface_plan_count",),
    "content_material_zone_count": ("content_material_zone_count",),
    "content_finish_preset_count": ("content_finish_preset_count",),
    "content_wear_profile_count": ("content_wear_profile_count",),
    "content_marking_set_count": ("content_marking_set_count",),
    "content_surface_zone_count": ("content_surface_zone_count",),
    "content_decal_count": ("content_decal_count",),
    "room_pack_preset_count": ("room_pack_preset_count",),
    "footprint_size_preset_count": ("footprint_size_preset_count",),
    "packing_policy_preset_count": ("packing_policy_preset_count",),
    "clearance_preset_count": ("clearance_preset_count",),
    "service_reach_preset_count": ("service_reach_preset_count",),
    "role_item_set_count": ("role_item_set_count",),
    "preset_item_count": ("preset_item_count",),
    "role_preset_count": ("role_preset_count",),
    "policy_rule_count": ("policy_rule_count",),
    "building_envelope_count": ("building_envelope_count",),
    "floor_stack_count": ("floor_stack_count",),
    "facade_grid_count": ("facade_grid_count",),
    "facade_bay_count": ("facade_bay_count", "window_bay_count"),
    "roof_profile_count": ("roof_profile_count",),
    "vertical_core_count": ("vertical_core_count", "core_count"),
    "entrance_plan_count": ("entrance_plan_count",),
    "floor_plate_count": ("floor_plate_count",),
    "room_stack_count": ("room_stack_count",),
    "facade_side_count": ("facade_side_count", "wall_side_count"),
    "window_bay_count": ("window_bay_count", "facade_bay_count"),
    "site_compound_count": ("site_compound_count",),
    "building_lot_count": ("building_lot_count", "lot_count"),
    "courtyard_plan_count": ("courtyard_plan_count", "courtyard_count"),
    "pedestrian_path_count": ("pedestrian_path_count", "path_count", "walkway_count"),
    "service_alley_count": ("service_alley_count", "alley_count"),
    "parking_zone_count": ("parking_zone_count", "parking_count"),
    "loading_zone_count": ("loading_zone_count", "loading_count", "dock_count"),
    "exterior_utility_count": ("exterior_utility_count", "utility_count"),
    "site_building_count": ("site_building_count", "building_count", "structure_count"),
    "site_route_count": ("site_route_count", "route_count"),
    "public_space_plan_count": ("public_space_plan_count", "public_space_count", "park_count"),
    "growth_boundary_count": ("growth_boundary_count", "boundary_count"),
    "district_dependency_count": ("district_dependency_count", "dependency_count"),
    "development_pressure_count": ("development_pressure_count", "pressure_count"),
    "climate_zone_count": ("climate_zone_count", "climate_count", "biome_system_count"),
    "climate_risk_map_count": ("climate_risk_map_count", "risk_map_count"),
    "flood_risk_count": ("flood_risk_count", "flood_count", "hazard_count"),
    "fire_risk_count": ("fire_risk_count", "fire_count", "hazard_count"),
    "heat_risk_count": ("heat_risk_count", "heat_count", "hazard_count"),
    "resource_constraint_count": ("resource_constraint_count", "constraint_count", "scarcity_loop_count"),
    "protected_land_count": ("protected_land_count", "protected_count", "conservation_zone_count"),
    "green_infrastructure_count": ("green_infrastructure_count", "green_count"),
    "stormwater_system_count": ("stormwater_system_count", "stormwater_count"),
    "cooling_corridor_count": ("cooling_corridor_count", "cooling_count"),
    "evacuation_route_count": ("evacuation_route_count", "evacuation_count", "route_count"),
    "emergency_shelter_count": ("emergency_shelter_count", "shelter_count"),
    "resilience_plan_count": ("resilience_plan_count", "resilience_count"),
    "climate_adaptation_count": ("climate_adaptation_count", "adaptation_count"),
    "transit_oriented_growth_count": ("transit_oriented_growth_count", "transit_growth_count"),
    "risk_mitigation_count": ("risk_mitigation_count", "mitigation_count"),
    "phases": ("phases", "growth_phases", "stages"),
    "growth_phases": ("growth_phases", "phases", "stages"),
    "zones": ("zones", "expansion_zones", "districts"),
    "expansion_zones": ("expansion_zones", "zones", "districts"),
    "projects": ("projects", "upgrades", "buildings"),
    "upgrades": ("upgrades", "projects"),
    "materials": ("materials", "materials_required", "construction_materials", "resources_required"),
    "materials_required": ("materials_required", "materials", "construction_materials", "resources_required"),
    "construction_materials": ("construction_materials", "materials", "materials_required"),
    "staff_roles": ("staff_roles", "crews", "teams", "workers"),
    "occupants": ("occupants", "occupancy", "population_groups"),
    "occupancy": ("occupancy", "occupants", "population_groups"),
    "capacity": ("capacity", "occupancy_capacity"),
    "damage_level": ("damage_level", "damage"),
    "repair_priority": ("repair_priority", "priority"),
    "demolition_reason": ("demolition_reason", "reason"),
    "renovation_theme": ("renovation_theme", "theme"),
    "permit_state": ("permit_state",),
    "inspection_state": ("inspection_state",),
    "build_progress": ("build_progress", "progress", "completion"),
    "upgrade_level": ("upgrade_level",),
    "construction_style": ("construction_style", "style"),
    "districts": ("districts", "zones", "expansion_zones"),
    "buildings": ("buildings", "projects", "upgrades"),
    "city_blocks": ("city_blocks", "blocks"),
    "zoning_districts": ("zoning_districts", "zones", "districts"),
    "zoning": ("zoning", "zone_type"),
    "density": ("density", "allowed_density"),
    "allowed_uses": ("allowed_uses", "uses"),
    "parcel_count": ("parcel_count", "land_parcel_count", "lot_count"),
    "parcels": ("parcels", "lots", "land_parcels"),
    "lots": ("lots", "parcels", "land_parcels"),
    "subdivision_pattern": ("subdivision_pattern", "parcel_pattern"),
    "block_count": ("block_count", "block_plan_count"),
    "blocks": ("blocks", "city_blocks"),
    "street_levels": ("street_levels", "road_types", "roads"),
    "road_types": ("road_types", "street_levels", "roads"),
    "transit_modes": ("transit_modes", "modes"),
    "services": ("services", "civic_services", "utilities"),
    "civic_services": ("civic_services", "services"),
    "coverage_radius": ("coverage_radius", "radius"),
    "coverage_threshold": ("coverage_threshold", "service_threshold"),
    "utilities": ("utilities", "services", "corridors"),
    "corridors": ("corridors", "utility_corridors"),
    "district_site_plan": ("district_site_plan",),
    "street_crossing": ("street_crossing",),
    "perimeter_plan": ("perimeter_plan",),
    "security_gate": ("security_gate",),
    "landscape_zone": ("landscape_zone",),
    "traffic_flow": ("traffic_flow",),
    "service_flow": ("service_flow",),
    "district_site_profile": ("district_site_profile", "site_layout_profile"),
    "district_compounds": ("district_compounds", "site_compounds", "compounds"),
    "district_blocks": ("district_blocks", "blocks"),
    "street_crossings": ("street_crossings", "crossings", "crosswalks"),
    "perimeter_segments": ("perimeter_segments",),
    "security_gates": ("security_gates", "gates"),
    "landscape_zones": ("landscape_zones", "landscape"),
    "traffic_routes": ("traffic_routes", "traffic_flows"),
    "service_routes": ("service_routes", "service_flows"),
    "district_site_controls": ("district_site_controls",),
    "access_sequence": ("access_sequence",),
    "public_entry": ("public_entry",),
    "service_entry": ("service_entry",),
    "threshold_transition": ("threshold_transition",),
    "entry_lobby": ("entry_lobby",),
    "access_checkpoint": ("access_checkpoint",),
    "loading_path": ("loading_path",),
    "wayfinding_node": ("wayfinding_node",),
    "access_transition_profile": ("access_transition_profile",),
    "entry_points": ("entry_points", "public_entries"),
    "public_entries": ("public_entries", "entry_points"),
    "service_entry_points": ("service_entry_points", "service_entries"),
    "thresholds": ("thresholds", "threshold_transitions"),
    "lobby_zones": ("lobby_zones", "lobbies"),
    "checkpoint_nodes": ("checkpoint_nodes", "checkpoints"),
    "loading_routes": ("loading_routes", "loading_paths"),
    "wayfinding_nodes": ("wayfinding_nodes", "signage_nodes", "map_nodes"),
    "access_transition_controls": ("access_transition_controls",),
    "circulation_core": ("circulation_core",),
    "stair_run": ("stair_run",),
    "elevator_bank": ("elevator_bank",),
    "egress_route": ("egress_route",),
    "emergency_exit": ("emergency_exit",),
    "corridor_spine": ("corridor_spine",),
    "floor_transition": ("floor_transition",),
    "public_circulation": ("public_circulation",),
    "service_circulation": ("service_circulation",),
    "stair_detail": ("stair_detail",),
    "tread_pattern": ("tread_pattern",),
    "landing_platform": ("landing_platform",),
    "handrail_run": ("handrail_run",),
    "corridor_shell": ("corridor_shell",),
    "door_rhythm": ("door_rhythm",),
    "ceiling_service_grid": ("ceiling_service_grid",),
    "egress_surface_plan": ("egress_surface_plan",),
    "room_route_binding": ("room_route_binding",),
    "circulation_profile": ("circulation_profile",),
    "circulation_detail_profile": ("circulation_detail_profile", "detail_profile"),
    "circulation_floors": ("circulation_floors", "served_floor_labels"),
    "served_floor_labels": ("served_floor_labels", "circulation_floors"),
    "stair_runs": ("stair_runs", "stairs"),
    "elevator_banks": ("elevator_banks", "elevators"),
    "egress_routes": ("egress_routes", "exit_routes"),
    "emergency_exits": ("emergency_exits", "exits"),
    "corridor_spines": ("corridor_spines", "corridors"),
    "floor_transitions": ("floor_transitions", "transitions"),
    "public_routes": ("public_routes", "visitor_routes"),
    "service_circulation_routes": ("service_circulation_routes", "service_routes"),
    "circulation_controls": ("circulation_controls",),
    "circulation_detail_controls": ("circulation_detail_controls",),
    "tread_count": ("tread_count", "treads"),
    "riser_count": ("riser_count", "risers"),
    "landing_count": ("landing_count", "landings"),
    "handrail_count": ("handrail_count", "handrails"),
    "corridor_wall_count": ("corridor_wall_count", "wall_count"),
    "door_bay_count": ("door_bay_count", "door_bays"),
    "ceiling_grid_count": ("ceiling_grid_count", "service_grid_count"),
    "egress_surface_zones": ("egress_surface_zones", "surface_zones"),
    "room_route_targets": ("room_route_targets", "route_rooms"),
    "public_spaces": ("public_spaces", "parks", "plazas"),
    "parks": ("parks", "public_spaces"),
    "boundary_type": ("boundary_type", "growth_boundary"),
    "growth_limit": ("growth_limit",),
    "dependencies": ("dependencies", "dependency_rules", "district_dependencies"),
    "dependency_rules": ("dependency_rules", "dependencies", "district_dependencies"),
    "pressure_sources": ("pressure_sources", "drivers"),
    "pressure_level": ("pressure_level", "development_pressure"),
    "climate_zones": ("climate_zones", "zones", "biomes"),
    "hazards": ("hazards", "risk_types", "risks"),
    "risk_types": ("risk_types", "hazards", "risks"),
    "flood_level": ("flood_level", "flood"),
    "fire_level": ("fire_level", "fire"),
    "heat_level": ("heat_level", "heat"),
    "stormwater_capacity": ("stormwater_capacity", "capacity"),
    "canopy_cover": ("canopy_cover", "tree_canopy"),
    "resilience_score": ("resilience_score", "score"),
    "adaptation_measures": ("adaptation_measures", "mitigation_actions", "measures"),
    "evacuation_routes": ("evacuation_routes", "routes"),
    "shelters": ("shelters", "emergency_shelters"),
    "protected_areas": ("protected_areas", "protected_land"),
    "resource_limits": ("resource_limits", "resources", "constraints"),
    "transit_growth": ("transit_growth", "growth"),
    "mitigation_actions": ("mitigation_actions", "adaptation_measures", "measures"),
    "network_nodes": ("network_nodes", "nodes", "service_nodes", "route_nodes"),
    "line_segments": ("line_segments", "segments", "connection_segment_count"),
    "service_nodes": ("service_nodes", "network_nodes", "nodes"),
    "service_taps": ("service_taps", "tap_count", "service_connection_count"),
    "substations": ("substations", "substation_count", "power_nodes"),
    "voltage": ("voltage",),
    "redundancy": ("redundancy",),
    "pressure": ("pressure",),
    "storage_capacity": ("storage_capacity", "capacity"),
    "pump_capacity": ("pump_capacity", "capacity"),
    "treatment_capacity": ("treatment_capacity", "capacity"),
    "trunk_count": ("trunk_count", "fiber_line_count"),
    "station_spacing": ("station_spacing", "spacing"),
    "ridership": ("ridership", "usage"),
    "stations": ("stations", "stops", "network_nodes"),
    "stops": ("stops", "stations", "network_nodes"),
    "served_floors": ("served_floors", "floors", "floor_count"),
    "rooms_served": ("rooms_served", "room_count", "rooms"),
    "service_load": ("service_load", "load"),
    "service_zones": ("service_zones", "zones", "rooms"),
    "circuits": ("circuits", "circuit_count"),
    "circuit_count": ("circuit_count", "circuits"),
    "risers": ("risers", "riser_count"),
    "riser_count": ("riser_count", "risers"),
    "panels": ("panels", "panel_count"),
    "panel_count": ("panel_count", "panels"),
    "meters": ("meters", "meter_count"),
    "meter_count": ("meter_count", "meters"),
    "vents": ("vents", "vent_count"),
    "vent_count": ("vent_count", "vents"),
    "shafts": ("shafts", "shaft_count"),
    "shaft_count": ("shaft_count", "shafts"),
    "cars": ("cars", "car_count", "elevator_count"),
    "car_count": ("car_count", "cars", "elevator_count"),
    "dock_bays": ("dock_bays", "dock_bay_count", "loading_dock_count"),
    "dock_bay_count": ("dock_bay_count", "dock_bays", "loading_dock_count"),
    "sprinkler_density": ("sprinkler_density", "coverage"),
    "fire_rating": ("fire_rating", "rating"),
    "waste_capacity": ("waste_capacity", "capacity"),
    "airflow": ("airflow", "flow_rate"),
    "chain_count": ("chain_count", "supply_chain_count"),
    "logistics_count": ("logistics_count", "supply_chain_count"),
    "processors": ("processors", "stages"),
    "depots": ("depots", "storage_depots"),
    "markets": ("markets", "market_nodes"),
    "sinks": ("sinks", "demand_sinks"),
    "routes": ("routes", "supply_routes", "transport_routes"),
    "transport_modes": ("transport_modes", "modes", "mode"),
    "inventory": ("inventory", "stock"),
    "throughput": ("throughput", "throughput_rate", "rate"),
    "throughput_rate": ("throughput_rate", "throughput", "rate"),
    "latency": ("latency",),
    "loss_rate": ("loss_rate",),
    "failure_rate": ("failure_rate",),
    "recovery_time": ("recovery_time",),
    "batch_size": ("batch_size",),
    "source_nodes": ("source_nodes", "sources", "from_nodes"),
    "sink_nodes": ("sink_nodes", "sinks", "to_nodes"),
    "priorities": ("priorities", "production_priorities"),
    "quotas": ("quotas", "quota", "goods"),
    "allocations": ("allocations", "allocation", "goods"),
    "reserve_goods": ("reserve_goods", "goods", "resources"),
    "reserve_ratio": ("reserve_ratio", "reserve"),
    "rationing": ("rationing",),
    "ration_rate": ("ration_rate",),
    "embargo_targets": ("embargo_targets", "embargoes", "targets"),
    "sabotage_targets": ("sabotage_targets", "targets", "facilities"),
    "maintenance_targets": ("maintenance_targets", "repair_targets", "facilities"),
    "repair_interval": ("repair_interval",),
    "mobilization_level": ("mobilization_level", "mobilization"),
    "production_modes": ("production_modes", "modes", "mode"),
    "readiness": ("readiness", "readiness_level"),
    "readiness_threshold": ("readiness_threshold",),
    "procurement_sources": ("procurement_sources", "suppliers", "sources"),
    "contracts": ("contracts", "procurement_contracts"),
    "strategic_goal": ("strategic_goal", "strategy"),
    "war_state": ("war_state",),
    "peace_focus": ("peace_focus", "production_focus"),
    "factions": ("factions", "belligerents", "rivals", "sides"),
    "belligerents": ("belligerents", "factions", "sides"),
    "allies": ("allies", "partners", "coalition"),
    "rivals": ("rivals", "enemies", "factions"),
    "objectives": ("objectives", "strategic_objectives", "goals"),
    "fronts": ("fronts", "battlefronts", "theaters", "zones"),
    "treaty_terms": ("treaty_terms", "terms", "clauses"),
    "ceasefire_terms": ("ceasefire_terms", "terms", "conditions"),
    "diplomatic_demands": ("diplomatic_demands", "demands", "terms"),
    "negotiation_terms": ("negotiation_terms", "terms", "agenda"),
    "sanction_targets": ("sanction_targets", "targets", "rivals"),
    "intelligence_targets": ("intelligence_targets", "targets", "facilities"),
    "operations": ("operations", "covert_operations", "targets"),
    "disaster_type": ("disaster_type", "disaster"),
    "disaster_zones": ("disaster_zones", "zones", "regions"),
    "response_teams": ("response_teams", "teams"),
    "emergency_level": ("emergency_level", "severity"),
    "escalation_steps": ("escalation_steps", "steps", "phases"),
    "escalation_level": ("escalation_level", "escalation", "pressure"),
    "deescalation": ("deescalation", "relief"),
    "casus_belli": ("casus_belli", "claim"),
    "doctrine": ("doctrine", "ai_type"),
    "goals": ("goals", "objectives", "strategic_goals"),
    "threats": ("threats", "risks", "rivals"),
    "signals": ("signals", "inputs", "perception_signals"),
    "policies": ("policies", "policy_options", "response_modes"),
    "options": ("options", "actions", "action_options"),
    "response_modes": ("response_modes", "policies"),
    "risk_tolerance": ("risk_tolerance", "risk"),
    "aggression": ("aggression",),
    "caution": ("caution",),
    "utility_weights": ("utility_weights", "weights"),
    "decision_threshold": ("decision_threshold", "threshold"),
    "memory_horizon": ("memory_horizon",),
    "adaptation_rate": ("adaptation_rate",),
    "policy_bias": ("policy_bias",),
    "fallback_policy": ("fallback_policy",),
    "orders": ("orders", "world_orders", "tasks"),
    "tasks": ("tasks", "assignments", "work_items"),
    "crews": ("crews", "teams", "assignees"),
    "crew_size": ("crew_size",),
    "teams": ("teams", "crews"),
    "assignees": ("assignees", "crews"),
    "schedule": ("schedule",),
    "start_time": ("start_time",),
    "duration": ("duration",),
    "deadline": ("deadline",),
    "repeat": ("repeat",),
    "priority_level": ("priority_level", "priority"),
    "queue_policy": ("queue_policy",),
    "completion": ("completion", "progress"),
    "progress": ("progress", "completion"),
    "worksites": ("worksites", "sites"),
    "patrols": ("patrols", "routes"),
    "convoys": ("convoys", "routes"),
    "missions": ("missions", "objectives"),
    "resources_required": ("resources_required", "resources"),
    "supplies": ("supplies", "goods"),
    "dock_count": ("dock_count", "pier_count"),
    "vehicles": ("vehicle_count", "vehicles"),
    "vehicle_count": ("vehicle_count", "vehicles"),
    "boats": ("boat_count", "boats"),
    "boat_count": ("boat_count", "boats"),
    "machines": ("machine_count", "machines"),
    "machine_count": ("machine_count", "machines"),
    "interior_modules": ("interior_module_count", "interior_count", "room_count"),
    "interior_module_count": ("interior_module_count", "interior_count", "room_count"),
    "furniture_clusters": ("furniture_cluster_count", "furniture_count"),
    "furniture_cluster_count": ("furniture_cluster_count", "furniture_count"),
    "foliage_clusters": ("foliage_cluster_count", "foliage_count"),
    "foliage_cluster_count": ("foliage_cluster_count", "foliage_count"),
    "child_sockets": ("child_socket_count", "module_socket_count"),
    "child_socket_count": ("child_socket_count", "module_socket_count"),
    "child_module_count": ("child_module_count", "module_slot_count"),
    "module_slot_count": ("module_slot_count", "child_module_count"),
    "vehicle_slot_count": ("vehicle_slot_count", "vehicle_count"),
    "boat_slot_count": ("boat_slot_count", "boat_count"),
    "machine_slot_count": ("machine_slot_count", "machine_count"),
    "interior_slot_count": ("interior_slot_count", "interior_module_count", "interior_count"),
    "furniture_slot_count": ("furniture_slot_count", "furniture_cluster_count", "furniture_count"),
    "foliage_slot_count": ("foliage_slot_count", "foliage_cluster_count", "foliage_count"),
    "vehicle_module": ("vehicle_module", "vehicle_template", "vehicle_archetype"),
    "vehicle_modules": ("vehicle_modules", "vehicle_module_templates"),
    "boat_module": ("boat_module", "boat_template", "boat_archetype"),
    "boat_modules": ("boat_modules", "boat_module_templates"),
    "machine_module": ("machine_module", "machine_template", "machine_archetype"),
    "machine_modules": ("machine_modules", "machine_module_templates"),
    "interior_module": ("interior_module", "interior_template", "interior_archetype"),
    "interior_modules_list": ("interior_modules", "interior_module_templates"),
    "furniture_module": ("furniture_module", "furniture_template", "furniture_archetype"),
    "furniture_modules": ("furniture_modules", "furniture_module_templates"),
    "foliage_module": ("foliage_module", "foliage_template", "foliage_archetype"),
    "foliage_modules": ("foliage_modules", "foliage_module_templates"),
    "child_module_template": ("child_module_template",),
    "apron_count": ("apron_count",),
}
_CHILD_MODULE_KINDS = ("vehicle", "boat", "machine", "interior", "furniture", "foliage", "generic")
_CHILD_MODULE_MAPPING_KEYS = {
    "child_modules",
    "module_overrides",
    "slot_modules",
    "module_templates",
}
_CHILD_MODULE_CONTROL_MAP_KEYS = {
    "child_module_controls",
    "module_controls",
    "slot_controls",
}
_CHILD_MODULE_POSITION_MAP_KEYS = {
    "slot_positions",
    "module_positions",
    "child_module_positions",
}
_CHILD_MODULE_FACING_MAP_KEYS = {
    "slot_facing",
    "slot_facings",
    "module_facing",
    "child_module_facing",
}
_CHILD_MODULE_CLEARANCE_MAP_KEYS = {
    "slot_clearances",
    "module_clearances",
    "child_module_clearances",
}
_CHILD_MODULE_DIRECT_KEYS = {
    "child_module_template",
    "child_module_count",
    "child_socket_count",
    "module_slot_count",
    "module_socket_count",
}
_ASSEMBLY_SURFACE_ZONES: dict[str, dict[str, str]] = {
    "rack": {
        "assembly_anchor": "industrial_steel",
        "assembly_slot": "hazard_paint",
        "rack_socket": "bare_metal",
        "weapon_mount": "hazard_paint",
        "rack_clamp": "bare_metal",
        "rack_label": "warning_paint",
    },
    "docking_bay": {
        "assembly_anchor": "weathered_steel",
        "assembly_slot": "warning_paint",
        "mooring": "rope",
        "dock": "deck_wood",
        "mooring_line": "rope",
        "fender": "rubber",
    },
    "parking": {
        "assembly_anchor": "concrete",
        "assembly_slot": "warning_paint",
        "parking_bay": "lane_paint",
        "service_mount": "industrial_steel",
        "wheel_chock": "rubber",
        "tie_down": "bare_metal",
    },
    "hangar": {
        "assembly_anchor": "concrete",
        "assembly_slot": "hazard_paint",
        "hangar_bay": "warning_paint",
        "service_mount": "industrial_steel",
        "wheel_chock": "rubber",
        "tie_down": "bare_metal",
        "service_umbilical": "emissive_panel",
    },
    "room_layout": {
        "assembly_anchor": "wood",
        "assembly_slot": "trim_paint",
        "floor_grid": "wood",
        "wall_mount": "painted_plaster",
        "floor_pad": "rubber",
        "wall_bracket": "brushed_metal",
    },
    "machine_line": {
        "assembly_anchor": "industrial_steel",
        "assembly_slot": "hazard_paint",
        "base_mount": "industrial_steel",
        "service_mount": "warning_paint",
    },
    "site_plan": {
        "assembly_anchor": "concrete",
        "assembly_slot": "painted_stone",
        "lot_socket": "concrete",
        "road_socket": "asphalt",
    },
    "terrain_cluster": {
        "assembly_anchor": "soil",
        "assembly_slot": "moss",
        "terrain_anchor": "stone",
        "root_socket": "soil",
    },
    "route_network": {
        "assembly_anchor": "asphalt",
        "assembly_slot": "lane_paint",
        "road_start": "lane_paint",
        "road_end": "lane_paint",
        "road_coupler": "warning_paint",
        "route_socket": "lane_paint",
    },
    "access_chain": {
        "assembly_anchor": "industrial_steel",
        "assembly_slot": "warning_paint",
        "walkway_start": "warning_paint",
        "walkway_end": "warning_paint",
        "access_coupler": "warning_paint",
        "alignment_brace": "industrial_steel",
    },
    "utility_run": {
        "assembly_anchor": "industrial_steel",
        "assembly_slot": "hazard_paint",
        "pipe_start": "bare_metal",
        "pipe_end": "bare_metal",
        "conduit_start": "industrial_steel",
        "conduit_end": "industrial_steel",
    },
    "convoy": {
        "assembly_anchor": "painted_metal",
        "assembly_slot": "hazard_paint",
        "convoy_link": "bare_metal",
    },
}
_PROCEDURAL_SURFACE_DEFAULTS: dict[str, dict[str, Any]] = {
    "procedural_building": {
        "materials": ["painted_stone", "glass", "roof_tile", "trim_paint", "canvas", "brushed_metal", "emissive_panel"],
        "material_layers": ["painted_stone", "trim_paint", "dust", "roof_tile"],
        "story_decals": ["address_plate", "window_grime", "shop_sign", "roof_service_mark"],
        "wear_story": "used",
        "wear_level": 0.28,
        "zones": {
            "window": "glass",
            "roof": "roof_tile",
            "door": "trim_paint",
            "column": "painted_stone",
            "balcony": "trim_paint",
            "awning": "canvas",
            "cornice": "trim_paint",
            "tower": "painted_stone",
            "chimney": "stone",
            "dormer": "glass",
            "arch": "painted_stone",
            "parapet": "trim_paint",
            "signage": "emissive_panel",
            "equipment": "brushed_metal",
            "fire_escape": "brushed_metal",
            "service": "trim_paint",
        },
    },
    "procedural_vehicle": {
        "materials": ["painted_metal", "rubber", "glass", "bare_metal", "industrial_steel", "hazard_paint", "emissive_panel"],
        "material_layers": ["painted_metal", "bare_metal", "rubber", "dust", "hazard_paint"],
        "story_decals": ["unit_number", "paint_chips", "socket_labels"],
        "wear_story": "field_used",
        "wear_level": 0.35,
        "zones": {
            "wheel": "rubber",
            "track": "rubber",
            "suspension": "industrial_steel",
            "cabin": "glass",
            "engine": "bare_metal",
            "chassis": "painted_metal",
            "cargo": "painted_metal",
            "turret": "industrial_steel",
            "wing": "painted_metal",
            "rotor": "bare_metal",
            "arm": "industrial_steel",
            "crew": "glass",
            "cockpit": "glass",
            "payload": "painted_metal",
            "bay": "painted_metal",
            "hardpoint": "hazard_paint",
            "socket": "hazard_paint",
            "thruster": "bare_metal",
            "stabilizer": "painted_metal",
            "sensor": "emissive_panel",
            "antenna": "bare_metal",
        },
    },
    "procedural_weapon": {
        "materials": ["gunmetal", "bare_metal", "polymer", "leather", "edge_steel", "optic_glass", "emissive_panel", "hazard_paint"],
        "material_layers": ["gunmetal", "bare_metal", "polymer", "edge_wear"],
        "story_decals": ["serial_mark", "edge_wear", "grip_scuff", "rail_index_marks"],
        "wear_story": "field_used",
        "wear_level": 0.34,
        "zones": {
            "barrel": "gunmetal",
            "blade": "edge_steel",
            "tip": "edge_steel",
            "grip": "leather",
            "guard": "bare_metal",
            "stock": "polymer",
            "magazine": "gunmetal",
            "sight": "optic_glass",
            "trigger": "bare_metal",
            "head": "edge_steel",
            "rail": "bare_metal",
            "hardpoint": "hazard_paint",
            "socket": "hazard_paint",
            "muzzle": "gunmetal",
            "ammo": "gunmetal",
            "bay": "polymer",
            "power": "emissive_panel",
            "cell": "emissive_panel",
            "sling": "leather",
            "stabilizer": "bare_metal",
            "sensor": "optic_glass",
        },
    },
    "procedural_boat": {
        "materials": [
            "marine_paint",
            "deck_wood",
            "weathered_steel",
            "sailcloth",
            "rope",
            "brass",
            "warning_paint",
            "emissive_panel",
            "rubber",
            "salt_wear",
        ],
        "material_layers": ["marine_paint", "deck_wood", "salt_wear", "rope", "warning_paint"],
        "story_decals": ["waterline_wear", "hull_number", "salt_streaks", "deck_scuff", "mission_socket_labels"],
        "wear_story": "field_used",
        "wear_level": 0.42,
        "zones": {
            "hull": "marine_paint",
            "keel": "marine_paint",
            "deck": "deck_wood",
            "cabin": "deck_wood",
            "mast": "weathered_steel",
            "sail": "sailcloth",
            "canvas": "sailcloth",
            "rigging": "rope",
            "pontoon": "marine_paint",
            "float": "rubber",
            "outrigger": "deck_wood",
            "cargo": "deck_wood",
            "hold": "deck_wood",
            "railing": "weathered_steel",
            "rudder": "marine_paint",
            "propeller": "brass",
            "anchor": "weathered_steel",
            "engine": "weathered_steel",
            "crew": "glass",
            "bridge": "glass",
            "payload": "deck_wood",
            "bay": "deck_wood",
            "hardpoint": "warning_paint",
            "socket": "warning_paint",
            "thruster": "brass",
            "stabilizer": "marine_paint",
            "sensor": "emissive_panel",
            "antenna": "weathered_steel",
            "cleat": "brass",
        },
    },
    "procedural_machine": {
        "materials": ["industrial_steel", "bare_metal", "rubber", "hazard_paint", "emissive_panel"],
        "material_layers": ["industrial_steel", "bare_metal", "grease", "hazard_paint"],
        "story_decals": ["hazard_stripe", "service_number", "oil_stain"],
        "wear_story": "field_used",
        "wear_level": 0.46,
        "zones": {
            "base": "industrial_steel",
            "column": "industrial_steel",
            "arm": "bare_metal",
            "hydraulic": "bare_metal",
            "piston": "bare_metal",
            "conveyor": "rubber",
            "gear": "bare_metal",
            "tank": "industrial_steel",
            "crane": "hazard_paint",
            "tool": "bare_metal",
            "light": "emissive_panel",
        },
    },
    "procedural_road": {
        "materials": ["asphalt", "lane_paint", "concrete", "warning_paint", "brushed_metal"],
        "material_layers": ["asphalt", "dust", "lane_paint", "concrete"],
        "story_decals": ["lane_marker", "edge_wear", "stop_bar", "crosswalk_wear"],
        "wear_story": "field_used",
        "wear_level": 0.45,
        "zones": {
            "road": "asphalt",
            "lane": "lane_paint",
            "sidewalk": "concrete",
            "junction": "asphalt",
            "branch": "asphalt",
            "crosswalk": "lane_paint",
            "turnout": "edge_gravel",
            "median": "concrete",
            "curb": "concrete",
            "ramp": "concrete",
            "stop": "lane_paint",
            "arrow": "lane_paint",
            "bike": "lane_paint",
            "parking": "lane_paint",
            "streetlight": "brushed_metal",
            "bollard": "warning_paint",
        },
    },
    "procedural_bridge": {
        "materials": ["weathered_steel", "concrete", "warning_paint"],
        "material_layers": ["weathered_steel", "concrete", "warning_paint"],
        "story_decals": ["warning_stripe", "span_numbers"],
        "wear_story": "field_used",
        "wear_level": 0.38,
        "zones": {"bridge": "weathered_steel", "railing": "warning_paint", "pier": "concrete"},
    },
    "procedural_terrain": {
        "materials": ["soil", "stone", "moss", "shallow_water"],
        "material_layers": ["soil", "stone", "moss"],
        "story_decals": ["trail_scuff", "moss_patch", "ground_mottle"],
        "wear_story": "weathered",
        "wear_level": 0.50,
        "zones": {"terrain": "soil", "cliff": "stone", "ridge": "stone", "path": "soil", "terrace": "moss", "water": "shallow_water", "clearing": "moss", "platform": "worn_stone"},
    },
    "procedural_city_block": {
        "materials": ["concrete", "asphalt", "glass", "roof_tile", "painted_stone", "lane_paint", "trim_paint", "brushed_metal"],
        "material_layers": ["concrete", "asphalt", "glass", "urban_grime", "lane_paint"],
        "story_decals": ["street_lines", "lot_numbers", "window_grime"],
        "wear_story": "field_used",
        "wear_level": 0.40,
        "zones": {
            "road": "asphalt",
            "street": "asphalt",
            "lot": "concrete",
            "building": "painted_stone",
            "roof": "roof_tile",
            "window": "glass",
            "door": "trim_paint",
            "sidewalk": "concrete",
            "alley": "asphalt",
            "plaza": "concrete",
            "crosswalk": "lane_paint",
            "streetlight": "brushed_metal",
        },
    },
    "procedural_interior": {
        "materials": ["painted_plaster", "wood", "glass", "emissive_panel"],
        "material_layers": ["painted_plaster", "wood", "dust"],
        "story_decals": ["scuff_marks", "room_label"],
        "wear_story": "used",
        "wear_level": 0.30,
        "zones": {
            "floor": "wood",
            "window": "glass",
            "door": "wood",
            "column": "painted_plaster",
            "corridor": "wood",
            "partition": "painted_plaster",
            "alcove": "painted_plaster",
            "stair": "wood",
            "light": "emissive_panel",
            "furniture": "wood",
            "table": "wood",
            "chair": "wood",
            "bed": "wood",
            "shelf": "wood",
            "cabinet": "wood",
            "counter": "wood",
            "lamp": "emissive_panel",
        },
    },
    "procedural_furniture": {
        "materials": ["finished_wood", "upholstery_fabric", "leather", "brushed_metal", "laminate", "glass", "emissive_panel"],
        "material_layers": ["finished_wood", "edge_wear", "upholstery_fabric", "dust"],
        "story_decals": ["edge_scuff", "seat_wear", "drawer_label"],
        "wear_story": "used",
        "wear_level": 0.26,
        "zones": {
            "base": "finished_wood",
            "seat": "upholstery_fabric",
            "back": "upholstery_fabric",
            "chair": "finished_wood",
            "leg": "brushed_metal",
            "table": "finished_wood",
            "desk": "finished_wood",
            "bed": "finished_wood",
            "mattress": "upholstery_fabric",
            "shelf": "finished_wood",
            "cabinet": "finished_wood",
            "drawer": "finished_wood",
            "cushion": "upholstery_fabric",
            "counter": "laminate",
            "workbench": "finished_wood",
            "appliance": "brushed_metal",
            "fixture": "brushed_metal",
            "lamp": "brushed_metal",
            "light": "emissive_panel",
        },
    },
    "procedural_foliage": {
        "materials": ["soil", "bark", "leaf_litter", "moss", "short_grass", "stone", "fungus", "flower_petal", "terracotta"],
        "material_layers": ["soil", "bark", "leaf_litter", "moss"],
        "story_decals": ["leaf_litter", "moss_patch", "bark_scars", "soil_mottle"],
        "wear_story": "weathered",
        "wear_level": 0.38,
        "zones": {
            "ground": "soil",
            "terrain": "soil",
            "trunk": "bark",
            "bark": "bark",
            "branch": "bark",
            "root": "bark",
            "canopy": "leaf_litter",
            "leaf": "leaf_litter",
            "bush": "leaf_litter",
            "grass": "short_grass",
            "rock": "stone",
            "stone": "stone",
            "mushroom": "fungus",
            "fungus": "fungus",
            "log": "bark",
            "vine": "moss",
            "flower": "flower_petal",
            "petal": "flower_petal",
            "planter": "terracotta",
            "pot": "terracotta",
        },
    },
    "procedural_urban_prop": {
        "materials": [
            "painted_metal",
            "weathered_steel",
            "concrete",
            "asphalt",
            "finished_wood",
            "recycled_plastic",
            "canvas",
            "glass",
            "emissive_panel",
            "warning_paint",
        ],
        "material_layers": ["painted_metal", "urban_grime", "edge_wear", "warning_paint"],
        "story_decals": ["street_grime", "sticker_residue", "service_number", "warning_stripe"],
        "wear_story": "field_used",
        "wear_level": 0.42,
        "zones": {
            "urban": "concrete",
            "base": "concrete",
            "sidewalk": "concrete",
            "curb": "concrete",
            "fence": "painted_metal",
            "gate": "painted_metal",
            "sign": "painted_metal",
            "signage": "painted_metal",
            "streetlight": "weathered_steel",
            "streetlamp": "weathered_steel",
            "light": "emissive_panel",
            "bench": "finished_wood",
            "seat": "finished_wood",
            "trash": "recycled_plastic",
            "bin": "recycled_plastic",
            "utility": "weathered_steel",
            "pole": "weathered_steel",
            "cable": "weathered_steel",
            "wire": "weathered_steel",
            "kiosk": "painted_metal",
            "stall": "finished_wood",
            "market": "finished_wood",
            "canopy": "canvas",
            "awning": "canvas",
            "window": "glass",
            "barrier": "warning_paint",
            "barricade": "warning_paint",
            "crate": "finished_wood",
            "bollard": "warning_paint",
        },
    },
    "procedural_infrastructure": {
        "materials": [
            "galvanized_steel",
            "cast_iron",
            "concrete",
            "painted_metal",
            "warning_paint",
            "rubber_gasket",
            "utility_plastic",
            "cable_insulation",
            "urban_grime",
        ],
        "material_layers": ["galvanized_steel", "urban_grime", "edge_wear", "warning_paint"],
        "story_decals": ["service_number", "flow_arrow", "warning_stripe", "maintenance_grime"],
        "wear_story": "field_used",
        "wear_level": 0.46,
        "zones": {
            "infrastructure": "concrete",
            "base": "concrete",
            "service": "galvanized_steel",
            "pipe": "galvanized_steel",
            "pipeline": "galvanized_steel",
            "duct": "galvanized_steel",
            "vent": "galvanized_steel",
            "drain": "cast_iron",
            "channel": "cast_iron",
            "hydrant": "warning_paint",
            "transformer": "painted_metal",
            "substation": "painted_metal",
            "rail": "galvanized_steel",
            "conduit": "galvanized_steel",
            "cable": "cable_insulation",
            "wire": "cable_insulation",
            "junction": "utility_plastic",
            "box": "utility_plastic",
            "valve": "warning_paint",
            "manhole": "cast_iron",
            "cover": "cast_iron",
            "support": "galvanized_steel",
            "bracket": "galvanized_steel",
            "tray": "galvanized_steel",
        },
    },
    "procedural_access": {
        "materials": [
            "galvanized_steel",
            "safety_grate",
            "warning_paint",
            "rubber_tread",
            "concrete",
            "glass",
            "emissive_panel",
            "urban_grime",
        ],
        "material_layers": ["galvanized_steel", "edge_wear", "urban_grime", "warning_paint"],
        "story_decals": ["step_wear", "safety_stripe", "route_arrow", "maintenance_label"],
        "wear_story": "field_used",
        "wear_level": 0.44,
        "zones": {
            "access": "concrete",
            "base": "concrete",
            "catwalk": "safety_grate",
            "deck": "safety_grate",
            "walkway": "safety_grate",
            "span": "galvanized_steel",
            "guardrail": "warning_paint",
            "railing": "warning_paint",
            "ladder": "galvanized_steel",
            "rung": "rubber_tread",
            "ramp": "rubber_tread",
            "gantry": "galvanized_steel",
            "frame": "galvanized_steel",
            "elevator": "painted_metal",
            "lift": "painted_metal",
            "shaft": "galvanized_steel",
            "platform": "safety_grate",
            "tunnel": "concrete",
            "corridor": "concrete",
            "scaffold": "galvanized_steel",
            "gate": "warning_paint",
            "support": "galvanized_steel",
            "column": "galvanized_steel",
            "light": "emissive_panel",
            "window": "glass",
        },
    },
    "procedural_setpiece": {
        "materials": [
            "concrete",
            "asphalt",
            "painted_metal",
            "weathered_steel",
            "glass",
            "safety_grate",
            "warning_paint",
            "urban_grime",
        ],
        "material_layers": ["concrete", "painted_metal", "edge_wear", "urban_grime"],
        "story_decals": ["wayfinding_mark", "service_number", "route_arrow", "district_mark"],
        "wear_story": "field_used",
        "wear_level": 0.44,
        "zones": {
            "setpiece": "concrete",
            "base": "concrete",
            "terrain": "concrete",
            "building": "painted_metal",
            "roof": "weathered_steel",
            "window": "glass",
            "road": "asphalt",
            "route": "asphalt",
            "access": "safety_grate",
            "walkway": "safety_grate",
            "catwalk": "safety_grate",
            "utility": "weathered_steel",
            "pipe": "weathered_steel",
            "conduit": "weathered_steel",
            "prop": "painted_metal",
            "perimeter": "warning_paint",
            "gate": "warning_paint",
            "tower": "painted_metal",
            "dock": "weathered_steel",
            "apron": "concrete",
            "courtyard": "concrete",
            "ritual": "polished_stone",
            "vehicle": "painted_metal",
            "chassis": "painted_metal",
            "wheel": "rubber",
            "boat": "marine_paint",
            "hull": "marine_paint",
            "machine": "industrial_steel",
            "conveyor": "rubber_tread",
            "interior": "painted_plaster",
            "furniture": "finished_wood",
            "foliage": "moss",
            "socket": "weathered_steel",
        },
    },
}
_PROCEDURAL_INTERFACE_DEFAULTS: dict[str, dict[str, tuple[str, ...]]] = {
    "procedural_building": {
        "sockets": ("entry_door", "roof_mount", "window_grid", "side_wall_left", "side_wall_right", "balcony_mount", "tower_mount", "chimney_mount"),
        "anchors": ("floor_contact", "room_origin", "facade_center", "roof_center", "tower_axis"),
    },
    "procedural_vehicle": {
        "sockets": ("front_mount", "rear_mount", "roof_mount", "wheel_left", "wheel_right", "track_left", "track_right", "turret_mount", "cargo_bay", "rotor_mount", "wing_mount", "arm_mount"),
        "anchors": ("ground_contact", "cabin_center", "tow_point", "chassis_center", "payload_center"),
    },
    "procedural_weapon": {
        "sockets": ("muzzle", "underbarrel_mount", "optic_mount", "stock_mount", "blade_socket", "tool_head_socket"),
        "anchors": ("grip_center", "balance_point", "muzzle_axis", "blade_axis"),
    },
    "procedural_boat": {
        "sockets": (
            "bow_mount",
            "stern_mount",
            "deck_mount",
            "mast_socket",
            "sail_halyard",
            "rigging_tie",
            "cargo_hold",
            "pontoon_mount",
            "outrigger_mount",
            "rudder_mount",
            "propeller_shaft",
            "anchor_roller",
        ),
        "anchors": ("waterline", "deck_center", "hull_center", "keel_line", "mast_axis", "stern_drive_axis"),
    },
    "procedural_machine": {
        "sockets": ("base_mount", "arm_mount", "tool_mount", "conveyor_start", "conveyor_end", "tank_port", "crane_hook"),
        "anchors": ("machine_origin", "work_envelope", "control_side", "service_panel"),
    },
    "procedural_road": {
        "sockets": ("road_start", "road_end", "sidewalk_left", "sidewalk_right", "junction_north", "junction_south", "junction_east", "junction_west"),
        "anchors": ("lane_center", "surface_mount", "ground_contact", "intersection_center", "branch_origin"),
    },
    "procedural_bridge": {
        "sockets": ("bridge_start", "bridge_end", "rail_left", "rail_right", "pier_mounts"),
        "anchors": ("deck_center", "span_center", "foundation_contact"),
    },
    "procedural_terrain": {
        "sockets": ("path_start", "path_end", "cliff_edge", "platform_mount"),
        "anchors": ("ground_origin", "highest_point", "traversal_center"),
    },
    "procedural_city_block": {
        "sockets": ("north_road", "south_road", "east_road", "west_road", "lot_grid"),
        "anchors": ("block_center", "street_center", "lot_origin"),
    },
    "procedural_interior": {
        "sockets": ("entry", "window_wall", "floor_grid", "ceiling_mount", "corridor_start", "corridor_end", "partition_opening"),
        "anchors": ("room_origin", "floor_center", "door_center", "corridor_axis", "stair_core"),
    },
    "procedural_furniture": {
        "sockets": (
            "floor_contact",
            "seat_mount",
            "tabletop_mount",
            "drawer_pull",
            "shelf_slot",
            "counter_edge",
            "appliance_port",
            "lamp_socket",
        ),
        "anchors": ("floor_contact", "seat_center", "table_center", "bed_center", "storage_face", "work_surface"),
    },
    "procedural_foliage": {
        "sockets": (
            "ground_contact",
            "root_socket",
            "trunk_socket",
            "branch_socket",
            "canopy_socket",
            "vine_attach",
            "planter_insert",
            "scatter_origin",
        ),
        "anchors": ("ground_contact", "trunk_axis", "canopy_center", "root_spread", "scatter_center"),
    },
    "procedural_urban_prop": {
        "sockets": (
            "ground_contact",
            "fence_join_left",
            "fence_join_right",
            "gate_hinge",
            "sign_face",
            "lamp_socket",
            "bench_mount",
            "bin_mount",
            "utility_wire_start",
            "utility_wire_end",
            "kiosk_service_face",
            "stall_counter",
            "barrier_join",
            "bollard_line",
        ),
        "anchors": ("ground_contact", "street_edge", "sidewalk_center", "sign_face", "utility_axis", "market_front"),
    },
    "procedural_infrastructure": {
        "sockets": (
            "ground_contact",
            "pipe_start",
            "pipe_end",
            "duct_start",
            "duct_end",
            "conduit_start",
            "conduit_end",
            "drain_inlet",
            "drain_outlet",
            "junction_port",
            "transformer_port",
            "valve_mount",
            "service_rail_mount",
            "cable_tray_start",
            "cable_tray_end",
        ),
        "anchors": ("ground_contact", "service_center", "network_axis", "maintenance_access", "junction_center"),
    },
    "procedural_access": {
        "sockets": (
            "ground_contact",
            "walkway_start",
            "walkway_end",
            "catwalk_start",
            "catwalk_end",
            "ladder_top",
            "ladder_bottom",
            "ramp_start",
            "ramp_end",
            "platform_mount",
            "guardrail_join",
            "gantry_mount",
            "elevator_landing",
            "tunnel_entry",
            "tunnel_exit",
            "scaffold_join",
        ),
        "anchors": ("ground_contact", "route_axis", "platform_center", "vertical_access_axis", "maintenance_entry"),
    },
    "procedural_setpiece": {
        "sockets": (
            "ground_contact",
            "main_entry",
            "road_start",
            "road_end",
            "utility_start",
            "utility_end",
            "access_start",
            "access_end",
            "perimeter_gate",
            "courtyard_origin",
            "dock_edge",
            "apron_edge",
            "ritual_axis",
            "child_module_socket",
            "vehicle_bay",
            "boat_mooring",
            "machine_pad",
            "interior_entry",
            "furniture_anchor",
            "foliage_anchor",
        ),
        "anchors": (
            "setpiece_origin",
            "terrain_center",
            "primary_structure",
            "route_axis",
            "utility_axis",
            "access_axis",
            "prop_cluster",
            "child_module_origin",
        ),
    },
}


class SceneMaterializeError(RuntimeError):
    """Raised when scene asset materialization cannot produce valid sources."""

    def __init__(self, diagnostics: list[dict[str, Any]]) -> None:
        super().__init__("Scene asset materialization failed")
        self.diagnostics = diagnostics


def materialize_scene_assets(
    scene_graph_path: str | Path,
    out_dir: str | Path,
    *,
    mode: str = "preview",
    build_assets: bool = False,
) -> dict[str, Any]:
    """Lower a Scene Graph into deterministic Lathe asset source files."""
    source_path = Path(scene_graph_path)
    scene_graph, diagnostics = load_and_check_scene_graph(source_path)
    if diagnostics:
        raise SceneMaterializeError(diagnostics)

    scene_plan = plan_scene(scene_graph, mode=mode)
    plan_diagnostics = validate_scene_plan_payload(scene_plan)
    if _has_error_diagnostic([*scene_plan.get("diagnostics", []), *plan_diagnostics]):
        raise SceneMaterializeError([*scene_plan.get("diagnostics", []), *plan_diagnostics])

    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_root / "scene_graph.json", scene_graph)
    write_json_atomic(output_root / "scene_plan.json", scene_plan)

    scene_id = str(scene_graph.get("scene_id") or "scene")
    scene_module_slug = _slug(scene_id, fallback="scene")
    object_index = _objects_by_id(scene_graph)
    material_index = _materials_by_id(scene_graph)
    entries: list[dict[str, Any]] = []
    diagnostics_out: list[dict[str, Any]] = []

    for task in scene_plan.get("asset_tasks", []):
        if not isinstance(task, Mapping):
            continue
        entry = _materialize_asset_task(
            output_root=output_root,
            scene_id=scene_id,
            scene_module_slug=scene_module_slug,
            scene_graph=scene_graph,
            task=task,
            object_index=object_index,
            material_index=material_index,
        )
        entries.append(entry)
        diagnostics_out.extend(entry["check"]["diagnostics"])
        diagnostics_out.extend(entry["plan"]["diagnostics"])

    error_diagnostics = [diagnostic for diagnostic in diagnostics_out if diagnostic.get("severity") == "error"]
    if error_diagnostics:
        raise SceneMaterializeError(error_diagnostics)

    build_results: list[dict[str, Any]] = []
    nested_build_results: list[dict[str, Any]] = []
    if build_assets:
        for entry in entries:
            build_payload = _build_generated_asset_source(output_root, entry)
            entry["build"] = build_payload
            build_results.append(build_payload)
            diagnostics_out.extend(build_payload["diagnostics"])
            nested_assets = _build_nested_asset_sources(output_root, entry)
            if nested_assets.get("summary", {}).get("nested_asset_count"):
                nested_assembly = _write_nested_assembly_manifest(
                    output_root=output_root,
                    entry=entry,
                    nested_assets=nested_assets,
                    parent_build=build_payload,
                )
                if nested_assembly:
                    nested_assets = {
                        **dict(nested_assets),
                        "assembly": nested_assembly,
                    }
                entry["nested_assets"] = nested_assets
                nested_builds = _nested_build_payloads(nested_assets)
                nested_build_results.extend(nested_builds)
                for nested_build in nested_builds:
                    diagnostics_out.extend(nested_build.get("diagnostics", []))
            _attach_build_payload_to_metadata(
                output_root,
                entry["metadata_path"],
                build_payload,
                nested_assets=entry.get("nested_assets") if isinstance(entry.get("nested_assets"), Mapping) else None,
            )

    all_build_results = [*build_results, *nested_build_results]
    build_failures = [build for build in all_build_results if not build["ok"]]
    nested_source_count = sum(
        int(
            entry.get("nested_assets", {})
            .get("summary", {})
            .get("nested_asset_count", 0)
        )
        for entry in entries
        if isinstance(entry.get("nested_assets"), Mapping)
    )
    nested_assembly_count = sum(
        1
        for entry in entries
        if isinstance(entry.get("nested_assets"), Mapping)
        and isinstance(entry["nested_assets"].get("assembly"), Mapping)
        and entry["nested_assets"]["assembly"].get("path")
    )
    manifest: dict[str, Any] = {
        "schema_version": SCENE_MATERIALIZATION_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "source_scene_graph": "scene_graph.json",
        "source_scene_plan": "scene_plan.json",
        "generated_source_root": "assets",
        "summary": {
            "asset_tasks": len(entries),
            "source_files": len(entries) + nested_source_count,
            "nested_source_files": nested_source_count,
            "nested_assembly_files": nested_assembly_count,
            "object_instances": sum(len(entry["object_ids"]) for entry in entries),
            "instance_friendly_sources": sum(1 for entry in entries if entry["instancing"]["instance_friendly"]),
            "checker_errors": sum(
                1
                for entry in entries
                for diagnostic in entry["check"]["diagnostics"]
                if diagnostic.get("severity") == "error"
            ),
            "planner_errors": sum(
                1
                for entry in entries
                for diagnostic in entry["plan"]["diagnostics"]
                if diagnostic.get("severity") == "error"
            ),
            "parent_builds_requested": len(build_results),
            "parent_builds_succeeded": sum(1 for build in build_results if build["ok"]),
            "parent_builds_failed": sum(1 for build in build_results if not build["ok"]),
            "nested_builds_requested": len(nested_build_results),
            "nested_builds_succeeded": sum(1 for build in nested_build_results if build["ok"]),
            "nested_builds_failed": sum(1 for build in nested_build_results if not build["ok"]),
            "builds_requested": len(all_build_results),
            "builds_succeeded": sum(1 for build in all_build_results if build["ok"]),
            "builds_failed": len(build_failures),
        },
        "asset_sources": entries,
        "diagnostics": diagnostics_out,
    }
    write_json_atomic(output_root / "scene_materialization_manifest.json", manifest)
    return {
        "ok": not build_failures,
        "command": "scene.materialize",
        "contract": SCENE_MATERIALIZATION_CONTRACT,
        "path": str(source_path),
        "out": str(output_root),
        "mode": mode,
        "build_assets": build_assets,
        "manifest": manifest,
        "diagnostics": diagnostics_out,
    }


def _materialize_asset_task(
    *,
    output_root: Path,
    scene_id: str,
    scene_module_slug: str,
    scene_graph: Mapping[str, Any],
    task: Mapping[str, Any],
    object_index: Mapping[str, Mapping[str, Any]],
    material_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    object_ids = [str(object_id) for object_id in task.get("object_ids", []) if isinstance(object_id, str)]
    objects = [object_index[object_id] for object_id in object_ids if object_id in object_index]
    source = task.get("source") if isinstance(task.get("source"), Mapping) else {}
    source_ref = str(source.get("ref") or (object_ids[0] if object_ids else "asset"))
    asset_name = _asset_name(source_ref, str(task.get("cache_key") or source_ref))
    asset_kind = _infer_asset_kind(source_ref, objects)
    material_ids = _material_ids_for_objects(objects)
    material_declarations = [
        _material_declaration(material_id, material_index.get(material_id, {})) for material_id in material_ids
    ]
    source_text = _asset_source_text(
        scene_id=scene_id,
        scene_module_slug=scene_module_slug,
        asset_name=asset_name,
        asset_kind=asset_kind,
        source_ref=source_ref,
        source=source,
        scene_graph=scene_graph,
        task=task,
        objects=objects,
        material_ids=material_ids,
        material_declarations=material_declarations,
    )

    source_rel = f"assets/{asset_name}/{asset_name}.lth"
    metadata_rel = f"assets/{asset_name}/metadata.json"
    source_path = _package_path(output_root, source_rel)
    metadata_path = _package_path(output_root, metadata_rel)
    write_text_atomic(source_path, source_text)

    check_payload = _check_source(source_path)
    plan_payload = _plan_source(source_path, asset_name) if check_payload["ok"] else {"ok": False, "diagnostics": []}
    nested_assets = (
        _materialize_nested_asset_sources(
            output_root=output_root,
            parent_source_rel=source_rel,
            parent_source_path=source_path,
            parent_asset_name=asset_name,
        )
        if check_payload["ok"] and plan_payload.get("ok")
        else {"schema_version": "lathe.nested_asset_sources.v1", "summary": {"nested_asset_count": 0}, "assets": []}
    )
    metadata = {
        "schema_version": "lathe.generated_scene_asset_metadata.v1",
        "scene_id": scene_id,
        "asset_name": asset_name,
        "asset_kind": asset_kind,
        "asset_task_id": str(task.get("task_id") or ""),
        "cache_key": str(task.get("cache_key") or ""),
        "source": dict(source),
        "object_ids": object_ids,
        "source_scene_roles": sorted({str(obj.get("role")) for obj in objects if isinstance(obj.get("role"), str)}),
        "material_ids": material_ids,
        "instancing": _instancing_metadata(task),
        "nested_assets": nested_assets,
        "provenance": {
            "created_by": "lathe.scene.materialize",
            "created_from": "scene_graph_object_task",
            "deterministic": True,
        },
        "check": check_payload,
        "plan": plan_payload,
    }
    write_json_atomic(metadata_path, metadata)
    entry = {
        "asset_task_id": str(task.get("task_id") or ""),
        "asset_name": asset_name,
        "asset_kind": asset_kind,
        "cache_key": str(task.get("cache_key") or ""),
        "source": dict(source),
        "object_ids": object_ids,
        "source_path": source_rel,
        "metadata_path": metadata_rel,
        "material_ids": material_ids,
        "instancing": metadata["instancing"],
        "check": check_payload,
        "plan": plan_payload,
    }
    nested_manifest = nested_asset_manifest_for_signature(nested_assets)
    if nested_manifest.get("summary", {}).get("nested_asset_count"):
        entry["nested_assets"] = nested_manifest
    return entry


def _materialize_nested_asset_sources(
    *,
    output_root: Path,
    parent_source_rel: str,
    parent_source_path: Path,
    parent_asset_name: str,
) -> dict[str, Any]:
    """Write nested child asset sources for a generated parent asset."""
    try:
        program = parse_file(parent_source_path)
        plan = build_plan(program, parent_asset_name)
        parent_asset = plan.get("effective_asset")
        if not isinstance(parent_asset, dict):
            return {"schema_version": "lathe.nested_asset_sources.v1", "summary": {"nested_asset_count": 0}, "assets": []}
        graph = build_asset_graph(parent_asset)
    except _GENERATED_SOURCE_ERRORS:
        return {"schema_version": "lathe.nested_asset_sources.v1", "summary": {"nested_asset_count": 0}, "assets": []}

    nested_assets = graph.authoring.get("nested_assets", {})
    if not isinstance(nested_assets, Mapping):
        return {"schema_version": "lathe.nested_asset_sources.v1", "summary": {"nested_asset_count": 0}, "assets": []}

    parent_dir = str(PurePosixPath(parent_source_rel).parent).replace("\\", "/")
    entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for raw_asset in nested_assets.get("assets", []) or []:
        if not isinstance(raw_asset, Mapping):
            continue
        asset_name = _slug(str(raw_asset.get("asset_name") or "nested_asset"), fallback="nested_asset")
        child_rel = f"{parent_dir}/children/{asset_name}/{asset_name}.lth"
        child_metadata_rel = f"{parent_dir}/children/{asset_name}/metadata.json"
        child_path = _package_path(output_root, child_rel)
        child_metadata_path = _package_path(output_root, child_metadata_rel)
        write_text_atomic(child_path, str(raw_asset.get("source_text") or ""))
        child_check = _check_source(child_path)
        child_plan = _plan_source(child_path, asset_name) if child_check["ok"] else {"ok": False, "diagnostics": []}
        diagnostics.extend(child_check["diagnostics"])
        diagnostics.extend(child_plan["diagnostics"])
        package = dict(raw_asset.get("package") or {}) if isinstance(raw_asset.get("package"), Mapping) else {}
        package["source_path"] = child_rel
        package["metadata_path"] = child_metadata_rel
        child_metadata = {
            "schema_version": "lathe.generated_nested_asset_metadata.v1",
            "parent_asset_name": parent_asset_name,
            "asset_name": asset_name,
            "asset_kind": str(raw_asset.get("asset_kind") or ""),
            "family": str(raw_asset.get("family") or ""),
            "instance_id": str(raw_asset.get("instance_id") or ""),
            "slot_id": str(raw_asset.get("slot_id") or ""),
            "source_path": child_rel,
            "placement": dict(raw_asset.get("placement") or {}) if isinstance(raw_asset.get("placement"), Mapping) else {},
            "dependency": dict(raw_asset.get("dependency") or {}) if isinstance(raw_asset.get("dependency"), Mapping) else {},
            "package": package,
            "check": child_check,
            "plan": child_plan,
        }
        write_json_atomic(child_metadata_path, child_metadata)
        entries.append(
            {
                **{key: value for key, value in raw_asset.items() if key != "source_text"},
                "asset_name": asset_name,
                "source_path": child_rel,
                "metadata_path": child_metadata_rel,
                "package": package,
                "check": child_check,
                "plan": child_plan,
            }
        )

    manifest = nested_asset_manifest_for_signature({**dict(nested_assets), "assets": entries})
    manifest["diagnostics"] = diagnostics
    return manifest


def _asset_source_text(
    *,
    scene_id: str,
    scene_module_slug: str,
    asset_name: str,
    asset_kind: str,
    source_ref: str,
    source: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
    task: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    material_ids: list[str],
    material_declarations: list[str],
) -> str:
    role = _asset_role(objects, source_ref)
    style = _style_tokens(objects)
    interactions = _interaction_tokens(objects)
    scale = _asset_scale(objects)
    seed = _seed_from_key(str(task.get("cache_key") or asset_name))
    procedural_family = _procedural_family(source, objects)
    parts = _asset_parts(objects, procedural_family=procedural_family)
    negatives = _negative_tokens(asset_kind)
    shape_controls = _shape_controls_for_generated_asset(
        source=source,
        objects=objects,
        task=task,
        procedural_family=procedural_family,
    )
    base_shape_controls = dict(shape_controls)
    creative_grammar = creative_grammar_for_scene(
        source=source,
        objects=objects,
        task=task,
        family=procedural_family,
        shape_controls=shape_controls,
    )
    shape_controls = dict(creative_grammar.get("shape_controls") or shape_controls)
    object_grammar = object_grammar_for_scene(
        source=source,
        objects=objects,
        task=task,
        family=procedural_family,
        shape_controls=base_shape_controls,
    )
    object_shape_controls = dict(object_grammar.get("shape_controls") or {})
    shape_controls.update(object_shape_controls)
    shape_controls.update(_module_shape_controls_for_generated_asset(objects=objects, task=task))
    child_module_layout = child_module_layout_from_authoring(
        family=procedural_family or "",
        shape_controls=shape_controls,
        connections=[],
    )
    shape_controls = dict(child_module_layout.get("shape_controls") or shape_controls)
    interface_controls = _interface_controls_for_generated_asset(
        source=source,
        scene_graph=scene_graph,
        objects=objects,
        task=task,
        procedural_family=procedural_family,
    )
    connection_layout = connection_layout_from_authoring(
        family=procedural_family or "",
        shape_controls=shape_controls,
        connections=[
            *interface_controls.get("connections", []),
            *child_module_layout.get("connections", []),
        ],
        sockets=[*interface_controls.get("sockets", []), *child_module_layout.get("sockets", [])],
        anchors=[
            *interface_controls.get("anchors", []),
            *interface_controls.get("pivots", []),
            *child_module_layout.get("anchors", []),
        ],
    )
    shape_controls = dict(connection_layout.get("shape_controls") or shape_controls)
    grammar_surface: dict[str, Any] = {}
    creative_surface = creative_grammar.get("surface", {})
    if isinstance(creative_surface, Mapping):
        _merge_surface_authoring(grammar_surface, creative_surface)
    object_surface = object_grammar.get("surface", {})
    if isinstance(object_surface, Mapping):
        _merge_surface_authoring(grammar_surface, object_surface)
    surface_authoring = _surface_authoring_for_generated_asset(
        source=source,
        objects=objects,
        task=task,
        procedural_family=procedural_family,
        shape_controls=shape_controls,
        creative_surface=grammar_surface,
    )
    if interface_controls.get("sockets"):
        shape_controls.setdefault("module_sockets", interface_controls["sockets"][:12])
    if interface_controls.get("anchors"):
        shape_controls.setdefault("module_anchors", interface_controls["anchors"][:12])
    lines = [
        f"module wonder.generated_assets.{scene_module_slug}.{asset_name}",
        "",
        f"// Generated by Lathe {SCENE_MATERIALIZATION_VERSION}.",
        f"// Source scene: {scene_id}.",
        f"// Source asset reference: {_comment_value(source_ref)}.",
        f"// Source kind: {_comment_value(str(source.get('kind') or 'generated'))}.",
        f"// Source object IDs: {', '.join(str(obj.get('object_id')) for obj in objects)}.",
        f"// Cache key: {_comment_value(str(task.get('cache_key') or ''))}.",
        "",
    ]
    if material_declarations:
        lines.extend(material_declarations)
        lines.append("")
    lines.extend(
        [
            f"asset {asset_name}: {asset_kind} {{",
            "  intent {",
            f"    role = {_source_string(role)}",
            f"    style = {_source_array(style)}",
            f"    parts = {_source_array(parts, identifiers=True)}",
            f"    materials = {_source_array(material_ids or ['mat_scene_default'], identifiers=True)}",
            f"    negatives = {_source_array(negatives)}",
            f"    scale = {scale}m",
            f"    interactions = {_source_array(interactions, identifiers=True)}",
            "  }",
            "",
        ]
    )
    if procedural_family:
        lines.extend(
            [
                "  assembly {",
                f"    runtime_family = {procedural_family}",
                "  }",
                "",
            ]
        )
    if surface_authoring:
        lines.extend(_surface_block_lines(surface_authoring))
        lines.append("")
    lines.extend(
        [
            "  build {",
            "    shape {",
            "      mode = generate",
            "      candidates = 1",
            f"      seed = {seed}",
        ]
    )
    for key, value in sorted(shape_controls.items()):
        lines.append(f"      {key} = {_source_value(value, identifiers=True)}")
    lines.extend(
        [
            "    }",
        ]
    )
    if interface_controls:
        lines.extend(_interfaces_block_lines(interface_controls))
    lines.extend(
        [
            "  }",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _material_declaration(material_id: str, material: Mapping[str, Any]) -> str:
    pbr = material.get("pbr") if isinstance(material.get("pbr"), Mapping) else {}
    basecolor = _hex_to_rgb(pbr.get("basecolor")) or [128, 128, 128]
    emissive = _hex_to_rgb(pbr.get("emissive")) or [0, 0, 0]
    metallic = _number_or_default(pbr.get("metallic"), 0.0)
    roughness = _number_or_default(pbr.get("roughness"), 0.7)
    lines = [
        f"material {material_id} {{",
        f"  basecolor = {_source_array(basecolor)}",
        f"  metallic = {metallic:g}",
        f"  roughness = {roughness:g}",
        f"  emissive = {_source_array(emissive)}",
    ]
    role = material.get("role")
    if isinstance(role, str) and _IDENTIFIER_RE.match(role):
        lines.append(f"  surface_profile = {role}")
    lines.append("}")
    return "\n".join(lines)


def validate_scene_materialization_manifest_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema diagnostics for a Scene Materialization Manifest payload."""
    from ..wonder import validate_contract

    return validate_contract(SCENE_MATERIALIZATION_CONTRACT, payload)


def _check_source(path: Path) -> dict[str, Any]:
    try:
        program = parse_file(path)
        diagnostics = check_program(program)
    except _GENERATED_SOURCE_ERRORS as exc:
        diagnostics = [
            {
                "code": "SM1901",
                "name": "generated_asset_source_check_failed",
                "severity": "error",
                "phase": "scene_materialization_check",
                "path": str(path),
                "message": str(exc),
            }
        ]
    return {"ok": not _has_error_diagnostic(diagnostics), "diagnostics": diagnostics}


def _plan_source(path: Path, asset_name: str) -> dict[str, Any]:
    try:
        program = parse_file(path)
        plan = build_plan(program, asset_name)
    except _GENERATED_SOURCE_ERRORS as exc:
        return {
            "ok": False,
            "asset": asset_name,
            "diagnostics": [
                {
                    "code": "SM1902",
                    "name": "generated_asset_plan_failed",
                    "severity": "error",
                    "phase": "scene_materialization_plan",
                    "path": str(path),
                    "message": str(exc),
                }
            ],
        }
    return {
        "ok": True,
        "asset": asset_name,
        "kind": str(plan.get("kind") or ""),
        "stages": list(plan.get("stages", [])),
        "backend_stack_id": str(plan.get("backend_stack", {}).get("id") or ""),
        "diagnostics": [],
    }


def _build_generated_asset_source(
    output_root: Path,
    entry: Mapping[str, Any],
    *,
    build_rel: str | None = None,
) -> dict[str, Any]:
    source_path = _package_path(output_root, str(entry["source_path"]))
    resolved_build_rel = build_rel or f"builds/{entry['asset_name']}"
    build_dir = _package_path(output_root, resolved_build_rel)
    try:
        program = parse_file(source_path)
        report = _run_build_asset(program, str(entry["asset_name"]), build_dir)
    except BuildError as exc:
        diagnostics = [
            _normalize_build_diagnostic(
                diagnostic,
                asset_name=str(entry["asset_name"]),
                source_path=str(source_path),
                message=str(exc),
            )
            for diagnostic in (exc.diagnostics or [{}])
        ]
        return {
            "requested": True,
            "ok": False,
            "asset": str(entry["asset_name"]),
            "out_dir": resolved_build_rel,
            "report_path": None,
            "certified": False,
            "diagnostics": diagnostics,
        }
    report_path = build_dir / "build_report.json"
    certified = bool(report.get("certified"))
    return {
        "requested": True,
        "ok": certified,
        "asset": str(entry["asset_name"]),
        "out_dir": resolved_build_rel,
        "report_path": f"{resolved_build_rel}/build_report.json" if report_path.is_file() else None,
        "certified": certified,
        "score": report.get("score"),
        "threshold": report.get("threshold"),
        "diagnostics": [],
    }


def _build_nested_asset_sources(output_root: Path, entry: Mapping[str, Any]) -> dict[str, Any]:
    nested_assets = entry.get("nested_assets") if isinstance(entry.get("nested_assets"), Mapping) else {}
    if not nested_assets:
        return {}
    assets: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = list(nested_assets.get("diagnostics") or [])
    parent_asset_name = str(entry.get("asset_name") or nested_assets.get("parent_asset_name") or "asset")
    for raw_asset in nested_assets.get("assets", []) or []:
        if not isinstance(raw_asset, Mapping):
            continue
        asset_name = _slug(str(raw_asset.get("asset_name") or "nested_asset"), fallback="nested_asset")
        if not raw_asset.get("source_path"):
            assets.append(dict(raw_asset))
            continue
        child_build_rel = f"builds/{parent_asset_name}/children/{asset_name}"
        build_payload = _build_generated_asset_source(
            output_root,
            {**dict(raw_asset), "asset_name": asset_name},
            build_rel=child_build_rel,
        )
        if isinstance(raw_asset.get("metadata_path"), str):
            _attach_build_payload_to_metadata(output_root, str(raw_asset["metadata_path"]), build_payload)
        package = dict(raw_asset.get("package") or {}) if isinstance(raw_asset.get("package"), Mapping) else {}
        package["build_root"] = child_build_rel
        package["build_report_path"] = build_payload.get("report_path")
        package["package_manifest_path"] = f"{child_build_rel}/stages/package/package_manifest.json"
        package["selector_manifest_path"] = f"{child_build_rel}/selector_manifest.json"
        package["status"] = "built" if build_payload.get("ok") else "failed"
        diagnostics.extend(build_payload.get("diagnostics", []))
        assets.append(
            {
                **{key: value for key, value in raw_asset.items() if key != "source_text"},
                "asset_name": asset_name,
                "build": build_payload,
                "package": package,
            }
        )
    summary = dict(nested_assets.get("summary") or {})
    summary["nested_build_count"] = len([asset for asset in assets if isinstance(asset.get("build"), Mapping)])
    summary["nested_build_succeeded"] = sum(
        1 for asset in assets if isinstance(asset.get("build"), Mapping) and asset["build"].get("ok")
    )
    summary["nested_build_failed"] = sum(
        1 for asset in assets if isinstance(asset.get("build"), Mapping) and not asset["build"].get("ok")
    )
    return nested_asset_manifest_for_signature(
        {
            **dict(nested_assets),
            "summary": summary,
            "assets": assets,
            "diagnostics": diagnostics,
        }
    )


def _nested_build_payloads(nested_assets: Mapping[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for asset in nested_assets.get("assets", []) or []:
        if not isinstance(asset, Mapping):
            continue
        build = asset.get("build")
        if isinstance(build, Mapping):
            payloads.append(dict(build))
    return payloads


def _write_nested_assembly_manifest(
    *,
    output_root: Path,
    entry: Mapping[str, Any],
    nested_assets: Mapping[str, Any],
    parent_build: Mapping[str, Any],
) -> dict[str, Any]:
    assembly_rel = f"assets/{entry['asset_name']}/nested_assembly_manifest.json"
    assembly = nested_assembly_manifest(
        parent_asset_name=str(entry["asset_name"]),
        parent_source_path=str(entry["source_path"]),
        parent_metadata_path=str(entry["metadata_path"]),
        parent_build=parent_build,
        nested_assets=nested_assets,
        package_root=output_root,
    )
    assembly["scene_object_ids"] = list(entry.get("object_ids") or [])
    assembly["scene_object_id"] = assembly["scene_object_ids"][0] if assembly["scene_object_ids"] else ""
    assembly["path"] = assembly_rel
    write_json_atomic(_package_path(output_root, assembly_rel), assembly)
    return {
        "path": assembly_rel,
        "schema_version": assembly["schema_version"],
        "summary": dict(assembly.get("summary") or {}),
        "aggregate_package": dict(assembly.get("aggregate_package") or {}),
        "consumable": dict(assembly.get("consumable") or {}),
        "attachments": list(assembly.get("attachments") or []),
    }


def _attach_build_payload_to_metadata(
    output_root: Path,
    metadata_path: str,
    build_payload: Mapping[str, Any],
    *,
    nested_assets: Mapping[str, Any] | None = None,
) -> None:
    path = _package_path(output_root, metadata_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["build"] = dict(build_payload)
    if nested_assets is not None:
        metadata["nested_assets"] = nested_asset_manifest_for_signature(nested_assets)
    write_json_atomic(path, metadata)


def _run_build_asset(program: dict[str, Any], asset_name: str, build_dir: Path) -> dict[str, Any]:
    from ..executor import build_asset

    return build_asset(program, asset_name, build_dir)


def _normalize_build_diagnostic(
    diagnostic: Any,
    *,
    asset_name: str,
    source_path: str,
    message: str,
) -> dict[str, Any]:
    if isinstance(diagnostic, Mapping):
        payload = dict(diagnostic)
    else:
        payload = {}
    payload.setdefault("code", "SM1904")
    payload.setdefault("name", "generated_asset_build_failed")
    payload["severity"] = payload.get("severity") if payload.get("severity") in {"warning", "error"} else "error"
    payload.setdefault("phase", "scene_materialization_build")
    payload.setdefault("path", source_path)
    payload.setdefault("asset", asset_name)
    payload.setdefault("message", message or "Generated asset build failed.")
    return payload


def _objects_by_id(scene_graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["object_id"]): item
        for item in scene_graph.get("objects", [])
        if isinstance(item, Mapping) and isinstance(item.get("object_id"), str)
    }


def _materials_by_id(scene_graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["material_id"]): item
        for item in scene_graph.get("materials", [])
        if isinstance(item, Mapping) and isinstance(item.get("material_id"), str)
    }


def _material_ids_for_objects(objects: list[Mapping[str, Any]]) -> list[str]:
    material_ids: set[str] = set()
    for obj in objects:
        for binding in obj.get("material_bindings", []):
            if isinstance(binding, Mapping) and isinstance(binding.get("material"), str):
                material_ids.add(binding["material"])
    return sorted(material_ids)


def _infer_asset_kind(source_ref: str, objects: list[Mapping[str, Any]]) -> str:
    tokens = _classification_tokens(source_ref, objects)
    roles = {str(obj.get("role", "")).lower() for obj in objects}
    if roles & {"hero_prop", "narrative_clue"}:
        return "hard_surface_prop"
    if tokens & _ARCHITECTURE_TOKENS:
        return "env_module"
    if tokens & _MECHANICAL_TOKENS:
        return "mechanical_assembly"
    return "hard_surface_prop"


def _classification_tokens(source_ref: str, objects: list[Mapping[str, Any]]) -> set[str]:
    raw_parts: list[str] = [source_ref]
    for obj in objects:
        for field in ("object_id", "name", "role", "lathe_asset", "source_family", "source_kit"):
            value = obj.get(field)
            if isinstance(value, str):
                raw_parts.append(value)
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            for field in (
                "archetype",
                "object_archetype",
                "loadout",
                "family_loadout",
                "vehicle_loadout",
                "vehicle_archetype",
                "boat_loadout",
                "boat_archetype",
                "vessel_loadout",
                "weapon_loadout",
                "weapon_archetype",
                "tool_loadout",
                "drive_type",
                "vehicle_type",
                "boat_type",
                "vessel_type",
                "weapon_type",
                "tool_type",
            ):
                value = state.get(field)
                if isinstance(value, str):
                    raw_parts.append(value)
    tokens: set[str] = set()
    for part in raw_parts:
        tokens.update(token for token in _NON_IDENTIFIER_RE.sub("_", part.lower()).split("_") if token)
    return tokens


def _asset_role(objects: list[Mapping[str, Any]], source_ref: str) -> str:
    roles = [str(obj.get("role")) for obj in objects if isinstance(obj.get("role"), str)]
    if len(set(roles)) == 1:
        name = objects[0].get("name") if objects and isinstance(objects[0].get("name"), str) else source_ref
        return f"{roles[0].replace('_', ' ')} generated from scene object {name}"
    if roles:
        return "shared scene asset for " + ", ".join(sorted(set(roles)))
    return f"generated scene asset for {source_ref}"


def _style_tokens(objects: list[Mapping[str, Any]]) -> list[str]:
    tags: set[str] = {"scene_ready"}
    for obj in objects:
        for tag in obj.get("semantic_tags", []):
            if isinstance(tag, str):
                tags.add(_slug(tag, fallback="tag"))
        role = obj.get("role")
        if isinstance(role, str):
            tags.add(_slug(role, fallback="role"))
    return sorted(tags)


def _interaction_tokens(objects: list[Mapping[str, Any]]) -> list[str]:
    interactions: set[str] = {"place_in_world"}
    for obj in objects:
        for affordance in obj.get("affordances", []):
            if isinstance(affordance, Mapping) and isinstance(affordance.get("action"), str):
                interactions.add(_slug(affordance["action"], fallback="interact"))
    return sorted(interactions)


def _procedural_family(source: Mapping[str, Any], objects: list[Mapping[str, Any]]) -> str | None:
    for key in ("source_family", "ref", "lathe_asset", "source_asset"):
        value = source.get(key)
        if isinstance(value, str) and value.startswith("procedural_"):
            return value
    for obj in objects:
        for key in ("source_family", "lathe_asset", "source_asset"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith("procedural_"):
                return value
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        value = state.get("procedural_family") if isinstance(state, Mapping) else None
        if isinstance(value, str) and value.startswith("procedural_"):
            return value
    tokens = _classification_tokens(
        str(source.get("ref") or source.get("source_family") or source.get("lathe_asset") or "scene"),
        objects,
    )
    for key in (
        "kind",
        "style",
        "theme",
        "biome",
        "faction",
        "archetype",
        "object_archetype",
        "setpiece",
        "loadout",
        "family_loadout",
        "vehicle_loadout",
        "boat_loadout",
        "vessel_loadout",
        "weapon_loadout",
        "tool_loadout",
    ):
        value = source.get(key)
        if isinstance(value, str):
            tokens.update(token for token in _NON_IDENTIFIER_RE.sub("_", value.lower()).split("_") if token)
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
        "setpiece",
    } & tokens:
        return "procedural_setpiece"
    if tokens & _BOAT_TOKENS:
        return "procedural_boat"
    if tokens & _VEHICLE_TOKENS:
        return "procedural_vehicle"
    if tokens & _WEAPON_TOKENS:
        return "procedural_weapon"
    return None


def _asset_parts(objects: list[Mapping[str, Any]], *, procedural_family: str | None = None) -> list[str]:
    parts = {"body"}
    if procedural_family in _PROCEDURAL_FAMILY_PARTS:
        parts.update(_PROCEDURAL_FAMILY_PARTS[procedural_family])
    parts.update(_room_content_parts(objects))
    parts.update(_assembly_parts(objects))
    for obj in objects:
        for binding in obj.get("material_bindings", []):
            if isinstance(binding, Mapping) and isinstance(binding.get("slot"), str):
                parts.add(_slug(binding["slot"], fallback="part"))
    return sorted(parts)


def _room_content_parts(objects: list[Mapping[str, Any]]) -> set[str]:
    parts: set[str] = set()
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if not isinstance(state, Mapping):
            continue
        for key in ("packed_item", "content_asset_type", "furniture_type", "fixture_type"):
            value = state.get(key)
            if isinstance(value, str):
                parts.update(_ROOM_CONTENT_ITEM_PARTS.get(_slug(value, fallback="item"), ()))
    return parts


def _assembly_parts(objects: list[Mapping[str, Any]]) -> set[str]:
    parts: set[str] = set()
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if not isinstance(state, Mapping):
            continue
        mode = _assembly_mode(state)
        if not mode and not state.get("assembly_anchor") and not state.get("generated_assembly_member"):
            continue
        parts.update({"assembly_anchor", "assembly_slot", "assembly_socket"})
        parts.update(_identifier_list(state.get("assembly_sockets")))
        for key, value in state.items():
            if isinstance(key, str) and key.startswith("socket_") and key.endswith("_kind") and isinstance(value, str):
                parts.add(_slug(value, fallback="socket"))
            if isinstance(key, str) and key.startswith("attach_") and key.endswith("_socket") and isinstance(value, str):
                parts.add(_slug(value, fallback="socket"))
        if mode == "rack":
            parts.update({"rack_frame", "rack_socket", "weapon_mount", "tool_mount", "rack_clamp", "rack_label"})
        elif mode == "docking_bay":
            parts.update({"dock", "mooring", "cleat", "deck_mount", "mooring_line", "fender"})
        elif mode == "parking":
            parts.update({"parking_bay", "service_mount", "wheel_stop", "wheel_chock", "tie_down"})
        elif mode == "hangar":
            parts.update({"hangar_bay", "service_mount", "apron", "tie_down", "service_umbilical", "wheel_chock"})
        elif mode == "room_layout":
            parts.update({"floor_grid", "wall_mount", "furniture_anchor", "floor_pad", "wall_bracket"})
        elif mode == "machine_line":
            parts.update({"base_mount", "service_rail", "conveyor_start", "conveyor_end"})
        elif mode == "site_plan":
            parts.update({"lot_socket", "road_socket", "entry_socket"})
        elif mode == "terrain_cluster":
            parts.update({"terrain_anchor", "root_socket"})
        elif mode in {"route_network", "access_chain", "utility_run", "convoy", "chain", "loop", "ring"}:
            parts.update({"chain_link", "route_socket", "connection_socket", "road_coupler", "access_coupler", "utility_coupler", "alignment_brace"})
    return parts


def _shape_controls_for_generated_asset(
    *,
    source: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    task: Mapping[str, Any],
    procedural_family: str | None,
) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    if procedural_family:
        controls["scene_source_family"] = procedural_family
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            _merge_state_shape_controls(controls, state)
    overrides = task.get("asset_overrides") if isinstance(task.get("asset_overrides"), Mapping) else {}
    state_overrides = overrides.get("state") if isinstance(overrides.get("state"), Mapping) else {}
    if isinstance(state_overrides, Mapping):
        _merge_state_shape_controls(controls, state_overrides)
    controls.update(_transform_shape_controls(objects, procedural_family=procedural_family))
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        building_controls = state.get("building_envelope_controls") if isinstance(state, Mapping) else {}
        if isinstance(building_controls, Mapping):
            for key, value in building_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    controls[key] = normalized
        site_controls = state.get("site_compound_controls") if isinstance(state, Mapping) else {}
        if isinstance(site_controls, Mapping):
            primary_site_controls = state.get("object_archetype") == "site_compound" or bool(site_controls.get("site_compound_count"))
            for key, value in site_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    if primary_site_controls and not (key == "site_compound_count" and controls.get("district_site_plan_count")):
                        controls[key] = normalized
                    else:
                        controls.setdefault(key, normalized)
        district_controls = state.get("district_site_controls") if isinstance(state, Mapping) else {}
        if isinstance(district_controls, Mapping):
            primary_district_controls = state.get("object_archetype") == "district_site_plan" or bool(district_controls.get("district_site_plan_count"))
            for key, value in district_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    if primary_district_controls:
                        controls[key] = normalized
                    else:
                        controls.setdefault(key, normalized)
        access_controls = state.get("access_transition_controls") if isinstance(state, Mapping) else {}
        if isinstance(access_controls, Mapping):
            primary_access_controls = state.get("object_archetype") == "access_sequence" or bool(access_controls.get("access_sequence_count"))
            for key, value in access_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    if primary_access_controls:
                        controls[key] = normalized
                    else:
                        controls.setdefault(key, normalized)
        circulation_controls = state.get("circulation_controls") if isinstance(state, Mapping) else {}
        if isinstance(circulation_controls, Mapping):
            primary_circulation_controls = state.get("object_archetype") == "circulation_core" or bool(circulation_controls.get("circulation_core_count"))
            for key, value in circulation_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    if primary_circulation_controls:
                        controls[key] = normalized
                    else:
                        controls.setdefault(key, normalized)
        circulation_detail_controls = state.get("circulation_detail_controls") if isinstance(state, Mapping) else {}
        if isinstance(circulation_detail_controls, Mapping):
            primary_detail_controls = state.get("object_archetype") in {"stair_detail", "corridor_shell", "egress_surface_plan", "room_route_binding"} or bool(
                circulation_detail_controls.get("stair_detail_count") or circulation_detail_controls.get("corridor_shell_count")
            )
            for key, value in circulation_detail_controls.items():
                if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                    continue
                normalized = _shape_control_value(value)
                if normalized is not None:
                    if primary_detail_controls:
                        controls[key] = normalized
                    else:
                        controls.setdefault(key, normalized)
    if source.get("kind"):
        controls["scene_source_kind"] = str(source["kind"])
    return controls


_COMPLEX_PROCEDURAL_CONTROL_KEYS = {
    "packing_origin",
    "packing_slots",
    "slot_positions",
    "packed_positions",
    "packed_transforms",
    "resolved_transforms",
    "clearance_reservations",
    "service_anchor_map",
    "service_anchors",
    "child_objects",
    "generated_child_assets",
    "content_asset_controls",
    "content_surface_zones",
    "content_finish_layers",
    "content_markings",
    "content_wear",
    "building_envelope_controls",
    "site_compound_controls",
    "site_buildings",
    "building_lots",
    "courtyard_program",
    "pedestrian_paths",
    "service_alleys",
    "parking_zones",
    "loading_zones",
    "exterior_utilities",
    "site_access_points",
    "site_utility_map",
    "district_site_controls",
    "district_compounds",
    "district_blocks",
    "street_crossings",
    "perimeter_segments",
    "security_gates",
    "landscape_zones",
    "traffic_routes",
    "service_routes",
    "access_transition_controls",
    "entry_points",
    "public_entries",
    "service_entry_points",
    "thresholds",
    "lobby_zones",
    "checkpoint_nodes",
    "loading_routes",
    "wayfinding_nodes",
    "circulation_controls",
    "circulation_floors",
    "served_floor_labels",
    "stair_runs",
    "elevator_banks",
    "egress_routes",
    "emergency_exits",
    "corridor_spines",
    "floor_transitions",
    "public_routes",
    "service_circulation_routes",
    "floor_roles",
    "circulation_detail_controls",
    "egress_surface_zones",
    "room_route_targets",
    "floor_plan",
    "floor_heights",
    "facade_sides",
    "facade_bays",
    "vertical_core_types",
    "entrance_locations",
    "resolved_position",
    "resolved_rotation",
    "room_packing_result",
}


def _merge_state_shape_controls(target: dict[str, Any], state: Mapping[str, Any]) -> None:
    for key, aliases in _PROCEDURAL_CONTROL_ALIASES.items():
        if key not in state:
            continue
        value = state[key]
        if key in _COMPLEX_PROCEDURAL_CONTROL_KEYS and isinstance(value, Mapping | Sequence) and not isinstance(value, str | bytes | bytearray):
            normalized_value = deepcopy(value)
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            if not all(isinstance(item, str | int | float | bool) for item in value):
                continue
            normalized_value: Any = [str(item) for item in value]
        elif isinstance(value, str | int | float | bool):
            normalized_value = value
        else:
            continue
        for alias in aliases:
            target.setdefault(alias, normalized_value)
    content_controls = state.get("content_asset_controls")
    if isinstance(content_controls, Mapping):
        for key, value in content_controls.items():
            if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                continue
            normalized = _shape_control_value(value)
            if normalized is not None:
                target.setdefault(key, normalized)
    building_controls = state.get("building_envelope_controls")
    if isinstance(building_controls, Mapping):
        for key, value in building_controls.items():
            if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                continue
            normalized = _shape_control_value(value)
            if normalized is not None:
                target.setdefault(key, normalized)
    site_controls = state.get("site_compound_controls")
    if isinstance(site_controls, Mapping):
        for key, value in site_controls.items():
            if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                continue
            normalized = _shape_control_value(value)
            if normalized is not None:
                target.setdefault(key, normalized)
    district_controls = state.get("district_site_controls")
    if isinstance(district_controls, Mapping):
        for key, value in district_controls.items():
            if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                continue
            normalized = _shape_control_value(value)
            if normalized is not None:
                target.setdefault(key, normalized)
    for key in ("connection_length", "connection_yaw_degrees"):
        value = state.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            target.setdefault(key, round(float(value), 6))
    if state.get("derived_connector_transform") is True:
        target["derived_connector_transform"] = True
    _merge_child_module_shape_controls(target, state)
    _merge_assembly_shape_controls(target, state)


def _merge_assembly_shape_controls(target: dict[str, Any], state: Mapping[str, Any]) -> None:
    mode = _assembly_mode(state)
    family = _assembly_family(state)
    count = _assembly_count(state)
    if mode:
        target.setdefault("assembly_mode", mode)
        target.setdefault("assembly_type", mode)
        target.setdefault("assembly_layout", mode)
    if family:
        target.setdefault("assembly_family", family)
    if count:
        target.setdefault("assembly_count", count)
        target.setdefault("assembly_slot_count", count)
        target.setdefault("slot_count", count)
        target.setdefault("module_socket_count", count)
    if state.get("assembly_anchor") is True:
        target["assembly_anchor"] = True
        target.setdefault("assembly_role", "anchor")
    if state.get("generated_assembly_member") is True:
        target["assembly_member"] = True
        target.setdefault("assembly_role", "member")
    for key in (
        "assembly_group",
        "assembly_index",
        "assembly_sockets",
        "assembly_socket",
        "child_socket",
        "chain_socket",
        "selection_strategy",
        "variant_option",
    ):
        if key not in state:
            continue
        normalized = _shape_control_value(state[key])
        if normalized is not None:
            target.setdefault(key, normalized)
    if not mode:
        return
    if mode == "rack":
        target.setdefault("rack_count", max(1, count or 1))
        target.setdefault("hardpoint_count", max(1, count or 1))
        target.setdefault("module_socket_count", max(1, count or 1))
        target.setdefault("infrastructure_type", "equipment_rack")
    elif mode == "docking_bay":
        target.setdefault("dock_count", max(1, count or 1))
        target.setdefault("mooring_points", max(1, count or 1))
        target.setdefault("cleat_count", max(1, count or 1))
        target.setdefault("infrastructure_type", "dock")
    elif mode == "parking":
        target.setdefault("parking_bay_count", max(1, count or 1))
        target.setdefault("infrastructure_type", "parking_pad")
    elif mode == "hangar":
        target.setdefault("hangar_bay_count", max(1, count or 1))
        target.setdefault("apron_count", max(1, count or 1))
        target.setdefault("infrastructure_type", "hangar_pad")
    elif mode == "room_layout":
        target.setdefault("floor_grid_count", max(1, count or 1))
        target.setdefault("room_role", "layout_anchor")
        target.setdefault("furniture_cluster_count", max(1, count or 1))
    elif mode == "machine_line":
        target.setdefault("station_count", max(1, count or 1))
        target.setdefault("service_rail_count", max(1, count or 1))
        target.setdefault("junction_box_count", max(1, count or 1))
        target.setdefault("infrastructure_type", "machine_line")
    elif mode == "site_plan":
        target.setdefault("lot_count", max(1, count or 1))
        target.setdefault("building_count", max(1, count or 1))
    elif mode == "terrain_cluster":
        target.setdefault("terrain_anchor_count", max(1, count or 1))
        target.setdefault("clearing_count", max(1, count or 1))
    elif mode in {"route_network", "access_chain", "utility_run", "convoy", "chain", "loop", "ring"}:
        target.setdefault("connection_segment_count", max(1, (count or 2) - 1))
        target.setdefault("route_segment_count", max(1, (count or 2) - 1))


def _module_shape_controls_for_generated_asset(
    *,
    objects: list[Mapping[str, Any]],
    task: Mapping[str, Any],
) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            _merge_child_module_shape_controls(controls, state)
    overrides = task.get("asset_overrides") if isinstance(task.get("asset_overrides"), Mapping) else {}
    state_overrides = overrides.get("state") if isinstance(overrides.get("state"), Mapping) else {}
    if isinstance(state_overrides, Mapping):
        _merge_child_module_shape_controls(controls, state_overrides)
    return controls


def _merge_child_module_shape_controls(target: dict[str, Any], state: Mapping[str, Any]) -> None:
    for key, value in state.items():
        if not isinstance(key, str):
            continue
        if key in _CHILD_MODULE_MAPPING_KEYS and isinstance(value, Mapping):
            _merge_module_template_mapping(target, value)
            continue
        if key in _CHILD_MODULE_CONTROL_MAP_KEYS and isinstance(value, Mapping):
            _merge_module_control_mapping(target, value)
            continue
        if key in _CHILD_MODULE_POSITION_MAP_KEYS and isinstance(value, Mapping):
            _merge_slot_value_mapping(target, value, field="position")
            continue
        if key in _CHILD_MODULE_FACING_MAP_KEYS and isinstance(value, Mapping):
            _merge_slot_value_mapping(target, value, field="facing_degrees")
            continue
        if key in _CHILD_MODULE_CLEARANCE_MAP_KEYS and isinstance(value, Mapping):
            _merge_slot_value_mapping(target, value, field="clearance")
            continue
        if not _is_child_module_control_key(key, value):
            continue
        normalized = _shape_control_value(value)
        if normalized is not None:
            target[key] = normalized


def _is_child_module_control_key(key: str, value: Any) -> bool:
    if key in _CHILD_MODULE_DIRECT_KEYS:
        return True
    for kind in _CHILD_MODULE_KINDS:
        if key in {
            f"{kind}_module",
            f"{kind}_template",
            f"{kind}_archetype",
            f"{kind}_module_templates",
            f"{kind}_templates",
            f"{kind}_slot_count",
        }:
            return True
        if key == f"{kind}_modules":
            return isinstance(value, str) or (
                isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray)
            )
        if key.startswith(f"{kind}_") and "_module_" in key:
            return True
        if key.startswith(f"{kind}_slot_") and key.endswith(("_module", "_template", "_archetype")):
            return True
        if key.startswith(f"{kind}_") and key.endswith(("_position", "_facing", "_facing_degrees", "_clearance")):
            return True
    return key.startswith("child_module_")


def _merge_module_template_mapping(target: dict[str, Any], mapping: Mapping[str, Any]) -> None:
    for raw_slot, raw_value in mapping.items():
        slot = _slug(str(raw_slot), fallback="slot")
        template = _template_value(raw_value)
        if template:
            target[_module_template_control_key(slot)] = template
        if isinstance(raw_value, Mapping):
            _merge_module_control_payload(target, slot, raw_value)


def _merge_module_control_mapping(target: dict[str, Any], mapping: Mapping[str, Any]) -> None:
    for raw_key, raw_value in mapping.items():
        key = _slug(str(raw_key), fallback="module_control")
        if isinstance(raw_value, Mapping):
            _merge_module_control_payload(target, key, raw_value)
            continue
        normalized = _shape_control_value(raw_value)
        if normalized is None:
            continue
        target[_module_control_key(key)] = normalized


def _merge_slot_value_mapping(target: dict[str, Any], mapping: Mapping[str, Any], *, field: str) -> None:
    for raw_slot, raw_value in mapping.items():
        slot = _slug(str(raw_slot), fallback="slot")
        normalized = _shape_control_value(raw_value)
        if normalized is not None:
            target[_slot_control_key(slot, field)] = normalized


def _merge_module_control_payload(target: dict[str, Any], slot: str, payload: Mapping[str, Any]) -> None:
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str):
            continue
        field = _slug(raw_key, fallback="control")
        if field in {"module", "template", "archetype"}:
            continue
        normalized = _shape_control_value(raw_value)
        if normalized is not None:
            target[f"{_module_control_prefix(slot)}_{field}"] = normalized


def _template_value(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("module", "template", "archetype"):
            item = value.get(key)
            if isinstance(item, str | int | float) and not isinstance(item, bool):
                return _slug(str(item), fallback="module")
        return ""
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        return _slug(str(value), fallback="module")
    return ""


def _module_template_control_key(slot: str) -> str:
    if slot.endswith(("_module", "_template", "_archetype")):
        return slot
    if slot in _CHILD_MODULE_KINDS:
        return f"{slot}_module"
    return f"{slot}_module"


def _module_control_key(key: str) -> str:
    if "_module_" in key:
        return key
    for kind in _CHILD_MODULE_KINDS:
        indexed = re.match(rf"^({kind}_(?:slot_)?[0-9]{{1,2}})_(.+)$", key)
        if indexed:
            return f"{indexed.group(1)}_module_{indexed.group(2)}"
        if key.startswith(f"{kind}_"):
            return key.replace(f"{kind}_", f"{kind}_module_", 1)
    return key


def _module_control_prefix(slot: str) -> str:
    if slot.endswith("_module"):
        return slot
    return f"{slot}_module"


def _slot_control_key(slot: str, field: str) -> str:
    if slot.endswith(f"_{field}"):
        return slot
    return f"{slot}_{field}"


def _shape_control_value(value: Any) -> Any | None:
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        items = [item for item in value if isinstance(item, bool | int | float | str)]
        if items:
            return [str(item) if not isinstance(item, bool | int | float) else item for item in items]
    return None


def _interface_controls_for_generated_asset(
    *,
    source: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    task: Mapping[str, Any],
    procedural_family: str | None,
) -> dict[str, list[Any]]:
    controls: dict[str, list[Any]] = {"sockets": [], "anchors": [], "pivots": [], "connections": []}
    defaults = _PROCEDURAL_INTERFACE_DEFAULTS.get(procedural_family or "")
    if isinstance(defaults, Mapping):
        for key in ("sockets", "anchors", "pivots"):
            controls[key].extend(_identifier_list(defaults.get(key, ())))
    source_interfaces = source.get("interfaces") if isinstance(source.get("interfaces"), Mapping) else {}
    if isinstance(source_interfaces, Mapping):
        for key in ("sockets", "anchors", "pivots"):
            controls[key].extend(_identifier_list(source_interfaces.get(key, ())))
        controls["connections"].extend(_connection_list(source_interfaces.get("connections")))
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            _merge_state_interfaces(controls, state)
    _merge_scene_relationship_connections(
        controls,
        scene_graph=scene_graph,
        objects=objects,
        procedural_family=procedural_family,
    )
    overrides = task.get("asset_overrides") if isinstance(task.get("asset_overrides"), Mapping) else {}
    state_overrides = overrides.get("state") if isinstance(overrides.get("state"), Mapping) else {}
    if isinstance(state_overrides, Mapping):
        _merge_state_interfaces(controls, state_overrides)
    return {
        key: _dedupe_identifiers(values) if key != "connections" else _dedupe_connections(values)
        for key, values in controls.items()
        if values
    }


def _merge_state_interfaces(target: dict[str, list[Any]], state: Mapping[str, Any]) -> None:
    target["sockets"].extend(_identifier_list(state.get("composition_sockets")))
    target["anchors"].extend(_identifier_list(state.get("composition_anchors")))
    target["pivots"].extend(_identifier_list(state.get("composition_pivots")))
    target["connections"].extend(_connection_list(state.get("composition_connections")))
    mode = _assembly_mode(state)
    count = _assembly_count(state)
    assembly_sockets = _identifier_list(state.get("assembly_sockets"))
    if assembly_sockets:
        target["sockets"].extend(assembly_sockets)
    if mode:
        if state.get("assembly_anchor") is True:
            target["anchors"].append(_slug(f"{mode}_anchor", fallback="anchor"))
        if state.get("generated_assembly_member") is True:
            target["anchors"].append(_slug(f"{mode}_member", fallback="anchor"))
        if count:
            for index in range(min(count, 32)):
                socket = assembly_sockets[index % len(assembly_sockets)] if assembly_sockets else f"{mode}_slot"
                target["sockets"].append(_slug(f"{socket}_{index + 1:02d}", fallback="socket"))
    for key, value in state.items():
        if not isinstance(key, str):
            continue
        if key.startswith("socket_") and key.endswith("_kind") and isinstance(value, str):
            socket_name = key.removeprefix("socket_").removesuffix("_kind")
            target["sockets"].append(_slug(f"{socket_name}_{value}", fallback="socket"))
        elif key.startswith("attach_") and key.endswith("_target"):
            attach_name = key.removeprefix("attach_").removesuffix("_target")
            target["anchors"].append(_slug(attach_name, fallback="anchor"))
            target["connections"].append(
                {
                    "id": _slug(f"{attach_name}_to_{value}", fallback="connection"),
                    "source": _slug(attach_name, fallback="anchor"),
                    "target": str(value),
                    "relation": "attached_to",
                }
            )
        elif key.startswith("connect_") and key.endswith("_target"):
            connect_name = key.removeprefix("connect_").removesuffix("_target")
            target["sockets"].append(_slug(connect_name, fallback="socket"))
            target["connections"].append(
                {
                    "id": _slug(f"{connect_name}_to_{value}", fallback="connection"),
                    "source": _slug(connect_name, fallback="socket"),
                    "target": str(value),
                    "relation": "connects_to",
                }
            )


def _connection_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            dict(item) if isinstance(item, Mapping) else item
            for item in value
            if item is not None and item != ""
        ]
    return [value]


def _dedupe_connections(values: Sequence[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        key = json.dumps(value, sort_keys=True, ensure_ascii=True) if isinstance(value, Mapping) else str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(value) if isinstance(value, Mapping) else value)
    return out


def _merge_scene_relationship_connections(
    target: dict[str, list[Any]],
    *,
    scene_graph: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    procedural_family: str | None,
) -> None:
    object_ids = {str(obj.get("object_id")) for obj in objects if isinstance(obj.get("object_id"), str)}
    if not object_ids:
        return
    for relationship in scene_graph.get("relationships", []) or []:
        if not isinstance(relationship, Mapping):
            continue
        source_ref = relationship.get("from")
        target_ref = relationship.get("to")
        if not isinstance(source_ref, str) or not isinstance(target_ref, str):
            continue
        from_local = source_ref in object_ids
        to_local = target_ref in object_ids
        if not from_local and not to_local:
            continue
        relation = str(relationship.get("type") or "connects_to")
        source_endpoint = (
            _relationship_local_endpoint(procedural_family, relation, outbound=True)
            if from_local
            else _scene_endpoint_ref(source_ref)
        )
        target_endpoint = (
            _relationship_local_endpoint(procedural_family, relation, outbound=False)
            if to_local
            else _scene_endpoint_ref(target_ref)
        )
        if from_local:
            target["anchors"].append(_slug(source_endpoint, fallback="anchor"))
        if to_local:
            target["anchors"].append(_slug(target_endpoint, fallback="anchor"))
        target["connections"].append(
            {
                "id": _slug(
                    str(relationship.get("relationship_id") or f"{source_ref}_{relation}_{target_ref}"),
                    fallback="connection",
                ),
                "source": source_endpoint,
                "target": target_endpoint,
                "relation": relation,
            }
        )


def _scene_endpoint_ref(value: str) -> str:
    return f"scene.{_slug(value, fallback='object')}"


def _relationship_local_endpoint(
    procedural_family: str | None,
    relation: str,
    *,
    outbound: bool,
) -> str:
    family = procedural_family or ""
    relation_key = relation.lower()
    family_map: dict[str, dict[str, tuple[str, str]]] = {
        "procedural_access": {
            "routes_to": ("route_axis", "route_axis"),
            "connects_to": ("route_axis", "route_axis"),
            "opens_to": ("maintenance_entry", "walkway_start"),
            "attached_to": ("maintenance_entry", "platform_mount"),
            "snaps_to": ("platform_mount", "platform_mount"),
            "supports": ("access_support", "platform_mount"),
        },
        "procedural_building": {
            "routes_to": ("entry_door", "entry_door"),
            "opens_to": ("entry_door", "entry_door"),
            "attached_to": ("facade_center", "side_wall_left"),
            "supports": ("floor_contact", "roof_mount"),
            "snaps_to": ("side_wall_right", "side_wall_left"),
        },
        "procedural_interior": {
            "routes_to": ("corridor_axis", "corridor_axis"),
            "opens_to": ("door_center", "corridor_start"),
            "attached_to": ("room_origin", "partition_opening"),
            "contains": ("room_origin", "floor_grid"),
        },
        "procedural_road": {
            "routes_to": ("road_end", "road_start"),
            "connects_to": ("road_end", "road_start"),
            "snaps_to": ("junction_east", "junction_west"),
        },
        "procedural_bridge": {
            "routes_to": ("bridge_end", "bridge_start"),
            "connects_to": ("bridge_end", "bridge_start"),
            "supports": ("foundation_contact", "pier_mounts"),
        },
        "procedural_infrastructure": {
            "connects_to": ("network_axis", "service_center"),
            "routes_to": ("network_axis", "service_center"),
            "attached_to": ("maintenance_access", "junction_center"),
            "supports": ("ground_contact", "service_center"),
        },
        "procedural_city_block": {
            "routes_to": ("street_center", "north_road"),
            "connects_to": ("street_center", "lot_grid"),
            "contains": ("block_center", "lot_origin"),
        },
        "procedural_terrain": {
            "routes_to": ("traversal_center", "path_start"),
            "connects_to": ("traversal_center", "path_end"),
            "supports": ("ground_origin", "platform_mount"),
        },
        "procedural_setpiece": {
            "routes_to": ("route_axis", "main_entry"),
            "connects_to": ("road_end", "road_start"),
            "opens_to": ("main_entry", "courtyard_origin"),
            "attached_to": ("utility_axis", "utility_start"),
            "supports": ("terrain_center", "ground_contact"),
            "contains": ("setpiece_origin", "primary_structure"),
        },
    }
    default_map = {
        "routes_to": ("route_axis", "route_axis"),
        "connects_to": ("connection_out", "connection_in"),
        "opens_to": ("entry", "entry"),
        "attached_to": ("attach_point", "mount"),
        "snaps_to": ("snap_out", "snap_in"),
        "supports": ("support", "mount"),
        "contains": ("container", "contained"),
    }
    endpoints = family_map.get(family, {}).get(relation_key) or default_map.get(relation_key) or ("connection_out", "connection_in")
    return endpoints[0] if outbound else endpoints[1]


def _identifier_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values: Sequence[Any] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        values = value
    else:
        values = [value]
    return [_slug(str(item), fallback="interface") for item in values if item is not None and item != ""]


def _assembly_mode(state: Mapping[str, Any]) -> str:
    value = state.get("assembly_mode") or state.get("assembly_type") or state.get("assembly_layout")
    return _slug(str(value), fallback="assembly") if isinstance(value, str) and value else ""


def _assembly_family(state: Mapping[str, Any]) -> str:
    value = state.get("assembly_family") or state.get("variant_family") or state.get("source_family")
    return _slug(str(value), fallback="assembly_family") if isinstance(value, str) and value else ""


def _assembly_count(state: Mapping[str, Any]) -> int:
    for key in ("assembly_count", "generator_count", "placement_count", "slot_count"):
        value = state.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return max(0, min(128, int(value)))
        if isinstance(value, str):
            try:
                return max(0, min(128, int(float(value))))
            except ValueError:
                continue
    sockets = _identifier_list(state.get("assembly_sockets"))
    return len(sockets)


def _dedupe_identifiers(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(_slug(value, fallback="interface") for value in values if value))


def _transform_shape_controls(
    objects: list[Mapping[str, Any]],
    *,
    procedural_family: str | None,
) -> dict[str, Any]:
    extents: list[list[float]] = []
    for obj in objects:
        transform = obj.get("transform") if isinstance(obj.get("transform"), Mapping) else {}
        scale = transform.get("scale") if isinstance(transform, Mapping) else None
        if not isinstance(scale, list) or len(scale) < 3:
            continue
        values = [float(value) for value in scale[:3] if isinstance(value, int | float) and not isinstance(value, bool)]
        if len(values) == 3 and all(value > 0 for value in values):
            extents.append(values)
    if not extents:
        return {}
    max_x = max(item[0] for item in extents)
    max_y = max(item[1] for item in extents)
    max_z = max(item[2] for item in extents)
    basis = max(max_x, max_y, max_z, 0.001)
    controls = {
        "width_scale": round(max_x / basis, 6),
        "length_scale": round(max_y / basis, 6),
        "depth_scale": round(max_y / basis, 6),
        "height_scale": round(max_z / basis, 6),
    }
    if procedural_family == "procedural_building":
        controls["building_width"] = controls["width_scale"]
        controls["building_depth"] = controls["depth_scale"]
    elif procedural_family == "procedural_city_block":
        controls["block_width"] = controls["width_scale"]
        controls["block_depth"] = controls["depth_scale"]
    elif procedural_family == "procedural_interior":
        controls["room_width"] = controls["width_scale"]
        controls["room_depth"] = controls["depth_scale"]
        controls["room_height"] = controls["height_scale"]
    elif procedural_family == "procedural_furniture":
        controls["furniture_width"] = controls["width_scale"]
        controls["furniture_depth"] = controls["depth_scale"]
        controls["furniture_height"] = controls["height_scale"]
    elif procedural_family == "procedural_foliage":
        controls["foliage_width"] = controls["width_scale"]
        controls["foliage_depth"] = controls["depth_scale"]
        controls["foliage_height"] = controls["height_scale"]
    elif procedural_family == "procedural_urban_prop":
        controls["urban_width"] = controls["width_scale"]
        controls["street_prop_width"] = controls["width_scale"]
        controls["urban_depth"] = controls["depth_scale"]
        controls["street_prop_depth"] = controls["depth_scale"]
        controls["urban_height"] = controls["height_scale"]
        controls["street_prop_height"] = controls["height_scale"]
    elif procedural_family == "procedural_infrastructure":
        controls["infrastructure_width"] = controls["width_scale"]
        controls["network_width"] = controls["width_scale"]
        controls["infrastructure_depth"] = controls["depth_scale"]
        controls["network_depth"] = controls["depth_scale"]
        controls["infrastructure_height"] = controls["height_scale"]
        controls["network_height"] = controls["height_scale"]
    elif procedural_family == "procedural_access":
        controls["access_width"] = controls["width_scale"]
        controls["traversal_width"] = controls["width_scale"]
        controls["access_depth"] = controls["depth_scale"]
        controls["traversal_depth"] = controls["depth_scale"]
        controls["access_height"] = controls["height_scale"]
        controls["traversal_height"] = controls["height_scale"]
    elif procedural_family == "procedural_setpiece":
        controls["setpiece_width"] = controls["width_scale"]
        controls["setpiece_depth"] = controls["depth_scale"]
        controls["setpiece_height"] = controls["height_scale"]
    elif procedural_family == "procedural_vehicle":
        controls["vehicle_width"] = controls["width_scale"]
        controls["vehicle_length"] = controls["length_scale"]
        controls["vehicle_height"] = controls["height_scale"]
    elif procedural_family == "procedural_boat":
        controls["boat_width"] = controls["width_scale"]
        controls["boat_length"] = controls["length_scale"]
        controls["boat_height"] = controls["height_scale"]
    elif procedural_family == "procedural_machine":
        controls["machine_width"] = controls["width_scale"]
        controls["machine_depth"] = controls["depth_scale"]
        controls["machine_height"] = controls["height_scale"]
    elif procedural_family == "procedural_terrain":
        controls["terrain_width"] = controls["width_scale"]
        controls["terrain_depth"] = controls["depth_scale"]
        controls["terrain_height"] = controls["height_scale"]
    elif procedural_family in {"procedural_road", "procedural_bridge"}:
        controls["road_width" if procedural_family == "procedural_road" else "bridge_width"] = controls["width_scale"]
        controls["road_length" if procedural_family == "procedural_road" else "bridge_length"] = controls["length_scale"]
    return controls


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)]


def _merge_surface_authoring(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
            continue
        if key in {
            "materials",
            "material_layers",
            "layers",
            "story_decals",
            "faction_marks",
            "markings",
            "decals",
            "decal_targets",
            "story_targets",
            "story_regions",
            "patterns",
            "mask_programs",
            "trim_sheets",
            "damage_decals",
            "damage_targets",
            "exposed_materials",
            "transition_materials",
            "weather_decals",
            "environment_decals",
        }:
            existing = _as_string_list(target.get(key))
            target[key] = list(dict.fromkeys([*existing, *_as_string_list(value)]))
        elif key in {"zones", "material_zones"} and isinstance(value, Mapping):
            zones = dict(target.get("zones", {})) if isinstance(target.get("zones"), Mapping) else {}
            for zone_key, zone_value in value.items():
                if isinstance(zone_key, str) and _IDENTIFIER_RE.match(zone_key):
                    zones[zone_key] = str(zone_value)
            target["zones"] = zones
        elif isinstance(value, str | int | float | bool):
            target[key] = value


def _surface_authoring_for_generated_asset(
    *,
    source: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    task: Mapping[str, Any],
    procedural_family: str | None,
    shape_controls: Mapping[str, Any],
    creative_surface: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    surface: dict[str, Any] = {}
    defaults = _PROCEDURAL_SURFACE_DEFAULTS.get(procedural_family or "")
    if isinstance(defaults, Mapping):
        _merge_surface_authoring(surface, defaults)
    if isinstance(creative_surface, Mapping):
        _merge_surface_authoring(surface, creative_surface)
    for obj in objects:
        overrides = obj.get("surface_overrides") if isinstance(obj.get("surface_overrides"), Mapping) else {}
        if isinstance(overrides, Mapping):
            _merge_surface_authoring(surface, overrides)
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            _merge_surface_authoring(surface, _content_surface_authoring_from_state(state))
    overrides = task.get("asset_overrides") if isinstance(task.get("asset_overrides"), Mapping) else {}
    surface_overrides = overrides.get("surface_overrides") if isinstance(overrides.get("surface_overrides"), Mapping) else {}
    if isinstance(surface_overrides, Mapping):
        _merge_surface_authoring(surface, surface_overrides)
    material_ids: list[str] = []
    for obj in objects:
        for binding in obj.get("material_bindings", []):
            if isinstance(binding, Mapping) and isinstance(binding.get("material"), str):
                material_ids.append(binding["material"])
    if material_ids:
        _merge_surface_authoring(surface, {"materials": material_ids})
    _merge_surface_authoring(surface, _assembly_surface_authoring(objects, shape_controls))
    zones = surface.get("zones") if isinstance(surface.get("zones"), Mapping) else {}
    if zones:
        _merge_surface_authoring(surface, {"materials": list(zones.values())})
    grammar = surface_grammar_for_controls(
        procedural_family=procedural_family,
        shape_controls=dict(shape_controls),
        surface=surface,
    )
    return merge_surface_grammar(surface, grammar)


def _content_surface_authoring_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    surface: dict[str, Any] = {}
    zones = state.get("content_surface_zones")
    if isinstance(zones, Mapping):
        _merge_surface_authoring(surface, {"zones": zones})
    layers = state.get("content_finish_layers")
    if isinstance(layers, Sequence) and not isinstance(layers, str | bytes | bytearray):
        _merge_surface_authoring(surface, {"material_layers": [str(item) for item in layers if item is not None and str(item) != ""]})
    markings = state.get("content_markings")
    if isinstance(markings, Sequence) and not isinstance(markings, str | bytes | bytearray):
        values = [str(item) for item in markings if item is not None and str(item) != ""]
        _merge_surface_authoring(surface, {"story_decals": values, "decals": values})
    wear = state.get("content_wear")
    if isinstance(wear, Sequence) and not isinstance(wear, str | bytes | bytearray):
        _merge_surface_authoring(surface, {"patterns": [str(item) for item in wear if item is not None and str(item) != ""]})
    for key in (
        "content_surface_plan_count",
        "content_material_zone_count",
        "content_finish_preset_count",
        "content_wear_profile_count",
        "content_marking_set_count",
        "content_surface_zone_count",
        "content_decal_count",
        "surface_layer_count",
        "material_zone_count",
        "decal_count",
        "wear_pattern_count",
    ):
        value = state.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            surface[key] = value
    return surface


def _assembly_surface_authoring(objects: list[Mapping[str, Any]], shape_controls: Mapping[str, Any]) -> dict[str, Any]:
    modes = [_assembly_mode(obj.get("state") if isinstance(obj.get("state"), Mapping) else {}) for obj in objects]
    modes.extend(_identifier_list(shape_controls.get("assembly_mode")))
    modes = [mode for mode in modes if mode]
    if not modes:
        return {}
    surface: dict[str, Any] = {
        "material_layers": ["edge_wear", "socket_labels"],
        "story_decals": ["assembly_slot_label", "snap_alignment_mark"],
        "markings": ["socket_index_marks"],
    }
    zones: dict[str, str] = {}
    for mode in modes:
        zones.update(_ASSEMBLY_SURFACE_ZONES.get(mode, {}))
    socket_names: list[str] = []
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        if isinstance(state, Mapping):
            socket_names.extend(_identifier_list(state.get("assembly_sockets")))
            for key, value in state.items():
                if isinstance(key, str) and key.startswith("socket_") and key.endswith("_kind") and isinstance(value, str):
                    socket_names.append(value)
                if isinstance(key, str) and key.startswith("attach_") and key.endswith("_socket") and isinstance(value, str):
                    socket_names.append(value)
    for socket_name in _dedupe_identifiers(socket_names):
        zones.setdefault(socket_name, "hazard_paint")
    if zones:
        surface["zones"] = zones
    return surface


def _surface_block_lines(surface: Mapping[str, Any]) -> list[str]:
    lines = ["  surface {"]
    for key in (
        "materials",
        "material_layers",
        "layers",
        "story_decals",
        "faction_marks",
        "markings",
        "decals",
        "decal_targets",
        "story_targets",
        "story_regions",
        "patterns",
        "mask_programs",
        "trim_sheets",
        "damage_decals",
        "damage_targets",
        "exposed_materials",
        "transition_materials",
        "weather_decals",
        "environment_decals",
    ):
        values = _as_string_list(surface.get(key))
        if values:
            lines.append(f"    {key} = {_source_array(values, identifiers=True)}")
    for key in (
        "wear_story",
        "usage_history",
        "story",
        "wear_level",
        "edge_wear",
        "damage_level",
        "damage_type",
        "exposed_material",
        "from_material",
        "to_material",
        "transition_profile",
        "weather_type",
        "atmosphere_type",
        "sky_material",
        "cloud_material",
        "wet_material",
        "dry_material",
        "liquid_type",
        "wetness_level",
        "moisture_level",
        "rain_rate",
        "snow_rate",
        "fog_density",
        "mist_density",
        "smoke_density",
        "heat_haze_level",
        "wind_speed",
        "wind_direction",
        "surface_layer_count",
        "material_zone_count",
        "decal_count",
        "wear_pattern_count",
        "damage_surface_count",
        "crack_count",
        "scratch_count",
        "scorch_count",
        "dent_count",
        "chip_count",
        "surface_transition_count",
        "content_surface_plan_count",
        "content_material_zone_count",
        "content_finish_preset_count",
        "content_wear_profile_count",
        "content_marking_set_count",
        "content_surface_zone_count",
        "content_decal_count",
        "weather_system_count",
        "atmosphere_count",
        "wind_zone_count",
        "liquid_body_count",
        "puddle_count",
        "fire_source_count",
        "smoke_emitter_count",
        "mist_volume_count",
        "wetness_zone_count",
        "heat_haze_count",
        "time_of_day_count",
        "environment_effect_count",
        "story_density",
        "story_asymmetry",
        "asymmetry",
    ):
        if key in surface:
            lines.append(f"    {key} = {_source_value(surface[key], identifiers=True)}")
    zones = surface.get("zones") if isinstance(surface.get("zones"), Mapping) else {}
    for part, material in sorted(zones.items(), key=lambda item: str(item[0])):
        if isinstance(part, str) and _IDENTIFIER_RE.match(part):
            lines.append(f"    zones.{part} = {_source_value(material, identifiers=True)}")
    lines.append("  }")
    return lines


def _interfaces_block_lines(interfaces: Mapping[str, list[Any]]) -> list[str]:
    lines = ["    interfaces {"]
    for key in ("sockets", "pivots", "anchors"):
        values = _dedupe_identifiers(interfaces.get(key, []))
        if values:
            lines.append(f"      {key} = {_source_array(values, identifiers=True)}")
    connections = _dedupe_connections(interfaces.get("connections", []))
    if connections:
        lines.append(f"      connections = [{', '.join(_connection_call(value) for value in connections)}]")
    lines.append("    }")
    return lines


def _connection_call(value: Any) -> str:
    if isinstance(value, str):
        if "->" in value:
            source, target = value.split("->", 1)
            payload: Mapping[str, Any] = {
                "source": source.strip(),
                "target": target.strip(),
                "relation": "connects_to",
            }
        else:
            payload = {"source": value, "target": "", "relation": "connects_to"}
    elif isinstance(value, Mapping):
        payload = value
    else:
        payload = {"source": str(value), "target": "", "relation": "connects_to"}
    args: list[str] = []
    for key in ("id", "source", "target", "relation", "socket_type", "compat_kind", "clearance", "snap_grid"):
        item = payload.get(key)
        if item is None or item == "":
            continue
        args.append(f"{key}: {_source_value(item, identifiers=True)}")
    return f"connection({', '.join(args)})"


def _asset_scale(objects: list[Mapping[str, Any]]) -> str:
    scales: list[float] = []
    for obj in objects:
        transform = obj.get("transform")
        if not isinstance(transform, Mapping):
            continue
        raw_scale = transform.get("scale")
        if isinstance(raw_scale, list):
            scales.extend(float(value) for value in raw_scale if isinstance(value, int | float) and value > 0)
    if not scales:
        return "1"
    return f"{max(scales):.3f}".rstrip("0").rstrip(".")


def _negative_tokens(asset_kind: str) -> list[str]:
    if asset_kind == "env_module":
        return ["free_floating", "single_prop_only"]
    if asset_kind == "mechanical_assembly":
        return ["nonfunctional_shape", "ambiguous_mechanism"]
    return ["unscaled", "unplaceable"]


def _instancing_metadata(task: Mapping[str, Any]) -> dict[str, Any]:
    object_ids = [str(object_id) for object_id in task.get("object_ids", []) if isinstance(object_id, str)]
    return {
        "instance_friendly": len(object_ids) > 1 and not bool(task.get("requires_unique_build", False)),
        "object_count": len(object_ids),
        "requires_unique_build": bool(task.get("requires_unique_build", False)),
        "uniqueness_reasons": list(task.get("uniqueness_reasons", []))
        if isinstance(task.get("uniqueness_reasons"), list)
        else [],
    }


def _asset_name(source_ref: str, cache_key: str) -> str:
    return f"{_slug(source_ref, fallback='scene_asset')}_{_fingerprint(cache_key, size=8)}"


def _slug(value: str, *, fallback: str) -> str:
    slug = _NON_IDENTIFIER_RE.sub("_", value.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    return slug[:72].rstrip("_") or fallback


def _fingerprint(value: str, *, size: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:size]


def _seed_from_key(value: str) -> int:
    return int(_fingerprint(value, size=8), 16)


def _source_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _source_array(values: list[Any], *, identifiers: bool = False) -> str:
    items: list[str] = []
    for value in values:
        if identifiers and isinstance(value, str) and _IDENTIFIER_RE.match(value):
            items.append(value)
        else:
            items.append(json.dumps(value, ensure_ascii=True))
    return "[" + ", ".join(items) + "]"


def _source_value(value: Any, *, identifiers: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return _source_array(value, identifiers=identifiers)
    if identifiers and isinstance(value, str) and _IDENTIFIER_RE.match(value):
        return value
    return json.dumps(str(value), ensure_ascii=True)


def _hex_to_rgb(value: Any) -> list[int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return None
    return [int(value[index : index + 2], 16) for index in (1, 3, 5)]


def _number_or_default(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def _comment_value(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ")


def _package_path(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if target != root_resolved and root_resolved not in target.parents:
        raise SceneMaterializeError(
            [
                {
                    "code": "SM1903",
                    "name": "generated_asset_path_escape",
                    "severity": "error",
                    "phase": "scene_materialization_write",
                    "path": relative_path,
                    "message": "Generated asset source path escapes the materialization output directory.",
                }
            ]
        )
    return target


def _has_error_diagnostic(diagnostics: list[dict[str, Any]]) -> bool:
    return any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)


__all__ = [
    "SCENE_MATERIALIZATION_CONTRACT",
    "SCENE_MATERIALIZATION_SCHEMA_FILENAME",
    "SCENE_MATERIALIZATION_VERSION",
    "SceneMaterializeError",
    "materialize_scene_assets",
    "validate_scene_materialization_manifest_payload",
]
