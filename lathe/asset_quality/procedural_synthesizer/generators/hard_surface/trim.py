"""Generator for node_type='trim' in the hard_surface domain.

Translates a typed TrimAttributes into a single ShapeIR v2 op. Flat
bands emit ``solid.box``; rounded / rabbet / ogee / bullnose profiles
emit ``solid.extruded_profile`` with the corresponding 2D profile
polygon swept along ``edge_axis``.

No family-name awareness; all variation flows through typed attributes.
"""

from __future__ import annotations

import math
from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.trim import TrimAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="trim",
    domain="hard_surface",
    consumed_attribute_fields=(
        "edge_axis",
        "length_cm",
        "cross_section_width_cm",
        "cross_section_height_cm",
        "profile",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.extruded_profile"),
    required_kernel_capabilities=("solid.box", "solid.extruded_profile"),
    fallback_diagnostics=("trim_unsupported_profile",),
    output_kind="visible_geometry",
)


def _rounded_band_profile(width: float, height: float, segments: int = 8) -> list[tuple[float, float]]:
    """Quarter-circle rounded top, flat bottom + sides."""
    half_w = width * 0.5
    points: list[tuple[float, float]] = [(-half_w, 0.0), (half_w, 0.0)]
    radius = min(half_w, height)
    # right side: vertical to height-radius, then quarter arc to top
    points.append((half_w, height - radius))
    for index in range(1, segments + 1):
        theta = (math.pi * 0.5) * (index / float(segments))
        points.append((half_w - radius + radius * math.cos(theta), height - radius + radius * math.sin(theta)))
    # left side mirrored — top at (0, height) is already the last arc point
    for index in range(segments - 1, -1, -1):
        theta = (math.pi * 0.5) * (index / float(segments))
        points.append((-(half_w - radius + radius * math.cos(theta)), height - radius + radius * math.sin(theta)))
    points.append((-half_w, height - radius))
    return points


def _rabbet_profile(width: float, height: float) -> list[tuple[float, float]]:
    """L-shaped rabbet — full width at bottom, half width at top."""
    half_w = width * 0.5
    return [
        (-half_w, 0.0),
        (half_w, 0.0),
        (half_w, height * 0.5),
        (0.0, height * 0.5),
        (0.0, height),
        (-half_w, height),
    ]


def _ogee_profile(width: float, height: float, segments: int = 6) -> list[tuple[float, float]]:
    """S-curve profile (concave-then-convex) classic ogee."""
    half_w = width * 0.5
    points: list[tuple[float, float]] = [(-half_w, 0.0), (half_w, 0.0)]
    # Right side: up height with S-curve in x
    for index in range(1, segments + 1):
        t = index / float(segments)
        # Two-phase S: concave from (half_w, 0) to (0, height/2), convex to (-half_w/2, height)
        if t <= 0.5:
            phase = t * 2.0
            x = half_w * (1.0 - 0.5 * phase * phase)
            y = height * 0.5 * phase
        else:
            phase = (t - 0.5) * 2.0
            x = half_w * 0.5 * (1.0 - phase)
            y = height * (0.5 + 0.5 * phase)
        points.append((x, y))
    # Mirror left side
    for px, py in reversed(points[2:]):
        points.append((-px, py))
    points.append((-half_w, 0.0))
    return points


def _bullnose_profile(width: float, height: float, segments: int = 16) -> list[tuple[float, float]]:
    """Full half-circle bullnose along the top."""
    half_w = width * 0.5
    radius = min(half_w, height)
    flat_height = max(0.0, height - radius)
    points: list[tuple[float, float]] = [
        (-half_w, 0.0),
        (half_w, 0.0),
        (half_w, flat_height),
    ]
    for index in range(1, segments):
        theta = math.pi * (index / float(segments))
        points.append((half_w * math.cos(theta), flat_height + radius * math.sin(theta)))
    points.append((-half_w, flat_height))
    return points


_PROFILE_BUILDERS = {
    "rounded_band": _rounded_band_profile,
    "rabbet": _rabbet_profile,
    "ogee": _ogee_profile,
    "bullnose": _bullnose_profile,
}


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: TrimAttributes = node.typed_attributes

    if attrs.profile == "flat_band":
        # Simple box: length along edge_axis, cross section across the other two.
        axis_order = {"x": ("length_cm", "cross_section_width_cm", "cross_section_height_cm"),
                      "y": ("cross_section_width_cm", "length_cm", "cross_section_height_cm"),
                      "z": ("cross_section_width_cm", "cross_section_height_cm", "length_cm")}
        wkey, hkey, dkey = axis_order[attrs.edge_axis]
        parameters: dict[str, object] = {
            "width_cm": float(getattr(attrs, wkey)),
            "height_cm": float(getattr(attrs, hkey)),
            "depth_cm": float(getattr(attrs, dkey)),
            "trim_profile": attrs.profile,
            "trim_edge_axis": attrs.edge_axis,
        }
        if attrs.region_id is not None:
            parameters["region_id"] = attrs.region_id
        yield ShapeOp(
            op="solid.box",
            target=node.node_id,
            parameters=parameters,
            purpose=f"procedural_trim.{attrs.profile}",
        )
        return

    # Non-flat profiles: emit an extruded_profile swept along edge_axis.
    builder = _PROFILE_BUILDERS.get(attrs.profile)
    if builder is None:
        # Unreachable given the schema validates profile, but defensive.
        raise ValueError(f"trim.profile={attrs.profile!r} has no profile builder")

    profile_polygon = builder(
        attrs.cross_section_width_cm,
        attrs.cross_section_height_cm,
    )
    parameters = {
        "profile_polygon": tuple(profile_polygon),
        "extrude_height": float(attrs.length_cm),
        "axis": attrs.edge_axis,
        "trim_profile": attrs.profile,
        "trim_edge_axis": attrs.edge_axis,
    }
    if attrs.region_id is not None:
        parameters["region_id"] = attrs.region_id
    yield ShapeOp(
        op="solid.extruded_profile",
        target=node.node_id,
        parameters=parameters,
        purpose=f"procedural_trim.{attrs.profile}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
