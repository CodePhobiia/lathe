"""Material authoring helpers.

Resolves material references, applies default PBR parameters and
feeds the surface stage and packaging.
"""

from __future__ import annotations

from typing import Any


def palette_for_material(name: str) -> dict[str, Any]:
    """Palette for material.

    Args:
        name: name argument.

    Returns:
        The result.
    """
    lname = name.lower()
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
            "roughness_range": list(values.get("roughness_range", palette_for_material(name)["roughness_range"])),
            "emissive": list(values.get("emissive", palette_for_material(name)["emissive"])),
            "surface_profile": str(values.get("surface_profile", palette_for_material(name)["surface_profile"])),
            "wear": float(values.get("wear", palette_for_material(name)["wear"])),
            "normal_intensity": float(values.get("normal_intensity", palette_for_material(name)["normal_intensity"])),
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
    surface = asset.get("surface", {})
    materials = list(surface.get("materials", [])) or list(asset.get("intent", {}).get("materials", []))
    palette = surface.get("resolved_palette", {})
    palette_materials = list(palette.get("values", {}).get("materials", []) or palette.get("values", {}).get("slots", []))
    if palette_materials:
        materials = list(dict.fromkeys([*materials, *palette_materials]))
    surface_program = surface.get("resolved_surface_program", {})
    zone_overrides = dict(surface.get("zones", {}) or surface_program.get("values", {}).get("zones", {}) or {})
    primary = materials[0] if materials else "default_body"
    secondary = materials[1] if len(materials) > 1 else primary
    tertiary = materials[2] if len(materials) > 2 else secondary
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
        if part not in zone_overrides:
            for key, value in zone_overrides.items():
                key_text = str(key).lower()
                if key_text and key_text in lname:
                    material_name = str(value)
                    break
        if part not in component_materials and any(token in lname for token in ("handle", "hinge", "lock", "frame", "bracket", "rotor")):
            material_name = secondary
        elif part not in component_materials and any(token in lname for token in ("glass", "screen", "socket", "lining")):
            material_name = tertiary
        payload = _custom_material(asset, material_name) or palette_for_material(material_name)
        zones.append(
            {
                "part": part,
                "material": material_name,
                **payload,
            }
        )
    return zones
