"""UV unwrap adapters (xatlas, deterministic box).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import trimesh

from .common import unit_to_cm, unit_to_px_per_m
from .geometry import derived_lightmap_uv
from .mesh import RuntimeMesh
from ..uv_organization import build_uv_organization


_DEFAULT_PART_IMPORTANCE: tuple[tuple[str, float], ...] = (
    ("body", 0.40),
    ("hull", 0.40),
    ("shell", 0.40),
    ("lid_panel", 0.20),
    ("lid", 0.18),
    ("front_hatch", 0.10),
    ("door", 0.10),
    ("hatch", 0.10),
    ("brass_band", 0.05),
    ("band", 0.05),
    ("hinge", 0.05),
    ("handle", 0.05),
    ("foot", 0.025),
    ("leg", 0.04),
    ("lock_plate", 0.05),
    ("lock", 0.04),
    ("clasp", 0.04),
    ("rivet", 0.01),
    ("trim", 0.04),
)


def _normalize_part_token(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _kernel_semantic_weight_boost(
    manifest_entry: dict[str, Any] | None,
) -> tuple[float, dict[str, int]]:
    if not isinstance(manifest_entry, dict):
        return 0.0, {}
    metadata = manifest_entry.get("metadata")
    if not isinstance(metadata, dict):
        return 0.0, {}
    kernel_semantics = metadata.get("kernel_semantics")
    counts: dict[str, int] = {}
    if isinstance(kernel_semantics, dict):
        for field, records in kernel_semantics.items():
            if isinstance(records, list):
                counts[str(field)] = sum(1 for item in records if isinstance(item, dict))
    operation_semantics = metadata.get("operation_semantics")
    if isinstance(operation_semantics, list):
        counts["operation_semantics"] = sum(
            1 for item in operation_semantics if isinstance(item, dict)
        )
    boost = 0.0
    feature_count = counts.get("kernel_feature_details", 0)
    edge_count = counts.get("kernel_edge_treatments", 0) + counts.get("kernel_edge_controls", 0)
    pattern_count = counts.get("kernel_pattern_instances", 0) + counts.get("kernel_scatters", 0)
    operation_count = counts.get("operation_semantics", 0)
    if feature_count:
        boost += min(0.08, 0.02 * feature_count)
    if edge_count:
        boost += min(0.06, 0.02 * edge_count)
    if pattern_count:
        boost += min(0.04, 0.01 * pattern_count)
    if operation_count:
        boost += min(0.05, 0.01 * operation_count)
    return min(0.18, boost), counts


def _part_importance_weight(
    part_name: str,
    manifest_entry: dict[str, Any] | None = None,
) -> float:
    """Map a part name to a default texel-density importance weight.

    Larger weight means the part receives proportionally more atlas area
    in the shared per-part xatlas pack. Values are unnormalized — callers
    normalize across the full part set so weights end up summing to 1.0.
    """
    token = _normalize_part_token(part_name)
    semantic_boost, _counts = _kernel_semantic_weight_boost(manifest_entry)
    for needle, weight in _DEFAULT_PART_IMPORTANCE:
        if needle in token:
            return float(weight) + semantic_boost
    return 0.05 + semantic_boost


def _uv_resolution(asset: dict[str, Any], *, default: int = 2048) -> int:
    raw = asset.get("build", {}).get("uv", {}).get("resolution", default)
    if isinstance(raw, dict):
        raw = raw.get("value", default)
    return max(1, int(raw or default))


def _uv_coverage(coords: np.ndarray) -> dict[str, float]:
    return {
        "u_min": round(float(coords[:, 0].min()), 6),
        "u_max": round(float(coords[:, 0].max()), 6),
        "v_min": round(float(coords[:, 1].min()), 6),
        "v_max": round(float(coords[:, 1].max()), 6),
    }


def _units_per_meter(units: str | None) -> float:
    return {"m": 1.0, "cm": 100.0, "mm": 1000.0}.get(str(units or "cm").lower(), 100.0)


def _face_area_units(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    if len(faces) == 0:
        return np.zeros(0, dtype=np.float64)
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return np.linalg.norm(cross, axis=1) * 0.5


def _face_uv_area(uvs: np.ndarray, faces: np.ndarray) -> np.ndarray:
    if len(faces) == 0:
        return np.zeros(0, dtype=np.float64)
    tri = uvs[faces]
    a = tri[:, 1] - tri[:, 0]
    b = tri[:, 2] - tri[:, 0]
    return np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) * 0.5


def _remap_xatlas_face_parts(
    *,
    source_faces: np.ndarray,
    source_face_parts: list[str],
    mapped_faces: np.ndarray,
    vertex_mapping: np.ndarray,
) -> tuple[list[str], dict[str, Any]]:
    """Infer post-xatlas face part labels from original vertex ownership."""
    if len(source_face_parts) != len(source_faces):
        return ["mesh"] * len(mapped_faces), {
            "schema": "lathe.uv.xatlas_face_part_remap.v1",
            "method": "fallback_single_mesh_label",
            "reason": "source_face_parts_misaligned",
            "source_face_count": int(len(source_faces)),
            "source_face_part_count": int(len(source_face_parts)),
            "mapped_face_count": int(len(mapped_faces)),
            "preserved": False,
        }
    exact_by_vertices: dict[tuple[int, ...], str] = {}
    source_face_sets: list[set[int]] = []
    vertex_to_faces: dict[int, list[int]] = {}
    for face_index, face in enumerate(np.asarray(source_faces, dtype=np.int64)):
        vertices = tuple(sorted(int(value) for value in face))
        exact_by_vertices.setdefault(vertices, str(source_face_parts[face_index]))
        face_set = set(vertices)
        source_face_sets.append(face_set)
        for vertex in face_set:
            vertex_to_faces.setdefault(vertex, []).append(face_index)

    out: list[str] = []
    exact_count = 0
    overlap_count = 0
    fallback_count = 0
    vertex_mapping = np.asarray(vertex_mapping, dtype=np.int64)
    for mapped_face in np.asarray(mapped_faces, dtype=np.int64):
        if any(int(index) < 0 or int(index) >= len(vertex_mapping) for index in mapped_face):
            out.append("mesh")
            fallback_count += 1
            continue
        source_vertices = tuple(sorted(int(vertex_mapping[int(index)]) for index in mapped_face))
        exact_part = exact_by_vertices.get(source_vertices)
        if exact_part:
            out.append(exact_part)
            exact_count += 1
            continue
        candidate_scores: dict[int, int] = {}
        source_vertex_set = set(source_vertices)
        for vertex in source_vertex_set:
            for face_index in vertex_to_faces.get(vertex, []):
                candidate_scores[face_index] = len(source_vertex_set & source_face_sets[face_index])
        if candidate_scores:
            best_face, best_score = max(candidate_scores.items(), key=lambda item: item[1])
            if best_score >= 2:
                out.append(str(source_face_parts[best_face]))
                overlap_count += 1
                continue
        out.append("mesh")
        fallback_count += 1

    return out, {
        "schema": "lathe.uv.xatlas_face_part_remap.v1",
        "method": "vmapping_exact_or_majority_vertex_overlap_v1",
        "source_face_count": int(len(source_faces)),
        "mapped_face_count": int(len(mapped_faces)),
        "preserved": fallback_count == 0,
        "exact_face_count": int(exact_count),
        "overlap_face_count": int(overlap_count),
        "fallback_face_count": int(fallback_count),
        "fallback_label": "mesh",
    }


def _texel_density_audit(
    *,
    vertices: np.ndarray,
    faces: np.ndarray,
    uvs: np.ndarray,
    face_parts: list[str],
    resolution: int,
    units: str | None,
    requested_px_per_m: float | None,
) -> dict[str, Any]:
    face_count = int(len(faces))
    if face_count == 0 or len(uvs) == 0:
        return {
            "schema": "lathe.uv.texel_density_audit.v1",
            "face_count": face_count,
            "part_count": 0,
            "per_part": [],
        }
    world_area_units = _face_area_units(vertices, faces)
    uv_area_px = _face_uv_area(uvs, faces) * float(resolution * resolution)
    units_scale = _units_per_meter(units)
    part_totals: dict[str, dict[str, float]] = {}
    for index in range(face_count):
        part = face_parts[index] if index < len(face_parts) else "mesh"
        entry = part_totals.setdefault(
            str(part),
            {"world_area_m2": 0.0, "uv_area_px2": 0.0, "face_count": 0.0},
        )
        entry["world_area_m2"] += float(world_area_units[index]) / float(units_scale * units_scale)
        entry["uv_area_px2"] += float(uv_area_px[index])
        entry["face_count"] += 1.0

    per_part: list[dict[str, Any]] = []
    densities: list[float] = []
    for part, totals in sorted(part_totals.items()):
        world_area_m2 = totals["world_area_m2"]
        uv_area = totals["uv_area_px2"]
        density = (uv_area / world_area_m2) ** 0.5 if world_area_m2 > 1e-12 and uv_area > 0.0 else 0.0
        densities.append(density)
        record: dict[str, Any] = {
            "part": part,
            "face_count": int(totals["face_count"]),
            "world_area_m2": round(world_area_m2, 8),
            "uv_area_px2": round(uv_area, 6),
            "actual_px_per_m": round(density, 6),
        }
        if requested_px_per_m and requested_px_per_m > 0.0:
            record["requested_px_per_m"] = round(float(requested_px_per_m), 6)
            record["density_ratio_vs_requested"] = round(density / float(requested_px_per_m), 6)
        per_part.append(record)

    nonzero = [value for value in densities if value > 0.0]
    min_density = min(nonzero) if nonzero else 0.0
    max_density = max(nonzero) if nonzero else 0.0
    total_world_area = sum(item["world_area_m2"] for item in part_totals.values())
    total_uv_area = sum(item["uv_area_px2"] for item in part_totals.values())
    area_weighted = (
        (total_uv_area / total_world_area) ** 0.5
        if total_world_area > 1e-12 and total_uv_area > 0.0
        else 0.0
    )
    audit: dict[str, Any] = {
        "schema": "lathe.uv.texel_density_audit.v1",
        "face_count": face_count,
        "part_count": len(per_part),
        "resolution": int(resolution),
        "units": str(units or "cm"),
        "area_weighted_px_per_m": round(area_weighted, 6),
        "min_px_per_m": round(min_density, 6),
        "max_px_per_m": round(max_density, 6),
        "density_ratio": round(max_density / min_density, 6) if min_density > 0.0 else 0.0,
        "lowest_density_part": min(per_part, key=lambda item: item["actual_px_per_m"])["part"] if per_part else "",
        "highest_density_part": max(per_part, key=lambda item: item["actual_px_per_m"])["part"] if per_part else "",
        "per_part": per_part,
    }
    if requested_px_per_m and requested_px_per_m > 0.0:
        audit["requested_px_per_m"] = round(float(requested_px_per_m), 6)
        audit["area_weighted_ratio_vs_requested"] = round(area_weighted / float(requested_px_per_m), 6)
    return audit


def _direct_face_normals(face_vertices: np.ndarray) -> np.ndarray:
    normals = np.cross(face_vertices[:, 1] - face_vertices[:, 0], face_vertices[:, 2] - face_vertices[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    safe_lengths = np.where(lengths > 1e-12, lengths, 1.0)
    return normals / safe_lengths[:, None]


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
    resolution = _uv_resolution(asset)
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(unit_to_cm(padding_px)) / float(resolution))
    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    organization = build_uv_organization(
        asset,
        list(face_parts),
        resolution=resolution,
        padding_normalized=padding_norm,
        requested_sets=requested_sets,
    )
    chart_ids = [entry["chart_id"] for entry in organization["chart_manifest"]]
    cells = math.ceil(math.sqrt(max(1, len(chart_ids))))
    cell_size = 1.0 / cells
    chart_to_cell = {chart_id: (idx % cells, idx // cells) for idx, chart_id in enumerate(chart_ids)}

    source_vertices = np.asarray(mesh.vertices, dtype=np.float64)
    source_faces = np.asarray(mesh.faces, dtype=np.int64)
    source_face_vertices = source_vertices[source_faces]
    source_face_normals = _direct_face_normals(source_face_vertices)
    vertices = source_face_vertices.reshape(-1, 3)
    faces = np.arange(len(vertices), dtype=np.int64).reshape(-1, 3)
    uv = np.zeros((len(vertices), 2), dtype=np.float64)
    uv_lightmap = np.zeros((len(vertices), 2), dtype=np.float64)
    new_face_parts: list[str] = []

    for face_index, face_vertices in enumerate(source_face_vertices):
        normal = source_face_normals[face_index]
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
        chart_id = organization["part_to_chart"].get(part, chart_ids[0] if chart_ids else "uvc_01_mesh")
        cell_x, cell_y = chart_to_cell.get(chart_id, (0, 0))
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
    for name, coords in [("base", uv), ("lightmap", uv_lightmap)]:
        if name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": name,
                "coverage": _uv_coverage(coords),
                "vertex_count": len(coords),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    density_audit = _texel_density_audit(
        vertices=np.asarray(uv_mesh.vertices, dtype=np.float64),
        faces=np.asarray(uv_mesh.faces, dtype=np.int64),
        uvs=uv,
        face_parts=new_face_parts,
        resolution=resolution,
        units=runtime.units,
        requested_px_per_m=px_per_m,
    )
    actual_px_per_m = float(density_audit.get("area_weighted_px_per_m", 0.0) or 0.0)
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": len(chart_ids),
            "semantic_grouping": organization["chart_grouping"],
            "resolution": resolution,
            "cells": cells,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
        },
        "texel_density": {
            "requested_px_per_m": px_per_m,
            "actual_px_per_m": round(actual_px_per_m, 6),
            "audit": density_audit,
        },
        "uv_organization": {
            key: value
            for key, value in organization.items()
            if key not in {"chart_manifest", "material_id_layout"}
        },
        "chart_manifest": organization["chart_manifest"],
        "material_id_layout": organization["material_id_layout"],
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
    source_visual_uv = getattr(mesh.visual, "uv", None)
    generated_source_uv_remap: dict[str, Any] = {
        "available": False,
        "source": "input_mesh_visual_uv",
        "preservation": "none",
    }
    if source_visual_uv is not None and len(source_visual_uv) == len(mesh.vertices):
        source_uv = np.asarray(source_visual_uv, dtype=np.float64)
        mapped_source_uv = source_uv[np.asarray(vmapping, dtype=np.int64)]
        generated_source_uv_remap = {
            "available": True,
            "source": "input_mesh_visual_uv",
            "preservation": "xatlas_vmapping_source_uv_sidecar_v1",
            "source_vertex_count": int(len(source_uv)),
            "mapped_vertex_count": int(len(mapped_source_uv)),
            "coverage": _uv_coverage(mapped_source_uv),
        }

    lightmap_uv = derived_lightmap_uv(base_uv)
    uv_mesh = trimesh.Trimesh(vertices=mapped_vertices, faces=mapped_faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=base_uv)
    face_parts, face_part_remap = _remap_xatlas_face_parts(
        source_faces=faces,
        source_face_parts=list(runtime_mesh.face_parts),
        mapped_faces=mapped_faces,
        vertex_mapping=np.asarray(vmapping, dtype=np.int64),
    )
    runtime = RuntimeMesh(
        mesh=uv_mesh, face_parts=face_parts, part_colors=runtime_mesh.part_colors, units=runtime_mesh.units
    )

    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    resolution = int(((runtime_config or {}).get("uv", {}).get("xatlas", {}) or {}).get("resolution", 2048))
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(unit_to_cm(padding_px)) / max(1.0, float(resolution)))
    organization = build_uv_organization(
        asset,
        face_parts,
        resolution=resolution,
        padding_normalized=padding_norm,
        requested_sets=requested_sets,
    )
    uv_sets = []
    for name, coords in [("base", base_uv), ("lightmap", lightmap_uv)]:
        if name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": name,
                "coverage": _uv_coverage(coords),
                "vertex_count": len(coords),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    density_audit = _texel_density_audit(
        vertices=np.asarray(uv_mesh.vertices, dtype=np.float64),
        faces=np.asarray(uv_mesh.faces, dtype=np.int64),
        uvs=base_uv,
        face_parts=face_parts,
        resolution=resolution,
        units=runtime.units,
        requested_px_per_m=px_per_m,
    )
    actual_px_per_m = float(density_audit.get("area_weighted_px_per_m", 0.0) or 0.0)
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": max(1, len(set(face_parts))),
            "semantic_chart_count": organization["chart_count"],
            "semantic_grouping": organization["chart_grouping"],
            "resolution": resolution,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
            "generated_source_uv_remap": dict(generated_source_uv_remap),
            "face_part_remap": dict(face_part_remap),
        },
        "texel_density": {
            "requested_px_per_m": px_per_m,
            "actual_px_per_m": round(actual_px_per_m, 6),
            "audit": density_audit,
        },
        "uv_organization": {
            key: value
            for key, value in organization.items()
            if key not in {"chart_manifest", "material_id_layout"}
        },
        "chart_manifest": organization["chart_manifest"],
        "material_id_layout": organization["material_id_layout"],
    }
    execution = {
        "mode": "xatlas",
        "resolution": resolution,
        "lightmap_strategy": "derived_inset",
        "vertex_count": len(mapped_vertices),
        "triangle_count": len(mapped_faces),
        "generated_source_uv_remap": dict(generated_source_uv_remap),
    }
    return runtime, meta, execution


def _split_runtime_mesh_by_part(
    runtime_mesh: RuntimeMesh,
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Partition a RuntimeMesh into ``(part_name, vertices, faces)`` triples.

    Each partition is a self-contained mesh with vertices remapped so
    indices start at zero. Vertex order within a part is preserved by
    appearance in the source faces. Parts with no faces are skipped.
    """
    mesh = runtime_mesh.mesh
    face_parts = list(runtime_mesh.face_parts)
    if len(face_parts) != len(mesh.faces):
        return []
    src_vertices = np.asarray(mesh.vertices, dtype=np.float64)
    src_faces = np.asarray(mesh.faces, dtype=np.int64)

    by_part: dict[str, list[int]] = {}
    for face_idx, part in enumerate(face_parts):
        by_part.setdefault(part, []).append(face_idx)

    out: list[tuple[str, np.ndarray, np.ndarray]] = []
    for part in sorted(by_part):
        face_indices = np.asarray(by_part[part], dtype=np.int64)
        if face_indices.size == 0:
            continue
        sub_faces = src_faces[face_indices]
        unique_verts, inverse = np.unique(sub_faces.reshape(-1), return_inverse=True)
        local_faces = inverse.reshape(sub_faces.shape).astype(np.int64)
        local_vertices = src_vertices[unique_verts]
        out.append((part, local_vertices, local_faces))
    return out


def _split_multi_part_scene(
    multi_part_scene: Any,
) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], list[dict[str, Any]]]:
    """Partition a ``MultiPartScene`` into per-part triples + manifest dicts.

    Iterates the scene's manifest in declared order so part identity matches
    the topology contract (blueprint component order). Returns parts
    parallel to the manifest entries; parts whose geometry has zero faces
    or is missing from ``scene.geometry`` are dropped from both lists.
    """
    parts: list[tuple[str, np.ndarray, np.ndarray]] = []
    manifest_entries: list[dict[str, Any]] = []
    geometry = getattr(getattr(multi_part_scene, "scene", None), "geometry", None)
    manifest = getattr(multi_part_scene, "manifest", None)
    if not isinstance(geometry, dict) or not manifest:
        return parts, manifest_entries
    for entry in manifest:
        name = getattr(entry, "name", None)
        if not name:
            continue
        geom = geometry.get(name)
        if not isinstance(geom, trimesh.Trimesh):
            continue
        if len(geom.faces) == 0:
            continue
        local_vertices = np.asarray(geom.vertices, dtype=np.float64)
        local_faces = np.asarray(geom.faces, dtype=np.int64)
        parts.append((str(name), local_vertices, local_faces))
        as_dict = entry.as_dict() if hasattr(entry, "as_dict") else {"name": str(name)}
        manifest_entries.append(as_dict)
    return parts, manifest_entries


def apply_xatlas_uv_per_part(
    runtime_mesh: RuntimeMesh,
    asset: dict[str, Any],
    runtime_config: dict[str, Any] | None,
    multi_part_scene: Any = None,
) -> tuple[RuntimeMesh, dict[str, Any], dict[str, Any]]:
    """Per-part xatlas unwrap with shared-atlas packing and importance weights.

    Each named part runs xatlas independently to get its own UV islands,
    then all parts share a single packed atlas via the multi-mesh
    ``xatlas.Atlas`` API. Importance weights bias atlas area allocation
    so hero parts (body shell, lid panel) get more texel density than
    decorative parts (rivets, feet). Output preserves named-part
    identity through ``face_parts`` and the per-part UV islands report.

    When ``multi_part_scene`` (a :class:`lathe.topology_runtime.MultiPartScene`)
    is provided, parts are taken from the scene's manifest in declared order
    and per-part manifest tags are surfaced in ``per_part_islands``. Without
    it the function falls back to partitioning ``runtime_mesh.face_parts``.
    """
    try:
        import xatlas
    except (ImportError, OSError, RuntimeError) as exc:
        raise RuntimeError(f"xatlas is unavailable: {exc}") from exc

    manifest_entries: list[dict[str, Any]] = []
    parts: list[tuple[str, np.ndarray, np.ndarray]] = []
    part_source = "runtime_mesh_face_parts"
    if multi_part_scene is not None:
        parts, manifest_entries = _split_multi_part_scene(multi_part_scene)
        if parts:
            part_source = "multi_part_scene"
    if not parts:
        parts = _split_runtime_mesh_by_part(runtime_mesh)
        manifest_entries = [{"name": name} for name, _, _ in parts]
    if len(parts) <= 1:
        # Single part: defer to the merged-mesh fast path for backwards compat.
        return apply_xatlas_uv(runtime_mesh, asset, runtime_config)

    raw_weights: list[float] = [
        _part_importance_weight(
            name,
            manifest_entries[index] if index < len(manifest_entries) else None,
        )
        for index, (name, _, _) in enumerate(parts)
    ]
    total_weight = float(sum(raw_weights)) or 1.0
    norm_weights = [w / total_weight for w in raw_weights]

    surface_areas: list[float] = []
    for _, vertices, faces in parts:
        v = vertices[faces]
        cross = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        area = float(np.linalg.norm(cross, axis=1).sum() * 0.5)
        surface_areas.append(max(area, 1e-9))

    # Add UNSCALED vertices: a uniform global texels_per_unit on the pack
    # options gives every chart the same world->texel ratio, which is the
    # industry hero standard (e.g. 1024 px/m +/- 25%). Importance weights
    # are still surfaced as telemetry in per_part_islands but no longer
    # warp the UV scale.
    atlas = xatlas.Atlas()
    for _name, vertices, faces in parts:
        atlas.add_mesh(vertices.astype(np.float32), faces.astype(np.uint32))

    chart_options = xatlas.ChartOptions()
    pack_options = xatlas.PackOptions()
    resolution = int(((runtime_config or {}).get("uv", {}).get("xatlas", {}) or {}).get("resolution", 2048))
    pack_options.resolution = resolution
    pack_options.rotate_charts = bool(asset["build"]["uv"].get("pack_rotate", True))
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(unit_to_cm(padding_px)) / max(1.0, float(resolution)))
    pack_options.padding = max(1, int(round(padding_norm * resolution)))
    texel_density_request = asset.get("build", {}).get("uv", {}).get("texel_density")
    if texel_density_request is not None:
        try:
            target_px_per_m = float(unit_to_px_per_m(texel_density_request))
        except (TypeError, ValueError):
            target_px_per_m = 1024.0
    else:
        target_px_per_m = 1024.0
    # xatlas's pack_options.texels_per_unit is in MESH UNITS, but
    # ``target_px_per_m`` is px-per-meter. Lathe runtime meshes ship in cm
    # by default (``RuntimeMesh.units = "cm"``) — passing the px/m value
    # directly tells xatlas to allocate 100x the texel demand, which spills
    # to many atlas pages and explodes pack runtime (~19 min on chest at
    # 1024 px/m). Scale by the unit factor so 1024 px/m on a cm mesh
    # becomes 10.24 texels/unit, matching the requested world density.
    units = (getattr(runtime_mesh, "units", "cm") or "cm").lower()
    units_per_meter = {"m": 1.0, "cm": 100.0, "mm": 1000.0}.get(units, 100.0)
    pack_options.texels_per_unit = target_px_per_m / units_per_meter
    atlas.generate(chart_options=chart_options, pack_options=pack_options, verbose=False)

    out_vertices_chunks: list[np.ndarray] = []
    out_faces_chunks: list[np.ndarray] = []
    out_uv_chunks: list[np.ndarray] = []
    out_face_parts: list[str] = []
    per_part_islands: list[dict[str, Any]] = []
    vertex_offset = 0

    for index, (name, vertices, _faces) in enumerate(parts):
        vmapping, indices, uvs = atlas.get_mesh(index)
        vmap = np.asarray(vmapping, dtype=np.int64)
        idx = np.asarray(indices, dtype=np.int64)
        part_uv = np.asarray(uvs, dtype=np.float64)
        # vmapping indexes the per-part input vertices, so restore unscaled
        # positions by indexing the part's source vertices (not the scaled).
        mapped_verts = vertices[vmap]
        mapped_faces = idx.reshape(-1, 3) + vertex_offset

        out_vertices_chunks.append(mapped_verts)
        out_faces_chunks.append(mapped_faces.astype(np.int64))
        out_uv_chunks.append(part_uv)
        out_face_parts.extend([name] * len(mapped_faces))
        bounds = (
            _uv_coverage(part_uv) if len(part_uv) else
            {"u_min": 0.0, "u_max": 0.0, "v_min": 0.0, "v_max": 0.0}
        )
        manifest_entry = manifest_entries[index] if index < len(manifest_entries) else {}
        semantic_boost, kernel_semantic_counts = _kernel_semantic_weight_boost(
            manifest_entry if isinstance(manifest_entry, dict) else None
        )
        island_record: dict[str, Any] = {
            "part": name,
            "importance_weight": round(norm_weights[index], 6),
            "raw_weight": round(raw_weights[index], 6),
            "semantic_weight_boost": round(semantic_boost, 6),
            "surface_area": round(surface_areas[index], 6),
            "vertex_count": int(len(mapped_verts)),
            "triangle_count": int(len(mapped_faces)),
            "uv_bounds": bounds,
            "uv_island_chart_count": int(atlas.get_mesh_chart_count(index)),
        }
        if kernel_semantic_counts:
            island_record["kernel_semantic_counts"] = dict(sorted(kernel_semantic_counts.items()))
        manifest_tags = manifest_entry.get("tags") if isinstance(manifest_entry, dict) else None
        if isinstance(manifest_tags, list) and manifest_tags:
            island_record["tags"] = list(manifest_tags)
        parent_component = (
            manifest_entry.get("parent_blueprint_component")
            if isinstance(manifest_entry, dict)
            else None
        )
        if parent_component:
            island_record["parent_blueprint_component"] = str(parent_component)
        per_part_islands.append(island_record)
        vertex_offset += len(mapped_verts)

    if not out_vertices_chunks:
        # Defensive: fall back to merged-mesh path if the partition collapsed.
        return apply_xatlas_uv(runtime_mesh, asset, runtime_config)

    mapped_vertices = np.concatenate(out_vertices_chunks, axis=0)
    mapped_faces = np.concatenate(out_faces_chunks, axis=0)
    base_uv = np.concatenate(out_uv_chunks, axis=0)
    lightmap_uv = derived_lightmap_uv(base_uv)

    uv_mesh = trimesh.Trimesh(vertices=mapped_vertices, faces=mapped_faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=base_uv)
    runtime = RuntimeMesh(
        mesh=uv_mesh,
        face_parts=out_face_parts,
        part_colors=dict(runtime_mesh.part_colors),
        units=runtime_mesh.units,
    )

    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    organization = build_uv_organization(
        asset,
        out_face_parts,
        resolution=resolution,
        padding_normalized=padding_norm,
        requested_sets=requested_sets,
    )
    uv_sets = []
    for set_name, coords in [("base", base_uv), ("lightmap", lightmap_uv)]:
        if set_name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": set_name,
                "coverage": _uv_coverage(coords),
                "vertex_count": len(coords),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    utilization_value: float | None
    try:
        utilization_value = float(atlas.utilization)
    except (AttributeError, TypeError, ValueError):
        utilization_value = None
    density_audit = _texel_density_audit(
        vertices=np.asarray(uv_mesh.vertices, dtype=np.float64),
        faces=np.asarray(uv_mesh.faces, dtype=np.int64),
        uvs=base_uv,
        face_parts=out_face_parts,
        resolution=resolution,
        units=runtime.units,
        requested_px_per_m=px_per_m,
    )
    actual_px_per_m = float(density_audit.get("area_weighted_px_per_m", 0.0) or 0.0)
    density_by_part = {
        str(record.get("part") or ""): record
        for record in density_audit.get("per_part", [])
        if isinstance(record, dict)
    }
    for island_record in per_part_islands:
        part_density = density_by_part.get(str(island_record.get("part") or ""))
        if part_density:
            island_record["actual_px_per_m"] = part_density.get("actual_px_per_m")
            if "density_ratio_vs_requested" in part_density:
                island_record["density_ratio_vs_requested"] = part_density["density_ratio_vs_requested"]

    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": int(atlas.chart_count),
            "atlas_count": int(atlas.atlas_count),
            "per_part_chart_count": int(len(parts)),
            "semantic_chart_count": organization["chart_count"],
            "semantic_grouping": organization["chart_grouping"],
            "resolution": resolution,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
            "utilization": utilization_value,
            "per_part_islands": per_part_islands,
            "part_source": part_source,
            "generated_source_uv_remap": {
                "available": False,
                "source": "input_mesh_visual_uv",
                "preservation": "per_part_xatlas_v1",
            },
        },
        "texel_density": {
            "requested_px_per_m": px_per_m,
            "actual_px_per_m": round(actual_px_per_m, 6),
            "audit": density_audit,
        },
        "uv_organization": {
            key: value
            for key, value in organization.items()
            if key not in {"chart_manifest", "material_id_layout"}
        },
        "chart_manifest": organization["chart_manifest"],
        "material_id_layout": organization["material_id_layout"],
    }
    execution = {
        "mode": "xatlas_per_part",
        "resolution": resolution,
        "part_count": len(parts),
        "part_source": part_source,
        "lightmap_strategy": "derived_inset",
        "vertex_count": len(mapped_vertices),
        "triangle_count": len(mapped_faces),
        "utilization": utilization_value,
        "per_part_islands": per_part_islands,
    }
    return runtime, meta, execution
