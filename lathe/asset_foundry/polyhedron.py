"""Foundry F4 — prism + half-space polyhedron builders.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §10
(Prismatic Kernel adaptation) and §16.3 (VioletCrystalCluster), the
Foundry needs first-class faceted polyhedral primitives for the
LowPolyFantasy style pack and the hard-surface side of the kernel.

This module provides:
  - PrismMesh: deterministic N-sided prism builder (top/bottom polygons
    + side quads + optional taper). Faces carry zone_id + flat_normal
    policy for the stylized stack.
  - HalfSpacePolyhedron: convex polyhedron built from a set of
    half-space inequalities. Used for crystals + faceted cliff stones.
  - build_prism_mesh / build_half_space_polyhedron: pure functional API.

All builders are deterministic and pure-Python. They emit a typed
mesh representation that downstream stages (ShapeIR lowering, the
kernel program, the package writer) consume without requiring any
specific runtime backend.

Reference: gemeini_research.md "Prismatic Kernel Architecture" — half-
space CSG for crystals/architecture; flat-normal policy for premium
faceted look.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

POLYHEDRON_VERSION = "lathe.asset_foundry.polyhedron_v1"


@dataclass(frozen=True)
class HalfSpace:
    """One half-space constraint: ``normal . x <= offset``.

    The normal must be a unit-length 3-vector. The intersection of N
    half-spaces produces a convex polyhedron when consistent.
    """

    normal: tuple[float, float, float]
    offset: float
    label: str = ""
    """Optional zone label for face attribution (e.g.
    ``crystal_face_north``)."""


@dataclass(frozen=True)
class PrismMesh:
    """A faceted prism mesh — top + bottom + N side quads.

    Vertices and faces are emitted as plain Python tuples so the
    structure is JSON-friendly. Each face carries:

    - ``zone_id``: which zone the face belongs to (top / bottom / side_NN)
    - ``flat_normal``: True for LowPolyFantasy-style faceted shading
    """

    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    """Each face is a tuple of vertex indices, CCW from outside."""

    face_zone_ids: tuple[str, ...]
    """Same length as ``faces``."""

    flat_normals: bool = True

    def vertex_count(self) -> int:
        return len(self.vertices)

    def face_count(self) -> int:
        return len(self.faces)

    def quad_face_count(self) -> int:
        return sum(1 for f in self.faces if len(f) == 4)

    def ngon_face_count(self) -> int:
        return sum(1 for f in self.faces if len(f) > 4)


@dataclass(frozen=True)
class HalfSpacePolyhedron:
    """A convex polyhedron built from half-space constraints.

    Emits the same mesh shape as ``PrismMesh`` so downstream stages
    treat them interchangeably.
    """

    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    face_zone_ids: tuple[str, ...]
    half_spaces: tuple[HalfSpace, ...]
    flat_normals: bool = True

    def vertex_count(self) -> int:
        return len(self.vertices)

    def face_count(self) -> int:
        return len(self.faces)


def build_prism_mesh(
    *,
    sides: int,
    base_radius_cm: float,
    height_cm: float,
    top_radius_cm: float | None = None,
    base_z_cm: float = 0.0,
    twist_deg: float = 0.0,
    flat_normals: bool = True,
    zone_prefix: str = "prism",
) -> PrismMesh:
    """Build an N-sided prism mesh (optionally tapered + twisted).

    Args:
        sides: number of side faces (>= 3).
        base_radius_cm: bottom-polygon circumradius.
        height_cm: vertical extent.
        top_radius_cm: top-polygon circumradius (defaults to base, =
            untapered).
        base_z_cm: Z coordinate of the bottom face center.
        twist_deg: optional rotation of the top polygon relative to the
            bottom (helps faceted crystals look less mechanical).
        flat_normals: zone-flagged for the renderer / surface stage.
        zone_prefix: prefix for face zone IDs.

    Returns:
        PrismMesh with vertex/face arrays and per-face zone attribution.
    """
    if sides < 3:
        raise ValueError(f"prism sides must be >= 3 (got {sides})")
    if base_radius_cm <= 0 or height_cm <= 0:
        raise ValueError("prism base_radius_cm and height_cm must be positive")
    if top_radius_cm is None:
        top_radius_cm = base_radius_cm
    top_z = base_z_cm + height_cm
    twist_rad = math.radians(twist_deg)
    angle_step = 2.0 * math.pi / sides

    bottom_ring: list[tuple[float, float, float]] = []
    top_ring: list[tuple[float, float, float]] = []
    for i in range(sides):
        theta = i * angle_step
        bx = base_radius_cm * math.cos(theta)
        by = base_radius_cm * math.sin(theta)
        bottom_ring.append((bx, by, base_z_cm))
        theta_top = theta + twist_rad
        tx = top_radius_cm * math.cos(theta_top)
        ty = top_radius_cm * math.sin(theta_top)
        top_ring.append((tx, ty, top_z))

    vertices: list[tuple[float, float, float]] = list(bottom_ring) + list(top_ring)
    faces: list[tuple[int, ...]] = []
    zones: list[str] = []

    # Side quads — CCW from outside.
    for i in range(sides):
        j = (i + 1) % sides
        b_i = i
        b_j = j
        t_i = sides + i
        t_j = sides + j
        faces.append((b_i, b_j, t_j, t_i))
        zones.append(f"{zone_prefix}.side_{i:02d}")

    # Bottom n-gon — CCW from below = CW from above; reverse for outward.
    bottom_face = tuple(reversed(range(sides)))
    faces.append(bottom_face)
    zones.append(f"{zone_prefix}.bottom")

    # Top n-gon — CCW from above.
    top_face = tuple(range(sides, 2 * sides))
    faces.append(top_face)
    zones.append(f"{zone_prefix}.top")

    return PrismMesh(
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_zone_ids=tuple(zones),
        flat_normals=flat_normals,
    )


def _project_onto_face(
    half_space: HalfSpace, point: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Project a point onto a half-space's bounding plane.

    Used by the half-space polyhedron builder to snap vertices onto
    the cutting planes when computing intersections.
    """
    nx, ny, nz = half_space.normal
    px, py, pz = point
    signed = nx * px + ny * py + nz * pz - half_space.offset
    return (px - nx * signed, py - ny * signed, pz - nz * signed)


def build_half_space_polyhedron(
    half_spaces: Sequence[HalfSpace],
    *,
    bbox_extent_cm: float = 50.0,
    zone_prefix: str = "polyhedron",
) -> HalfSpacePolyhedron:
    """Build a convex polyhedron from half-space inequalities.

    Uses a bounded-bbox initial volume + iterative half-space clipping
    via the Sutherland-Hodgman polygon-clipping idea, generalized to
    3D faces. Each input half-space contributes at most one face to
    the output (when it actively clips the volume).

    The implementation is intentionally simple (O(F * H) per face per
    half-space). For Foundry F4's stylized stack (crystals, faceted
    rocks, cliff stones), input counts are tiny (< 20 half-spaces),
    and determinism matters more than throughput.

    Args:
        half_spaces: ``normal . x <= offset`` constraints. Normals
            should be unit-length; offsets in cm.
        bbox_extent_cm: half-size of the seed bounding cube (centered
            at origin). Choose larger than any expected half-space
            offset.
        zone_prefix: prefix for face zone IDs.

    Returns:
        HalfSpacePolyhedron with vertices/faces/zone attribution.
    """
    if not half_spaces:
        raise ValueError("at least one half_space is required")

    # Seed cube: 6 faces, 8 vertices.
    e = bbox_extent_cm
    cube_vertices: list[tuple[float, float, float]] = [
        (-e, -e, -e),
        (e, -e, -e),
        (e, e, -e),
        (-e, e, -e),
        (-e, -e, e),
        (e, -e, e),
        (e, e, e),
        (-e, e, e),
    ]
    # 6 quad faces with CCW outward normals.
    cube_faces: list[tuple[int, ...]] = [
        (0, 3, 2, 1),  # bottom -Z
        (4, 5, 6, 7),  # top +Z
        (0, 1, 5, 4),  # front -Y
        (1, 2, 6, 5),  # right +X
        (2, 3, 7, 6),  # back +Y
        (3, 0, 4, 7),  # left -X
    ]
    cube_zones: list[str] = [
        f"{zone_prefix}.bbox_{i:02d}" for i in range(len(cube_faces))
    ]

    vertices: list[tuple[float, float, float]] = list(cube_vertices)
    faces: list[list[int]] = [list(f) for f in cube_faces]
    zones: list[str] = list(cube_zones)

    def _classify(
        v_idx: int, half_space: HalfSpace
    ) -> tuple[float, bool]:
        """Return signed distance + inside flag."""
        nx, ny, nz = half_space.normal
        x, y, z = vertices[v_idx]
        signed = nx * x + ny * y + nz * z - half_space.offset
        return signed, signed <= 1e-9

    for hs_idx, hs in enumerate(half_spaces):
        new_faces: list[list[int]] = []
        new_zones: list[str] = []
        emerging_edges: dict[tuple[int, int], int] = {}
        # Clip each existing face against the half-space.
        for face, zone in zip(faces, zones):
            classifications = [_classify(v, hs) for v in face]
            inside_count = sum(1 for _, ok in classifications if ok)
            if inside_count == len(face):
                new_faces.append(face)
                new_zones.append(zone)
                continue
            if inside_count == 0:
                continue  # entirely cut off
            # Mixed — build clipped polygon + record new edge endpoints.
            clipped: list[int] = []
            new_edge: list[int] = []
            for i in range(len(face)):
                a_idx = face[i]
                b_idx = face[(i + 1) % len(face)]
                a_signed, a_inside = classifications[i]
                b_signed, b_inside = classifications[(i + 1) % len(face)]
                if a_inside:
                    clipped.append(a_idx)
                if a_inside != b_inside:
                    # Edge crosses the plane; compute intersection.
                    t = a_signed / (a_signed - b_signed) if (a_signed - b_signed) != 0 else 0.5
                    ax, ay, az = vertices[a_idx]
                    bx, by, bz = vertices[b_idx]
                    px = ax + t * (bx - ax)
                    py = ay + t * (by - ay)
                    pz = az + t * (bz - az)
                    # Snap to plane to avoid drift.
                    snapped = _project_onto_face(hs, (px, py, pz))
                    edge_key = (min(a_idx, b_idx), max(a_idx, b_idx))
                    if edge_key in emerging_edges:
                        new_v_idx = emerging_edges[edge_key]
                    else:
                        new_v_idx = len(vertices)
                        vertices.append(snapped)
                        emerging_edges[edge_key] = new_v_idx
                    clipped.append(new_v_idx)
                    new_edge.append(new_v_idx)
            if len(clipped) >= 3:
                new_faces.append(clipped)
                new_zones.append(zone)
        # Synthesize the new face from emerging-edge vertices.
        if emerging_edges:
            new_face_indices = sorted(set(emerging_edges.values()))
            if len(new_face_indices) >= 3:
                # Sort the new face vertices CCW around the half-space's
                # normal axis. Pick a centroid; sort by angle in the
                # plane perpendicular to the normal.
                cx = sum(vertices[v][0] for v in new_face_indices) / len(new_face_indices)
                cy = sum(vertices[v][1] for v in new_face_indices) / len(new_face_indices)
                cz = sum(vertices[v][2] for v in new_face_indices) / len(new_face_indices)
                nx, ny, nz = hs.normal
                # Build two perpendicular axes in the cutting plane.
                if abs(nx) <= abs(ny) and abs(nx) <= abs(nz):
                    helper = (1.0, 0.0, 0.0)
                elif abs(ny) <= abs(nz):
                    helper = (0.0, 1.0, 0.0)
                else:
                    helper = (0.0, 0.0, 1.0)
                hx, hy, hz = helper
                # u = normalize(helper - normal * dot(helper, normal))
                dot = nx * hx + ny * hy + nz * hz
                ux = hx - nx * dot
                uy = hy - ny * dot
                uz = hz - nz * dot
                u_len = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
                ux, uy, uz = ux / u_len, uy / u_len, uz / u_len
                # v = normal cross u
                vx = ny * uz - nz * uy
                vy = nz * ux - nx * uz
                vz = nx * uy - ny * ux

                def _angle(v_idx: int) -> float:
                    x, y, z = vertices[v_idx]
                    dx, dy, dz = x - cx, y - cy, z - cz
                    u_proj = dx * ux + dy * uy + dz * uz
                    v_proj = dx * vx + dy * vy + dz * vz
                    return math.atan2(v_proj, u_proj)

                sorted_indices = sorted(new_face_indices, key=_angle)
                new_faces.append(sorted_indices)
                new_zones.append(f"{zone_prefix}.{hs.label or f'cut_{hs_idx:02d}'}")
        faces = new_faces
        zones = new_zones
        if not faces:
            # Half-space set is over-constrained — return an empty
            # polyhedron rather than raising; downstream code can detect
            # via face_count == 0.
            break

    return HalfSpacePolyhedron(
        vertices=tuple(vertices),
        faces=tuple(tuple(f) for f in faces),
        face_zone_ids=tuple(zones),
        half_spaces=tuple(half_spaces),
        flat_normals=True,
    )


__all__ = [
    "POLYHEDRON_VERSION",
    "HalfSpace",
    "HalfSpacePolyhedron",
    "PrismMesh",
    "build_half_space_polyhedron",
    "build_prism_mesh",
]
