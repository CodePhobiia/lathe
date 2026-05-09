"""Bridge between :class:`SubdivMesh` and the executor's RuntimeMesh.

The executor pipeline carries triangulated :class:`trimesh.Trimesh`
buffers. Catmull-Clark output is quad-only; Loop output is triangle
only. We round-trip through ``trimesh.Trimesh`` by triangulating each
output face deterministically (fan-triangulation about the first
vertex) so downstream stages keep their flat-buffer expectations.

This module is imported lazily from the topology stage to avoid the
``import trimesh`` cost when subdivision finishing is disabled.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .from_geometry import SubdivisionFinishingSpec, apply_finishing
from .mesh import SubdivMesh, mesh_from_arrays


def trimesh_to_subdiv(mesh: trimesh.Trimesh) -> SubdivMesh:
    """Convert a :class:`trimesh.Trimesh` to a :class:`SubdivMesh`.

    All faces are treated as triangles (which is how trimesh stores
    them). The resulting cage is the natural input to :func:`Loop`; it
    is also a valid -- if very fine -- input to Catmull-Clark.
    """
    positions = [tuple(map(float, v)) for v in mesh.vertices.tolist()]
    faces = [tuple(int(idx) for idx in face) for face in mesh.faces.tolist()]
    return mesh_from_arrays(positions, faces)


def subdiv_to_trimesh(refined: SubdivMesh) -> trimesh.Trimesh:
    """Triangulate a :class:`SubdivMesh` and return a ``trimesh.Trimesh``.

    Quad and n-gon faces are fan-triangulated around their first
    vertex, the same convention used by Blender's "Quads to Tris"
    operator with the BEAUTY=False / SHORTEST_DIAG=False switches.
    """
    positions = np.asarray(refined.positions, dtype=np.float64)
    triangles: list[tuple[int, int, int]] = []
    for face in refined.faces:
        if len(face) == 3:
            triangles.append((face[0], face[1], face[2]))
        else:
            anchor = face[0]
            for i in range(1, len(face) - 1):
                triangles.append((anchor, face[i], face[i + 1]))
    faces = np.asarray(triangles, dtype=np.int64)
    out = trimesh.Trimesh(
        vertices=positions, faces=faces, process=False, validate=False
    )
    return out


def apply_finishing_to_trimesh(
    mesh: trimesh.Trimesh,
    spec: SubdivisionFinishingSpec | None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Run a subdivision finishing spec over a :class:`trimesh.Trimesh`."""
    if spec is None or spec.levels <= 0:
        return mesh, {"applied": False, "reason": "no subdivision spec"}
    cage = trimesh_to_subdiv(mesh)
    refined, report = apply_finishing(cage, spec)
    if not report.get("applied"):
        return mesh, report
    return subdiv_to_trimesh(refined), report


__all__ = [
    "apply_finishing_to_trimesh",
    "subdiv_to_trimesh",
    "trimesh_to_subdiv",
]
