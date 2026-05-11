"""Generator for node_type='weld' in the hard_surface domain.

Emits a continuous solid.cylinder for fillet / butt / seam welds, or
N solid.sphere ops for spot / tack welds distributed along the axis.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.weld import WeldAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="weld",
    domain="hard_surface",
    consumed_attribute_fields=(
        "kind",
        "bead_radius_cm",
        "length_cm",
        "axis",
        "spot_count",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.cylinder", "solid.sphere"),
    required_kernel_capabilities=("solid.cylinder", "solid.sphere"),
    fallback_diagnostics=("weld_unsupported_kind",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: WeldAttributes = node.typed_attributes
    region = attrs.region_id

    if attrs.kind in ("fillet", "butt", "seam"):
        bead_params: dict[str, object] = {
            "radius_cm": float(attrs.bead_radius_cm),
            "height_cm": float(attrs.length_cm),
            "axis": attrs.axis,
            "weld_kind": attrs.kind,
            "weld_part": "bead",
        }
        if region is not None:
            bead_params["region_id"] = f"{region}.bead"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.bead",
            parameters=bead_params,
            purpose=f"procedural_weld.{attrs.kind}.bead",
        )
        return

    # spot / tack: distributed sphere beads
    spot_count = max(1, attrs.spot_count)
    for index in range(spot_count):
        spot_params: dict[str, object] = {
            "radius_cm": float(attrs.bead_radius_cm),
            "weld_kind": attrs.kind,
            "weld_part": "spot",
            "spot_index": index,
            "axis": attrs.axis,
            "position_t": index / float(max(1, spot_count - 1)) if spot_count > 1 else 0.5,
            "span_length_cm": float(attrs.length_cm),
        }
        if region is not None:
            spot_params["region_id"] = f"{region}.spot.{index}"
        yield ShapeOp(
            op="solid.sphere",
            target=f"{node.node_id}.spot.{index}",
            parameters=spot_params,
            purpose=f"procedural_weld.{attrs.kind}.spot[{index}]",
        )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
