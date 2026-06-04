"""Edge-group selector resolver (Wave 19 / S2).

Resolves ``op.edge_group_select`` predicate dicts into concrete edge
id sets a mesh actually carries. The predicate language:

    {
        "angle_gt_deg": 35,               # dihedral angle threshold
        "angle_lt_deg": 175,
        "exposed": true,                  # not buried in geometry
        "role_in": ["outer_corner", ...], # edge_role tag membership
        "feature_scale_gt": 0.5,          # edge length threshold (cm)
        "axis_aligned_to": "z",           # one of x/y/z or "any"
        "material_boundary": true,        # transitions between zones
    }

The resolver takes a mesh + a metadata dict per edge (computed by the
topology stage) and returns the set of edge ids matching every
non-null predicate field. Edges without metadata default to
``role="generic"`` + ``exposed=true`` + ``material_boundary=false``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

CONTRACT_VERSION = "lathe.shape.edge_group_selector_v1"


@dataclass(frozen=True)
class EdgeMetadata:
    """Per-edge metadata the selector reads."""

    edge_id: str
    role: str = "generic"
    dihedral_angle_deg: float = 90.0
    length_cm: float = 1.0
    exposed: bool = True
    material_boundary: bool = False
    axis: str = "any"  # "x" | "y" | "z" | "any"
    face_ids: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class EdgeGroup:
    """A resolved edge group."""

    name: str
    edge_ids: tuple[str, ...]
    selector_predicate: Mapping[str, Any]
    fallback_used: bool = False


def _angle_match(angle: float, gt: float | None, lt: float | None) -> bool:
    if gt is not None and angle <= gt:
        return False
    if lt is not None and angle >= lt:
        return False
    return True


def select_edge_group(
    name: str,
    predicate: Mapping[str, Any],
    edges: Iterable[EdgeMetadata],
) -> EdgeGroup:
    """Apply ``predicate`` to ``edges`` and return the matching group.

    The predicate is interpreted permissively: any field not in the
    dict imposes no constraint. The ``role_in`` field uses substring
    matching (so ``["corner"]`` matches roles like ``outer_corner``
    and ``panel_corner_edge``).
    """
    angle_gt = predicate.get("angle_gt_deg")
    angle_lt = predicate.get("angle_lt_deg")
    angle_gt_f = float(angle_gt) if isinstance(angle_gt, (int, float)) else None
    angle_lt_f = float(angle_lt) if isinstance(angle_lt, (int, float)) else None

    require_exposed = predicate.get("exposed")
    require_exposed_b = bool(require_exposed) if require_exposed is not None else None

    role_in = predicate.get("role_in")
    role_in_tokens: tuple[str, ...] = ()
    if isinstance(role_in, (list, tuple)):
        role_in_tokens = tuple(str(r).lower() for r in role_in)

    feature_scale_gt = predicate.get("feature_scale_gt")
    feature_scale_gt_f = (
        float(feature_scale_gt) if isinstance(feature_scale_gt, (int, float)) else None
    )

    axis = predicate.get("axis_aligned_to")
    axis_s = str(axis).lower() if isinstance(axis, str) else None

    require_material_boundary = predicate.get("material_boundary")
    require_material_boundary_b = (
        bool(require_material_boundary) if require_material_boundary is not None else None
    )

    matched: list[str] = []
    for edge in edges:
        if not _angle_match(edge.dihedral_angle_deg, angle_gt_f, angle_lt_f):
            continue
        if require_exposed_b is True and not edge.exposed:
            continue
        if require_exposed_b is False and edge.exposed:
            continue
        if role_in_tokens:
            role_lower = edge.role.lower()
            if not any(token in role_lower for token in role_in_tokens):
                continue
        if feature_scale_gt_f is not None and edge.length_cm <= feature_scale_gt_f:
            continue
        if axis_s and axis_s != "any" and edge.axis != "any" and edge.axis != axis_s:
            continue
        if require_material_boundary_b is not None and edge.material_boundary != require_material_boundary_b:
            continue
        matched.append(edge.edge_id)

    return EdgeGroup(
        name=name,
        edge_ids=tuple(matched),
        selector_predicate=dict(predicate),
        fallback_used=False,
    )


def default_edge_metadata_for_box(
    body_dims: Mapping[str, float], edge_id_prefix: str = "body"
) -> tuple[EdgeMetadata, ...]:
    """Emit canonical edge metadata for a box-shaped primary volume.

    A box has 12 edges. Each gets a role (outer_corner_x|y|z),
    dihedral 90°, length from body dims, exposed=true,
    material_boundary=false (until a zone splits the body).
    """
    hx = body_dims.get("x", 30.0)
    hy = body_dims.get("y", 30.0)
    hz = body_dims.get("z", 30.0)
    # 4 X-aligned edges (length = hx)
    # 4 Y-aligned edges (length = hy)
    # 4 Z-aligned edges (length = hz)
    edges: list[EdgeMetadata] = []
    for i, (axis, length, role) in enumerate(
        [("x", hx, "outer_corner_x")] * 4
        + [("y", hy, "outer_corner_y")] * 4
        + [("z", hz, "outer_corner_z")] * 4
    ):
        edges.append(
            EdgeMetadata(
                edge_id=f"{edge_id_prefix}.edge.{i}",
                role=role,
                dihedral_angle_deg=90.0,
                length_cm=float(length),
                exposed=True,
                material_boundary=False,
                axis=axis,
            )
        )
    return tuple(edges)


__all__ = [
    "CONTRACT_VERSION",
    "EdgeMetadata",
    "EdgeGroup",
    "select_edge_group",
    "default_edge_metadata_for_box",
]
