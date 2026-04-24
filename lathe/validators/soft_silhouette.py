"""Soft-silhouette validator (BL-34 scope).

Minimal silhouette validator associated with the ``lathe.stack.soft_surface_prop_v1``
second backend stack. The current implementation is intentionally shallow
and exists to prove the plugin-model end-to-end (Plan 08 Phase 4, scoped
down per Wave 4.IV.e).

Two proxy checks run here:

1. **Sample density** -- proxied by the triangle count on the final
   topology mesh. A soft-surface silhouette needs enough curvature
   samples to avoid faceted reads; below a floor we emit
   ``soft_silhouette_too_jagged``.
2. **Fold-crease avoidance** -- proxied by a dihedral-angle maximum.
   If the mesh has a fold past ``MAX_DIHEDRAL_DEGREES`` it reads as a
   sharp crease unsuitable for a soft-surface prop; we emit
   ``soft_silhouette_too_jagged``.

A third tripwire fires when the mesh is *too* smooth with no readable
silhouette features -- this yields ``soft_silhouette_too_smooth`` and
catches degenerate all-sphere outputs.

# TODO(BL-34-followup): full curvature-continuity analysis (per-vertex
# principal curvatures, per-edge C^1/C^2 continuity, silhouette-edge
# ray casts from canonical camera angles) is deferred to the full
# Plan 08 Phase 4 implementation. The thresholds below are tuned so
# a minimal hero (rounded bag shape) certifies and so a crafted-bad
# input (jagged cube, flat plane) fails loudly in tests.
"""

from __future__ import annotations

import math
from typing import Any


# Thresholds -- tuned for the Wave 4.IV.e proof. See docstring.
MIN_TRIANGLE_SAMPLES = 24
MIN_VERTEX_SAMPLES = 16
MAX_DIHEDRAL_DEGREES = 150.0
MIN_READABLE_EDGE_VARIANCE = 1e-4
IDEAL_SAMPLE_TARGET = 500


def _mesh_stats(runtime: dict[str, Any]) -> dict[str, Any]:
    topology = runtime.get("topology", {}) or {}
    bundle = topology.get("bundle", {}) or {}
    stats = bundle.get("mesh_stats", {}) or {}
    return stats


def _max_dihedral_degrees(runtime: dict[str, Any]) -> float:
    """Return the maximum dihedral angle (degrees) across the runtime mesh.

    Uses the trimesh runtime mesh attached to the topology stage when
    available; falls back to a neutral midrange value so missing-mesh
    cases don't cause false positives.
    """
    topology = runtime.get("topology", {}) or {}
    runtime_mesh = topology.get("runtime_mesh")
    if runtime_mesh is None or not hasattr(runtime_mesh, "mesh"):
        return 0.0
    mesh = runtime_mesh.mesh
    try:
        adjacency = mesh.face_adjacency
        angles = mesh.face_adjacency_angles
    except Exception:  # noqa: BLE001 -- defensive; any trimesh call can raise
        return 0.0
    if angles is None or len(angles) == 0 or len(adjacency) == 0:
        return 0.0
    # ``face_adjacency_angles`` is in radians and is the angle between
    # adjacent face normals; a near-zero value means flat (C^0), a value
    # near pi means a sharp fold.
    return math.degrees(float(max(angles)))


def _edge_length_variance(runtime: dict[str, Any]) -> float:
    """Return a cheap proxy for edge-length variance on the final mesh.

    A completely uniform mesh (e.g., a single sphere subdivision with
    no features) has near-zero variance; a mesh with any silhouette
    features has non-trivial variance. We use this to catch the
    too-smooth failure mode.
    """
    topology = runtime.get("topology", {}) or {}
    runtime_mesh = topology.get("runtime_mesh")
    if runtime_mesh is None or not hasattr(runtime_mesh, "mesh"):
        return 0.0
    mesh = runtime_mesh.mesh
    try:
        lengths = mesh.edges_unique_length
    except Exception:  # noqa: BLE001
        return 0.0
    if lengths is None or len(lengths) == 0:
        return 0.0
    mean = float(sum(lengths) / len(lengths))
    if mean <= 0:
        return 0.0
    # Normalized variance (coefficient of variation squared is
    # scale-invariant; good enough as a proxy).
    diffs = [((float(ln) - mean) / mean) ** 2 for ln in lengths]
    return float(sum(diffs) / len(diffs))


def evaluate_soft_silhouette(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Run the soft-silhouette validator.

    Returns a report with ``metrics``, ``diagnostics`` and a ``score``
    in ``[0, 1]``. Intended to be composed with the core validators
    when the soft-surface stack is active. This function does not
    mutate ``runtime``.

    Args:
        asset: materialized asset dict.
        runtime: runtime accumulator the executor builds up across
            stages.

    Returns:
        Validator report dict.
    """
    asset_name = asset.get("name", "<anonymous>")
    stats = _mesh_stats(runtime)
    triangle_count = int(stats.get("triangle_count", 0) or 0)
    vertex_count = int(stats.get("vertex_count", 0) or 0)
    max_dihedral = _max_dihedral_degrees(runtime)
    edge_variance = _edge_length_variance(runtime)

    diagnostics: list[dict[str, Any]] = []

    # Tripwire 1: too few samples -> too jagged to read as soft.
    if triangle_count > 0 and triangle_count < MIN_TRIANGLE_SAMPLES:
        diagnostics.append({
            "code": "L6701",
            "name": "soft_silhouette_too_jagged",
            "severity": "error",
            "phase": "validate",
            "asset": asset_name,
            "stage": "validate",
            "path": "validate.soft_silhouette.samples",
            "message": (
                f"Soft silhouette has only {triangle_count} triangle samples "
                f"(minimum {MIN_TRIANGLE_SAMPLES}); silhouette reads as jagged."
            ),
            "suggested_repairs": ["retopo_auto", "reselect_candidate"],
        })

    if vertex_count > 0 and vertex_count < MIN_VERTEX_SAMPLES:
        diagnostics.append({
            "code": "L6702",
            "name": "soft_silhouette_too_jagged",
            "severity": "error",
            "phase": "validate",
            "asset": asset_name,
            "stage": "validate",
            "path": "validate.soft_silhouette.vertices",
            "message": (
                f"Soft silhouette has only {vertex_count} vertex samples "
                f"(minimum {MIN_VERTEX_SAMPLES})."
            ),
            "suggested_repairs": ["retopo_auto", "reselect_candidate"],
        })

    # Tripwire 2: too-sharp fold -> too jagged crease.
    if max_dihedral > MAX_DIHEDRAL_DEGREES:
        diagnostics.append({
            "code": "L6703",
            "name": "soft_silhouette_too_jagged",
            "severity": "error",
            "phase": "validate",
            "asset": asset_name,
            "stage": "validate",
            "path": "validate.soft_silhouette.max_dihedral",
            "message": (
                f"Maximum dihedral angle {max_dihedral:.1f} deg exceeds soft-surface "
                f"fold limit {MAX_DIHEDRAL_DEGREES:.1f} deg."
            ),
            "suggested_repairs": ["retopo_auto", "reselect_candidate"],
        })

    # Tripwire 3: too-smooth / no features -> unreadable silhouette.
    if triangle_count > 0 and edge_variance < MIN_READABLE_EDGE_VARIANCE:
        diagnostics.append({
            "code": "L6704",
            "name": "soft_silhouette_too_smooth",
            "severity": "warning",
            "phase": "validate",
            "asset": asset_name,
            "stage": "validate",
            "path": "validate.soft_silhouette.edge_variance",
            "message": (
                f"Edge-length variance {edge_variance:.6f} is below "
                f"{MIN_READABLE_EDGE_VARIANCE:.6f}; silhouette is featureless."
            ),
            "suggested_repairs": ["reselect_candidate"],
        })

    # Score: simple composite across the same three axes so callers can
    # blend into a critic weighting. Higher is better.
    sample_score = 1.0 if triangle_count >= MIN_TRIANGLE_SAMPLES else (
        triangle_count / max(1, MIN_TRIANGLE_SAMPLES)
    )
    sample_score = min(1.0, triangle_count / IDEAL_SAMPLE_TARGET) if triangle_count > MIN_TRIANGLE_SAMPLES else sample_score
    fold_score = 1.0 if max_dihedral <= MAX_DIHEDRAL_DEGREES else max(
        0.0, 1.0 - (max_dihedral - MAX_DIHEDRAL_DEGREES) / 30.0
    )
    variance_score = 1.0 if edge_variance >= MIN_READABLE_EDGE_VARIANCE else max(
        0.0, edge_variance / max(MIN_READABLE_EDGE_VARIANCE, 1e-9)
    )
    composite = 0.5 * sample_score + 0.35 * fold_score + 0.15 * variance_score

    return {
        "schema": "lathe.soft_silhouette_ir.v1",
        "score": round(composite, 6),
        "metrics": {
            "triangle_count": triangle_count,
            "vertex_count": vertex_count,
            "max_dihedral_degrees": round(max_dihedral, 4),
            "edge_length_variance": round(edge_variance, 8),
            "sample_score": round(sample_score, 6),
            "fold_score": round(fold_score, 6),
            "variance_score": round(variance_score, 6),
        },
        "thresholds": {
            "min_triangle_samples": MIN_TRIANGLE_SAMPLES,
            "min_vertex_samples": MIN_VERTEX_SAMPLES,
            "max_dihedral_degrees": MAX_DIHEDRAL_DEGREES,
            "min_readable_edge_variance": MIN_READABLE_EDGE_VARIANCE,
        },
        "diagnostics": diagnostics,
    }
