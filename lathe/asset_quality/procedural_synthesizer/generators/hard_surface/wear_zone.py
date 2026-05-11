"""Generator for node_type='wear_zone' in the hard_surface domain.

Emits a metadata-only ``op.wear_zone`` op carrying the wear record.
No geometry; the surface stage consumes the op to bias wear masks
during basecolor / roughness / normal authoring.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.wear_zone import WearZoneAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="wear_zone",
    domain="hard_surface",
    consumed_attribute_fields=(
        "zone_id",
        "wear_kind",
        "intensity",
        "host_face_axis",
        "coverage_fraction",
        "tags",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("op.wear_zone",),
    required_kernel_capabilities=(),
    fallback_diagnostics=(),
    output_kind="material_metadata",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: WearZoneAttributes = node.typed_attributes
    parameters: dict[str, object] = {
        "zone_id": attrs.zone_id,
        "wear_kind": attrs.wear_kind,
        "intensity": attrs.intensity,
        "coverage_fraction": float(attrs.coverage_fraction),
    }
    if attrs.host_face_axis is not None:
        parameters["host_face_axis"] = attrs.host_face_axis
    if attrs.tags:
        parameters["tags"] = list(attrs.tags)
    yield ShapeOp(
        op="op.wear_zone",
        target=node.node_id,
        parameters=parameters,
        purpose=f"procedural_wear_zone.{attrs.zone_id}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
