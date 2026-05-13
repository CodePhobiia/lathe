"""Per-NODE_TYPE anchor emitters for the placement_binding contract.

Each NODE_TYPE declares the anchors a host node exposes (target side)
and the anchors a source node carries (source side). Generators
consume these to drive the relation resolver — without per-asset
heuristics.

Registry layout::

    ANCHOR_EMITTERS[node_type] = AnchorEmitter

Each ``AnchorEmitter`` produces ``Anchor`` objects from a node's
attributes + body dimensions context. Anchor IDs are stable within a
synthesis run so trace evidence references the same anchor across
stages.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ....shape.placement import Anchor, Frame

# An anchor emitter callable signature.
AnchorEmitter = Callable[[dict[str, Any], dict[str, float]], list[Anchor]]


def _box_corner_anchors(
    node_id: str,
    dims: dict[str, float],
    affordances: tuple[str, ...] = ("receives_attachment", "wrappable"),
) -> list[Anchor]:
    """Emit 8 corner anchors for a box-like body's exterior."""
    hx = dims.get("x", 30.0) / 2.0
    hy = dims.get("y", 30.0) / 2.0
    hz = dims.get("z", 30.0) / 2.0
    anchors: list[Anchor] = []
    signs = [
        (-1, -1, -1),
        (1, -1, -1),
        (-1, 1, -1),
        (1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (-1, 1, 1),
        (1, 1, 1),
    ]
    for i, (sx, sy, sz) in enumerate(signs):
        origin = (sx * hx, sy * hy, sz * hz)
        # Corner normal points outward diagonally.
        norm_mag = (sx * sx + sy * sy + sz * sz) ** 0.5
        z_axis = (sx / norm_mag, sy / norm_mag, sz / norm_mag)
        anchors.append(
            Anchor(
                anchor_id=f"{node_id}.corner.{i}",
                role="exterior_corner",
                frame=Frame(origin_cm=origin, z_axis=z_axis),
                bounds_cm=(8.0, 8.0, 8.0),
                affordances=affordances,
                capacity=1,
                host_node_id=node_id,
                metadata={"corner_index": i, "signs": (sx, sy, sz)},
            )
        )
    return anchors


def _box_face_anchors(node_id: str, dims: dict[str, float]) -> list[Anchor]:
    """Emit 6 face-center anchors (+X, -X, +Y, -Y, +Z, -Z)."""
    hx = dims.get("x", 30.0) / 2.0
    hy = dims.get("y", 30.0) / 2.0
    hz = dims.get("z", 30.0) / 2.0
    face_specs = [
        ("face.pos_x", (hx, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ("face.neg_x", (-hx, 0.0, 0.0), (-1.0, 0.0, 0.0)),
        ("face.pos_y", (0.0, hy, 0.0), (0.0, 1.0, 0.0)),
        ("face.neg_y", (0.0, -hy, 0.0), (0.0, -1.0, 0.0)),
        ("face.pos_z", (0.0, 0.0, hz), (0.0, 0.0, 1.0)),
        ("face.neg_z", (0.0, 0.0, -hz), (0.0, 0.0, -1.0)),
    ]
    anchors: list[Anchor] = []
    for suffix, origin, normal in face_specs:
        anchors.append(
            Anchor(
                anchor_id=f"{node_id}.{suffix}",
                role="exterior_face",
                frame=Frame(origin_cm=origin, z_axis=normal),
                bounds_cm=(dims.get("x", 30.0), dims.get("y", 30.0), 5.0),
                affordances=(
                    "receives_attachment",
                    "hosts_inset",
                    "aligned_target",
                ),
                capacity=8,
                host_node_id=node_id,
                metadata={"face_normal": normal},
            )
        )
    return anchors


def _box_edge_anchors(
    node_id: str, dims: dict[str, float]
) -> list[Anchor]:
    """Emit 12 edge midpoint anchors for box-like bodies."""
    hx = dims.get("x", 30.0) / 2.0
    hy = dims.get("y", 30.0) / 2.0
    hz = dims.get("z", 30.0) / 2.0
    edge_specs = [
        # X-aligned edges (4)
        ("edge.x.pyp_z", (0.0, hy, hz), (0.0, 1.0, 1.0)),
        ("edge.x.pyn_z", (0.0, hy, -hz), (0.0, 1.0, -1.0)),
        ("edge.x.nyp_z", (0.0, -hy, hz), (0.0, -1.0, 1.0)),
        ("edge.x.nyn_z", (0.0, -hy, -hz), (0.0, -1.0, -1.0)),
        # Y-aligned edges (4)
        ("edge.y.pxp_z", (hx, 0.0, hz), (1.0, 0.0, 1.0)),
        ("edge.y.pxn_z", (hx, 0.0, -hz), (1.0, 0.0, -1.0)),
        ("edge.y.nxp_z", (-hx, 0.0, hz), (-1.0, 0.0, 1.0)),
        ("edge.y.nxn_z", (-hx, 0.0, -hz), (-1.0, 0.0, -1.0)),
        # Z-aligned edges (4) — vertical edges, suitable for hinge anchors.
        ("edge.z.pxp_y", (hx, hy, 0.0), (1.0, 1.0, 0.0)),
        ("edge.z.pxn_y", (hx, -hy, 0.0), (1.0, -1.0, 0.0)),
        ("edge.z.nxp_y", (-hx, hy, 0.0), (-1.0, 1.0, 0.0)),
        ("edge.z.nxn_y", (-hx, -hy, 0.0), (-1.0, -1.0, 0.0)),
    ]
    anchors: list[Anchor] = []
    for suffix, origin, normal in edge_specs:
        # Normalize the diagonal normal.
        mag = sum(n * n for n in normal) ** 0.5
        if mag > 0:
            normal_n = tuple(n / mag for n in normal)
        else:
            normal_n = (0.0, 0.0, 1.0)
        anchors.append(
            Anchor(
                anchor_id=f"{node_id}.{suffix}",
                role="exterior_edge",
                frame=Frame(origin_cm=origin, z_axis=normal_n),
                bounds_cm=(dims.get("x", 30.0), dims.get("y", 30.0), 2.0),
                affordances=("receives_attachment", "wrappable", "hinge_target"),
                capacity=2,
                host_node_id=node_id,
                metadata={"edge_axis": suffix.split(".")[1]},
            )
        )
    return anchors


def emit_primary_volume_anchors(
    node: dict[str, Any], body_dims: dict[str, float]
) -> list[Anchor]:
    """Primary volume hosts corner + face + edge anchors."""
    node_id = str(node.get("node_id") or "primary_volume")
    anchors: list[Anchor] = []
    anchors.extend(_box_corner_anchors(node_id, body_dims))
    anchors.extend(_box_face_anchors(node_id, body_dims))
    anchors.extend(_box_edge_anchors(node_id, body_dims))
    return anchors


def _source_attachment_anchor(
    node: dict[str, Any],
    role: str,
    affordance: str,
    z_axis: tuple[float, float, float] = (0.0, 0.0, -1.0),
) -> list[Anchor]:
    """Helper for source-side anchors (the part being attached).

    The source anchor's z axis points INTO the host (typically downward
    or back, opposite to the host face normal). This is what
    ``RelationResolver`` checks against the host face's normal under
    the ``opposed`` normal policy.
    """
    node_id = str(node.get("node_id") or "")
    return [
        Anchor(
            anchor_id=f"{node_id}.mount",
            role=role,
            frame=Frame(origin_cm=(0.0, 0.0, 0.0), z_axis=z_axis),
            bounds_cm=(4.0, 4.0, 1.0),
            affordances=(affordance,),
            capacity=1,
            host_node_id=node_id,
            metadata={"source_role": role},
        )
    ]


def emit_handle_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "handle_back", "attaches")


def emit_foot_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "foot_top", "supports")


def emit_latch_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "latch_back", "attaches")


def emit_bracket_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    """Brackets wrap around an exterior corner (and can also attach).

    Affordances cover both ``wraps_around`` and ``attached_to`` edges
    since brackets are used as both corner guards (wraps) and bolt-on
    reinforcements (attaches).
    """
    node_id = str(node.get("node_id") or "")
    return [
        Anchor(
            anchor_id=f"{node_id}.wrap",
            role="bracket_wrap_origin",
            frame=Frame(origin_cm=(0.0, 0.0, 0.0), z_axis=(0.0, 0.0, -1.0)),
            bounds_cm=(6.0, 6.0, 6.0),
            affordances=("wraps", "attaches"),
            capacity=1,
            host_node_id=node_id,
        )
    ]


def emit_fastener_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "fastener_root", "attaches")


def emit_trim_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "trim_back", "wraps")


def emit_hinge_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    """Hinges align with an edge axis."""
    node_id = str(node.get("node_id") or "")
    return [
        Anchor(
            anchor_id=f"{node_id}.barrel",
            role="hinge_barrel",
            frame=Frame(origin_cm=(0.0, 0.0, 0.0)),
            bounds_cm=(2.0, 2.0, 6.0),
            affordances=("aligns", "attaches"),
            capacity=1,
            host_node_id=node_id,
        )
    ]


def emit_panel_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "panel_back", "attaches")


def emit_door_leaf_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "leaf_hinge_edge", "aligns")


def emit_mount_anchors(node: dict[str, Any], _: dict[str, float]) -> list[Anchor]:
    return _source_attachment_anchor(node, "mount_top", "supports")


ANCHOR_EMITTERS: dict[str, AnchorEmitter] = {
    "primary_volume": emit_primary_volume_anchors,
    "handle": emit_handle_anchors,
    "foot": emit_foot_anchors,
    "latch": emit_latch_anchors,
    "bracket": emit_bracket_anchors,
    "fastener": emit_fastener_anchors,
    "trim": emit_trim_anchors,
    "hinge": emit_hinge_anchors,
    "panel": emit_panel_anchors,
    "door_leaf": emit_door_leaf_anchors,
    "mount": emit_mount_anchors,
}


def emit_anchors_for_node(
    node_type: str,
    node: Mapping[str, Any],
    body_dims: dict[str, float],
) -> list[Anchor]:
    """Dispatch to the registered emitter for ``node_type``.

    Returns empty list when no emitter is registered — callers should
    fall back to the heuristic placement path until full coverage.
    """
    emitter = ANCHOR_EMITTERS.get(node_type)
    if emitter is None:
        return []
    return emitter(dict(node), body_dims)


__all__ = [
    "AnchorEmitter",
    "ANCHOR_EMITTERS",
    "emit_anchors_for_node",
]
