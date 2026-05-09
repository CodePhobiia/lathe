"""Surface grammar derivation from procedural family and world context."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .creative_grammar import creative_grammar_from_asset
from .fidelity import _tier_multipliers
from .object_grammar import object_grammar_from_asset


_ROUGHNESS_DELTA_CAP = 0.5
_NORMAL_DELTA_CAP = 0.45


def _scaled_delta(base: float, fidelity_tier: str, kind: str = "normal") -> float:
    """Scale a base delta value by fidelity tier with sqrt-softened multiplier.

    detail_density spans 0.7/1.0/1.35/2.2 across tiers; sqrt softens that to
    ~0.84/1.0/1.16/1.48 so visual deltas grow without going hyperreal at hero/
    cinematic tiers. Sign of base is preserved; magnitude is capped at the
    physical clamp for the channel (roughness within [0,1], normal map clip).
    """

    if not base:
        return 0.0
    try:
        mult = float(_tier_multipliers(fidelity_tier).get("detail_density", 1.0))
    except KeyError:
        mult = 1.0
    scaled = base * math.sqrt(max(0.0, mult))
    cap = _ROUGHNESS_DELTA_CAP if kind == "roughness" else _NORMAL_DELTA_CAP
    if scaled > cap:
        return cap
    if scaled < -cap:
        return -cap
    return scaled


def _scale_feature_deltas(feature: dict[str, Any], fidelity_tier: str) -> None:
    """In-place scale roughness/normal deltas of a feature dict by tier."""

    rough = float(feature.get("roughness_delta", 0.0) or 0.0)
    normal = float(feature.get("normal_delta", 0.0) or 0.0)
    if rough:
        feature["roughness_delta"] = _scaled_delta(rough, fidelity_tier, "roughness")
    if normal:
        feature["normal_delta"] = _scaled_delta(normal, fidelity_tier, "normal")


def _infer_fidelity_tier_from_asset(asset: dict[str, Any]) -> str:
    """Mirror ``infer_fidelity_profile`` thresholds without an AssetGraph.

    The presets here run in the surface stage where the materialized asset is
    the only context available; this avoids importing AssetGraph circularly.
    """

    validate = asset.get("validate", {}) if isinstance(asset.get("validate"), dict) else {}
    critic_name = str(validate.get("score") or "").lower()
    threshold = _number(validate.get("threshold"), 0.80)
    if "cinematic" in critic_name or threshold >= 0.92:
        return "cinematic"
    if "hero" in critic_name or threshold >= 0.86:
        return "hero"
    if threshold <= 0.78:
        return "blockout"
    return "game"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _token(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return text or default


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


def _present(value: Any) -> bool:
    return value not in ("", None) and value != [] and value != {}


def _feature(
    kind: str,
    targets: list[str],
    *,
    profile: str = "",
    material: str = "",
    roughness_delta: float = 0.0,
    normal_delta: float = 0.0,
    wear_delta: float = 0.0,
    basecolor_mix: list[int] | None = None,
    mix: float = 0.0,
    emissive: list[int] | None = None,
    wear_layer: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": kind,
        "targets": targets,
        "profile": profile,
        "material": material,
        "roughness_delta": roughness_delta,
        "normal_delta": normal_delta,
        "wear_delta": wear_delta,
        "mix": mix,
    }
    if basecolor_mix:
        out["basecolor_mix"] = list(basecolor_mix)
    if emissive:
        out["emissive"] = list(emissive)
    if wear_layer:
        out["wear_layer"] = wear_layer
    return out


_LANDFORM_PRESETS: dict[str, dict[str, Any]] = {
    "terrain_patch": {
        "materials": ["soil", "grass", "moss", "stone"],
        "material_layers": ["soil", "grass", "moss"],
        "story_decals": ["ground_mottle", "moss_patch"],
        "story_targets": ["terrain_patch", "terrain"],
        "wear_story": "weathered",
        "wear_level": 0.34,
        "zones": {"terrain": "soil", "terrain_patch": "soil", "terrace": "moss", "path": "packed_soil"},
        "patterns": ["soil_variation", "grass_mottle"],
        "features": [
            _feature("soil_variation", ["terrain", "patch", "ground"], profile="natural_ground", normal_delta=0.08),
            _feature("moss_growth", ["terrace", "rim", "edge"], profile="grass_mottle", material="moss", basecolor_mix=[70, 110, 64], mix=0.18),
        ],
    },
    "ridge": {
        "materials": ["stratified_stone", "lichen", "soil"],
        "material_layers": ["stratified_stone", "lichen", "dust"],
        "story_decals": ["lichen_patch", "erosion_lines"],
        "story_targets": ["ridge", "cliff"],
        "wear_story": "weathered",
        "wear_level": 0.56,
        "zones": {"ridge": "stratified_stone", "cliff": "stratified_stone", "terrain": "soil"},
        "patterns": ["strata_banding", "erosion_streaks"],
        "features": [
            _feature("strata_banding", ["ridge", "cliff"], profile="stratified_stone", normal_delta=0.16, wear_delta=0.12, wear_layer="dirt_grime"),
            _feature("lichen_growth", ["ridge", "edge"], profile="grass_mottle", material="lichen", basecolor_mix=[106, 132, 82], mix=0.16),
        ],
    },
    "cliff": {
        "materials": ["stratified_stone", "wet_stone", "talus"],
        "material_layers": ["stratified_stone", "wet_stone", "dust"],
        "story_decals": ["crack_lines", "talus_scree"],
        "story_targets": ["cliff", "terrain"],
        "wear_story": "weathered",
        "wear_level": 0.62,
        "zones": {"cliff": "stratified_stone", "ridge": "stratified_stone", "terrain": "talus"},
        "patterns": ["strata_banding", "cracked_stone"],
        "features": [
            _feature("cracked_stone", ["cliff", "face"], profile="cracked_stone", normal_delta=0.20, wear_delta=0.16, wear_layer="micro_scratches"),
            _feature("talus_scree", ["terrain", "base"], profile="rock_scree", material="talus", roughness_delta=0.08, normal_delta=0.10),
        ],
    },
    "clearing": {
        "materials": ["short_grass", "packed_soil", "leaf_litter"],
        "material_layers": ["short_grass", "packed_soil", "leaf_litter"],
        "story_decals": ["foot_scuff", "leaf_litter"],
        "story_targets": ["clearing", "terrain"],
        "wear_story": "used",
        "wear_level": 0.30,
        "zones": {"clearing": "short_grass", "terrain": "short_grass", "path": "packed_soil"},
        "patterns": ["grass_mottle", "leaf_litter"],
        "features": [
            _feature("trampled_grass", ["clearing", "path"], profile="grass_mottle", material="packed_soil", basecolor_mix=[92, 72, 42], mix=0.20, wear_delta=0.08),
            _feature("leaf_litter", ["clearing", "rim"], profile="leaf_litter", material="leaf_litter", basecolor_mix=[124, 84, 38], mix=0.15),
        ],
    },
    "platform": {
        "materials": ["worn_stone", "moss", "edge_dust"],
        "material_layers": ["worn_stone", "moss", "edge_dust"],
        "story_decals": ["edge_chips", "moss_patch"],
        "story_targets": ["platform", "terrain_platform"],
        "wear_story": "ancient",
        "wear_level": 0.48,
        "zones": {"platform": "worn_stone", "terrain_platform": "worn_stone", "terrain": "soil"},
        "patterns": ["chipped_edge", "moss_patch"],
        "features": [
            _feature("chipped_edge", ["platform", "terrain_platform", "edge"], profile="cracked_stone", normal_delta=0.15, wear_delta=0.18, wear_layer="edge_wear"),
            _feature("moss_inset", ["platform", "top"], profile="grass_mottle", material="moss", basecolor_mix=[66, 112, 68], mix=0.12),
        ],
    },
    "water": {
        "materials": ["shallow_water", "wet_stone", "mud", "foam"],
        "material_layers": ["shallow_water", "foam", "silt"],
        "story_decals": ["shoreline_foam", "waterline_silt"],
        "story_targets": ["water", "basin"],
        "wear_story": "wet",
        "wear_level": 0.22,
        "zones": {"water": "shallow_water", "basin": "mud", "rim": "wet_stone", "terrain": "wet_stone"},
        "patterns": ["water_ripple", "shoreline_silt"],
        "features": [
            _feature("water_ripple", ["water"], profile="water_ripple", roughness_delta=-0.24, normal_delta=0.22, basecolor_mix=[48, 116, 146], mix=0.28, emissive=[0, 10, 16]),
            _feature("shoreline_foam", ["rim", "basin", "water"], profile="foam_wash", material="foam", basecolor_mix=[218, 232, 224], mix=0.16),
            _feature("waterline_silt", ["basin", "terrain"], profile="mud_silt", material="mud", roughness_delta=0.10, normal_delta=0.08, wear_layer="dirt_grime"),
        ],
    },
    "path": {
        "materials": ["packed_soil", "gravel", "dust"],
        "material_layers": ["packed_soil", "gravel", "dust"],
        "story_decals": ["trail_scuff", "edge_wear"],
        "story_targets": ["path", "road"],
        "wear_story": "field_used",
        "wear_level": 0.42,
        "zones": {"path": "packed_soil", "road": "packed_soil", "sidewalk": "gravel", "branch": "packed_soil", "turnout": "gravel"},
        "patterns": ["trail_scuff", "gravel_noise"],
        "features": [
            _feature("trail_scuff", ["path", "road"], profile="mud_silt", normal_delta=0.12, wear_delta=0.20, wear_layer="dirt_grime"),
        ],
    },
    "road_edge": {
        "materials": ["asphalt", "road_dust", "concrete", "edge_gravel"],
        "material_layers": ["asphalt", "road_dust", "edge_gravel"],
        "story_decals": ["road_edge_wear", "tire_scuff"],
        "story_targets": ["road", "edge", "sidewalk"],
        "wear_story": "field_used",
        "wear_level": 0.50,
        "zones": {"road": "asphalt", "edge": "edge_gravel", "curb": "concrete", "sidewalk": "concrete", "junction": "asphalt", "branch": "asphalt", "crosswalk": "lane_paint", "turnout": "edge_gravel", "roundabout": "concrete"},
        "patterns": ["asphalt_grit", "edge_gravel"],
        "features": [
            _feature("road_edge_grit", ["edge", "curb", "sidewalk"], profile="asphalt_grit", material="edge_gravel", roughness_delta=0.12, normal_delta=0.10),
            _feature("tire_scuff", ["road"], profile="asphalt_grit", basecolor_mix=[18, 18, 18], mix=0.12, wear_delta=0.12),
        ],
    },
}

_LANDFORM_PRESETS["trail"] = _LANDFORM_PRESETS["path"]
_LANDFORM_PRESETS["road"] = _LANDFORM_PRESETS["road_edge"]
_LANDFORM_PRESETS["street_edge"] = _LANDFORM_PRESETS["road_edge"]

_BIOME_PRESETS: dict[str, dict[str, Any]] = {
    "forest": {
        "materials": ["moss", "leaf_litter", "bark", "packed_soil"],
        "material_layers": ["moss", "leaf_litter"],
        "story_decals": ["moss_patch", "leaf_litter"],
        "patterns": ["grass_mottle", "leaf_litter"],
        "features": [
            _feature("forest_floor", ["terrain", "clearing", "path"], profile="leaf_litter", material="leaf_litter", basecolor_mix=[108, 84, 42], mix=0.16),
            _feature("moss_edges", ["ridge", "cliff", "platform", "edge"], profile="grass_mottle", material="moss", basecolor_mix=[64, 112, 70], mix=0.18),
        ],
    },
    "desert": {
        "materials": ["sand", "sun_bleached_stone", "dust"],
        "material_layers": ["sand", "dust"],
        "story_decals": ["wind_streaks", "sand_drift"],
        "patterns": ["sand_ripple", "wind_streaks"],
        "features": [
            _feature("sand_ripple", ["terrain", "path", "clearing"], profile="sand_ripple", material="sand", basecolor_mix=[180, 148, 92], mix=0.22, normal_delta=0.10),
            _feature("sun_bleach", ["stone", "cliff", "ridge"], profile="cracked_stone", material="sun_bleached_stone", basecolor_mix=[156, 142, 114], mix=0.12),
        ],
    },
    "wetland": {
        "materials": ["mud", "algae", "shallow_water", "wet_stone"],
        "material_layers": ["mud", "algae", "water_silt"],
        "story_decals": ["mud_splatter", "algae_bloom"],
        "patterns": ["mud_silt", "water_ripple"],
        "features": [
            _feature("algae_bloom", ["water", "basin", "rim"], profile="grass_mottle", material="algae", basecolor_mix=[64, 112, 72], mix=0.20, roughness_delta=0.08),
            _feature("mud_splatter", ["terrain", "path", "clearing"], profile="mud_silt", material="mud", roughness_delta=0.12, normal_delta=0.10, wear_layer="dirt_grime"),
        ],
    },
    "swamp": {
        "materials": ["mud", "algae", "shallow_water", "rotting_wood"],
        "material_layers": ["mud", "algae", "water_silt"],
        "story_decals": ["mud_splatter", "algae_bloom"],
        "patterns": ["mud_silt", "water_ripple"],
        "features": [
            _feature("swamp_algae", ["water", "basin", "rim"], profile="grass_mottle", material="algae", basecolor_mix=[54, 104, 62], mix=0.24),
            _feature("soft_mud", ["terrain", "path"], profile="mud_silt", material="mud", roughness_delta=0.16, normal_delta=0.12, wear_layer="dirt_grime"),
        ],
    },
    "snow": {
        "materials": ["snow", "ice", "cold_stone"],
        "material_layers": ["snow", "ice", "frost"],
        "story_decals": ["snow_drift", "frost_edge"],
        "patterns": ["snow_drift", "ice_scratch"],
        "features": [
            _feature("snow_drift", ["terrain", "platform", "ridge"], profile="snow_drift", material="snow", basecolor_mix=[220, 226, 228], mix=0.26, roughness_delta=0.08, normal_delta=0.06),
            _feature("ice_sheen", ["water", "path"], profile="ice_scratch", material="ice", basecolor_mix=[174, 214, 228], mix=0.22, roughness_delta=-0.16),
        ],
    },
    "volcanic": {
        "materials": ["basalt", "ash", "lava_glow"],
        "material_layers": ["basalt", "ash", "lava_glow"],
        "story_decals": ["lava_crack", "ash_fall"],
        "patterns": ["basalt_crack", "lava_crack"],
        "features": [
            _feature("basalt_crack", ["cliff", "ridge", "platform"], profile="basalt_crack", material="basalt", basecolor_mix=[40, 40, 42], mix=0.24, normal_delta=0.20),
            _feature("lava_glow", ["crack", "cliff", "platform"], profile="lava_crack", material="lava_glow", basecolor_mix=[174, 58, 24], mix=0.16, emissive=[220, 74, 18]),
        ],
    },
    "coastal": {
        "materials": ["sand", "shallow_water", "wet_stone", "foam"],
        "material_layers": ["sand", "wet_stone", "foam"],
        "story_decals": ["shoreline_foam", "waterline_silt"],
        "patterns": ["sand_ripple", "water_ripple"],
        "features": [
            _feature("coastal_sand", ["terrain", "path", "clearing"], profile="sand_ripple", material="sand", basecolor_mix=[174, 148, 96], mix=0.20),
            _feature("surf_foam", ["water", "rim", "basin"], profile="foam_wash", material="foam", basecolor_mix=[220, 232, 224], mix=0.18),
        ],
    },
    "urban": {
        "materials": ["concrete", "asphalt", "urban_grime", "lane_paint"],
        "material_layers": ["concrete", "asphalt", "urban_grime"],
        "story_decals": ["street_lines", "grime_streaks"],
        "patterns": ["asphalt_grit", "concrete_mottle"],
        "features": [
            _feature("urban_grime", ["road", "sidewalk", "building", "lot"], profile="concrete_mottle", material="urban_grime", roughness_delta=0.10, wear_delta=0.12, wear_layer="dirt_grime"),
        ],
    },
    "mountain": {
        "materials": ["stratified_stone", "lichen", "cold_stone"],
        "material_layers": ["stratified_stone", "lichen", "dust"],
        "story_decals": ["lichen_patch", "crack_lines"],
        "patterns": ["strata_banding", "cracked_stone"],
        "features": [
            _feature("highland_lichen", ["ridge", "cliff"], profile="grass_mottle", material="lichen", basecolor_mix=[104, 130, 84], mix=0.14),
        ],
    },
}


_FAMILY_PRESETS: dict[str, dict[str, Any]] = {
    "procedural_boat": {
        "materials": ["marine_paint", "deck_wood", "weathered_steel", "sailcloth", "rope", "brass", "salt_wear"],
        "material_layers": ["marine_paint", "salt_wear", "deck_wood", "rope"],
        "story_decals": ["waterline_wear", "salt_streaks", "deck_scuff", "hull_number"],
        "decal_targets": ["hull", "sail", "deck", "cabin"],
        "story_targets": ["hull", "deck", "sail", "rigging", "propeller", "anchor"],
        "wear_story": "field_used",
        "wear_level": 0.44,
        "zones": {
            "hull": "marine_paint",
            "keel": "marine_paint",
            "deck": "deck_wood",
            "cabin": "deck_wood",
            "mast": "weathered_steel",
            "sail": "sailcloth",
            "rigging": "rope",
            "pontoon": "marine_paint",
            "outrigger": "deck_wood",
            "cargo": "deck_wood",
            "hold": "deck_wood",
            "rudder": "marine_paint",
            "propeller": "brass",
            "anchor": "weathered_steel",
            "engine": "weathered_steel",
        },
        "patterns": ["painted_panel", "wood_grain", "woven_fabric", "salt_streaks"],
        "features": [
            _feature(
                "waterline_wear",
                ["hull", "keel", "rudder", "pontoon"],
                profile="painted_panel",
                material="salt_wear",
                basecolor_mix=[188, 198, 190],
                mix=0.16,
                roughness_delta=0.08,
                wear_delta=0.18,
                wear_layer="edge_wear",
            ),
            _feature(
                "deck_scuff",
                ["deck", "hold", "cargo"],
                profile="wood_grain",
                material="deck_wood",
                basecolor_mix=[96, 70, 44],
                mix=0.12,
                normal_delta=0.08,
                wear_delta=0.12,
                wear_layer="micro_scratches",
            ),
            _feature(
                "sailcloth_weave",
                ["sail", "canvas"],
                profile="woven_fabric",
                material="sailcloth",
                basecolor_mix=[214, 208, 182],
                mix=0.20,
                roughness_delta=0.10,
                normal_delta=0.12,
            ),
            _feature(
                "rope_fiber",
                ["rigging", "rope", "cable"],
                profile="woven_fabric",
                material="rope",
                basecolor_mix=[130, 116, 82],
                mix=0.18,
                normal_delta=0.12,
                wear_delta=0.06,
            ),
            _feature(
                "prop_tarnish",
                ["propeller", "anchor"],
                profile="worn_brass",
                material="brass",
                basecolor_mix=[92, 98, 82],
                mix=0.12,
                roughness_delta=0.08,
                wear_delta=0.10,
            ),
        ],
    },
    "procedural_furniture": {
        "materials": ["finished_wood", "upholstery_fabric", "leather", "brushed_metal", "laminate", "glass", "emissive_panel"],
        "material_layers": ["finished_wood", "upholstery_fabric", "edge_wear", "dust"],
        "story_decals": ["edge_scuff", "seat_wear", "drawer_label"],
        "decal_targets": ["drawer", "cabinet", "appliance", "counter"],
        "story_targets": ["seat", "table", "bed", "shelf", "cabinet", "drawer", "counter", "appliance"],
        "wear_story": "used",
        "wear_level": 0.28,
        "zones": {
            "base": "finished_wood",
            "chair": "finished_wood",
            "seat": "upholstery_fabric",
            "back": "upholstery_fabric",
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
        "patterns": ["wood_grain", "woven_fabric", "painted_panel"],
        "features": [
            _feature(
                "seat_wear",
                ["seat", "cushion", "mattress", "upholstery"],
                profile="woven_fabric",
                material="upholstery_fabric",
                basecolor_mix=[126, 116, 100],
                mix=0.16,
                roughness_delta=0.08,
                normal_delta=0.10,
                wear_delta=0.12,
                wear_layer="micro_scratches",
            ),
            _feature(
                "wood_edge_scuff",
                ["table", "desk", "bed", "shelf", "cabinet", "drawer", "workbench"],
                profile="wood_grain",
                material="finished_wood",
                basecolor_mix=[92, 66, 42],
                mix=0.12,
                roughness_delta=0.06,
                wear_delta=0.14,
                wear_layer="edge_wear",
            ),
            _feature(
                "counter_polish",
                ["counter", "appliance"],
                profile="painted_panel",
                material="laminate",
                basecolor_mix=[176, 172, 158],
                mix=0.12,
                roughness_delta=-0.08,
                normal_delta=0.04,
            ),
            _feature(
                "drawer_pull_wear",
                ["drawer", "cabinet", "fixture"],
                profile="brushed_metal",
                material="brushed_metal",
                roughness_delta=0.04,
                wear_delta=0.10,
                wear_layer="micro_scratches",
            ),
            _feature(
                "lamp_glow",
                ["lamp", "light"],
                profile="emissive_panel",
                material="emissive_panel",
                basecolor_mix=[236, 204, 126],
                mix=0.24,
                emissive=[160, 112, 42],
            ),
        ],
    },
    "procedural_foliage": {
        "materials": ["soil", "bark", "leaf_litter", "moss", "short_grass", "stone", "fungus", "flower_petal", "terracotta"],
        "material_layers": ["soil", "bark", "leaf_litter", "moss"],
        "story_decals": ["leaf_litter", "moss_patch", "bark_scars", "soil_mottle"],
        "decal_targets": ["ground", "trunk", "rock", "log", "planter"],
        "story_targets": ["tree", "trunk", "branch", "leaf", "bush", "grass", "rock", "mushroom", "log", "vine"],
        "wear_story": "weathered",
        "wear_level": 0.40,
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
            "shrub": "leaf_litter",
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
        "patterns": ["grass_mottle", "leaf_litter", "wood_grain", "cracked_stone"],
        "features": [
            _feature(
                "bark_ridges",
                ["trunk", "branch", "root", "log", "bark"],
                profile="wood_grain",
                material="bark",
                basecolor_mix=[92, 62, 34],
                mix=0.16,
                normal_delta=0.14,
                wear_delta=0.10,
                wear_layer="micro_scratches",
            ),
            _feature(
                "leaf_mottle",
                ["leaf", "canopy", "bush", "vine"],
                profile="grass_mottle",
                material="leaf_litter",
                basecolor_mix=[66, 122, 58],
                mix=0.20,
                roughness_delta=0.08,
                normal_delta=0.10,
            ),
            _feature(
                "forest_floor",
                ["ground", "grass", "soil"],
                profile="leaf_litter",
                material="leaf_litter",
                basecolor_mix=[96, 74, 38],
                mix=0.18,
                normal_delta=0.08,
                wear_layer="dirt_grime",
            ),
            _feature(
                "stone_lichen",
                ["rock", "stone", "planter"],
                profile="cracked_stone",
                material="moss",
                basecolor_mix=[82, 112, 72],
                mix=0.12,
                roughness_delta=0.10,
                normal_delta=0.12,
            ),
            _feature(
                "fungal_cap_mottle",
                ["mushroom", "fungus"],
                profile="leaf_litter",
                material="fungus",
                basecolor_mix=[180, 142, 112],
                mix=0.18,
                normal_delta=0.08,
            ),
            _feature(
                "flower_color",
                ["flower", "petal", "blossom"],
                profile="grass_mottle",
                material="flower_petal",
                basecolor_mix=[202, 80, 142],
                mix=0.24,
                roughness_delta=-0.04,
            ),
        ],
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
        "decal_targets": ["sign", "barrier", "kiosk", "bin", "bollard"],
        "story_targets": [
            "fence",
            "gate",
            "sign",
            "streetlight",
            "bench",
            "bin",
            "utility",
            "kiosk",
            "stall",
            "barrier",
            "bollard",
        ],
        "wear_story": "field_used",
        "wear_level": 0.44,
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
            "lamp": "weathered_steel",
            "light": "emissive_panel",
            "glow": "emissive_panel",
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
        "patterns": ["painted_panel", "concrete_mottle", "brushed_metal", "woven_fabric"],
        "features": [
            _feature(
                "street_grime",
                ["base", "sidewalk", "curb", "barrier", "bollard"],
                profile="concrete_mottle",
                material="urban_grime",
                basecolor_mix=[72, 70, 64],
                mix=0.18,
                roughness_delta=0.10,
                normal_delta=0.08,
                wear_delta=0.18,
                wear_layer="dirt_grime",
            ),
            _feature(
                "paint_chip_edges",
                ["fence", "gate", "sign", "kiosk", "pole", "streetlight"],
                profile="painted_panel",
                material="painted_metal",
                basecolor_mix=[78, 86, 94],
                mix=0.14,
                roughness_delta=0.06,
                normal_delta=0.06,
                wear_delta=0.16,
                wear_layer="edge_wear",
            ),
            _feature(
                "sign_label_panel",
                ["sign", "signage", "kiosk"],
                profile="painted_panel",
                material="painted_metal",
                basecolor_mix=[198, 188, 132],
                mix=0.16,
                roughness_delta=-0.04,
                wear_delta=0.08,
            ),
            _feature(
                "warning_stripe",
                ["barrier", "bollard", "gate"],
                profile="painted_panel",
                material="warning_paint",
                basecolor_mix=[222, 166, 42],
                mix=0.22,
                roughness_delta=0.04,
                wear_delta=0.12,
                wear_layer="edge_wear",
            ),
            _feature(
                "streetlight_glow",
                ["streetlight", "streetlamp", "lamp", "light", "glow"],
                profile="emissive_panel",
                material="emissive_panel",
                basecolor_mix=[236, 210, 126],
                mix=0.24,
                emissive=[180, 130, 54],
            ),
            _feature(
                "awning_fabric_wear",
                ["stall", "kiosk", "awning", "canopy"],
                profile="woven_fabric",
                material="canvas",
                basecolor_mix=[142, 116, 82],
                mix=0.16,
                roughness_delta=0.08,
                normal_delta=0.12,
                wear_delta=0.08,
            ),
            _feature(
                "bench_slat_wear",
                ["bench", "seat", "crate"],
                profile="wood_grain",
                material="finished_wood",
                basecolor_mix=[88, 66, 44],
                mix=0.13,
                roughness_delta=0.06,
                normal_delta=0.08,
                wear_delta=0.12,
                wear_layer="micro_scratches",
            ),
        ],
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
        "decal_targets": ["pipe", "duct", "transformer", "junction", "valve", "manhole"],
        "story_targets": [
            "pipe",
            "duct",
            "drain",
            "hydrant",
            "transformer",
            "conduit",
            "junction",
            "valve",
            "manhole",
            "support",
            "tray",
        ],
        "wear_story": "field_used",
        "wear_level": 0.48,
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
        "patterns": ["brushed_metal", "concrete_mottle", "painted_panel", "carbon_rubber"],
        "features": [
            _feature(
                "maintenance_grime",
                ["pipe", "duct", "drain", "manhole", "support", "base"],
                profile="concrete_mottle",
                material="urban_grime",
                basecolor_mix=[62, 60, 54],
                mix=0.18,
                roughness_delta=0.12,
                normal_delta=0.08,
                wear_delta=0.18,
                wear_layer="dirt_grime",
            ),
            _feature(
                "galvanized_edge_wear",
                ["pipe", "duct", "conduit", "rail", "tray", "support"],
                profile="brushed_metal",
                material="galvanized_steel",
                basecolor_mix=[132, 138, 136],
                mix=0.14,
                roughness_delta=0.06,
                normal_delta=0.08,
                wear_delta=0.14,
                wear_layer="edge_wear",
            ),
            _feature(
                "flow_arrow",
                ["pipe", "valve", "junction"],
                profile="painted_panel",
                material="warning_paint",
                basecolor_mix=[226, 176, 48],
                mix=0.20,
                roughness_delta=0.04,
                wear_delta=0.08,
            ),
            _feature(
                "access_label",
                ["transformer", "junction", "box", "manhole"],
                profile="painted_panel",
                material="utility_plastic",
                basecolor_mix=[190, 198, 188],
                mix=0.14,
                roughness_delta=0.02,
                wear_delta=0.08,
            ),
            _feature(
                "cast_iron_polish",
                ["drain", "manhole", "cover"],
                profile="brushed_metal",
                material="cast_iron",
                basecolor_mix=[58, 60, 60],
                mix=0.16,
                roughness_delta=0.08,
                normal_delta=0.10,
                wear_delta=0.16,
            ),
            _feature(
                "insulation_band",
                ["cable", "wire", "tray"],
                profile="carbon_rubber",
                material="cable_insulation",
                basecolor_mix=[34, 42, 52],
                mix=0.16,
                roughness_delta=0.05,
                normal_delta=0.08,
            ),
        ],
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
        "decal_targets": ["catwalk", "walkway", "ladder", "ramp", "platform", "gate"],
        "story_targets": [
            "catwalk",
            "walkway",
            "ladder",
            "ramp",
            "gantry",
            "elevator",
            "platform",
            "tunnel",
            "scaffold",
            "guardrail",
            "gate",
        ],
        "wear_story": "field_used",
        "wear_level": 0.46,
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
        "patterns": ["brushed_metal", "painted_panel", "carbon_rubber", "concrete_mottle"],
        "features": [
            _feature(
                "grate_edge_wear",
                ["catwalk", "walkway", "platform", "deck"],
                profile="brushed_metal",
                material="safety_grate",
                basecolor_mix=[126, 134, 132],
                mix=0.14,
                roughness_delta=0.08,
                normal_delta=0.12,
                wear_delta=0.18,
                wear_layer="edge_wear",
            ),
            _feature(
                "route_arrow",
                ["catwalk", "walkway", "platform", "ramp"],
                profile="painted_panel",
                material="warning_paint",
                basecolor_mix=[220, 172, 48],
                mix=0.18,
                roughness_delta=0.04,
                wear_delta=0.10,
            ),
            _feature(
                "rubber_step_scuff",
                ["ladder", "rung", "ramp", "tread"],
                profile="carbon_rubber",
                material="rubber_tread",
                basecolor_mix=[36, 40, 42],
                mix=0.14,
                roughness_delta=0.08,
                normal_delta=0.10,
                wear_delta=0.14,
            ),
            _feature(
                "safety_rail_wear",
                ["guardrail", "gate", "railing"],
                profile="painted_panel",
                material="warning_paint",
                basecolor_mix=[230, 174, 42],
                mix=0.20,
                roughness_delta=0.06,
                wear_delta=0.16,
                wear_layer="edge_wear",
            ),
            _feature(
                "tunnel_grime",
                ["tunnel", "corridor", "base"],
                profile="concrete_mottle",
                material="urban_grime",
                basecolor_mix=[62, 60, 56],
                mix=0.18,
                roughness_delta=0.12,
                normal_delta=0.08,
                wear_delta=0.18,
                wear_layer="dirt_grime",
            ),
            _feature(
                "landing_light",
                ["elevator", "lift", "tunnel", "light"],
                profile="emissive_panel",
                material="emissive_panel",
                basecolor_mix=[220, 206, 134],
                mix=0.20,
                emissive=[170, 130, 58],
            ),
        ],
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
            "polished_stone",
        ],
        "material_layers": ["concrete", "painted_metal", "edge_wear", "urban_grime"],
        "story_decals": ["wayfinding_mark", "service_number", "route_arrow", "district_mark"],
        "decal_targets": ["building", "gate", "route", "utility", "prop", "tower"],
        "story_targets": [
            "setpiece",
            "terrain",
            "building",
            "road",
            "access",
            "utility",
            "prop",
            "perimeter",
            "gate",
            "tower",
            "dock",
            "apron",
            "ritual",
        ],
        "wear_story": "field_used",
        "wear_level": 0.46,
        "zones": {
            "setpiece": "concrete",
            "base": "concrete",
            "terrain": "concrete",
            "courtyard": "concrete",
            "building": "painted_metal",
            "primary": "painted_metal",
            "secondary": "painted_metal",
            "warehouse": "painted_metal",
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
            "ritual": "polished_stone",
            "vehicle": "painted_metal",
            "chassis": "painted_metal",
            "wheel": "rubber",
            "rotor": "painted_metal",
            "cargo_module": "painted_metal",
            "turret": "weathered_steel",
            "boat": "marine_paint",
            "hull": "marine_paint",
            "pontoon": "marine_paint",
            "sail": "canvas",
            "cargo_hold": "deck_wood",
            "machine": "industrial_steel",
            "conveyor": "rubber_tread",
            "hydraulic": "weathered_steel",
            "crane": "industrial_steel",
            "interior": "painted_plaster",
            "ceiling_light": "emissive_panel",
            "alcove": "painted_plaster",
            "furniture": "finished_wood",
            "shelf": "finished_wood",
            "lamp": "emissive_panel",
            "foliage": "moss",
            "bush": "moss",
            "grass": "moss",
            "rock": "stone",
            "flower": "leaf_litter",
            "socket": "weathered_steel",
            "module": "weathered_steel",
            "module_slot": "weathered_steel",
            "mount": "weathered_steel",
            "parking_bay": "warning_paint",
            "mooring": "marine_paint",
            "machine_pad": "industrial_steel",
            "room_entry": "painted_plaster",
            "furniture_anchor": "finished_wood",
            "terrain_anchor": "moss",
        },
        "patterns": ["concrete_mottle", "painted_panel", "brushed_metal", "asphalt_grit"],
        "features": [
            _feature(
                "setpiece_ground_grime",
                ["setpiece", "terrain", "courtyard", "base"],
                profile="concrete_mottle",
                material="urban_grime",
                basecolor_mix=[68, 66, 60],
                mix=0.18,
                roughness_delta=0.10,
                normal_delta=0.08,
                wear_delta=0.18,
                wear_layer="dirt_grime",
            ),
            _feature(
                "route_scuffed_edges",
                ["road", "route", "apron"],
                profile="asphalt_grit",
                material="asphalt",
                basecolor_mix=[42, 44, 44],
                mix=0.16,
                roughness_delta=0.08,
                normal_delta=0.10,
                wear_delta=0.14,
            ),
            _feature(
                "utility_service_marks",
                ["utility", "pipe", "conduit", "junction"],
                profile="brushed_metal",
                material="weathered_steel",
                basecolor_mix=[118, 124, 122],
                mix=0.14,
                roughness_delta=0.06,
                normal_delta=0.08,
                wear_delta=0.12,
            ),
            _feature(
                "perimeter_warning_marks",
                ["perimeter", "gate", "tower"],
                profile="painted_panel",
                material="warning_paint",
                basecolor_mix=[226, 170, 42],
                mix=0.20,
                roughness_delta=0.05,
                wear_delta=0.16,
                wear_layer="edge_wear",
            ),
            _feature(
                "ritual_stone_patina",
                ["temple", "ritual", "column"],
                profile="mineral_stone",
                material="polished_stone",
                basecolor_mix=[168, 154, 126],
                mix=0.16,
                roughness_delta=0.06,
                normal_delta=0.08,
                wear_delta=0.12,
            ),
            _feature(
                "child_module_edge_wear",
                ["vehicle", "machine", "boat", "socket", "module_slot", "mount"],
                profile="painted_panel",
                material="painted_metal",
                basecolor_mix=[92, 98, 100],
                mix=0.14,
                roughness_delta=0.06,
                normal_delta=0.08,
                wear_delta=0.14,
                wear_layer="edge_wear",
            ),
        ],
    },
}


def _empty_grammar(
    *,
    procedural_family: str = "",
    landform: str = "",
    biome: str = "",
    pattern: str = "",
) -> dict[str, Any]:
    return {
        "schema": "lathe.surface_grammar.v1",
        "procedural_family": procedural_family,
        "landform": landform,
        "biome": biome,
        "environment_pattern": pattern,
        "materials": [],
        "material_layers": [],
        "story_decals": [],
        "decal_targets": [],
        "story_targets": [],
        "zones": {},
        "patterns": [],
        "features": [],
    }


def _merge_preset(target: dict[str, Any], preset: dict[str, Any]) -> None:
    for key in ("materials", "material_layers", "story_decals", "decal_targets", "story_targets", "patterns"):
        target[key] = _dedupe([*target.get(key, []), *[str(item) for item in _as_list(preset.get(key))]])
    zones = dict(target.get("zones", {}))
    zones.update({str(key): str(value) for key, value in dict(preset.get("zones", {})).items()})
    target["zones"] = zones
    target["features"] = [*target.get("features", []), *deepcopy(list(preset.get("features", [])))]
    for key in ("wear_story", "wear_level"):
        if key in preset:
            target[key] = preset[key]


def surface_grammar_for_controls(
    *,
    procedural_family: str | None = None,
    shape_controls: dict[str, Any] | None = None,
    surface: dict[str, Any] | None = None,
    fidelity_tier: str = "game",
) -> dict[str, Any]:
    """Derive reusable surface intent from procedural and scene context."""
    controls = shape_controls if isinstance(shape_controls, dict) else {}
    source_surface = surface if isinstance(surface, dict) else {}
    tier = fidelity_tier if fidelity_tier in {"blockout", "game", "hero", "cinematic"} else "game"
    family = _token(procedural_family or controls.get("scene_source_family") or source_surface.get("family"))
    landform = _token(
        controls.get("landform")
        or controls.get("environment_feature")
        or source_surface.get("landform")
        or source_surface.get("surface_grammar")
    )
    biome = _token(
        controls.get("biome")
        or controls.get("habitat")
        or source_surface.get("biome")
        or source_surface.get("habitat")
    )
    pattern = _token(controls.get("environment_pattern") or controls.get("scatter_pattern") or source_surface.get("pattern"))
    grammar = _empty_grammar(procedural_family=family, landform=landform, biome=biome, pattern=pattern)

    if family == "procedural_terrain" and not landform:
        landform = "terrain_patch"
        grammar["landform"] = landform
    if family == "procedural_road" and landform in {"", "path", "trail"}:
        landform = landform or "road_edge"
        grammar["landform"] = landform

    if family in _FAMILY_PRESETS:
        _merge_preset(grammar, _FAMILY_PRESETS[family])
    if landform in _LANDFORM_PRESETS:
        _merge_preset(grammar, _LANDFORM_PRESETS[landform])
    if biome in _BIOME_PRESETS:
        _merge_preset(grammar, _BIOME_PRESETS[biome])

    if family == "procedural_boat":
        boat_type = _token(
            controls.get("boat_type")
            or controls.get("hull_type")
            or controls.get("watercraft_type")
            or controls.get("vessel_type")
        )
        if boat_type:
            grammar["boat_type"] = boat_type
        zones = dict(grammar.get("zones", {}))
        if boat_type in {"catamaran", "trimaran", "pontoon", "pontoon_boat"} or _number(
            controls.get("pontoon_count") or controls.get("pontoons"),
            default=0.0,
        ):
            zones.update({"pontoon": "marine_paint", "float": "rubber"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "pontoon_waterline"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "waterline_wear"])
        if boat_type in {"sailboat", "sloop", "schooner", "ketch", "cutter", "tall_ship"} or _number(
            controls.get("sail_count") or controls.get("sails"),
            default=0.0,
        ):
            zones.update({"sail": "sailcloth", "rigging": "rope", "mast": "weathered_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "sail_panel_mark"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "woven_fabric"])
        if _number(controls.get("propeller_count") or controls.get("propellers"), default=0.0):
            zones.update({"propeller": "brass", "rudder": "marine_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "stern_spray_wear"])
        if _number(controls.get("cargo_hold_count") or controls.get("cargo_holds"), default=0.0):
            zones.update({"cargo": "deck_wood", "hold": "deck_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "cargo_stencil", "hold_scuff"])
        grammar["zones"] = zones

    if family == "procedural_furniture":
        furniture_type = _token(
            controls.get("furniture_type")
            or controls.get("furnishing_type")
            or controls.get("room_role")
            or controls.get("archetype")
        )
        if furniture_type:
            grammar["furniture_type"] = furniture_type
        zones = dict(grammar.get("zones", {}))
        if furniture_type in {"office", "desk", "workstation"} or _number(controls.get("table_count") or controls.get("tables"), default=0.0):
            zones.update({"desk": "finished_wood", "table": "finished_wood", "leg": "brushed_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "desktop_wear"])
        if furniture_type in {"bedroom", "bed", "bunk"} or _number(controls.get("bed_count") or controls.get("beds"), default=0.0):
            zones.update({"bed": "finished_wood", "mattress": "upholstery_fabric", "cushion": "upholstery_fabric"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "fabric_pressure_wear"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "woven_fabric"])
        if furniture_type in {"kitchen", "bar", "counter"} or _number(controls.get("counter_count") or controls.get("counters"), default=0.0):
            zones.update({"counter": "laminate", "cabinet": "finished_wood", "drawer": "finished_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "counter_edge_wear"])
        if furniture_type in {"storage", "library", "workshop"} or _number(controls.get("shelf_count") or controls.get("shelves"), default=0.0):
            zones.update({"shelf": "finished_wood", "cabinet": "finished_wood", "drawer": "finished_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "shelf_dust", "drawer_label"])
        if _number(controls.get("appliance_count") or controls.get("appliances"), default=0.0):
            zones.update({"appliance": "brushed_metal", "fixture": "brushed_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "control_label"])
        if _number(controls.get("lamp_count") or controls.get("lamps"), default=0.0):
            zones.update({"lamp": "brushed_metal", "light": "emissive_panel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "warm_light_falloff"])
        grammar["zones"] = zones

    if family == "procedural_foliage":
        foliage_type = _token(
            controls.get("foliage_type")
            or controls.get("plant_type")
            or controls.get("nature_type")
            or controls.get("archetype")
        )
        if foliage_type:
            grammar["foliage_type"] = foliage_type
        zones = dict(grammar.get("zones", {}))
        if foliage_type in {"tree", "oak", "pine", "palm", "dead_tree", "forest_kit", "woodland_kit"} or _number(
            controls.get("trunk_count") or controls.get("tree_count"),
            default=0.0,
        ):
            zones.update({"trunk": "bark", "branch": "bark", "root": "bark", "canopy": "leaf_litter"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "bark_scars", "fallen_leaves"])
        if _number(controls.get("bush_count") or controls.get("bushes"), default=0.0):
            zones.update({"bush": "leaf_litter", "shrub": "leaf_litter"})
            grammar["patterns"] = _dedupe([*grammar["patterns"], "grass_mottle"])
        if _number(controls.get("grass_count") or controls.get("grass_clumps"), default=0.0):
            zones.update({"grass": "short_grass"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "grass_variation"])
        if _number(controls.get("rock_count") or controls.get("rocks"), default=0.0):
            zones.update({"rock": "stone", "stone": "stone"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "lichen_patch"])
        if _number(controls.get("mushroom_count") or controls.get("mushrooms"), default=0.0):
            zones.update({"mushroom": "fungus", "fungus": "fungus"})
            grammar["patterns"] = _dedupe([*grammar["patterns"], "leaf_litter"])
        if _number(controls.get("vine_count") or controls.get("vines"), default=0.0):
            zones.update({"vine": "moss"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "vine_growth"])
        if _number(controls.get("flower_count") or controls.get("flowers"), default=0.0):
            zones.update({"flower": "flower_petal", "petal": "flower_petal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "blossom_scatter"])
        if _number(controls.get("planter_count") or controls.get("planters"), default=0.0):
            zones.update({"planter": "terracotta", "pot": "terracotta"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "soil_spill"])
        grammar["zones"] = zones

    if family == "procedural_urban_prop":
        urban_type = _token(
            controls.get("urban_prop_type")
            or controls.get("street_prop_type")
            or controls.get("set_dressing_type")
            or controls.get("archetype")
        )
        if urban_type:
            grammar["urban_prop_type"] = urban_type
        zones = dict(grammar.get("zones", {}))
        if urban_type in {"traffic", "roadside", "barrier", "construction", "checkpoint"} or _number(
            controls.get("barrier_count") or controls.get("barriers"),
            default=0.0,
        ):
            zones.update({"barrier": "warning_paint", "bollard": "warning_paint", "gate": "painted_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "warning_stripe", "road_dust"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "painted_panel"])
        if _number(controls.get("sign_count") or controls.get("signs"), default=0.0):
            zones.update({"sign": "painted_metal", "signage": "painted_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "sign_label", "sticker_residue"])
        if _number(controls.get("streetlight_count") or controls.get("streetlights"), default=0.0):
            zones.update({"streetlight": "weathered_steel", "streetlamp": "weathered_steel", "light": "emissive_panel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "lamp_glow"])
        if _number(controls.get("pole_count") or controls.get("utility_pole_count"), default=0.0):
            zones.update({"pole": "weathered_steel", "utility": "weathered_steel", "cable": "weathered_steel", "wire": "weathered_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "service_number"])
        if _number(controls.get("bench_count") or controls.get("benches"), default=0.0):
            zones.update({"bench": "finished_wood", "seat": "finished_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "seat_wear"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "wood_grain"])
        if _number(controls.get("bin_count") or controls.get("trash_bin_count"), default=0.0):
            zones.update({"trash": "recycled_plastic", "bin": "recycled_plastic"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "waste_label", "street_grime"])
        if _number(controls.get("kiosk_count") or controls.get("stall_count"), default=0.0):
            zones.update({"kiosk": "painted_metal", "stall": "finished_wood", "canopy": "canvas", "awning": "canvas", "window": "glass"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "vendor_label", "awning_fade"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "woven_fabric"])
        if _number(controls.get("street_crate_count") or controls.get("crate_count"), default=0.0):
            zones.update({"crate": "finished_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "cargo_stencil"])
        grammar["zones"] = zones

    if family == "procedural_infrastructure":
        infrastructure_type = _token(
            controls.get("infrastructure_type")
            or controls.get("utility_type")
            or controls.get("service_type")
            or controls.get("network_type")
            or controls.get("archetype")
        )
        service_type = _token(controls.get("service_type") or controls.get("utility_type") or controls.get("network_service"))
        if infrastructure_type:
            grammar["infrastructure_type"] = infrastructure_type
        if service_type:
            grammar["service_type"] = service_type
        zones = dict(grammar.get("zones", {}))
        if _number(controls.get("pipe_count") or controls.get("pipes"), default=0.0):
            zones.update({"pipe": "galvanized_steel", "pipeline": "galvanized_steel", "valve": "warning_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "flow_arrow", "pipe_id_band"])
        if _number(controls.get("duct_count") or controls.get("ducts"), default=0.0):
            zones.update({"duct": "galvanized_steel", "vent": "galvanized_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "inspection_panel_id"])
        if _number(controls.get("drain_count") or controls.get("drains"), default=0.0):
            zones.update({"drain": "cast_iron", "channel": "cast_iron", "manhole": "cast_iron"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "water_stain", "access_cover_wear"])
        if _number(controls.get("hydrant_count") or controls.get("hydrants"), default=0.0):
            zones.update({"hydrant": "warning_paint", "valve": "warning_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "hydrant_service_mark"])
        if _number(controls.get("transformer_count") or controls.get("transformers"), default=0.0):
            zones.update({"transformer": "painted_metal", "substation": "painted_metal", "warning": "warning_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "high_voltage_label"])
        if _number(controls.get("junction_box_count") or controls.get("junction_boxes"), default=0.0):
            zones.update({"junction": "utility_plastic", "box": "utility_plastic"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "junction_label"])
        if _number(controls.get("conduit_count") or controls.get("conduits"), default=0.0):
            zones.update({"conduit": "galvanized_steel", "cable": "cable_insulation", "wire": "cable_insulation"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "cable_color_band"])
        if _number(controls.get("cable_tray_count") or controls.get("cable_trays"), default=0.0):
            zones.update({"tray": "galvanized_steel", "cable": "cable_insulation"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "tray_route_label"])
        grammar["zones"] = zones

    if family == "procedural_access":
        access_type = _token(
            controls.get("access_type")
            or controls.get("traversal_type")
            or controls.get("maintenance_access_type")
            or controls.get("archetype")
        )
        if access_type:
            grammar["access_type"] = access_type
        zones = dict(grammar.get("zones", {}))
        if _number(controls.get("catwalk_count") or controls.get("catwalks"), default=0.0):
            zones.update({"catwalk": "safety_grate", "deck": "safety_grate", "guardrail": "warning_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "catwalk_route_arrow", "grate_edge_wear"])
        if _number(controls.get("walkway_count") or controls.get("walkways"), default=0.0):
            zones.update({"walkway": "safety_grate", "span": "galvanized_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "route_arrow"])
        if _number(controls.get("ladder_count") or controls.get("ladders"), default=0.0):
            zones.update({"ladder": "galvanized_steel", "rung": "rubber_tread"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "rung_scuff"])
        if _number(controls.get("ramp_count") or controls.get("ramps"), default=0.0):
            zones.update({"ramp": "rubber_tread", "tread": "rubber_tread"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "anti_slip_wear"])
        if _number(controls.get("gantry_count") or controls.get("gantries"), default=0.0):
            zones.update({"gantry": "galvanized_steel", "frame": "galvanized_steel", "support": "galvanized_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "load_rating_label"])
        if _number(controls.get("elevator_count") or controls.get("elevators"), default=0.0):
            zones.update({"elevator": "painted_metal", "lift": "painted_metal", "shaft": "galvanized_steel", "window": "glass"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "landing_label", "call_button_glow"])
        if _number(controls.get("tunnel_count") or controls.get("tunnels"), default=0.0):
            zones.update({"tunnel": "concrete", "corridor": "concrete", "light": "emissive_panel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "tunnel_grime", "exit_arrow"])
        if _number(controls.get("scaffold_count") or controls.get("scaffolds"), default=0.0):
            zones.update({"scaffold": "galvanized_steel", "platform": "safety_grate"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "temporary_tag"])
        if _number(controls.get("safety_gate_count") or controls.get("safety_gates"), default=0.0):
            zones.update({"gate": "warning_paint", "guardrail": "warning_paint"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "safety_stripe"])
        grammar["zones"] = zones

    if family == "procedural_setpiece":
        archetype = _token(controls.get("object_archetype") or controls.get("archetype") or controls.get("setpiece"))
        if archetype:
            grammar["object_archetype"] = archetype
        zones = dict(grammar.get("zones", {}))
        if archetype in {"outpost", "fortress"}:
            zones.update({"perimeter": "warning_paint", "gate": "warning_paint", "tower": "painted_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "unit_stencil", "hazard_chevron"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "painted_panel"])
        if archetype == "market" or _number(controls.get("stall_count") or controls.get("kiosk_count"), default=0.0):
            zones.update({"stall": "finished_wood", "kiosk": "painted_metal", "canopy": "canvas", "sign": "painted_metal"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "vendor_label", "awning_fade"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "woven_fabric", "wood_grain"])
        if archetype == "factory" or _number(controls.get("pipe_count") or controls.get("conveyor_count"), default=0.0):
            zones.update({"utility": "weathered_steel", "pipe": "weathered_steel", "conduit": "weathered_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "flow_arrow", "hazard_stripe"])
        if archetype == "harbor" or _number(controls.get("dock_count") or controls.get("pier_count"), default=0.0):
            zones.update({"dock": "deck_wood", "pier": "deck_wood", "water": "shallow_water"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "waterline_wear", "dock_number"])
        if archetype == "hangar" or _number(controls.get("apron_count") or controls.get("runway_count"), default=0.0):
            zones.update({"apron": "concrete", "runway": "asphalt", "light": "emissive_panel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "runway_marking", "hangar_number"])
        if archetype == "temple" or _number(controls.get("column_count") or controls.get("dome_count"), default=0.0):
            zones.update({"ritual": "polished_stone", "column": "polished_stone", "dome": "worn_brass"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "etched_runes", "patina_marks"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "mineral_stone"])
        if _number(controls.get("vehicle_count") or controls.get("vehicles"), default=0.0):
            zones.update({"vehicle": "painted_metal", "chassis": "painted_metal", "wheel": "rubber", "rotor": "painted_metal", "cargo_module": "painted_metal", "turret": "weathered_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "vehicle_id_mark"])
        if _number(controls.get("boat_count") or controls.get("boats"), default=0.0):
            zones.update({"boat": "marine_paint", "hull": "marine_paint", "deck": "deck_wood", "pontoon": "marine_paint", "sail": "canvas", "cargo_hold": "deck_wood"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "hull_number", "waterline_wear"])
        if _number(controls.get("machine_count") or controls.get("machines"), default=0.0):
            zones.update({"machine": "industrial_steel", "conveyor": "rubber_tread", "hydraulic": "weathered_steel", "crane": "industrial_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "machine_label", "oil_stain"])
        if _number(controls.get("interior_module_count") or controls.get("room_count"), default=0.0):
            zones.update({"interior": "painted_plaster", "room": "painted_plaster", "partition": "painted_plaster", "ceiling_light": "emissive_panel", "alcove": "painted_plaster"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "room_label"])
        if _number(controls.get("furniture_cluster_count") or controls.get("furniture_count"), default=0.0):
            zones.update({"furniture": "finished_wood", "table": "finished_wood", "shelf": "finished_wood", "lamp": "emissive_panel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "surface_scuff"])
        if _number(controls.get("foliage_cluster_count") or controls.get("foliage_count"), default=0.0):
            zones.update({"foliage": "moss", "tree": "bark", "canopy": "leaf_litter", "bush": "moss", "grass": "moss", "rock": "stone", "flower": "leaf_litter"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "leaf_litter"])
        if _number(controls.get("child_socket_count") or controls.get("module_socket_count"), default=0.0):
            zones.update({"socket": "weathered_steel", "module": "weathered_steel", "module_slot": "weathered_steel", "mount": "weathered_steel"})
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "module_alignment_mark"])
        if _number(controls.get("module_slot_count") or controls.get("child_module_count"), default=0.0):
            zones.update(
                {
                    "parking_bay": "warning_paint",
                    "mooring": "marine_paint",
                    "machine_pad": "industrial_steel",
                    "room_entry": "painted_plaster",
                    "furniture_anchor": "finished_wood",
                    "terrain_anchor": "moss",
                }
            )
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "slot_id_marker"])
        grammar["zones"] = zones

    density = _number(controls.get("biome_density") or controls.get("environment_density"), default=0.0)
    if density > 0.0 and grammar.get("features"):
        grammar["density"] = round(density, 6)
        grammar["wear_level"] = round(min(1.0, _number(grammar.get("wear_level"), 0.0) + density * 0.12), 6)
    if pattern in {"cluster", "clusters", "patch", "patches", "natural"}:
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], "organic_variation"])
        grammar["patterns"] = _dedupe([*grammar["patterns"], "organic_variation"])
    elif pattern in {"grid", "linear", "line"}:
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], "alignment_wear"])
        grammar["patterns"] = _dedupe([*grammar["patterns"], "alignment_wear"])

    damage_type = _token(source_surface.get("damage_type") or controls.get("damage_type"))
    damage_level = _number(source_surface.get("damage_level") or controls.get("damage_level"), default=0.0)
    crack_count = _number(source_surface.get("crack_count") or controls.get("crack_count"), default=0.0)
    scratch_count = _number(source_surface.get("scratch_count") or controls.get("scratch_count"), default=0.0)
    scorch_count = _number(source_surface.get("scorch_count") or controls.get("scorch_count"), default=0.0)
    dent_count = _number(source_surface.get("dent_count") or controls.get("dent_count"), default=0.0)
    if damage_type or damage_level > 0.0 or any(count > 0.0 for count in (crack_count, scratch_count, scorch_count, dent_count)):
        surface_targets = [
            _token(item)
            for item in (
                _as_list(source_surface.get("damage_targets"))
                + _as_list(source_surface.get("story_targets"))
                + _as_list(source_surface.get("decal_targets"))
            )
            if _token(item)
        ] or ["surface", "edge"]
        exposed_materials = [_token(item) for item in _as_list(source_surface.get("exposed_materials")) if _token(item)]
        exposed_material = _token(source_surface.get("exposed_material") or controls.get("exposed_material") or (exposed_materials[0] if exposed_materials else ""), "exposed_core")
        damage_profile = damage_type or "damaged_surface"
        grammar["damage_type"] = damage_profile
        damage_decals = [_token(item) for item in _as_list(source_surface.get("damage_decals")) if _token(item)]
        if not damage_decals:
            damage_decals = ["crack_lines" if crack_count else "scratch_cluster" if scratch_count else "damage_mark"]
        grammar["materials"] = _dedupe([*grammar["materials"], exposed_material, *exposed_materials])
        grammar["material_layers"] = _dedupe([*grammar["material_layers"], exposed_material, "surface_dust"])
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], *damage_decals])
        grammar["patterns"] = _dedupe([*grammar["patterns"], damage_profile, "fracture_detail" if crack_count else "surface_damage"])
        grammar["wear_level"] = round(max(_number(grammar.get("wear_level"), 0.0), min(1.0, damage_level or 0.55)), 6)
        grammar["features"].append(
            _feature(
                "damage_surface",
                surface_targets,
                profile=damage_profile,
                material=exposed_material,
                roughness_delta=0.10 + min(0.20, damage_level * 0.10),
                normal_delta=0.18 + min(0.24, (crack_count + dent_count) * 0.02),
                wear_delta=0.20 + min(0.35, damage_level * 0.25),
                wear_layer="surface_damage",
            )
        )
        if scorch_count:
            grammar["materials"] = _dedupe([*grammar["materials"], "soot", "heat_discolor"])
            grammar["story_decals"] = _dedupe([*grammar["story_decals"], "soot_stain", "heat_bloom"])
            grammar["patterns"] = _dedupe([*grammar["patterns"], "soot_gradient"])
            grammar["features"].append(
                _feature(
                    "scorch_surface",
                    surface_targets,
                    profile="soot_gradient",
                    material="soot",
                    roughness_delta=0.18,
                    normal_delta=0.08,
                    wear_delta=0.30,
                    basecolor_mix=[30, 28, 24],
                    mix=0.22,
                    wear_layer="scorch",
                )
            )

    transition_materials = [_token(item) for item in _as_list(source_surface.get("transition_materials")) if _token(item)]
    from_material = _token(source_surface.get("from_material") or controls.get("from_material") or (transition_materials[0] if transition_materials else ""))
    to_material = _token(source_surface.get("to_material") or controls.get("to_material") or (transition_materials[-1] if transition_materials else ""))
    transition_profile = _token(source_surface.get("transition_profile") or controls.get("transition_profile"))
    transition_count = _number(source_surface.get("surface_transition_count") or controls.get("surface_transition_count"), default=0.0)
    if transition_materials or (from_material and to_material) or transition_profile or transition_count > 0.0:
        if from_material:
            transition_materials.append(from_material)
        if to_material:
            transition_materials.append(to_material)
        transition_materials = _dedupe(transition_materials)
        profile = transition_profile or "material_transition"
        grammar["transition_profile"] = profile
        targets = [_token(item) for item in _as_list(source_surface.get("story_targets") or source_surface.get("decal_targets")) if _token(item)] or ["edge", "surface"]
        grammar["materials"] = _dedupe([*grammar["materials"], *transition_materials])
        grammar["material_layers"] = _dedupe([*grammar["material_layers"], *transition_materials])
        grammar["patterns"] = _dedupe([*grammar["patterns"], profile])
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], "material_transition_band"])
        grammar["features"].append(
            _feature(
                "surface_transition",
                targets,
                profile=profile,
                material=transition_materials[-1] if transition_materials else "",
                roughness_delta=0.08,
                normal_delta=0.08,
                wear_delta=0.14,
                wear_layer="transition_band",
            )
        )

    weather_type = _token(source_surface.get("weather_type") or controls.get("weather_type"))
    liquid_type = _token(source_surface.get("liquid_type") or controls.get("liquid_type"))
    wetness_level = _number(source_surface.get("wetness_level") or source_surface.get("moisture_level") or controls.get("wetness_level"), default=0.0)
    puddle_count = _number(source_surface.get("puddle_count") or controls.get("puddle_count"), default=0.0)
    fog_density = _number(source_surface.get("fog_density") or source_surface.get("mist_density") or controls.get("fog_density"), default=0.0)
    smoke_density = _number(source_surface.get("smoke_density") or controls.get("smoke_density"), default=0.0)
    heat_haze_level = _number(source_surface.get("heat_haze_level") or controls.get("heat_haze_level"), default=0.0)
    environment_decals = [
        _token(item)
        for item in (_as_list(source_surface.get("environment_decals")) + _as_list(source_surface.get("weather_decals")))
        if _token(item)
    ]
    if weather_type or liquid_type or wetness_level > 0.0 or puddle_count > 0.0:
        wet_material = _token(source_surface.get("wet_material") or controls.get("wet_material"), "wet_stone")
        liquid = liquid_type or _token(source_surface.get("liquid_type"), "shallow_water")
        if weather_type:
            grammar["weather_type"] = weather_type
        grammar["liquid_type"] = liquid
        grammar["materials"] = _dedupe([*grammar["materials"], liquid, wet_material, "foam"])
        grammar["material_layers"] = _dedupe([*grammar["material_layers"], liquid, "wet_sheen", "waterline_wear"])
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], *environment_decals, "wet_streak", "waterline_wear"])
        grammar["patterns"] = _dedupe([*grammar["patterns"], "water_ripple", "wet_sheen"])
        grammar["wear_level"] = round(max(_number(grammar.get("wear_level"), 0.0), min(1.0, wetness_level or 0.36)), 6)
        grammar["features"].append(
            _feature(
                "wetness",
                ["ground", "surface", "edge", "terrain"],
                profile="wet_sheen",
                material=liquid,
                roughness_delta=-0.18,
                normal_delta=0.06 + min(0.16, puddle_count * 0.01),
                wear_delta=0.08,
                basecolor_mix=[44, 78, 86],
                mix=0.16 + min(0.20, wetness_level * 0.15),
                wear_layer="wetness",
            )
        )
    if fog_density > 0.0 or smoke_density > 0.0 or heat_haze_level > 0.0 or weather_type in {"fog", "mist", "smoke", "ash", "storm"}:
        profile = "heat_shimmer" if heat_haze_level > 0.0 else "soot_gradient" if smoke_density > 0.0 else "volume_haze"
        material = "heat_discolor" if heat_haze_level > 0.0 else "soot" if smoke_density > 0.0 else "cloud_vapor"
        grammar["materials"] = _dedupe([*grammar["materials"], material, "air_haze"])
        grammar["material_layers"] = _dedupe([*grammar["material_layers"], material, "air_haze"])
        grammar["story_decals"] = _dedupe([*grammar["story_decals"], *environment_decals, "fog_gradient" if fog_density else "heat_bloom"])
        grammar["patterns"] = _dedupe([*grammar["patterns"], profile])
        grammar["features"].append(
            _feature(
                "environment_volume",
                ["air", "surface", "light", "edge"],
                profile=profile,
                material=material,
                roughness_delta=0.08 if smoke_density else -0.04,
                normal_delta=0.05,
                wear_delta=0.16 if smoke_density else 0.04,
                basecolor_mix=[42, 42, 40] if smoke_density else [180, 190, 192],
                mix=0.12 + min(0.22, max(fog_density, smoke_density, heat_haze_level) * 0.18),
                wear_layer="environment_effect",
            )
        )

    if not any(grammar.get(key) for key in ("materials", "material_layers", "story_decals", "zones", "features")):
        return {}
    if tier != "game":
        for feature in grammar.get("features", []):
            if isinstance(feature, dict):
                _scale_feature_deltas(feature, tier)
    grammar["fidelity_tier"] = tier
    return grammar


def surface_grammar_for_asset(asset: dict[str, Any]) -> dict[str, Any]:
    """Derive surface grammar from a materialized asset dictionary."""
    assembly = asset.get("assembly", {}) if isinstance(asset.get("assembly"), dict) else {}
    resolved_family = assembly.get("resolved_family", {}) if isinstance(assembly.get("resolved_family"), dict) else {}
    values = resolved_family.get("values", {}) if isinstance(resolved_family.get("values"), dict) else {}
    family = (
        values.get("runtime_family")
        or values.get("family_key")
        or assembly.get("runtime_family")
        or assembly.get("family_key")
        or assembly.get("family")
    )
    shape_controls = asset.get("build", {}).get("shape", {})
    creative = creative_grammar_from_asset(
        asset,
        family=str(family or ""),
        shape_controls=shape_controls if isinstance(shape_controls, dict) else {},
    )
    merged_shape_controls = creative.get("shape_controls", shape_controls)
    object_grammar = object_grammar_from_asset(
        asset,
        family=str(family or ""),
        shape_controls=shape_controls if isinstance(shape_controls, dict) else {},
    )
    object_shape_controls = dict(merged_shape_controls if isinstance(merged_shape_controls, dict) else {})
    object_shape_controls.update(dict(object_grammar.get("shape_controls") or {}))
    if not family and object_grammar.get("summary", {}).get("matched_archetypes"):
        family = "procedural_setpiece"
    return surface_grammar_for_controls(
        procedural_family=str(family or ""),
        shape_controls=object_shape_controls if isinstance(object_shape_controls, dict) else {},
        surface=asset.get("surface", {}) if isinstance(asset.get("surface"), dict) else {},
        fidelity_tier=_infer_fidelity_tier_from_asset(asset),
    )


def merge_surface_grammar(surface: dict[str, Any], grammar: dict[str, Any]) -> dict[str, Any]:
    """Return source surface controls with grammar-derived authoring merged in."""
    if not grammar:
        return dict(surface)
    out = dict(surface)
    for key in (
        "materials",
        "material_layers",
        "layers",
        "story_decals",
        "decals",
        "decal_targets",
        "story_targets",
        "patterns",
        "damage_decals",
        "damage_targets",
        "exposed_materials",
        "transition_materials",
        "weather_decals",
        "environment_decals",
    ):
        values = [str(item) for item in _as_list(grammar.get(key)) if str(item)]
        if values:
            out[key] = _dedupe([*values, *[str(item) for item in _as_list(out.get(key)) if str(item)]])
    zones = dict(out.get("zones", {})) if isinstance(out.get("zones"), dict) else {}
    zones.update({str(key): str(value) for key, value in dict(grammar.get("zones", {})).items()})
    if zones:
        out["zones"] = zones
    for key in ("wear_story", "wear_level"):
        if grammar.get(key) is not None:
            out[key] = grammar[key]
    grammar_metadata_keys = {
        "schema",
        "procedural_family",
        "landform",
        "biome",
        "environment_pattern",
        "density",
        "boat_type",
        "furniture_type",
        "foliage_type",
        "object_archetype",
        "damage_type",
        "transition_profile",
        "weather_type",
        "liquid_type",
    }
    out["surface_grammar"] = {
        key: value for key, value in grammar.items() if key in grammar_metadata_keys and _present(value)
    }
    return out


def _matches_feature(feature: dict[str, Any], *, part: str, material: str) -> bool:
    targets = [_token(item) for item in _as_list(feature.get("targets")) if _token(item)]
    if not targets:
        return True
    text = f"{_token(part)} {_token(material)}"
    return any(target in text for target in targets)


def _mix_color(base: list[Any], target: list[Any], amount: float) -> list[int]:
    amount = max(0.0, min(1.0, amount))
    out: list[int] = []
    for index in range(3):
        base_value = float(base[index]) if index < len(base) else 0.0
        target_value = float(target[index]) if index < len(target) else base_value
        out.append(int(round(max(0.0, min(255.0, base_value * (1.0 - amount) + target_value * amount)))))
    return out


def apply_surface_grammar_to_zone(
    payload: dict[str, Any],
    *,
    grammar: dict[str, Any],
    part: str,
    material: str,
) -> dict[str, Any]:
    """Apply matching grammar features to one material-zone payload."""
    if not grammar:
        return payload
    out = dict(payload)
    matched = [
        deepcopy(feature)
        for feature in grammar.get("features", [])
        if isinstance(feature, dict) and _matches_feature(feature, part=part, material=material)
    ]
    if not matched:
        return out
    zone_metadata_keys = {
        "schema",
        "landform",
        "biome",
        "environment_pattern",
        "density",
        "boat_type",
        "furniture_type",
        "foliage_type",
        "object_archetype",
    }
    out["surface_grammar"] = {
        key: value for key, value in grammar.items() if key in zone_metadata_keys and _present(value)
    }
    out["surface_features"] = [{"kind": str(item.get("kind", "")), "profile": str(item.get("profile", ""))} for item in matched]
    for feature in matched:
        if feature.get("profile"):
            out["surface_profile"] = str(feature["profile"])
        out["roughness"] = round(max(0.02, min(0.98, float(out.get("roughness", 0.58)) + float(feature.get("roughness_delta", 0.0)))), 6)
        roughness_range = list(out.get("roughness_range", [out["roughness"], out["roughness"]]))
        if len(roughness_range) >= 2:
            delta = float(feature.get("roughness_delta", 0.0))
            out["roughness_range"] = [
                round(max(0.02, min(0.98, float(roughness_range[0]) + delta)), 6),
                round(max(0.02, min(0.98, float(roughness_range[1]) + delta)), 6),
            ]
        out["normal_intensity"] = round(
            max(0.0, min(1.0, float(out.get("normal_intensity", 0.07)) + float(feature.get("normal_delta", 0.0)))),
            6,
        )
        out["wear"] = round(max(0.0, min(1.0, float(out.get("wear", 0.0)) + float(feature.get("wear_delta", 0.0)))), 6)
        if feature.get("basecolor_mix"):
            out["basecolor"] = _mix_color(list(out.get("basecolor", [118, 118, 118])), list(feature["basecolor_mix"]), float(feature.get("mix", 0.0)))
        if feature.get("emissive"):
            current = list(out.get("emissive", [0, 0, 0]))
            out["emissive"] = [max(int(current[index]) if index < len(current) else 0, int(feature["emissive"][index])) for index in range(3)]
        wear_layer = str(feature.get("wear_layer", "") or "")
        if wear_layer:
            layers = list(out.get("wear_layers", [])) if isinstance(out.get("wear_layers"), list) else []
            intensity = round(max(0.05, min(1.0, float(feature.get("wear_delta", 0.12)) + float(out.get("wear", 0.0)) * 0.35)), 6)
            layers.append({"kind": wear_layer, "intensity": intensity})
            out["wear_layers"] = layers
    return out
