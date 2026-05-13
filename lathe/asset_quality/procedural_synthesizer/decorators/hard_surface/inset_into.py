"""Edge decorator for edge_type='inset_into' in the hard_surface domain.

When source is `inset_into` target, the source's geometry recesses into
the target — like an inset panel into a face. The source ops are
subtracted (or set into) the target's volume. Emits op.union with
blend_mode=subtract tagging, leaving downstream boolean stages to
realize the subtraction with appropriate kernel ops.

Works for any (source_node, target_node) pair regardless of node_type.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="inset_into",
    domain="hard_surface",
    consumed_attribute_fields=("depth_cm",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("inset_into_unresolved_target",),
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
    depth_cm = raw_attrs.get("depth_cm")
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "inset_into",
            "blend_mode": "subtract",
        }
        if depth_cm is not None:
            params["inset_depth_cm"] = float(depth_cm)
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_inset_into.{edge.source_id}_to_{edge.target_id}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
