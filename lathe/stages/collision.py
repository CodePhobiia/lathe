"""Deterministic convex-hull collision proxies (STAGE-2, V0.2 E3).

Uses trimesh's built-in ``convex_hull`` (scipy/qhull) which is deterministic
for a given point set. Produces:

- A single hull over the full mesh.
- Per-part hulls when the runtime mesh carries ``face_parts`` metadata.

V-HACD style concave decomposition is intentionally deferred (STAGE-2b). A
single convex hull per part is the research-findings-gpt.MD V0.2 MVP target.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

try:  # pragma: no cover - scipy is present when trimesh convex hull is available.
    from scipy.spatial import QhullError
except ImportError:  # pragma: no cover
    _QHULL_ERROR_TYPES: tuple[type[Exception], ...] = ()
else:
    _QHULL_ERROR_TYPES = (QhullError,)


_CONVEX_HULL_ERRORS = (ValueError, *_QHULL_ERROR_TYPES)


@dataclass
class ConvexProxy:
    """A named convex hull over a vertex subset."""

    name: str
    mesh: trimesh.Trimesh
    aabb_min: tuple[float, float, float]
    aabb_max: tuple[float, float, float]


def single_hull(mesh: trimesh.Trimesh) -> ConvexProxy:
    """Return one convex hull enclosing the entire mesh."""
    if len(mesh.vertices) == 0:
        empty = trimesh.Trimesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False
        )
        return ConvexProxy(name="hull", mesh=empty, aabb_min=(0.0, 0.0, 0.0), aabb_max=(0.0, 0.0, 0.0))
    hull = mesh.convex_hull
    # Ensure deterministic winding (outward normals).
    hull.fix_normals(multibody=False)
    bounds = hull.bounds
    return ConvexProxy(
        name="hull",
        mesh=hull,
        aabb_min=(float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])),
        aabb_max=(float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])),
    )


def per_part_hulls(
    mesh: trimesh.Trimesh,
    face_parts: list[str],
) -> list[ConvexProxy]:
    """Return one convex hull per unique part name in ``face_parts``.

    ``face_parts`` must align 1:1 with ``mesh.faces``. If it does not, returns
    a single hull named ``mesh``.
    """
    if len(face_parts) != len(mesh.faces) or not face_parts:
        proxy = single_hull(mesh)
        proxy.name = "mesh"
        return [proxy]

    results: list[ConvexProxy] = []
    faces = np.asarray(mesh.faces, dtype=np.int64)
    for part in sorted(set(face_parts)):
        face_mask = np.array([fp == part for fp in face_parts], dtype=bool)
        part_face_indices = faces[face_mask]
        if len(part_face_indices) == 0:
            continue
        used_verts = np.unique(part_face_indices.reshape(-1))
        if len(used_verts) < 4:
            continue
        part_points = mesh.vertices[used_verts]
        try:
            hull_mesh = trimesh.convex.convex_hull(part_points)
        except _CONVEX_HULL_ERRORS:
            continue
        if hull_mesh is None or len(hull_mesh.vertices) == 0:
            continue
        hull_mesh.fix_normals(multibody=False)
        bounds = hull_mesh.bounds
        results.append(
            ConvexProxy(
                name=str(part),
                mesh=hull_mesh,
                aabb_min=(float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])),
                aabb_max=(float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])),
            )
        )
    if not results:
        proxy = single_hull(mesh)
        proxy.name = "mesh"
        return [proxy]
    return results


def combine_hulls(proxies: list[ConvexProxy]) -> trimesh.Trimesh:
    """Merge per-part hulls into a single mesh (for GLB export).

    Deterministic order: proxies are merged in their list order. Vertex/face
    arrays are concatenated with face indices offset by cumulative vertex
    count.
    """
    if not proxies:
        return trimesh.Trimesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False
        )
    all_verts: list[np.ndarray] = []
    all_faces: list[np.ndarray] = []
    offset = 0
    for proxy in proxies:
        verts = np.asarray(proxy.mesh.vertices, dtype=np.float64)
        faces = np.asarray(proxy.mesh.faces, dtype=np.int64)
        all_verts.append(verts)
        all_faces.append(faces + offset)
        offset += len(verts)
    return trimesh.Trimesh(
        vertices=np.concatenate(all_verts, axis=0),
        faces=np.concatenate(all_faces, axis=0),
        process=False,
    )
