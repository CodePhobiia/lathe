"""Generator for node_type='handle' in the hard_surface domain.

Translates a typed HandleAttributes into ShapeIR v2 ops per style:
  - bar / loop: 1 capsule running along ``axis``
  - knob: 1 sphere with optional cylinder standoff
  - recessed_grip: 1 capsule oriented in-plane (no standoff)
  - latch_lever: 1 elongated box (lever) on a cylinder pivot
  - pull_ring: 1 torus

No family-name awareness; all variation flows through typed attributes.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.handle import HandleAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="handle",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "length_cm",
        "grip_radius_cm",
        "standoff_cm",
        "axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=(
        "solid.capsule",
        "solid.cylinder",
        "solid.sphere",
        "solid.box",
        "solid.torus",
    ),
    required_kernel_capabilities=("solid.capsule", "solid.cylinder", "solid.sphere"),
    fallback_diagnostics=("handle_unsupported_style",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: HandleAttributes = node.typed_attributes
    region = attrs.region_id

    if attrs.style in ("bar", "loop"):
        params: dict[str, object] = {
            "radius_cm": float(attrs.grip_radius_cm),
            "length_cm": float(attrs.length_cm),
            "axis": attrs.axis,
            "handle_style": attrs.style,
        }
        if region is not None:
            params["region_id"] = region
        yield ShapeOp(
            op="solid.capsule",
            target=node.node_id,
            parameters=params,
            purpose=f"procedural_handle.{attrs.style}",
        )
        return

    if attrs.style == "knob":
        if attrs.standoff_cm > 0:
            standoff_params: dict[str, object] = {
                "radius_cm": float(attrs.grip_radius_cm * 0.6),
                "height_cm": float(attrs.standoff_cm),
                "axis": attrs.axis,
                "handle_style": attrs.style,
                "handle_part": "standoff",
            }
            if region is not None:
                standoff_params["region_id"] = f"{region}.standoff"
            yield ShapeOp(
                op="solid.cylinder",
                target=f"{node.node_id}.standoff",
                parameters=standoff_params,
                purpose=f"procedural_handle.{attrs.style}.standoff",
            )
        knob_params: dict[str, object] = {
            "radius_cm": float(attrs.length_cm * 0.5),
            "handle_style": attrs.style,
            "handle_part": "knob",
        }
        if region is not None:
            knob_params["region_id"] = f"{region}.knob"
        yield ShapeOp(
            op="solid.sphere",
            target=f"{node.node_id}.knob",
            parameters=knob_params,
            purpose=f"procedural_handle.{attrs.style}.knob",
        )
        return

    if attrs.style == "recessed_grip":
        # In-plane capsule; standoff is irrelevant for a recessed grip.
        params = {
            "radius_cm": float(attrs.grip_radius_cm),
            "length_cm": float(attrs.length_cm),
            "axis": attrs.axis,
            "handle_style": attrs.style,
        }
        if region is not None:
            params["region_id"] = region
        yield ShapeOp(
            op="solid.capsule",
            target=node.node_id,
            parameters=params,
            purpose=f"procedural_handle.{attrs.style}",
        )
        return

    if attrs.style == "latch_lever":
        pivot_params: dict[str, object] = {
            "radius_cm": float(attrs.grip_radius_cm * 1.2),
            "height_cm": float(attrs.standoff_cm if attrs.standoff_cm > 0 else attrs.grip_radius_cm),
            "axis": attrs.axis,
            "handle_style": attrs.style,
            "handle_part": "pivot",
        }
        if region is not None:
            pivot_params["region_id"] = f"{region}.pivot"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.pivot",
            parameters=pivot_params,
            purpose=f"procedural_handle.{attrs.style}.pivot",
        )
        # Lever — a thin elongated box perpendicular to pivot axis.
        axis_order = {"x": ("height_cm", "width_cm", "depth_cm"),
                      "y": ("width_cm", "height_cm", "depth_cm"),
                      "z": ("width_cm", "depth_cm", "height_cm")}
        keys = axis_order[attrs.axis]
        lever_extents: dict[str, float] = {
            keys[0]: float(attrs.length_cm),
            keys[1]: float(attrs.grip_radius_cm * 2.0),
            keys[2]: float(attrs.grip_radius_cm * 1.5),
        }
        lever_params: dict[str, object] = {
            **lever_extents,
            "handle_style": attrs.style,
            "handle_part": "lever",
        }
        if region is not None:
            lever_params["region_id"] = f"{region}.lever"
        yield ShapeOp(
            op="solid.box",
            target=f"{node.node_id}.lever",
            parameters=lever_params,
            purpose=f"procedural_handle.{attrs.style}.lever",
        )
        return

    if attrs.style == "pull_ring":
        ring_params: dict[str, object] = {
            "major_radius_cm": float(attrs.length_cm * 0.5),
            "minor_radius_cm": float(attrs.grip_radius_cm),
            "axis": attrs.axis,
            "handle_style": attrs.style,
        }
        if region is not None:
            ring_params["region_id"] = region
        yield ShapeOp(
            op="solid.torus",
            target=node.node_id,
            parameters=ring_params,
            purpose=f"procedural_handle.{attrs.style}",
        )
        return


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
