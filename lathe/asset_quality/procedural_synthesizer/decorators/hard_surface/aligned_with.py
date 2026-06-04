"""Edge decorator for edge_type='aligned_with' in the hard_surface domain.

When source is `aligned_with` target, the source's geometry shares an
axis-orientation with target. Lightweight metadata edge — does NOT
modify boolean topology; downstream placement / orientation stages
consult the alignment hint when positioning the source relative to
target.

Emits an op.union with edge_kind='aligned_with' and blend_mode='add'
so the source still becomes part of the assembly tree, but the
alignment axis is recorded in parameters for transform stages.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="aligned_with",
    domain="hard_surface",
    consumed_attribute_fields=("alignment_axis",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("aligned_with_unsupported_axis",),
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
    axis = str(raw_attrs.get("alignment_axis") or "y")
    if axis not in _VALID_AXES:
        return

    target_op = target_ops[0]
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "aligned_with",
            "alignment_axis": axis,
            "blend_mode": "add",
        }
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_aligned_with.{edge.source_id}_to_{edge.target_id}.{axis}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
