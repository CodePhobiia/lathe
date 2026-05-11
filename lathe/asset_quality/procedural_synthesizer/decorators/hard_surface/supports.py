"""Edge decorator for edge_type='supports' in the hard_surface domain.

When source `supports` target, the source bears the load of target —
typical for brackets supporting a panel, mounts supporting a casing,
frames supporting trim. Geometrically equivalent to `attached_to`
(additive boolean), but carries semantic load_path metadata so
downstream physics / rigging stages can infer structure.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver


_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="supports",
    domain="hard_surface",
    consumed_attribute_fields=("load_axis",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("supports_unresolved_target",),
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
    load_axis = raw_attrs.get("load_axis")

    target_op = target_ops[0]
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "supports",
            "blend_mode": "add",
        }
        if load_axis is not None:
            params["load_axis"] = str(load_axis)
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_supports.{edge.source_id}_to_{edge.target_id}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
