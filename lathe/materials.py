"""Material authoring helpers.

Resolves material references, applies default PBR parameters and
feeds the surface stage and packaging.
"""

from __future__ import annotations

from typing import Any

from .creative_grammar import creative_grammar_from_asset
from .geometry_detail import style_pack_surface_defaults
from .object_grammar import object_grammar_from_asset
from .surface_grammar import (
    apply_surface_grammar_to_zone,
    merge_surface_grammar,
    surface_grammar_for_asset,
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _token(value: Any) -> str:
    return str(value).lower().replace("-", "_").replace(" ", "_").strip()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _level(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    token = _token(value)
    levels = {
        "none": 0.0,
        "off": 0.0,
        "low": 0.25,
        "light": 0.35,
        "medium": 0.55,
        "standard": 0.55,
        "high": 0.75,
        "heavy": 0.9,
        "hero": 1.0,
    }
    if token in levels:
        return levels[token]
    try:
        return max(0.0, float(token))
    except ValueError:
        return default


def palette_for_material(name: str) -> dict[str, Any]:
    """Palette for material.

    Args:
        name: name argument.

    Returns:
        The result.
    """
    lname = name.lower()
    if "water" in lname:
        return {
            "basecolor": [50, 112, 142],
            "metallic": 0.0,
            "roughness": 0.10,
            "roughness_range": [0.04, 0.20],
            "emissive": [0, 8, 16],
            "surface_profile": "water_ripple",
            "wear": 0.04,
            "normal_intensity": 0.24,
        }
    if "foam" in lname:
        return {
            "basecolor": [218, 232, 224],
            "metallic": 0.0,
            "roughness": 0.46,
            "roughness_range": [0.30, 0.62],
            "emissive": [0, 0, 0],
            "surface_profile": "foam_wash",
            "wear": 0.02,
            "normal_intensity": 0.08,
        }
    if "salt" in lname:
        return {
            "basecolor": [202, 208, 198],
            "metallic": 0.0,
            "roughness": 0.82,
            "roughness_range": [0.66, 0.94],
            "emissive": [0, 0, 0],
            "surface_profile": "painted_panel",
            "wear": 0.42,
            "normal_intensity": 0.08,
        }
    if "sand" in lname:
        return {
            "basecolor": [174, 145, 92],
            "metallic": 0.0,
            "roughness": 0.94,
            "roughness_range": [0.84, 0.99],
            "emissive": [0, 0, 0],
            "surface_profile": "sand_ripple",
            "wear": 0.18,
            "normal_intensity": 0.20,
        }
    if any(token in lname for token in ("mud", "silt", "packed_soil", "talus", "gravel", "dust", "ash", "grime")):
        return {
            "basecolor": [54, 54, 48] if "grime" in lname else [70, 58, 42] if "ash" not in lname else [86, 82, 78],
            "metallic": 0.0,
            "roughness": 0.93,
            "roughness_range": [0.80, 0.99],
            "emissive": [0, 0, 0],
            "surface_profile": "concrete_mottle" if "grime" in lname else "mud_silt" if "gravel" not in lname and "talus" not in lname else "rock_scree",
            "wear": 0.32,
            "normal_intensity": 0.24,
        }
    if any(token in lname for token in ("grass", "leaf", "bark", "algae", "lichen")):
        return {
            "basecolor": [70, 112, 58] if "leaf" not in lname and "bark" not in lname else [118, 82, 40],
            "metallic": 0.0,
            "roughness": 0.88,
            "roughness_range": [0.74, 0.96],
            "emissive": [0, 0, 0],
            "surface_profile": "leaf_litter" if "leaf" in lname or "bark" in lname else "grass_mottle",
            "wear": 0.16,
            "normal_intensity": 0.18,
        }
    if "fungus" in lname or "mushroom" in lname:
        return {
            "basecolor": [154, 128, 98],
            "metallic": 0.0,
            "roughness": 0.84,
            "roughness_range": [0.70, 0.94],
            "emissive": [0, 0, 0],
            "surface_profile": "leaf_litter",
            "wear": 0.12,
            "normal_intensity": 0.16,
        }
    if "flower" in lname or "petal" in lname or "blossom" in lname:
        return {
            "basecolor": [186, 92, 132],
            "metallic": 0.0,
            "roughness": 0.74,
            "roughness_range": [0.62, 0.88],
            "emissive": [0, 0, 0],
            "surface_profile": "grass_mottle",
            "wear": 0.08,
            "normal_intensity": 0.10,
        }
    if "terracotta" in lname or "planter" in lname:
        return {
            "basecolor": [146, 76, 48],
            "metallic": 0.0,
            "roughness": 0.82,
            "roughness_range": [0.70, 0.94],
            "emissive": [0, 0, 0],
            "surface_profile": "mineral_stone",
            "wear": 0.22,
            "normal_intensity": 0.16,
        }
    if "snow" in lname or "frost" in lname:
        return {
            "basecolor": [220, 226, 228],
            "metallic": 0.0,
            "roughness": 0.82,
            "roughness_range": [0.62, 0.94],
            "emissive": [0, 0, 0],
            "surface_profile": "snow_drift",
            "wear": 0.10,
            "normal_intensity": 0.10,
        }
    if "ice" in lname:
        return {
            "basecolor": [174, 214, 228],
            "metallic": 0.0,
            "roughness": 0.20,
            "roughness_range": [0.08, 0.34],
            "emissive": [8, 24, 36],
            "surface_profile": "ice_scratch",
            "wear": 0.08,
            "normal_intensity": 0.12,
        }
    if "lava" in lname:
        return {
            "basecolor": [132, 48, 24],
            "metallic": 0.0,
            "roughness": 0.42,
            "roughness_range": [0.24, 0.64],
            "emissive": [220, 74, 18],
            "surface_profile": "lava_crack",
            "wear": 0.16,
            "normal_intensity": 0.18,
        }
    if any(token in lname for token in ("basalt", "stratified", "worn_stone", "wet_stone", "cold_stone", "bleached_stone")):
        basecolor = [82, 88, 84] if "wet" in lname else [112, 108, 96] if "bleached" in lname else [72, 72, 72]
        return {
            "basecolor": basecolor,
            "metallic": 0.0,
            "roughness": 0.54 if "wet" in lname else 0.74,
            "roughness_range": [0.36, 0.66] if "wet" in lname else [0.56, 0.90],
            "emissive": [0, 0, 0],
            "surface_profile": "stratified_stone" if "stratified" in lname else "cracked_stone",
            "wear": 0.32,
            "normal_intensity": 0.22,
        }
    if "asphalt" in lname:
        return {
            "basecolor": [34, 36, 38],
            "metallic": 0.0,
            "roughness": 0.88,
            "roughness_range": [0.78, 0.96],
            "emissive": [0, 0, 0],
            "surface_profile": "asphalt_grit",
            "wear": 0.42,
            "normal_intensity": 0.20,
        }
    if "concrete" in lname or "plaster" in lname or "stone" in lname or "tile" in lname:
        return {
            "basecolor": [126, 126, 116],
            "metallic": 0.0,
            "roughness": 0.76,
            "roughness_range": [0.62, 0.90],
            "emissive": [0, 0, 0],
            "surface_profile": "mineral_stone",
            "wear": 0.24,
            "normal_intensity": 0.18,
        }
    if "soil" in lname or "dirt" in lname or "moss" in lname:
        return {
            "basecolor": [70, 78, 48] if "moss" in lname else [92, 70, 48],
            "metallic": 0.0,
            "roughness": 0.92,
            "roughness_range": [0.82, 0.98],
            "emissive": [0, 0, 0],
            "surface_profile": "natural_ground",
            "wear": 0.34,
            "normal_intensity": 0.22,
        }
    if "oak" in lname or "wood" in lname:
        return {
            "basecolor": [125, 82, 48],
            "metallic": 0.0,
            "roughness": 0.68,
            "roughness_range": [0.56, 0.82],
            "emissive": [0, 0, 0],
            "surface_profile": "wood_grain",
            "wear": 0.18,
            "normal_intensity": 0.12,
        }
    if "leather" in lname:
        return {
            "basecolor": [92, 58, 36],
            "metallic": 0.0,
            "roughness": 0.62,
            "roughness_range": [0.50, 0.76],
            "emissive": [0, 0, 0],
            "surface_profile": "creased_leather",
            "wear": 0.20,
            "normal_intensity": 0.16,
        }
    if any(token in lname for token in ("fabric", "canvas", "cloth", "rope", "upholstery")):
        return {
            "basecolor": [118, 112, 94] if "rope" in lname else [112, 104, 84],
            "metallic": 0.0,
            "roughness": 0.86,
            "roughness_range": [0.74, 0.94],
            "emissive": [0, 0, 0],
            "surface_profile": "woven_fabric",
            "wear": 0.16,
            "normal_intensity": 0.15,
        }
    if "laminate" in lname:
        return {
            "basecolor": [154, 150, 136],
            "metallic": 0.0,
            "roughness": 0.48,
            "roughness_range": [0.36, 0.66],
            "emissive": [0, 0, 0],
            "surface_profile": "painted_panel",
            "wear": 0.14,
            "normal_intensity": 0.08,
        }
    if "brass" in lname:
        return {
            "basecolor": [191, 150, 72],
            "metallic": 1.0,
            "roughness": 0.36,
            "roughness_range": [0.22, 0.52],
            "emissive": [0, 0, 0],
            "surface_profile": "worn_brass",
            "wear": 0.26,
            "normal_intensity": 0.10,
        }
    if "cast_iron" in lname or "iron" in lname:
        return {
            "basecolor": [58, 62, 64],
            "metallic": 1.0,
            "roughness": 0.58,
            "roughness_range": [0.44, 0.76],
            "emissive": [0, 0, 0],
            "surface_profile": "brushed_metal",
            "wear": 0.34,
            "normal_intensity": 0.14,
        }
    if "cable_insulation" in lname or "insulation" in lname:
        return {
            "basecolor": [36, 44, 54],
            "metallic": 0.0,
            "roughness": 0.70,
            "roughness_range": [0.58, 0.84],
            "emissive": [0, 0, 0],
            "surface_profile": "carbon_rubber",
            "wear": 0.16,
            "normal_intensity": 0.12,
        }
    if "safety_grate" in lname or "grate" in lname:
        return {
            "basecolor": [118, 126, 124],
            "metallic": 1.0,
            "roughness": 0.56,
            "roughness_range": [0.42, 0.74],
            "emissive": [0, 0, 0],
            "surface_profile": "brushed_metal",
            "wear": 0.30,
            "normal_intensity": 0.16,
        }
    if "rubber_tread" in lname or "tread" in lname:
        return {
            "basecolor": [36, 38, 38],
            "metallic": 0.0,
            "roughness": 0.78,
            "roughness_range": [0.66, 0.92],
            "emissive": [0, 0, 0],
            "surface_profile": "carbon_rubber",
            "wear": 0.22,
            "normal_intensity": 0.16,
        }
    if "gasket" in lname:
        return {
            "basecolor": [34, 36, 34],
            "metallic": 0.0,
            "roughness": 0.76,
            "roughness_range": [0.64, 0.90],
            "emissive": [0, 0, 0],
            "surface_profile": "carbon_rubber",
            "wear": 0.18,
            "normal_intensity": 0.12,
        }
    if "velvet" in lname or "lining" in lname:
        return {
            "basecolor": [132, 28, 32],
            "metallic": 0.0,
            "roughness": 0.82,
            "roughness_range": [0.74, 0.92],
            "emissive": [0, 0, 0],
            "surface_profile": "fabric_lining",
            "wear": 0.05,
            "normal_intensity": 0.05,
        }
    if "aluminum" in lname or "steel" in lname:
        return {
            "basecolor": [104, 112, 122],
            "metallic": 1.0,
            "roughness": 0.42,
            "roughness_range": [0.28, 0.56],
            "emissive": [0, 0, 0],
            "surface_profile": "brushed_metal",
            "wear": 0.20,
            "normal_intensity": 0.08,
        }
    if "metal" in lname:
        return {
            "basecolor": [106, 112, 118],
            "metallic": 1.0,
            "roughness": 0.46,
            "roughness_range": [0.30, 0.62],
            "emissive": [0, 0, 0],
            "surface_profile": "worked_metal",
            "wear": 0.22,
            "normal_intensity": 0.10,
        }
    if "carbon" in lname or "rubber" in lname:
        return {
            "basecolor": [46, 50, 54],
            "metallic": 0.0,
            "roughness": 0.72,
            "roughness_range": [0.64, 0.86],
            "emissive": [0, 0, 0],
            "surface_profile": "carbon_rubber",
            "wear": 0.08,
            "normal_intensity": 0.14,
        }
    if "plastic" in lname:
        return {
            "basecolor": [92, 100, 96] if "utility" in lname else [78, 84, 92],
            "metallic": 0.0,
            "roughness": 0.50,
            "roughness_range": [0.38, 0.68],
            "emissive": [0, 0, 0],
            "surface_profile": "molded_plastic",
            "wear": 0.12,
            "normal_intensity": 0.08,
        }
    if "glass" in lname:
        return {
            "basecolor": [214, 152, 78],
            "metallic": 0.0,
            "roughness": 0.18,
            "roughness_range": [0.10, 0.28],
            "emissive": [26, 18, 6],
            "surface_profile": "screen_glass",
            "wear": 0.03,
            "normal_intensity": 0.04,
        }
    if "emissive" in lname or "neon" in lname or "light" in lname:
        return {
            "basecolor": [72, 154, 190],
            "metallic": 0.0,
            "roughness": 0.24,
            "roughness_range": [0.14, 0.36],
            "emissive": [48, 170, 230],
            "surface_profile": "emissive_panel",
            "wear": 0.05,
            "normal_intensity": 0.04,
        }
    if "grease" in lname or "oil" in lname:
        return {
            "basecolor": [28, 30, 26],
            "metallic": 0.0,
            "roughness": 0.28,
            "roughness_range": [0.16, 0.42],
            "emissive": [0, 0, 0],
            "surface_profile": "mud_silt",
            "wear": 0.36,
            "normal_intensity": 0.16,
        }
    if "paint" in lname:
        return {
            "basecolor": [92, 102, 116],
            "metallic": 0.0,
            "roughness": 0.54,
            "roughness_range": [0.42, 0.68],
            "emissive": [0, 0, 0],
            "surface_profile": "painted_panel",
            "wear": 0.16,
            "normal_intensity": 0.10,
        }
    return {
        "basecolor": [118, 118, 118],
        "metallic": 0.0,
        "roughness": 0.58,
        "roughness_range": [0.48, 0.68],
        "emissive": [0, 0, 0],
        "surface_profile": "neutral_panel",
        "wear": 0.10,
        "normal_intensity": 0.07,
    }


def _custom_material(asset: dict[str, Any], name: str) -> dict[str, Any] | None:
    resolved = asset.get("surface", {}).get("resolved_materials", {})
    material = resolved.get(name)
    if not material:
        return None
    values = dict(material.get("values", {}))
    if values:
        return {
            "basecolor": list(values.get("basecolor", palette_for_material(name)["basecolor"])),
            "metallic": float(values.get("metallic", palette_for_material(name)["metallic"])),
            "roughness": float(values.get("roughness", palette_for_material(name)["roughness"])),
            "roughness_range": list(
                values.get("roughness_range", palette_for_material(name)["roughness_range"])
            ),
            "emissive": list(values.get("emissive", palette_for_material(name)["emissive"])),
            "surface_profile": str(
                values.get("surface_profile", palette_for_material(name)["surface_profile"])
            ),
            "wear": float(values.get("wear", palette_for_material(name)["wear"])),
            "normal_intensity": float(
                values.get("normal_intensity", palette_for_material(name)["normal_intensity"])
            ),
        }
    return None


def assign_material_zones(asset: dict[str, Any], part_names: list[str]) -> list[dict[str, Any]]:
    """Assign material zones.

    Args:
        asset: asset argument.
        part_names: part_names argument.

    Returns:
        The result.
    """
    surface_grammar = surface_grammar_for_asset(asset)
    surface = merge_surface_grammar(surface_with_style_pack_defaults(asset), surface_grammar)
    materials = list(surface.get("materials", [])) or list(asset.get("intent", {}).get("materials", []))
    material_layers = [str(item) for item in _as_list(surface.get("material_layers") or surface.get("layers"))]
    if material_layers:
        materials = list(dict.fromkeys([*material_layers, *materials]))
    palette = surface.get("resolved_palette", {})
    palette_materials = list(
        palette.get("values", {}).get("materials", []) or palette.get("values", {}).get("slots", [])
    )
    if palette_materials:
        materials = list(dict.fromkeys([*materials, *palette_materials]))
    surface_program = surface.get("resolved_surface_program", {})
    zone_overrides = dict(
        surface.get("zones", {}) or surface_program.get("values", {}).get("zones", {}) or {}
    )
    primary = materials[0] if materials else "default_body"
    secondary = materials[1] if len(materials) > 1 else primary
    tertiary = materials[2] if len(materials) > 2 else secondary
    wear_story = _token(surface.get("wear_story") or surface.get("usage_history") or surface.get("story"))
    wear_level = _level(
        surface.get("wear_level", surface.get("edge_wear", surface.get("damage_level"))),
        _story_wear_default(wear_story),
    )
    story_marks = [
        str(item)
        for item in _as_list(surface.get("story_decals"))
        + _as_list(surface.get("faction_marks"))
        + _as_list(surface.get("markings"))
    ]
    component_materials: dict[str, str] = {}
    for component in asset.get("assembly", {}).get("resolved_components", []):
        values = component.get("values", {})
        part = values.get("part")
        material_name = values.get("material_zone") or values.get("material")
        if part and material_name:
            component_materials[str(part)] = str(material_name)
    zones = []
    for part in sorted(set(part_names)):
        lname = part.lower()
        material_name = str(zone_overrides.get(part, component_materials.get(part, primary)))
        matched_zone_override = part in zone_overrides
        if not matched_zone_override and part not in component_materials:
            for key, value in sorted(zone_overrides.items(), key=_zone_specificity, reverse=True):
                key_text = str(key).lower()
                if key_text and key_text in lname:
                    material_name = str(value)
                    matched_zone_override = True
                    break
        if not matched_zone_override and part not in component_materials and any(
            token in lname for token in ("handle", "hinge", "lock", "frame", "bracket", "rotor")
        ):
            material_name = secondary
        elif not matched_zone_override and part not in component_materials and any(
            token in lname
            for token in (
                "module_socket",
                "module_slot",
                "child_socket",
                "parking_bay",
                "machine_pad",
                "mount",
            )
        ):
            material_name = _first_material_matching(materials, "weathered", "steel", "metal", "paint") or secondary
        elif not matched_zone_override and part not in component_materials and any(
            token in lname for token in ("glass", "screen", "socket", "lining")
        ):
            material_name = tertiary
        elif not matched_zone_override and part not in component_materials:
            material_name = _semantic_zone_material(
                lname,
                primary=material_name,
                secondary=secondary,
                tertiary=tertiary,
                materials=materials,
            )
        payload = _custom_material(asset, material_name) or palette_for_material(material_name)
        payload = _apply_surface_story(
            payload,
            part=part,
            material_layers=material_layers,
            wear_story=wear_story,
            wear_level=wear_level,
            story_marks=story_marks,
        )
        payload = apply_surface_grammar_to_zone(
            payload,
            grammar=surface_grammar,
            part=part,
            material=material_name,
        )
        zones.append(
            {
                "part": part,
                "material": material_name,
                **payload,
            }
        )
    return zones


def _first_material_matching(materials: list[str], *tokens: str) -> str | None:
    for material in materials:
        lname = material.lower()
        if any(token in lname for token in tokens):
            return material
    return None


def _zone_specificity(item: tuple[str, Any]) -> tuple[int, int]:
    key = str(item[0]).lower()
    priority = {
        "basin": 8,
        "rim": 8,
        "edge": 7,
        "curb": 7,
        "clearing": 7,
        "path": 6,
        "catwalk": 8,
        "deck": 8,
        "walkway": 8,
        "span": 8,
        "guardrail": 8,
        "railing": 8,
        "ladder": 8,
        "rung": 8,
        "ramp": 8,
        "gantry": 8,
        "elevator": 8,
        "lift": 8,
        "shaft": 8,
        "platform": 8,
        "tunnel": 8,
        "scaffold": 8,
        "gate": 8,
        "setpiece": 8,
        "courtyard": 8,
        "perimeter": 8,
        "dock": 8,
        "apron": 8,
        "ritual": 8,
        "socket": 8,
        "module": 8,
        "module_slot": 9,
        "mount": 9,
        "parking_bay": 9,
        "mooring": 9,
        "machine_pad": 9,
        "room_entry": 9,
        "furniture_anchor": 9,
        "terrain_anchor": 9,
        "rotor": 8,
        "cargo_module": 8,
        "turret": 8,
        "pontoon": 8,
        "sail": 8,
        "cargo_hold": 8,
        "hydraulic": 8,
        "crane": 8,
        "ceiling_light": 8,
        "alcove": 8,
        "shelf": 8,
        "lamp": 8,
        "bush": 8,
        "grass": 8,
        "rock": 8,
        "flower": 8,
        "tower": 7,
        "building": 7,
        "utility": 7,
        "support": 7,
        "access": 1,
        "ridge": 6,
        "cliff": 6,
        "water": 5,
        "terrain": 1,
        "ground": 1,
        "body": 0,
    }.get(key, 4)
    return (priority, len(key))


def _semantic_zone_material(
    part_name: str,
    *,
    primary: str,
    secondary: str,
    tertiary: str,
    materials: list[str],
) -> str:
    if any(token in part_name for token in ("window", "glass", "screen", "lens", "windshield")):
        return _first_material_matching(materials, "glass") or tertiary
    if any(token in part_name for token in ("module_socket", "module_slot", "child_socket", "mount")):
        return _first_material_matching(materials, "weathered", "steel", "metal") or secondary
    if "parking_bay" in part_name:
        return _first_material_matching(materials, "warning", "paint", "concrete") or secondary
    if "mooring" in part_name:
        return _first_material_matching(materials, "marine", "paint", "weathered", "steel") or secondary
    if "machine_pad" in part_name:
        return _first_material_matching(materials, "industrial", "steel", "concrete") or secondary
    if any(token in part_name for token in ("setpiece", "courtyard")):
        return _first_material_matching(materials, "concrete", "stone") or primary
    if any(token in part_name for token in ("primary_building", "secondary_building", "warehouse")):
        return _first_material_matching(materials, "paint", "stone", "metal") or primary
    if any(token in part_name for token in ("perimeter", "gatehouse", "watchtower")):
        return _first_material_matching(materials, "warning", "paint", "steel", "stone") or secondary
    if "dock" in part_name:
        return _first_material_matching(materials, "deck", "wood", "weathered", "steel") or secondary
    if "apron" in part_name:
        return _first_material_matching(materials, "concrete", "asphalt") or primary
    if "ritual" in part_name:
        return _first_material_matching(materials, "brass", "stone", "polished") or secondary
    if any(token in part_name for token in ("streetlight", "streetlamp", "lamp_post", "glow_panel")):
        return _first_material_matching(materials, "emissive", "light", "steel", "metal") or tertiary
    if any(token in part_name for token in ("fence", "gate", "sign", "signage")):
        return _first_material_matching(materials, "paint", "metal", "steel") or secondary
    if any(token in part_name for token in ("utility_pole", "pole", "wire", "cable_span")):
        return _first_material_matching(materials, "weathered", "steel", "metal") or secondary
    if any(token in part_name for token in ("barrier", "barricade", "bollard")):
        return _first_material_matching(materials, "warning", "paint", "concrete") or secondary
    if any(token in part_name for token in ("trash_bin", "waste_bin")) or (
        "bin" in part_name and "cabin" not in part_name
    ):
        return _first_material_matching(materials, "plastic", "recycled", "metal") or secondary
    if "bench" in part_name and "workbench" not in part_name:
        return _first_material_matching(materials, "wood", "plastic", "metal") or primary
    if any(token in part_name for token in ("kiosk", "market_stall", "vendor_stall")):
        return _first_material_matching(materials, "paint", "metal", "wood") or primary
    if "street_crate" in part_name:
        return _first_material_matching(materials, "wood", "plastic") or primary
    if any(token in part_name for token in ("urban_base", "sidewalk", "curb")):
        return _first_material_matching(materials, "concrete", "asphalt") or primary
    if any(token in part_name for token in ("infrastructure_base", "service_base")):
        return _first_material_matching(materials, "concrete", "grime") or primary
    if any(token in part_name for token in ("pipe_run", "pipeline", "duct_run", "service_rail", "support_bracket")):
        return _first_material_matching(materials, "galvanized", "steel", "metal") or secondary
    if any(token in part_name for token in ("drain_channel", "manhole_cover", "manhole")):
        return _first_material_matching(materials, "cast_iron", "iron", "metal") or secondary
    if any(token in part_name for token in ("fire_hydrant", "hydrant", "valve_wheel", "valve")):
        return _first_material_matching(materials, "warning", "paint", "metal") or secondary
    if any(token in part_name for token in ("transformer_box", "substation")):
        return _first_material_matching(materials, "paint", "metal", "steel") or secondary
    if any(token in part_name for token in ("junction_box", "service_box")):
        return _first_material_matching(materials, "plastic", "utility", "metal") or secondary
    if any(token in part_name for token in ("overhead_conduit", "conduit", "cable_tray")):
        return _first_material_matching(materials, "galvanized", "steel", "insulation") or secondary
    if any(token in part_name for token in ("access_base", "tunnel_segment")):
        return _first_material_matching(materials, "concrete", "grime") or primary
    if any(token in part_name for token in ("catwalk_deck", "walkway_span", "access_platform")):
        return _first_material_matching(materials, "grate", "galvanized", "steel") or secondary
    if any(token in part_name for token in ("guardrail", "safety_gate")):
        return _first_material_matching(materials, "warning", "paint", "steel") or secondary
    if any(token in part_name for token in ("access_ladder", "gantry_frame", "scaffold_frame", "access_support")):
        return _first_material_matching(materials, "galvanized", "steel", "metal") or secondary
    if "access_ramp" in part_name:
        return _first_material_matching(materials, "rubber", "tread", "grate") or secondary
    if any(token in part_name for token in ("elevator_shaft", "lift_cabin")):
        return _first_material_matching(materials, "paint", "metal", "glass") or secondary
    if any(token in part_name for token in ("awning", "canopy")):
        return _first_material_matching(materials, "canvas", "fabric") or secondary
    if any(token in part_name for token in ("barrel", "receiver", "magazine", "trigger", "muzzle")):
        return _first_material_matching(materials, "gunmetal", "metal", "steel") or secondary
    if any(token in part_name for token in ("blade", "tip", "head", "axe", "hammer")):
        return _first_material_matching(materials, "edge", "steel", "metal") or secondary
    if any(token in part_name for token in ("stock", "grip", "handle")):
        return _first_material_matching(materials, "leather", "polymer", "wood") or secondary
    if any(token in part_name for token in ("sight", "optic")):
        return _first_material_matching(materials, "glass", "optic") or tertiary
    if any(token in part_name for token in ("balcony", "cornice", "trim", "dormer")):
        return _first_material_matching(materials, "trim", "paint", "wood") or secondary
    if any(token in part_name for token in ("roof", "chimney")):
        return _first_material_matching(materials, "roof", "tile", "stone") or secondary
    if any(token in part_name for token in ("partition", "wall", "alcove")):
        return _first_material_matching(materials, "plaster", "paint", "wood") or primary
    if any(token in part_name for token in ("corridor", "floor", "stair")):
        return _first_material_matching(materials, "wood", "floor", "concrete") or secondary
    if any(token in part_name for token in ("seat", "cushion", "mattress", "pillow", "upholstery")):
        return _first_material_matching(materials, "upholstery", "fabric", "leather") or secondary
    if any(token in part_name for token in ("chair", "table", "desk", "bed", "shelf", "cabinet", "drawer", "workbench")):
        return _first_material_matching(materials, "wood", "laminate", "paint") or primary
    if any(token in part_name for token in ("counter", "countertop")):
        return _first_material_matching(materials, "laminate", "stone", "wood") or primary
    if any(token in part_name for token in ("appliance", "fixture", "lamp")):
        return _first_material_matching(materials, "metal", "steel", "emissive") or secondary
    if "furniture" in part_name:
        return _first_material_matching(materials, "wood", "fabric", "metal") or primary
    if any(token in part_name for token in ("wheel", "tire", "rubber")):
        return _first_material_matching(materials, "rubber") or secondary
    if any(token in part_name for token in ("track", "tread", "conveyor", "belt")):
        return _first_material_matching(materials, "rubber", "carbon") or secondary
    if any(token in part_name for token in ("suspension", "axle", "gear", "piston", "hydraulic", "arm", "crane", "turret")):
        return _first_material_matching(materials, "steel", "metal", "bare_metal") or secondary
    if any(token in part_name for token in ("sail", "canvas")):
        return _first_material_matching(materials, "sailcloth", "canvas", "fabric") or secondary
    if any(token in part_name for token in ("rigging", "rope", "cable")):
        return _first_material_matching(materials, "rope", "fabric", "steel", "metal") or secondary
    if any(token in part_name for token in ("propeller", "prop")):
        return _first_material_matching(materials, "brass", "metal", "steel") or secondary
    if any(token in part_name for token in ("anchor", "railing")):
        return _first_material_matching(materials, "steel", "metal", "weathered") or secondary
    if any(token in part_name for token in ("hull", "keel", "rudder")):
        return _first_material_matching(materials, "marine", "paint", "wood", "steel") or primary
    if any(token in part_name for token in ("pontoon", "float")):
        return _first_material_matching(materials, "rubber", "marine", "paint") or primary
    if any(token in part_name for token in ("outrigger", "cargo_hold", "hold")):
        return _first_material_matching(materials, "deck", "wood", "paint") or secondary
    if any(token in part_name for token in ("machine", "base", "column", "cargo", "tank", "vessel")):
        return _first_material_matching(materials, "industrial", "paint", "metal") or primary
    if any(token in part_name for token in ("wing", "rotor")):
        return _first_material_matching(materials, "paint", "metal", "aluminum") or secondary
    if any(token in part_name for token in ("tree_branch", "trunk", "root", "log", "bark")):
        return _first_material_matching(materials, "bark", "wood") or secondary
    if any(token in part_name for token in ("canopy", "leaf", "bush", "shrub")):
        return _first_material_matching(materials, "leaf", "grass", "moss") or secondary
    if any(token in part_name for token in ("grass", "reed", "vine")):
        return _first_material_matching(materials, "grass", "moss", "leaf") or secondary
    if any(token in part_name for token in ("mushroom", "fungus")):
        return _first_material_matching(materials, "fungus", "mushroom") or secondary
    if any(token in part_name for token in ("flower", "blossom", "petal")):
        return _first_material_matching(materials, "flower", "petal") or tertiary
    if any(token in part_name for token in ("planter", "pot")):
        return _first_material_matching(materials, "terracotta", "stone", "clay") or secondary
    if any(token in part_name for token in ("road", "street", "asphalt", "junction", "intersection", "branch", "roundabout")):
        return _first_material_matching(materials, "asphalt") or primary
    if any(token in part_name for token in ("lane", "stripe", "marking", "label", "warning", "crosswalk")):
        return _first_material_matching(materials, "paint", "stripe") or secondary
    if any(token in part_name for token in ("sidewalk", "turnout", "pier", "abutment", "lot", "concrete")):
        return _first_material_matching(materials, "concrete", "stone") or secondary
    if any(token in part_name for token in ("terrain", "cliff", "ridge", "rock", "stone")):
        return _first_material_matching(materials, "stone", "rock", "soil") or primary
    if any(token in part_name for token in ("path", "soil", "ground", "moss")):
        return _first_material_matching(materials, "soil", "dirt", "moss") or primary
    if any(token in part_name for token in ("deck", "floor", "door", "mast")):
        return _first_material_matching(materials, "wood", "deck") or secondary
    if any(token in part_name for token in ("engine", "chassis", "railing", "bridge", "column")):
        return _first_material_matching(materials, "metal", "steel", "concrete") or secondary
    if any(token in part_name for token in ("light", "emissive", "lamp")):
        return _first_material_matching(materials, "emissive", "neon", "light") or tertiary
    return primary


def surface_with_style_pack_defaults(asset: dict[str, Any]) -> dict[str, Any]:
    """Return source surface controls with style-pack defaults filled in."""
    source_surface = dict(asset.get("surface", {}) or {})
    shape_controls = asset.get("build", {}).get("shape", {})
    if not isinstance(shape_controls, dict):
        shape_controls = {}
    base_shape_controls = dict(shape_controls)
    resolved_family = asset.get("assembly", {}).get("resolved_family", {})
    family = (
        resolved_family.get("values", {}).get("runtime_family")
        or resolved_family.get("values", {}).get("family_key")
        or asset.get("assembly", {}).get("runtime_family")
        or asset.get("assembly", {}).get("family_key")
        or asset.get("assembly", {}).get("family")
        or ""
    )
    creative = creative_grammar_from_asset(asset, family=str(family), shape_controls=shape_controls)
    creative_shape = creative.get("shape_controls")
    if isinstance(creative_shape, dict):
        shape_controls = creative_shape
    surface = dict(creative.get("surface", {})) if isinstance(creative.get("surface"), dict) else {}
    object_grammar = object_grammar_from_asset(asset, family=str(family), shape_controls=base_shape_controls)
    object_shape = object_grammar.get("shape_controls")
    if isinstance(object_shape, dict):
        shape_controls = {**shape_controls, **object_shape}
    object_surface = object_grammar.get("surface", {})
    if isinstance(object_surface, dict):
        for key, value in object_surface.items():
            if key in {"materials", "material_layers", "layers", "story_decals", "faction_marks", "markings", "patterns"}:
                surface[key] = list(
                    dict.fromkeys(
                        [
                            *[str(item) for item in _as_list(surface.get(key))],
                            *[str(item) for item in _as_list(value)],
                        ]
                    )
                )
            elif key == "zones" and isinstance(value, dict):
                zones = dict(surface.get("zones", {})) if isinstance(surface.get("zones"), dict) else {}
                zones.update({str(zone_key): str(zone_value) for zone_key, zone_value in value.items()})
                surface["zones"] = zones
            else:
                surface[key] = value
    for key in ("materials", "material_layers", "layers", "story_decals", "faction_marks", "markings", "patterns"):
        source_values = source_surface.get(key)
        if source_values:
            surface[key] = list(
                dict.fromkeys(
                    [
                        *[str(item) for item in _as_list(source_values)],
                        *[str(item) for item in _as_list(surface.get(key))],
                    ]
                )
            )
    for key, value in source_surface.items():
        if key not in surface:
            surface[key] = value
    defaults = style_pack_surface_defaults(
        shape_controls.get("style_pack", shape_controls.get("style_packs")),
        shape_controls.get("style_intensity"),
    )
    if not defaults:
        return surface
    for key in ("material_layers", "layers", "story_decals", "faction_marks", "markings"):
        default_values = defaults.get(key)
        if default_values and not surface.get(key):
            surface[key] = list(default_values) if isinstance(default_values, (list, tuple)) else [default_values]
    for key in ("wear_story", "usage_history", "story", "wear_level", "edge_wear", "damage_level"):
        if defaults.get(key) and not surface.get(key):
            surface[key] = defaults[key]
    return surface


def _story_wear_default(wear_story: str) -> float:
    return {
        "factory_new": 0.02,
        "new": 0.04,
        "used": 0.28,
        "field_used": 0.35,
        "battle_worn": 0.68,
        "ancient": 0.78,
        "salvaged": 0.62,
        "luxury": 0.10,
        "prototype": 0.18,
    }.get(wear_story, 0.0)


def _layer_role(part: str, material_layers: list[str]) -> str:
    if not material_layers:
        return ""
    lname = part.lower()
    if any(token in lname for token in ("screen", "glass", "lens", "socket", "label", "light")):
        return "accent"
    if any(token in lname for token in ("trim", "guard", "handle", "hinge", "frame", "bolt", "rivet")):
        return "secondary"
    return "base"


def _apply_surface_story(
    payload: dict[str, Any],
    *,
    part: str,
    material_layers: list[str],
    wear_story: str,
    wear_level: float,
    story_marks: list[str],
) -> dict[str, Any]:
    out = dict(payload)
    if material_layers:
        out["procedural_layers"] = list(material_layers)
        out["material_layer_role"] = _layer_role(part, material_layers)
    if wear_story:
        out["wear_story"] = wear_story
    if story_marks:
        out["story_marks"] = list(dict.fromkeys(story_marks))
    if wear_level > 0.0 or wear_story:
        wear_bonus = min(0.35, wear_level * 0.32)
        roughness = float(out.get("roughness", 0.58))
        normal_intensity = float(out.get("normal_intensity", 0.07))
        roughness_range = list(out.get("roughness_range", [roughness - 0.10, roughness + 0.10]))
        out["wear"] = round(_clamp01(float(out.get("wear", 0.1)) + wear_bonus), 6)
        out["roughness"] = round(_clamp01(roughness + wear_bonus * 0.34), 6)
        out["normal_intensity"] = round(_clamp01(normal_intensity + wear_bonus * 0.45), 6)
        out["roughness_range"] = [
            round(_clamp01(float(roughness_range[0]) - wear_bonus * 0.15), 6),
            round(_clamp01(float(roughness_range[1]) + wear_bonus * 0.22), 6),
        ]
        out["wear_layers"] = _wear_layers_for_story(wear_story, wear_level)
    return out


def _wear_layers_for_story(wear_story: str, wear_level: float) -> list[dict[str, Any]]:
    if wear_level <= 0.0 and not wear_story:
        return []
    layers = [
        {"kind": "edge_wear", "intensity": round(min(1.0, wear_level), 6)},
        {"kind": "micro_scratches", "intensity": round(min(1.0, wear_level * 0.82), 6)},
    ]
    if wear_story in {"battle_worn", "ancient", "salvaged", "field_used"}:
        layers.append({"kind": "dirt_grime", "intensity": round(min(1.0, wear_level * 0.70), 6)})
    if wear_story in {"battle_worn", "salvaged"}:
        layers.append({"kind": "paint_chips", "intensity": round(min(1.0, wear_level * 0.64), 6)})
    if wear_story == "ancient":
        layers.append({"kind": "patina", "intensity": round(min(1.0, wear_level * 0.72), 6)})
    return layers
