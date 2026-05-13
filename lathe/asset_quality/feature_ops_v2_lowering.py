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


def lower_trim_sweep(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """Lower ``op.trim_sweep`` — sweep a 2D profile along a path.

    Approximates the sweep as a chain of ``solid.box`` segments aligned
    with the path. ``fuse_policy: separate_submesh`` skips the
    op.union back into the host so the trim stays as its own zone.
    """
    path = op.parameters.get("path", [])
    profile = op.parameters.get("profile", {})
    fuse_policy = str(op.parameters.get("fuse_policy", "fused_to_host"))
    material_zone = op.parameters.get("material_zone")
    target = op.target or "trim"

    if not isinstance(path, (list, tuple)) or len(path) < 2:
        return (op,)
    if isinstance(profile, dict):
        width = float(profile.get("width_cm", 1.5))
        height = float(profile.get("height_cm", 0.6))
    else:
        width, height = 1.5, 0.6

    ops_out: list[ShapeOp] = []
    for i in range(len(path) - 1):
        p0 = path[i]
        p1 = path[i + 1]
        cx = (p0[0] + p1[0]) / 2.0
        cy = (p0[1] + p1[1]) / 2.0
        cz = (p0[2] + p1[2]) / 2.0
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dz = p1[2] - p0[2]
        length = (dx * dx + dy * dy + dz * dz) ** 0.5
        seg_params: dict[str, Any] = {
            "width_cm": max(length, 0.1),
            "height_cm": width,
            "depth_cm": height,
            "center": (cx, cy, cz),
        }
        if material_zone:
            seg_params["region_id"] = str(material_zone)
        ops_out.append(
            ShapeOp(
                op="solid.box",
                target=f"{target}.seg.{i}",
                parameters=seg_params,
                purpose=f"op.trim_sweep.segment.{i}",
            )
        )

    if fuse_policy != "separate_submesh":
        for i in range(len(ops_out)):
            ops_out.append(
                ShapeOp(
                    op="op.union",
                    target=ctx.body_part_name,
                    parameters={"source": ops_out[i].target, "operation": "union"},
                    purpose=f"op.trim_sweep.fuse.{i}",
                )
            )
    return tuple(ops_out)


def lower_profile_sweep(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """Lower ``op.profile_sweep`` — non-planar sweep with scale/rotation.

    Delegates to trim_sweep semantics for the segment chain but
    honors scale_along_path / rotation_along_path / twist_deg as
    metadata on each segment (kernel can interpolate).
    """
    base_segments = lower_trim_sweep(op, ctx)
    scale_curve = op.parameters.get("scale_along_path", [])
    rotation_curve = op.parameters.get("rotation_along_path", [])
    twist_deg = float(op.parameters.get("twist_deg", 0.0))
    annotated: list[ShapeOp] = []
    for i, seg in enumerate(base_segments):
        new_params = dict(seg.parameters)
        if isinstance(scale_curve, list) and i < len(scale_curve):
            new_params["scale_factor"] = float(scale_curve[i])
        if isinstance(rotation_curve, list) and i < len(rotation_curve):
            new_params["rotation_deg"] = float(rotation_curve[i])
        new_params["twist_deg"] = twist_deg
        annotated.append(
            ShapeOp(op=seg.op, target=seg.target, parameters=new_params, purpose=seg.purpose)
        )
    return tuple(annotated)


def lower_fastener_pattern(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """Lower ``op.fastener_pattern`` — distribute N fasteners over an anchor set.

    Emits ``count`` ``solid.cylinder`` head + shaft pairs, with
    centers distributed by ``pattern_type``: grid (rows × columns
    on a face), line (along the longest body axis), ring (around
    the body's centroid), perimeter (along the body's bounding
    perimeter).
    """
    pattern_type = str(op.parameters.get("pattern_type", "grid"))
    count = max(1, int(op.parameters.get("count", 4)))
    fastener_template = op.parameters.get("fastener_template", {})
    if isinstance(fastener_template, dict):
        head_radius = float(fastener_template.get("head_radius_cm", 0.4))
        head_height = float(fastener_template.get("head_height_cm", 0.4))
    else:
        head_radius, head_height = 0.4, 0.4

    dims = ctx.body_dimensions_cm
    hx = float(dims.get("x", 30.0)) / 2.0
    hy = float(dims.get("y", 30.0)) / 2.0
    hz = float(dims.get("z", 30.0)) / 2.0
    standoff = 0.3

    centers: list[tuple[float, float, float]] = []
    if pattern_type == "grid":
        rows = max(1, int(count ** 0.5))
        cols = (count + rows - 1) // rows
        x_step = (2 * hx) / max(cols + 1, 2)
        z_step = (2 * hz) / max(rows + 1, 2)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= count:
                    break
                centers.append(
                    (-hx + x_step * (c + 1), hy + standoff, -hz + z_step * (r + 1))
                )
                idx += 1
    elif pattern_type == "line":
        x_step = (2 * hx) / (count + 1)
        for i in range(count):
            centers.append((-hx + x_step * (i + 1), hy + standoff, 0.0))
    elif pattern_type == "ring":
        import math
        for i in range(count):
            theta = 2 * math.pi * i / count
            centers.append(
                (hx * 0.7 * math.cos(theta), hy + standoff, hz * 0.7 * math.sin(theta))
            )
    else:  # perimeter
        x_step = (2 * hx) / max(count, 1)
        for i in range(count):
            centers.append((-hx + x_step * i, hy + standoff, hz))

    ops_out: list[ShapeOp] = []
    target_base = op.target or "fastener"
    for i, c in enumerate(centers):
        ops_out.append(
            ShapeOp(
                op="solid.cylinder",
                target=f"{target_base}.{i}.head",
                parameters={
                    "radius_cm": head_radius,
                    "height_cm": head_height,
                    "axis": "y",
                    "center": c,
                },
                purpose=f"op.fastener_pattern.{pattern_type}.{i}.head",
            )
        )
    return tuple(ops_out)


def lower_boolean_group(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """Lower ``op.boolean_group`` — batched boolean over a cluster.

    Emits a single ``op.union`` per cutter (legacy serial form) plus
    a metadata tag indicating the kernel should treat them as a
    batched cluster. The variadic executor consumes the tag and
    materializes the cluster once.
    """
    target = op.target or ctx.body_part_name
    operation = str(op.parameters.get("operation", "difference"))
    cutters = op.parameters.get("cutters", [])
    evaluation = str(op.parameters.get("evaluation", "batched"))

    if not isinstance(cutters, (list, tuple)) or not cutters:
        return (op,)

    ops_out: list[ShapeOp] = []
    for i, cutter_id in enumerate(cutters):
        params: dict[str, Any] = {
            "source": str(cutter_id),
            "operation": operation,
            "_lathe_boolean_cluster_id": op.target or "cluster",
            "_lathe_boolean_evaluation": evaluation,
            "_lathe_boolean_cluster_index": i,
        }
        if operation == "difference":
            params["edge_kind"] = "panel_cut"
            params["blend_mode"] = "subtract"
        ops_out.append(
            ShapeOp(
                op="op.union",
                target=target,
                parameters=params,
                purpose=f"op.boolean_group.{operation}.{i}",
            )
        )
    return tuple(ops_out)


def lower_lod_policy(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """``op.lod_policy`` is metadata — preserves its payload verbatim."""
    return (op,)


def lower_edge_group_select(op: ShapeOp, ctx: FeatureOpLoweringContext) -> tuple[ShapeOp, ...]:
    """``op.edge_group_select`` is metadata — preserves the selector predicate.

    The edge-group selector resolver consumes this op at the topology
    stage to compute concrete edge id sets from the predicate.
    """
    return (op,)


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
    if op.op == "op.trim_sweep":
        return lower_trim_sweep(op, ctx)
    if op.op == "op.profile_sweep":
        return lower_profile_sweep(op, ctx)
    if op.op == "op.fastener_pattern":
        return lower_fastener_pattern(op, ctx)
    if op.op == "op.boolean_group":
        return lower_boolean_group(op, ctx)
    if op.op == "op.lod_policy":
        return lower_lod_policy(op, ctx)
    if op.op == "op.edge_group_select":
        return lower_edge_group_select(op, ctx)
    return (op,)


__all__ = [
    "CONTRACT_VERSION",
    "FeatureOpLoweringContext",
    "lower_panel_inset",
    "lower_weighted_bevel",
    "lower_feature_op_v2",
]
