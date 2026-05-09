"""Pre-subdivision sanity checks.

The subdivision schemes assume the input cage is a *non-degenerate
polygon mesh*: faces have at least three vertices, every edge has at
least one adjacent face, no vertex appears twice in a face, and there
are no zero-length edges. We do not require manifoldness because the
boundary handling rule already covers the open-mesh case, but we do
flag obviously bad inputs early so the algorithms below never silently
produce NaN positions.
"""

from __future__ import annotations

from math import sqrt

from .mesh import SubdivMesh


class SubdivisionValidationError(ValueError):
    """Raised by :func:`validate_for_subdivision` when the cage is unfit."""


def validate_for_subdivision(
    mesh: SubdivMesh,
    *,
    require_manifold: bool = False,
    epsilon: float = 1e-9,
) -> dict[str, object]:
    """Verify ``mesh`` is suitable as a subdivision cage.

    Returns a small report dict with mesh statistics (face/edge/vertex
    counts, boundary edge count, max non-manifold valence). Raises
    :class:`SubdivisionValidationError` if any hard precondition is
    violated. ``require_manifold=True`` upgrades non-manifold edges
    from a soft warning to a hard error.
    """
    if mesh.face_count() == 0:
        raise SubdivisionValidationError("mesh has no faces")
    if mesh.vertex_count() == 0:
        raise SubdivisionValidationError("mesh has no vertices")

    for face_idx, face in enumerate(mesh.faces):
        if len(face) < 3:
            raise SubdivisionValidationError(
                f"face {face_idx} has fewer than 3 vertices"
            )
        if len(set(face)) != len(face):
            raise SubdivisionValidationError(
                f"face {face_idx} repeats a vertex: {face}"
            )

    for edge_idx, (a, b) in enumerate(mesh.edges):
        ax, ay, az = mesh.positions[a]
        bx, by, bz = mesh.positions[b]
        length = sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
        if length <= epsilon:
            raise SubdivisionValidationError(
                f"edge {edge_idx} has zero length between {a} and {b}"
            )

    boundary_count = 0
    nonmanifold_count = 0
    for faces in mesh.edge_faces:
        if len(faces) == 1:
            boundary_count += 1
        elif len(faces) > 2:
            nonmanifold_count += 1

    if require_manifold and nonmanifold_count:
        raise SubdivisionValidationError(
            f"mesh has {nonmanifold_count} non-manifold edges"
        )

    return {
        "vertex_count": mesh.vertex_count(),
        "edge_count": mesh.edge_count(),
        "face_count": mesh.face_count(),
        "boundary_edge_count": boundary_count,
        "nonmanifold_edge_count": nonmanifold_count,
        "is_quad_only": mesh.is_quad_only(),
        "is_triangle_only": mesh.is_triangle_only(),
    }


__all__ = ["SubdivisionValidationError", "validate_for_subdivision"]
