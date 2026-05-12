"""Object grammar controls for high-level archetype composition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_ARCHETYPE_ORDER = (
    "outpost",
    "market",
    "fortress",
    "factory",
    "harbor",
    "hangar",
    "temple",
)

_TOKEN_ALIASES = {
    "bazaar": "market",
    "marketplace": "market",
    "vendor": "market",
    "stall": "market",
    "citadel": "fortress",
    "fort": "fortress",
    "stronghold": "fortress",
    "castle": "fortress",
    "command": "outpost",
    "checkpoint": "outpost",
    "watchpost": "outpost",
    "camp": "outpost",
    "compound": "outpost",
    "harbour": "harbor",
    "dock": "harbor",
    "dockyard": "harbor",
    "marina": "harbor",
    "port": "harbor",
    "shipyard": "harbor",
    "airfield": "hangar",
    "airbase": "hangar",
    "runway": "hangar",
    "shrine": "temple",
    "sanctuary": "temple",
    "cathedral": "temple",
    "monastery": "temple",
    "plant": "factory",
    "workshop": "factory",
    "foundry": "factory",
    "refinery": "factory",
}

_ARCHETYPE_PRESETS: dict[str, dict[str, Any]] = {
    "outpost": {
        "systems": [
            "terrain_pad",
            "command_building",
            "watchtower_ring",
            "perimeter_barriers",
            "access_walkways",
            "utility_runs",
            "entry_road",
            "supply_props",
        ],
        "shape": {
            "setpiece_layout": "defensive_cluster",
            "setpiece_density": 0.72,
            "structure_count": 3,
            "building_count": 3,
            "tower_count": 3,
            "fence_count": 8,
            "gate_count": 1,
            "barrier_count": 6,
            "street_crate_count": 6,
            "road_segment_count": 2,
            "branch_count": 1,
            "catwalk_count": 2,
            "platform_count": 3,
            "guardrail_count": 8,
            "pipe_count": 2,
            "conduit_count": 2,
            "junction_box_count": 2,
            "vehicle_count": 1,
            "interior_module_count": 1,
            "furniture_cluster_count": 1,
            "child_socket_count": 4,
            "terrain_platforms": 2,
            "structural_profile": "fortified",
            "path_profile": "zigzag",
            "facade_style": "fortified",
            "roof_style": "flat",
            "style_pack": "battle_worn_field",
        },
        "surface": {
            "materials": ["painted_steel", "concrete", "asphalt", "warning_paint", "urban_grime"],
            "material_layers": ["painted_steel", "edge_wear", "dust", "warning_paint"],
            "story_decals": ["unit_stencil", "hazard_chevron", "supply_mark", "route_arrow"],
            "faction_marks": ["unit_stencil", "checkpoint_id"],
            "wear_story": "battle_worn",
            "wear_level": 0.62,
        },
    },
    "market": {
        "systems": [
            "plaza_ground",
            "stall_rows",
            "kiosk_cluster",
            "pedestrian_paths",
            "canopies",
            "signage",
            "street_lights",
            "service_crates",
        ],
        "shape": {
            "setpiece_layout": "plaza_market",
            "setpiece_density": 0.82,
            "structure_count": 4,
            "building_count": 2,
            "lot_count": 4,
            "stall_count": 10,
            "kiosk_count": 3,
            "awning_count": 8,
            "sign_count": 8,
            "streetlight_count": 4,
            "bench_count": 3,
            "street_crate_count": 8,
            "interior_module_count": 1,
            "furniture_cluster_count": 4,
            "foliage_cluster_count": 1,
            "child_socket_count": 5,
            "road_segment_count": 3,
            "crosswalk_count": 2,
            "branch_count": 2,
            "path_profile": "meander",
            "structural_profile": "curbed",
            "facade_style": "public_grid",
            "style_pack": "architectural_world",
        },
        "surface": {
            "materials": ["painted_metal", "canvas", "finished_wood", "concrete", "asphalt"],
            "material_layers": ["painted_metal", "canvas", "urban_grime", "edge_wear"],
            "story_decals": ["vendor_label", "awning_fade", "street_grime", "painted_number"],
            "markings": ["wayfinding_mark", "price_board"],
            "wear_story": "inhabited",
            "wear_level": 0.44,
        },
    },
    "fortress": {
        "systems": [
            "fortified_keep",
            "curtain_wall",
            "gatehouse",
            "tower_ring",
            "courtyard",
            "patrol_walkways",
            "bridge_entry",
            "rocky_terrain",
        ],
        "shape": {
            "setpiece_layout": "walled_courtyard",
            "setpiece_density": 0.86,
            "structure_count": 5,
            "building_count": 3,
            "tower_count": 6,
            "wall_count": 8,
            "fence_count": 8,
            "gate_count": 2,
            "road_segment_count": 2,
            "span_count": 1,
            "catwalk_count": 4,
            "walkway_count": 4,
            "guardrail_count": 10,
            "interior_module_count": 2,
            "furniture_cluster_count": 1,
            "child_socket_count": 6,
            "terrain_platforms": 3,
            "ridge_count": 2,
            "structural_profile": "buttressed",
            "facade_style": "fortified",
            "roof_style": "dome",
            "style_pack": "architectural_world",
        },
        "surface": {
            "materials": ["stone", "weathered_steel", "concrete", "roof_tile", "urban_grime"],
            "material_layers": ["stone", "dust", "edge_wear", "moss"],
            "story_decals": ["water_stain", "banner_mark", "edge_grime", "crack_lines"],
            "faction_marks": ["crest_emblem", "gate_sigils"],
            "wear_story": "ancient",
            "wear_level": 0.64,
        },
    },
    "factory": {
        "systems": [
            "production_hall",
            "service_yard",
            "machine_line",
            "conveyor_spine",
            "pipe_racks",
            "catwalk_network",
            "loading_road",
            "utility_boxes",
        ],
        "shape": {
            "setpiece_layout": "industrial_yard",
            "setpiece_density": 0.88,
            "structure_count": 4,
            "building_count": 3,
            "floor_count": 2,
            "bay_count": 5,
            "chimney_count": 3,
            "conveyor_count": 3,
            "machine_count": 4,
            "pipe_count": 6,
            "duct_count": 4,
            "conduit_count": 5,
            "cable_tray_count": 4,
            "junction_box_count": 4,
            "transformer_count": 2,
            "machine_count": 4,
            "interior_module_count": 1,
            "child_socket_count": 7,
            "catwalk_count": 4,
            "gantry_count": 3,
            "platform_count": 4,
            "road_segment_count": 3,
            "turnout_count": 2,
            "structural_profile": "gantry",
            "path_profile": "service_trench",
            "facade_style": "industrial_grid",
            "style_pack": "industrial_hero",
        },
        "surface": {
            "materials": ["industrial_steel", "painted_metal", "bare_metal", "rubber", "grease", "warning_paint"],
            "material_layers": ["industrial_steel", "bare_metal", "grease", "hazard_paint"],
            "story_decals": ["hazard_stripe", "flow_arrow", "service_number", "oil_stain"],
            "wear_story": "worked_hard",
            "wear_level": 0.68,
        },
    },
    "harbor": {
        "systems": [
            "water_edge",
            "dock_spines",
            "pier_grid",
            "moored_boats",
            "cargo_yard",
            "warehouse",
            "service_roads",
            "shore_utilities",
        ],
        "shape": {
            "setpiece_layout": "waterfront_grid",
            "setpiece_density": 0.80,
            "structure_count": 4,
            "building_count": 2,
            "dock_count": 4,
            "pier_count": 4,
            "walkway_count": 4,
            "railing_count": 8,
            "boat_count": 3,
            "cargo_hold_count": 3,
            "street_crate_count": 8,
            "machine_count": 1,
            "child_socket_count": 7,
            "pipe_count": 3,
            "road_segment_count": 2,
            "water_count": 1,
            "path_profile": "branching",
            "structural_profile": "truss",
            "facade_style": "warehouse",
            "style_pack": "industrial_hero",
        },
        "surface": {
            "materials": ["marine_paint", "deck_wood", "weathered_steel", "salt_wear", "concrete", "shallow_water"],
            "material_layers": ["marine_paint", "salt_wear", "deck_wood", "urban_grime"],
            "story_decals": ["waterline_wear", "cargo_stencil", "salt_streaks", "dock_number"],
            "wear_story": "field_used",
            "wear_level": 0.56,
        },
    },
    "hangar": {
        "systems": [
            "hangar_shell",
            "wide_bay_door",
            "runway_apron",
            "maintenance_racks",
            "fuel_lines",
            "gantry_access",
            "service_vehicles",
            "lighting_grid",
        ],
        "shape": {
            "setpiece_layout": "airfield_apron",
            "setpiece_density": 0.76,
            "structure_count": 3,
            "building_count": 2,
            "bay_count": 6,
            "door_count": 3,
            "road_segment_count": 4,
            "lane_count": 2,
            "turnout_count": 2,
            "pipe_count": 4,
            "conduit_count": 4,
            "fuel_line_count": 3,
            "gantry_count": 2,
            "platform_count": 3,
            "streetlight_count": 6,
            "vehicle_count": 2,
            "machine_count": 2,
            "interior_module_count": 1,
            "child_socket_count": 6,
            "wing_count": 2,
            "rotor_count": 2,
            "structural_profile": "truss",
            "path_profile": "straight",
            "facade_style": "wide_bay",
            "roof_style": "arched",
            "style_pack": "vehicle_workshop",
        },
        "surface": {
            "materials": ["painted_steel", "concrete", "rubber_tread", "fuel_stain", "emissive_panel"],
            "material_layers": ["painted_steel", "concrete", "edge_wear", "fuel_stain"],
            "story_decals": ["runway_marking", "hangar_number", "maintenance_label", "hazard_stripe"],
            "wear_story": "field_used",
            "wear_level": 0.48,
        },
    },
    "temple": {
        "systems": [
            "sanctuary_hall",
            "column_court",
            "ceremonial_path",
            "spire_or_dome",
            "altar_platform",
            "garden_terrain",
            "ornament_markers",
            "processional_steps",
        ],
        "shape": {
            "setpiece_layout": "ritual_axis",
            "setpiece_density": 0.74,
            "structure_count": 4,
            "building_count": 2,
            "column_count": 10,
            "tower_count": 3,
            "dome_count": 1,
            "stair_count": 4,
            "road_segment_count": 1,
            "path_count": 3,
            "terrain_platforms": 3,
            "ridge_count": 1,
            "sign_count": 3,
            "interior_module_count": 2,
            "furniture_cluster_count": 2,
            "foliage_cluster_count": 3,
            "child_socket_count": 5,
            "radial_detail_repeats": 8,
            "structural_profile": "buttressed",
            "path_profile": "curve",
            "facade_style": "ornate",
            "roof_style": "dome",
            "style_pack": "arcane_luxury",
        },
        "surface": {
            "materials": ["polished_stone", "worn_brass", "inset_glass", "moss", "dust"],
            "material_layers": ["polished_stone", "worn_brass", "dust", "moss"],
            "story_decals": ["etched_runes", "patina_marks", "ceremonial_path_wear", "edge_rub"],
            "faction_marks": ["crest_emblem", "ritual_glyph"],
            "wear_story": "ancient",
            "wear_level": 0.52,
        },
    },
}

_GENERIC_SETPIECE = {
    "systems": ["terrain_pad", "primary_structure", "route_spine", "access_nodes", "utility_runs", "prop_cluster"],
    "shape": {
        "object_archetype": "compound",
        "archetype": "compound",
        "setpiece_layout": "compound_cluster",
        "setpiece_density": 0.62,
        "structure_count": 3,
        "building_count": 2,
        "road_segment_count": 2,
        "access_count": 2,
        "infrastructure_count": 2,
        "prop_count": 4,
        "child_socket_count": 3,
        "terrain_platforms": 1,
        "structural_profile": "facade_grid",
    },
    "surface": {
        "materials": ["concrete", "painted_metal", "weathered_steel", "urban_grime"],
        "material_layers": ["concrete", "painted_metal", "edge_wear", "dust"],
        "story_decals": ["wayfinding_mark", "service_number", "edge_grime"],
        "wear_story": "used",
        "wear_level": 0.36,
    },
}


def object_grammar_from_asset(
    asset: Mapping[str, Any],
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive object-archetype controls from an asset declaration."""
    intent = asset.get("intent") if isinstance(asset.get("intent"), Mapping) else {}
    surface = asset.get("surface") if isinstance(asset.get("surface"), Mapping) else {}
    experimental = asset.get("experimental") if isinstance(asset.get("experimental"), Mapping) else {}
    art_direction = experimental.get("art_direction") if isinstance(experimental.get("art_direction"), Mapping) else {}
    tokens = _tokens_from_values(
        family,
        asset.get("kind"),
        intent.get("role"),
        intent.get("style"),
        intent.get("parts"),
        intent.get("materials"),
        surface.get("materials"),
        surface.get("patterns"),
        shape_controls,
        art_direction,
    )
    return object_grammar_for_tokens(tokens, family=family, shape_controls=shape_controls, surface=surface)


def object_grammar_for_scene(
    *,
    source: Mapping[str, Any],
    objects: Sequence[Mapping[str, Any]],
    task: Mapping[str, Any] | None,
    family: str | None,
    shape_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive object-archetype controls from scene-source objects."""
    values: list[Any] = [
        family,
        source.get("kind"),
        source.get("ref"),
        source.get("source_family"),
        source.get("archetype"),
        source.get("object_archetype"),
        source.get("setpiece"),
        source.get("style"),
        source.get("theme"),
        source.get("biome"),
        source.get("faction"),
    ]
    for obj in objects:
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        values.extend(
            [
                obj.get("role"),
                obj.get("name"),
                obj.get("semantic_tags"),
                obj.get("material_intent"),
                obj.get("style"),
                obj.get("theme"),
                obj.get("biome"),
                obj.get("faction"),
                state,
            ]
        )
    overrides = task.get("asset_overrides") if isinstance(task, Mapping) and isinstance(task.get("asset_overrides"), Mapping) else {}
    state_overrides = overrides.get("state") if isinstance(overrides.get("state"), Mapping) else {}
    values.append(state_overrides)
    tokens = _tokens_from_values(*values, shape_controls)
    return object_grammar_for_tokens(tokens, family=family or "", shape_controls=shape_controls, surface={})


def object_grammar_for_tokens(
    tokens: Sequence[str],
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None = None,
    surface: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve tokens into archetype, system, shape, and surface controls."""
    token_set = {_alias(token) for token in tokens if token}
    matched = [name for name in _ARCHETYPE_ORDER if name in token_set]
    derived_shape: dict[str, Any] = {}
    derived_surface: dict[str, Any] = {}
    systems: list[str] = []
    if not matched and family == "procedural_setpiece":  # no-family-dispatch: terminal-fallback heuristic that lets `procedural_setpiece` resolve to the compound archetype when no archetype tokens matched; migrate to an intent-tag check on `setpiece` once intent tags become a stable surface
        matched = ["compound"]
        _merge_shape_defaults(derived_shape, _GENERIC_SETPIECE["shape"])
        _merge_surface_defaults(derived_surface, _GENERIC_SETPIECE["surface"])
        systems.extend(_GENERIC_SETPIECE["systems"])
    for name in matched:
        preset = _ARCHETYPE_PRESETS.get(name)
        if not preset:
            continue
        systems.extend(str(item) for item in preset.get("systems", []) if item)
        _merge_shape_defaults(derived_shape, preset.get("shape", {}))
        _merge_surface_defaults(derived_surface, preset.get("surface", {}))
    if matched:
        primary = "compound" if matched == ["compound"] else matched[0]
        derived_shape.setdefault("object_archetype", primary)
        derived_shape.setdefault("archetype", primary)
        derived_shape.setdefault("setpiece_systems", _dedupe(systems))
        derived_shape.setdefault("archetype_system_count", len(_dedupe(systems)))
        derived_shape.setdefault("object_grammar", "_".join(matched[:4]))
    if family == "procedural_setpiece":  # no-family-dispatch: same procedural_setpiece terminal-fallback as above; migrate to an intent-tag check together with the earlier site
        _merge_shape_defaults(derived_shape, _setpiece_family_defaults(token_set))

    base_shape = dict(shape_controls or {})
    shape = dict(derived_shape)
    shape.update(base_shape)
    surface_out = dict(derived_surface)
    _merge_surface_defaults(surface_out, dict(surface or {}), authored_wins=True)
    return {
        "shape_controls": shape,
        "surface": surface_out,
        "summary": {
            "tokens": sorted(token_set),
            "matched_archetypes": matched,
            "object_archetype": shape.get("object_archetype", ""),
            "systems": _dedupe(systems),
            "family": family,
        },
    }


def _setpiece_family_defaults(tokens: set[str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "scene_composition": "multi_system_setpiece",
        "placement_count": 1,
    }
    if tokens & {"military", "battle_worn", "defensive"}:
        defaults.setdefault("structural_profile", "fortified")
        defaults.setdefault("barrier_count", 4)
        defaults.setdefault("vehicle_count", 1)
    if tokens & {"urban", "civic", "corporate"}:
        defaults.setdefault("road_segment_count", 3)
        defaults.setdefault("sign_count", 3)
        defaults.setdefault("furniture_cluster_count", 1)
    if tokens & {"industrial", "workshop"}:
        defaults.setdefault("pipe_count", 3)
        defaults.setdefault("catwalk_count", 2)
        defaults.setdefault("machine_count", 2)
    if tokens & {"vehicle", "rover", "truck", "car", "aircraft", "drone"}:
        defaults.setdefault("vehicle_count", 1)
    if tokens & {"boat", "ship", "vessel", "watercraft"}:
        defaults.setdefault("boat_count", 1)
    if tokens & {"machine", "machinery", "conveyor", "assembler"}:
        defaults.setdefault("machine_count", 1)
    if tokens & {"interior", "room", "hall", "chamber"}:
        defaults.setdefault("interior_module_count", 1)
    if tokens & {"furniture", "furnishing", "table", "chair", "bench"}:
        defaults.setdefault("furniture_cluster_count", 1)
    if tokens & {"forest", "desert", "swamp", "volcanic", "coastal"}:
        defaults.setdefault("terrain_platforms", 2)
        defaults.setdefault("path_count", 2)
        defaults.setdefault("foliage_cluster_count", 1)
    return defaults


def _tokens_from_values(*values: Any) -> list[str]:
    tokens: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            tokens.extend(_split_tokens(value))
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if key in {
                    "archetype",
                    "object_archetype",
                    "setpiece",
                    "scene_composition",
                    "setpiece_layout",
                    "style",
                    "styles",
                    "theme",
                    "genre",
                    "era",
                    "biome",
                    "habitat",
                    "faction",
                    "material_intent",
                    "loadout",
                    "family_loadout",
                    "vehicle_loadout",
                    "boat_loadout",
                    "vessel_loadout",
                    "weapon_loadout",
                    "tool_loadout",
                    "kit_style",
                    "visual_system",
                    "theme_pack",
                    "style_pack",
                    "style_packs",
                    "structural_profile",
                    "facade_style",
                    "access_style",
                    "district_style",
                    "landform",
                    "role",
                    "name",
                    "semantic_tags",
                }:
                    tokens.extend(_tokens_from_values(item))
        elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
            for item in value:
                tokens.extend(_tokens_from_values(item))
    return _dedupe(_alias(token) for token in tokens if token)


def _split_tokens(value: str) -> list[str]:
    text = value.lower().replace("-", "_").replace("/", "_").replace(",", " ")
    raw: list[str] = []
    for chunk in text.split():
        raw.append(chunk.strip("_"))
        raw.extend(part for part in chunk.split("_") if part)
    return [item for item in raw if item]


def _merge_shape_defaults(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = _copy_value(value)
        elif isinstance(target.get(key), list):
            target[key] = _dedupe([*target[key], *_as_list(value)])


def _merge_surface_defaults(target: dict[str, Any], source: Mapping[str, Any], *, authored_wins: bool = False) -> None:
    for key, value in source.items():
        if key in {"materials", "material_layers", "layers", "story_decals", "decals", "faction_marks", "markings", "patterns"}:
            existing = [str(item) for item in _as_list(target.get(key))]
            incoming = [str(item) for item in _as_list(value)]
            target[key] = _dedupe([*(existing if authored_wins else incoming), *(incoming if authored_wins else existing)])
        elif key in {"zones", "material_zones"} and isinstance(value, Mapping):
            zones = dict(target.get("zones", {})) if isinstance(target.get("zones"), Mapping) else {}
            for zone_key, zone_value in value.items():
                zones[str(zone_key)] = str(zone_value)
            target["zones"] = zones
        elif authored_wins:
            target[key] = _copy_value(value)
        else:
            target.setdefault(key, _copy_value(value))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _copy_value(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _dedupe(values: Sequence[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _alias(token: str) -> str:
    return _TOKEN_ALIASES.get(token, token)
