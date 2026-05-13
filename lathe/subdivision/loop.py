"""Loop subdivision for triangle meshes.

Implements Charles Loop's 1987 scheme:

* Each triangle is replaced by four triangles. Three of them sit at the
  corners and use the original vertex plus the two adjacent edge points;
  the fourth is the central triangle made of the three edge points.
* Edge points are weighted ``(3/8) * (a + b) + (1/8) * (c + d)`` for an
  interior edge whose endpoints are ``a, b`` and whose two opposite
  vertices (one per adjacent triangle) are ``c, d``. Boundary edges
  fall back to the simple midpoint.
* Original vertices are repositioned by the Loop mask
  ``(1 - n*beta) * v + beta * sum(neighbours)`` where ``beta`` is the
  Warren constant ``3 / (8 n)`` for ``n >= 3`` and ``3/16`` for
  ``n == 3``. Boundary/sharp-crease vertices fall through to the curve
  mask ``(c1 + 6 v + c2) / 8``.

Crease handling mirrors the Catmull-Clark path: edges with sharpness
>= 1 are kept at their midpoint and vertices touched by exactly two
sharp edges are repositioned along the crease curve.
"""

from __future__ import annotations

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


def _opposite_vertex(face: tuple[int, ...], a: int, b: int) -> int:
    for v in face:
        if v not in (a, b):
            return v
    raise ValueError(f"face {face} has no opposite to edge ({a}, {b})")


def subdivide_loop(
    mesh: SubdivMesh,
    *,
    creases: CreaseTags | None = None,
    boundary: BoundaryRule = BoundaryRule.SMOOTH,
) -> SubdivMesh:
    """Apply one level of Loop subdivision.

    The input mesh must be triangle-only; the function raises a
    :class:`ValueError` otherwise so the caller can fall back to
    Catmull-Clark for quad meshes.
    """
    if not mesh.is_triangle_only():
        raise ValueError("Loop subdivision requires a triangle mesh")
    creases = creases or CreaseTags.empty()
    boundary_edges, boundary_vertices = classify_boundary_edges(mesh)

    # --- effective per-edge sharpness ---------------------------------
    edge_sharp: list[float] = []
    for edge_idx, (a, b) in enumerate(mesh.edges):
        sharp = creases.edge_sharpness(a, b)
        if edge_idx in boundary_edges and boundary in (
            BoundaryRule.SHARP,
            BoundaryRule.CORNERS,
        ):
            sharp = INFINITE_CREASE
        edge_sharp.append(sharp)

    # --- edge points ---------------------------------------------------
    edge_points: list[Vec3] = []
    for edge_idx, (a, b) in enumerate(mesh.edges):
        midpoint = mesh.edge_midpoint(edge_idx)
        adj_faces = mesh.edge_faces[edge_idx]
        sharp = edge_sharp[edge_idx]
        if not adj_faces or len(adj_faces) == 1 or sharp >= 1:
            if sharp > 0 and sharp < 1:
                # interior edge that is semi-sharp: blend smooth/sharp.
                # We need the smooth variant first, fall through after.
                pass
            else:
                edge_points.append(midpoint)
                continue
        # Smooth Loop edge mask.
        ax, ay, az = mesh.positions[a]
        bx, by, bz = mesh.positions[b]
        endpoint_term = ((ax + bx) * 3.0 / 8.0, (ay + by) * 3.0 / 8.0, (az + bz) * 3.0 / 8.0)
        opposite_sum: Vec3 = (0.0, 0.0, 0.0)
        for f_idx in adj_faces:
            opp = _opposite_vertex(mesh.faces[f_idx], a, b)
            opposite_sum = _add(opposite_sum, mesh.positions[opp])
        opposite_term = _scale(opposite_sum, 1.0 / 8.0)
        smooth_point = _add(endpoint_term, opposite_term)
        if sharp <= 0:
            edge_points.append(smooth_point)
        else:
            edge_points.append(_lerp(smooth_point, midpoint, sharp))

    # --- repositioned vertex points ------------------------------------
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
            new_vertex_positions.append(position)
            continue

        if sharp_edge_count == 2:
            neighbours = []
            for e_idx in sharp_edges_for_vertex:
                a, b = mesh.edges[e_idx]
                other = b if a == v_idx else a
                neighbours.append(mesh.positions[other])
            blended = _add(_scale(position, 6.0), _add(neighbours[0], neighbours[1]))
            new_vertex_positions.append(_scale(blended, 1.0 / 8.0))
            continue

        neighbour_indices = []
        for e_idx in mesh.vertex_edges[v_idx]:
            a, b = mesh.edges[e_idx]
            neighbour_indices.append(b if a == v_idx else a)
        n = len(neighbour_indices)
        if n == 0:
            new_vertex_positions.append(position)
            continue
        beta = 3.0 / 16.0 if n == 3 else 3.0 / (8.0 * n)
        neighbour_sum: Vec3 = (0.0, 0.0, 0.0)
        for nb in neighbour_indices:
            neighbour_sum = _add(neighbour_sum, mesh.positions[nb])
        smoothed = _add(
            _scale(position, 1.0 - n * beta),
            _scale(neighbour_sum, beta),
        )
        new_vertex_positions.append(smoothed)

    # --- assemble new mesh ---------------------------------------------
    edge_offset = len(new_vertex_positions)
    new_positions: list[Vec3] = list(new_vertex_positions) + list(edge_points)
    new_faces: list[tuple[int, ...]] = []
    for _face_idx, face in enumerate(mesh.faces):
        v0, v1, v2 = face
        e01 = edge_offset + mesh.edge_lookup(v0, v1)  # type: ignore[operator]
        e12 = edge_offset + mesh.edge_lookup(v1, v2)  # type: ignore[operator]
        e20 = edge_offset + mesh.edge_lookup(v2, v0)  # type: ignore[operator]
        new_faces.append((v0, e01, e20))
        new_faces.append((v1, e12, e01))
        new_faces.append((v2, e20, e12))
        new_faces.append((e01, e12, e20))

    return SubdivMesh.from_indexed(new_positions, new_faces)


def _is_open_corner(
    mesh: SubdivMesh, vertex_idx: int, boundary_edge_indices: set[int]
) -> bool:
    count = 0
    for e_idx in mesh.vertex_edges[vertex_idx]:
        if e_idx in boundary_edge_indices:
            count += 1
            if count > 2:
                return False
    return count == 2


__all__ = ["subdivide_loop"]
