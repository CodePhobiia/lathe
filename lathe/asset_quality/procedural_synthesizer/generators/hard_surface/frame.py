"""Generator for node_type='frame' in the hard_surface domain.

Translates a typed FrameAttributes into 4 ShapeIR v2 solid.box ops —
one per frame member (top rail, bottom rail, left stile, right
stile). Emitting one op per member preserves face-attribution
downstream so traces can attribute material zones and edge treatments
to specific frame parts.

No family-name awareness; the frame composition is parameterized
entirely through typed attributes that StyleKnowledge / brief inputs
populate.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.frame import FrameAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="frame",
    domain="hard_surface",
    consumed_attribute_fields=(
        "plane",
        "outer_width_cm",
        "outer_height_cm",
        "member_thickness_cm",
        "protrusion_cm",
        "corner_style",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box",),
    required_kernel_capabilities=("solid.box",),
    fallback_diagnostics=("frame_unsupported_corner_style",),
    output_kind="visible_geometry",
)


# Mapping from plane -> (u_axis_index, v_axis_index, normal_axis_index)
# where u and v are the in-plane axes and normal is the thickness axis.
_PLANE_AXES: dict[str, tuple[int, int, int]] = {
    "xy": (0, 1, 2),  # u=x, v=y, normal=z
    "xz": (0, 2, 1),  # u=x, v=z, normal=y
    "yz": (1, 2, 0),  # u=y, v=z, normal=x
}

# Frame-member tags used for the per-rail target / region_id suffix.
_MEMBER_TAGS: tuple[str, ...] = ("top_rail", "bottom_rail", "left_stile", "right_stile")


def _member_extents(
    member_tag: str,
    outer_width: float,
    outer_height: float,
    member_thickness: float,
    protrusion: float,
) -> tuple[float, float, float]:
    """Return (u_extent, v_extent, normal_extent) for a frame member.

    Top/bottom rails span the full outer_width but are member_thickness
    tall. Left/right stiles span outer_height minus the rail thicknesses
    so the four members meet at sharp corners without overlap.
    """
    rail_thickness = float(member_thickness)
    side_rail_height = float(outer_height) - 2.0 * rail_thickness
    side_rail_height = max(side_rail_height, rail_thickness)  # clamp degenerate inputs
    normal_extent = max(rail_thickness, float(protrusion))
    if member_tag in ("top_rail", "bottom_rail"):
        return (float(outer_width), rail_thickness, normal_extent)
    # left_stile / right_stile
    return (rail_thickness, side_rail_height, normal_extent)


def _member_center_offset(
    member_tag: str,
    outer_width: float,
    outer_height: float,
    member_thickness: float,
) -> tuple[float, float]:
    """Return the (u_offset, v_offset) of a member center relative to frame center."""
    rail_thickness = float(member_thickness)
    half_outer_width = float(outer_width) * 0.5
    half_outer_height = float(outer_height) * 0.5
    half_rail = rail_thickness * 0.5
    if member_tag == "top_rail":
        return (0.0, half_outer_height - half_rail)
    if member_tag == "bottom_rail":
        return (0.0, -(half_outer_height - half_rail))
    if member_tag == "left_stile":
        return (-(half_outer_width - half_rail), 0.0)
    if member_tag == "right_stile":
        return (half_outer_width - half_rail, 0.0)
    raise ValueError(f"unknown frame member tag {member_tag!r}")


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: FrameAttributes = node.typed_attributes
    u_axis, v_axis, normal_axis = _PLANE_AXES[attrs.plane]
    axis_names = ("width_cm", "height_cm", "depth_cm")

    for member_tag in _MEMBER_TAGS:
        u_extent, v_extent, n_extent = _member_extents(
            member_tag,
            attrs.outer_width_cm,
            attrs.outer_height_cm,
            attrs.member_thickness_cm,
            attrs.protrusion_cm,
        )
        u_off, v_off = _member_center_offset(
            member_tag,
            attrs.outer_width_cm,
            attrs.outer_height_cm,
            attrs.member_thickness_cm,
        )
        # Build the box's xyz extents from (u, v, normal) extents per plane.
        extents_by_axis = [0.0, 0.0, 0.0]
        extents_by_axis[u_axis] = u_extent
        extents_by_axis[v_axis] = v_extent
        extents_by_axis[normal_axis] = n_extent
        # Build the offset for trace recording (the kernel itself uses
        # absolute coordinates; downstream stages compose offsets via
        # target / edge metadata).
        offset_by_axis = [0.0, 0.0, 0.0]
        offset_by_axis[u_axis] = u_off
        offset_by_axis[v_axis] = v_off

        member_target = f"{node.node_id}.{member_tag}"
        parameters: dict[str, object] = {
            axis_names[0]: float(extents_by_axis[0]),
            axis_names[1]: float(extents_by_axis[1]),
            axis_names[2]: float(extents_by_axis[2]),
            "offset_cm": tuple(float(v) for v in offset_by_axis),
            "frame_member": member_tag,
            "frame_corner_style": attrs.corner_style,
        }
        if attrs.region_id is not None:
            parameters["region_id"] = f"{attrs.region_id}.{member_tag}"
        yield ShapeOp(
            op="solid.box",
            target=member_target,
            parameters=parameters,
            purpose=f"procedural_frame.{member_tag}",
        )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
