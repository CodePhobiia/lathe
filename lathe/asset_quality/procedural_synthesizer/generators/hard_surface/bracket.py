"""Generator for node_type='bracket' in the hard_surface domain.

A bracket connects two perpendicular faces of a host volume. The
geometry is two perpendicular plates (an L shape) for l_bracket /
corner_brace / angle_plate, three plates (T shape) for t_bracket, or
a single triangular fillet plate for gusset.

Emits 1-3 solid.box ops; no booleans needed — placement of the host
edge determines the final assembled topology.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.bracket import BracketAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="bracket",
    domain="hard_surface",
    consumed_attribute_fields=(
        "profile",
        "leg_length_cm",
        "leg_width_cm",
        "thickness_cm",
        "orientation",
        "fillet_cm",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box",),
    required_kernel_capabilities=("solid.box",),
    fallback_diagnostics=("bracket_unsupported_profile",),
    output_kind="visible_geometry",
)


def _leg_extents(
    orientation: str, leg_axis: str, leg_length: float, leg_width: float, thickness: float
) -> dict[str, float]:
    """Compute extents for a bracket leg given orientation + axis.

    orientation names the plane (xy/xz/yz). leg_axis names which axis
    inside that plane is the long axis. The remaining in-plane axis is
    leg_width; the out-of-plane axis is thickness.
    """
    plane_axes = {
        "xy": ("x", "y", "z"),
        "xz": ("x", "z", "y"),
        "yz": ("y", "z", "x"),
    }
    in_a, in_b, out = plane_axes[orientation]
    long_axis = leg_axis
    wide_axis = in_a if leg_axis == in_b else in_b
    out_axis = out

    extents = {"width_cm": 0.0, "height_cm": 0.0, "depth_cm": 0.0}
    axis_to_key = {"x": "width_cm", "y": "height_cm", "z": "depth_cm"}
    extents[axis_to_key[long_axis]] = float(leg_length)
    extents[axis_to_key[wide_axis]] = float(leg_width)
    extents[axis_to_key[out_axis]] = float(thickness)
    return extents


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: BracketAttributes = node.typed_attributes
    region = attrs.region_id
    plane_axes = {
        "xy": ("x", "y"),
        "xz": ("x", "z"),
        "yz": ("y", "z"),
    }
    axis_a, axis_b = plane_axes[attrs.orientation]

    # leg A: long along axis_a, thin along the out-of-plane axis
    leg_a = _leg_extents(
        attrs.orientation, axis_a, attrs.leg_length_cm, attrs.leg_width_cm, attrs.thickness_cm
    )
    params_a: dict[str, object] = {
        **leg_a,
        "bracket_profile": attrs.profile,
        "bracket_part": "leg_a",
        "bracket_orientation": attrs.orientation,
    }
    if attrs.fillet_cm > 0:
        params_a["fillet_cm"] = float(attrs.fillet_cm)
    if region is not None:
        params_a["region_id"] = f"{region}.leg_a"
    yield ShapeOp(
        op="solid.box",
        target=f"{node.node_id}.leg_a",
        parameters=params_a,
        purpose=f"procedural_bracket.{attrs.profile}.leg_a",
    )

    # gusset is single-leg (triangular fillet — emitted as a single
    # plate; downstream surface stages can shape it)
    if attrs.profile == "gusset":
        return

    # leg B: long along axis_b
    leg_b = _leg_extents(
        attrs.orientation, axis_b, attrs.leg_length_cm, attrs.leg_width_cm, attrs.thickness_cm
    )
    params_b: dict[str, object] = {
        **leg_b,
        "bracket_profile": attrs.profile,
        "bracket_part": "leg_b",
        "bracket_orientation": attrs.orientation,
    }
    if attrs.fillet_cm > 0:
        params_b["fillet_cm"] = float(attrs.fillet_cm)
    if region is not None:
        params_b["region_id"] = f"{region}.leg_b"
    yield ShapeOp(
        op="solid.box",
        target=f"{node.node_id}.leg_b",
        parameters=params_b,
        purpose=f"procedural_bracket.{attrs.profile}.leg_b",
    )

    # T-bracket adds a third leg perpendicular to A in the same plane
    if attrs.profile == "t_bracket":
        leg_c = _leg_extents(
            attrs.orientation, axis_b, attrs.leg_length_cm * 0.5, attrs.leg_width_cm, attrs.thickness_cm
        )
        params_c: dict[str, object] = {
            **leg_c,
            "bracket_profile": attrs.profile,
            "bracket_part": "leg_c",
            "bracket_orientation": attrs.orientation,
        }
        if region is not None:
            params_c["region_id"] = f"{region}.leg_c"
        yield ShapeOp(
            op="solid.box",
            target=f"{node.node_id}.leg_c",
            parameters=params_c,
            purpose=f"procedural_bracket.{attrs.profile}.leg_c",
        )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
