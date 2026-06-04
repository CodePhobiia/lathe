"""Generator for node_type='decal_zone' in the hard_surface domain.

Emits a metadata-only ``op.decal_zone`` op carrying the decal record.
No geometry; the surface stage consumes the op to place decals at
authoring time.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.decal_zone import DecalZoneAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="decal_zone",
    domain="hard_surface",
    consumed_attribute_fields=(
        "zone_id",
        "decal_intent",
        "size_cm",
        "host_face_axis",
        "priority",
        "tags",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("op.decal_zone",),
    required_kernel_capabilities=(),
    fallback_diagnostics=(),
    output_kind="material_metadata",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: DecalZoneAttributes = node.typed_attributes
    parameters: dict[str, object] = {
        "zone_id": attrs.zone_id,
        "decal_intent": attrs.decal_intent,
        "size_cm": [float(attrs.size_cm[0]), float(attrs.size_cm[1])],
        "priority": int(attrs.priority),
    }
    if attrs.host_face_axis is not None:
        parameters["host_face_axis"] = attrs.host_face_axis
    if attrs.tags:
        parameters["tags"] = list(attrs.tags)
    yield ShapeOp(
        op="op.decal_zone",
        target=node.node_id,
        parameters=parameters,
        purpose=f"procedural_decal_zone.{attrs.zone_id}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
