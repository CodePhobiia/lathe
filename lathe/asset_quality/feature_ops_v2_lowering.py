"""ShapeIR v2 next-tier feature ops — lowering (Wave 16 / research M4).

Lowering implementations for ``op.panel_inset`` and
``op.weighted_bevel`` — the two highest-leverage authored-grade ops
per the research's M4 priority list.

The pattern: each op_id maps to a function that takes the op's
parameters + a body context (dimensions, faces, edges) and emits a
sequence of v1-compatible ShapeOp records. The synthesizer's
existing lowering path picks up these ops from the registry.

This module is the contract for op lowering. Wiring into the
existing ``shape_ir_v2.lower_to_v1`` dispatch is the integration
step at the synthesizer's lowering pass.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .shape_ir_v2 import ShapeOp

CONTRACT_VERSION = "lathe.shape.feature_ops_v2_lowering_v1"


@dataclass(frozen=True)
class FeatureOpLoweringContext:
    """Per-op lowering context."""

    asset_id: str
    body_dimensions_cm: Mapping[str, float]
    body_part_name: str = "body"


def lower_panel_inset(
    op: ShapeOp, ctx: FeatureOpLoweringContext
) -> tuple[ShapeOp, ...]:
    """Lower ``op.panel_inset`` to a recessed panel on a target face.

    Strategy: emit a ``solid.box`` cutter sized to face_minus_margin
    × depth_cm, positioned at the face center with the depth axis
    along the face normal, then an ``op.union`` (difference) into
    the body.
    """
    target_face = str(op.parameters.get("target_face", f"{ctx.body_part_name}.face.pos_y"))
    margin_cm = float(op.parameters.get("margin_cm", 4.0))
    depth_cm = float(op.parameters.get("depth_cm", 1.5))
    material_zone = op.parameters.get("material_zone")

    # Parse the target_face name: "body.face.<axis_side>"
    face_token = target_face.split(".")[-1] if "." in target_face else "pos_y"
    axis_signs = {
        "pos_x": (1, 0, 0),
        "neg_x": (-1, 0, 0),
        "pos_y": (0, 1, 0),
        "neg_y": (0, -1, 0),
        "pos_z": (0, 0, 1),
        "neg_z": (0, 0, -1),
    }
    sx, sy, sz = axis_signs.get(face_token, (0, 1, 0))

    dims = ctx.body_dimensions_cm
    hx = float(dims.get("x", 30.0)) / 2.0
    hy = float(dims.get("y", 30.0)) / 2.0
    hz = float(dims.get("z", 30.0)) / 2.0

    if abs(sx) > 0:
        # X face: cutter is y × z minus margin × depth (X)
        cutter_dims = (depth_cm, max(2.0, dims["y"] - 2 * margin_cm), max(2.0, dims["z"] - 2 * margin_cm))
        cutter_center = (sx * (hx - depth_cm / 2.0), 0.0, 0.0)
    elif abs(sy) > 0:
        cutter_dims = (max(2.0, dims["x"] - 2 * margin_cm), depth_cm, max(2.0, dims["z"] - 2 * margin_cm))
        cutter_center = (0.0, sy * (hy - depth_cm / 2.0), 0.0)
    else:
        cutter_dims = (max(2.0, dims["x"] - 2 * margin_cm), max(2.0, dims["y"] - 2 * margin_cm), depth_cm)
        cutter_center = (0.0, 0.0, sz * (hz - depth_cm / 2.0))

    cutter_id = f"{op.target or 'panel_inset'}.cutter"
    cutter_params: dict[str, Any] = {
        "width_cm": cutter_dims[0],
        "height_cm": cutter_dims[1],
        "depth_cm": cutter_dims[2],
        "center": cutter_center,
    }
    if material_zone:
        cutter_params["region_id"] = str(material_zone)

    return (
        ShapeOp(
            op="solid.box",
            target=cutter_id,
            parameters=cutter_params,
            purpose=f"op.panel_inset.cutter.{face_token}",
        ),
        ShapeOp(
            op="op.union",
            target=ctx.body_part_name,
            parameters={
                "source": cutter_id,
                "operation": "difference",
                "edge_kind": "panel_inset",
                "blend_mode": "subtract",
            },
            purpose=f"op.panel_inset.apply.{face_token}",
        ),
    )


def lower_weighted_bevel(
    op: ShapeOp, ctx: FeatureOpLoweringContext
) -> tuple[ShapeOp, ...]:
    """Lower ``op.weighted_bevel`` to a sequence of edge-targeted bevels.

    Emits one ``op.bevel`` per edge in the named edge group with the
    weighted radius + segments + profile + normal policy. The
    weighting comes from the edge group's per-edge weights when the
    selector emits them; otherwise uniform.

    The ``edge_group`` parameter is a string name that the synthesizer's
    edge-group resolver translates to a concrete edge id set. This
    lowering passes the resolved group id through as a kernel hint —
    the kernel does the actual selective bevel.
    """
    edge_group = str(op.parameters.get("edge_group", "hero_silhouette_edges"))
    radius_cm = float(op.parameters.get("radius_cm", 0.8))
    segments = int(op.parameters.get("segments", 2))
    profile = str(op.parameters.get("profile", "chamfer"))
    normal_policy = str(op.parameters.get("normal_policy", "hard_break"))
    zone_policy = str(op.parameters.get("zone_policy", "inherit_or_boundary"))

    bevel_params: dict[str, Any] = {
        "edge_group": edge_group,
        "radius_cm": radius_cm,
        "segments": segments,
        "profile": profile,
        "normal_policy": normal_policy,
        "zone_policy": zone_policy,
        "weighted": True,
    }
    return (
        ShapeOp(
            op="op.bevel",
            target=op.target or ctx.body_part_name,
            parameters=bevel_params,
            purpose=f"op.weighted_bevel.{edge_group}",
        ),
    )


def lower_feature_op_v2(
    op: ShapeOp, ctx: FeatureOpLoweringContext
) -> tuple[ShapeOp, ...]:
    """Dispatch a feature_ops_v2 op to its lowering function.

    Returns the original op wrapped in a single-element tuple when
    the op_id has no specialized lowering — graceful pass-through.
    """
    if op.op == "op.panel_inset":
        return lower_panel_inset(op, ctx)
    if op.op == "op.weighted_bevel":
        return lower_weighted_bevel(op, ctx)
    return (op,)


__all__ = [
    "CONTRACT_VERSION",
    "FeatureOpLoweringContext",
    "lower_panel_inset",
    "lower_weighted_bevel",
    "lower_feature_op_v2",
]
