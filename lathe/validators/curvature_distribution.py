"""Roadmap §5.9 — curvature-distribution validator.

Builds a per-vertex discrete mean-curvature estimate via the
angle-defect approximation::

    K_v ≈ (2π - sum(face_angles_at_v)) / area_voronoi(v)

For closed flat-faced meshes (cubes, stacked boxes), the curvature
histogram is *peaky* — almost all vertices land on a corner where
angle-defect ≈ π/2 with a few degenerate ones at zero. Real
hard-surface assets, by contrast, have curvature spread across mid-
range bins thanks to bevels, fillets, and rounded greeble forms.

We score the distribution by rewarding mid-range mass and penalising
twin-peaked corner-only histograms.

Mesh-only; pure numpy.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "lathe.validate.curvature_distribution_v1"

_HIST_BINS = 12
_MIDRANGE_TARGET = 0.35
_CURVED_VERTEX_TARGET = 0.22
_WARN_THRESHOLD = 0.40


def _vertex_angle_defects(
    vertices: np.ndarray, faces: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(per_vertex_curvature, per_vertex_voronoi_area)``."""
    n_verts = vertices.shape[0]
    defects = np.full(n_verts, 2.0 * np.pi, dtype=np.float64)
    areas = np.zeros(n_verts, dtype=np.float64)

    tri = vertices[faces]
    a = tri[:, 1] - tri[:, 0]
    b = tri[:, 2] - tri[:, 1]
    c = tri[:, 0] - tri[:, 2]
    la = np.linalg.norm(a, axis=1)
    lb = np.linalg.norm(b, axis=1)
    lc = np.linalg.norm(c, axis=1)
    safe_la = np.maximum(la, 1e-12)
    safe_lb = np.maximum(lb, 1e-12)
    safe_lc = np.maximum(lc, 1e-12)
    cos0 = np.clip(np.einsum("ij,ij->i", a, -c) / (safe_la * safe_lc), -1.0, 1.0)
    cos1 = np.clip(np.einsum("ij,ij->i", -a, b) / (safe_la * safe_lb), -1.0, 1.0)
    cos2 = np.clip(np.einsum("ij,ij->i", -b, c) / (safe_lb * safe_lc), -1.0, 1.0)
    ang0 = np.arccos(cos0)
    ang1 = np.arccos(cos1)
    ang2 = np.arccos(cos2)

    cross = np.cross(a, c)
    face_areas = 0.5 * np.linalg.norm(cross, axis=1)
    one_third_area = face_areas / 3.0

    for k, ang in enumerate((ang0, ang1, ang2)):
        np.subtract.at(defects, faces[:, k], ang)
        np.add.at(areas, faces[:, k], one_third_area)

    return defects, areas


def _curvature_histogram(curvature: np.ndarray, n_bins: int) -> np.ndarray:
    if len(curvature) == 0:
        return np.zeros(n_bins)
    abs_c = np.abs(curvature)
    cap = np.percentile(abs_c, 99.0) if len(abs_c) > 0 else 1.0
    cap = max(cap, 1e-6)
    clipped = np.minimum(abs_c, cap) / cap
    counts, _ = np.histogram(clipped, bins=n_bins, range=(0.0, 1.0))
    total = counts.sum()
    if total <= 0:
        return np.zeros(n_bins)
    return counts.astype(np.float64) / float(total)


def evaluate_curvature_distribution(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate the discrete curvature distribution histogram."""
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
    defects, areas = _vertex_angle_defects(vertices, faces)
    curvature = defects / np.maximum(areas, 1e-9)

    hist = _curvature_histogram(curvature, _HIST_BINS)
    n_bins = len(hist)
    end_mass = float(hist[0]) + float(hist[-1]) if n_bins >= 2 else 1.0
    midrange_mass = float(hist[1 : n_bins - 1].sum()) if n_bins >= 3 else 0.0
    total_mass = end_mass + midrange_mass
    midrange_share = midrange_mass / total_mass if total_mass > 0 else 0.0
    end_share = end_mass / total_mass if total_mass > 0 else 1.0

    peak_penalty = max(0.0, min(1.0, end_share - _MIDRANGE_TARGET))
    legacy_score = max(0.0, min(1.0, midrange_share - 0.5 * peak_penalty + 0.25))

    flat_share = float(hist[0]) if n_bins >= 1 else 1.0
    sharp_share = float(hist[-1]) if n_bins >= 2 else 0.0
    curved_mass = max(0.0, min(1.0, midrange_mass + sharp_share))
    curved_midrange_share = midrange_mass / curved_mass if curved_mass > 0.0 else 0.0
    curved_support = min(1.0, curved_mass / _CURVED_VERTEX_TARGET)
    curved_score = max(
        0.0,
        min(
            1.0,
            0.15 + 0.70 * curved_midrange_share * curved_support - 0.20 * sharp_share,
        ),
    )
    score = round(max(legacy_score, curved_score), 6)

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
            "histogram": [round(float(v), 6) for v in hist.tolist()],
            "midrange_share": round(midrange_share, 6),
            "end_share": round(end_share, 6),
            "flat_share": round(flat_share, 6),
            "sharp_share": round(sharp_share, 6),
            "curved_mass": round(curved_mass, 6),
            "curved_midrange_share": round(curved_midrange_share, 6),
            "curved_vertex_target": _CURVED_VERTEX_TARGET,
            "legacy_score": round(legacy_score, 6),
            "curved_score": round(curved_score, 6),
            "peak_penalty": round(peak_penalty, 6),
            "warn_threshold": _WARN_THRESHOLD,
            "vertex_count": int(vertices.shape[0]),
        },
    }
