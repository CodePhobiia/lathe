"""Generator for node_type='socket' in the hard_surface domain.

Emits a subtractive cylinder (round profile) or box (square /
rounded_square / keyway profiles). Subtraction against the host
volume is performed downstream; this generator emits the cutter
geometry tagged with ``blend_mode=subtract``.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.socket import SocketAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="socket",
    domain="hard_surface",
    consumed_attribute_fields=(
        "depth_axis",
        "depth_cm",
        "radius_cm",
        "profile",
        "chamfer_cm",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.cylinder", "solid.box", "solid.rounded_box"),
    required_kernel_capabilities=("solid.cylinder", "solid.box"),
    fallback_diagnostics=("socket_unsupported_profile",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: SocketAttributes = node.typed_attributes
    region = attrs.region_id

    if attrs.profile == "round":
        params: dict[str, object] = {
            "radius_cm": float(attrs.radius_cm),
            "height_cm": float(attrs.depth_cm),
            "axis": attrs.depth_axis,
            "socket_profile": attrs.profile,
            "blend_mode": "subtract",
        }
        if attrs.chamfer_cm > 0:
            params["chamfer_cm"] = float(attrs.chamfer_cm)
        if region is not None:
            params["region_id"] = region
        yield ShapeOp(
            op="solid.cylinder",
            target=node.node_id,
            parameters=params,
            purpose=f"procedural_socket.{attrs.profile}",
        )
        return

    # square / rounded_square / keyway: box-based cutter.
    side = float(attrs.radius_cm) * 2.0
    axis_order = {
        "x": ("depth", "side", "side"),
        "y": ("side", "depth", "side"),
        "z": ("side", "side", "depth"),
    }
    keys = axis_order[attrs.depth_axis]
    extents = {
        "width_cm": float(attrs.depth_cm if keys[0] == "depth" else side),
        "height_cm": float(attrs.depth_cm if keys[1] == "depth" else side),
        "depth_cm": float(attrs.depth_cm if keys[2] == "depth" else side),
    }
    params = {
        **extents,
        "socket_profile": attrs.profile,
        "blend_mode": "subtract",
    }
    if attrs.profile == "rounded_square":
        params["rounding_cm"] = float(attrs.radius_cm) * 0.2
        op = "solid.rounded_box"
    else:
        op = "solid.box"
    if attrs.profile == "keyway":
        # Keyway = rectangular slot with one rounded edge — flag for downstream surfacing
        params["socket_keyway_orientation"] = attrs.depth_axis
    if attrs.chamfer_cm > 0:
        params["chamfer_cm"] = float(attrs.chamfer_cm)
    if region is not None:
        params["region_id"] = region
    yield ShapeOp(
        op=op,
        target=node.node_id,
        parameters=params,
        purpose=f"procedural_socket.{attrs.profile}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
