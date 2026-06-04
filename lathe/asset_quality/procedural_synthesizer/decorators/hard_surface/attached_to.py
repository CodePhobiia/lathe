"""Edge decorator for edge_type='attached_to' in the hard_surface domain.

When a panel is `attached_to` a primary volume, the relationship is
modeled as the panel being a child component of the primary volume's
assembly. The decorator emits an op.union (or component-grouping op)
that captures the structural attachment for downstream stages —
topology preserves the part name, UV groups the chart with the parent,
surface zones inherit the parent's material context.

No family-name awareness; the decorator works for any (source_node,
target_node) pair where source's ops can attach to target's ops.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="attached_to",
    domain="hard_surface",
    consumed_attribute_fields=(),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("attached_to_unresolved_target",),
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
        # Either endpoint didn't produce visible geometry — nothing to
        # attach. The pipeline's trace already recorded the dispatch.
        return

    # op.union with the target's primary op as the union root, the
    # source's primary op as the attached component. The shape_ir_v2
    # union op consumes the source as a child of the target's
    # boolean tree.
    target_op = target_ops[0]
    source_op = source_ops[0]
    yield ShapeOp(
        op="op.union",
        target=target_op.target,
        parameters={
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
        },
        purpose=f"procedural_attached_to.{edge.source_id}_to_{edge.target_id}",
    )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
