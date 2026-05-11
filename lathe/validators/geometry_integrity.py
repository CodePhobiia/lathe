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
_BOOLEAN_FALLBACK_CODE = "L6204"
_DIRECT_MODIFIER_CODE = "L6205"
_MIN_TRIANGLE_PAIR_FACES = 2
_TRIANGLE_DIMENSIONS = 2
_TRIANGLE_VERTICES = 2
_GEOMETRY_EPS = 1e-12
_INCONSISTENT_NORMAL_DOT = -0.5
_MAX_SELF_INTERSECTION_PAIRS = 25_000
_MAX_SELF_INTERSECTION_FACE_SCAN = 2048
_DIRECT_MODIFIER_RECORD_LIMIT = 32


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


def _self_intersection_rate(mesh: trimesh.Trimesh) -> tuple[float, int, int, bool, int, int]:
    """Return bounded self-intersection evidence.

    The tuple is ``(rate, intersecting_pair_count, tested_pair_count,
    scan_limited, scanned_face_rows, total_face_rows)``.

    Broad phase is AABB overlap; narrow phase is a SAT + segment-pierces-
    triangle test. Adjacent faces are excluded — adjacency is taken as
    *shared vertex position* (not just shared index) so that seam-split
    duplicates along part boundaries do not register as self-intersections.

    The narrow phase is intentionally bounded. Large generated fixtures can
    produce enough overlapping AABB pairs for the SAT/segment test to dominate
    end-to-end builds. When the cap is reached, validator evidence marks the
    result as a bounded sample rather than implying an exhaustive scan.
    """
    faces = mesh.faces
    n_faces = len(faces)
    if n_faces < _MIN_TRIANGLE_PAIR_FACES:
        return 0.0, 0, 0, False, 0, int(n_faces)

    try:
        tri_verts = mesh.vertices[faces]
    except (IndexError, ValueError):
        return 0.0, 0, 0, False, 0, int(n_faces)

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

    max_pairs_to_scan = max(1, int(_MAX_SELF_INTERSECTION_PAIRS))
    scan_limited = False
    intersecting = 0
    tested = 0
    max_face_rows = max(1, int(_MAX_SELF_INTERSECTION_FACE_SCAN))
    if n_faces - 1 > max_face_rows:
        scan_indices = np.unique(np.linspace(0, n_faces - 2, max_face_rows, dtype=np.int64))
        scan_limited = True
    else:
        scan_indices = np.arange(n_faces - 1, dtype=np.int64)
    scanned_face_rows = 0
    for raw_i in scan_indices:
        i = int(raw_i)
        if i < 0 or i >= n_faces - 1:
            continue
        scanned_face_rows += 1
        if tested >= max_pairs_to_scan:
            scan_limited = True
            break
        lo_i = bounds_min[i]
        hi_i = bounds_max[i]
        overlap = np.all(bounds_min[i + 1 :] <= hi_i, axis=1) & np.all(bounds_max[i + 1 :] >= lo_i, axis=1)
        candidates = np.nonzero(overlap)[0] + (i + 1)
        for j in candidates:
            j_int = int(j)
            if (i, j_int) in adjacency_pairs:
                continue
            if tested >= max_pairs_to_scan:
                scan_limited = True
                break
            tested += 1
            if _triangles_intersect(tri_verts[i], tri_verts[j_int]):
                intersecting += 1

    total_pairs = n_faces * (n_faces - 1) // 2
    if total_pairs <= 0 or tested <= 0:
        return 0.0, intersecting, tested, scan_limited, scanned_face_rows, int(n_faces)
    denominator = tested if scan_limited else total_pairs
    rate = intersecting / float(max(1, denominator))
    return float(rate), int(intersecting), int(tested), bool(scan_limited), scanned_face_rows, int(n_faces)


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


def _selected_shape_integration_report(runtime: dict[str, Any]) -> dict[str, Any]:
    shape_state = runtime.get("shape")
    if not isinstance(shape_state, dict):
        return {}
    bundle = shape_state.get("bundle")
    if not isinstance(bundle, dict):
        return {}
    selected_id = str(bundle.get("selected_candidate_id") or "")
    for candidate in bundle.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("candidate_id") or "") != selected_id:
            continue
        report = candidate.get("integration_report")
        return dict(report) if isinstance(report, dict) else {}
    return {}


def _boolean_fallback_evidence(report: dict[str, Any]) -> dict[str, Any]:
    fallback_records = [
        dict(record)
        for record in report.get("kernel_program_boolean_fallback_records", []) or []
        if isinstance(record, dict)
    ]
    fallback_reason = (
        report.get("boolean_fallback_reason")
        or report.get("kernel_program_failure_reason")
        or report.get("reason")
        or ""
    )
    fallback_mode = str(report.get("mode") or "")
    boolean_fallback = str(report.get("boolean_fallback") or "")
    fallback_count = int(report.get("kernel_program_boolean_fallback_count", 0) or 0)
    has_fallback = bool(
        fallback_records
        or fallback_count > 0
        or boolean_fallback
        or "fallback" in fallback_mode
        or "fallback" in str(fallback_reason)
        or "omitted" in str(fallback_reason)
    )
    return {
        "has_boolean_fallback": has_fallback,
        "fallback_count": max(fallback_count, len(fallback_records)),
        "fallback_records": fallback_records,
        "fallback_reason": str(fallback_reason),
        "boolean_fallback": boolean_fallback,
        "mode": fallback_mode,
        "geometry_kernel": str(
            report.get("geometry_kernel")
            or report.get("boolean_kernel")
            or report.get("kernel_program_kernel")
            or ""
        ),
        "kernel_program_succeeded": bool(report.get("kernel_program_succeeded", False)),
    }


def _direct_modifier_execution_evidence(mesh: trimesh.Trimesh) -> dict[str, Any]:
    metadata = getattr(mesh, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return {
            "attempted_count": 0,
            "applied_count": 0,
            "degraded_count": 0,
            "preserved_downstream_count": 0,
            "degraded_records": [],
        }
    raw_applications = metadata.get("lathe_v2_kernel_modifier_applications")
    if isinstance(raw_applications, dict):
        raw_applications = raw_applications.get("applications")
    applications = [
        dict(record)
        for record in (raw_applications or [])
        if isinstance(record, dict)
    ]
    degraded_records: list[dict[str, Any]] = []
    preserved_count = 0
    applied_count = 0
    for record in applications:
        application = str(record.get("geometry_application") or "")
        if bool(record.get("geometry_applied")):
            applied_count += 1
        if application == "direct_modifier_preserved_for_downstream_stage":
            preserved_count += 1
            continue
        fallback_reason = str(record.get("fallback_reason") or "")
        degraded = bool(
            application.startswith("unsupported")
            or application.startswith("invalid")
            or application.endswith("_failed")
            or "blocked_after_prior_modifier" in application
            or "missing" in application
            or "failed" in application
            or bool(record.get("failure_reason"))
            or bool(record.get("failure_type"))
            or (fallback_reason and "fallback" in fallback_reason.lower())
        )
        if degraded:
            degraded_records.append(
                {
                    "name": str(record.get("name") or ""),
                    "geometry_application": application,
                    "geometry_applied": bool(record.get("geometry_applied")),
                    "operation": str(record.get("operation") or ""),
                    "failure_type": str(record.get("failure_type") or ""),
                    "failure_reason": str(record.get("failure_reason") or ""),
                    "fallback_reason": fallback_reason,
                }
            )
    return {
        "attempted_count": len(applications),
        "applied_count": applied_count,
        "degraded_count": len(degraded_records),
        "preserved_downstream_count": preserved_count,
        "degraded_records": degraded_records[:_DIRECT_MODIFIER_RECORD_LIMIT],
        "degraded_records_truncated": len(degraded_records) > _DIRECT_MODIFIER_RECORD_LIMIT,
    }


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

    (
        intersection_rate,
        intersecting_pairs,
        tested_pairs,
        intersection_scan_limited,
        intersection_scanned_face_rows,
        intersection_total_face_rows,
    ) = _self_intersection_rate(mesh)
    normal_score, winding_ok, bad_edges, edge_pairs = _normal_consistency(mesh)

    if body_count_stability_check:
        body_stability, body_counts = _body_count_stability(mesh, runtime)
    else:
        body_stability = 1.0
        body_counts = []
    shape_integration_report = _selected_shape_integration_report(runtime)
    boolean_fallback = _boolean_fallback_evidence(shape_integration_report)
    direct_modifier_evidence = _direct_modifier_execution_evidence(mesh)

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
                    "scan_limited": intersection_scan_limited,
                    "pair_budget": _MAX_SELF_INTERSECTION_PAIRS,
                    "face_scan_budget": _MAX_SELF_INTERSECTION_FACE_SCAN,
                    "scanned_face_rows": intersection_scanned_face_rows,
                    "total_face_rows": intersection_total_face_rows,
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

    if boolean_fallback["has_boolean_fallback"]:
        diagnostics.append(
            {
                "code": _BOOLEAN_FALLBACK_CODE,
                "name": "boolean_csg_fallback",
                "severity": "error" if geometry_strict else "warning",
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "path": "validate.geometry_integrity.boolean_csg_fallback",
                "message": (
                    "Geometry integrity detected a degraded boolean/kernel path; "
                    "fallback execution cannot silently certify a final asset claim"
                ),
                "details": {
                    "metric": "boolean_kernel_fallback_count",
                    **boolean_fallback,
                },
                "suggested_repairs": ["use_manifold_geometry_kernel", "repair_boolean_csg"],
            }
        )

    if int(direct_modifier_evidence["degraded_count"]) > 0:
        diagnostics.append(
            {
                "code": _DIRECT_MODIFIER_CODE,
                "name": "direct_modifier_degraded",
                "severity": "error" if geometry_strict else "warning",
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "path": "validate.geometry_integrity.direct_modifier_degraded",
                "message": (
                    "Geometry integrity detected ShapeIR v2 direct modifier(s) "
                    "that were unsupported, invalid, blocked, failed, or degraded"
                ),
                "details": {
                    "metric": "direct_modifier_degraded_count",
                    **direct_modifier_evidence,
                },
                "suggested_repairs": [
                    "repair_direct_modifier_parameters",
                    "lower_supported_shape_ir_v2_operation",
                    "use_supported_geometry_modifier",
                ],
            }
        )

    metrics = {
        "self_intersection_rate": round(float(intersection_rate), 6),
        "normal_consistency": round(float(normal_score), 6),
        "body_count_stability": round(float(body_stability), 6),
        "boolean_kernel_fallback_count": int(boolean_fallback["fallback_count"]),
        "direct_modifier_degraded_count": int(direct_modifier_evidence["degraded_count"]),
        "direct_modifier_attempted_count": int(direct_modifier_evidence["attempted_count"]),
    }

    evidence = {
        "evaluated": True,
        "intersecting_pairs": intersecting_pairs,
        "tested_pairs": tested_pairs,
        "self_intersection_scan_limited": bool(intersection_scan_limited),
        "self_intersection_pair_budget": int(_MAX_SELF_INTERSECTION_PAIRS),
        "self_intersection_face_scan_budget": int(_MAX_SELF_INTERSECTION_FACE_SCAN),
        "self_intersection_scanned_face_rows": int(intersection_scanned_face_rows),
        "self_intersection_total_face_rows": int(intersection_total_face_rows),
        "is_winding_consistent": bool(winding_ok),
        "inconsistent_edge_adjacencies": int(bad_edges),
        "edge_adjacencies": int(edge_pairs),
        "body_count_stability_check": body_count_stability_check,
        "observed_body_counts": body_counts,
        "boolean_fallback": boolean_fallback,
        "direct_modifier_execution": direct_modifier_evidence,
        "geometry_strict": geometry_strict,
    }

    return {
        "metrics": metrics,
        "evidence": evidence,
        "diagnostics": diagnostics,
    }
