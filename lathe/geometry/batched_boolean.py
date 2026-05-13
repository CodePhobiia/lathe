"""Batched boolean executor (Wave 12 / research §1).

Per research §1: instead of N serial binary booleans, compile all
interacting meshes in a cluster, build one arrangement, classify by
the boolean expression, and extract once. libigl's variadic boolean
model is the mental reference.

This module is the executor contract — actual variadic mesh
arrangement code that integrates with the manifold3d kernel is the
follow-up implementation work. The contract surface is here so the
synthesizer can target batched-eval semantics from day one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .feature_dag import FeatureDAG, FeatureDAGNode
from .spatial_cluster import AABB, ClusterEntry, cluster_by_bbox_overlap

CONTRACT_VERSION = "lathe.geometry.batched_boolean_v1"


@dataclass(frozen=True)
class BatchedBooleanRequest:
    """One cluster's batched boolean problem."""

    cluster_id: str
    primitive_ids: tuple[str, ...]
    boolean_expression: str  # e.g. "(body - cut1 - cut2 - cut3) + bracket_0"
    preserve_provenance: bool = True


@dataclass(frozen=True)
class BatchedBooleanResult:
    """Outcome of a batched boolean evaluation."""

    cluster_id: str
    output_face_count: int
    primitive_ids: tuple[str, ...]
    provenance_map: Mapping[str, str] = field(default_factory=dict)
    elapsed_s: float = 0.0
    fell_back_to_serial: bool = False


def plan_batched_boolean(
    dag: FeatureDAG, primitive_aabbs: Mapping[str, AABB], margin_cm: float = 0.5
) -> list[BatchedBooleanRequest]:
    """Plan a batched boolean evaluation by spatial clustering.

    For each cluster, infer a default boolean expression: primitives
    are unioned, and any boolean nodes in the DAG that reference cluster
    primitives are folded into the cluster's expression.
    """
    entries: list[ClusterEntry] = []
    for prim in dag.primitive_nodes():
        aabb = primitive_aabbs.get(prim.node_id)
        if aabb is None:
            continue
        entries.append(
            ClusterEntry(primitive_id=prim.node_id, aabb=aabb, role=str(prim.provenance.get("role") or ""))
        )

    clusters = cluster_by_bbox_overlap(entries, margin_cm)
    requests: list[BatchedBooleanRequest] = []
    for i, cluster in enumerate(clusters):
        prim_ids = tuple(c.primitive_id for c in cluster)
        if len(prim_ids) == 1:
            expr = prim_ids[0]
        else:
            # Default expression: union all primitives in the cluster.
            expr = "(" + " + ".join(prim_ids) + ")"
        # Find boolean ops in the DAG whose inputs are subset of prim_ids
        # and rewrite the cluster expression to honor them.
        for bnode in dag.boolean_nodes():
            if not set(bnode.inputs).issubset(set(prim_ids)):
                continue
            op = str(bnode.parameters.get("operation", "union"))
            if op == "difference" and len(bnode.inputs) >= 2:
                target = bnode.inputs[0]
                cutters = bnode.inputs[1:]
                expr = f"({target} - " + " - ".join(cutters) + ")"
        requests.append(
            BatchedBooleanRequest(
                cluster_id=f"cluster_{i}",
                primitive_ids=prim_ids,
                boolean_expression=expr,
            )
        )
    return requests


def execute_batched_request_stub(request: BatchedBooleanRequest) -> BatchedBooleanResult:
    """Stub executor — returns a synthetic result for contract tests.

    The real executor wires through the manifold3d kernel + provenance-
    preserving variadic arrangement. This stub lets downstream code
    (synthesizer, optimize stage, package stage) exercise the data
    flow without the heavy kernel hookup.
    """
    return BatchedBooleanResult(
        cluster_id=request.cluster_id,
        output_face_count=len(request.primitive_ids) * 32,  # synthetic
        primitive_ids=request.primitive_ids,
        provenance_map={pid: f"face_group:{pid}" for pid in request.primitive_ids},
        elapsed_s=0.001,
        fell_back_to_serial=False,
    )


__all__ = [
    "CONTRACT_VERSION",
    "BatchedBooleanRequest",
    "BatchedBooleanResult",
    "plan_batched_boolean",
    "execute_batched_request_stub",
]
