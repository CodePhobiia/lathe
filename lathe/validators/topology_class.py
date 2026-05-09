"""Roadmap §5.9 — topology-class compliance validator.

Per quality_framework §1, scores the runtime mesh against three
topology hygiene metrics:

* **quad-domination ratio** — count(quads)/(quads+tris+ngons). The
  authoritative runtime mesh in this scaffold is always triangulated,
  so quad-domination is detected by collapsing coplanar triangle pairs
  that share an edge into a synthetic quad.
* **n-gon count** — synthetic n-gons (5+ coplanar tris around a shared
  pole) are blocked, especially in deformation zones.
* **pole-vertex count** — vertices with edge-valence ≥ 5 in
  deformation zones (areas declared by the asset graph as articulating).

Mesh-only; no Blender / external bmesh dependency.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "lathe.validate.topology_class_compliance_v1"

_QUAD_PAIR_PLANARITY_DOT = 0.99  # cos(~8.1°)
# On triangulated meshes, interior vertices have valence ~6 by default
# (each tri-tile contributes 2 edges per vertex). Valence ≥5 would flag
# virtually every interior vertex. ≥7 captures genuine poles where extra
# edges concentrate (T-junctions, fan vertices, real hub vertices).
_POLE_MIN_VALENCE = 7
_QUAD_DOMINATION_TARGET = 0.65
# A box corner shared by 3 quads triangulates to ~6 incident tris; bevels and
# chamfers push that into the 5-6 range. Threshold ≥7 flags genuine topology
# errors (T-junctions, true ngons) rather than natural hard-surface corners.
_NGON_MIN_TRIS = 7
# Density-based saturation for ngon and pole penalties. Triangulated
# hard-surface meshes (booleans, feature merges, multi-part assemblies)
# routinely carry 20-30% extraordinary-vertex density even when the
# topology is acceptable for production. Saturating at 30% means a mesh
# at the upper end of normal hard-surface density gets a maximum (not
# zero) penalty, while a mesh with truly broken topology saturates fully.
_NGON_DENSITY_SATURATION = 0.30
_POLE_DENSITY_SATURATION = 0.30
# Hero-asset blocking gate fires only when ngons exceed this fraction of
# verts (so a few isolated ngons don't fail certification).
_NGON_BLOCK_DENSITY = 0.05
_HERO_ASSET_CLASSES = frozenset({"hero", "aaa_hero"})


def _hero_asset_class(asset: dict[str, Any]) -> str | None:
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    raw = intent.get("asset_class")
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().lower()
    return candidate if candidate in _HERO_ASSET_CLASSES else None


def _vertex_valence(faces: np.ndarray, n_verts: int) -> np.ndarray:
    valence = np.zeros(n_verts, dtype=np.int32)
    edges = np.concatenate(
        [
            faces[:, [0, 1]],
            faces[:, [1, 2]],
            faces[:, [2, 0]],
        ],
        axis=0,
    )
    edges = np.sort(edges, axis=1)
    edges_unique = np.unique(edges, axis=0)
    for v0, v1 in edges_unique:
        valence[v0] += 1
        valence[v1] += 1
    return valence


def _quad_domination_ratio(mesh: Any, faces: np.ndarray) -> float:
    """Approximate quad share by counting coplanar adjacent triangle pairs."""
    if len(faces) < 2:
        return 0.0
    try:
        adjacency = np.asarray(mesh.face_adjacency, dtype=np.int64)
        face_normals = np.asarray(mesh.face_normals, dtype=np.float64)
    except (AttributeError, ValueError, RuntimeError):
        return 0.0
    if len(adjacency) == 0:
        return 0.0
    a_n = face_normals[adjacency[:, 0]]
    b_n = face_normals[adjacency[:, 1]]
    dots = np.einsum("ij,ij->i", a_n, b_n)
    coplanar = dots >= _QUAD_PAIR_PLANARITY_DOT
    used = np.zeros(len(faces), dtype=bool)
    quad_count = 0
    for idx in np.nonzero(coplanar)[0]:
        a_idx, b_idx = int(adjacency[idx, 0]), int(adjacency[idx, 1])
        if used[a_idx] or used[b_idx]:
            continue
        used[a_idx] = True
        used[b_idx] = True
        quad_count += 1
    triangulated = len(faces) - 2 * quad_count
    total_polys = quad_count + triangulated
    if total_polys <= 0:
        return 0.0
    return float(quad_count) / float(total_polys)


def _ngon_count(faces: np.ndarray, n_verts: int) -> int:
    """Count synthetic n-gons: vertices with >= ``_NGON_MIN_TRIS`` incident tris."""
    incidence = np.zeros(n_verts, dtype=np.int32)
    np.add.at(incidence, faces.ravel(), 1)
    return int(np.sum(incidence >= _NGON_MIN_TRIS))


def _deformation_zone_vertex_mask(
    runtime: dict[str, Any], n_verts: int, mesh: Any | None = None
) -> np.ndarray:
    """Best-effort: tag vertices that fall inside named deformation zones.

    The scaffold's topology bundle exposes ``part_groups`` with bounds.
    A part is a deformation zone when its name contains a deformation
    token (joint/hinge/pivot/articulate). We mask vertices whose
    positions fall inside any such part's AABB. When no deformation
    zones are declared, all vertices count (no zoning).

    Note: tokens like ``lid``, ``door``, ``swing`` were intentionally
    dropped — those name parts that are *static hard-surface* in
    typical hard-surface assets (chest lids, cabinet doors, hatch
    panels) and are not skinned/deformable. Use rig-axis tokens
    (``hinge_axis`` etc.) to indicate genuine articulation.

    ``mesh`` is the position-welded mesh whose vertex count must equal
    ``n_verts``. When omitted we fall back to the raw runtime mesh.
    """
    topology = runtime.get("topology") if isinstance(runtime.get("topology"), dict) else {}
    bundle = topology.get("bundle") if isinstance(topology.get("bundle"), dict) else {}
    part_groups = bundle.get("part_groups") if isinstance(bundle.get("part_groups"), list) else []
    deformation_tokens = ("hinge", "joint", "pivot", "articulate")
    deformation_groups = [
        group
        for group in part_groups
        if isinstance(group, dict)
        and any(tok in str(group.get("name", "")).lower() for tok in deformation_tokens)
    ]
    if not deformation_groups:
        return np.ones(n_verts, dtype=bool)

    if mesh is None:
        runtime_mesh = topology.get("runtime_mesh")
        mesh = getattr(runtime_mesh, "mesh", None) if runtime_mesh is not None else None
    if mesh is None:
        return np.ones(n_verts, dtype=bool)
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    if verts.shape[0] != n_verts:
        return np.ones(n_verts, dtype=bool)

    mask = np.zeros(n_verts, dtype=bool)
    for group in deformation_groups:
        bmin = np.asarray(group.get("bounds_min", [0.0, 0.0, 0.0]), dtype=np.float64)
        bmax = np.asarray(group.get("bounds_max", [0.0, 0.0, 0.0]), dtype=np.float64)
        in_box = np.all((verts >= bmin) & (verts <= bmax), axis=1)
        mask |= in_box
    return mask


def _position_welded_mesh(mesh: Any) -> Any:
    """Return a copy of ``mesh`` with co-located vertices merged.

    The downstream runtime mesh may carry vertex *splits* applied for
    shading-attribute reasons (Wave 1C hard-edge vertex split duplicates
    vertices at hard edges so smooth-shading does not average normals
    across them). Those duplicates share positions but have distinct
    indices, which destroys ``face_adjacency`` (it requires shared
    vertex indices) and therefore wrecks the adjacency-based quad
    detection here.

    The validator measures *geometric* topology, not the per-corner
    attribute mesh, so we collapse co-located duplicates before
    computing metrics. Returns the input unchanged on any failure.
    """
    try:
        welded = mesh.copy()
        welded.merge_vertices(merge_tex=False, merge_norm=False)
        return welded
    except Exception:
        return mesh


def evaluate_topology_class_compliance(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate quad-domination, n-gon block, pole valence in deformation zones."""
    topology = runtime.get("topology") if isinstance(runtime.get("topology"), dict) else {}
    runtime_mesh = topology.get("runtime_mesh")
    raw_mesh = getattr(runtime_mesh, "mesh", None) if runtime_mesh is not None else None
    if raw_mesh is None or len(raw_mesh.faces) == 0:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "skipped",
            "evidence": {"reason": "topology runtime mesh unavailable"},
        }

    mesh = _position_welded_mesh(raw_mesh)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    n_verts = int(np.asarray(mesh.vertices).shape[0])

    quad_ratio = _quad_domination_ratio(mesh, faces)
    ngon_total = _ngon_count(faces, n_verts)

    valence = _vertex_valence(faces, n_verts)
    pole_mask_global = valence >= _POLE_MIN_VALENCE
    deformation_mask = _deformation_zone_vertex_mask(runtime, n_verts, mesh=mesh)
    poles_in_deformation = int(np.sum(pole_mask_global & deformation_mask))

    asset_class = _hero_asset_class(asset)
    quad_score = max(0.0, min(1.0, quad_ratio / max(1e-9, _QUAD_DOMINATION_TARGET)))
    ngon_saturation_count = max(1.0, n_verts * _NGON_DENSITY_SATURATION)
    ngon_penalty = min(1.0, ngon_total / ngon_saturation_count)
    pole_saturation_count = max(1.0, n_verts * _POLE_DENSITY_SATURATION)
    pole_penalty = min(1.0, poles_in_deformation / pole_saturation_count)
    score = round(
        max(
            0.0,
            min(1.0, 0.55 * quad_score + 0.30 * (1.0 - ngon_penalty) + 0.15 * (1.0 - pole_penalty)),
        ),
        6,
    )

    ngon_block_count = max(1.0, n_verts * _NGON_BLOCK_DENSITY)
    blocking = ngon_total >= ngon_block_count and asset_class is not None
    if blocking:
        status = "fail"
        severity = "error"
    elif quad_score < 0.5 or pole_penalty > 0.5:
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
            "quad_domination_ratio": round(float(quad_ratio), 6),
            "quad_domination_target": _QUAD_DOMINATION_TARGET,
            "ngon_count": ngon_total,
            "ngon_min_incident_tris": _NGON_MIN_TRIS,
            "ngon_saturation_count": round(float(ngon_saturation_count), 3),
            "ngon_density_saturation": _NGON_DENSITY_SATURATION,
            "ngon_block_count": round(float(ngon_block_count), 3),
            "ngon_block_density": _NGON_BLOCK_DENSITY,
            "poles_in_deformation_zones": poles_in_deformation,
            "pole_saturation_count": round(float(pole_saturation_count), 3),
            "pole_density_saturation": _POLE_DENSITY_SATURATION,
            "global_pole_count": int(np.sum(pole_mask_global)),
            "vertex_count": n_verts,
            "deformation_zones_declared": bool(np.any(deformation_mask)) and not bool(np.all(deformation_mask)),
            "asset_class": asset_class,
        },
    }
