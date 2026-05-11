"""Generator for node_type='panel' in the hard_surface domain.

Translates a typed PanelAttributes into a ShapeIR v2 solid.panel op
(the existing v2 first-class panel primitive). No family-name awareness.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.panel import PanelAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="panel",
    domain="hard_surface",
    consumed_attribute_fields=(
        "plane",
        "width_cm",
        "height_cm",
        "thickness_cm",
        "inset_depth_cm",
        "border_policy",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.panel",),
    required_kernel_capabilities=("solid.panel",),
    fallback_diagnostics=("panel_unsupported_border_policy",),
    output_kind="visible_geometry",
)


_PLANE_TO_AXIS: dict[str, str] = {
    "xy": "z",   # panel's flat face in xy plane => thickness along z
    "xz": "y",
    "yz": "x",
}


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: PanelAttributes = node.typed_attributes
    axis = _PLANE_TO_AXIS[attrs.plane]

    # ShapeIR v2 solid.panel kernel parameters
    parameters: dict[str, object] = {
        "width_cm": float(attrs.width_cm),
        "height_cm": float(attrs.height_cm),
        "thickness_cm": float(attrs.thickness_cm),
        "axis": axis,
    }
    if attrs.inset_depth_cm > 0:
        parameters["inset_depth_cm"] = float(attrs.inset_depth_cm)
    if attrs.border_policy != "sharp":
        parameters["border_policy"] = attrs.border_policy
    if attrs.region_id is not None:
        parameters["region_id"] = attrs.region_id

    yield ShapeOp(
        op="solid.panel",
        target=node.node_id,
        parameters=parameters,
        purpose="procedural_panel",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
