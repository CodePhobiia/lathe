"""Boolean -> seam_group -> edge_loop bevel author API (roadmap §5.1).

Phase 1 KEY DEMO. Lets any hard-surface family lowering or fixture author
emit the canonical idiom

    body   = box(...)
    cutout = box(...).translate(...)
    result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
    fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)

without hand-crafting ``boolean_seam_groups`` and ``v2_polybevel_modifier``
records on each :class:`~lathe.shape_ir.ShapePrimitive`. The rest of the
shape stage already wires the chain end-to-end (see
``lathe.exact_solids._extract_post_boolean_seam_groups`` and
``_apply_post_boolean_polybevel``); this module's only job is to spell
the author intent in one call so the contract cannot drift between
producers.

The two helpers compose:

    a = box_with_seam_group(part="body", center=..., extents=..., blend_mode="union")
    b = box_with_seam_group(part="body", center=..., extents=...,
                            blend_mode="subtract", seam_group="lip")
    fillet_edge(b, edge_class="lip", radius_cm=1.0, segments=4)
    # primitives [a, b] now author the full chain.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..shape_ir import ShapePrimitive

__all__ = [
    "box_with_seam_group",
    "fillet_edge",
    "tag_boolean_seam_group",
]


def tag_boolean_seam_group(
    primitive: ShapePrimitive,
    *,
    seam_group: str,
    target_part: str | None = None,
) -> ShapePrimitive:
    """Mark ``primitive`` as a boolean operand whose A/B intersection
    edges should be tagged with ``seam_group`` after the boolean fuses.

    Mutates and returns the primitive so the call chains naturally.
    Works on any boolean operand (subtract/intersect/union); the seam
    is read by ``_extract_post_boolean_seam_groups`` and matched against
    the operand's bbox to identify the result-mesh edges that border it.
    """
    if not isinstance(seam_group, str) or not seam_group:
        raise ValueError("tag_boolean_seam_group requires a non-empty seam_group name")
    operation = primitive.blend_mode if primitive.blend_mode in {"subtract", "intersect", "union"} else "subtract"
    record = {
        "name": seam_group,
        "operation": operation,
        "target": target_part or primitive.part,
    }
    existing = list(primitive.boolean_seam_groups)
    if not any(isinstance(group, dict) and group.get("name") == seam_group for group in existing):
        existing.append(record)
    primitive.boolean_seam_groups = existing
    return primitive


def fillet_edge(
    primitive: ShapePrimitive,
    *,
    edge_class: str | Iterable[str],
    radius_cm: float,
    segments: int = 4,
) -> ShapePrimitive:
    """Attach a polybevel edge-loop intent to ``primitive``.

    After the boolean fuses, the post-boolean cutback pass replaces sharp
    edges classified by ``edge_class`` with an edge loop of ``segments``
    bevel faces of width ``radius_cm``. The primitive must also carry the
    matching ``boolean_seam_groups`` entry (use :func:`tag_boolean_seam_group`
    or :func:`box_with_seam_group`); the polybevel cutback uses the seam
    group's edge-list to know which edges to bevel.

    Mutates and returns the primitive.
    """
    if isinstance(edge_class, str):
        targets = [edge_class]
    else:
        targets = [str(item) for item in edge_class if str(item)]
    if not targets:
        raise ValueError("fillet_edge requires at least one edge_class")
    if radius_cm <= 0.0:
        raise ValueError("fillet_edge radius_cm must be > 0")
    if segments < 1:
        raise ValueError("fillet_edge segments must be >= 1")

    primitive.bevel_seam_groups = [
        *list(primitive.bevel_seam_groups),
        {
            "width_cm": float(radius_cm),
            "segments": int(segments),
            "target_seam_groups": list(targets),
        },
    ]
    primitive.v2_polybevel_modifier = {
        "width_cm": float(radius_cm),
        "segments": int(segments),
        "target_seam_groups": list(targets),
        "source_boolean_seam_group_count": len(primitive.boolean_seam_groups),
    }
    return primitive


def box_with_seam_group(
    *,
    part: str,
    center: tuple[float, float, float],
    extents: tuple[float, float, float],
    blend_mode: str = "subtract",
    seam_group: str | None = None,
    bevel_radius_cm: float | None = None,
    bevel_segments: int = 4,
    component: str | None = None,
    region: str | None = None,
    tags: Iterable[str] | None = None,
) -> ShapePrimitive:
    """One-call constructor for the §5.1 idiom on a box operand.

    If ``seam_group`` is given, the resulting boolean A/B edges are tagged
    with that name. If ``bevel_radius_cm`` is also given, a polybevel of
    ``bevel_segments`` segments is queued so the post-boolean cutback
    pass replaces the seam's sharp edges with a chamfered loop.

    A subtract operand with ``seam_group="lip"`` and
    ``bevel_radius_cm=1.0`` is the canonical hatch-lip / panel-cut
    idiom.
    """
    primitive = ShapePrimitive(
        primitive_type="box",
        part=part,
        center=center,
        extents=extents,
        blend_mode=blend_mode,
        component=component,
        region=region,
        tags=list(tags) if tags else [],
    )
    if seam_group is not None:
        tag_boolean_seam_group(primitive, seam_group=seam_group)
        if bevel_radius_cm is not None:
            fillet_edge(
                primitive,
                edge_class=seam_group,
                radius_cm=bevel_radius_cm,
                segments=bevel_segments,
            )
    return primitive
