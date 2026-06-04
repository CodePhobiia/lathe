"""Edge decorator for edge_type='cuts' in the hard_surface domain.

When source `cuts` target, the source's geometry subtracts from the
target — typical for slots cutting a panel, holes cutting a face,
keyways cutting a shaft. Subtractive variant of `attached_to`. Emits
op.union with blend_mode=subtract.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="cuts",
    domain="hard_surface",
    consumed_attribute_fields=("depth_cm",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("cuts_unresolved_target",),
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

    raw_attrs = edge.raw_attributes if isinstance(edge.raw_attributes, dict) else {}
    depth_cm = raw_attrs.get("depth_cm")

    target_op = target_ops[0]
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "cuts",
            "blend_mode": "subtract",
        }
        if depth_cm is not None:
            params["cut_depth_cm"] = float(depth_cm)
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_cuts.{edge.source_id}_to_{edge.target_id}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
