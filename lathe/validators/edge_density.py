"""Roadmap §5.9 — edge-density variance validator.

Cubes (and unbroken stacked primitives) have nearly uniform edge length
per face: every face is a square slice of the bounding box. Real
hard-surface assets have a wide distribution of edge lengths driven by
bevels, panel breaks, greebles, and vent slots.

We bucket faces by area and compute the *variance* of mean edge-length
per face inside each bucket. Higher variance means more silhouette
disturbance; lower variance means a uniform shoebox topology.

Operates on the authoritative runtime mesh; no renderer dependency.

Score: monotonically increasing in variance, normalized so a single
unbeveled cube → score ≈ 0 and a richly detailed asset → score ≈ 1.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "lathe.validate.edge_density_variance_v1"

_AREA_BUCKET_COUNT = 4
_VARIANCE_NORMALIZER = 0.05  # picks score≈1 around variance≈0.05·mean²
_WARN_THRESHOLD = 0.35


def _per_face_mean_edge_length(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri_verts = vertices[faces]
    edges_a = tri_verts[:, 1] - tri_verts[:, 0]
    edges_b = tri_verts[:, 2] - tri_verts[:, 1]
    edges_c = tri_verts[:, 0] - tri_verts[:, 2]
    lens = np.stack(
        [
            np.linalg.norm(edges_a, axis=1),
            np.linalg.norm(edges_b, axis=1),
            np.linalg.norm(edges_c, axis=1),
        ],
        axis=1,
    )
    return np.mean(lens, axis=1)


def _bucketed_variance(
    face_areas: np.ndarray, edge_means: np.ndarray, n_buckets: int
) -> tuple[float, list[dict[str, float]]]:
    if len(face_areas) == 0:
        return 0.0, []
    sorted_idx = np.argsort(face_areas)
    chunk_size = max(1, len(face_areas) // n_buckets)
    bucket_summary: list[dict[str, float]] = []
    bucket_variances: list[float] = []
    for b_idx in range(n_buckets):
        start = b_idx * chunk_size
        if b_idx == n_buckets - 1:
            stop = len(face_areas)
        else:
            stop = min((b_idx + 1) * chunk_size, len(face_areas))
        if start >= stop:
            continue
        members = sorted_idx[start:stop]
        if len(members) < 2:
            continue
        sample = edge_means[members]
        mean_len = float(np.mean(sample))
        var = float(np.var(sample))
        denom = max(1e-9, mean_len * mean_len)
        normalized_var = var / denom
        bucket_variances.append(normalized_var)
        bucket_summary.append(
            {
                "face_count": len(members),
                "mean_edge_length": round(mean_len, 6),
                "edge_length_variance": round(var, 6),
                "normalized_variance": round(normalized_var, 6),
            }
        )
    if not bucket_variances:
        return 0.0, bucket_summary
    return float(np.mean(bucket_variances)), bucket_summary


def evaluate_edge_density_variance(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate per-face edge-density variance across area buckets."""
    topology = runtime.get("topology") if isinstance(runtime.get("topology"), dict) else {}
    runtime_mesh = topology.get("runtime_mesh")
    mesh = getattr(runtime_mesh, "mesh", None) if runtime_mesh is not None else None
    if mesh is None or len(mesh.faces) == 0:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "skipped",
            "evidence": {"reason": "topology runtime mesh unavailable"},
        }

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    edge_means = _per_face_mean_edge_length(vertices, faces)
    face_areas = np.asarray(mesh.area_faces, dtype=np.float64)

    overall_norm_variance, bucket_summary = _bucketed_variance(
        face_areas, edge_means, _AREA_BUCKET_COUNT
    )
    score = round(min(1.0, overall_norm_variance / max(1e-9, _VARIANCE_NORMALIZER)), 6)

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
            "mean_normalized_variance": round(overall_norm_variance, 6),
            "buckets": bucket_summary,
            "warn_threshold": _WARN_THRESHOLD,
            "face_count": len(faces),
        },
    }
