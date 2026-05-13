"""Generator for node_type='vent' in the hard_surface domain.

Translates a typed VentAttributes into a recess + slats:
  - One subtractive solid.box for the recess.
  - N solid.box ops for slats (horizontal_slat / vertical_slat).
  - One sphere-pack approximation (single solid.sphere per cell) for
    honeycomb (downstream surface stages can refine via decals).
  - Circular grille emits a circular pattern of solid.cylinder slats.

All emitted ops carry vent_style and vent_part tags so downstream
material stages can attribute paint / corrosion / grime.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.vent import VentAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="vent",
    domain="hard_surface",
    consumed_attribute_fields=(
        "style",
        "width_cm",
        "height_cm",
        "depth_cm",
        "slat_count",
        "host_face_axis",
        "region_id",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("solid.box", "solid.cylinder", "solid.sphere"),
    required_kernel_capabilities=("solid.box", "solid.cylinder"),
    fallback_diagnostics=("vent_unsupported_style",),
    output_kind="visible_geometry",
)


def _axis_to_extents(axis: str, depth: float, plane_w: float, plane_h: float) -> dict[str, float]:
    """Build a box extents dict where `axis` is the depth direction."""
    if axis == "x":
        return {"width_cm": depth, "height_cm": plane_w, "depth_cm": plane_h}
    if axis == "y":
        return {"width_cm": plane_w, "height_cm": depth, "depth_cm": plane_h}
    return {"width_cm": plane_w, "height_cm": plane_h, "depth_cm": depth}


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: VentAttributes = node.typed_attributes
    region = attrs.region_id

    # Recess (subtractive)
    recess_extents = _axis_to_extents(
        attrs.host_face_axis, attrs.depth_cm, attrs.width_cm, attrs.height_cm
    )
    recess_params: dict[str, object] = {
        **recess_extents,
        "vent_style": attrs.style,
        "vent_part": "recess",
        "blend_mode": "subtract",
        "host_face_axis": attrs.host_face_axis,
    }
    if region is not None:
        recess_params["region_id"] = f"{region}.recess"
    yield ShapeOp(
        op="solid.box",
        target=f"{node.node_id}.recess",
        parameters=recess_params,
        purpose=f"procedural_vent.{attrs.style}.recess",
    )

    # Slats per style
    slat_count = max(1, int(attrs.slat_count))
    if attrs.style in ("horizontal_slat", "vertical_slat"):
        # plane_w x plane_h is the in-face area; the long axis of slats
        # is plane_w (horizontal) or plane_h (vertical).
        long_dim = attrs.width_cm if attrs.style == "horizontal_slat" else attrs.height_cm
        cross_dim = attrs.height_cm if attrs.style == "horizontal_slat" else attrs.width_cm
        slat_thickness = cross_dim / (slat_count * 2.0 + 1.0)
        for index in range(slat_count):
            slat_extents = _axis_to_extents(
                attrs.host_face_axis,
                attrs.depth_cm * 0.5,
                long_dim if attrs.style == "horizontal_slat" else slat_thickness,
                slat_thickness if attrs.style == "horizontal_slat" else long_dim,
            )
            slat_params: dict[str, object] = {
                **slat_extents,
                "vent_style": attrs.style,
                "vent_part": "slat",
                "slat_index": index,
                "host_face_axis": attrs.host_face_axis,
            }
            if region is not None:
                slat_params["region_id"] = f"{region}.slat.{index}"
            yield ShapeOp(
                op="solid.box",
                target=f"{node.node_id}.slat.{index}",
                parameters=slat_params,
                purpose=f"procedural_vent.{attrs.style}.slat[{index}]",
            )
        return

    if attrs.style == "circular_grille":
        outer_radius = min(attrs.width_cm, attrs.height_cm) * 0.5
        ring_count = max(1, slat_count // 2)
        for ring in range(ring_count):
            radius = outer_radius * (ring + 1) / float(ring_count + 1)
            ring_params: dict[str, object] = {
                "radius_cm": float(radius),
                "height_cm": float(attrs.depth_cm * 0.4),
                "axis": attrs.host_face_axis,
                "vent_style": attrs.style,
                "vent_part": "ring",
                "ring_index": ring,
            }
            if region is not None:
                ring_params["region_id"] = f"{region}.ring.{ring}"
            yield ShapeOp(
                op="solid.cylinder",
                target=f"{node.node_id}.ring.{ring}",
                parameters=ring_params,
                purpose=f"procedural_vent.{attrs.style}.ring[{ring}]",
            )
        return

    # honeycomb: approximate with a sphere-cell grid; downstream
    # surface stages can refine to hex cells via decal masks.
    cell_radius = min(attrs.width_cm, attrs.height_cm) / float(slat_count * 2 + 1)
    rows = max(2, slat_count)
    cols = max(2, slat_count)
    for row in range(rows):
        for col in range(cols):
            cell_params: dict[str, object] = {
                "radius_cm": float(cell_radius),
                "vent_style": attrs.style,
                "vent_part": "cell",
                "cell_row": row,
                "cell_col": col,
            }
            if region is not None:
                cell_params["region_id"] = f"{region}.cell.{row}.{col}"
            yield ShapeOp(
                op="solid.sphere",
                target=f"{node.node_id}.cell.{row}.{col}",
                parameters=cell_params,
                purpose=f"procedural_vent.{attrs.style}.cell[{row},{col}]",
            )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
