"""Edge decorator for edge_type='mirrors' in the hard_surface domain.

When source `mirrors` target, the source's geometry is duplicated as
a mirror reflection of target across a specified plane. Emits a
metadata-tagged op.union; downstream stages apply the mirror transform
during materialization.

The mirror_plane attribute (xy / xz / yz) names the reflection plane.
"""

from __future__ import annotations

from collections.abc import Iterable

from ....shape_ir_v2 import ShapeOp
from ...context import ConstructionEdgeTyped, SynthesizerContext
from ...registry import EdgeDecoratorCapabilityManifest, EdgeTypeDecorator, OpResolver

_VALID_PLANES: frozenset[str] = frozenset({"xy", "xz", "yz"})


_MANIFEST = EdgeDecoratorCapabilityManifest(
    edge_type="mirrors",
    domain="hard_surface",
    consumed_attribute_fields=("mirror_plane",),
    consumed_style_fields=(),
    emitted_op_kinds=("op.union",),
    required_kernel_capabilities=("op.union",),
    fallback_diagnostics=("mirrors_unsupported_plane",),
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
    plane = str(raw_attrs.get("mirror_plane") or "yz")
    if plane not in _VALID_PLANES:
        return

    target_op = target_ops[0]
    for source_op in source_ops:
        params: dict[str, object] = {
            "source": {
                "op": source_op.op,
                "target": source_op.target,
                "parameters": dict(source_op.parameters),
            },
            "edge_kind": "mirrors",
            "mirror_plane": plane,
            "blend_mode": "add",
        }
        yield ShapeOp(
            op="op.union",
            target=target_op.target,
            parameters=params,
            purpose=f"procedural_mirrors.{edge.source_id}_to_{edge.target_id}.{plane}",
        )


DECORATOR = EdgeTypeDecorator(manifest=_MANIFEST, implementation=_impl)
