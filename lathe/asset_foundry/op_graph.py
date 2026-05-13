"""Foundry F1 — typed GeometryOpGraph.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §6.1
+ §7 and docs/asset-quality/lathe-frontier-geometry-kernel-roadmap.md
§7.1, the GeometryOpGraph is the typed internal artifact between
ShapeIR/ShapeIR-v2 and backend execution.

Each node records:
  - operation_id (stable)
  - op (canonical, e.g. ``solid.box``, ``op.bevel``, ``style.facet_field``)
  - semantic_part (which logical part the op contributes to)
  - inputs (operation_ids it consumes)
  - params (operation parameters)
  - required_capabilities (kernel capability tokens)
  - fallback_policy
  - attribute_mapping (how part/material/feature ids propagate)
  - evidence_requirements (what artifact evidence proves execution)

The graph is paired with a planner that picks a backend lane per node
based on the capability matrix (Foundry F0). Per ``newresearch.md`` §1
("lazy CSG/feature DAG"), execution is deferred and batched per
spatial cluster downstream.

This module does **not** execute the graph — execution is the kernel
program's job (already implemented in
``lathe/geometry/kernel_program.py``). This module is the **typed
descriptor + planner**, internal-only, additive on top of ShapeIR v2.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .capability_matrix import (
    CapabilityRecord,
    CapabilityStatus,
    FoundryCapabilityMatrix,
    build_capability_matrix,
)

OP_GRAPH_VERSION = "lathe.asset_foundry.op_graph_v1"


class BackendLane(str, Enum):
    """Backend lanes per masterplan §6.1 and newresearch.md §1.

    Each op is routed to exactly one lane based on its required
    capabilities + the matrix's supporting_kernels.
    """

    MANIFOLD_SOLID = "manifold_solid"
    """Manifold full-CSG lane for robust watertight booleans + primitives."""

    REFERENCE_MESH = "reference_mesh"
    """Reference/trimesh fallback for primitives + mesh ops when Manifold
    is unavailable or unsupported."""

    MESH_FEATURE = "mesh_feature"
    """Mesh-level feature ops: bevel/chamfer/inset/panel/trim/socket."""

    PRISMATIC_STYLIZED = "prismatic_stylized"
    """Foundry F4 stylized operators: prism, crystal, half-space polyhedra,
    facet field."""

    SDF_FIELD = "sdf_field"
    """SDF/level-set lane for organic blends + soft wear masks."""

    DCC_REFERENCE = "dcc_reference"
    """Optional Blender/Houdini reference lane for quality target evidence."""

    GAME_FINALIZE = "game_finalize"
    """Collision proxy, LOD chain, UV/material conventions, engine handoff."""

    METADATA_ONLY = "metadata_only"
    """No geometry; pure attribute/zone/seam record (e.g. op.material_zone)."""

    UNSUPPORTED = "unsupported"
    """Op has no lane mapping; planner emits an unsupported diagnostic."""


# Map from op_family -> default BackendLane.
_FAMILY_LANE_MAP: Mapping[str, BackendLane] = {
    "solid": BackendLane.MANIFOLD_SOLID,
    "boolean": BackendLane.MANIFOLD_SOLID,
    "edge": BackendLane.MESH_FEATURE,
    "feature": BackendLane.MESH_FEATURE,
    "repetition": BackendLane.MESH_FEATURE,
    "integration": BackendLane.MESH_FEATURE,
    "wear": BackendLane.MESH_FEATURE,
    "surface": BackendLane.METADATA_ONLY,
    "stylized": BackendLane.PRISMATIC_STYLIZED,
    "runtime": BackendLane.GAME_FINALIZE,
    "package": BackendLane.GAME_FINALIZE,
}


@dataclass(frozen=True)
class AttributeMapping:
    """Per-op attribute propagation contract.

    Records what happens to face/edge/vertex semantic attributes
    when this operation executes. Required by masterplan §7.3 and
    newresearch.md §5 (zone preservation).
    """

    preserved: tuple[str, ...] = ()
    """Attributes that pass through unchanged (e.g. ``part_id``,
    ``material_zone``)."""

    transformed: tuple[str, ...] = ()
    """Attributes whose values may change (e.g. ``face_id`` after a
    boolean)."""

    split: tuple[str, ...] = ()
    """Attributes that may split across multiple output faces (e.g.
    ``panel_region`` after a panel cut)."""

    merged: tuple[str, ...] = ()
    """Attributes that may merge across input faces."""

    generated: tuple[str, ...] = ()
    """New attribute keys this op introduces (e.g. ``bevel_ring`` after
    op.bevel)."""

    dropped: tuple[str, ...] = ()
    """Attributes that this op intentionally drops. Dropping
    ``part_id`` / ``material_zone`` / ``semantic_socket`` is a
    diagnostic-worthy event."""


@dataclass(frozen=True)
class GeometryOpNode:
    """One typed node in the GeometryOpGraph."""

    operation_id: str
    """Stable per-graph identifier (e.g. ``crate.body.bevel_outer_01``)."""

    op: str
    """Canonical op token (matches a CapabilityRecord.operation_id)."""

    semantic_part: str
    """Which logical part this op belongs to."""

    inputs: tuple[str, ...] = ()
    """Operation IDs this node consumes."""

    params: Mapping[str, Any] = field(default_factory=dict)
    """Operation parameters (sizes, axes, counts, profiles)."""

    required_capabilities: tuple[str, ...] = ()
    """Kernel capability tokens this op needs (e.g.
    ``mesh.bevel.edge_group``, ``attributes.face_region_preservation``)."""

    fallback_policy: str = "fail_certification_if_missing"
    """One of:
      - ``fail_certification_if_missing`` — strict, blocks certification.
      - ``warn_and_skip`` — emit diagnostic, continue without op.
      - ``approximate_with_diagnostic`` — fall back to a labeled approx.
    """

    attribute_mapping: AttributeMapping = field(default_factory=AttributeMapping)
    """How attributes propagate through this op."""

    evidence_requirements: tuple[str, ...] = ()
    """Required evidence tokens (mirrored from CapabilityRecord)."""


@dataclass(frozen=True)
class GeometryOpGraph:
    """Typed graph of geometry operations.

    Internal-only artifact between ShapeIR v2 and backend execution.
    The graph is deterministic, serializable, and survives the kernel
    program execution path so provenance lands in the .lthpkg sidecar.
    """

    asset_id: str
    nodes: tuple[GeometryOpNode, ...]

    def node_by_id(self, operation_id: str) -> GeometryOpNode | None:
        for node in self.nodes:
            if node.operation_id == operation_id:
                return node
        return None

    def topological_order(self) -> tuple[str, ...]:
        """Return operation_ids in dependency order (inputs before
        consumers). Deterministic by node declaration order on ties.
        Raises ValueError on a cycle (which would be a graph-author bug).
        """
        seen: set[str] = set()
        order: list[str] = []
        node_map = {n.operation_id: n for n in self.nodes}
        temp: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in seen:
                return
            if node_id in temp:
                raise ValueError(f"cycle in op graph at {node_id}")
            node = node_map.get(node_id)
            if node is None:
                return  # input refers to upstream; tolerate
            temp.add(node_id)
            for dep in node.inputs:
                visit(dep)
            temp.discard(node_id)
            seen.add(node_id)
            order.append(node_id)

        for node in self.nodes:
            visit(node.operation_id)
        return tuple(order)


@dataclass(frozen=True)
class OpGraphPlan:
    """Result of planning a GeometryOpGraph against the capability matrix.

    The planner assigns one backend lane per op + records the
    capability status. Downstream execution (kernel_program) consults
    the plan to route to the right kernel; .lthpkg evidence consults
    the plan to surface unsupported / fallback nodes truthfully.
    """

    asset_id: str
    graph_version: str
    """The GeometryOpGraph version this plan was built against."""

    lanes_by_op: Mapping[str, str]
    """operation_id -> BackendLane.value."""

    capability_by_op: Mapping[str, str]
    """operation_id -> CapabilityStatus.value."""

    unsupported_ops: tuple[str, ...]
    """operation_ids with status == unsupported."""

    fallback_ops: tuple[str, ...]
    """operation_ids with status == fallback."""

    not_started_ops: tuple[str, ...]
    """operation_ids whose op canonical token is in the matrix but
    has status == not_started."""

    missing_from_matrix: tuple[str, ...]
    """operation_ids whose op token is not in the capability matrix
    at all — a graph-author bug or a forward-looking op."""

    topo_order: tuple[str, ...]
    """Deterministic execution order."""


def _lane_for_op(record: CapabilityRecord | None, default_family: str = "") -> BackendLane:
    """Pick the backend lane for one op based on its capability record."""
    if record is None:
        return BackendLane.UNSUPPORTED
    if record.status == CapabilityStatus.UNSUPPORTED:
        return BackendLane.UNSUPPORTED
    if record.status == CapabilityStatus.NOT_STARTED:
        return BackendLane.UNSUPPORTED
    # Operation_id namespace prefix gives strong hints; family is the
    # secondary signal.
    op_id = record.operation_id
    if op_id.startswith("style.") or op_id.startswith("mesh.") or op_id.startswith(
        "terrain."
    ):
        return BackendLane.PRISMATIC_STYLIZED
    if op_id.startswith("runtime.") or op_id.startswith("package."):
        return BackendLane.GAME_FINALIZE
    return _FAMILY_LANE_MAP.get(record.op_family, BackendLane.MESH_FEATURE)


def plan_op_graph(
    graph: GeometryOpGraph,
    matrix: FoundryCapabilityMatrix | None = None,
) -> OpGraphPlan:
    """Plan a GeometryOpGraph against the capability matrix.

    Pure function. Returns a plan record that downstream execution
    consults to route to the right kernel lane and that the .lthpkg
    evidence sidecar surfaces.
    """
    matrix = matrix if matrix is not None else build_capability_matrix()
    lanes_by_op: dict[str, str] = {}
    capability_by_op: dict[str, str] = {}
    unsupported: list[str] = []
    fallback: list[str] = []
    not_started: list[str] = []
    missing: list[str] = []

    for node in graph.nodes:
        record = matrix.lookup(node.op)
        lane = _lane_for_op(record)
        lanes_by_op[node.operation_id] = lane.value
        if record is None:
            capability_by_op[node.operation_id] = "missing_from_matrix"
            missing.append(node.operation_id)
            continue
        capability_by_op[node.operation_id] = record.status.value
        if record.status == CapabilityStatus.UNSUPPORTED:
            unsupported.append(node.operation_id)
        elif record.status == CapabilityStatus.NOT_STARTED:
            not_started.append(node.operation_id)
        elif record.status == CapabilityStatus.FALLBACK:
            fallback.append(node.operation_id)
        elif record.status == CapabilityStatus.PARTIAL:
            # PARTIAL = fallback at execution time for some inputs.
            fallback.append(node.operation_id)

    return OpGraphPlan(
        asset_id=graph.asset_id,
        graph_version=OP_GRAPH_VERSION,
        lanes_by_op=lanes_by_op,
        capability_by_op=capability_by_op,
        unsupported_ops=tuple(unsupported),
        fallback_ops=tuple(fallback),
        not_started_ops=tuple(not_started),
        missing_from_matrix=tuple(missing),
        topo_order=graph.topological_order(),
    )


def graph_from_shape_program(
    asset_id: str,
    shape_program: Mapping[str, Any],
) -> GeometryOpGraph:
    """Build a GeometryOpGraph from a ShapeIR-v2 ShapeProgram dict.

    The ShapeProgram from ``lathe.asset_quality.shape_ir_v2.ShapeProgram``
    (or its dict form emitted by grammar_lowering) has shape:

    ``{"version": "shape_ir_v2", "ops": [{"op": "...", "target": "...",
       "parameters": {...}, "purpose": "..."}, ...]}``

    Each op becomes a GeometryOpNode keyed by ``purpose`` (which is
    already unique-by-construction in the grammar_lowering recipe).
    """
    ops = shape_program.get("ops") if isinstance(shape_program, Mapping) else None
    if not isinstance(ops, (list, tuple)):
        return GeometryOpGraph(asset_id=asset_id, nodes=())
    nodes: list[GeometryOpNode] = []
    seen_ids: set[str] = set()
    for i, op_entry in enumerate(ops):
        if not isinstance(op_entry, Mapping):
            continue
        op_token = str(op_entry.get("op") or "").strip()
        if not op_token:
            continue
        purpose = str(op_entry.get("purpose") or "").strip()
        target = str(op_entry.get("target") or "").strip()
        op_id_candidate = purpose or f"{op_token}.{target}" if target else f"{op_token}.{i:04d}"
        # Resolve collisions.
        op_id = op_id_candidate
        suffix = 1
        while op_id in seen_ids:
            op_id = f"{op_id_candidate}.{suffix:02d}"
            suffix += 1
        seen_ids.add(op_id)
        semantic_part = (
            target.split(".", 1)[0] if "." in target else (target or "unknown")
        )
        params = op_entry.get("parameters")
        params = dict(params) if isinstance(params, Mapping) else {}
        nodes.append(
            GeometryOpNode(
                operation_id=op_id,
                op=op_token,
                semantic_part=semantic_part,
                inputs=(),
                params=params,
                required_capabilities=(op_token,),
            )
        )
    return GeometryOpGraph(asset_id=asset_id, nodes=tuple(nodes))


__all__ = [
    "OP_GRAPH_VERSION",
    "BackendLane",
    "AttributeMapping",
    "GeometryOpNode",
    "GeometryOpGraph",
    "OpGraphPlan",
    "graph_from_shape_program",
    "plan_op_graph",
]
