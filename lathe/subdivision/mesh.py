"""Indexed-face mesh used by the subdivision finishing pass.

This module purposefully avoids depending on :mod:`trimesh` so the
algorithms can run without the heavy executor stack imported. A small
helper, :func:`mesh_to_arrays`, converts results back into the flat
``(positions, faces)`` representation downstream stages expect.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]
Edge = tuple[int, int]
Face = tuple[int, ...]


def _canon_edge(a: int, b: int) -> Edge:
    """Return ``(a, b)`` ordered so the smaller index comes first."""
    return (a, b) if a <= b else (b, a)


@dataclass
class SubdivMesh:
    """Minimal indexed-face mesh with derived edge/adjacency tables.

    Instances are immutable from the algorithm's point of view: the
    subdivision routines build a new mesh rather than mutating in place.
    Faces may have any vertex count >= 3 (Catmull-Clark handles n-gons by
    splitting them into N quads through their centroid).
    """

    positions: list[Vec3]
    faces: list[Face]
    edges: list[Edge] = field(default_factory=list)
    edge_index: dict[Edge, int] = field(default_factory=dict)
    face_edges: list[tuple[int, ...]] = field(default_factory=list)
    edge_faces: list[list[int]] = field(default_factory=list)
    vertex_faces: list[list[int]] = field(default_factory=list)
    vertex_edges: list[list[int]] = field(default_factory=list)

    @classmethod
    def from_indexed(
        cls,
        positions: Iterable[Sequence[float]],
        faces: Iterable[Sequence[int]],
    ) -> SubdivMesh:
        """Build a :class:`SubdivMesh` from raw ``positions``/``faces``."""
        pos_list: list[Vec3] = []
        for p in positions:
            if len(p) != 3:
                raise ValueError(f"positions must be 3-tuples, got {p!r}")
            pos_list.append((float(p[0]), float(p[1]), float(p[2])))
        face_list: list[Face] = []
        for face in faces:
            indices = tuple(int(i) for i in face)
            if len(indices) < 3:
                raise ValueError(f"face has fewer than 3 vertices: {face!r}")
            for idx in indices:
                if not 0 <= idx < len(pos_list):
                    raise ValueError(f"face index {idx} out of range")
            face_list.append(indices)
        mesh = cls(positions=pos_list, faces=face_list)
        mesh._rebuild_topology()
        return mesh

    def copy(self) -> SubdivMesh:
        """Return a structural copy of the mesh."""
        return SubdivMesh.from_indexed(self.positions, self.faces)

    def _rebuild_topology(self) -> None:
        edges: list[Edge] = []
        edge_index: dict[Edge, int] = {}
        face_edges: list[tuple[int, ...]] = []
        edge_faces: list[list[int]] = []
        vertex_faces: list[list[int]] = [[] for _ in self.positions]
        vertex_edges: list[list[int]] = [[] for _ in self.positions]

        for face_idx, face in enumerate(self.faces):
            for v in face:
                vertex_faces[v].append(face_idx)
            indices: list[int] = []
            for i, v in enumerate(face):
                w = face[(i + 1) % len(face)]
                if v == w:
                    raise ValueError(
                        f"degenerate edge in face {face_idx}: ({v}, {w})"
                    )
                key = _canon_edge(v, w)
                e_idx = edge_index.get(key)
                if e_idx is None:
                    e_idx = len(edges)
                    edge_index[key] = e_idx
                    edges.append(key)
                    edge_faces.append([])
                    vertex_edges[key[0]].append(e_idx)
                    vertex_edges[key[1]].append(e_idx)
                edge_faces[e_idx].append(face_idx)
                indices.append(e_idx)
            face_edges.append(tuple(indices))

        for face_list in vertex_faces:
            face_list.sort()
        for edge_list in vertex_edges:
            edge_list.sort()

        self.edges = edges
        self.edge_index = edge_index
        self.face_edges = face_edges
        self.edge_faces = edge_faces
        self.vertex_faces = vertex_faces
        self.vertex_edges = vertex_edges

    def edge_lookup(self, a: int, b: int) -> int | None:
        """Return the edge index for the unordered pair ``(a, b)``."""
        return self.edge_index.get(_canon_edge(a, b))

    def is_boundary_edge(self, edge_idx: int) -> bool:
        """``True`` when the edge belongs to fewer than two faces."""
        return len(self.edge_faces[edge_idx]) < 2

    def face_centroid(self, face_idx: int) -> Vec3:
        """Average of a face's vertex positions (deterministic)."""
        face = self.faces[face_idx]
        sx = sy = sz = 0.0
        for v in face:
            x, y, z = self.positions[v]
            sx += x
            sy += y
            sz += z
        n = float(len(face))
        return (sx / n, sy / n, sz / n)

    def edge_midpoint(self, edge_idx: int) -> Vec3:
        """Geometric midpoint of edge ``edge_idx``."""
        a, b = self.edges[edge_idx]
        ax, ay, az = self.positions[a]
        bx, by, bz = self.positions[b]
        return (0.5 * (ax + bx), 0.5 * (ay + by), 0.5 * (az + bz))

    def vertex_count(self) -> int:
        """Number of vertices."""
        return len(self.positions)

    def face_count(self) -> int:
        """Number of faces."""
        return len(self.faces)

    def edge_count(self) -> int:
        """Number of unique undirected edges."""
        return len(self.edges)

    def is_quad_only(self) -> bool:
        """``True`` iff every face has exactly four vertices."""
        return all(len(face) == 4 for face in self.faces)

    def is_triangle_only(self) -> bool:
        """``True`` iff every face has exactly three vertices."""
        return all(len(face) == 3 for face in self.faces)


def mesh_from_arrays(
    positions: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
) -> SubdivMesh:
    """Convenience wrapper around :meth:`SubdivMesh.from_indexed`."""
    return SubdivMesh.from_indexed(positions, faces)


def mesh_to_arrays(mesh: SubdivMesh) -> tuple[list[Vec3], list[tuple[int, ...]]]:
    """Return the flat ``(positions, faces)`` representation."""
    return list(mesh.positions), list(mesh.faces)


__all__ = [
    "Edge",
    "Face",
    "SubdivMesh",
    "Vec3",
    "mesh_from_arrays",
    "mesh_to_arrays",
]
