"""Generator for node_type='guard' in the hard_surface domain.

Emits N solid.cylinder bars distributed across the host area. Style
governs the bar distribution pattern:

  - box_cage / perimeter_rail / blade_shroud: bars distributed along
    width axis, all parallel to ``axis``.
  - cylindrical_cage: bars distributed around a circular ring at fixed
    angular spacing.
  - fan_grille: bars distributed across the host face like a circular
    fan grille (radial spokes).
"""

from __future__ import annotations

import math
from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.guard import GuardAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="guard",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "width_cm",
        "height_cm",
        "depth_cm",
        "bar_radius_cm",
        "bar_count",
        "axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.cylinder",),
    required_kernel_capabilities=("solid.cylinder",),
    fallback_diagnostics=("guard_unsupported_style",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: GuardAttributes = node.typed_attributes
    region = attrs.region_id
    bar_count = max(2, attrs.bar_count)

    if attrs.style in ("box_cage", "perimeter_rail", "blade_shroud"):
        bar_length = attrs.height_cm if attrs.axis == "y" else (
            attrs.width_cm if attrs.axis == "x" else attrs.depth_cm
        )
        for bar_index in range(bar_count):
            t = bar_index / float(bar_count - 1)
            bar_params: dict[str, object] = {
                "radius_cm": float(attrs.bar_radius_cm),
                "height_cm": float(bar_length),
                "axis": attrs.axis,
                "guard_style": attrs.style,
                "guard_part": "bar",
                "bar_index": bar_index,
                "bar_position_t": t,
            }
            if region is not None:
                bar_params["region_id"] = f"{region}.bar.{bar_index}"
            yield ShapeOp(
                op="solid.cylinder",
                target=f"{node.node_id}.bar.{bar_index}",
                parameters=bar_params,
                purpose=f"procedural_guard.{attrs.style}.bar[{bar_index}]",
            )
        return

    if attrs.style == "cylindrical_cage":
        ring_radius = min(attrs.width_cm, attrs.depth_cm) * 0.5
        bar_length = attrs.height_cm if attrs.axis == "y" else (
            attrs.width_cm if attrs.axis == "x" else attrs.depth_cm
        )
        for bar_index in range(bar_count):
            theta = 2.0 * math.pi * (bar_index / float(bar_count))
            bar_params = {
                "radius_cm": float(attrs.bar_radius_cm),
                "height_cm": float(bar_length),
                "axis": attrs.axis,
                "guard_style": attrs.style,
                "guard_part": "bar",
                "bar_index": bar_index,
                "ring_radius_cm": float(ring_radius),
                "ring_angle_rad": float(theta),
            }
            if region is not None:
                bar_params["region_id"] = f"{region}.bar.{bar_index}"
            yield ShapeOp(
                op="solid.cylinder",
                target=f"{node.node_id}.bar.{bar_index}",
                parameters=bar_params,
                purpose=f"procedural_guard.{attrs.style}.bar[{bar_index}]",
            )
        return

    # fan_grille: radial spokes
    spoke_length = min(attrs.width_cm, attrs.height_cm) * 0.5
    for spoke_index in range(bar_count):
        theta = math.pi * (spoke_index / float(bar_count))
        spoke_params: dict[str, object] = {
            "radius_cm": float(attrs.bar_radius_cm),
            "height_cm": float(spoke_length * 2.0),
            "axis": attrs.axis,
            "guard_style": attrs.style,
            "guard_part": "spoke",
            "spoke_index": spoke_index,
            "spoke_angle_rad": float(theta),
        }
        if region is not None:
            spoke_params["region_id"] = f"{region}.spoke.{spoke_index}"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.spoke.{spoke_index}",
            parameters=spoke_params,
            purpose=f"procedural_guard.{attrs.style}.spoke[{spoke_index}]",
        )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
