"""Texture control pack: in-memory representation of per-asset textures.

Collects the images and per-channel metadata the surface stage
produces and the package stage consumes.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def relative_uri(root: Path, path: Path) -> str:
    """Relative uri.

    Args:
        root: root argument.
        path: path argument.

    Returns:
        The result.
    """
    return str(path.relative_to(root)).replace("/", "\\")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _slug(value: Any, fallback: str = "chart") -> str:
    text = str(value or fallback).strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    slug = "_".join(part for part in "".join(chars).split("_") if part)
    return slug[:64] or fallback


def _stable_byte(label: str, offset: int = 0) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int(digest[offset % len(digest)])


def _tangent_normal_rgb(x: int = 128, y: int = 128) -> tuple[int, int, int]:
    nx = (max(0, min(255, int(x))) / 255.0) * 2.0 - 1.0
    ny = (max(0, min(255, int(y))) / 255.0) * 2.0 - 1.0
    radial = nx * nx + ny * ny
    if radial > 0.95:
        scale = math.sqrt(0.95 / max(radial, 1e-8))
        nx *= scale
        ny *= scale
    nz = math.sqrt(max(0.0, 1.0 - min(0.95, nx * nx + ny * ny)))
    out_x = int(round((nx * 0.5 + 0.5) * 255.0))
    out_y = int(round((ny * 0.5 + 0.5) * 255.0))
    out_z = int(round((nz * 0.5 + 0.5) * 255.0))
    return (
        max(0, min(255, out_x)),
        max(0, min(255, out_y)),
        max(0, min(255, out_z)),
    )


def _generated_chart_sidecar_maps(
    *,
    pack_dir: Path,
    out_dir: Path,
    target_size: int,
    generated_surface_charts: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = generated_surface_charts if isinstance(generated_surface_charts, dict) else {}
    bindings = payload.get("bindings", [])
    if not isinstance(bindings, list) or not bindings:
        return {}
    chart_size = max(64, min(512, int(target_size // 4) if target_size else 256))
    sidecar_dir = pack_dir / "generated_surface_charts"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, Any] = {}
    for index, raw_binding in enumerate(bindings):
        if not isinstance(raw_binding, dict):
            continue
        chart_id = str(raw_binding.get("chart_id") or f"generated_chart_{index + 1:02d}")
        chart_slug = _slug(chart_id, f"generated_chart_{index + 1:02d}")
        edge_count = max(1, int(raw_binding.get("edge_count", 0) or 1))
        uv_span_cm = max(0.0, float(raw_binding.get("uv_span_cm", 0.0) or 0.0))
        seed = _stable_byte(f"{chart_id}:{uv_span_cm}:{edge_count}") / 255.0
        trim_mask = Image.new("L", (chart_size, chart_size), 0)
        edge_wear = Image.new("L", (chart_size, chart_size), 0)
        roughness = Image.new("L", (chart_size, chart_size), 178)
        normal = Image.new("RGB", (chart_size, chart_size), (128, 128, 255))
        basecolor = Image.new("RGB", (chart_size, chart_size), (118, 120, 116))
        id_mask = Image.new("RGB", (chart_size, chart_size), (8, 8, 8))

        trim_draw = ImageDraw.Draw(trim_mask, "L")
        wear_draw = ImageDraw.Draw(edge_wear, "L")
        rough_draw = ImageDraw.Draw(roughness, "L")
        normal_draw = ImageDraw.Draw(normal, "RGB")
        base_draw = ImageDraw.Draw(basecolor, "RGB")
        id_draw = ImageDraw.Draw(id_mask, "RGB")

        y0 = int(chart_size * 0.18)
        y1 = int(chart_size * 0.82)
        trim_draw.rectangle((0, y0, chart_size - 1, y1), fill=210)
        id_color = (
            72 + _stable_byte(chart_id, 0) % 96,
            72 + _stable_byte(chart_id, 1) % 96,
            72 + _stable_byte(chart_id, 2) % 96,
        )
        id_draw.rectangle((0, y0, chart_size - 1, y1), fill=id_color)
        base_color = (
            124 + int(seed * 38.0),
            128 + int(seed * 26.0),
            126 + int(seed * 18.0),
        )
        base_draw.rectangle((0, y0, chart_size - 1, y1), fill=base_color)
        rough_draw.rectangle((0, y0, chart_size - 1, y1), fill=206)
        normal_draw.rectangle((0, y0, chart_size - 1, y1), fill=_tangent_normal_rgb())
        for edge_y, normal_y in ((y0, 104), (y1, 152)):
            trim_draw.line((0, edge_y, chart_size - 1, edge_y), fill=255, width=3)
            wear_draw.line((0, edge_y, chart_size - 1, edge_y), fill=230, width=4)
            rough_draw.line((0, edge_y, chart_size - 1, edge_y), fill=232, width=3)
            normal_draw.line(
                (0, edge_y, chart_size - 1, edge_y),
                fill=_tangent_normal_rgb(128, normal_y),
                width=3,
            )
            base_draw.line((0, edge_y, chart_size - 1, edge_y), fill=(184, 178, 164), width=2)
        notch_count = min(32, max(2, edge_count))
        step = chart_size / float(notch_count + 1)
        for notch in range(1, notch_count + 1):
            x = int(round(notch * step))
            strength = 120 + int((_stable_byte(f"{chart_id}:{notch}", 0) / 255.0) * 80.0)
            trim_draw.line((x, y0 + 3, x, y1 - 3), fill=strength, width=1)
            wear_draw.line((x, y0, x, y0 + int((y1 - y0) * 0.22)), fill=180, width=1)
            base_draw.line((x, y0 + 2, x, y1 - 2), fill=(96, 96, 90), width=1)
        records[chart_id] = {
            "chart_id": chart_id,
            "schema": "lathe.generated_surface_chart_maps.v1",
            "source": "surface_control_pack.generated_surface_charts",
            "surface_role": raw_binding.get("surface_role", ""),
            "edge_count": edge_count,
            "uv_span_cm": uv_span_cm,
            "source_uv_bounds": list(raw_binding.get("source_uv_bounds", []))
            if isinstance(raw_binding.get("source_uv_bounds"), list)
            else [],
            "source_uv_polygon": list(raw_binding.get("source_uv_polygon", []))
            if isinstance(raw_binding.get("source_uv_polygon"), list)
            else [],
            "source_uv_space": str(raw_binding.get("source_uv_space", "")),
            "images": {
                "basecolor": relative_uri(out_dir, Path(write_image(basecolor, sidecar_dir / f"{chart_slug}_basecolor.png")["uri"])),
                "normal": relative_uri(out_dir, Path(write_image(normal, sidecar_dir / f"{chart_slug}_normal.png")["uri"])),
                "roughness": relative_uri(out_dir, Path(write_image(roughness, sidecar_dir / f"{chart_slug}_roughness.png")["uri"])),
                "trim_mask": relative_uri(out_dir, Path(write_image(trim_mask, sidecar_dir / f"{chart_slug}_trim_mask.png")["uri"])),
                "edge_wear": relative_uri(out_dir, Path(write_image(edge_wear, sidecar_dir / f"{chart_slug}_edge_wear.png")["uri"])),
                "id": relative_uri(out_dir, Path(write_image(id_mask, sidecar_dir / f"{chart_slug}_id.png")["uri"])),
            },
            "paint_policy": "chart_local_generated_bevel_strip_sidecar_v1",
        }
    return records


def _generated_chart_packed_atlas(
    *,
    pack_dir: Path,
    out_dir: Path,
    target_size: int,
    chart_maps: dict[str, Any],
) -> dict[str, Any]:
    if not chart_maps:
        return {}
    chart_items = [
        (str(chart_id), record)
        for chart_id, record in sorted(chart_maps.items())
        if isinstance(record, dict) and isinstance(record.get("images"), dict)
    ]
    if not chart_items:
        return {}
    atlas_size = max(128, min(1024, int(target_size // 2) if target_size else 512))
    columns = max(1, int(math.ceil(math.sqrt(len(chart_items)))))
    rows = max(1, int(math.ceil(len(chart_items) / columns)))
    cell_w = max(1, atlas_size // columns)
    cell_h = max(1, atlas_size // rows)
    atlas_dir = pack_dir / "generated_surface_chart_atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    modes = {
        "basecolor": ("RGB", (0, 0, 0)),
        "normal": ("RGB", (128, 128, 255)),
        "roughness": ("L", 0),
        "trim_mask": ("L", 0),
        "edge_wear": ("L", 0),
        "id": ("RGB", (8, 8, 8)),
    }
    atlases = {
        name: Image.new(mode, (atlas_size, atlas_size), fill)
        for name, (mode, fill) in modes.items()
    }
    layout: dict[str, Any] = {}
    for index, (chart_id, record) in enumerate(chart_items):
        col = index % columns
        row = index // columns
        left = col * cell_w
        top = row * cell_h
        right = atlas_size if col == columns - 1 else min(atlas_size, left + cell_w)
        bottom = atlas_size if row == rows - 1 else min(atlas_size, top + cell_h)
        width = max(1, right - left)
        height = max(1, bottom - top)
        layout[chart_id] = {
            "rect_px": [left, top, right, bottom],
            "rect_uv": [
                round(left / atlas_size, 6),
                round(top / atlas_size, 6),
                round(right / atlas_size, 6),
                round(bottom / atlas_size, 6),
            ],
            "source_uv_bounds": list(record.get("source_uv_bounds", []))
            if isinstance(record.get("source_uv_bounds"), list)
            else [],
            "source_uv_polygon": list(record.get("source_uv_polygon", []))
            if isinstance(record.get("source_uv_polygon"), list)
            else [],
            "source_uv_space": str(record.get("source_uv_space", "")),
            "primary_atlas_merge_hint": {
                "strategy": "reuse_generated_bevel_strip_source_uv_bounds",
                "requires_primary_unwrap_island_insertion": True,
                "ready": bool(record.get("source_uv_bounds") or record.get("source_uv_polygon")),
            },
            "source_chart_images": dict(record.get("images", {})),
        }
        images = record.get("images", {})
        for name, atlas in atlases.items():
            image_uri = images.get(name)
            if not image_uri:
                continue
            image_path = out_dir / str(image_uri)
            if not image_path.exists():
                continue
            with Image.open(image_path) as opened:
                source = opened.convert(modes[name][0])
            atlas.paste(source.resize((width, height)), (left, top))
    atlas_images = {
        name: relative_uri(out_dir, Path(write_image(image, atlas_dir / f"{name}.png")["uri"]))
        for name, image in atlases.items()
    }
    return {
        "schema": "lathe.generated_surface_chart_atlas.v1",
        "source": "surface_control_pack.generated_surface_chart_maps",
        "packing": {
            "strategy": "deterministic_grid",
            "atlas_size_px": atlas_size,
            "columns": columns,
            "rows": rows,
            "chart_count": len(chart_items),
            "primary_atlas_merge_policy": "carry_generated_strip_source_uv_bounds_for_future_primary_xatlas_insertion",
        },
        "layout": layout,
        "images": atlas_images,
        "paint_policy": "packed_generated_bevel_strip_sidecar_atlas_v1",
    }


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
    wear_mask: Image.Image | None = None,
    material_layer_mask: Image.Image | None = None,
    uv_organization: dict[str, Any] | None = None,
    chart_manifest: list[dict[str, Any]] | None = None,
    material_id_layout: dict[str, Any] | None = None,
    generated_surface_charts: dict[str, Any] | None = None,
    surface_story_placement_plan: dict[str, Any] | None = None,
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
    if wear_mask is not None:
        outputs["wear_mask"] = write_image(wear_mask.convert("L"), pack_dir / "wear_mask.png")
    if material_layer_mask is not None:
        outputs["material_layer_mask"] = write_image(
            material_layer_mask.convert("L"), pack_dir / "material_layer_mask.png"
        )
    generated_surface_chart_maps = _generated_chart_sidecar_maps(
        pack_dir=pack_dir,
        out_dir=out_dir,
        target_size=size,
        generated_surface_charts=generated_surface_charts,
    )
    generated_surface_chart_atlas = _generated_chart_packed_atlas(
        pack_dir=pack_dir,
        out_dir=out_dir,
        target_size=size,
        chart_maps=generated_surface_chart_maps,
    )
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
                "surface_profile": entry.get("surface_profile", ""),
                "procedural_layers": _as_list(entry.get("procedural_layers")),
                "surface_features": _as_list(entry.get("surface_features")),
                "material_hints": _as_list(entry.get("material_hints")),
                "wear_layers": _as_list(entry.get("wear_layers")),
                "topology_material_zones": _as_list(entry.get("topology_material_zones")),
                "semantic_surface_role": entry.get("semantic_surface_role", ""),
                "material_source": entry.get("material_source", ""),
                "material_zone_source": entry.get("material_zone_source", ""),
                "topology_material_hint": entry.get("topology_material_hint", ""),
                "previous_material": entry.get("previous_material", ""),
            }
            for entry in material_zones
        },
        "semantic_descriptors": {
            "surface_program": source_surface.get("program", ""),
            "policy": source_surface.get("policy", ""),
            "decal_libraries": list(source_surface.get("decal_libraries", [])),
            "mask_programs": list(source_surface.get("mask_programs", [])),
            "trim_sheets": list(source_surface.get("trim_sheets", [])),
            "material_layers": [
                str(item)
                for item in _as_list(source_surface.get("material_layers") or source_surface.get("layers"))
            ],
            "wear_story": source_surface.get("wear_story", source_surface.get("usage_history", "")),
            "surface_grammar": source_surface.get("surface_grammar", {}),
        },
        "images": {name: relative_uri(out_dir, Path(entry["uri"])) for name, entry in outputs.items()},
        "map_metadata": {
            "normal_reference": {
                "space": "tangent",
                "convention": "OpenGL +Y",
                "encoding": "rgb_unit_signed_8bit",
                "neutral_rgb": list(_tangent_normal_rgb()),
                "z_policy": "renormalized_from_xy",
                "world_space_face_normal_bake": False,
            },
            "generated_surface_chart_normals": {
                "space": "tangent",
                "convention": "OpenGL +Y",
                "encoding": "rgb_unit_signed_8bit",
                "z_policy": "renormalized_from_xy",
            },
        },
    }
    if uv_organization:
        manifest["uv_organization"] = dict(uv_organization)
    if chart_manifest:
        manifest["chart_manifest"] = list(chart_manifest)
    if material_id_layout:
        manifest["material_id_layout"] = dict(material_id_layout)
    if generated_surface_charts:
        manifest["generated_surface_charts"] = dict(generated_surface_charts)
    if generated_surface_chart_maps:
        manifest["generated_surface_chart_maps"] = dict(generated_surface_chart_maps)
    if generated_surface_chart_atlas:
        manifest["generated_surface_chart_atlas"] = dict(generated_surface_chart_atlas)
    if surface_story_placement_plan:
        manifest["surface_story_placement_plan"] = dict(surface_story_placement_plan)
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "manifest_uri": relative_uri(out_dir, manifest_path),
        "images": manifest["images"],
        "required_maps": required_maps,
        "map_metadata": manifest["map_metadata"],
        "per_zone_constraints": manifest["per_zone_constraints"],
        "generated_surface_chart_maps": generated_surface_chart_maps,
        "generated_surface_chart_atlas": generated_surface_chart_atlas,
    }
