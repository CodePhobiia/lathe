"""Generator for node_type='latch' in the hard_surface domain.

Emits a mounting plate (solid.box) plus a style-specific arm. Mechanism
kinematics are out of scope; latches are emitted in their closed-state
visible geometry.

  - hasp / draw_latch: arm is solid.box (flat strap)
  - barrel_lock / cam_lock: arm is solid.cylinder (cylindrical body)
  - padlock_eye: arm is solid.torus (D-shackle eye)
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.latch import LatchAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="latch",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "plate_width_cm",
        "plate_height_cm",
        "plate_thickness_cm",
        "arm_length_cm",
        "arm_radius_cm",
        "host_face_axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.cylinder", "solid.torus"),
    required_kernel_capabilities=("solid.box", "solid.cylinder"),
    fallback_diagnostics=("latch_unsupported_style",),
    output_kind="visible_geometry",
)


def _plate_extents(axis: str, w: float, h: float, t: float) -> dict[str, float]:
    if axis == "x":
        return {"width_cm": t, "height_cm": w, "depth_cm": h}
    if axis == "y":
        return {"width_cm": w, "height_cm": t, "depth_cm": h}
    return {"width_cm": w, "height_cm": h, "depth_cm": t}


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: LatchAttributes = node.typed_attributes
    region = attrs.region_id

    plate_extents = _plate_extents(
        attrs.host_face_axis,
        attrs.plate_width_cm,
        attrs.plate_height_cm,
        attrs.plate_thickness_cm,
    )
    plate_params: dict[str, object] = {
        **plate_extents,
        "latch_style": attrs.style,
        "latch_part": "plate",
        "host_face_axis": attrs.host_face_axis,
    }
    if region is not None:
        plate_params["region_id"] = f"{region}.plate"
    yield ShapeOp(
        op="solid.box",
        target=f"{node.node_id}.plate",
        parameters=plate_params,
        purpose=f"procedural_latch.{attrs.style}.plate",
    )

    if attrs.style in ("hasp", "draw_latch"):
        arm_extents = _plate_extents(
            attrs.host_face_axis,
            attrs.arm_length_cm,
            attrs.arm_radius_cm * 2.0,
            attrs.plate_thickness_cm * 0.6,
        )
        arm_params: dict[str, object] = {
            **arm_extents,
            "latch_style": attrs.style,
            "latch_part": "arm",
            "host_face_axis": attrs.host_face_axis,
        }
        if region is not None:
            arm_params["region_id"] = f"{region}.arm"
        yield ShapeOp(
            op="solid.box",
            target=f"{node.node_id}.arm",
            parameters=arm_params,
            purpose=f"procedural_latch.{attrs.style}.arm",
        )
        return

    if attrs.style in ("barrel_lock", "cam_lock"):
        arm_params = {
            "radius_cm": float(attrs.arm_radius_cm),
            "height_cm": float(attrs.arm_length_cm),
            "axis": attrs.host_face_axis,
            "latch_style": attrs.style,
            "latch_part": "barrel",
        }
        if region is not None:
            arm_params["region_id"] = f"{region}.barrel"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.barrel",
            parameters=arm_params,
            purpose=f"procedural_latch.{attrs.style}.barrel",
        )
        return

    # padlock_eye: D-shackle as torus
    torus_params: dict[str, object] = {
        "major_radius_cm": float(attrs.arm_length_cm * 0.5),
        "minor_radius_cm": float(attrs.arm_radius_cm),
        "axis": attrs.host_face_axis,
        "latch_style": attrs.style,
        "latch_part": "shackle",
    }
    if region is not None:
        torus_params["region_id"] = f"{region}.shackle"
    yield ShapeOp(
        op="solid.torus",
        target=f"{node.node_id}.shackle",
        parameters=torus_params,
        purpose=f"procedural_latch.{attrs.style}.shackle",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
