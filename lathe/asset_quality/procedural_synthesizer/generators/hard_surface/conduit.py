"""Generator for node_type='conduit' in the hard_surface domain.

Emits a single solid.cylinder for the straight span, plus
solid.sphere endcaps when bend_count > 0 (the spheres become bend
joints when concatenated with adjacent conduits along a routed path).
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.conduit import ConduitAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="conduit",
    domain="hard_surface",
    consumed_attribute_fields=(
        "kind",
        "radius_cm",
        "length_cm",
        "axis",
        "bend_count",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.cylinder", "solid.sphere"),
    required_kernel_capabilities=("solid.cylinder", "solid.sphere"),
    fallback_diagnostics=("conduit_unsupported_kind",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: ConduitAttributes = node.typed_attributes
    region = attrs.region_id

    span_params: dict[str, object] = {
        "radius_cm": float(attrs.radius_cm),
        "height_cm": float(attrs.length_cm),
        "axis": attrs.axis,
        "conduit_kind": attrs.kind,
        "conduit_part": "span",
    }
    if region is not None:
        span_params["region_id"] = f"{region}.span"
    yield ShapeOp(
        op="solid.cylinder",
        target=f"{node.node_id}.span",
        parameters=span_params,
        purpose=f"procedural_conduit.{attrs.kind}.span",
    )

    if attrs.bend_count > 0:
        for bend_index in range(min(2, attrs.bend_count)):
            endcap_params: dict[str, object] = {
                "radius_cm": float(attrs.radius_cm * 1.05),
                "conduit_kind": attrs.kind,
                "conduit_part": "endcap",
                "endcap_index": bend_index,
            }
            if region is not None:
                endcap_params["region_id"] = f"{region}.endcap.{bend_index}"
            yield ShapeOp(
                op="solid.sphere",
                target=f"{node.node_id}.endcap.{bend_index}",
                parameters=endcap_params,
                purpose=f"procedural_conduit.{attrs.kind}.endcap[{bend_index}]",
            )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
