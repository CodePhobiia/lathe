"""Creative grammar controls for biome, faction, era, genre, and style intent."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "industrial": {
        "shape": {
            "style_pack": "industrial_hero",
            "structural_profile": "gantry",
            "route_structure": "service_trench",
            "edge_treatment": "chamfered",
            "panelization": 1.20,
            "greeble_density": 1.15,
            "trim_density": 1.10,
        },
        "surface": {
            "material_layers": ["painted_steel", "bare_metal", "rubber"],
            "story_decals": ["service_number", "hazard_stripe", "edge_rub"],
            "wear_story": "field_used",
            "wear_level": 0.54,
        },
    },
    "brutalist": {
        "shape": {
            "style_pack": "architectural_world",
            "facade_style": "brutalist",
            "structural_profile": "buttressed",
            "roof_style": "flat",
            "edge_hardness": "hard",
            "panelization": 1.10,
        },
        "surface": {
            "material_layers": ["concrete", "weathered_steel", "urban_grime"],
            "story_decals": ["water_stain", "painted_number", "edge_grime"],
            "wear_story": "inhabited",
            "wear_level": 0.46,
        },
    },
    "cyberpunk": {
        "shape": {
            "style_pack": "sleek_sci_fi",
            "path_profile": "s_curve",
            "structural_profile": "truss",
            "facade_style": "connected_facade",
            "edge_treatment": "soft",
            "ridge_density": 1.20,
        },
        "surface": {
            "material_layers": ["ceramic_composite", "brushed_aluminum", "signal_glass", "emissive_panel"],
            "story_decals": ["calibration_id", "neon_wayfinding", "thin_color_bar"],
            "markings": ["neon_lane", "access_glyph"],
            "wear_story": "prototype",
            "wear_level": 0.22,
        },
    },
    "sci_fi": {
        "shape": {
            "style_pack": "sleek_sci_fi",
            "structural_profile": "truss",
            "edge_treatment": "soft",
            "module_count": 2,
            "radial_detail_repeats": 6,
        },
        "surface": {
            "material_layers": ["ceramic_composite", "brushed_aluminum", "signal_glass"],
            "story_decals": ["calibration_id", "thin_color_bar"],
            "wear_story": "prototype",
            "wear_level": 0.18,
        },
    },
    "battle_worn": {
        "shape": {
            "style_pack": "battle_worn_field",
            "structural_profile": "fortified",
            "edge_treatment": "guarded",
            "outset_depth": 1.10,
            "attachment_count": 5,
        },
        "surface": {
            "material_layers": ["chipped_paint", "bare_metal", "grime"],
            "story_decals": ["scrape_cluster", "operator_label", "paint_chip_stripe"],
            "wear_story": "battle_worn",
            "wear_level": 0.80,
        },
    },
    "arcane": {
        "shape": {
            "style_pack": "arcane_luxury",
            "roof_style": "dome",
            "facade_style": "gothic",
            "structural_profile": "buttressed",
            "path_profile": "curve",
            "radial_detail_repeats": 8,
        },
        "surface": {
            "material_layers": ["worn_brass", "dark_wood", "inset_glass"],
            "story_decals": ["etched_runes", "edge_rub", "patina_marks"],
            "wear_story": "ancient",
            "wear_level": 0.48,
        },
    },
    "architectural": {
        "shape": {
            "style_pack": "architectural_world",
            "structural_profile": "facade_grid",
            "facade_style": "grid",
            "detail_motifs": ["arch_frame", "column_set", "structural_frame"],
        },
        "surface": {
            "material_layers": ["stone", "painted_metal", "glass"],
            "story_decals": ["wayfinding_mark", "painted_number", "edge_grime"],
            "wear_story": "inhabited",
            "wear_level": 0.36,
        },
    },
    "workshop": {
        "shape": {
            "style_pack": "vehicle_workshop",
            "structural_profile": "gantry",
            "route_structure": "service_trench",
            "module_count": 3,
            "attachment_count": 4,
        },
        "surface": {
            "material_layers": ["painted_steel", "rubber", "oil_dark_metal"],
            "story_decals": ["warning_label", "scrape_cluster", "service_stencil"],
            "wear_story": "worked_hard",
            "wear_level": 0.72,
        },
    },
}

_BIOME_PRESETS: dict[str, dict[str, Any]] = {
    "forest": {
        "shape": {"biome": "forest", "path_profile": "curve", "structural_profile": "covered"},
        "surface": {"material_layers": ["moss", "leaf_litter", "weathered_wood"], "story_decals": ["moss_patch", "leaf_litter"]},
    },
    "desert": {
        "shape": {"biome": "desert", "path_profile": "meander", "structural_profile": "curbed"},
        "surface": {"material_layers": ["sand", "sun_bleached_stone", "dust"], "story_decals": ["sand_drift", "sun_fade"]},
    },
    "swamp": {
        "shape": {"biome": "swamp", "path_profile": "meander", "structural_profile": "service_trench"},
        "surface": {"material_layers": ["algae", "wet_stone", "mud"], "story_decals": ["algae_streak", "waterline_silt"]},
    },
    "volcanic": {
        "shape": {"biome": "volcanic", "path_profile": "zigzag", "structural_profile": "barrier"},
        "surface": {"material_layers": ["basalt", "ash", "scorched_metal"], "story_decals": ["ash_streak", "heat_discoloration"]},
    },
    "urban": {
        "shape": {"biome": "urban", "structural_profile": "curbed", "facade_style": "connected_facade"},
        "surface": {"material_layers": ["concrete", "painted_metal", "urban_grime"], "story_decals": ["painted_number", "edge_grime"]},
    },
}

_FACTION_PRESETS: dict[str, dict[str, Any]] = {
    "military": {
        "shape": {"structural_profile": "fortified", "edge_treatment": "guarded", "support_profile": "truss"},
        "surface": {"faction_marks": ["unit_stencil", "hazard_chevron"], "markings": ["serial_number"], "wear_story": "battle_worn"},
    },
    "corporate": {
        "shape": {"style_pack": "sleek_sci_fi", "facade_style": "clean_grid", "edge_treatment": "soft"},
        "surface": {"faction_marks": ["brand_stripe", "access_tier_mark"], "markings": ["thin_color_bar"], "wear_story": "maintained"},
    },
    "civic": {
        "shape": {"style_pack": "architectural_world", "facade_style": "public_grid", "structural_profile": "facade_grid"},
        "surface": {"faction_marks": ["wayfinding_mark", "district_number"], "markings": ["painted_number"], "wear_story": "inhabited"},
    },
    "nomad": {
        "shape": {"path_profile": "meander", "structural_profile": "patched", "edge_treatment": "rounded"},
        "surface": {"faction_marks": ["tribal_mark", "route_knot"], "material_layers": ["patched_canvas", "weathered_wood", "worn_metal"], "wear_story": "field_used"},
    },
    "royal": {
        "shape": {"style_pack": "arcane_luxury", "facade_style": "ornate", "roof_style": "dome"},
        "surface": {"faction_marks": ["crest_emblem", "gilded_line"], "material_layers": ["worn_brass", "polished_stone", "inset_glass"], "wear_story": "ceremonial"},
    },
    "alien": {
        "shape": {"style_pack": "sleek_sci_fi", "path_profile": "curve", "structural_profile": "organic_rib", "edge_treatment": "soft"},
        "surface": {"faction_marks": ["glyph_cluster", "biolume_stripe"], "material_layers": ["ceramic_composite", "signal_glass", "emissive_panel"], "wear_story": "otherworldly"},
    },
}

_TOKEN_ALIASES = {
    "science_fiction": "sci_fi",
    "scifi": "sci_fi",
    "sci-fi": "sci_fi",
    "fantasy": "arcane",
    "magical": "arcane",
    "militarized": "military",
    "army": "military",
    "company": "corporate",
    "city": "urban",
    "industrial_access": "industrial",
    "factory": "industrial",
    "garage": "workshop",
    "vehicle": "workshop",
}


def creative_grammar_from_asset(
    asset: Mapping[str, Any],
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive creative controls from an asset declaration."""
    intent = asset.get("intent") if isinstance(asset.get("intent"), Mapping) else {}
    surface = asset.get("surface") if isinstance(asset.get("surface"), Mapping) else {}
    experimental = asset.get("experimental") if isinstance(asset.get("experimental"), Mapping) else {}
    art_direction = experimental.get("art_direction") if isinstance(experimental.get("art_direction"), Mapping) else {}
    tokens = _tokens_from_values(
        family,
        asset.get("kind"),
        intent.get("role"),
        intent.get("style"),
        intent.get("materials"),
        surface.get("materials"),
        surface.get("patterns"),
        shape_controls,
        art_direction,
    )
    return creative_grammar_for_tokens(tokens, family=family, shape_controls=shape_controls, surface=surface)


def creative_grammar_for_scene(
    *,
    source: Mapping[str, Any],
    objects: Sequence[Mapping[str, Any]],
    task: Mapping[str, Any] | None,
    family: str | None,
    shape_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive creative controls from scene-source objects."""
    values: list[Any] = [family, source.get("kind"), source.get("ref"), source.get("source_family")]
    for key in ("style", "styles", "theme", "genre", "era", "biome", "faction", "material_intent"):
        values.append(source.get(key))
    for obj in objects:
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
            ]
        )
        state = obj.get("state") if isinstance(obj.get("state"), Mapping) else {}
        values.append(state)
    overrides = task.get("asset_overrides") if isinstance(task, Mapping) and isinstance(task.get("asset_overrides"), Mapping) else {}
    state_overrides = overrides.get("state") if isinstance(overrides.get("state"), Mapping) else {}
    values.append(state_overrides)
    tokens = _tokens_from_values(*values, shape_controls)
    return creative_grammar_for_tokens(tokens, family=family or "", shape_controls=shape_controls, surface={})


def creative_grammar_for_tokens(
    tokens: Sequence[str],
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None = None,
    surface: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve tokens into concrete shape and surface controls."""
    token_set = {_alias(token) for token in tokens if token}
    derived_shape: dict[str, Any] = {}
    derived_surface: dict[str, Any] = {}
    matched: list[str] = []
    for token in sorted(token_set):
        for table in (_STYLE_PRESETS, _BIOME_PRESETS, _FACTION_PRESETS):
            preset = table.get(token)
            if preset:
                matched.append(token)
                _merge_shape_defaults(derived_shape, preset.get("shape", {}))
                _merge_surface_defaults(derived_surface, preset.get("surface", {}))
    _merge_shape_defaults(derived_shape, _family_defaults(family, token_set))
    _merge_surface_defaults(derived_surface, _material_intent_surface(token_set))

    base_shape = dict(shape_controls or {})
    shape = dict(derived_shape)
    shape.update(base_shape)
    source_surface = dict(surface or {})
    surface_out = dict(derived_surface)
    _merge_surface_defaults(surface_out, source_surface, authored_wins=True)
    if matched:
        shape.setdefault("creative_grammar", "_".join(matched[:4]))
        shape.setdefault("style_intensity", 1.0)
        shape.setdefault("creative_tags", sorted(token_set)[:16])
    return {
        "shape_controls": shape,
        "surface": surface_out,
        "summary": {
            "tokens": sorted(token_set),
            "matched_presets": sorted(set(matched)),
            "family": family,
        },
    }


def _family_defaults(family: str, tokens: set[str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    if family == "procedural_building":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"arcane", "royal", "gothic"}:
            defaults.update({"roof_style": "dome", "facade_style": "gothic", "tower_count": 2})
        elif tokens & {"industrial", "brutalist", "military"}:
            defaults.update({"roof_style": "flat", "facade_style": "fortified", "column_count": 4})
    elif family == "procedural_road":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"urban", "corporate", "civic"}:
            defaults.update({"road_edge_count": 2, "crosswalk_count": 2, "structural_profile": "curbed"})
        if tokens & {"desert", "forest", "swamp"}:
            defaults.update({"landform": "path", "path_profile": "meander"})
    elif family == "procedural_bridge":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"industrial", "military"}:
            defaults.update({"structural_profile": "truss", "support_count": 4})
        if tokens & {"arcane", "royal"}:
            defaults.update({"structural_profile": "covered", "route_structure": "covered"})
    elif family == "procedural_access":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"industrial", "military", "workshop"}:
            defaults.update({"access_style": "industrial", "structural_profile": "gantry", "guardrail_count": 4})
        if tokens & {"cyberpunk", "sci_fi", "corporate"}:
            defaults.update({"access_style": "sleek", "structural_profile": "truss", "emissive_count": 2})
    elif family == "procedural_infrastructure":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"industrial", "workshop"}:
            defaults.update({"service_type": "mixed", "support_count": 4, "route_structure": "service_trench"})
        if tokens & {"cyberpunk", "sci_fi", "corporate"}:
            defaults.update({"service_type": "data", "conduit_count": 3, "cable_tray_count": 2})
    elif family == "procedural_terrain":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"forest", "swamp", "desert", "volcanic"}:
            defaults.update({"landform": "terrain_patch", "path_count": 1, "terrain_platforms": 1})
    elif family == "procedural_furniture":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"royal", "arcane"}:
            defaults.update({"furniture_style": "ornate", "leg_count": 4, "cushion_count": 2})
        elif tokens & {"industrial", "workshop"}:
            defaults.update({"furniture_style": "utility", "shelf_count": 2, "drawer_count": 2})
    elif family == "procedural_vehicle":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"military", "battle_worn"}:
            defaults.update({"drive_type": "tracked", "turret_count": 1, "armor_panel_count": 4})
        elif tokens & {"sci_fi", "cyberpunk"}:
            defaults.update({"drive_type": "hover", "rotor_count": 4, "wing_count": 2})
    elif family == "procedural_setpiece":  # no-family-dispatch: per-family creative grammar templates; lift each into a StyleKnowledge + CompositionPolicy pair so the alias selects the right pair without explicit family branching
        if tokens & {"military", "battle_worn"}:
            defaults.update({"structural_profile": "fortified", "barrier_count": 6, "tower_count": 2})
        if tokens & {"industrial", "workshop"}:
            defaults.update({"structural_profile": "gantry", "pipe_count": 4, "catwalk_count": 3})
        if tokens & {"urban", "civic", "corporate"}:
            defaults.update({"road_segment_count": 3, "sign_count": 4, "facade_style": "connected_facade"})
        if tokens & {"arcane", "royal"}:
            defaults.update({"roof_style": "dome", "facade_style": "ornate", "column_count": 8})
    return defaults


def _material_intent_surface(tokens: set[str]) -> dict[str, Any]:
    surface: dict[str, Any] = {}
    if tokens & {"metal", "steel", "industrial", "military"}:
        _merge_surface_defaults(surface, {"materials": ["painted_steel", "bare_metal"], "material_layers": ["edge_wear"]})
    if tokens & {"glass", "neon", "cyberpunk", "sci_fi"}:
        _merge_surface_defaults(surface, {"materials": ["signal_glass", "emissive_panel"], "story_decals": ["thin_color_bar"]})
    if tokens & {"wood", "forest", "nomad", "arcane"}:
        _merge_surface_defaults(surface, {"materials": ["weathered_wood", "dark_wood"], "material_layers": ["edge_dust"]})
    if tokens & {"stone", "brutalist", "civic", "royal"}:
        _merge_surface_defaults(surface, {"materials": ["stone", "concrete"], "story_decals": ["edge_grime"]})
    return surface


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
                    "furniture_style",
                    "district_style",
                    "landform",
                }:
                    tokens.extend(_tokens_from_values(item))
        elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
            for item in value:
                tokens.extend(_tokens_from_values(item))
    return list(dict.fromkeys(_alias(token) for token in tokens if token))


def _split_tokens(value: str) -> list[str]:
    text = value.lower().replace("-", "_").replace("/", "_").replace(",", " ")
    raw = []
    for chunk in text.split():
        raw.append(chunk.strip("_"))
        raw.extend(part for part in chunk.split("_") if part)
    return [item for item in raw if item]


def _merge_shape_defaults(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = _copy_value(value)
        elif isinstance(target.get(key), list):
            target[key] = list(dict.fromkeys([*target[key], *_as_list(value)]))


def _merge_surface_defaults(target: dict[str, Any], source: Mapping[str, Any], *, authored_wins: bool = False) -> None:
    for key, value in source.items():
        if key in {"materials", "material_layers", "layers", "story_decals", "decals", "faction_marks", "markings", "patterns"}:
            existing = [str(item) for item in _as_list(target.get(key))]
            incoming = [str(item) for item in _as_list(value)]
            target[key] = list(dict.fromkeys([*(existing if authored_wins else incoming), *(incoming if authored_wins else existing)]))
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


def _alias(token: str) -> str:
    return _TOKEN_ALIASES.get(token, token)
