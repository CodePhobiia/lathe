"""Generator for node_type='mount' in the hard_surface domain.

Emits the mount pad as a solid.box, plus N subtractive solid.cylinder
ops for anchor through-holes. Flange uses a solid.cylinder pad for
circular geometry; all other styles use a box.

Anchor holes are emitted as subtractive cutters (blend_mode=subtract);
downstream boolean stages perform the actual subtraction.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.mount import MountAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="mount",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "width_cm",
        "depth_cm",
        "height_cm",
        "anchor_hole_count",
        "anchor_hole_radius_cm",
        "host_face_axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.cylinder"),
    required_kernel_capabilities=("solid.box", "solid.cylinder"),
    fallback_diagnostics=("mount_unsupported_style",),
    output_kind="visible_geometry",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: MountAttributes = node.typed_attributes
    region = attrs.region_id

    if attrs.style == "flange":
        radius = max(attrs.width_cm, attrs.depth_cm) * 0.5
        pad_params: dict[str, object] = {
            "radius_cm": float(radius),
            "height_cm": float(attrs.height_cm),
            "axis": attrs.host_face_axis,
            "mount_style": attrs.style,
            "mount_part": "pad",
        }
        if region is not None:
            pad_params["region_id"] = f"{region}.pad"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.pad",
            parameters=pad_params,
            purpose=f"procedural_mount.{attrs.style}.pad",
        )
    else:
        pad_params = {
            "width_cm": float(attrs.width_cm),
            "height_cm": float(attrs.height_cm),
            "depth_cm": float(attrs.depth_cm),
            "mount_style": attrs.style,
            "mount_part": "pad",
            "host_face_axis": attrs.host_face_axis,
        }
        if region is not None:
            pad_params["region_id"] = f"{region}.pad"
        yield ShapeOp(
            op="solid.box",
            target=f"{node.node_id}.pad",
            parameters=pad_params,
            purpose=f"procedural_mount.{attrs.style}.pad",
        )

    # Anchor through-holes (subtractive)
    for hole_index in range(attrs.anchor_hole_count):
        hole_params: dict[str, object] = {
            "radius_cm": float(attrs.anchor_hole_radius_cm),
            "height_cm": float(attrs.height_cm * 1.1),
            "axis": attrs.host_face_axis,
            "mount_style": attrs.style,
            "mount_part": "anchor_hole",
            "hole_index": hole_index,
            "blend_mode": "subtract",
        }
        if region is not None:
            hole_params["region_id"] = f"{region}.anchor.{hole_index}"
        yield ShapeOp(
            op="solid.cylinder",
            target=f"{node.node_id}.anchor.{hole_index}",
            parameters=hole_params,
            purpose=f"procedural_mount.{attrs.style}.anchor[{hole_index}]",
        )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
