"""``lathe.geometry.feature_dag_v1`` — lazy feature DAG (research §1).

Per research §1: Lathe ops should not immediately become final meshes.
They should become typed nodes (box, cylinder, cut, union, inset,
bracket, bevel rule, material zone, decal anchor) in a lazy DAG.
Evaluation happens *after* the full graph is known, in batches per
spatial cluster.

This module defines the DAG contract surface. The batched-boolean
executor + deferred bevel + coplanar merge passes live in sibling
modules under ``lathe.geometry.``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.geometry.feature_dag_v1"


@dataclass(frozen=True)
class FeatureDAGNode:
    """One node in the lazy feature DAG.

    - ``node_kind``: ``primitive``, ``transform``, ``boolean``, ``feature``,
      ``material_zone``, ``decal_anchor``, ``bevel_rule``, ``sweep_rule``.
    - ``parameters``: kind-specific parameter dict (radius_cm,
      dimensions_cm, transform_matrix, source_ids, ...).
    - ``inputs``: tuple of upstream node_ids the node depends on.
    - ``provenance``: provenance metadata (source_part_id, feature_role,
      material_class, uv_policy, zone_id) — preserved through the
      kernel into output faces (§1 invariant 5).
    """

    node_id: str
    node_kind: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureDAG:
    """A lazy DAG of typed feature nodes.

    Stored as a flat tuple of nodes; topology is captured by each
    node's ``inputs`` referring to earlier ``node_id`` values. The
    executor uses this to:

      1. broadphase-cluster interacting primitives by bbox overlap
      2. evaluate each cluster's boolean expression variadically
      3. preserve provenance across face attribution
      4. defer bevels to after booleans
    """

    dag_id: str
    nodes: tuple[FeatureDAGNode, ...] = ()

    def by_id(self, node_id: str) -> FeatureDAGNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def primitive_nodes(self) -> tuple[FeatureDAGNode, ...]:
        return tuple(n for n in self.nodes if n.node_kind == "primitive")

    def boolean_nodes(self) -> tuple[FeatureDAGNode, ...]:
        return tuple(n for n in self.nodes if n.node_kind == "boolean")


__all__ = [
    "CONTRACT_VERSION",
    "FeatureDAGNode",
    "FeatureDAG",
]
