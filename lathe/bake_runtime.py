from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree


def _uv_image_size(resolution: Any) -> int:
    if isinstance(resolution, dict) and resolution.get("type") == "unit":
        return int(resolution.get("value", 2048))
    if isinstance(resolution, (int, float)):
        return int(resolution)
    return 2048


def _face_uv_polygons(mesh: trimesh.Trimesh, size: int) -> list[list[tuple[float, float]]]:
    uv = getattr(mesh.visual, "uv", None)
    if uv is None:
        return []
    polygons = []
    for face in mesh.faces:
        pts = []
        for vertex_index in face:
            u, v = uv[vertex_index]
            pts.append((u * (size - 1), (1.0 - v) * (size - 1)))
        polygons.append(pts)
    return polygons


def _material_color_lookup(material_zones: list[dict[str, Any]]) -> dict[str, tuple[int, int, int]]:
    return {entry["part"]: tuple(int(value) for value in entry["basecolor"]) for entry in material_zones}


def _hash_seed(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") / float(2**32 - 1)


def _coord_grid(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.indices((size, size), dtype=np.float64)
    return xx / max(1, size - 1), yy / max(1, size - 1)


def _renormalize_tangent_normal_array(normal: np.ndarray) -> np.ndarray:
    out = np.asarray(normal, dtype=np.float64).copy()
    if out.ndim != 3 or out.shape[-1] < 3:
        return out
    nx = (out[..., 0] / 255.0) * 2.0 - 1.0
    ny = (out[..., 1] / 255.0) * 2.0 - 1.0
    radial = nx * nx + ny * ny
    radial_limit = 0.95
    scale = np.ones_like(radial, dtype=np.float64)
    saturated = radial > radial_limit
    scale[saturated] = np.sqrt(radial_limit / np.maximum(radial[saturated], 1e-8))
    nx = nx * scale
    ny = ny * scale
    radial = np.clip(nx * nx + ny * ny, 0.0, radial_limit)
    nz = np.sqrt(np.clip(1.0 - radial, 0.0, 1.0))
    out[..., 0] = np.clip((nx * 0.5 + 0.5) * 255.0, 0.0, 255.0)
    out[..., 1] = np.clip((ny * 0.5 + 0.5) * 255.0, 0.0, 255.0)
    out[..., 2] = np.clip((nz * 0.5 + 0.5) * 255.0, 0.0, 255.0)
    return np.clip(out, 0.0, 255.0)


def renormalize_tangent_normal_map(image: Image.Image) -> Image.Image:
    normal = np.asarray(image.convert("RGB"), dtype=np.float64)
    normal = _renormalize_tangent_normal_array(normal)
    return Image.fromarray(normal.astype(np.uint8), mode="RGB")


def _noise_field(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    field = (
        np.sin((x * (7.0 + seed * 5.0) + y * 1.8 + seed * 3.7) * np.pi * 2.0)
        + np.cos((y * (9.0 + seed * 4.0) - x * 1.2 + seed * 5.1) * np.pi * 2.0)
        + np.sin(((x + y) * (4.0 + seed * 3.0) + seed * 1.7) * np.pi * 2.0)
    )
    return np.clip(0.5 + field / 6.0, 0.0, 1.0)


def _wood_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    grain = np.sin((x * (20.0 + seed * 8.0) + y * (1.5 + seed)) * np.pi * 2.0)
    streaks = np.sin((x * (58.0 + seed * 12.0) + y * 2.0) * np.pi * 2.0)
    return np.clip(0.5 + grain * 0.28 + streaks * 0.10 + (_noise_field(size, seed) - 0.5) * 0.22, 0.0, 1.0)


def _metal_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    brushed = np.sin((y * (34.0 + seed * 10.0) + seed * 6.1) * np.pi * 2.0)
    brushed += np.sin((y * (87.0 + seed * 18.0) + x * 2.0) * np.pi * 2.0) * 0.35
    return np.clip(0.5 + brushed * 0.20 + (_noise_field(size, seed) - 0.5) * 0.14, 0.0, 1.0)


def _paint_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    panel = np.sin((x * (5.5 + seed * 2.0) + y * (5.0 + seed * 1.3)) * np.pi * 2.0)
    return np.clip(0.5 + panel * 0.14 + (_noise_field(size, seed) - 0.5) * 0.18, 0.0, 1.0)


def _fabric_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    weave = np.sin((x * (48.0 + seed * 6.0)) * np.pi * 2.0) * np.sin((y * (48.0 + seed * 5.0)) * np.pi * 2.0)
    return np.clip(0.5 + weave * 0.12 + (_noise_field(size, seed) - 0.5) * 0.08, 0.0, 1.0)


def _glass_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    scanlines = np.sin((y * (64.0 + seed * 10.0) + seed * 2.0) * np.pi * 2.0)
    glow = np.exp(-((x - 0.52) ** 2 + (y - 0.46) ** 2) / 0.08)
    return np.clip(0.46 + scanlines * 0.08 + glow * 0.22 + (_noise_field(size, seed) - 0.5) * 0.04, 0.0, 1.0)


def _water_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    ripples = np.sin((x * (18.0 + seed * 4.0) + y * 3.2 + seed * 5.0) * np.pi * 2.0)
    cross = np.sin((y * (22.0 + seed * 6.0) - x * 2.4 + seed * 2.1) * np.pi * 2.0)
    return np.clip(0.52 + ripples * 0.18 + cross * 0.10 + (_noise_field(size, seed) - 0.5) * 0.10, 0.0, 1.0)


def _sand_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    dunes = np.sin((x * (10.0 + seed * 3.0) + y * (2.2 + seed)) * np.pi * 2.0)
    fine = np.sin((x * 82.0 + y * 17.0 + seed * 9.0) * np.pi * 2.0)
    return np.clip(0.55 + dunes * 0.16 + fine * 0.06 + (_noise_field(size, seed) - 0.5) * 0.16, 0.0, 1.0)


def _vegetation_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    tuft = np.sin((x * (38.0 + seed * 6.0) + seed) * np.pi * 2.0) * np.sin((y * (21.0 + seed * 4.0)) * np.pi * 2.0)
    blotch = _noise_field(size, seed + 0.19)
    return np.clip(0.46 + tuft * 0.10 + (blotch - 0.5) * 0.38, 0.0, 1.0)


def _snow_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    drift = np.sin((x * (5.0 + seed * 2.0) + y * (8.0 + seed * 2.5)) * np.pi * 2.0)
    sparkle = np.sin((x * 96.0 - y * 61.0 + seed * 13.0) * np.pi * 2.0)
    return np.clip(0.68 + drift * 0.12 + sparkle * 0.035 + (_noise_field(size, seed) - 0.5) * 0.08, 0.0, 1.0)


def _cracked_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    strata = np.sin((y * (14.0 + seed * 5.0) + x * 1.6 + seed * 3.1) * np.pi * 2.0)
    cracks = np.abs(np.sin((x * (17.0 + seed * 7.0) - y * 11.0 + seed * 5.2) * np.pi * 2.0))
    cracks = np.where(cracks > 0.93, 0.0, 1.0)
    return np.clip(0.50 + strata * 0.16 + (_noise_field(size, seed) - 0.5) * 0.18 - (1.0 - cracks) * 0.44, 0.0, 1.0)


def _mud_pattern(size: int, seed: float) -> np.ndarray:
    x, y = _coord_grid(size)
    clumps = _noise_field(size, seed + 0.41)
    channels = np.sin((x * (13.0 + seed * 4.0) + y * (9.0 + seed * 3.0)) * np.pi * 2.0)
    return np.clip(0.42 + (clumps - 0.5) * 0.42 + channels * 0.08, 0.0, 1.0)


def _profile_pattern(profile: str, size: int, seed: float) -> np.ndarray:
    if profile == "wood_grain":
        return _wood_pattern(size, seed)
    if profile in {"brushed_metal", "worn_brass"}:
        return _metal_pattern(size, seed)
    if profile in {"fabric_lining", "woven_fabric"}:
        return _fabric_pattern(size, seed)
    if profile == "screen_glass":
        return _glass_pattern(size, seed)
    if profile in {"water_ripple", "foam_wash"}:
        return _water_pattern(size, seed)
    if profile in {"sand_ripple", "wind_streaks"}:
        return _sand_pattern(size, seed)
    if profile in {"grass_mottle", "leaf_litter"}:
        return _vegetation_pattern(size, seed)
    if profile in {"snow_drift", "ice_scratch"}:
        return _snow_pattern(size, seed)
    if profile in {"cracked_stone", "stratified_stone", "basalt_crack", "lava_crack", "rock_scree"}:
        return _cracked_pattern(size, seed)
    if profile in {"mud_silt", "concrete_mottle"}:
        return _mud_pattern(size, seed)
    if profile in {"painted_panel", "neutral_panel", "carbon_rubber", "emissive_panel"}:
        return _paint_pattern(size, seed)
    return _noise_field(size, seed)


def _material_layer_color(name: str, fallback: np.ndarray) -> np.ndarray:
    lname = name.lower()
    if "water" in lname:
        return np.asarray([48.0, 116.0, 146.0], dtype=np.float64)
    if "foam" in lname:
        return np.asarray([218.0, 232.0, 224.0], dtype=np.float64)
    if "salt" in lname:
        return np.asarray([202.0, 208.0, 198.0], dtype=np.float64)
    if "sand" in lname:
        return np.asarray([174.0, 145.0, 92.0], dtype=np.float64)
    if "mud" in lname or "silt" in lname or "soil" in lname or "dust" in lname or "grime" in lname:
        if "grime" in lname:
            return np.asarray([56.0, 56.0, 50.0], dtype=np.float64)
        return np.asarray([84.0, 62.0, 40.0], dtype=np.float64)
    if "grass" in lname or "moss" in lname or "algae" in lname or "lichen" in lname:
        return np.asarray([70.0, 112.0, 64.0], dtype=np.float64)
    if "leaf" in lname or "bark" in lname:
        return np.asarray([124.0, 84.0, 38.0], dtype=np.float64)
    if "fungus" in lname or "mushroom" in lname:
        return np.asarray([154.0, 128.0, 98.0], dtype=np.float64)
    if "flower" in lname or "petal" in lname or "blossom" in lname:
        return np.asarray([186.0, 92.0, 132.0], dtype=np.float64)
    if "terracotta" in lname or "planter" in lname:
        return np.asarray([146.0, 76.0, 48.0], dtype=np.float64)
    if "canvas" in lname or "cloth" in lname or "rope" in lname or "upholstery" in lname:
        return np.asarray([126.0, 118.0, 92.0], dtype=np.float64)
    if "laminate" in lname:
        return np.asarray([154.0, 150.0, 136.0], dtype=np.float64)
    if "snow" in lname or "frost" in lname:
        return np.asarray([220.0, 226.0, 228.0], dtype=np.float64)
    if "ice" in lname:
        return np.asarray([174.0, 214.0, 228.0], dtype=np.float64)
    if "lava" in lname:
        return np.asarray([220.0, 74.0, 18.0], dtype=np.float64)
    if "basalt" in lname or "stone" in lname or "rock" in lname:
        return np.asarray([104.0, 104.0, 98.0], dtype=np.float64)
    if "hazard" in lname or "warning" in lname:
        return np.asarray([216.0, 164.0, 42.0], dtype=np.float64)
    if "cast_iron" in lname or "iron" in lname:
        return np.asarray([58.0, 62.0, 64.0], dtype=np.float64)
    if "galvanized" in lname:
        return np.asarray([132.0, 140.0, 140.0], dtype=np.float64)
    if "safety_grate" in lname or "grate" in lname:
        return np.asarray([118.0, 126.0, 124.0], dtype=np.float64)
    if "gasket" in lname or "insulation" in lname:
        return np.asarray([34.0, 40.0, 46.0], dtype=np.float64)
    if "rubber_tread" in lname or "tread" in lname:
        return np.asarray([34.0, 36.0, 36.0], dtype=np.float64)
    if "paint" in lname:
        return np.asarray([88.0, 102.0, 120.0], dtype=np.float64)
    if "brass" in lname or "gold" in lname:
        return np.asarray([190.0, 150.0, 72.0], dtype=np.float64)
    if "copper" in lname:
        return np.asarray([176.0, 92.0, 52.0], dtype=np.float64)
    if "metal" in lname or "steel" in lname or "aluminum" in lname:
        return np.asarray([138.0, 144.0, 148.0], dtype=np.float64)
    if "rubber" in lname or "carbon" in lname:
        return np.asarray([38.0, 42.0, 46.0], dtype=np.float64)
    if "plastic" in lname:
        return np.asarray([72.0, 82.0, 92.0], dtype=np.float64)
    if "glass" in lname or "screen" in lname:
        return np.asarray([76.0, 124.0, 196.0], dtype=np.float64)
    if "wood" in lname or "oak" in lname:
        return np.asarray([118.0, 72.0, 42.0], dtype=np.float64)
    return fallback


def _wear_layer_intensity(zone: dict[str, Any], kind: str) -> float:
    for layer in zone.get("wear_layers", []) or []:
        if isinstance(layer, dict) and str(layer.get("kind", "")) == kind:
            return float(layer.get("intensity", 0.0))
    return 0.0


def _hint_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _zone_material_hint_tokens(zone: dict[str, Any]) -> set[str]:
    tokens = {_hint_token(item) for item in zone.get("material_hints", []) or [] if _hint_token(item)}
    for record in zone.get("topology_material_zones", []) or []:
        if not isinstance(record, dict):
            continue
        for key in (
            "material_hint",
            "damage_kind",
            "feature_kind",
            "treatment_kind",
            "semantic_role",
        ):
            token = _hint_token(record.get(key))
            if token:
                tokens.add(token)
    return tokens


def _zone_kernel_wear_bias(zone: dict[str, Any]) -> dict[str, float]:
    tokens = _zone_material_hint_tokens(zone)
    bias = {
        "edge_wear": 0.0,
        "micro_scratches": 0.0,
        "dirt_grime": 0.0,
        "paint_chips": 0.0,
        "dents": 0.0,
    }
    if tokens & {"bevel", "chamfer", "edge_treatment"}:
        bias["edge_wear"] = max(bias["edge_wear"], 0.22)
    if tokens & {"trim_band", "panel_frame", "vent_slats", "ribs", "ribbed_panel", "visible_feature_detail"}:
        bias["edge_wear"] = max(bias["edge_wear"], 0.16)
        bias["micro_scratches"] = max(bias["micro_scratches"], 0.08)
    if tokens & {"gear", "threaded_cylinder", "thread", "spring", "curved_tube", "curve_sweep"}:
        bias["edge_wear"] = max(bias["edge_wear"], 0.20)
        bias["micro_scratches"] = max(bias["micro_scratches"], 0.12)
    if tokens & {"wear_scratch", "scratch", "scratch_mask", "micro_scratch", "micro_scratches"}:
        bias["micro_scratches"] = max(bias["micro_scratches"], 0.58)
    if tokens & {"wear_grime", "grime", "grime_mask", "dirt", "dirt_grime"}:
        bias["dirt_grime"] = max(bias["dirt_grime"], 0.54)
    if tokens & {"wear_edge_chip", "edge_chip", "wear_chip", "chip", "paint_chip", "paint_chips"}:
        bias["paint_chips"] = max(bias["paint_chips"], 0.50)
        bias["edge_wear"] = max(bias["edge_wear"], 0.34)
    if tokens & {"wear_dent", "dent", "dent_mask", "dents"}:
        bias["dents"] = max(bias["dents"], 0.46)
        bias["edge_wear"] = max(bias["edge_wear"], 0.24)
        bias["micro_scratches"] = max(bias["micro_scratches"], 0.16)
        bias["paint_chips"] = max(bias["paint_chips"], 0.18)
    return bias


def _surface_material_masks(
    zone: dict[str, Any],
    *,
    size: int,
    seed: float,
    curvature: np.ndarray,
    ao: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    layers = [str(item) for item in zone.get("procedural_layers", []) or [] if str(item)]
    if not layers:
        zero = np.zeros((size, size), dtype=np.float64)
        return zero, zero

    x, y = _coord_grid(size)
    noise = _noise_field(size, seed + 0.173)
    role = str(zone.get("material_layer_role", "base"))
    layer_count = len(layers)
    underlayer_strength = 0.18 if layer_count >= 2 else 0.0
    if role == "secondary":
        underlayer_strength += 0.10
    elif role == "accent":
        underlayer_strength += 0.06
    wear = float(zone.get("wear", 0.0))
    chip_bias = np.clip((curvature - 0.46) * (1.40 + wear) + (noise - 0.58) * 1.25, 0.0, 1.0)
    underlayer_mask = np.clip(chip_bias * (underlayer_strength + wear * 0.36), 0.0, 1.0)

    if layer_count < 3:
        return underlayer_mask, np.zeros((size, size), dtype=np.float64)

    stripe_phase = seed * 3.1
    stripe_width = 0.36 if any("hazard" in item.lower() or "warning" in item.lower() for item in layers) else 0.18
    stripe_wave = np.sin((x * (7.0 + seed * 1.7) + y * (2.4 + seed) + stripe_phase) * np.pi * 2.0)
    edge_band = np.clip((curvature - 0.42) * 2.4 + (0.76 - ao) * 0.72, 0.0, 1.0)
    accent_mask = np.where(stripe_wave > 1.0 - stripe_width, 1.0, 0.0)
    accent_mask = np.clip(accent_mask * (0.40 + edge_band * 0.45), 0.0, 1.0)
    return underlayer_mask, accent_mask


def _surface_wear_masks(
    zone: dict[str, Any],
    *,
    size: int,
    seed: float,
    curvature: np.ndarray,
    ao: np.ndarray,
) -> dict[str, np.ndarray]:
    x, y = _coord_grid(size)
    noise = _noise_field(size, seed + 0.391)
    wear = float(zone.get("wear", 0.0))
    kernel_bias = _zone_kernel_wear_bias(zone)
    edge_intensity = max(wear, _wear_layer_intensity(zone, "edge_wear"), kernel_bias["edge_wear"])
    scratch_intensity = max(
        wear * 0.52,
        _wear_layer_intensity(zone, "micro_scratches"),
        kernel_bias["micro_scratches"],
    )
    grime_intensity = max(_wear_layer_intensity(zone, "dirt_grime"), kernel_bias["dirt_grime"])
    chip_intensity = max(_wear_layer_intensity(zone, "paint_chips"), kernel_bias["paint_chips"])
    patina_intensity = _wear_layer_intensity(zone, "patina")
    dent_intensity = kernel_bias["dents"]

    scratch_wave = np.sin((x * (96.0 + seed * 21.0) + y * (8.0 + seed * 3.0)) * np.pi * 2.0)
    scratch_mask = np.clip((np.abs(scratch_wave) - 0.90) * 9.0, 0.0, 1.0) * scratch_intensity
    edge_mask = np.clip((curvature - 0.44) * 2.7 + (noise - 0.62) * 0.55, 0.0, 1.0) * edge_intensity
    grime_mask = np.clip((0.78 - ao) * 1.25 + (noise - 0.55) * 0.42, 0.0, 1.0) * grime_intensity
    chip_mask = np.clip((noise - 0.61) * 2.0 + edge_mask * 0.90, 0.0, 1.0) * chip_intensity
    patina_mask = np.clip((noise - 0.47) * 1.2 + (1.0 - curvature) * 0.25, 0.0, 1.0) * patina_intensity
    dent_wave = np.sin((x * (9.0 + seed * 3.0) - y * (11.0 + seed * 2.0) + seed * 4.0) * np.pi * 2.0)
    dent_mask = np.clip((0.82 - np.abs(dent_wave)) * 1.45 + (0.58 - curvature) * 0.34, 0.0, 1.0)
    dent_mask *= dent_intensity

    return {
        "edge_wear": edge_mask,
        "micro_scratches": scratch_mask,
        "dirt_grime": grime_mask,
        "paint_chips": chip_mask,
        "patina": patina_mask,
        "dents": dent_mask,
    }


def _color_mask(image: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    return np.all(image == np.asarray(color, dtype=np.uint8), axis=-1)


def _primary_padding_zone(material_zones: list[dict[str, Any]]) -> dict[str, Any]:
    for zone in material_zones:
        if str(zone.get("part", "")).lower() == "body":
            return zone
    return (
        material_zones[0]
        if material_zones
        else {
            "part": "atlas_padding",
            "material": "neutral_panel",
            "basecolor": [118, 118, 118],
            "roughness": 0.58,
            "roughness_range": [0.48, 0.68],
            "emissive": [0, 0, 0],
            "surface_profile": "neutral_panel",
        }
    )


def pad_low_coverage_atlas_maps(
    *,
    id_map: Image.Image,
    material_zones: list[dict[str, Any]],
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    ao: Image.Image,
    curvature: Image.Image,
    emissive: Image.Image,
    minimum_coverage: float = 0.50,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image, Image.Image, Image.Image]:
    """Author deterministic padding pixels for sparse atlases."""
    id_source = np.asarray(id_map.convert("RGB"), dtype=np.uint8)
    background = np.all(id_source == np.asarray((8, 8, 8), dtype=np.uint8), axis=-1)
    coverage = 1.0 - float(np.mean(background))
    if coverage >= minimum_coverage or not np.any(background):
        return basecolor, normal, roughness, ao, curvature, emissive

    zone = _primary_padding_zone(material_zones)
    size = id_source.shape[0]
    seed = _hash_seed(f"atlas_padding:{zone.get('part', '')}:{zone.get('material', '')}")
    pattern = _profile_pattern(str(zone.get("surface_profile", "neutral_panel")), size, seed)
    x, y = _coord_grid(size)
    fine = np.clip(
        0.5
        + np.sin((x * (72.0 + seed * 18.0) + seed) * np.pi * 2.0) * 0.22
        + np.cos((y * (64.0 + seed * 21.0) - seed) * np.pi * 2.0) * 0.18
        + (pattern - 0.5) * 0.45,
        0.0,
        1.0,
    )

    base = np.asarray(basecolor.convert("RGB"), dtype=np.float64)
    base_value = np.asarray(zone.get("basecolor", [118, 118, 118]), dtype=np.float64)
    tint = np.asarray([22.0, 18.0, 14.0], dtype=np.float64)
    base_fill = base_value + (fine[..., None] - 0.5) * 116.0 + (pattern[..., None] - 0.5) * tint
    base[background] = np.clip(base_fill[background], 0.0, 255.0)

    normal_arr = np.asarray(normal.convert("RGB"), dtype=np.float64)
    x_detail = (fine - 0.5) * 176.0
    y_detail = np.sin((y * (88.0 + seed * 11.0) + x * 9.0) * np.pi * 2.0) * 78.0 + (pattern - 0.5) * 62.0
    normal_arr[..., 0][background] = np.clip(128.0 + x_detail[background], 0.0, 255.0)
    normal_arr[..., 1][background] = np.clip(128.0 + y_detail[background], 0.0, 255.0)
    normal_arr = _renormalize_tangent_normal_array(normal_arr)

    rough = np.asarray(roughness.convert("L"), dtype=np.float64)
    roughness_min, roughness_max = zone.get(
        "roughness_range",
        [zone.get("roughness", 0.5), zone.get("roughness", 0.5)],
    )
    rough_fill = (float(roughness_min) + (float(roughness_max) - float(roughness_min)) * fine) * 255.0
    rough[background] = np.clip(rough_fill[background], 0.0, 255.0)

    ao_arr = np.asarray(ao.convert("L"), dtype=np.float64)
    ao_fill = 160.0 + (fine - 0.5) * 112.0
    ao_arr[background] = np.clip(ao_fill[background], 36.0, 255.0)

    curvature_arr = np.asarray(curvature.convert("L"), dtype=np.float64)
    curvature_fill = 96.0 + np.abs(fine - 0.5) * 220.0
    curvature_arr[background] = np.clip(curvature_fill[background], 0.0, 255.0)

    emissive_arr = np.asarray(emissive.convert("RGB"), dtype=np.float64)
    if any(max(zone_entry.get("emissive", [0, 0, 0])) > 0 for zone_entry in material_zones):
        glow = np.asarray([10.0, 28.0, 54.0], dtype=np.float64) * np.clip(fine[..., None] - 0.62, 0.0, 1.0)
        emissive_arr[background] = np.clip(glow[background], 0.0, 255.0)

    return (
        Image.fromarray(base.astype(np.uint8), mode="RGB"),
        Image.fromarray(normal_arr.astype(np.uint8), mode="RGB"),
        Image.fromarray(rough.astype(np.uint8), mode="L"),
        Image.fromarray(ao_arr.astype(np.uint8), mode="L"),
        Image.fromarray(curvature_arr.astype(np.uint8), mode="L"),
        Image.fromarray(emissive_arr.astype(np.uint8), mode="RGB"),
    )


def bake_id_map(
    mesh: trimesh.Trimesh, face_parts: list[str], material_zones: list[dict[str, Any]], size: int
) -> Image.Image:
    image = Image.new("RGB", (size, size), (8, 8, 8))
    draw = ImageDraw.Draw(image, "RGB")
    colors = _material_color_lookup(material_zones)
    polygons = _face_uv_polygons(mesh, size)
    for face_index, polygon in enumerate(polygons):
        part = face_parts[min(face_index, len(face_parts) - 1)] if face_parts else "mesh"
        draw.polygon(polygon, fill=colors.get(part, (128, 128, 128)))
    return image


def bake_basecolor_map(
    id_map: Image.Image, material_zones: list[dict[str, Any]], curvature_map: Image.Image, ao_map: Image.Image
) -> Image.Image:
    source = np.asarray(id_map, dtype=np.uint8)
    out = source.astype(np.float64).copy()
    curvature = np.asarray(curvature_map.convert("L"), dtype=np.float64) / 255.0
    ao = np.asarray(ao_map.convert("L"), dtype=np.float64) / 255.0
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(source, color)
        if not np.any(mask):
            continue
        seed = _hash_seed(f"{zone['part']}:{zone['material']}")
        pattern = _profile_pattern(str(zone.get("surface_profile", "neutral_panel")), source.shape[0], seed)
        wear = float(zone.get("wear", 0.0))
        pattern_strength = 0.24 + 0.30 * wear
        base = np.asarray(zone["basecolor"], dtype=np.float64)
        variation = (pattern - 0.5) * 255.0 * pattern_strength
        edge_wear = np.clip((curvature - 0.50) * (0.72 + wear), 0.0, 0.48)
        cavity_darkening = np.clip((0.74 - ao) * 0.44, 0.0, 0.30)
        values = np.tile(base, (source.shape[0], source.shape[1], 1))
        values += variation[..., None]
        values += edge_wear[..., None] * np.asarray([46.0, 42.0, 38.0], dtype=np.float64)
        values -= cavity_darkening[..., None] * np.asarray([38.0, 34.0, 28.0], dtype=np.float64)

        layer_mask, accent_mask = _surface_material_masks(
            zone,
            size=source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        layers = [str(item) for item in zone.get("procedural_layers", []) or [] if str(item)]
        if len(layers) >= 2:
            underlayer_color = _material_layer_color(layers[1], base)
            values = values * (1.0 - layer_mask[..., None] * 0.84) + underlayer_color * (
                layer_mask[..., None] * 0.84
            )
        if len(layers) >= 3:
            accent_color = _material_layer_color(layers[2], base)
            values = values * (1.0 - accent_mask[..., None] * 0.72) + accent_color * (
                accent_mask[..., None] * 0.72
            )

        wear_masks = _surface_wear_masks(
            zone,
            size=source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        chip_color = (
            _material_layer_color(layers[1], base)
            if len(layers) >= 2
            else np.asarray([150.0, 150.0, 145.0], dtype=np.float64)
        )
        values = values * (1.0 - wear_masks["paint_chips"][..., None] * 0.88) + chip_color * (
            wear_masks["paint_chips"][..., None] * 0.88
        )
        values += wear_masks["micro_scratches"][..., None] * np.asarray(
            [42.0, 39.0, 35.0], dtype=np.float64
        )
        values -= wear_masks["dirt_grime"][..., None] * np.asarray([82.0, 72.0, 58.0], dtype=np.float64)
        values -= wear_masks["dents"][..., None] * np.asarray([46.0, 40.0, 34.0], dtype=np.float64)
        values += wear_masks["edge_wear"][..., None] * np.asarray([38.0, 34.0, 30.0], dtype=np.float64)
        values = values * (1.0 - wear_masks["patina"][..., None] * 0.54) + np.asarray(
            [72.0, 128.0, 106.0], dtype=np.float64
        ) * (wear_masks["patina"][..., None] * 0.54)
        out[mask] = np.clip(values[mask], 0.0, 255.0)
    return Image.fromarray(out.astype(np.uint8), mode="RGB")


def bake_normal_map(mesh: trimesh.Trimesh, size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), (128, 128, 255))
    draw = ImageDraw.Draw(image, "RGB")
    polygons = _face_uv_polygons(mesh, size)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    tangents, bitangents, frame_normals = _low_face_tangent_frames(mesh)
    for face_index, polygon in enumerate(polygons):
        if len(tangents) == len(polygons):
            rgb = _normal_to_tangent_rgb(
                normals[face_index],
                tangents[face_index],
                bitangents[face_index],
                frame_normals[face_index],
            )
        else:
            # No UV tangent basis is available; keep the fallback honest as
            # neutral tangent-space instead of baking world-space normals.
            rgb = (128, 128, 255)
        draw.polygon(polygon, fill=rgb)
    return image


def _face_curvature_values(mesh: trimesh.Trimesh) -> np.ndarray:
    adjacency = mesh.face_adjacency
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    curvature = np.zeros(len(mesh.faces), dtype=np.float64)
    if len(adjacency) > 0:
        for left, right in adjacency:
            dot = float(np.clip(np.dot(normals[left], normals[right]), -1.0, 1.0))
            angle = np.arccos(dot)
            curvature[left] = max(curvature[left], angle)
            curvature[right] = max(curvature[right], angle)
    return curvature


def _nearest_high_faces(
    low_mesh: trimesh.Trimesh,
    high_mesh: trimesh.Trimesh,
    *,
    bake_cage_offset_cm: float = 0.0,
) -> np.ndarray:
    if len(low_mesh.faces) == 0 or len(high_mesh.faces) == 0:
        return np.zeros(len(low_mesh.faces), dtype=np.int64)
    high_centroids = np.asarray(high_mesh.triangles_center, dtype=np.float64)
    low_centroids = np.asarray(low_mesh.triangles_center, dtype=np.float64)
    offset = max(0.0, float(bake_cage_offset_cm or 0.0))
    if offset > 0.0:
        low_normals = np.asarray(low_mesh.face_normals, dtype=np.float64)
        if len(low_normals) == len(low_centroids):
            low_centroids = low_centroids + low_normals * offset
    _, indices = cKDTree(high_centroids).query(low_centroids)
    return np.asarray(indices, dtype=np.int64)


def _ray_projected_high_faces(
    low_mesh: trimesh.Trimesh,
    high_mesh: trimesh.Trimesh,
    *,
    bake_cage_offset_cm: float = 0.0,
    max_ray_distance_cm: float | None = None,
    bidirectional: bool = False,
    projection_stats: dict[str, Any] | None = None,
) -> np.ndarray:
    def record_stats(
        *,
        ray_backend_available: bool,
        ray_hit_count: int,
        fallback_count: int,
        rejected_distance_count: int = 0,
    ) -> None:
        if projection_stats is None:
            return
        projection_stats.update(
            {
                "source": "ray_cage_high_to_low_projection_v1",
                "face_count": len(low_mesh.faces),
                "ray_backend_available": ray_backend_available,
                "ray_hit_count": ray_hit_count,
                "fallback_count": fallback_count,
                "rejected_distance_count": rejected_distance_count,
                "bake_cage_offset_cm": max(0.0, float(bake_cage_offset_cm or 0.0)),
                "max_ray_distance_cm": None
                if max_ray_distance_cm is None
                else max(0.0, float(max_ray_distance_cm)),
                "bidirectional": bool(bidirectional),
            }
        )

    if len(low_mesh.faces) == 0 or len(high_mesh.faces) == 0:
        record_stats(ray_backend_available=False, ray_hit_count=0, fallback_count=len(low_mesh.faces))
        return np.zeros(len(low_mesh.faces), dtype=np.int64)
    low_centroids = np.asarray(low_mesh.triangles_center, dtype=np.float64)
    low_normals = np.asarray(low_mesh.face_normals, dtype=np.float64)
    if len(low_centroids) != len(low_normals):
        record_stats(ray_backend_available=False, ray_hit_count=0, fallback_count=len(low_mesh.faces))
        return _nearest_high_faces(
            low_mesh,
            high_mesh,
            bake_cage_offset_cm=bake_cage_offset_cm,
        )
    offset = max(0.0, float(bake_cage_offset_cm or 0.0))
    origins = low_centroids + low_normals * offset
    directions = -low_normals
    ray_source_indices = np.arange(len(low_mesh.faces), dtype=np.int64)
    if bidirectional:
        origins = np.vstack([origins, low_centroids - low_normals * offset])
        directions = np.vstack([directions, low_normals])
        ray_source_indices = np.concatenate([ray_source_indices, ray_source_indices])
    ray_faces = np.full(len(low_mesh.faces), -1, dtype=np.int64)
    max_distance = None if max_ray_distance_cm is None else max(0.0, float(max_ray_distance_cm))
    try:
        locations, ray_indices, triangle_indices = high_mesh.ray.intersects_location(
            origins,
            directions,
            multiple_hits=False,
        )
    except (ImportError, ModuleNotFoundError, ValueError, RuntimeError, AttributeError, IndexError):
        record_stats(ray_backend_available=False, ray_hit_count=0, fallback_count=len(low_mesh.faces))
        return _nearest_high_faces(
            low_mesh,
            high_mesh,
            bake_cage_offset_cm=bake_cage_offset_cm,
        )
    rejected_distance_count = 0
    if len(ray_indices) > 0:
        origin_points = origins[np.asarray(ray_indices, dtype=np.int64)]
        hit_distances = np.linalg.norm(np.asarray(locations, dtype=np.float64) - origin_points, axis=1)
        best_distance = np.full(len(low_mesh.faces), np.inf, dtype=np.float64)
        for ray_index, triangle_index, distance in zip(ray_indices, triangle_indices, hit_distances, strict=False):
            low_face_index = int(ray_source_indices[int(ray_index)])
            distance = float(distance)
            if max_distance is not None and distance > max_distance:
                rejected_distance_count += 1
                continue
            if distance < best_distance[low_face_index]:
                best_distance[low_face_index] = distance
                ray_faces[low_face_index] = int(triangle_index)
    missing = ray_faces < 0
    if np.any(missing):
        nearest = _nearest_high_faces(
            low_mesh,
            high_mesh,
            bake_cage_offset_cm=bake_cage_offset_cm,
        )
        ray_faces[missing] = nearest[missing]
    record_stats(
        ray_backend_available=True,
        ray_hit_count=int(np.count_nonzero(~missing)),
        fallback_count=int(np.count_nonzero(missing)),
        rejected_distance_count=rejected_distance_count,
    )
    return ray_faces


def _low_face_tangent_frames(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    uv = getattr(mesh.visual, "uv", None)
    if uv is None or len(mesh.faces) == 0:
        empty = np.zeros((0, 3), dtype=np.float64)
        return empty, empty, empty
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    tangents = np.zeros((len(faces), 3), dtype=np.float64)
    bitangents = np.zeros((len(faces), 3), dtype=np.float64)
    frame_normals = np.zeros((len(faces), 3), dtype=np.float64)
    for face_index, face in enumerate(faces):
        p0, p1, p2 = vertices[face]
        uv0, uv1, uv2 = np.asarray(uv[face], dtype=np.float64)
        dp1 = p1 - p0
        dp2 = p2 - p0
        duv1 = uv1 - uv0
        duv2 = uv2 - uv0
        normal = normals[face_index]
        normal = normal / max(1e-8, float(np.linalg.norm(normal)))
        determinant = float(duv1[0] * duv2[1] - duv2[0] * duv1[1])
        if abs(determinant) > 1e-8:
            inv = 1.0 / determinant
            tangent = (dp1 * duv2[1] - dp2 * duv1[1]) * inv
            bitangent = (-dp1 * duv2[0] + dp2 * duv1[0]) * inv
        else:
            tangent = dp1 if float(np.linalg.norm(dp1)) > 1e-8 else dp2
            tangent = tangent - normal * float(np.dot(normal, tangent))
            bitangent = np.cross(normal, tangent)
        tangent = tangent - normal * float(np.dot(normal, tangent))
        tangent = tangent / max(1e-8, float(np.linalg.norm(tangent)))
        bitangent_hint = bitangent - normal * float(np.dot(normal, bitangent))
        bitangent_hint = bitangent_hint / max(1e-8, float(np.linalg.norm(bitangent_hint)))
        bitangent = np.cross(normal, tangent)
        bitangent = bitangent / max(1e-8, float(np.linalg.norm(bitangent)))
        if float(np.dot(bitangent, bitangent_hint)) < 0.0:
            bitangent = -bitangent
        tangents[face_index] = tangent
        bitangents[face_index] = bitangent
        frame_normals[face_index] = normal
    return tangents, bitangents, frame_normals


def _normal_to_tangent_rgb(
    normal: np.ndarray,
    tangent: np.ndarray,
    bitangent: np.ndarray,
    frame_normal: np.ndarray,
) -> tuple[int, int, int]:
    world = np.asarray(normal, dtype=np.float64)
    world = world / max(1e-8, float(np.linalg.norm(world)))
    tangent_space = np.asarray(
        [
            float(np.dot(world, tangent)),
            float(np.dot(world, bitangent)),
            float(np.dot(world, frame_normal)),
        ],
        dtype=np.float64,
    )
    tangent_space = tangent_space / max(1e-8, float(np.linalg.norm(tangent_space)))
    return tuple(
        int(round(max(0, min(255, (value * 0.5 + 0.5) * 255.0))))
        for value in tangent_space
    )


def bake_highlow_normal_transfer_map(
    low_mesh: trimesh.Trimesh,
    high_mesh: trimesh.Trimesh,
    size: int,
    *,
    bake_cage_offset_cm: float = 0.0,
    max_ray_distance_cm: float | None = None,
    bidirectional: bool = False,
    transfer_stats: dict[str, Any] | None = None,
    transfer_channel: str = "normal",
) -> Image.Image:
    image = Image.new("RGB", (size, size), (128, 128, 255))
    draw = ImageDraw.Draw(image, "RGB")
    polygons = _face_uv_polygons(low_mesh, size)
    if not polygons or len(high_mesh.faces) == 0:
        return bake_normal_map(low_mesh, size)
    tangents, bitangents, frame_normals = _low_face_tangent_frames(low_mesh)
    if len(tangents) != len(polygons):
        return bake_normal_map(low_mesh, size)
    normals = np.asarray(high_mesh.face_normals, dtype=np.float64)
    projection_stats: dict[str, Any] = {}
    high_face_for_low_face = _ray_projected_high_faces(
        low_mesh,
        high_mesh,
        bake_cage_offset_cm=bake_cage_offset_cm,
        max_ray_distance_cm=max_ray_distance_cm,
        bidirectional=bidirectional,
        projection_stats=projection_stats,
    )
    if transfer_stats is not None:
        transfer_stats[transfer_channel] = projection_stats
    for face_index, polygon in enumerate(polygons):
        normal = normals[int(high_face_for_low_face[face_index])]
        rgb = _normal_to_tangent_rgb(
            normal,
            tangents[face_index],
            bitangents[face_index],
            frame_normals[face_index],
        )
        draw.polygon(polygon, fill=rgb)
    return image


def bake_highlow_curvature_transfer_map(
    low_mesh: trimesh.Trimesh,
    high_mesh: trimesh.Trimesh,
    size: int,
    *,
    bake_cage_offset_cm: float = 0.0,
    max_ray_distance_cm: float | None = None,
    bidirectional: bool = False,
    transfer_stats: dict[str, Any] | None = None,
    transfer_channel: str = "curvature",
) -> Image.Image:
    image = Image.new("L", (size, size), 128)
    draw = ImageDraw.Draw(image, "L")
    polygons = _face_uv_polygons(low_mesh, size)
    if not polygons or len(high_mesh.faces) == 0:
        return bake_curvature_map(low_mesh, size)
    high_curvature = _face_curvature_values(high_mesh)
    projection_stats: dict[str, Any] = {}
    high_face_for_low_face = _ray_projected_high_faces(
        low_mesh,
        high_mesh,
        bake_cage_offset_cm=bake_cage_offset_cm,
        max_ray_distance_cm=max_ray_distance_cm,
        bidirectional=bidirectional,
        projection_stats=projection_stats,
    )
    if transfer_stats is not None:
        transfer_stats[transfer_channel] = projection_stats
    for face_index, polygon in enumerate(polygons):
        value = int(max(0, min(255, 64 + high_curvature[int(high_face_for_low_face[face_index])] / np.pi * 191)))
        draw.polygon(polygon, fill=value)
    return image


def enhance_normal_map(
    base_normal: Image.Image,
    id_map: Image.Image,
    material_zones: list[dict[str, Any]],
    curvature_map: Image.Image,
) -> Image.Image:
    source = np.asarray(base_normal, dtype=np.float64)
    out = source.copy()
    id_source = np.asarray(id_map, dtype=np.uint8)
    curvature = np.asarray(curvature_map.convert("L"), dtype=np.float64) / 255.0
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        seed = _hash_seed(zone["part"])
        pattern = _profile_pattern(
            str(zone.get("surface_profile", "neutral_panel")), id_source.shape[0], seed
        )
        intensity = float(zone.get("normal_intensity", 0.05))
        wear = float(zone.get("wear", 0.0))
        detail_gain = 1.3 + min(2.0, intensity * 4.4 + wear * 1.25)
        wear_masks = _surface_wear_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=np.ones_like(curvature),
        )
        layer_mask, accent_mask = _surface_material_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=np.ones_like(curvature),
        )
        x_detail = (pattern - 0.5) * (82.0 * intensity + 16.0) * detail_gain
        y_detail = (
            (curvature - 0.5) + (pattern - 0.5) * 0.65
        ) * (76.0 * intensity + 12.0) * detail_gain
        x_detail += (
            wear_masks["micro_scratches"] - wear_masks["dirt_grime"] * 0.28
        ) * (50.0 + intensity * 168.0) * detail_gain
        y_detail += (
            wear_masks["paint_chips"] * 36.0
            - wear_masks["dents"] * 58.0
            - wear_masks["patina"] * 18.0
            + (layer_mask + accent_mask) * 30.0
        ) * detail_gain
        out[..., 0][mask] = np.clip(source[..., 0][mask] + x_detail[mask], 0.0, 255.0)
        out[..., 1][mask] = np.clip(source[..., 1][mask] + y_detail[mask], 0.0, 255.0)
    out = _renormalize_tangent_normal_array(out)
    return Image.fromarray(out.astype(np.uint8), mode="RGB")


def bake_curvature_map(mesh: trimesh.Trimesh, size: int) -> Image.Image:
    image = Image.new("L", (size, size), 128)
    draw = ImageDraw.Draw(image, "L")
    polygons = _face_uv_polygons(mesh, size)
    curvature = _face_curvature_values(mesh)
    for face_index, polygon in enumerate(polygons):
        value = int(max(0, min(255, 64 + curvature[face_index] / np.pi * 191)))
        draw.polygon(polygon, fill=value)
    return image


def bake_ao_map(mesh: trimesh.Trimesh, size: int) -> Image.Image:
    image = Image.new("L", (size, size), 200)
    draw = ImageDraw.Draw(image, "L")
    polygons = _face_uv_polygons(mesh, size)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    upward_bias = np.asarray(mesh.face_normals[:, 1], dtype=np.float64)
    for face_index, polygon in enumerate(polygons):
        upward = max(0.0, normals[face_index][1])
        value = int(max(36, min(255, 72 + upward * 150 + upward_bias[face_index] * 18)))
        draw.polygon(polygon, fill=value)
    return image


def bake_roughness_map(
    id_map: Image.Image, material_zones: list[dict[str, Any]], curvature_map: Image.Image, ao_map: Image.Image
) -> Image.Image:
    id_source = np.asarray(id_map, dtype=np.uint8)
    curvature = np.asarray(curvature_map.convert("L"), dtype=np.float64) / 255.0
    ao = np.asarray(ao_map.convert("L"), dtype=np.float64) / 255.0
    out = np.full(id_source.shape[:2], 148.0, dtype=np.float64)
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        seed = _hash_seed(f"roughness:{zone['part']}")
        pattern = _profile_pattern(
            str(zone.get("surface_profile", "neutral_panel")), id_source.shape[0], seed
        )
        roughness_min, roughness_max = zone.get(
            "roughness_range", [zone.get("roughness", 0.5), zone.get("roughness", 0.5)]
        )
        values = roughness_min + (roughness_max - roughness_min) * np.clip(pattern * 1.08, 0.0, 1.0)
        wear = float(zone.get("wear", 0.0))
        wear_masks = _surface_wear_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        layer_mask, accent_mask = _surface_material_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        values = np.clip(
            values + (1.0 - ao) * 0.12 - np.clip(curvature - 0.48, 0.0, 0.42) * wear * 0.48, 0.02, 0.98
        )
        values = np.clip(
            values
            - wear_masks["edge_wear"] * 0.20
            + wear_masks["micro_scratches"] * 0.10
            + wear_masks["dirt_grime"] * 0.24
            + wear_masks["paint_chips"] * 0.16
            + wear_masks["patina"] * 0.18
            + wear_masks["dents"] * 0.12
            + layer_mask * 0.08
            - accent_mask * 0.06,
            0.02,
            0.98,
        )
        out[mask] = values[mask] * 255.0
    return Image.fromarray(out.astype(np.uint8), mode="L")


def bake_wear_mask(
    id_map: Image.Image, material_zones: list[dict[str, Any]], curvature_map: Image.Image, ao_map: Image.Image
) -> Image.Image:
    id_source = np.asarray(id_map, dtype=np.uint8)
    curvature = np.asarray(curvature_map.convert("L"), dtype=np.float64) / 255.0
    ao = np.asarray(ao_map.convert("L"), dtype=np.float64) / 255.0
    out = np.zeros(id_source.shape[:2], dtype=np.float64)
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        seed = _hash_seed(f"wear-mask:{zone['part']}:{zone['material']}")
        masks = _surface_wear_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        combined = np.maximum.reduce(list(masks.values()))
        out[mask] = np.maximum(out[mask], combined[mask] * 255.0)
    return Image.fromarray(np.clip(out, 0.0, 255.0).astype(np.uint8), mode="L")


def bake_material_layer_mask(
    id_map: Image.Image, material_zones: list[dict[str, Any]], curvature_map: Image.Image, ao_map: Image.Image
) -> Image.Image:
    id_source = np.asarray(id_map, dtype=np.uint8)
    curvature = np.asarray(curvature_map.convert("L"), dtype=np.float64) / 255.0
    ao = np.asarray(ao_map.convert("L"), dtype=np.float64) / 255.0
    out = np.zeros(id_source.shape[:2], dtype=np.float64)
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        seed = _hash_seed(f"layer-mask:{zone['part']}:{zone['material']}")
        layer_mask, accent_mask = _surface_material_masks(
            zone,
            size=id_source.shape[0],
            seed=seed,
            curvature=curvature,
            ao=ao,
        )
        combined = np.maximum(layer_mask, accent_mask)
        out[mask] = np.maximum(out[mask], combined[mask] * 255.0)
    return Image.fromarray(np.clip(out, 0.0, 255.0).astype(np.uint8), mode="L")


def bake_metallic_map(id_map: Image.Image, material_zones: list[dict[str, Any]]) -> Image.Image:
    id_source = np.asarray(id_map, dtype=np.uint8)
    out = np.zeros(id_source.shape[:2], dtype=np.uint8)
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        out[mask] = int(max(0, min(255, float(zone.get("metallic", 0.0)) * 255.0)))
    return Image.fromarray(out, mode="L")


def bake_emissive_map(id_map: Image.Image, material_zones: list[dict[str, Any]]) -> Image.Image:
    image = np.zeros((*id_map.size[::-1], 3), dtype=np.uint8)
    id_source = np.asarray(id_map, dtype=np.uint8)
    _x, y = _coord_grid(id_source.shape[0])
    for zone in material_zones:
        color = tuple(int(value) for value in zone["basecolor"])
        mask = _color_mask(id_source, color)
        if not np.any(mask):
            continue
        emissive = np.asarray(zone.get("emissive", [0, 0, 0]), dtype=np.float64)
        if emissive.max() <= 0:
            continue
        seed = _hash_seed(f"emissive:{zone['part']}")
        profile = str(zone.get("surface_profile", "neutral_panel"))
        pulse = _profile_pattern(profile, id_source.shape[0], seed)
        if profile == "screen_glass":
            pulse = np.clip(0.45 + pulse * 0.55 + np.sin(y * np.pi * 36.0) * 0.08, 0.0, 1.0)
        values = np.clip(emissive[None, None, :] * (0.55 + pulse[..., None] * 0.65), 0.0, 255.0)
        image[mask] = values[mask].astype(np.uint8)
    return Image.fromarray(image, mode="RGB")


def apply_decal_overlays(
    basecolor_map: Image.Image,
    roughness_map: Image.Image,
    emissive_map: Image.Image,
    decals: list[str],
    placements: list[dict[str, Any]] | None = None,
) -> tuple[Image.Image, Image.Image, Image.Image]:
    if not decals:
        return basecolor_map, roughness_map, emissive_map

    basecolor = basecolor_map.copy()
    roughness = roughness_map.copy()
    emissive = emissive_map.copy()
    base_draw = ImageDraw.Draw(basecolor, "RGB")
    rough_draw = ImageDraw.Draw(roughness, "L")
    emissive_draw = ImageDraw.Draw(emissive, "RGB")
    width, height = basecolor.size
    placement_by_decal = {
        str(item.get("decal", "")).lower(): item
        for item in (placements or [])
        if isinstance(item, dict)
    }

    def anchor_for(name: str, default_x: float, default_y: float) -> tuple[float, float]:
        placement = placement_by_decal.get(str(name).lower())
        anchor = placement.get("anchor_uv") if isinstance(placement, dict) else None
        if isinstance(anchor, list) and len(anchor) >= 2:
            return (
                max(0.02, min(0.96, float(anchor[0]))),
                max(0.02, min(0.96, float(anchor[1]))),
            )
        return default_x, default_y

    def draw_label_block(
        x0: float, y0: float, x1: float, y1: float, color: tuple[int, int, int], roughness_value: int
    ) -> None:
        rect = [int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)]
        base_draw.rectangle(rect, fill=color)
        rough_draw.rectangle(rect, fill=roughness_value)

    def draw_story_label(name: str) -> None:
        seed = _hash_seed(f"label:{name}")
        x0, y0 = anchor_for(name, 0.08 + seed * 0.28, 0.08 + (1.0 - seed) * 0.16)
        x0 = min(0.72, x0)
        y0 = min(0.82, y0)
        draw_label_block(x0, y0, x0 + 0.24, y0 + 0.065, (222, 220, 208), 148)
        draw_label_block(x0 + 0.025, y0 + 0.017, x0 + 0.19, y0 + 0.027, (32, 36, 42), 126)
        draw_label_block(x0 + 0.025, y0 + 0.038, x0 + 0.15, y0 + 0.047, (32, 36, 42), 126)

    def draw_scrape_cluster(name: str) -> None:
        seed = _hash_seed(f"scrape:{name}")
        ax, ay = anchor_for(name, 0.28 + seed * 0.46, 0.30 + (1.0 - seed) * 0.34)
        cx = int(width * ax)
        cy = int(height * ay)
        span = max(18, width // 9)
        for index in range(7):
            offset = int((index - 3) * max(4, width // 80))
            length = int(span * (0.45 + (index % 3) * 0.16))
            y = cy + offset
            base_draw.line(
                [(cx - length // 2, y + length // 5), (cx + length // 2, y - length // 5)],
                fill=(196, 188, 166),
                width=max(1, width // 180),
            )
            rough_draw.line(
                [(cx - length // 2, y + length // 5), (cx + length // 2, y - length // 5)],
                fill=92,
                width=max(1, width // 140),
            )

    def draw_dent_cluster(name: str) -> None:
        seed = _hash_seed(f"dent:{name}")
        ax, ay = anchor_for(name, 0.36 + seed * 0.32, 0.34 + (1.0 - seed) * 0.28)
        cx = int(width * ax)
        cy = int(height * ay)
        for index in range(4):
            radius = max(6, int(width * (0.018 + ((seed + index * 0.071) % 0.022))))
            x = cx + int((index - 1.5) * radius * 1.35)
            y = cy + int(np.sin(seed * 5.0 + index) * radius * 0.65)
            base_draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=(62, 58, 54),
                outline=(150, 142, 128),
                width=max(1, width // 190),
            )
            rough_draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=204)

    def draw_edge_rub() -> None:
        inset = max(4, width // 48)
        for step in range(3):
            color = (184 - step * 18, 174 - step * 16, 148 - step * 14)
            rect = [inset + step * 5, inset + step * 5, width - inset - step * 5, height - inset - step * 5]
            base_draw.rectangle(rect, outline=color, width=max(1, width // 160))
            rough_draw.rectangle(rect, outline=104 + step * 8, width=max(1, width // 160))

    def draw_rune_cluster(name: str) -> None:
        seed = _hash_seed(f"rune:{name}")
        base_x = int(width * (0.32 + seed * 0.22))
        base_y = int(height * (0.38 + seed * 0.18))
        step = max(10, width // 32)
        rune_color = (92, 178, 138)
        for index in range(5):
            x = base_x + (index - 2) * step
            y = base_y + int(np.sin(index + seed) * step * 0.35)
            h = max(12, height // 24)
            base_draw.line([(x, y - h // 2), (x, y + h // 2)], fill=rune_color, width=max(1, width // 180))
            base_draw.line([(x - h // 4, y), (x + h // 4, y - h // 3)], fill=rune_color, width=max(1, width // 180))
            rough_draw.line([(x, y - h // 2), (x, y + h // 2)], fill=84, width=max(1, width // 150))
            emissive_draw.line([(x, y - h // 2), (x, y + h // 2)], fill=(18, 62, 40), width=max(1, width // 170))

    def draw_color_bar(name: str, color: tuple[int, int, int]) -> None:
        _, ay = anchor_for(name, 0.50, 0.62)
        top = int(height * max(0.08, min(0.88, ay)))
        bar_h = max(8, height // 28)
        base_draw.rectangle([int(width * 0.16), top, int(width * 0.84), top + bar_h], fill=color)
        rough_draw.rectangle([int(width * 0.16), top, int(width * 0.84), top + bar_h], fill=112)

    def draw_heat_marks(name: str) -> None:
        ax, ay = anchor_for(name, 0.66, 0.42)
        cx = int(width * ax)
        cy = int(height * ay)
        for radius, color in (
            (max(18, width // 12), (84, 92, 116)),
            (max(12, width // 16), (124, 86, 58)),
            (max(7, width // 24), (174, 126, 58)),
        ):
            base_draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=color, width=max(2, width // 120))
            rough_draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=118, width=max(1, width // 150))

    def draw_calibration_marks(name: str) -> None:
        _, ay = anchor_for(name, 0.50, 0.18)
        x0 = int(width * 0.18)
        x1 = int(width * 0.82)
        y = int(height * max(0.06, min(0.86, ay)))
        base_draw.line([(x0, y), (x1, y)], fill=(118, 176, 212), width=max(1, width // 160))
        rough_draw.line([(x0, y), (x1, y)], fill=98, width=max(1, width // 160))
        for index in range(9):
            x = x0 + int((x1 - x0) * index / 8)
            base_draw.line([(x, y - 6), (x, y + 6)], fill=(210, 226, 232), width=max(1, width // 220))

    def draw_mottled_patches(name: str, color: tuple[int, int, int], roughness_value: int) -> None:
        seed = _hash_seed(f"mottle:{name}")
        for index in range(18):
            px = int(width * ((seed + index * 0.137) % 1.0))
            py = int(height * ((seed * 0.71 + index * 0.191) % 1.0))
            rx = max(4, int(width * (0.010 + ((seed + index * 0.043) % 0.026))))
            ry = max(3, int(height * (0.008 + ((seed + index * 0.031) % 0.022))))
            base_draw.ellipse([px - rx, py - ry, px + rx, py + ry], fill=color)
            rough_draw.ellipse([px - rx, py - ry, px + rx, py + ry], fill=roughness_value)

    def draw_wavy_band(name: str, color: tuple[int, int, int], roughness_value: int) -> None:
        seed = _hash_seed(f"wavy:{name}")
        y0 = int(height * (0.55 + (seed - 0.5) * 0.16))
        points = []
        for index in range(18):
            x = int(width * index / 17)
            y = y0 + int(np.sin(index * 0.9 + seed * 4.0) * max(4, height // 44))
            points.append((x, y))
        base_draw.line(points, fill=color, width=max(2, width // 75))
        rough_draw.line(points, fill=roughness_value, width=max(2, width // 75))

    def draw_crack_network(name: str, emissive: bool = False) -> None:
        seed = _hash_seed(f"cracks:{name}")
        for index in range(9):
            x = int(width * ((seed + index * 0.173) % 1.0))
            y = int(height * ((seed * 0.53 + index * 0.127) % 1.0))
            length = max(18, int(width * (0.08 + ((seed + index * 0.037) % 0.09))))
            angle = (seed + index * 0.37) * np.pi
            x2 = int(x + np.cos(angle) * length)
            y2 = int(y + np.sin(angle) * length)
            color = (38, 34, 30)
            glow = (210, 64, 18)
            base_draw.line([(x, y), (x2, y2)], fill=glow if emissive else color, width=max(1, width // 130))
            rough_draw.line([(x, y), (x2, y2)], fill=92, width=max(1, width // 130))
            if emissive:
                emissive_draw.line([(x, y), (x2, y2)], fill=(220, 74, 18), width=max(1, width // 120))

    for decal in decals:
        name = str(decal).lower()
        if "trim_wear" in name or "warning_band" in name:
            inset = max(6, width // 40)
            base_draw.rectangle(
                [inset, inset, width - inset, height - inset],
                outline=(210, 184, 118),
                width=max(2, inset // 3),
            )
            rough_draw.rectangle(
                [inset, inset, width - inset, height - inset], outline=118, width=max(2, inset // 3)
            )
        if "crest" in name:
            cx, cy = width // 2, height // 2
            rx, ry = max(16, width // 14), max(18, height // 12)
            base_draw.ellipse(
                [cx - rx, cy - ry, cx + rx, cy + ry], fill=(188, 150, 74), outline=(230, 202, 132), width=3
            )
            base_draw.line([cx - rx // 2, cy, cx + rx // 2, cy], fill=(128, 54, 32), width=3)
            rough_draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=92)
        if (
            "serial" in name
            or "service_label" in name
            or "maintenance_label" in name
            or "shipping_mark" in name
            or "door_number" in name
        ):
            draw_label_block(0.12, 0.12, 0.34, 0.18, (224, 222, 214), 150)
            draw_label_block(0.14, 0.20, 0.30, 0.24, (32, 36, 42), 132)
            draw_label_block(0.14, 0.26, 0.28, 0.29, (32, 36, 42), 132)
            draw_label_block(0.62, 0.18, 0.84, 0.24, (214, 214, 208), 146)
            draw_label_block(0.64, 0.26, 0.80, 0.29, (28, 32, 40), 132)
        if (
            "unit" in name
            or "operator_label" in name
            or "cable_tag" in name
            or "calibration_id" in name
            or "service_number" in name
        ):
            draw_story_label(name)
        if "warning" in name:
            stripe_height = max(14, height // 18)
            top = int(height * 0.72)
            for offset in range(-width, width, stripe_height * 2):
                points = [
                    (offset, top + stripe_height),
                    (offset + stripe_height, top),
                    (offset + stripe_height * 3, top),
                    (offset + stripe_height * 2, top + stripe_height),
                ]
                base_draw.polygon(points, fill=(220, 170, 48))
                rough_draw.polygon(points, fill=108)
            draw_label_block(0.58, 0.70, 0.86, 0.76, (42, 44, 50), 120)
        if "screen_glow" in name:
            rect = [int(width * 0.28), int(height * 0.22), int(width * 0.72), int(height * 0.58)]
            emissive_draw.rectangle(rect, fill=(54, 98, 220))
            emissive_draw.rectangle(
                [rect[0] + 6, rect[1] + 6, rect[2] - 6, rect[3] - 6], outline=(142, 188, 255), width=3
            )
        if "trim" in name and "wear" not in name:
            draw_label_block(0.10, 0.82, 0.90, 0.86, (56, 62, 70), 144)
        if "scrape" in name or "scratch" in name:
            draw_scrape_cluster(name)
        if "dent" in name:
            draw_dent_cluster(name)
        if "chip" in name:
            draw_mottled_patches(name, (188, 180, 156), 96)
            draw_edge_rub()
        if "rubbed" in name or "handled" in name or "edge" in name:
            draw_edge_rub()
        if "rune" in name or "etched" in name:
            draw_rune_cluster(name)
        if "red_bar" in name:
            draw_color_bar(name, (170, 38, 44))
        if "stripe" in name and "warning" not in name:
            draw_color_bar(name, (74, 132, 180))
        if "heat" in name:
            draw_heat_marks(name)
        if "calibration" in name:
            draw_calibration_marks(name)
        if "moss" in name or "lichen" in name or "algae" in name:
            draw_mottled_patches(name, (70, 118, 68), 172)
        if "leaf" in name:
            draw_mottled_patches(name, (128, 82, 34), 184)
        if "mud" in name or "silt" in name or "grime" in name:
            draw_mottled_patches(name, (78, 58, 38), 218)
        if "foam" in name or "shoreline" in name or "waterline" in name:
            draw_wavy_band(name, (218, 232, 224), 142)
        if "snow" in name or "frost" in name:
            draw_wavy_band(name, (224, 230, 232), 188)
            draw_mottled_patches(name, (232, 236, 238), 204)
        if "trail" in name or "scuff" in name:
            draw_scrape_cluster(name)
        if "crack" in name or "strata" in name:
            draw_crack_network(name, emissive="lava" in name)
        if "lava" in name:
            draw_crack_network(name, emissive=True)
        if "sand" in name or "wind" in name:
            draw_wavy_band(name, (184, 150, 92), 220)

    return basecolor, roughness, emissive


def combine_orm(ao_map: Image.Image, roughness_map: Image.Image, metallic_map: Image.Image) -> Image.Image:
    ao = np.asarray(ao_map, dtype=np.uint8)
    roughness = np.asarray(roughness_map, dtype=np.uint8)
    metallic = np.asarray(metallic_map, dtype=np.uint8)
    orm = np.zeros((*ao.shape, 3), dtype=np.uint8)
    orm[:, :, 0] = ao
    orm[:, :, 1] = roughness
    orm[:, :, 2] = metallic
    return Image.fromarray(orm, mode="RGB")
