"""UV unwrap adapters (xatlas, deterministic box).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh

from .common import unit_to_cm, unit_to_px_per_m
from .geometry import derived_lightmap_uv
from .mesh import RuntimeMesh


def _uv_resolution(asset: dict[str, Any], *, default: int = 2048) -> int:
    raw = asset.get("build", {}).get("uv", {}).get("resolution", default)
    if isinstance(raw, dict):
        raw = raw.get("value", default)
    return max(1, int(raw or default))


def apply_box_uv(runtime_mesh: RuntimeMesh, asset: dict[str, Any]) -> tuple[RuntimeMesh, dict[str, Any]]:
    """Apply box uv.

    Args:
        runtime_mesh: runtime_mesh argument.
        asset: asset argument.

    Returns:
        The result.
    """
    mesh = runtime_mesh.mesh
    face_parts = runtime_mesh.face_parts
    unique_parts = sorted(set(face_parts))
    cells = math.ceil(math.sqrt(max(1, len(unique_parts))))
    cell_size = 1.0 / cells
    resolution = _uv_resolution(asset)
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(unit_to_cm(padding_px)) / float(resolution))
    part_to_cell = {part: (idx % cells, idx // cells) for idx, part in enumerate(unique_parts)}

    vertices = mesh.vertices[mesh.faces].reshape(-1, 3)
    faces = np.arange(len(vertices), dtype=np.int64).reshape(-1, 3)
    uv = np.zeros((len(vertices), 2), dtype=np.float64)
    uv_lightmap = np.zeros((len(vertices), 2), dtype=np.float64)
    new_face_parts: list[str] = []

    for face_index, face in enumerate(mesh.faces):
        face_vertices = mesh.vertices[face]
        normal = mesh.face_normals[face_index]
        abs_normal = np.abs(normal)
        if abs_normal[1] >= abs_normal[0] and abs_normal[1] >= abs_normal[2]:
            projected = face_vertices[:, [0, 2]]
        elif abs_normal[0] >= abs_normal[2]:
            projected = face_vertices[:, [2, 1]]
        else:
            projected = face_vertices[:, [0, 1]]
        mins = projected.min(axis=0)
        maxs = projected.max(axis=0)
        span = np.maximum(maxs - mins, 1e-6)
        local = (projected - mins) / span
        part = face_parts[face_index]
        cell_x, cell_y = part_to_cell[part]
        u0 = cell_x * cell_size + padding_norm * cell_size
        v0 = cell_y * cell_size + padding_norm * cell_size
        usable = cell_size * (1.0 - 2.0 * padding_norm)
        tri_uv = np.column_stack((u0 + local[:, 0] * usable, v0 + local[:, 1] * usable))
        tri_uv_lightmap = np.column_stack(
            (u0 + 0.05 * usable + local[:, 0] * usable * 0.9, v0 + 0.05 * usable + local[:, 1] * usable * 0.9)
        )
        base = face_index * 3
        uv[base : base + 3] = tri_uv
        uv_lightmap[base : base + 3] = tri_uv_lightmap
        new_face_parts.append(part)

    uv_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv)
    runtime = RuntimeMesh(
        mesh=uv_mesh,
        face_parts=new_face_parts,
        part_colors=runtime_mesh.part_colors,
        units=runtime_mesh.units,
    )

    uv_sets = []
    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    for name, coords in [("base", uv), ("lightmap", uv_lightmap)]:
        if name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": name,
                "coverage": {
                    "u_min": round(float(coords[:, 0].min()), 6),
                    "u_max": round(float(coords[:, 0].max()), 6),
                    "v_min": round(float(coords[:, 1].min()), 6),
                    "v_max": round(float(coords[:, 1].max()), 6),
                },
                "vertex_count": len(coords),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": len(unique_parts),
            "resolution": resolution,
            "cells": cells,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
        },
        "texel_density": {"requested_px_per_m": px_per_m, "actual_px_per_m": px_per_m},
    }
    return runtime, meta


def apply_xatlas_uv(
    runtime_mesh: RuntimeMesh, asset: dict[str, Any], runtime_config: dict[str, Any] | None
) -> tuple[RuntimeMesh, dict[str, Any], dict[str, Any]]:
    """Apply xatlas uv.

    Args:
        runtime_mesh: runtime_mesh argument.
        asset: asset argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    try:
        import xatlas
    except (ImportError, OSError, RuntimeError) as exc:
        # xatlas is a compiled C extension; import surfaces ImportError when
        # missing and OSError when the native library fails to load.
        raise RuntimeError(f"xatlas is unavailable: {exc}") from exc

    mesh = runtime_mesh.mesh
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32)
    vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
    mapped_vertices = vertices[np.asarray(vmapping, dtype=np.int64)]
    mapped_faces = np.asarray(indices, dtype=np.int64)
    base_uv = np.asarray(uvs, dtype=np.float64)

    lightmap_uv = derived_lightmap_uv(base_uv)
    uv_mesh = trimesh.Trimesh(vertices=mapped_vertices, faces=mapped_faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=base_uv)
    face_parts = (
        list(runtime_mesh.face_parts)
        if len(runtime_mesh.face_parts) == len(mesh.faces)
        else ["mesh"] * len(mapped_faces)
    )
    runtime = RuntimeMesh(
        mesh=uv_mesh, face_parts=face_parts, part_colors=runtime_mesh.part_colors, units=runtime_mesh.units
    )

    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    uv_sets = []
    for name, coords in [("base", base_uv), ("lightmap", lightmap_uv)]:
        if name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": name,
                "coverage": {
                    "u_min": round(float(coords[:, 0].min()), 6),
                    "u_max": round(float(coords[:, 0].max()), 6),
                    "v_min": round(float(coords[:, 1].min()), 6),
                    "v_max": round(float(coords[:, 1].max()), 6),
                },
                "vertex_count": len(coords),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    resolution = int(((runtime_config or {}).get("uv", {}).get("xatlas", {}) or {}).get("resolution", 2048))
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(unit_to_cm(padding_px)) / max(1.0, float(resolution)))
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": max(1, len(set(face_parts))),
            "resolution": resolution,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
        },
        "texel_density": {"requested_px_per_m": px_per_m, "actual_px_per_m": px_per_m},
    }
    execution = {
        "mode": "xatlas",
        "resolution": resolution,
        "lightmap_strategy": "derived_inset",
        "vertex_count": len(mapped_vertices),
        "triangle_count": len(mapped_faces),
    }
    return runtime, meta, execution
