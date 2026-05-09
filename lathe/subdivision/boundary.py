"""Boundary handling rules for the subdivision finishing pass.

Subdivision schemes need explicit policy at mesh boundaries because
those edges only have one adjacent face (so the standard "blend in two
adjacent face points" formula does not apply). We expose three modes
that match common DCC practice:

* ``smooth``  -- the legacy "edges and only corners" treatment: boundary
  edges interpolate purely from their endpoints, corner vertices use
  the (1/8, 6/8, 1/8) curve mask. Surface stays C^1 except at corners.
* ``sharp``  -- treat every boundary edge as if it carried an infinite
  crease; the boundary becomes a piecewise-linear chain pinned to the
  cage. Useful for chest lids, panels and trim sheets.
* ``corners`` -- mid-point: boundary edges stay sharp but interior
  vertices reached *through* the boundary are still smoothed. Match
  Maya's "Smooth (Crease All)" boundary mode.

The classifier :func:`classify_boundary_edges` walks a mesh once and
records which edge indices belong to the boundary so subdivision steps
can branch without paying the per-edge dispatch cost.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mesh import SubdivMesh


class BoundaryRule(str, Enum):
    """Boundary handling policy for subdivision."""

    SMOOTH = "smooth"
    SHARP = "sharp"
    CORNERS = "corners"

    @classmethod
    def from_text(cls, text: str) -> "BoundaryRule":
        """Parse a boundary rule from authored text."""
        normalised = text.lower().strip().replace("-", "_").replace(" ", "_")
        aliases = {
            "smooth": cls.SMOOTH,
            "always_sharp": cls.SHARP,
            "sharp": cls.SHARP,
            "edge_and_corner": cls.SHARP,
            "corners": cls.CORNERS,
            "edge_only": cls.SMOOTH,
            "open_smooth": cls.SMOOTH,
        }
        if normalised not in aliases:
            raise ValueError(f"unknown boundary rule: {text!r}")
        return aliases[normalised]


def classify_boundary_edges(mesh: "SubdivMesh") -> tuple[set[int], set[int]]:
    """Return ``(boundary_edge_indices, boundary_vertex_indices)``."""
    boundary_edges: set[int] = set()
    boundary_vertices: set[int] = set()
    for edge_idx, faces in enumerate(mesh.edge_faces):
        if len(faces) >= 2:
            continue
        boundary_edges.add(edge_idx)
        a, b = mesh.edges[edge_idx]
        boundary_vertices.add(a)
        boundary_vertices.add(b)
    return boundary_edges, boundary_vertices


__all__ = ["BoundaryRule", "classify_boundary_edges"]
