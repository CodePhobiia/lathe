"""Generator for node_type='inset' in the hard_surface domain.

Translates a typed InsetAttributes into a single subtractive box op
(flat-bottom inset) or rounded_box op (rounded-bottom inset).
Downstream stages perform the actual boolean subtraction against the
host volume; the synthesizer's job is to emit the cutter geometry +
recess metadata.

No family-name awareness; all variation flows through typed attributes.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.inset import InsetAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="inset",
    domain="hard_surface",
    consumed_attribute_fields=(
        "depth_axis",
        "depth_cm",
        "width_cm",
        "height_cm",
        "bottom_style",
        "rounding_cm",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.rounded_box"),
    required_kernel_capabilities=("solid.box",),
    fallback_diagnostics=("inset_unsupported_bottom_style",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: InsetAttributes = node.typed_attributes

    # The inset cutter's extent layout: depth along depth_axis,
    # width/height across the perpendicular axes.
    axis_order = {
        "x": ("depth_cm", "width_cm", "height_cm"),
        "y": ("width_cm", "depth_cm", "height_cm"),
        "z": ("width_cm", "height_cm", "depth_cm"),
    }
    wkey, hkey, dkey = axis_order[attrs.depth_axis]

    parameters: dict[str, object] = {
        "width_cm": float(getattr(attrs, wkey)),
        "height_cm": float(getattr(attrs, hkey)),
        "depth_cm": float(getattr(attrs, dkey)),
        "inset_depth_axis": attrs.depth_axis,
        "inset_bottom_style": attrs.bottom_style,
        "blend_mode": "subtract",
    }
    if attrs.region_id is not None:
        parameters["region_id"] = attrs.region_id

    if attrs.bottom_style == "rounded" and attrs.rounding_cm > 0:
        parameters["rounding_cm"] = float(attrs.rounding_cm)
        yield ShapeOp(
            op="solid.rounded_box",
            target=node.node_id,
            parameters=parameters,
            purpose=f"procedural_inset.{attrs.bottom_style}",
        )
        return

    # Flat or beveled bottom — box op. Beveled finishing is downstream
    # surface stage's responsibility; we pass the bottom_style metadata
    # so it can apply the right finishing pass.
    yield ShapeOp(
        op="solid.box",
        target=node.node_id,
        parameters=parameters,
        purpose=f"procedural_inset.{attrs.bottom_style}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
