"""Plan-to-bpy adapter for the Blender execution stage.

Translates the JSON execution plan into concrete ``bpy`` operations
(imports, modifiers, bakes, renders) inside the Blender driver.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def _hash_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unit_px(value: Any, default: int) -> int:
    if isinstance(value, dict) and value.get("type") == "unit" and value.get("unit") == "px":
        return int(value.get("value", default))
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _canonical_backends(execution: dict[str, Any], backend_ids: dict[str, Any]) -> dict[str, Any]:
    return {
        "geometry_backend": backend_ids["geometry_backend"].get(str(execution.get("geometry_backend", "")), ""),
        "topology_backend": backend_ids["topology_backend"],
        "uv_backend": backend_ids["uv_backend"].get(str(execution.get("uv_backend", "")), ""),
        "bake_backend": backend_ids["bake_backend"].get(str(execution.get("bake_backend", "")), ""),
        "surface_backend": backend_ids["surface_backend"].get(str(execution.get("surface_backend", "")), ""),
        "render_backend": backend_ids["render_backend"].get(str(execution.get("render_backend", "")), ""),
        "package_backend": backend_ids["package_backend"].get(str(execution.get("package_backend", "")), ""),
        "library_backend": backend_ids["library_backend"].get(str(execution.get("library_backend", "")), ""),
    }


def _resolve_render_fixture(asset: dict[str, Any]) -> dict[str, Any]:
    fixture = dict(asset.get("build", {}).get("surface", {}).get("resolved_render_fixture", {}).get("values", {}))
    if not fixture:
        fixture = {
            "views": ["front_34", "front", "side", "rear_34"],
            "shading": "studio_neutral",
            "passes": ["beauty", "normal", "depth"],
            "resolution": {"type": "unit", "value": 1024, "unit": "px"},
        }
    return fixture


def _resolve_bake_profile(asset: dict[str, Any]) -> dict[str, Any]:
    profile = dict(asset.get("build", {}).get("surface", {}).get("resolved_bake_profile", {}).get("values", {}))
    if not profile:
        profile = {
            "maps": list(asset.get("build", {}).get("surface", {}).get("bakes", [])),
            "target_resolution": asset.get("build", {}).get("surface", {}).get("resolution"),
            "normal_space": "tangent",
            "require_highlow": True,
        }
    return profile


def _planned_node_groups(asset: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for component in asset.get("assembly", {}).get("components", []):
        names.append(f"gn_{component}")
    for mechanism in asset.get("assembly", {}).get("mechanisms", []):
        names.append(f"gn_{mechanism}")
    for pattern in asset.get("surface", {}).get("patterns", []):
        names.append(f"mat_{pattern}")
    return names


def _planned_materials(asset: dict[str, Any]) -> list[str]:
    materials = list(asset.get("surface", {}).get("materials", []))
    material_graph = asset.get("surface", {}).get("material_graph", "")
    if material_graph:
        materials.append(material_graph)
    return sorted(dict.fromkeys(materials))
