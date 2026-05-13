"""B-Rep IR scaffold (typed; OCCT/build123d integration external).

Per northstar §10 Lane A future-tasks, a parallel B-Rep lane is
useful for CAD-style fillets, shells, and exact boolean operations
on freeform geometry. This module declares the typed IR so that
when an external builder wraps OCCT or build123d, downstream stages
already know how to consume the result.

The current implementation provides a builder for the simplest case:
an axis-aligned box B-Rep. Full freeform topology + curved-face
support is wired by the external builder.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

BREP_IR_VERSION = "lathe.asset_foundry.brep_ir_v1"


@dataclass(frozen=True)
class BrepVertex:
    """A 3D vertex in a B-Rep."""

    vertex_id: str
    position_cm: tuple[float, float, float]


@dataclass(frozen=True)
class BrepEdge:
    """An edge between two vertices.

    ``curve_kind`` is one of ``line`` (straight), ``circle``, ``arc``,
    ``nurbs``. ``parameters`` holds curve-kind-specific data.
    """

    edge_id: str
    start_vertex_id: str
    end_vertex_id: str
    curve_kind: str = "line"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    seam_class: str = ""
    """Optional seam classification (e.g. ``hero_bevel``, ``foot_split``)."""


@dataclass(frozen=True)
class BrepFace:
    """A face bounded by a closed loop of edges.

    ``surface_kind`` is one of ``planar``, ``cylindrical``,
    ``spherical``, ``nurbs``. ``parameters`` holds surface-kind data
    (e.g. normal + offset for planar).
    """

    face_id: str
    edge_loop: tuple[str, ...]
    surface_kind: str = "planar"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    zone_id: str = ""
    material_class: str = ""


@dataclass(frozen=True)
class BrepShell:
    """A watertight collection of faces."""

    shell_id: str
    face_ids: tuple[str, ...]
    is_solid: bool = True


@dataclass(frozen=True)
class BrepIR:
    """The full B-Rep IR for one asset."""

    asset_id: str
    vertices: Mapping[str, BrepVertex]
    edges: Mapping[str, BrepEdge]
    faces: Mapping[str, BrepFace]
    shells: tuple[BrepShell, ...]
    backend_status: str = "scaffold"
    """``scaffold`` (in-tree contract only) | ``occt`` (OCCT-backed) |
    ``build123d`` (build123d-backed)."""
    backend_status_reason: str = "no_occt_or_build123d_backend_wired_in_tree"


def build_box_brep(
    *,
    asset_id: str = "box_brep",
    width_cm: float = 10.0,
    height_cm: float = 10.0,
    depth_cm: float = 10.0,
    origin_cm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    zone_prefix: str = "box_brep",
) -> BrepIR:
    """Build a B-Rep IR for an axis-aligned box.

    The 8 vertices, 12 edges, and 6 planar faces are all generated
    deterministically. Use as a wire-test fixture for downstream
    consumers of the B-Rep IR.
    """
    ox, oy, oz = origin_cm
    hx, hy, hz = width_cm / 2.0, height_cm / 2.0, depth_cm / 2.0
    vertices: dict[str, BrepVertex] = {}
    v_positions = [
        (-hx, -hy, -hz),
        (hx, -hy, -hz),
        (hx, hy, -hz),
        (-hx, hy, -hz),
        (-hx, -hy, hz),
        (hx, -hy, hz),
        (hx, hy, hz),
        (-hx, hy, hz),
    ]
    for i, (vx, vy, vz) in enumerate(v_positions):
        vid = f"v_{i:01d}"
        vertices[vid] = BrepVertex(
            vertex_id=vid,
            position_cm=(vx + ox, vy + oy, vz + oz),
        )
    edges: dict[str, BrepEdge] = {}
    edge_pairs = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # bottom ring
        (4, 5), (5, 6), (6, 7), (7, 4),  # top ring
        (0, 4), (1, 5), (2, 6), (3, 7),  # verticals
    ]
    for i, (a, b) in enumerate(edge_pairs):
        eid = f"e_{i:02d}"
        edges[eid] = BrepEdge(
            edge_id=eid,
            start_vertex_id=f"v_{a:01d}",
            end_vertex_id=f"v_{b:01d}",
            curve_kind="line",
        )
    faces: dict[str, BrepFace] = {}
    face_data = [
        ("face_bottom", "0,0,-1", -hz - oz, ("e_00", "e_01", "e_02", "e_03")),
        ("face_top", "0,0,1", hz + oz, ("e_04", "e_05", "e_06", "e_07")),
        ("face_front", "0,-1,0", -hy - oy, ("e_00", "e_09", "e_04", "e_08")),
        ("face_right", "1,0,0", hx + ox, ("e_01", "e_10", "e_05", "e_09")),
        ("face_back", "0,1,0", hy + oy, ("e_02", "e_11", "e_06", "e_10")),
        ("face_left", "-1,0,0", -hx - ox, ("e_03", "e_08", "e_07", "e_11")),
    ]
    for face_id, normal, offset, loop in face_data:
        faces[face_id] = BrepFace(
            face_id=face_id,
            edge_loop=loop,
            surface_kind="planar",
            parameters={"normal": normal, "offset_cm": offset},
            zone_id=f"{zone_prefix}.{face_id}",
        )
    shell = BrepShell(
        shell_id="shell_solid",
        face_ids=tuple(faces.keys()),
        is_solid=True,
    )
    return BrepIR(
        asset_id=asset_id,
        vertices=vertices,
        edges=edges,
        faces=faces,
        shells=(shell,),
    )


__all__ = [
    "BREP_IR_VERSION",
    "BrepEdge",
    "BrepFace",
    "BrepIR",
    "BrepShell",
    "BrepVertex",
    "build_box_brep",
]
