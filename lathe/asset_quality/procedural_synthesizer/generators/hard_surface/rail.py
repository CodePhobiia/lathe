"""Generator for node_type='rail' in the hard_surface domain.

Translates a typed RailAttributes into one ShapeIR v2 op per
cross-section:
  - round: solid.cylinder
  - rounded_square: solid.rounded_box
  - square: solid.box
  - oval: solid.extruded_profile with oval polygon
"""

from __future__ import annotations

import math
from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.rail import RailAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="rail",
    domain="hard_surface",
    consumed_attribute_fields=(
        "axis",
        "length_cm",
        "cross_section",
        "radius_cm",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=(
        "solid.cylinder",
        "solid.box",
        "solid.rounded_box",
        "solid.extruded_profile",
    ),
    required_kernel_capabilities=("solid.cylinder", "solid.box"),
    fallback_diagnostics=("rail_unsupported_cross_section",),
    output_kind="visible_geometry",
)


def _oval_profile(radius: float, segments: int = 16) -> list[tuple[float, float]]:
    """Oval cross-section profile (2:1 aspect)."""
    points: list[tuple[float, float]] = []
    a = float(radius)
    b = float(radius) * 0.5
    for index in range(segments):
        theta = 2.0 * math.pi * (index / float(segments))
        points.append((a * math.cos(theta), b * math.sin(theta)))
    return points


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: RailAttributes = node.typed_attributes
    region = attrs.region_id

    if attrs.cross_section == "round":
        params: dict[str, object] = {
            "radius_cm": float(attrs.radius_cm),
            "height_cm": float(attrs.length_cm),
            "axis": attrs.axis,
            "rail_cross_section": attrs.cross_section,
        }
        if region is not None:
            params["region_id"] = region
        yield ShapeOp(
            op="solid.cylinder",
            target=node.node_id,
            parameters=params,
            purpose=f"procedural_rail.{attrs.cross_section}",
        )
        return

    if attrs.cross_section in ("square", "rounded_square"):
        # Build extents with the length along axis, radius*2 across.
        side = float(attrs.radius_cm) * 2.0
        axis_order = {
            "x": ("length_cm", "side", "side"),
            "y": ("side", "length_cm", "side"),
            "z": ("side", "side", "length_cm"),
        }
        keys = axis_order[attrs.axis]
        extents = {
            "width_cm": float(attrs.length_cm if keys[0] == "length_cm" else side),
            "height_cm": float(attrs.length_cm if keys[1] == "length_cm" else side),
            "depth_cm": float(attrs.length_cm if keys[2] == "length_cm" else side),
        }
        params = {
            **extents,
            "rail_cross_section": attrs.cross_section,
            "rail_axis": attrs.axis,
        }
        if attrs.cross_section == "rounded_square":
            params["rounding_cm"] = float(attrs.radius_cm) * 0.25
            op = "solid.rounded_box"
        else:
            op = "solid.box"
        if region is not None:
            params["region_id"] = region
        yield ShapeOp(
            op=op,
            target=node.node_id,
            parameters=params,
            purpose=f"procedural_rail.{attrs.cross_section}",
        )
        return

    # oval
    profile = _oval_profile(attrs.radius_cm)
    params = {
        "profile_polygon": tuple(profile),
        "extrude_height": float(attrs.length_cm),
        "axis": attrs.axis,
        "rail_cross_section": attrs.cross_section,
    }
    if region is not None:
        params["region_id"] = region
    yield ShapeOp(
        op="solid.extruded_profile",
        target=node.node_id,
        parameters=params,
        purpose=f"procedural_rail.{attrs.cross_section}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
