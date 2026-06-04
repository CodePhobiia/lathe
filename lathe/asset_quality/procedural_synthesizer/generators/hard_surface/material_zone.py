"""Generator for node_type='material_zone' in the hard_surface domain.

Translates a typed MaterialZoneAttributes into a single ShapeIR v2
``op.material_zone`` op that carries the zone metadata without
emitting geometry. The surface stage consumes this op to resolve
material assignments / overlay zones / wear zones / decal zones.

No family-name awareness; the zone metadata flows entirely through
typed attributes. Downstream stages that need the material zone
record can read it from the op's ``parameters`` payload directly.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.material_zone import MaterialZoneAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator

_MANIFEST = GeneratorCapabilityManifest(
    node_type="material_zone",
    domain="hard_surface",
    consumed_attribute_fields=(
        "zone_id",
        "material_hint",
        "priority",
        "host_face_axis",
        "tags",
    ),
    consumed_style_fields=("parameter_priors",),
    emitted_op_kinds=("op.material_zone",),
    required_kernel_capabilities=(),  # metadata only; no kernel call
    fallback_diagnostics=(),
    output_kind="material_metadata",
)


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: MaterialZoneAttributes = node.typed_attributes
    parameters: dict[str, object] = {
        "zone_id": attrs.zone_id,
        "material_hint": attrs.material_hint,
        "priority": int(attrs.priority),
    }
    if attrs.host_face_axis is not None:
        parameters["host_face_axis"] = attrs.host_face_axis
    if attrs.tags:
        parameters["tags"] = list(attrs.tags)
    yield ShapeOp(
        op="op.material_zone",
        target=node.node_id,
        parameters=parameters,
        purpose=f"procedural_material_zone.{attrs.zone_id}",
    )


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
