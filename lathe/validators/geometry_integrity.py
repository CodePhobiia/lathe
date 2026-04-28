"""Geometry-integrity validator (GEO-5/6/7).

Post-topology, post-kernel validator that inspects the authoritative
runtime mesh for three integrity properties:

* ``self_intersection_rate`` — non-adjacent faces that intersect each
  other. Watertight-by-construction kernels should produce zero.
* ``normal_consistency`` — ``trimesh.is_winding_consistent`` plus a
  per-edge neighbor-flip check.
* ``body_count_stability`` — opt-in re-evaluation of the kernel's
  disjoint-body count; catches backends whose splitter is non-deterministic.

The validator is wired into :class:`ValidatorPipeline` with
``stage_dependencies=["topology"]``; when the runtime lacks a topology
bundle (synthetic test scenarios) it degrades to empty evidence with no
diagnostics so downstream readers never crash.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

_SELF_INTERSECTION_CODE = "L6201"
_NORMAL_CONSISTENCY_CODE = "L6202"
_BODY_COUNT_STABILITY_CODE = "L6203"
_MIN_TRIANGLE_PAIR_FACES = 2
_TRIANGLE_DIMENSIONS = 2
_TRIANGLE_VERTICES = 2
_GEOMETRY_EPS = 1e-12
_INCONSISTENT_NORMAL_DOT = -0.5


def _get_runtime_mesh(runtime: dict[str, Any]) -> trimesh.Trimesh | None:
    topology = runtime.get("topology")
    if not isinstance(topology, dict):
        return None
    runtime_mesh = topology.get("runtime_mesh")
    if runtime_mesh is None:
        return None
    mesh = getattr(runtime_mesh, "mesh", None)
    if mesh is None or not isinstance(mesh, trimesh.Trimesh):
        return None
    if len(mesh.faces) == 0:
        return None
    return mesh


def _self_intersection_rate(mesh: trimesh.Trimesh) -> tuple[float, int, int]:
    """Return ``(rate, intersecting_pair_count, tested_pair_count)``.

    Broad phase is AABB overlap; narrow phase is a SAT + segment-pierces-
    triangle test. Adjacent faces are excluded — adjacency is taken as
    *shared vertex position* (not just shared index) so that seam-split
    duplicates along part boundaries do not register as self-intersections.
    """
    faces = mesh.faces
    n_faces = len(faces)
    if n_faces < _MIN_TRIANGLE_PAIR_FACES:
        return 0.0, 0, 0

    try:
        tri_verts = mesh.vertices[faces]
    except (IndexError, ValueError):
        return 0.0, 0, 0

    # Position-based vertex keys: snap each coordinate to a coarse grid so
    # duplicated seam vertices at the same physical location fold into one
    # bucket. This is a far more reliable "these two triangles touch" test
    # than trimesh's face_adjacency (which is manifold-only).
    extents = (
        mesh.extents if hasattr(mesh, "extents") else tri_verts.max(axis=(0, 1)) - tri_verts.min(axis=(0, 1))
    )
    scale = float(max(1.0, float(np.max(extents))))
    tol = 1e-6 * scale

    def _key(point: np.ndarray) -> tuple[int, int, int]:
        return (
            round(float(point[0]) / tol),
            round(float(point[1]) / tol),
            round(float(point[2]) / tol),
        )

    position_to_faces: dict[tuple[int, int, int], set[int]] = {}
    for idx in range(n_faces):
        for corner in range(3):
            position_to_faces.setdefault(_key(tri_verts[idx, corner]), set()).add(idx)

    adjacency_pairs: set[tuple[int, int]] = set()
    for faces_at_pos in position_to_faces.values():
        if len(faces_at_pos) < _MIN_TRIANGLE_PAIR_FACES:
            continue
        sorted_faces = sorted(faces_at_pos)
        for i_pos, fi in enumerate(sorted_faces):
            for fj in sorted_faces[i_pos + 1 :]:
                adjacency_pairs.add((fi, fj))

    bounds_min = tri_verts.min(axis=1)
    bounds_max = tri_verts.max(axis=1)

    max_pairs_to_scan = 400_000
    intersecting = 0
    tested = 0
    for i in range(n_faces - 1):
        if tested >= max_pairs_to_scan:
            break
        lo_i = bounds_min[i]
        hi_i = bounds_max[i]
        overlap = np.all(bounds_min[i + 1 :] <= hi_i, axis=1) & np.all(bounds_max[i + 1 :] >= lo_i, axis=1)
        candidates = np.nonzero(overlap)[0] + (i + 1)
        for j in candidates:
            j_int = int(j)
            if (i, j_int) in adjacency_pairs:
                continue
            tested += 1
            if tested > max_pairs_to_scan:
                break
            if _triangles_intersect(tri_verts[i], tri_verts[j_int]):
                intersecting += 1

    total_pairs = n_faces * (n_faces - 1) // 2
    if total_pairs <= 0:
        return 0.0, intersecting, tested
    rate = intersecting / float(total_pairs)
    return float(rate), int(intersecting), int(tested)


def _triangles_intersect(a: np.ndarray, b: np.ndarray) -> bool:
    """Triangle-triangle intersection via separating-axis + segment test.

    Returns True only when the two triangles' interiors properly cross.
    Pairs that merely touch (shared vertex, coincident edge, coplanar
    abutment) are excluded: the primary adjacency filter already catches
    those for most cases, and this narrow-phase guards against the few
    that slip through by bailing early when any corner is shared within
    a generous tolerance.
    """
    tol = 1e-6 * max(
        1.0,
        float(np.max(np.abs(np.concatenate([a.ravel(), b.ravel()])))),
    )
    for va in a:
        for vb in b:
            if np.all(np.abs(va - vb) < tol):
                return False

    n_a = np.cross(a[1] - a[0], a[2] - a[0])
    n_b = np.cross(b[1] - b[0], b[2] - b[0])
    if np.linalg.norm(n_a) < _GEOMETRY_EPS or np.linalg.norm(n_b) < _GEOMETRY_EPS:
        return False
    d_a = -float(np.dot(n_a, a[0]))
    d_b = -float(np.dot(n_b, b[0]))

    # SAT over both face normals: if all of one triangle lies strictly on
    # one side of the other's plane, they cannot cross.
    plane_eps = tol
    dist_b_to_a = np.dot(b, n_a) + d_a
    if np.all(dist_b_to_a > plane_eps) or np.all(dist_b_to_a < -plane_eps):
        return False
    dist_a_to_b = np.dot(a, n_b) + d_b
    if np.all(dist_a_to_b > plane_eps) or np.all(dist_a_to_b < -plane_eps):
        return False

    for edge_start, edge_end in ((b[0], b[1]), (b[1], b[2]), (b[2], b[0])):
        hit = _segment_pierces_triangle(edge_start, edge_end, a, n_a, d_a, tol)
        if hit:
            return True
    for edge_start, edge_end in ((a[0], a[1]), (a[1], a[2]), (a[2], a[0])):
        hit = _segment_pierces_triangle(edge_start, edge_end, b, n_b, d_b, tol)
        if hit:
            return True
    return False


def _segment_pierces_triangle(
    p0: np.ndarray,
    p1: np.ndarray,
    tri: np.ndarray,
    n: np.ndarray,
    d: float,
    tol: float,
) -> bool:
    dir_vec = p1 - p0
    denom = float(np.dot(n, dir_vec))
    if abs(denom) < _GEOMETRY_EPS:
        return False
    t = -(float(np.dot(n, p0)) + d) / denom
    # Require the piercing point to land strictly *inside* the segment;
    # endpoint hits are excluded so edge-shared pairs don't register.
    if t < tol or t > 1.0 - tol:
        return False
    hit = p0 + t * dir_vec
    return _point_in_triangle(hit, tri, n, tol)


def _point_in_triangle(point: np.ndarray, tri: np.ndarray, n: np.ndarray, tol: float) -> bool:
    c0 = np.cross(tri[1] - tri[0], point - tri[0])
    c1 = np.cross(tri[2] - tri[1], point - tri[1])
    c2 = np.cross(tri[0] - tri[2], point - tri[2])
    s0 = float(np.dot(c0, n))
    s1 = float(np.dot(c1, n))
    s2 = float(np.dot(c2, n))
    # Strict interior: require same-sign, *not* equal to zero, so that a
    # hit landing on a triangle's own edge doesn't count as penetration.
    eps = tol
    return (s0 > eps and s1 > eps and s2 > eps) or (s0 < -eps and s1 < -eps and s2 < -eps)


def _normal_consistency(mesh: trimesh.Trimesh) -> tuple[float, bool, int, int]:
    """Return ``(score, winding_consistent, n_inconsistent_edges, n_edges)``."""
    try:
        winding_consistent = bool(mesh.is_winding_consistent)
    except (AttributeError, ValueError):
        winding_consistent = True

    face_adjacency = getattr(mesh, "face_adjacency", None)
    face_normals = getattr(mesh, "face_normals", None)
    if face_adjacency is None or face_normals is None or len(face_adjacency) == 0:
        score = 1.0 if winding_consistent else 0.0
        return float(score), winding_consistent, 0, 0

    pairs = np.asarray(face_adjacency, dtype=np.int64)
    if pairs.ndim != _TRIANGLE_DIMENSIONS or pairs.shape[1] != _TRIANGLE_VERTICES or len(pairs) == 0:
        score = 1.0 if winding_consistent else 0.0
        return float(score), winding_consistent, 0, 0

    a_normals = np.asarray(face_normals[pairs[:, 0]], dtype=np.float64)
    b_normals = np.asarray(face_normals[pairs[:, 1]], dtype=np.float64)
    dots = np.einsum("ij,ij->i", a_normals, b_normals)
    inconsistent = int(np.sum(dots < _INCONSISTENT_NORMAL_DOT))
    total = len(pairs)
    if total == 0:
        score = 1.0 if winding_consistent else 0.0
        return float(score), winding_consistent, 0, 0
    edge_score = 1.0 - (inconsistent / float(total))
    winding_score = 1.0 if winding_consistent else 0.0
    score = float(min(edge_score, winding_score)) if not winding_consistent else float(edge_score)
    return score, winding_consistent, inconsistent, total


def _body_count_stability(
    mesh: trimesh.Trimesh,
    runtime: dict[str, Any],
    runs: int = 3,
) -> tuple[float, list[int]]:
    """Run the body-count computation ``runs`` times and compare.

    Uses the geometry kernel recorded on ``runtime['shape']['kernel']``
    when available, otherwise falls back to ``trimesh.Trimesh.split``.
    The check is only invoked when the caller opts in; the default
    path short-circuits at the call site.
    """
    kernel = None
    shape_state = runtime.get("shape")
    if isinstance(shape_state, dict):
        kernel = shape_state.get("kernel")

    counts: list[int] = []
    for _ in range(max(1, int(runs))):
        if kernel is not None and hasattr(kernel, "body_count"):
            try:
                counts.append(int(kernel.body_count(mesh)))
                continue
            except (TypeError, AttributeError, ValueError):
                pass
        try:
            counts.append(len(mesh.split(only_watertight=False)))
        except (TypeError, ValueError, RuntimeError):
            counts.append(1)

    if not counts:
        return 1.0, counts
    identical = sum(1 for c in counts if c == counts[0])
    score = identical / float(len(counts))
    return float(score), counts


def evaluate_geometry_integrity(
    asset: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate geometry integrity for the authoritative topology mesh.

    Args:
        asset: resolved asset dict (normalizer + resolver output).
        runtime: executor runtime after the topology stage has run.

    Returns:
        Legacy-style validator dict (``metrics`` + ``diagnostics`` + a
        few evidence fields). Wrapped by :class:`FunctionValidator` into
        a ``ValidatorReport`` at the pipeline boundary.
    """
    diagnostics: list[dict[str, Any]] = []
    mesh = _get_runtime_mesh(runtime)
    if mesh is None:
        return {
            "metrics": {
                "self_intersection_rate": 0.0,
                "normal_consistency": 1.0,
                "body_count_stability": 1.0,
            },
            "evidence": {
                "evaluated": False,
                "reason": "topology runtime mesh unavailable",
            },
            "diagnostics": diagnostics,
        }

    shape_cfg = asset.get("build", {}).get("shape", {}) or {}
    geometry_strict = bool(shape_cfg.get("geometry_strict", False))
    body_count_stability_check = bool(shape_cfg.get("body_count_stability_check", False))

    intersection_rate, intersecting_pairs, tested_pairs = _self_intersection_rate(mesh)
    normal_score, winding_ok, bad_edges, edge_pairs = _normal_consistency(mesh)

    if body_count_stability_check:
        body_stability, body_counts = _body_count_stability(mesh, runtime)
    else:
        body_stability = 1.0
        body_counts = []

    severity_intersection = "error" if geometry_strict else "warning"
    if intersecting_pairs > 0:
        diagnostics.append(
            {
                "code": _SELF_INTERSECTION_CODE,
                "name": "self_intersecting",
                "severity": severity_intersection,
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "path": "validate.geometry_integrity.self_intersection_rate",
                "message": (
                    f"Geometry integrity detected {intersecting_pairs} "
                    f"self-intersecting face pair(s) out of {tested_pairs} tested"
                ),
                "details": {
                    "metric": "self_intersection_rate",
                    "intersecting_pairs": intersecting_pairs,
                    "tested_pairs": tested_pairs,
                    "rate": intersection_rate,
                },
                "suggested_repairs": ["repair_self_intersections"],
            }
        )

    if not winding_ok or bad_edges > 0:
        diagnostics.append(
            {
                "code": _NORMAL_CONSISTENCY_CODE,
                "name": "inconsistent_normals",
                "severity": "warning",
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "path": "validate.geometry_integrity.normal_consistency",
                "message": (
                    "Geometry integrity detected inconsistent face winding / normals"
                    f" ({bad_edges} flipped edge-adjacencies of {edge_pairs})"
                ),
                "details": {
                    "metric": "normal_consistency",
                    "is_winding_consistent": winding_ok,
                    "inconsistent_edges": bad_edges,
                    "edge_pairs": edge_pairs,
                },
                "suggested_repairs": ["repair_face_winding"],
            }
        )

    if body_count_stability_check and body_stability < 1.0:
        diagnostics.append(
            {
                "code": _BODY_COUNT_STABILITY_CODE,
                "name": "unstable_body_count",
                "severity": "error",
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "path": "validate.geometry_integrity.body_count_stability",
                "message": (
                    "Geometry integrity detected unstable body-count across "
                    f"{len(body_counts)} runs: {body_counts}"
                ),
                "details": {
                    "metric": "body_count_stability",
                    "observed_counts": body_counts,
                    "stability": body_stability,
                },
                "suggested_repairs": ["use_deterministic_kernel"],
            }
        )

    metrics = {
        "self_intersection_rate": round(float(intersection_rate), 6),
        "normal_consistency": round(float(normal_score), 6),
        "body_count_stability": round(float(body_stability), 6),
    }

    evidence = {
        "evaluated": True,
        "intersecting_pairs": intersecting_pairs,
        "tested_pairs": tested_pairs,
        "is_winding_consistent": bool(winding_ok),
        "inconsistent_edge_adjacencies": int(bad_edges),
        "edge_adjacencies": int(edge_pairs),
        "body_count_stability_check": body_count_stability_check,
        "observed_body_counts": body_counts,
        "geometry_strict": geometry_strict,
    }

    return {
        "metrics": metrics,
        "evidence": evidence,
        "diagnostics": diagnostics,
    }
