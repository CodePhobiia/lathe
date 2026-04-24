"""Reference-image/material/mesh conditioning for the shape stage.

Produces the ``conditioning`` dict consumed by the scaffold compiler and
provider mux under the ``lathe.shape.intent_mesh_handoff_v1`` contract.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .primitives import (
    SUPPORTED_MESH_EXTS,
    _clamp,
    _characteristic_scale_cm,
    _load_mesh_file,
)


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _resolve_ref_path(source_root: Path, value: Any) -> Path | None:
    if isinstance(value, dict) and value.get("type") == "call":
        args = value.get("args", [])
        if args:
            value = args[0].get("value")
    try:
        path = Path(str(value))
    except (TypeError, ValueError, OSError):
        # str(value) can fail when value's __str__ is misbehaving; Path()
        # raises ValueError/OSError for path strings the OS can't represent.
        return None
    if not path.is_absolute():
        path = source_root / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if resolved.exists() and resolved.is_file():
        return resolved
    return None


def _image_kind_hint(path: Path) -> str:
    stem = path.stem.lower()
    if "front" in stem:
        return "front"
    if "side" in stem:
        return "side"
    if "top" in stem:
        return "top"
    if "mat" in stem or "material" in stem or "palette" in stem or "albedo" in stem:
        return "material"
    return "reference"


def _image_mask(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3].astype(np.float32)
    if alpha.min() != alpha.max():
        mask = alpha > 24
    else:
        gray = rgb.mean(axis=2)
        mask = gray < 245
        if mask.sum() < 16:
            mask = gray < 250
    if mask.sum() < 16:
        mask = np.ones(mask.shape, dtype=bool)
    return mask


def _dominant_palette(rgb_pixels: np.ndarray, count: int = 3) -> list[list[int]]:
    if len(rgb_pixels) == 0:
        return []
    if len(rgb_pixels) > 4096:
        idx = np.linspace(0, len(rgb_pixels) - 1, num=4096, dtype=int)
        rgb_pixels = rgb_pixels[idx]
    bins = (rgb_pixels // 32).astype(np.int16)
    uniq, counts = np.unique(bins, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:count]
    palette = []
    for bin_rgb in uniq[order]:
        palette.append([int(bin_rgb[0] * 32 + 16), int(bin_rgb[1] * 32 + 16), int(bin_rgb[2] * 32 + 16)])
    return palette


def _analyze_image_ref(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGBA")
    rgba = np.asarray(image, dtype=np.uint8)
    mask = _image_mask(image)
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    box_w = max(1, x1 - x0 + 1)
    box_h = max(1, y1 - y0 + 1)
    pixels = rgba[:, :, :3][mask]
    mean_rgb = [int(v) for v in pixels.mean(axis=0)] if len(pixels) else [200, 200, 200]
    return {
        "path": str(path),
        "kind": _image_kind_hint(path),
        "width": int(image.width),
        "height": int(image.height),
        "bbox": [x0, y0, x1, y1],
        "aspect": round(float(box_w / max(1, box_h)), 6),
        "fill_ratio": round(float(mask.sum() / max(1, box_w * box_h)), 6),
        "mean_rgb": mean_rgb,
        "palette": _dominant_palette(pixels, count=3),
    }


def _analyze_mesh_ref(path: Path) -> dict[str, Any] | None:
    mesh = _load_mesh_file(path)
    if mesh is None or len(mesh.faces) == 0:
        return None
    bounds = mesh.bounds
    extents = bounds[1] - bounds[0]
    return {
        "path": str(path),
        "vertex_count": int(len(mesh.vertices)),
        "triangle_count": int(len(mesh.faces)),
        "extents": [round(float(v), 6) for v in extents],
        "watertight": bool(mesh.is_watertight),
    }


def collect_shape_conditioning(asset: dict[str, Any], source_root: Path) -> dict[str, Any]:
    refs = asset.get("refs", {})
    consumed_refs: list[dict[str, Any]] = []
    image_refs: list[dict[str, Any]] = []
    material_refs: list[dict[str, Any]] = []
    mesh_refs: list[dict[str, Any]] = []

    for group in ("images", "materials"):
        for value in refs.get(group, []):
            resolved = _resolve_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if resolved is not None:
                analysis = _analyze_image_ref(resolved)
                entry["kind"] = analysis["kind"]
                if group == "materials" or analysis["kind"] == "material":
                    material_refs.append(analysis)
                else:
                    image_refs.append(analysis)
            consumed_refs.append(entry)

    for group in ("meshes", "assets"):
        for value in refs.get(group, []):
            resolved = _resolve_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if resolved is not None and resolved.suffix.lower() in SUPPORTED_MESH_EXTS:
                analysis = _analyze_mesh_ref(resolved)
                if analysis is not None:
                    mesh_refs.append(analysis)
                    entry["kind"] = "mesh"
            consumed_refs.append(entry)

    front = next((item for item in image_refs if item["kind"] == "front"), image_refs[0] if image_refs else None)
    side = next((item for item in image_refs if item["kind"] == "side"), image_refs[1] if len(image_refs) > 1 else front)
    material = material_refs[0] if material_refs else next((item for item in image_refs if item["kind"] == "material"), None)

    combined_palette: list[list[int]] = []
    for source in [material, front, side, *image_refs]:
        if not source:
            continue
        for color in source.get("palette", []):
            if color not in combined_palette:
                combined_palette.append(color)
        if len(combined_palette) >= 4:
            break

    total_declared = sum(len(refs.get(key, [])) for key in ("images", "materials", "meshes", "assets"))
    reference_strength = round(float((len(image_refs) + len(material_refs) + len(mesh_refs)) / max(1, total_declared)), 6)
    return {
        "source_root": str(source_root),
        "consumed_refs": consumed_refs,
        "image_refs": image_refs,
        "material_refs": material_refs,
        "mesh_refs": mesh_refs,
        "front_aspect": front["aspect"] if front else None,
        "side_aspect": side["aspect"] if side else None,
        "front_fill_ratio": front["fill_ratio"] if front else None,
        "side_fill_ratio": side["fill_ratio"] if side else None,
        "material_brightness": round(sum(material["mean_rgb"]) / (3 * 255.0), 6) if material else None,
        "palette": combined_palette,
        "reference_strength": reference_strength,
    }


def _conditioned_part_colors(parts: list[str], conditioning: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    palette = conditioning.get("palette", [])
    brightness = conditioning.get("material_brightness")
    out: dict[str, tuple[int, int, int]] = {}
    palette_index = 0
    for part in parts:
        lname = part.lower()
        if any(token in lname for token in ("glass", "camera", "sensor", "gimbal")):
            out[part] = (214, 148, 72)
            continue
        if any(token in lname for token in ("rotor", "fan", "prop")):
            out[part] = (72, 76, 84)
            continue
        if palette:
            rgb = palette[min(palette_index, len(palette) - 1)]
            palette_index += 1
            color = [int(v) for v in rgb]
            if brightness is not None and brightness < 0.45:
                color = [max(45, int(v * 0.9)) for v in color]
            out[part] = tuple(color)
            continue
        out[part] = _make_color(part)
    return out


def _conditioned_body_extents(asset: dict[str, Any], conditioning: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    scale_cm = _characteristic_scale_cm(asset)
    front_aspect = float(conditioning.get("front_aspect") or 1.55)
    side_aspect = float(conditioning.get("side_aspect") or 1.75)
    fill = float(conditioning.get("front_fill_ratio") or conditioning.get("side_fill_ratio") or 0.58)
    style = [str(item).lower() for item in asset.get("intent", {}).get("style", [])]
    slim_bias = 0.04 if any(token in style for token in ("premium", "near-future")) else 0.0
    width = scale_cm * _clamp(0.22 + 0.12 * front_aspect - slim_bias + float(rng.uniform(-0.02, 0.02)), 0.22, 0.56)
    height = scale_cm * _clamp(0.11 + 0.14 / max(0.8, front_aspect) + 0.03 * (1.0 - fill) + float(rng.uniform(-0.015, 0.015)), 0.10, 0.28)
    depth = scale_cm * _clamp(0.28 + 0.12 * side_aspect - slim_bias + float(rng.uniform(-0.03, 0.03)), 0.28, 0.82)
    return np.array([width, height, depth], dtype=float)
