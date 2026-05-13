"""Multi-LOD ShapeProgram emission from one construction graph (Wave 19 / S5).

The synthesizer's lowering produces one ShapeProgram today. Per
research §6 + the LODPolicy contract, the synthesizer should emit
per-LOD variants (LOD0–LOD3) by applying the policy's feature-
representation rules to each LOD level: drop fasteners at distance,
collapse bevels at proxy LOD, simplify trim to normal stamps mid-
range.

This module is the emission contract. It takes a ShapeProgram + an
LODPolicy + per-feature classification (silhouette-relevance) and
returns a tuple of ShapePrograms — one per LOD — with policy-driven
ops dropped or downgraded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .lod_policy import LODLevelPolicy, LODPolicy
from .shape_ir_v2 import ShapeOp, ShapeProgram

CONTRACT_VERSION = "lathe.asset.multi_lod_emission_v1"

# Map from op purpose / role hints → LODLevelPolicy field name.
# Drives the "drop this op at this LOD" decision per policy.
_PURPOSE_TO_POLICY_FIELD: dict[str, str] = {
    "procedural_fastener": "fastener_representation",
    "procedural_rivet": "fastener_representation",
    "procedural_screw": "fastener_representation",
    "procedural_decal_zone": "secondary_part_representation",
    "procedural_wear_zone": "secondary_part_representation",
    "procedural_bracket": "secondary_part_representation",
    "procedural_corner_guard": "secondary_part_representation",
    "procedural_trim": "trim_representation",
    "procedural_panel_groove": "panel_groove_representation",
    "procedural_lid_seam": "panel_groove_representation",
}


def _policy_field_for_op(op: ShapeOp) -> str | None:
    """Return the LODLevelPolicy field that controls this op's representation."""
    purpose = getattr(op, "purpose", "") or ""
    purpose_lower = purpose.lower()
    for token, field_name in _PURPOSE_TO_POLICY_FIELD.items():
        if token in purpose_lower:
            return field_name
    return None


def _representation_for_op(op: ShapeOp, level: LODLevelPolicy) -> str:
    field = _policy_field_for_op(op)
    if field is None:
        return "geometry"  # default: keep
    return getattr(level, field, "geometry")


def _adjust_bevel_op(op: ShapeOp, level: LODLevelPolicy) -> ShapeOp | None:
    """Downgrade bevel segments at lower LODs."""
    if op.op != "op.bevel":
        return op
    if level.bevel_segments <= 0:
        return None  # drop bevel entirely at proxy LODs
    new_params = dict(op.parameters)
    new_params["segments"] = level.bevel_segments
    return ShapeOp(op=op.op, target=op.target, parameters=new_params, purpose=op.purpose)


def emit_lod_variant(
    program: ShapeProgram, level: LODLevelPolicy
) -> ShapeProgram:
    """Apply a single LODLevelPolicy to a ShapeProgram.

    For each op:
      - check the policy field controlling its representation
      - "geometry" → keep
      - "normal_stamp" or "texture_only" → keep but tag for the
        surface stage to bake into normal/texture (op stays in program
        so kernel still places the geometry — surface stage handles
        downgrade)
      - "removed" → drop the op entirely
      - bevel ops: segments swapped to per-LOD count
    """
    out_ops: list[ShapeOp] = []
    for op in program.ops:
        if op.op == "op.bevel":
            adjusted = _adjust_bevel_op(op, level)
            if adjusted is not None:
                out_ops.append(adjusted)
            continue
        representation = _representation_for_op(op, level)
        if representation == "removed":
            continue
        if representation in ("normal_stamp", "texture_only"):
            # Surface stage will bake at the appropriate fidelity.
            tagged_params = dict(op.parameters)
            tagged_params["_lathe_lod_representation"] = representation
            out_ops.append(
                ShapeOp(op=op.op, target=op.target, parameters=tagged_params, purpose=op.purpose)
            )
            continue
        out_ops.append(op)
    return ShapeProgram(
        version=program.version,
        asset_name=f"{program.asset_name}_{level.lod_id.lower()}",
        family=program.family,
        ops=tuple(out_ops),
    )


def emit_lod_variants(
    program: ShapeProgram, policy: LODPolicy
) -> tuple[ShapeProgram, ...]:
    """Emit per-LOD ShapeProgram variants from one construction graph.

    Returns a tuple of programs aligned with ``policy.levels``.
    LOD0 is typically near-identical to the input; later LODs
    progressively drop / downgrade ops per the policy.
    """
    return tuple(emit_lod_variant(program, level) for level in policy.levels)


__all__ = [
    "CONTRACT_VERSION",
    "emit_lod_variant",
    "emit_lod_variants",
]
