"""Reference-image/material/mesh conditioning for the shape stage.

Produces the ``conditioning`` dict consumed by the scaffold compiler and
provider mux under the ``lathe.shape.intent_mesh_handoff_v1`` contract.
"""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from ...mesh_ingest import DEFAULT_MAX_BYTES, ShapeMeshLoadError
from ...paths import PathGuardError, safe_resolve
from ...security import InputClass, TrustLevel, boundary_policy, ingress_boundary
from .primitives import SUPPORTED_MESH_EXTS, _load_mesh_file

_ALLOWED_IMAGE_REF_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_IMAGE_REF_BYTES = 16 * 1024 * 1024
_MAX_IMAGE_REF_PIXELS = 16_000_000
_MAX_MESH_REF_BYTES = DEFAULT_MAX_BYTES
_EXTERNAL_IMAGE_BOUNDARY = boundary_policy(
    name="shape_conditioning_image_refs",
    input_class=InputClass.EXTERNAL_IMAGE,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "safe_project_relative_path",
        "format_allowlist",
        "byte_cap",
        "pixel_cap",
        "pillow_exception_narrowing",
    ),
)
_EXTERNAL_MESH_REF_BOUNDARY = boundary_policy(
    name="shape_conditioning_mesh_refs",
    input_class=InputClass.EXTERNAL_MESH,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "safe_project_relative_path",
        "format_allowlist",
        "byte_cap",
        "safe_mesh_loader",
    ),
)


class _ImageRefRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _path_rejection_code(exc: PathGuardError) -> str:
    message = str(exc)
    if "absolute path" in message:
        return "absolute_path_rejected"
    if "escapes root" in message or "path components" in message:
        return "path_traversal_rejected"
    return "invalid_path"


def _resolve_ref_path(source_root: Path, value: Any) -> tuple[Path | None, str | None]:
    try:
        resolved = safe_resolve(source_root, str(_raw_ref_value(value)))
    except PathGuardError as exc:
        return None, _path_rejection_code(exc)
    except (TypeError, ValueError, OSError):
        return None, "invalid_path"
    if resolved.exists() and resolved.is_file():
        return resolved, None
    return None, "missing"


def _raw_ref_value(value: Any) -> Any:
    if isinstance(value, dict) and value.get("type") == "call":
        args = value.get("args", [])
        if args:
            return args[0].get("value")
    return value


def _resolve_image_ref_path(source_root: Path, value: Any) -> tuple[Path | None, str | None]:
    try:
        resolved = safe_resolve(source_root, str(_raw_ref_value(value)))
    except PathGuardError as exc:
        return None, _path_rejection_code(exc)
    except (TypeError, ValueError, OSError):
        return None, "invalid_path"
    if not resolved.exists() or not resolved.is_file():
        return None, "missing"
    if resolved.suffix.lower() not in _ALLOWED_IMAGE_REF_EXTS:
        return None, "unsupported_image_format"
    try:
        size = resolved.stat().st_size
    except OSError:
        return None, "stat_failed"
    if size > _MAX_IMAGE_REF_BYTES:
        return None, "image_file_too_large"
    return resolved, None


def _resolve_mesh_ref_path(source_root: Path, value: Any) -> tuple[Path | None, str | None]:
    resolved, rejected = _resolve_ref_path(source_root, value)
    if resolved is None:
        return None, rejected
    if resolved.suffix.lower() not in SUPPORTED_MESH_EXTS:
        return None, "unsupported_mesh_format"
    try:
        size = resolved.stat().st_size
    except OSError:
        return None, "stat_failed"
    if size > _MAX_MESH_REF_BYTES:
        return None, "mesh_file_too_large"
    return resolved, None


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
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                if (int(opened.width) * int(opened.height)) > _MAX_IMAGE_REF_PIXELS:
                    raise _ImageRefRejected(
                        "image_dimensions_too_large",
                        "image dimensions exceed the configured limit",
                    )
                image = opened.convert("RGBA")
    except _ImageRefRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _ImageRefRejected("invalid_image", f"image could not be decoded: {exc}") from exc
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
        "vertex_count": len(mesh.vertices),
        "triangle_count": len(mesh.faces),
        "extents": [round(float(v), 6) for v in extents],
        "watertight": bool(mesh.is_watertight),
    }


@ingress_boundary(_EXTERNAL_IMAGE_BOUNDARY, _EXTERNAL_MESH_REF_BOUNDARY)
def collect_shape_conditioning(asset: dict[str, Any], source_root: Path) -> dict[str, Any]:
    refs = asset.get("refs", {})
    consumed_refs: list[dict[str, Any]] = []
    image_refs: list[dict[str, Any]] = []
    material_refs: list[dict[str, Any]] = []
    mesh_refs: list[dict[str, Any]] = []

    for group in ("images", "materials"):
        for value in refs.get(group, []):
            resolved, rejected_reason = _resolve_image_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if rejected_reason and rejected_reason != "missing":
                entry["rejected_reason"] = rejected_reason
            if resolved is not None:
                try:
                    analysis = _analyze_image_ref(resolved)
                except _ImageRefRejected as exc:
                    entry["exists"] = False
                    entry["rejected_reason"] = exc.code
                else:
                    entry["kind"] = analysis["kind"]
                    if group == "materials" or analysis["kind"] == "material":
                        material_refs.append(analysis)
                    else:
                        image_refs.append(analysis)
            consumed_refs.append(entry)

    for group in ("meshes", "assets"):
        for value in refs.get(group, []):
            if group == "meshes":
                resolved, rejected_reason = _resolve_mesh_ref_path(source_root, value)
            else:
                resolved, rejected_reason = _resolve_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if rejected_reason and rejected_reason != "missing":
                entry["rejected_reason"] = rejected_reason
            if resolved is not None and resolved.suffix.lower() in SUPPORTED_MESH_EXTS:
                try:
                    analysis = _analyze_mesh_ref(resolved)
                except ShapeMeshLoadError as exc:
                    entry["exists"] = False
                    entry["rejected_reason"] = exc.code
                    analysis = None
                if analysis is not None:
                    mesh_refs.append(analysis)
                    entry["kind"] = "mesh"
            consumed_refs.append(entry)

    front = next(
        (item for item in image_refs if item["kind"] == "front"), image_refs[0] if image_refs else None
    )
    side = next(
        (item for item in image_refs if item["kind"] == "side"),
        image_refs[1] if len(image_refs) > 1 else front,
    )
    material = (
        material_refs[0]
        if material_refs
        else next((item for item in image_refs if item["kind"] == "material"), None)
    )

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
    reference_strength = round(
        float((len(image_refs) + len(material_refs) + len(mesh_refs)) / max(1, total_declared)), 6
    )
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


def merge_quality_generation_conditioning(
    conditioning: dict[str, Any], quality_generation: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge pre-shape quality planning into shape-stage conditioning metadata."""
    out = dict(conditioning or {})
    generation = quality_generation if isinstance(quality_generation, dict) else {}
    if not generation:
        out.setdefault("quality_plan_consumed", False)
        return out
    adapters = generation.get("generation_adapters")
    quality_plan = generation.get("quality_plan")
    art_direction = generation.get("art_direction_ir") or (
        quality_plan.get("art_direction_ir") if isinstance(quality_plan, dict) else {}
    )
    out["quality_plan_consumed"] = isinstance(quality_plan, dict) and bool(quality_plan)
    out["quality_generation_source_stage"] = generation.get("source_stage")
    out["quality_conditioning"] = dict(adapters) if isinstance(adapters, dict) else {}
    if isinstance(quality_plan, dict):
        out["quality_plan"] = quality_plan
    if isinstance(art_direction, dict):
        out["art_direction_ir"] = art_direction
    return out


def _conditioned_part_colors(
    parts: list[str], conditioning: dict[str, Any]
) -> dict[str, tuple[int, int, int]]:
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
