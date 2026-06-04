"""Edge decorator for edge_type='wraps_around' in the hard_surface domain.

When source `wraps_around` target, the source's geometry encloses the
target (additively). Typical for trim that wraps a panel edge, banding
around a frame, or a guard around an interior volume. Emits an op.union
with the source as an additive child of the target's boolean tree.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="wraps_around",
    domain="hard_surface",
    consumed_attribute_fields=("offset_cm",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("wraps_around_unresolved_target",),
    output_kind="visible_geometry",
)


def _impl(
    edge: ConstructionEdgeTyped,
    ctx: SynthesizerContext,
    op_resolver: OpResolver,
) -> Iterable[ShapeOp]:
    source_ops = op_resolver.ops_for_node(edge.source_id)
    target_ops = op_resolver.ops_for_node(edge.target_id)
    if not source_ops or not target_ops:
        return

    target_op = target_ops[0]
    raw_attrs = edge.raw_attributes if isinstance(edge.raw_attributes, dict) else {}
    offset_cm = raw_attrs.get("offset_cm")
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "wraps_around",
            "blend_mode": "add",
        }
        if offset_cm is not None:
            params["wrap_offset_cm"] = float(offset_cm)
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_wraps_around.{edge.source_id}_to_{edge.target_id}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
