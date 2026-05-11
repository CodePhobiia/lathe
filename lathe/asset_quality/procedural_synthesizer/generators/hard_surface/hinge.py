"""Generator for node_type='hinge' in the hard_surface domain.

Emits 2 solid.box ops (leaves) + 1 solid.cylinder op (barrel/pin).

  - butt / strap / piano: two flat leaves + central barrel.
  - concealed: leaves only (recessed mounting); single leaf for
    visible side, barrel emitted but tagged concealed.
  - barrel: cylindrical barrel emphasized (larger radius), leaves
    narrower.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.hinge import HingeAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="hinge",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "leaf_width_cm",
        "leaf_height_cm",
        "leaf_thickness_cm",
        "barrel_radius_cm",
        "pin_axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.cylinder"),
    required_kernel_capabilities=("solid.box", "solid.cylinder"),
    fallback_diagnostics=("hinge_unsupported_style",),
    output_kind="visible_geometry",
)


def _leaf_extents(pin_axis: str, w: float, h: float, t: float) -> dict[str, float]:
    """Pin axis controls h direction (leaf_height). The remaining axes
    are width (longer) x thickness (thinner)."""
    if pin_axis == "x":
        return {"width_cm": h, "height_cm": w, "depth_cm": t}
    if pin_axis == "y":
        return {"width_cm": w, "height_cm": h, "depth_cm": t}
    return {"width_cm": w, "height_cm": t, "depth_cm": h}


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: HingeAttributes = node.typed_attributes
    region = attrs.region_id

    leaf_count = 1 if attrs.style == "concealed" else 2
    for leaf_index in range(leaf_count):
        leaf_extents = _leaf_extents(
            attrs.pin_axis,
            attrs.leaf_width_cm,
            attrs.leaf_height_cm,
            attrs.leaf_thickness_cm,
        )
        leaf_params: dict[str, object] = {
            **leaf_extents,
            "hinge_style": attrs.style,
            "hinge_part": "leaf",
            "leaf_index": leaf_index,
            "pin_axis": attrs.pin_axis,
        }
        if region is not None:
            leaf_params["region_id"] = f"{region}.leaf.{leaf_index}"
        yield ShapeOp(
            op="solid.box",
            target=f"{node.node_id}.leaf.{leaf_index}",
            parameters=leaf_params,
            purpose=f"procedural_hinge.{attrs.style}.leaf[{leaf_index}]",
        )

    barrel_params: dict[str, object] = {
        "radius_cm": float(attrs.barrel_radius_cm),
        "height_cm": float(attrs.leaf_height_cm),
        "axis": attrs.pin_axis,
        "hinge_style": attrs.style,
        "hinge_part": "barrel",
    }
    if attrs.style == "concealed":
        barrel_params["concealed"] = True
    if region is not None:
        barrel_params["region_id"] = f"{region}.barrel"
    yield ShapeOp(
        op="solid.cylinder",
        target=f"{node.node_id}.barrel",
        parameters=barrel_params,
        purpose=f"procedural_hinge.{attrs.style}.barrel",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
