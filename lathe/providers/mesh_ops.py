"""Mesh utilities used by shape-provider adapters.

These helpers don't talk to any provider; they operate on in-memory
``trimesh.Trimesh`` objects and asset-metadata dicts.  Kept in their own
module so the adapter packages can import them without pulling in provider
configuration or network code.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from ..mesh_ingest import safe_load_mesh
from .errors import ShapeMeshLoadError, ShapeProviderExecutionError


logger = logging.getLogger(__name__)


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
    if "dimensions" in intent and isinstance(intent["dimensions"], dict) and intent["dimensions"].get("type") == "call":
        args = intent["dimensions"].get("args", [])
        values = [_unit_to_cm(item["value"]) for item in args if isinstance(item, dict) and item.get("value") is not None]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, _unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def _make_color(name: str) -> tuple[int, int, int]:
    digest = np.frombuffer(np.frombuffer(name.encode("utf-8"), dtype=np.uint8).tobytes(), dtype=np.uint8)
    total = int(digest.sum()) if len(digest) else 0
    return (80 + total % 140, 80 + (total * 3) % 140, 80 + (total * 7) % 140)


def _root_name(parts: list[str]) -> str:
    body_names = [name for name in parts if any(token in name for token in ("body", "hull", "core", "base"))]
    return body_names[0] if body_names else (parts[0] if parts else "body")


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


def _load_mesh_file(path: Path) -> trimesh.Trimesh | None:
    """Load a mesh file from disk via the sandboxed ingest path (SEC-NEW-1).

    Delegates to :func:`lathe.mesh_ingest.safe_load_mesh` for size cap,
    format allowlist, magic-byte sniff, and post-load sanity checks.
    Returns ``None`` when the loader produces an empty geometry; raises
    :class:`ShapeProviderExecutionError` for any ingest rejection so the
    provider layer presents a single error class to callers.
    """
    try:
        loaded = safe_load_mesh(Path(path))
    except ShapeMeshLoadError as exc:
        logger.warning("Safe mesh ingest rejected %s (%s)", path, exc.code)
        raise ShapeProviderExecutionError(
            "lathe.provider.shape",
            f"Cannot load mesh: {path}",
            code="mesh_load_failed",
            details={"ingest_code": exc.code, **(exc.details or {})},
        ) from exc
    if len(loaded.faces) == 0 or len(loaded.vertices) == 0:
        return None
    return loaded.copy()


def _mesh_body_count(mesh: trimesh.Trimesh) -> int:
    """Return the number of connected components in ``mesh``.

    Falls back to a BFS over shared-vertex adjacency when
    ``trimesh.body_count`` fails.  The original code caught a bare
    ``Exception`` here; narrowing to ``(AttributeError, IndexError,
    ValueError)`` (Plan 10 C2) preserves the intentional BFS-fallback path
    while still letting genuinely unexpected errors surface.
    """
    try:
        return int(mesh.body_count)
    except (AttributeError, IndexError, ValueError) as exc:
        logger.debug("body_count fallback engaged for mesh: %s", type(exc).__name__)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) == 0:
        return 0
    vertex_to_faces: dict[int, list[int]] = {}
    for face_index, face in enumerate(faces):
        for vertex in face:
            vertex_to_faces.setdefault(int(vertex), []).append(face_index)
    visited = np.zeros(len(faces), dtype=bool)
    body_count = 0
    for start in range(len(faces)):
        if visited[start]:
            continue
        body_count += 1
        stack = [start]
        visited[start] = True
        while stack:
            face_index = stack.pop()
            for vertex in faces[face_index]:
                for neighbor in vertex_to_faces[int(vertex)]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        stack.append(neighbor)
    return int(body_count)


def _mesh_quality_score(mesh: trimesh.Trimesh) -> float:
    score = 0.78
    if mesh.is_watertight:
        score += 0.08
    if len(mesh.faces) > 0:
        score += 0.04
    if len(mesh.vertices) > 0:
        score += 0.04
    body_count = _mesh_body_count(mesh)
    if body_count >= 1:
        score += 0.03
    if len(mesh.faces) > 60000:
        score -= 0.05
    return max(0.35, min(0.98, round(score, 6)))


def _runtime_from_mesh(
    asset: dict[str, Any],
    mesh: trimesh.Trimesh,
    conditioning: dict[str, Any],
    *,
    provider_id: str,
    notes: list[str],
    candidate_index: int,
    provider_bias: float = 0.0,
    units: str = "cm",
    score_override: float | None = None,
) -> dict[str, Any]:
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    root = _root_name(parts)
    mesh = _normalize_mesh_to_scale(mesh, _characteristic_scale_cm(asset))
    face_parts = [root] * int(len(mesh.faces))
    part_colors = _conditioned_part_colors(parts, conditioning)
    score = score_override if score_override is not None else round(
        min(0.99, _mesh_quality_score(mesh) + provider_bias - 0.01 * candidate_index), 6
    )
    return {
        "mesh": mesh,
        "face_parts": face_parts,
        "part_colors": part_colors,
        "units": units,
        "meta": {
            "parts": [root],
            "declared_parts": parts,
            "coarse_material_slots": 1,
            "score": score,
            "selection_notes": notes,
            "conditioning": {
                "provider": provider_id,
                "reference_strength": conditioning.get("reference_strength", 0.0),
            },
        },
    }
