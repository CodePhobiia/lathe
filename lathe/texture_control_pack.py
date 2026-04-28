"""Texture control pack: in-memory representation of per-asset textures.

Collects the images and per-channel metadata the surface stage
produces and the package stage consumes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image


def relative_uri(root: Path, path: Path) -> str:
    """Relative uri.

    Args:
        root: root argument.
        path: path argument.

    Returns:
        The result.
    """
    return str(path.relative_to(root)).replace("/", "\\")


def write_image(image: Image.Image, path: Path) -> dict[str, Any]:
    """Write image.

    Args:
        image: image argument.
        path: path argument.

    Returns:
        The result.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {"name": path.stem, "uri": str(path), "size_bytes": path.stat().st_size}


def write_surface_control_pack(
    *,
    out_dir: Path,
    size: int,
    material_zones: list[dict[str, Any]],
    surface_cfg: dict[str, Any],
    source_surface: dict[str, Any],
    ao: Image.Image,
    curvature: Image.Image,
    normal: Image.Image,
    id_map: Image.Image,
) -> dict[str, Any]:
    """Write surface control pack.

    Args:
        out_dir: out_dir argument.
        size: size argument.
        material_zones: material_zones argument.
        surface_cfg: surface_cfg argument.
        source_surface: source_surface argument.
        ao: ao argument.
        curvature: curvature argument.
        normal: normal argument.
        id_map: id_map argument.

    Returns:
        The result.
    """
    pack_dir = out_dir / "surface_control_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    uv_layout = Image.new("L", (size, size), 0)
    padded = Image.new("L", (size, size), 255)
    preview = id_map.convert("RGB")
    outputs = {
        "uv_layout": write_image(uv_layout, pack_dir / "uv_layout.png"),
        "padded_island_mask": write_image(padded, pack_dir / "padded_island_mask.png"),
        "material_zone_mask": write_image(id_map.convert("RGB"), pack_dir / "material_zone_mask.png"),
        "ao": write_image(ao.convert("L"), pack_dir / "ao.png"),
        "curvature": write_image(curvature.convert("L"), pack_dir / "curvature.png"),
        "normal_reference": write_image(normal.convert("RGB"), pack_dir / "normal_reference.png"),
        "preview": write_image(preview, pack_dir / "preview.png"),
    }
    required_maps = list(surface_cfg.get("maps", []))
    manifest = {
        "schema": "lathe.surface_control_pack.v1",
        "target_resolution": size,
        "required_maps": required_maps,
        "material_zones": material_zones,
        "per_zone_constraints": {
            entry["part"]: {
                "material": entry["material"],
                "metallic": entry.get("metallic", 0.0),
                "roughness": entry.get("roughness", 0.5),
            }
            for entry in material_zones
        },
        "semantic_descriptors": {
            "surface_program": source_surface.get("program", ""),
            "policy": source_surface.get("policy", ""),
            "decal_libraries": list(source_surface.get("decal_libraries", [])),
            "mask_programs": list(source_surface.get("mask_programs", [])),
            "trim_sheets": list(source_surface.get("trim_sheets", [])),
        },
        "images": {name: relative_uri(out_dir, Path(entry["uri"])) for name, entry in outputs.items()},
    }
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "manifest_uri": relative_uri(out_dir, manifest_path),
        "images": manifest["images"],
        "required_maps": required_maps,
    }
