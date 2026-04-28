from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import trimesh
from PIL import Image, ImageDraw


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


def _profile_pattern(profile: str, size: int, seed: float) -> np.ndarray:
    if profile == "wood_grain":
        return _wood_pattern(size, seed)
    if profile in {"brushed_metal", "worn_brass"}:
        return _metal_pattern(size, seed)
    if profile == "fabric_lining":
        return _fabric_pattern(size, seed)
    if profile == "screen_glass":
        return _glass_pattern(size, seed)
    if profile in {"painted_panel", "neutral_panel", "carbon_rubber"}:
        return _paint_pattern(size, seed)
    return _noise_field(size, seed)


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
    nx = (normal_arr[..., 0] / 255.0) * 2.0 - 1.0
    ny = (normal_arr[..., 1] / 255.0) * 2.0 - 1.0
    nz = np.sqrt(np.clip(1.0 - np.clip(nx * nx + ny * ny, 0.0, 0.95), 0.0, 1.0))
    normal_arr[..., 2] = np.clip((nz * 0.5 + 0.5) * 255.0, 0.0, 255.0)

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
        out[mask] = np.clip(values[mask], 0.0, 255.0)
    return Image.fromarray(out.astype(np.uint8), mode="RGB")


def bake_normal_map(mesh: trimesh.Trimesh, size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), (128, 128, 255))
    draw = ImageDraw.Draw(image, "RGB")
    polygons = _face_uv_polygons(mesh, size)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    for face_index, polygon in enumerate(polygons):
        normal = normals[face_index]
        rgb = tuple(
            int(max(0, min(255, (value * 0.5 + 0.5) * 255.0))) for value in (normal[0], normal[1], normal[2])
        )
        draw.polygon(polygon, fill=rgb)
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
        x_detail = (pattern - 0.5) * (44.0 * intensity)
        y_detail = ((curvature - 0.5) + (pattern - 0.5) * 0.65) * (40.0 * intensity)
        out[..., 0][mask] = np.clip(source[..., 0][mask] + x_detail[mask], 0.0, 255.0)
        out[..., 1][mask] = np.clip(source[..., 1][mask] + y_detail[mask], 0.0, 255.0)
    nx = (out[..., 0] / 255.0) * 2.0 - 1.0
    ny = (out[..., 1] / 255.0) * 2.0 - 1.0
    nz = np.sqrt(np.clip(1.0 - np.clip(nx * nx + ny * ny, 0.0, 0.95), 0.0, 1.0))
    out[..., 2] = np.clip((nz * 0.5 + 0.5) * 255.0, 0.0, 255.0)
    return Image.fromarray(out.astype(np.uint8), mode="RGB")


def bake_curvature_map(mesh: trimesh.Trimesh, size: int) -> Image.Image:
    image = Image.new("L", (size, size), 128)
    draw = ImageDraw.Draw(image, "L")
    polygons = _face_uv_polygons(mesh, size)
    adjacency = mesh.face_adjacency
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    curvature = np.zeros(len(mesh.faces), dtype=np.float64)
    if len(adjacency) > 0:
        for left, right in adjacency:
            dot = float(np.clip(np.dot(normals[left], normals[right]), -1.0, 1.0))
            angle = np.arccos(dot)
            curvature[left] = max(curvature[left], angle)
            curvature[right] = max(curvature[right], angle)
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
        values = np.clip(
            values + (1.0 - ao) * 0.12 - np.clip(curvature - 0.48, 0.0, 0.42) * wear * 0.48, 0.02, 0.98
        )
        out[mask] = values[mask] * 255.0
    return Image.fromarray(out.astype(np.uint8), mode="L")


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
    basecolor_map: Image.Image, roughness_map: Image.Image, emissive_map: Image.Image, decals: list[str]
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

    def draw_label_block(
        x0: float, y0: float, x1: float, y1: float, color: tuple[int, int, int], roughness_value: int
    ) -> None:
        rect = [int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)]
        base_draw.rectangle(rect, fill=color)
        rough_draw.rectangle(rect, fill=roughness_value)

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
