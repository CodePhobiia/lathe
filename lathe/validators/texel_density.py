"""Roadmap §5.9 — texel-density consistency validator.

For each face that carries UVs, computes::

    texel_density = area_3d / area_uv

and reports the variance across the mesh. A high variance means the
texture stretches unevenly across the surface — a common shoebox
failure mode where one big slab gets the full UV chart while small
greebles compete for a few percent of UV space.

Mesh-only; consumes the UV-stage runtime mesh attached at
``runtime["uv"]["runtime_mesh"]``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "lathe.validate.texel_density_consistency_v1"

_VARIANCE_NORMALIZER = 0.40
_WARN_THRESHOLD = 0.50


def _per_face_3d_area(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = vertices[faces]
    edge1 = tri[:, 1] - tri[:, 0]
    edge2 = tri[:, 2] - tri[:, 0]
    return 0.5 * np.linalg.norm(np.cross(edge1, edge2), axis=1)


def _per_face_uv_area(uv: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = uv[faces]
    edge1 = tri[:, 1] - tri[:, 0]
    edge2 = tri[:, 2] - tri[:, 0]
    cross_z = edge1[:, 0] * edge2[:, 1] - edge1[:, 1] * edge2[:, 0]
    return 0.5 * np.abs(cross_z)


def _resolve_uv_mesh(runtime: dict[str, Any]) -> Any | None:
    uv_state = runtime.get("uv") if isinstance(runtime.get("uv"), dict) else {}
    uv_runtime_mesh = uv_state.get("runtime_mesh")
    candidate = getattr(uv_runtime_mesh, "mesh", None) if uv_runtime_mesh is not None else None
    if candidate is not None:
        return candidate
    topology = runtime.get("topology") if isinstance(runtime.get("topology"), dict) else {}
    runtime_mesh = topology.get("runtime_mesh")
    return getattr(runtime_mesh, "mesh", None) if runtime_mesh is not None else None


def evaluate_texel_density_consistency(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate per-face texel-density variance from UV coords."""
    mesh = _resolve_uv_mesh(runtime)
    if mesh is None or len(mesh.faces) == 0:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "skipped",
            "evidence": {"reason": "uv runtime mesh unavailable"},
        }

    visual = getattr(mesh, "visual", None)
    uv = getattr(visual, "uv", None) if visual is not None else None
    if uv is None or len(uv) != len(mesh.vertices):
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "skipped",
            "evidence": {"reason": "uv coordinates unavailable on runtime mesh"},
        }

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    uv_arr = np.asarray(uv, dtype=np.float64)
    area_3d = _per_face_3d_area(vertices, faces)
    area_uv = _per_face_uv_area(uv_arr, faces)
    valid = (area_uv > 1e-9) & (area_3d > 1e-12)
    if not bool(np.any(valid)):
        return {
            "version": VERSION,
            "score": 0.0,
            "status": "warn",
            "severity": "warning",
            "evidence": {"reason": "no UV-mapped faces with positive area"},
        }
    density = area_3d[valid] / area_uv[valid]
    log_density = np.log(np.maximum(density, 1e-9))
    variance = float(np.var(log_density))
    score = round(max(0.0, min(1.0, 1.0 - variance / max(1e-9, _VARIANCE_NORMALIZER))), 6)

    if score < _WARN_THRESHOLD:
        status = "warn"
        severity = "warning"
    else:
        status = "pass"
        severity = "info"

    return {
        "version": VERSION,
        "score": score,
        "status": status,
        "severity": severity,
        "evidence": {
            "log_density_variance": round(variance, 6),
            "mean_density": round(float(np.mean(density)), 6),
            "median_density": round(float(np.median(density)), 6),
            "uv_mapped_face_count": int(np.sum(valid)),
            "total_face_count": int(len(faces)),
            "warn_threshold": _WARN_THRESHOLD,
        },
    }
