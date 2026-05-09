"""Terminate an evaluated CGA :class:`AssemblyTree` into flat primitive records.

The output is a list of :class:`TerminalRecord` entries, each describing a
ShapePrimitive or kit_call call with its world-space transform. The flat list
is the format ``assembly_kernel`` (``lathe/assembly_kernel.py``) consumes when
authoring a procedural assembly without going through V1.1 component lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluator import AssemblyTree, ProductionNode
from .productions import Terminal


@dataclass
class TerminalRecord:
    """A flat terminal primitive emitted from an evaluated CGA tree."""

    name: str
    kind: str
    position: tuple[float, float, float]
    extents: tuple[float, float, float]  # width, depth, height (m)
    rotation: tuple[str, float]
    path: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def terminate_to_primitives(tree: AssemblyTree) -> list[TerminalRecord]:
    """Walk ``tree`` and produce a flat list of :class:`TerminalRecord`.

    The traversal is depth-first; ``path`` carries the chain of rule labels
    from root to terminal so callers can group by floor/wing/etc.
    """
    out: list[TerminalRecord] = []
    _walk(tree.root, out, [], {}, [])
    return out


def _walk(
    node: ProductionNode,
    out: list[TerminalRecord],
    path: list[str],
    inherited_metadata: dict[str, Any],
    derivation_steps: list[dict[str, Any]],
) -> None:
    label = node.label
    new_path = path + [label]
    node_metadata = dict(node.metadata)
    metadata = {**inherited_metadata, **node_metadata}
    steps = list(derivation_steps)
    if node_metadata or node.kind in {"split", "repeat", "choose", "extrude", "transform"}:
        steps.append(
            {
                "kind": node.kind,
                "label": label,
                **node_metadata,
            }
        )
    if node.kind == "terminal" and node.terminal is not None:
        record = _record_from_node(node, node.terminal, new_path)
        if metadata:
            record.metadata.update(metadata)
        if steps:
            record.metadata["derivation_steps"] = steps
        out.append(record)
        return
    for child in node.children:
        _walk(child, out, new_path, metadata, steps)


def _record_from_node(node: ProductionNode, terminal: Terminal, path: list[str]) -> TerminalRecord:
    shape = node.shape
    return TerminalRecord(
        name=terminal.name,
        kind=terminal.kind,
        position=shape.position,
        extents=(shape.width, shape.depth, shape.height),
        rotation=shape.rotation,
        path=path,
        params=dict(terminal.params),
        metadata=dict(node.metadata),
    )
