"""Semantic UV chart and material-ID organization helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .materials import assign_material_zones

_OFF = {"", "none", "off", "false", "0"}


def _token(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return text or default


def _slug(value: Any, default: str = "group") -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", _token(value, default)).strip("_")
    return text or default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _stable_color(index: int) -> list[int]:
    palette = (
        (216, 74, 72),
        (74, 137, 220),
        (88, 178, 120),
        (231, 168, 64),
        (145, 101, 205),
        (68, 190, 190),
        (226, 101, 167),
        (154, 154, 70),
    )
    base = palette[index % len(palette)]
    cycle = index // len(palette)
    if cycle == 0:
        return list(base)
    return [max(32, min(239, channel - cycle * 19)) for channel in base]


def _surface_id_map_requested(asset: dict[str, Any]) -> bool:
    surface_cfg = asset.get("build", {}).get("surface", {})
    if not isinstance(surface_cfg, dict):
        return False
    return bool(surface_cfg.get("id_map", False))


def uv_organization_controls(asset: dict[str, Any]) -> dict[str, Any]:
    """Resolve additive UV/material-ID organization controls from an asset."""
    uv_cfg = asset.get("build", {}).get("uv", {})
    if not isinstance(uv_cfg, dict):
        uv_cfg = {}
    surface_cfg = asset.get("build", {}).get("surface", {})
    if not isinstance(surface_cfg, dict):
        surface_cfg = {}

    chart_grouping = _token(
        uv_cfg.get("chart_grouping", uv_cfg.get("island_grouping", uv_cfg.get("layout_grouping"))),
        "part",
    )
    if chart_grouping in _OFF:
        chart_grouping = "part"
    if chart_grouping not in {
        "part",
        "material",
        "material_zone",
        "part_material",
        "detail_zone",
        "zone",
    }:
        chart_grouping = "part"

    material_id_strategy = _token(
        uv_cfg.get(
            "material_id_strategy",
            surface_cfg.get("material_id_strategy", "per_material_zone" if _surface_id_map_requested(asset) else ""),
        ),
        "",
    )
    if material_id_strategy in _OFF:
        material_id_strategy = "none"

    texture_set_strategy = _token(
        uv_cfg.get("texture_set_strategy", surface_cfg.get("texture_set_strategy", "")),
        "",
    )
    layout_strategy = _token(uv_cfg.get("layout_strategy", uv_cfg.get("atlas_layout", "")), "box_grid")
    island_naming = _token(uv_cfg.get("island_naming", ""), "semantic")
    preserve_detail_zones = bool(uv_cfg.get("preserve_detail_zones", False))

    active = any(
        key in uv_cfg
        for key in (
            "chart_grouping",
            "island_grouping",
            "layout_grouping",
            "material_id_strategy",
            "texture_set_strategy",
            "layout_strategy",
            "atlas_layout",
            "island_naming",
            "preserve_detail_zones",
        )
    ) or material_id_strategy != "none"

    return {
        "active": active,
        "chart_grouping": chart_grouping,
        "material_id_strategy": material_id_strategy,
        "texture_set_strategy": texture_set_strategy,
        "layout_strategy": layout_strategy,
        "island_naming": island_naming,
        "preserve_detail_zones": preserve_detail_zones,
    }


def build_uv_organization(
    asset: dict[str, Any],
    face_parts: list[str],
    *,
    resolution: int,
    padding_normalized: float,
    requested_sets: list[str],
) -> dict[str, Any]:
    """Build semantic chart and material-ID metadata for a UV unwrap."""
    controls = uv_organization_controls(asset)
    part_names = sorted(set(face_parts)) or ["mesh"]
    zones = assign_material_zones(asset, part_names)
    zone_by_part = {entry["part"]: entry for entry in zones}
    detail_zones = {str(item) for item in _as_list(asset.get("build", {}).get("shape", {}).get("detail_zones"))}
    chart_grouping = controls["chart_grouping"]

    grouped_parts: dict[str, list[str]] = defaultdict(list)
    group_materials: dict[str, set[str]] = defaultdict(set)
    for part in part_names:
        material = str(zone_by_part.get(part, {}).get("material", "default_body"))
        if chart_grouping in {"material", "material_zone"}:
            group_key = material
        elif chart_grouping == "part_material":
            group_key = f"{part}_{material}"
        elif chart_grouping in {"detail_zone", "zone"}:
            group_key = part if part in detail_zones else f"base_{material}"
        else:
            group_key = part
        grouped_parts[group_key].append(part)
        group_materials[group_key].add(material)

    material_to_parts: dict[str, list[str]] = defaultdict(list)
    for part in part_names:
        material = str(zone_by_part.get(part, {}).get("material", "default_body"))
        material_to_parts[material].append(part)

    material_entries = []
    material_id_by_material: dict[str, str] = {}
    if controls["material_id_strategy"] != "none":
        for index, material in enumerate(sorted(material_to_parts)):
            material_id = f"matid_{index + 1:02d}_{_slug(material, 'material')}"
            material_id_by_material[material] = material_id
            material_entries.append(
                {
                    "material_id": material_id,
                    "material": material,
                    "parts": sorted(material_to_parts[material]),
                    "rgb": _stable_color(index),
                }
            )

    chart_manifest = []
    part_to_chart: dict[str, str] = {}
    for index, group_key in enumerate(sorted(grouped_parts)):
        parts = sorted(grouped_parts[group_key])
        materials = sorted(group_materials[group_key])
        material = materials[0] if len(materials) == 1 else ""
        chart_id = f"uvc_{index + 1:02d}_{_slug(group_key)}"
        for part in parts:
            part_to_chart[part] = chart_id
        chart_manifest.append(
            {
                "chart_id": chart_id,
                "group": group_key,
                "grouping": chart_grouping,
                "island_name": f"{controls['island_naming']}_{_slug(group_key)}",
                "parts": parts,
                "material": material,
                "material_id": material_id_by_material.get(material, ""),
                "uv_sets": list(requested_sets),
                "texel_density_scale": 1.15 if any(part in detail_zones for part in parts) else 1.0,
            }
        )

    per_part_material_id = {
        part: material_id_by_material.get(str(zone_by_part.get(part, {}).get("material", "")), "")
        for part in part_names
    }
    material_id_layout = {
        "schema": "lathe.material_id_layout.v1",
        "strategy": controls["material_id_strategy"],
        "texture_set_strategy": controls["texture_set_strategy"],
        "count": len(material_entries),
        "ids": material_entries,
        "per_part": per_part_material_id,
    }

    return {
        "schema": "lathe.uv_organization.v1",
        **controls,
        "resolution": int(resolution),
        "padding_normalized": round(float(padding_normalized), 6),
        "requested_sets": list(requested_sets),
        "chart_count": len(chart_manifest),
        "material_id_count": len(material_entries),
        "part_to_chart": part_to_chart,
        "chart_manifest": chart_manifest,
        "material_id_layout": material_id_layout,
    }
