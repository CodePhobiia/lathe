"""Surface storytelling placement plans for decals and marks."""

from __future__ import annotations

import hashlib
from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _token(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return text or default


def _hash01(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") / float(2**32 - 1)


def _target_for_decal(decal: str, targets: list[str], material_zones: list[dict[str, Any]]) -> str:
    if targets:
        return targets[int(_hash01(decal) * len(targets)) % len(targets)]
    parts = [str(zone.get("part", "")) for zone in material_zones if str(zone.get("part", ""))]
    if not parts:
        return "body"
    name = decal.lower()
    preferred_tokens = (
        ("screen", "screen"),
        ("warning", "label"),
        ("label", "label"),
        ("unit", "label"),
        ("service", "panel"),
        ("calibration", "panel"),
        ("scrape", "body"),
        ("scratch", "body"),
        ("dent", "body"),
        ("chip", "edge"),
        ("grime", "body"),
        ("rune", "rune"),
        ("edge", "trim"),
        ("trim", "trim"),
    )
    for decal_token, part_token in preferred_tokens:
        if decal_token in name:
            for part in parts:
                if part_token in part.lower():
                    return part
    return parts[int(_hash01(f"target:{decal}") * len(parts)) % len(parts)]


def _anchor_for(decal: str, target: str, index: int, asymmetry: str) -> list[float]:
    seed = _hash01(f"story-placement:{target}:{decal}:{index}")
    x = 0.18 + seed * 0.58
    y = 0.16 + (1.0 - seed) * 0.56
    if asymmetry in {"left", "left_bias"}:
        x = 0.08 + x * 0.55
    elif asymmetry in {"right", "right_bias"}:
        x = 0.42 + x * 0.50
    elif asymmetry in {"asymmetric", "hero_asymmetric"}:
        x = 0.12 + ((x + index * 0.173) % 0.76)
        y = 0.12 + ((y + index * 0.119) % 0.72)
    return [round(max(0.04, min(0.94, x)), 6), round(max(0.04, min(0.94, y)), 6)]


def build_surface_story_placement_plan(
    *,
    source_surface: dict[str, Any],
    surface_cfg: dict[str, Any],
    material_zones: list[dict[str, Any]],
    material_id_layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create deterministic decal/story placement metadata from surface authoring."""
    decals = [
        str(item)
        for item in _as_list(surface_cfg.get("decals"))
        if str(item)
    ]
    explicit_targets = [
        str(item)
        for item in (
            _as_list(source_surface.get("story_targets"))
            + _as_list(source_surface.get("decal_targets"))
            + _as_list(source_surface.get("story_regions"))
        )
        if str(item)
    ]
    density = _token(source_surface.get("story_density", source_surface.get("decal_density", "")), "standard")
    asymmetry = _token(source_surface.get("story_asymmetry", source_surface.get("asymmetry", "")), "balanced")
    material_id_by_part = (
        material_id_layout.get("per_part", {})
        if isinstance(material_id_layout, dict) and isinstance(material_id_layout.get("per_part"), dict)
        else {}
    )
    zone_by_part = {str(zone.get("part", "")): zone for zone in material_zones}

    placements = []
    for index, decal in enumerate(decals):
        target = _target_for_decal(decal, explicit_targets, material_zones)
        zone = zone_by_part.get(target, {})
        material = str(zone.get("material", ""))
        anchor = _anchor_for(decal, target, index, asymmetry)
        placements.append(
            {
                "decal": decal,
                "target_part": target,
                "material": material,
                "material_id": str(material_id_by_part.get(target, "")),
                "anchor_uv": anchor,
                "scale": round(0.22 + _hash01(f"scale:{decal}:{target}") * 0.18, 6),
                "rotation_deg": int(round((_hash01(f"rot:{decal}:{target}") - 0.5) * 26.0)),
                "layer": "story" if decal in _as_list(source_surface.get("story_decals")) else "surface",
                "mask_id": f"story_{index + 1:02d}_{_token(decal, 'decal')}",
            }
        )

    return {
        "schema": "lathe.surface_story_placement.v1",
        "density": density,
        "asymmetry": asymmetry,
        "targets": explicit_targets,
        "placement_count": len(placements),
        "placements": placements,
    }
