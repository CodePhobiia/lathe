"""Visual node graph IR (Wave 18 / research §8 layer 2).

A typed intermediate representation that round-trips with the
construction graph the synthesizer consumes. A visual graph editor
serializes its node/edge state to ``AuthorGraph``; ``AuthorGraph``
projects to a construction_graph dict that the synthesizer reads.

The IR is intentionally schemaless on parameters — the visual graph
exposes whatever fields the node type's typed-attribute schema
defines, and the schema lives in the synthesizer's attribute
registry. The IR only carries node/edge structure + parameter
payloads.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.authoring.graph_ir_v1"


@dataclass(frozen=True)
class AuthorGraphNode:
    """One node in the visual authoring graph."""

    node_id: str
    node_type: str
    domain: str = "hard_surface"
    attributes: Mapping[str, Any] = field(default_factory=dict)
    layout_x: float = 0.0
    layout_y: float = 0.0
    locked: bool = False
    label: str = ""


@dataclass(frozen=True)
class AuthorGraphEdge:
    """One edge in the visual authoring graph."""

    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorGraph:
    """A complete authoring graph state."""

    graph_id: str
    nodes: tuple[AuthorGraphNode, ...] = ()
    edges: tuple[AuthorGraphEdge, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def find_node(self, node_id: str) -> AuthorGraphNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None


def author_graph_from_construction_graph(
    graph_id: str, construction: Mapping[str, Any]
) -> AuthorGraph:
    """Lift a construction_graph dict into an AuthorGraph."""
    raw_nodes = construction.get("nodes") or []
    raw_edges = construction.get("edges") or []
    nodes: list[AuthorGraphNode] = []
    if isinstance(raw_nodes, list):
        for i, node in enumerate(raw_nodes):
            if not isinstance(node, Mapping):
                continue
            nodes.append(
                AuthorGraphNode(
                    node_id=str(node.get("node_id") or f"node_{i}"),
                    node_type=str(node.get("node_type") or "primary_volume"),
                    domain=str(node.get("domain") or "hard_surface"),
                    attributes=dict(node.get("attributes") or {}),
                    label=str(node.get("node_id") or ""),
                )
            )
    edges: list[AuthorGraphEdge] = []
    if isinstance(raw_edges, list):
        for i, edge in enumerate(raw_edges):
            if not isinstance(edge, Mapping):
                continue
            edges.append(
                AuthorGraphEdge(
                    edge_id=str(edge.get("edge_id") or f"edge_{i}"),
                    source_id=str(edge.get("source_id") or ""),
                    target_id=str(edge.get("target_id") or ""),
                    edge_type=str(edge.get("edge_type") or "attached_to"),
                    attributes=dict(edge.get("attributes") or {}),
                )
            )
    return AuthorGraph(
        graph_id=graph_id,
        nodes=tuple(nodes),
        edges=tuple(edges),
        metadata={"source": "construction_graph"},
    )


def construction_graph_from_author_graph(graph: AuthorGraph) -> dict[str, Any]:
    """Project an AuthorGraph to the construction_graph dict shape.

    The synthesizer reads this dict directly via
    ``runtime_from_asset.construction_graph``.
    """
    return {
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "domain": n.domain,
                "attributes": dict(n.attributes),
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "edge_id": e.edge_id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type,
                "attributes": dict(e.attributes),
            }
            for e in graph.edges
        ],
        "_authoring_source": graph.graph_id,
    }


__all__ = [
    "CONTRACT_VERSION",
    "AuthorGraphNode",
    "AuthorGraphEdge",
    "AuthorGraph",
    "author_graph_from_construction_graph",
    "construction_graph_from_author_graph",
]
