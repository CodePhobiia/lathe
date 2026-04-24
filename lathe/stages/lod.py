"""Deterministic LOD decimation (STAGE-1, V0.2 E3).

Implements quadric-error-metric (Garland-Heckbert) edge-collapse decimation in
pure NumPy. Fully deterministic: given the same input mesh and target ratio,
produces the same output vertex/face arrays (and therefore the same GLB byte
hash when serialized via trimesh).

Public API:
    decimate(mesh, ratio) -> trimesh.Trimesh
    build_lods(mesh, ratios) -> list[LODResult]

Design notes:
- ``ratio`` is the fraction of *faces* to keep. Ratio 1.0 returns a copy of the
  input. Ratio 0.5 targets 50% of the original face count.
- All floating-point ops use float64. All ties are broken deterministically by
  element index, never by Python set/dict iteration order.
- No external C libraries required (``fast_simplification`` / ``open3d`` /
  ``pymeshlab``) — keeps the deterministic contract portable across platforms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import heapq
import numpy as np
import trimesh


@dataclass
class LODResult:
    """Result of a single LOD decimation."""

    level: int
    ratio: float
    mesh: trimesh.Trimesh
    tris: int
    verts: int


def _plane_quadric(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    """Plane-equation quadric (4x4) for the triangle (p0,p1,p2).

    Plane is ax+by+cz+d=0 with unit normal. Quadric is K = [a,b,c,d]^T [a,b,c,d].
    Degenerate triangles (zero area) contribute the zero matrix.
    """

    normal = np.cross(p1 - p0, p2 - p0)
    length = float(np.linalg.norm(normal))
    if length < 1e-18:
        return np.zeros((4, 4), dtype=np.float64)
    normal = normal / length
    d = -float(np.dot(normal, p0))
    plane = np.array([normal[0], normal[1], normal[2], d], dtype=np.float64)
    return np.outer(plane, plane)


def _collapse_cost(q_sum: np.ndarray, v_target: np.ndarray) -> float:
    """Evaluate v^T Q v for candidate vertex ``v_target`` under quadric ``q_sum``."""

    vec = np.array([v_target[0], v_target[1], v_target[2], 1.0], dtype=np.float64)
    return float(vec @ q_sum @ vec)


def _best_collapse_position(q_sum: np.ndarray, p0: np.ndarray, p1: np.ndarray) -> np.ndarray:
    """Return optimal collapse point under quadric ``q_sum``.

    Solves the 3x3 linear system derived from the top-left of ``q_sum``.
    Falls back to edge midpoint when the system is singular.
    """

    a = q_sum.copy()
    a[3, :] = [0.0, 0.0, 0.0, 1.0]
    try:
        solved = np.linalg.solve(a, np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64))
        return solved[:3]
    except np.linalg.LinAlgError:
        return 0.5 * (p0 + p1)


def decimate(mesh: trimesh.Trimesh, ratio: float) -> trimesh.Trimesh:
    """Decimate ``mesh`` to approximately ``ratio * len(faces)`` triangles.

    Deterministic: identical inputs produce identical outputs. Empty or
    near-empty meshes are returned as a trimesh copy without modification.
    """

    if ratio >= 0.9999:
        return mesh.copy()

    verts = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    n_faces = int(len(faces))
    if n_faces == 0:
        return mesh.copy()

    target_faces = max(4, int(round(ratio * n_faces)))
    if target_faces >= n_faces:
        return mesh.copy()

    n_verts = int(len(verts))
    vert_alive = np.ones(n_verts, dtype=bool)
    face_alive = np.ones(n_faces, dtype=bool)

    # Per-vertex quadric: sum of incident face plane quadrics.
    quadrics = np.zeros((n_verts, 4, 4), dtype=np.float64)
    for fi in range(n_faces):
        a, b, c = faces[fi]
        q = _plane_quadric(verts[a], verts[b], verts[c])
        quadrics[a] += q
        quadrics[b] += q
        quadrics[c] += q

    vert_faces: list[set[int]] = [set() for _ in range(n_verts)]
    for fi in range(n_faces):
        a, b, c = faces[fi]
        vert_faces[a].add(fi)
        vert_faces[b].add(fi)
        vert_faces[c].add(fi)

    # Canonical edge set — deterministic iteration order via sorted tuples.
    edge_set: set[tuple[int, int]] = set()
    for fi in range(n_faces):
        a, b, c = faces[fi]
        for u, v in ((a, b), (b, c), (a, c)):
            key = (int(min(u, v)), int(max(u, v)))
            edge_set.add(key)

    # Priority queue entries: (cost, tie_counter, u, v, version_u, version_v).
    # Tie-counter is incremented on insertion to guarantee deterministic ordering
    # when two edges share the same cost.
    vert_version = np.zeros(n_verts, dtype=np.int64)
    heap: list[tuple[float, int, int, int, int, int]] = []
    counter = 0

    def push_edge(u: int, v: int) -> None:
        nonlocal counter
        if not vert_alive[u] or not vert_alive[v]:
            return
        q_sum = quadrics[u] + quadrics[v]
        target = _best_collapse_position(q_sum, verts[u], verts[v])
        cost = _collapse_cost(q_sum, target)
        heapq.heappush(
            heap,
            (
                float(cost),
                counter,
                int(u),
                int(v),
                int(vert_version[u]),
                int(vert_version[v]),
            ),
        )
        counter += 1

    for u, v in sorted(edge_set):
        push_edge(u, v)

    current_faces = n_faces
    while current_faces > target_faces and heap:
        cost, _tie, u, v, ver_u, ver_v = heapq.heappop(heap)
        if not vert_alive[u] or not vert_alive[v]:
            continue
        if ver_u != int(vert_version[u]) or ver_v != int(vert_version[v]):
            continue

        q_sum = quadrics[u] + quadrics[v]
        new_pos = _best_collapse_position(q_sum, verts[u], verts[v])

        # Reject collapses that would flip any face normal of v's neighborhood.
        if _would_flip(verts, faces, face_alive, vert_faces, u, v, new_pos):
            # Penalize and reinsert — deterministic: cost+large bias, same counter path.
            heapq.heappush(heap, (cost + 1e12, counter, u, v, ver_u, ver_v))
            counter += 1
            # Break out if we've looped too many times without progress.
            if counter > n_faces * 50:
                break
            continue

        # Collapse v into u: move u to new_pos, merge v's adjacencies.
        verts[u] = new_pos
        quadrics[u] = q_sum
        vert_version[u] += 1
        vert_alive[v] = False

        affected_faces = sorted(vert_faces[u] | vert_faces[v])
        touched_verts: set[int] = set()
        for fi in affected_faces:
            if not face_alive[fi]:
                continue
            tri = faces[fi]
            for k in range(3):
                touched_verts.add(int(tri[k]))
            for k in range(3):
                if tri[k] == v:
                    tri[k] = u
            if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
                face_alive[fi] = False
                current_faces -= 1
            else:
                faces[fi] = tri

        # Rebuild vert_faces entries for every vertex touched by affected faces.
        for vi in sorted(touched_verts):
            vert_faces[vi] = {fi for fi in vert_faces[vi] if face_alive[fi]}
        # u now also owns any of v's still-live faces.
        vert_faces[u] = {fi for fi in (vert_faces[u] | vert_faces[v]) if face_alive[fi]}
        vert_faces[v] = set()

        # Reinsert edges incident to u.
        neighbor_verts: set[int] = set()
        for fi in sorted(vert_faces[u]):
            if not face_alive[fi]:
                continue
            for k in faces[fi]:
                nk = int(k)
                if nk != u and vert_alive[nk]:
                    neighbor_verts.add(nk)
        for nk in sorted(neighbor_verts):
            push_edge(u, nk)

    return _rebuild_mesh(verts, faces, vert_alive, face_alive)


def _would_flip(
    verts: np.ndarray,
    faces: np.ndarray,
    face_alive: np.ndarray,
    vert_faces: list[set[int]],
    u: int,
    v: int,
    new_pos: np.ndarray,
) -> bool:
    """True if moving u->new_pos (with v merged into u) would flip any face normal.

    Vectorized over affected faces for speed.
    """

    affected_all = list(vert_faces[u] | vert_faces[v])
    if not affected_all:
        return False
    affected_arr = np.fromiter((fi for fi in affected_all if face_alive[fi]), dtype=np.int64)
    if affected_arr.size == 0:
        return False
    tris = faces[affected_arr]
    # Skip faces that are entirely within the edge uv (they'll collapse away).
    uv_mask = (tris == u) | (tris == v)
    uv_count = uv_mask.sum(axis=1)
    keep_mask = uv_count < 2
    if not np.any(keep_mask):
        return False
    tris = tris[keep_mask]

    p0 = verts[tris[:, 0]]
    p1 = verts[tris[:, 1]]
    p2 = verts[tris[:, 2]]
    n_old = np.cross(p1 - p0, p2 - p0)

    new_p0 = np.where(((tris[:, 0:1] == u) | (tris[:, 0:1] == v)), new_pos[None, :], p0)
    new_p1 = np.where(((tris[:, 1:2] == u) | (tris[:, 1:2] == v)), new_pos[None, :], p1)
    new_p2 = np.where(((tris[:, 2:3] == u) | (tris[:, 2:3] == v)), new_pos[None, :], p2)
    n_new = np.cross(new_p1 - new_p0, new_p2 - new_p0)

    old_len = np.linalg.norm(n_old, axis=1)
    new_len = np.linalg.norm(n_new, axis=1)
    valid = (old_len > 1e-18) & (new_len > 1e-18)
    if not np.any(valid):
        return False
    dots = np.einsum("ij,ij->i", n_old[valid], n_new[valid]) / (old_len[valid] * new_len[valid])
    return bool(np.any(dots < 0.1))


def _rebuild_mesh(
    verts: np.ndarray,
    faces: np.ndarray,
    vert_alive: np.ndarray,
    face_alive: np.ndarray,
) -> trimesh.Trimesh:
    """Rebuild a clean trimesh.Trimesh from the live vertex/face subset.

    Reindexing is deterministic: live vertices are renumbered in ascending
    original-index order.
    """

    live_vert_ids = np.nonzero(vert_alive)[0]
    remap = -np.ones(len(verts), dtype=np.int64)
    remap[live_vert_ids] = np.arange(len(live_vert_ids), dtype=np.int64)
    new_verts = verts[live_vert_ids]

    live_face_ids = np.nonzero(face_alive)[0]
    live_faces = faces[live_face_ids]
    new_faces = remap[live_faces]
    # Drop any accidental degenerate faces from the remap.
    mask = (new_faces[:, 0] != new_faces[:, 1]) & (new_faces[:, 1] != new_faces[:, 2]) & (new_faces[:, 0] != new_faces[:, 2])
    new_faces = new_faces[mask]

    mesh = trimesh.Trimesh(vertices=new_verts, faces=new_faces, process=False)
    # Deterministic post-cleanup: remove unreferenced verts (no-op here because
    # we already compacted), and normalize winding if degenerate faces appeared.
    mesh.remove_unreferenced_vertices()
    return mesh


def build_lods(mesh: trimesh.Trimesh, ratios: Iterable[float]) -> list[LODResult]:
    """Build LOD chain for the given ratios.

    Edge cases:
    - Empty input mesh: returns a single LOD0 pointing to the empty mesh.
    - Ratios are used as-is (not sorted) so callers can request e.g. [1.0,
      0.5, 0.25, 0.1] and receive LOD0..LOD3 in order.
    """

    ratios_list = list(ratios)
    results: list[LODResult] = []
    if len(mesh.faces) == 0:
        results.append(
            LODResult(level=0, ratio=1.0, mesh=mesh.copy(), tris=0, verts=int(len(mesh.vertices)))
        )
        return results

    for idx, raw_ratio in enumerate(ratios_list):
        ratio = max(0.01, min(1.0, float(raw_ratio)))
        lod_mesh = decimate(mesh, ratio)
        results.append(
            LODResult(
                level=idx,
                ratio=ratio,
                mesh=lod_mesh,
                tris=int(len(lod_mesh.faces)),
                verts=int(len(lod_mesh.vertices)),
            )
        )
    return results
