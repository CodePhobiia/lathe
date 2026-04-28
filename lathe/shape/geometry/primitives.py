"""Primitive geometry factories and unit/scale helpers for the shape stage."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import trimesh

from ...mesh_ingest import safe_load_mesh

SUPPORTED_MESH_EXTS = {".glb", ".gltf", ".obj", ".ply", ".stl", ".off"}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _unit_to_cm(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "mm":
        return amount / 10.0
    if unit == "cm":
        return amount
    if unit == "m":
        return amount * 100.0
    return amount


def _characteristic_scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    if (
        "dimensions" in intent
        and isinstance(intent["dimensions"], dict)
        and intent["dimensions"].get("type") == "call"
    ):
        args = intent["dimensions"].get("args", [])
        values = [
            _unit_to_cm(item["value"])
            for item in args
            if isinstance(item, dict) and item.get("value") is not None
        ]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, _unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def _translated_box(extents: Iterable[float], center: Iterable[float]) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def _translated_cylinder(
    radius: float, height: float, center: Iterable[float], axis: str = "y"
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=24)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


def _load_mesh_file(path) -> trimesh.Trimesh | None:
    loaded = safe_load_mesh(path)
    if len(loaded.faces) == 0 or len(loaded.vertices) == 0:
        return None
    return loaded.copy()


def _normalize_mesh_to_scale(mesh: trimesh.Trimesh, target_extent_cm: float) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0
    mesh.apply_translation(-center)
    extents = mesh.extents
    max_extent = max(1e-6, float(max(extents)))
    mesh.apply_scale(float(target_extent_cm) / max_extent)
    return mesh
