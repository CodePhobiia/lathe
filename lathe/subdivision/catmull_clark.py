"""Catmull-Clark subdivision (CPU reference implementation).

Implements the classical Catmull-Clark scheme (Catmull & Clark, 1978)
extended with semi-sharp creases (Hoppe, DeRose et al., 1994) and the
three boundary handling modes defined in :mod:`.boundary`.

Per refinement level we produce three buckets of new vertices:

* **face points**   --- one centroid per face.
* **edge points**   --- one per edge; for smooth interior edges this is
  the average of the two endpoint positions, the two adjacent face
  points and the edge midpoint. For sharp/crease edges (sharpness >= 1)
  the edge point is the geometric midpoint, preserving the cage edge.
  Semi-sharp creases (``0 < s < 1``) interpolate linearly between the
  smooth and sharp edge points.
* **vertex points** --- the original vertices repositioned by the
  classical mask ``(F + 2R + (n - 3) V) / n`` for interior valence-``n``
  vertices, where ``F`` is the average of incident face points and
  ``R`` the average of incident edge midpoints. Boundary and crease
  vertices are repositioned by the curve mask ``(c1 + 6 v + c2) / 8``
  using the two crease neighbours; corner-locked vertices keep their
  position.

The function returns a fresh :class:`~lathe.subdivision.mesh.SubdivMesh`
with quad faces only (n-gons in the input fan around their centroid).
The output is deterministic: face order mirrors the source-face
iteration order and within each face the four child quads always use
the canonical ``(prev_edge, vertex, next_edge, face_centroid)``
arrangement.
"""

from __future__ import annotations

from typing import Sequence

from .boundary import BoundaryRule, classify_boundary_edges
from .creases import INFINITE_CREASE, CreaseTags
from .mesh import SubdivMesh, Vec3


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def subdivide_catmull_clark(
    mesh: SubdivMesh,
    *,
    creases: CreaseTags | None = None,
    boundary: BoundaryRule = BoundaryRule.SMOOTH,
) -> SubdivMesh:
    """Apply one level of Catmull-Clark to ``mesh``.

    ``creases`` defaults to the empty set; boundary handling defaults
    to ``smooth``. The output is a quad-only mesh.
    """
    creases = creases or CreaseTags.empty()
    boundary_edges, boundary_vertices = classify_boundary_edges(mesh)

    # ------------------------------------------------------------------
    # 1. Effective per-edge sharpness (combining boundary policy + tags).
    # ------------------------------------------------------------------
    edge_sharp: list[float] = []
    for edge_idx, (a, b) in enumerate(mesh.edges):
        sharp = creases.edge_sharpness(a, b)
        if edge_idx in boundary_edges and boundary in (
            BoundaryRule.SHARP,
            BoundaryRule.CORNERS,
        ):
            sharp = INFINITE_CREASE
        edge_sharp.append(sharp)

    # ------------------------------------------------------------------
    # 2. Face points = centroids.
    # ------------------------------------------------------------------
    face_points: list[Vec3] = [mesh.face_centroid(i) for i in range(mesh.face_count())]

    # ------------------------------------------------------------------
    # 3. Edge points: smooth + sharp variants then crease-blend.
    # ------------------------------------------------------------------
    edge_points: list[Vec3] = []
    for edge_idx, (a, b) in enumerate(mesh.edges):
        midpoint = mesh.edge_midpoint(edge_idx)
        adj_faces = mesh.edge_faces[edge_idx]
        sharp = edge_sharp[edge_idx]
        if not adj_faces:
            edge_points.append(midpoint)
            continue
        if len(adj_faces) == 1:
            # Boundary edge under the SMOOTH rule -- still average the
            # endpoint and the lone face point so the surface eases off.
            f_avg = face_points[adj_faces[0]]
            smooth_point = _scale(_add(midpoint, f_avg), 0.5)
        else:
            f_sum = (0.0, 0.0, 0.0)
            for f_idx in adj_faces:
                f_sum = _add(f_sum, face_points[f_idx])
            f_avg = _scale(f_sum, 1.0 / len(adj_faces))
            smooth_point = _scale(_add(midpoint, f_avg), 0.5)
        if sharp <= 0:
            edge_points.append(smooth_point)
        elif sharp >= 1:
            # Fully sharp at this level (semi-sharp values >= 1 still
            # behave as crease for one more level; the caller attenuates
            # creases between iterations).
            edge_points.append(midpoint)
        else:
            edge_points.append(_lerp(smooth_point, midpoint, sharp))

    # ------------------------------------------------------------------
    # 4. Original vertex positions repositioned by the C-C masks.
    # ------------------------------------------------------------------
    new_vertex_positions: list[Vec3] = []
    for v_idx, position in enumerate(mesh.positions):
        sharp_edges_for_vertex = [
            e_idx
            for e_idx in mesh.vertex_edges[v_idx]
            if edge_sharp[e_idx] > 0
        ]
        sharp_edge_count = len(sharp_edges_for_vertex)
        corner_sharp = creases.corner_sharpness(v_idx)
        is_boundary_vertex = v_idx in boundary_vertices
        boundary_corner = (
            is_boundary_vertex
            and boundary is BoundaryRule.CORNERS
            and _is_open_corner(mesh, v_idx, boundary_edges)
        )

        if (
            corner_sharp >= INFINITE_CREASE
            or boundary_corner
            or sharp_edge_count >= 3
        ):
            # Locked corner: keep the cage position.
            new_vertex_positions.append(position)
            continue

        if sharp_edge_count == 2:
            # Crease curve mask: blend with the two opposite neighbours.
            neighbours = []
            for e_idx in sharp_edges_for_vertex:
                a, b = mesh.edges[e_idx]
                other = b if a == v_idx else a
                neighbours.append(mesh.positions[other])
            blended = _add(_scale(position, 6.0), _add(neighbours[0], neighbours[1]))
            new_vertex_positions.append(_scale(blended, 1.0 / 8.0))
            continue

        # Smooth interior vertex.
        f_sum = (0.0, 0.0, 0.0)
        for f_idx in mesh.vertex_faces[v_idx]:
            f_sum = _add(f_sum, face_points[f_idx])
        face_avg = _scale(f_sum, 1.0 / max(len(mesh.vertex_faces[v_idx]), 1))

        edge_mid_sum = (0.0, 0.0, 0.0)
        edge_count = 0
        for e_idx in mesh.vertex_edges[v_idx]:
            edge_mid_sum = _add(edge_mid_sum, mesh.edge_midpoint(e_idx))
            edge_count += 1
        edge_mid_avg = _scale(edge_mid_sum, 1.0 / max(edge_count, 1))

        n = max(len(mesh.vertex_faces[v_idx]), 1)
        # Standard Catmull-Clark vertex mask: (F + 2R + (n-3) v) / n.
        weighted = _add(
            face_avg,
            _add(_scale(edge_mid_avg, 2.0), _scale(position, max(n - 3, 0))),
        )
        new_vertex_positions.append(_scale(weighted, 1.0 / n))

    # ------------------------------------------------------------------
    # 5. Allocate new vertex indices: original verts || edge points || face points.
    # ------------------------------------------------------------------
    edge_offset = len(new_vertex_positions)
    new_positions: list[Vec3] = list(new_vertex_positions)
    new_positions.extend(edge_points)
    face_offset = len(new_positions)
    new_positions.extend(face_points)

    # ------------------------------------------------------------------
    # 6. Build child quads. Each face becomes ``len(face)`` quads:
    #    (vertex_i, edge(i,i+1), face_centroid, edge(i-1,i)).
    # ------------------------------------------------------------------
    new_faces: list[tuple[int, ...]] = []
    for face_idx, face in enumerate(mesh.faces):
        n_face = len(face)
        face_centre_idx = face_offset + face_idx
        edge_ids = mesh.face_edges[face_idx]
        for i in range(n_face):
            v_curr = face[i]
            e_next = edge_ids[i]
            e_prev = edge_ids[(i - 1) % n_face]
            new_faces.append(
                (
                    v_curr,
                    edge_offset + e_next,
                    face_centre_idx,
                    edge_offset + e_prev,
                )
            )

    return SubdivMesh.from_indexed(new_positions, new_faces)


def _is_open_corner(
    mesh: SubdivMesh, vertex_idx: int, boundary_edge_indices: set[int]
) -> bool:
    """A boundary vertex is a "corner" if exactly two boundary edges meet."""
    count = 0
    for e_idx in mesh.vertex_edges[vertex_idx]:
        if e_idx in boundary_edge_indices:
            count += 1
            if count > 2:
                return False
    return count == 2


def _accumulate(values: Sequence[Vec3]) -> Vec3:
    accum: Vec3 = (0.0, 0.0, 0.0)
    for v in values:
        accum = _add(accum, v)
    return accum


__all__ = ["subdivide_catmull_clark"]
