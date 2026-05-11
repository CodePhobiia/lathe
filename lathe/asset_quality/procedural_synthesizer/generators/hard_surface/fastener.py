"""Generator for node_type='fastener' in the hard_surface domain.

Translates a typed FastenerAttributes into 2 ShapeIR v2 solid.cylinder
ops — one for the fastener head (short, wide) and one for the shaft
(long, narrow). Per-fastener targeting preserves face-attribution
downstream so traces can attribute fastener corrosion / wear masks
specifically.

No family-name awareness; all geometry flows through typed attributes.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.fastener import FastenerAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="fastener",
    domain="hard_surface",
    consumed_attribute_fields=(
        "kind",
        "head_radius_cm",
        "head_height_cm",
        "shaft_radius_cm",
        "shaft_length_cm",
        "axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.cylinder",),
    required_kernel_capabilities=("solid.cylinder",),
    fallback_diagnostics=("fastener_unsupported_kind",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: FastenerAttributes = node.typed_attributes

    head_parameters: dict[str, object] = {
        "radius_cm": float(attrs.head_radius_cm),
        "height_cm": float(attrs.head_height_cm),
        "axis": attrs.axis,
        "fastener_kind": attrs.kind,
        "fastener_part": "head",
    }
    if attrs.region_id is not None:
        head_parameters["region_id"] = f"{attrs.region_id}.head"
    yield ShapeOp(
        op="solid.cylinder",
        target=f"{node.node_id}.head",
        parameters=head_parameters,
        purpose=f"procedural_fastener.{attrs.kind}.head",
    )

    shaft_parameters: dict[str, object] = {
        "radius_cm": float(attrs.shaft_radius_cm),
        "height_cm": float(attrs.shaft_length_cm),
        "axis": attrs.axis,
        "fastener_kind": attrs.kind,
        "fastener_part": "shaft",
    }
    if attrs.region_id is not None:
        shaft_parameters["region_id"] = f"{attrs.region_id}.shaft"
    yield ShapeOp(
        op="solid.cylinder",
        target=f"{node.node_id}.shaft",
        parameters=shaft_parameters,
        purpose=f"procedural_fastener.{attrs.kind}.shaft",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
