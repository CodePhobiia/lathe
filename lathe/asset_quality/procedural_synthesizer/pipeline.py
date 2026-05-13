"""Procedural synthesizer compiler pipeline — 8 ordered stages.

Replaces family-name dispatch with staged procedural composition.
Each stage has a single concern, typed input/output, and an
inspectable trace.

Stages:
  1. resolve_context     — alias -> (style, policies); typed ctx
  2. normalize_graph     — dedupe, canonicalize, resolve refs
  3. expand_policies     — preconditions match -> add nodes/edges
  4. validate_attributes — typed schemas enforced
  5. topo_order          — deterministic dependency ordering
  6. emit_node_ops       — generators run with manifest attribution
  7. emit_edge_ops       — decorators run, references resolved
  8. validate_ops        — every emitted op in shape_ir_v2.ALL_OPS
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..shape_ir_v2 import ALL_OPS, SHAPE_IR_V2_VERSION, ShapeOp, ShapeProgram
from .attributes import ATTRIBUTE_SCHEMAS, validate_attributes
from .context import (
    ConstructionEdgeTyped,
    ConstructionNodeTyped,
    SynthesizerContext,
    resolve_context,
)
from .knowledge_loader import (
    CompositionPolicy,
    FamilyAlias,
    StyleKnowledge,
    precondition_matches,
)
from .registry import REGISTRY, GeneratorRegistry, OpResolver
from .trace import SynthesizerTrace, TraceBuilder


@dataclass(frozen=True)
class SynthesisResult:
    """The procedural compiler pipeline's output."""

    shape_program: ShapeProgram
    """The emitted ShapeIR v2 ShapeProgram. Drives downstream lowering
    and kernel execution.
    """

    synthesized_graph_nodes: tuple[Mapping[str, Any], ...]
    """Nodes that the compiler added (by composition policies) on top
    of the authored graph. Reported as additive synthesized graph
    nodes by the validator path for parity with the legacy recipe
    payload shape.
    """

    trace: SynthesizerTrace
    """Full trace of the 8-stage pipeline. JSON-serializable via
    ``.to_dict()``.
    """


# ---------- Stage 2: normalize_graph ----------


@dataclass(frozen=True)
class _NormalizedGraph:
    nodes: tuple[Mapping[str, Any], ...]
    edges: tuple[Mapping[str, Any], ...]


def _normalize_graph(ctx: SynthesizerContext, trace: TraceBuilder) -> _NormalizedGraph:
    trace.emit("stage_start", stage=2)
    seen_ids: set[str] = set()
    nodes: list[dict[str, Any]] = []
    for raw in ctx.raw_graph_nodes:
        node_id = str(raw.get("node_id") or "").strip()
        node_type = str(raw.get("node_type") or "").strip()
        if not node_id:
            # Skip nodes without IDs entirely; trace as unknown
            trace.emit(
                "unknown_node_type",
                stage=2,
                reason="missing_node_id",
                node=dict(raw),
            )
            continue
        if not node_type:
            trace.emit(
                "unknown_node_type",
                stage=2,
                reason="missing_node_type",
                node_id=node_id,
            )
            continue
        if node_id in seen_ids:
            trace.emit("node_deduped", stage=2, node_id=node_id)
            continue
        seen_ids.add(node_id)
        nodes.append(
            {
                "node_id": node_id,
                "node_type": node_type,
                "attributes": dict(raw.get("attributes") or {}),
            }
        )

    edges: list[dict[str, Any]] = []
    for raw in ctx.raw_graph_edges:
        source_id = str(raw.get("source_id") or "").strip()
        target_id = str(raw.get("target_id") or "").strip()
        edge_type = str(raw.get("edge_type") or "").strip()
        if not source_id or not target_id or not edge_type:
            trace.emit(
                "edge_canonicalized",
                stage=2,
                reason="malformed_edge",
                source_id=source_id,
                target_id=target_id,
            )
            continue
        if source_id not in seen_ids or target_id not in seen_ids:
            trace.emit(
                "edge_canonicalized",
                stage=2,
                reason="dangling_reference",
                source_id=source_id,
                target_id=target_id,
            )
            continue
        edges.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "attributes": dict(raw.get("attributes") or {}),
            }
        )

    trace.emit(
        "stage_end",
        stage=2,
        node_count=len(nodes),
        edge_count=len(edges),
    )
    return _NormalizedGraph(nodes=tuple(nodes), edges=tuple(edges))


# ---------- Stage 3: expand_policies ----------


def _resolve_count(raw_count: Any, brief: Mapping[str, Any]) -> int:
    """Resolve a policy-expansion count, applying ``brief.density`` as a multiplier.

    Density is a non-family knob: 1.0 is the canonical base, >1 produces
    more secondary features (more fasteners, more brackets), <1 produces
    fewer. Used so the same policy JSON can produce sparse "factory new"
    or dense "industrial heavy duty" outputs without per-policy variants.
    The multiplier rounds half-up; a base count of 1 with density 0.5
    stays at 1 to keep the minimum-canonical feature present.
    """
    raw_density = brief.get("density")
    try:
        density = float(raw_density) if raw_density is not None else 1.0
    except (TypeError, ValueError):
        density = 1.0
    if density <= 0:
        density = 1.0

    if isinstance(raw_count, int):
        base = max(0, raw_count)
    elif isinstance(raw_count, Mapping):
        field_name = raw_count.get("from_brief_field")
        default = int(raw_count.get("default") or 0)
        if isinstance(field_name, str):
            value = brief.get(field_name)
            if isinstance(value, int):
                base = max(0, value)
            else:
                base = default
        else:
            base = default
    else:
        base = 1

    if base == 0:
        return 0
    scaled = round(base * density)
    # Minimum-canonical preservation: if the base authored count is 1+
    # and density tries to round it to 0, keep 1 so the canonical feature
    # is at least present.
    if base >= 1 and scaled <= 0:
        return 1
    return scaled


def _body_dimensions_from_graph(
    nodes: list[dict[str, Any]],
) -> dict[str, float] | None:
    """Find the primary_volume node and return its ``dimensions_cm``.

    Used by policy expansion to compute corner / face positions for
    policy-added nodes (brackets, fasteners) that the policy JSON
    declares via ``placement.pattern``.
    """
    for node in nodes:
        if node.get("node_type") != "primary_volume":
            continue
        attrs = node.get("attributes") or {}
        if not isinstance(attrs, Mapping):
            continue
        dims = attrs.get("dimensions_cm")
        if isinstance(dims, Mapping):
            try:
                return {
                    "x": float(dims.get("x", 30.0)),
                    "y": float(dims.get("y", 30.0)),
                    "z": float(dims.get("z", 30.0)),
                }
            except (TypeError, ValueError):
                return None
    return None


def _position_for_policy_pattern(
    pattern: str,
    index: int,
    count: int,
    body_dims: dict[str, float],
) -> tuple[float, float, float] | None:
    """Map a policy.placement.pattern + index into a (x, y, z) position.

    Convention: ``+Z is up``, ``+Y is the "front" face``. Standoff is
    minimal (0.5cm) so the part sits flush against the body face.
    Returns None for unrecognized patterns — the policy node then
    falls back to origin (preserving prior behavior).
    """
    half_x = body_dims["x"] / 2.0
    half_y = body_dims["y"] / 2.0
    half_z = body_dims["z"] / 2.0
    standoff = 0.5

    if pattern in ("two_corners", "top_corners"):
        # Top-front-left, then top-front-right (or back if back-corner pair).
        if index == 0:
            return (-half_x - standoff, half_y, half_z)
        if index == 1:
            return (half_x + standoff, half_y, half_z)
    if pattern in ("four_corners", "top_face_corners"):
        # Four top corners (TL, TR, BL, BR on top face).
        signs = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        if 0 <= index < 4:
            sx, sy = signs[index]
            return (sx * (half_x + standoff), sy * (half_y + standoff), half_z)
    if pattern in ("eight_corners", "all_corners"):
        # 8 corners of the bounding box.
        signs = [
            (-1, -1, -1), (1, -1, -1), (-1, 1, -1), (1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1),
        ]
        if 0 <= index < 8:
            sx, sy, sz = signs[index]
            return (
                sx * (half_x + standoff),
                sy * (half_y + standoff),
                sz * (half_z + standoff),
            )
    if pattern == "front_face_anchor":
        return (0.0, half_y + standoff, 0.0)
    if pattern == "back_face_anchor":
        return (0.0, -half_y - standoff, 0.0)
    if pattern in ("top_face_anchor", "top_anchor"):
        return (0.0, 0.0, half_z + standoff)
    if pattern in ("bottom_face_anchor", "bottom_anchor"):
        return (0.0, 0.0, -half_z - standoff)
    if pattern in ("left_face_anchor", "left_anchor"):
        return (-half_x - standoff, 0.0, 0.0)
    if pattern in ("right_face_anchor", "right_anchor"):
        return (half_x + standoff, 0.0, 0.0)
    if pattern == "front_face_grid":
        # Distribute ``count`` items across the front face. Single
        # column for now — produces a vertical row of fasteners.
        if count == 1:
            return (0.0, half_y + standoff, 0.0)
        # Even distribution along Z.
        z_step = body_dims["z"] / (count + 1)
        z = -half_z + z_step * (index + 1)
        return (0.0, half_y + standoff, z)
    if pattern == "front_face_belt":
        # Single horizontal trim wrapping the front face at mid-height.
        return (0.0, half_y + standoff, 0.0)
    if pattern == "back_face_belt":
        return (0.0, -half_y - standoff, 0.0)
    return None


def _expand_policies(
    graph: _NormalizedGraph,
    ctx: SynthesizerContext,
    trace: TraceBuilder,
) -> _NormalizedGraph:
    trace.emit("stage_start", stage=3)
    nodes = list(graph.nodes)
    edges = list(graph.edges)
    body_dims = _body_dimensions_from_graph(nodes)
    for policy in ctx.policies:
        node_types_present = {node["node_type"] for node in nodes}
        if not precondition_matches(
            policy.precondition,
            node_types_present=node_types_present,
            brief=ctx.brief,
            parts=ctx.parts,
            intent_tags=ctx.intent_tags,
        ):
            trace.emit(
                "policy_skipped_precondition",
                stage=3,
                policy_id=policy.policy_id,
                node_types_present=sorted(node_types_present),
            )
            continue
        trace.emit("policy_applied", stage=3, policy_id=policy.policy_id)
        for expansion in policy.expansions:
            count = _resolve_count(expansion.count, ctx.brief)
            for index in range(count):
                # Deterministic node ID: (policy_id, add_node_type, index)
                # is unique within a single synthesize call because a
                # given policy runs at most once per call and each
                # expansion's per-index counter is monotonic. uuid was
                # used here historically and broke compiler determinism
                # — replaced with the stable triple.
                new_node_id = f"policy.{policy.policy_id}.{expansion.add_node_type}.{index}"
                attrs = dict(expansion.attributes_template)
                # Placement hints become regular attributes — the
                # generator decides how to interpret them.
                for placement_key, placement_value in expansion.placement.items():
                    attrs.setdefault(str(placement_key), placement_value)
                # Pattern-aware positioning: thread a position_cm into
                # the attrs from the policy's placement.pattern when
                # we know the body dimensions. Without this, every
                # policy-added node (corner bracket, fastener) stacks
                # at origin and gets buried inside the body. Recognized
                # patterns include two_corners, four_corners,
                # eight_corners, front/back/top/bottom/left/right
                # face anchors, front_face_grid, and front/back_face_belt.
                # Unrecognized patterns fall through (node stays at origin).
                if body_dims is not None and "position_cm" not in attrs:
                    pattern_value = expansion.placement.get("pattern")
                    if isinstance(pattern_value, str):
                        pos = _position_for_policy_pattern(
                            pattern_value, index, count, body_dims
                        )
                        if pos is not None:
                            attrs["position_cm"] = pos
                # Body-aware length resolution: policies declare
                # ``length_from_body: "x" | "y" | "z"`` to mark
                # length-like attributes that should match a body
                # axis at expansion time. Without this, a trim band
                # with hard-coded ``length_cm: 30.0`` clips to 30cm
                # on every asset regardless of body size.
                if body_dims is not None:
                    length_axis = expansion.placement.get("length_from_body")
                    if isinstance(length_axis, str) and length_axis in body_dims:
                        attrs["length_cm"] = float(body_dims[length_axis])
                added_node = {
                    "node_id": new_node_id,
                    "node_type": expansion.add_node_type,
                    "attributes": attrs,
                    "_added_by_policy": policy.policy_id,
                }
                nodes.append(added_node)
                trace.emit(
                    "policy_added_node",
                    stage=3,
                    policy_id=policy.policy_id,
                    node_id=new_node_id,
                    node_type=expansion.add_node_type,
                )
                for edge_template in expansion.edges_to_existing:
                    # Connect the new node to every existing node whose
                    # type matches edge_template.target_node_type.
                    # Slice ``nodes[:-1]`` excludes only the just-appended
                    # node (the new one is always at the tail because
                    # ``nodes.append(added_node)`` ran above). The
                    # previous ``nodes[:-1-index]`` form excluded ``index``
                    # extra nodes — wrongly hiding earlier policy
                    # expansions of this loop from being valid targets.
                    targets = [
                        node["node_id"]
                        for node in nodes[:-1]
                        if node["node_type"] == edge_template.target_node_type
                    ]
                    for target_id in targets:
                        edges.append(
                            {
                                "source_id": new_node_id,
                                "target_id": target_id,
                                "edge_type": edge_template.edge_type,
                                "attributes": dict(edge_template.attributes),
                                "_added_by_policy": policy.policy_id,
                            }
                        )
                        trace.emit(
                            "policy_added_edge",
                            stage=3,
                            policy_id=policy.policy_id,
                            source_id=new_node_id,
                            target_id=target_id,
                            edge_type=edge_template.edge_type,
                        )
    trace.emit(
        "stage_end",
        stage=3,
        node_count=len(nodes),
        edge_count=len(edges),
    )
    return _NormalizedGraph(nodes=tuple(nodes), edges=tuple(edges))


# ---------- Stage 4: validate_attributes ----------


def _validate_attributes_stage(
    graph: _NormalizedGraph,
    ctx: SynthesizerContext,
    trace: TraceBuilder,
) -> tuple[tuple[ConstructionNodeTyped, ...], tuple[ConstructionEdgeTyped, ...]]:
    trace.emit("stage_start", stage=4)
    typed_nodes: list[ConstructionNodeTyped] = []
    for node in graph.nodes:
        node_id = node["node_id"]
        node_type = node["node_type"]
        raw_attrs = node["attributes"]
        try:
            typed_attrs = validate_attributes(node_type, raw_attrs)
        except (ValueError, TypeError) as exc:
            trace.emit(
                "attribute_schema_violation",
                stage=4,
                node_id=node_id,
                node_type=node_type,
                reason=str(exc),
            )
            continue
        if node_type in ATTRIBUTE_SCHEMAS:
            trace.emit(
                "attribute_validated",
                stage=4,
                node_id=node_id,
                node_type=node_type,
            )
        typed_nodes.append(
            ConstructionNodeTyped(
                node_id=node_id,
                node_type=node_type,
                domain=ctx.domain,
                raw_attributes=raw_attrs,
                typed_attributes=typed_attrs,
                added_by_policy=node.get("_added_by_policy"),
            )
        )

    valid_ids = {node.node_id for node in typed_nodes}
    typed_edges: list[ConstructionEdgeTyped] = []
    for edge in graph.edges:
        if edge["source_id"] not in valid_ids or edge["target_id"] not in valid_ids:
            # Edge references a node that failed attribute validation.
            continue
        typed_edges.append(
            ConstructionEdgeTyped(
                source_id=edge["source_id"],
                target_id=edge["target_id"],
                edge_type=edge["edge_type"],
                domain=ctx.domain,
                raw_attributes=edge["attributes"],
                typed_attributes=edge["attributes"],  # no edge schemas yet
                added_by_policy=edge.get("_added_by_policy"),
            )
        )
    trace.emit(
        "stage_end",
        stage=4,
        validated_node_count=len(typed_nodes),
        validated_edge_count=len(typed_edges),
    )
    return tuple(typed_nodes), tuple(typed_edges)


# ---------- Stage 5: topo_order ----------


def _topological_order(
    nodes: tuple[ConstructionNodeTyped, ...],
    edges: tuple[ConstructionEdgeTyped, ...],
    trace: TraceBuilder,
) -> tuple[tuple[ConstructionNodeTyped, ...], tuple[ConstructionEdgeTyped, ...]]:
    """Order nodes parents-before-children, edges after their endpoints.

    A simple, deterministic topo-sort: nodes whose dependencies come
    earlier in the input order get placed first. Cycles trip a
    diagnostic and break by node_id.
    """
    trace.emit("stage_start", stage=5)

    # Build dependency map from edges: an edge source_id "depends on"
    # target_id when the edge_type is "attached_to" / "inset_into" /
    # similar. For simplicity, all edges induce a dependency: source
    # depends on target. The generator/decorator design ensures this
    # produces sensible order.
    dependencies: dict[str, set[str]] = {node.node_id: set() for node in nodes}
    for edge in edges:
        if edge.source_id in dependencies and edge.target_id in dependencies:
            dependencies[edge.source_id].add(edge.target_id)

    ordered_ids: list[str] = []
    placed: set[str] = set()

    # Kahn's algorithm with deterministic ordering by node_id
    remaining = {node.node_id for node in nodes}
    safety = len(remaining) * 2
    while remaining and safety > 0:
        ready = sorted(
            node_id for node_id in remaining
            if not (dependencies[node_id] - placed)
        )
        if not ready:
            # Cycle — break by picking lowest node_id deterministically
            fallback = sorted(remaining)[0]
            trace.emit(
                "cycle_in_construction_graph",
                stage=5,
                broken_at=fallback,
                remaining=sorted(remaining),
            )
            ready = [fallback]
        for node_id in ready:
            ordered_ids.append(node_id)
            placed.add(node_id)
            remaining.discard(node_id)
        safety -= 1

    by_id = {node.node_id: node for node in nodes}
    ordered_nodes = tuple(by_id[nid] for nid in ordered_ids if nid in by_id)

    # Edges follow node order: an edge is "ready" when both endpoints
    # are placed. Sort edges by (source_index, target_index) to keep
    # deterministic ordering.
    order_index = {nid: i for i, nid in enumerate(ordered_ids)}
    ordered_edges = tuple(
        sorted(
            edges,
            key=lambda e: (
                order_index.get(e.source_id, len(order_index)),
                order_index.get(e.target_id, len(order_index)),
                e.edge_type,
            ),
        )
    )

    trace.emit(
        "topo_order_resolved",
        stage=5,
        order=[node.node_id for node in ordered_nodes],
    )
    trace.emit("stage_end", stage=5)
    return ordered_nodes, ordered_edges


# ---------- Stage 5b: resolve_placement_bindings ----------


def _body_dims_from_typed_nodes(nodes: tuple[ConstructionNodeTyped, ...]) -> dict[str, float]:
    """Find primary_volume node and extract its dimensions_cm."""
    for node in nodes:
        if node.node_type != "primary_volume":
            continue
        raw = node.raw_attributes if isinstance(node.raw_attributes, Mapping) else {}
        dims = raw.get("dimensions_cm")
        if isinstance(dims, Mapping):
            try:
                return {
                    "x": float(dims.get("x", 30.0)),
                    "y": float(dims.get("y", 30.0)),
                    "z": float(dims.get("z", 30.0)),
                }
            except (TypeError, ValueError):
                pass
    return {"x": 30.0, "y": 30.0, "z": 30.0}


def _resolve_placement_bindings(
    nodes: tuple[ConstructionNodeTyped, ...],
    edges: tuple[ConstructionEdgeTyped, ...],
    trace: TraceBuilder,
) -> dict[str, tuple[float, float, float]]:
    """Anchor-driven placement resolution (research Milestone 1).

    For each construction edge whose ``edge_type`` matches a registered
    ``RelationSpec``, emit anchors for source and target nodes, invoke
    ``RelationResolver``, and return ``{node_id: position_cm}`` for the
    source node. Stage 6 reads this dict to override
    ``raw_attributes.position_cm`` with the anchor-resolved transform.

    Soft-fail by design — if any step errors (missing anchor emitter,
    unknown relation, no valid candidate), the node falls back to its
    existing heuristic position_cm. Anchor resolution is additive, not
    a hard gate.
    """
    trace.emit("placement_binding_start", stage=5)
    try:
        from ...shape.placement import RelationResolver
        from .anchors import emit_anchors_for_node
    except Exception as exc:  # pragma: no cover - import path safety
        trace.emit("placement_binding_import_failed", stage=5, error=str(exc))
        return {}

    body_dims = _body_dims_from_typed_nodes(nodes)
    resolver = RelationResolver()
    resolved: dict[str, tuple[float, float, float]] = {}
    anchor_cache: dict[str, list[Any]] = {}

    def anchors_for(node: ConstructionNodeTyped) -> list[Any]:
        if node.node_id in anchor_cache:
            return anchor_cache[node.node_id]
        raw_dict = dict(node.raw_attributes) if isinstance(node.raw_attributes, Mapping) else {}
        raw_dict["node_id"] = node.node_id
        try:
            anchors = emit_anchors_for_node(node.node_type, raw_dict, body_dims)
        except Exception as exc:  # pragma: no cover - emitter safety
            trace.emit(
                "anchor_emit_failed",
                stage=5,
                node_id=node.node_id,
                node_type=node.node_type,
                error=str(exc),
            )
            anchors = []
        anchor_cache[node.node_id] = anchors
        return anchors

    by_id = {n.node_id: n for n in nodes}
    # Track per-target-anchor usage so multiple sources docking with
    # the same host distribute across distinct anchors (capacity-aware).
    # Maps target_anchor_id → number of source bindings already placed.
    anchor_usage: dict[str, int] = {}
    for edge in edges:
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None or target is None:
            continue
        source_anchors = anchors_for(source)
        target_anchors_all = anchors_for(target)
        if not source_anchors or not target_anchors_all:
            continue
        # Filter out target anchors that have reached capacity.
        target_anchors = [
            a for a in target_anchors_all
            if anchor_usage.get(a.anchor_id, 0) < a.capacity
        ]
        if not target_anchors:
            # Capacity exhausted on all known anchors — record + fall
            # through to heuristic.
            trace.emit(
                "placement_binding_unresolved",
                stage=5,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation=edge.edge_type,
                proof="all_target_anchors_at_capacity",
            )
            continue
        try:
            binding = resolver.resolve(
                edge_id=f"{edge.source_id}__{edge.edge_type}__{edge.target_id}",
                relation=edge.edge_type,
                source_node_id=edge.source_id,
                target_node_id=edge.target_id,
                source_anchors=source_anchors,
                target_anchors=target_anchors,
            )
        except Exception as exc:  # pragma: no cover - resolver safety
            trace.emit(
                "relation_resolve_failed",
                stage=5,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation=edge.edge_type,
                error=str(exc),
            )
            continue
        if binding.is_resolved() and binding.chosen is not None:
            # First valid binding wins for each source node — subsequent
            # edges on the same source are decorators, not primary
            # placement. Mark the chosen target anchor as used.
            resolved.setdefault(edge.source_id, binding.chosen.transform_world_cm)
            # Stash the resolved frame so direct-anchor-read generators
            # (P1 migration) can consume it without going through the
            # position_cm bridge.
            try:
                from .anchors import ANCHOR_EMITTERS  # type: ignore
                from .generators._anchor_bridge import ResolvedAnchorFrame, stash_anchor_resolution

                # Find the target anchor's z_axis from its host's anchor list.
                z_axis_value: tuple[float, float, float] = (0.0, 0.0, 1.0)
                for a in target_anchors:
                    if a.anchor_id == binding.chosen.target_anchor_id:
                        z_axis_value = a.frame.z_axis
                        break
                _resolved_frame = ResolvedAnchorFrame(
                    transform_world_cm=binding.chosen.transform_world_cm,
                    z_axis=z_axis_value,
                    source_anchor_id=binding.chosen.source_anchor_id,
                    target_anchor_id=binding.chosen.target_anchor_id,
                    relation=edge.edge_type,
                )
                # ConstructionNodeTyped.raw_attributes is a frozen
                # Mapping; we can't mutate it. Instead, record the
                # frame in a side-channel keyed by source_id so the
                # P1 follow-on migration can read it deterministically.
                # The accumulator carries this for Stage 6.
                resolved.setdefault(
                    f"__frame__{edge.source_id}", _resolved_frame  # type: ignore
                )
                # Quiet unused-import warnings.
                _ = (ANCHOR_EMITTERS, stash_anchor_resolution)
            except Exception:  # pragma: no cover - bridge is additive
                pass
            anchor_usage[binding.chosen.target_anchor_id] = (
                anchor_usage.get(binding.chosen.target_anchor_id, 0) + 1
            )
            trace.emit(
                "placement_binding_resolved",
                stage=5,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation=edge.edge_type,
                source_anchor=binding.chosen.source_anchor_id,
                target_anchor=binding.chosen.target_anchor_id,
                transform_cm=list(binding.chosen.transform_world_cm),
            )
        else:
            trace.emit(
                "placement_binding_unresolved",
                stage=5,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation=edge.edge_type,
                proof=binding.proof,
            )

    trace.emit("placement_binding_end", stage=5, resolved_count=len(resolved))
    return resolved


# ---------- Stage 6: emit_node_ops ----------


@dataclass
class _NodeOpAccumulator:
    """Mutable accumulator for node-emitted ops + their owning node_id.

    Threaded through Stage 6 so Stage 7's edge decorators can ask
    "what ops did this node emit" via the OpResolver protocol.
    """

    ops: list[ShapeOp]
    ops_by_node: dict[str, list[ShapeOp]]
    anchor_resolved_positions: dict[str, tuple[float, float, float]]

    @classmethod
    def empty(cls) -> _NodeOpAccumulator:
        return cls(ops=[], ops_by_node={}, anchor_resolved_positions={})


class _OpResolverImpl:
    def __init__(self, accumulator: _NodeOpAccumulator) -> None:
        self._acc = accumulator

    def ops_for_node(self, node_id: str) -> tuple[ShapeOp, ...]:
        return tuple(self._acc.ops_by_node.get(node_id, ()))


def _emit_node_ops(
    nodes: tuple[ConstructionNodeTyped, ...],
    ctx: SynthesizerContext,
    registry: GeneratorRegistry,
    trace: TraceBuilder,
    anchor_positions: Mapping[str, tuple[float, float, float]] | None = None,
) -> _NodeOpAccumulator:
    trace.emit("stage_start", stage=6)
    acc = _NodeOpAccumulator.empty()
    acc.anchor_resolved_positions.update(anchor_positions or {})
    for node in nodes:
        generator = registry.resolve_generator(node.domain, node.node_type)
        if generator is None:
            trace.emit(
                "no_generator_for_node",
                stage=6,
                node_id=node.node_id,
                node_type=node.node_type,
                domain=node.domain,
            )
            continue
        trace.emit(
            "generator_resolved",
            stage=6,
            node_id=node.node_id,
            node_type=node.node_type,
            domain=node.domain,
            manifest_emitted_op_kinds=list(generator.manifest.emitted_op_kinds),
        )
        emitted: list[ShapeOp] = []
        for op in generator.implementation(node, ctx):
            if not isinstance(op, ShapeOp):
                raise TypeError(
                    f"generator for {node.node_type!r} emitted non-ShapeOp "
                    f"value {type(op).__name__}"
                )
            # Apply auto-graph positioning to primitive ops. The
            # construction-graph node may carry ``position_cm`` in its
            # raw attributes (see
            # ``_auto_graph_from_parts`` /
            # ``_infer_position_cm``). The kernel reads ``center`` on
            # every primitive (cube, capsule, cylinder, etc.) so we
            # thread the position through here — without touching
            # generators individually. Skips ops that already set
            # ``center`` (the generator's own placement wins) and
            # non-primitive ops (op.union, op.bevel, etc.).
            if op.op.startswith("solid.") and "center" not in op.parameters:
                # Priority: anchor-resolved position (M1 contract) →
                # raw_attributes.position_cm (heuristic fallback).
                resolved_position = acc.anchor_resolved_positions.get(node.node_id)
                if resolved_position is not None:
                    op.parameters["center"] = resolved_position
                    op.parameters["_lathe_placement_source"] = "anchor_binding"
                else:
                    raw_attrs = getattr(node, "raw_attributes", None)
                    if isinstance(raw_attrs, Mapping):
                        position = raw_attrs.get("position_cm")
                        if position is not None:
                            try:
                                coords = tuple(float(v) for v in position)
                                if len(coords) == 3:
                                    op.parameters["center"] = coords
                                    op.parameters["_lathe_placement_source"] = "heuristic_position_cm"
                            except (TypeError, ValueError):
                                pass
            emitted.append(op)
            acc.ops.append(op)
            trace.emit(
                "node_op",
                stage=6,
                node_id=node.node_id,
                node_type=node.node_type,
                op=op.op,
                target=op.target,
            )
        acc.ops_by_node[node.node_id] = emitted
    trace.emit("stage_end", stage=6, op_count=len(acc.ops))
    return acc


# ---------- Stage 7: emit_edge_ops ----------


def _emit_edge_ops(
    edges: tuple[ConstructionEdgeTyped, ...],
    ctx: SynthesizerContext,
    registry: GeneratorRegistry,
    accumulator: _NodeOpAccumulator,
    trace: TraceBuilder,
) -> list[ShapeOp]:
    trace.emit("stage_start", stage=7)
    resolver: OpResolver = _OpResolverImpl(accumulator)
    edge_ops: list[ShapeOp] = []
    for edge in edges:
        decorator = registry.resolve_decorator(edge.domain, edge.edge_type)
        if decorator is None:
            trace.emit(
                "no_decorator_for_edge",
                stage=7,
                source_id=edge.source_id,
                target_id=edge.target_id,
                edge_type=edge.edge_type,
                domain=edge.domain,
            )
            continue
        trace.emit(
            "decorator_resolved",
            stage=7,
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=edge.edge_type,
            domain=edge.domain,
        )
        for op in decorator.implementation(edge, ctx, resolver):
            if not isinstance(op, ShapeOp):
                raise TypeError(
                    f"decorator for {edge.edge_type!r} emitted non-ShapeOp "
                    f"value {type(op).__name__}"
                )
            edge_ops.append(op)
            trace.emit(
                "edge_op",
                stage=7,
                source_id=edge.source_id,
                target_id=edge.target_id,
                edge_type=edge.edge_type,
                op=op.op,
                target=op.target,
            )
    trace.emit("stage_end", stage=7, edge_op_count=len(edge_ops))
    return edge_ops


# ---------- Stage 8: validate_ops ----------


def _validate_ops(
    ops: list[ShapeOp], trace: TraceBuilder
) -> list[ShapeOp]:
    trace.emit("stage_start", stage=8)
    valid: list[ShapeOp] = []
    for op in ops:
        if op.op not in ALL_OPS:
            trace.emit(
                "emitted_op_outside_shape_ir_v2",
                stage=8,
                op=op.op,
                target=op.target,
            )
            continue
        valid.append(op)
    trace.emit("ops_validated", stage=8, valid_count=len(valid), total_count=len(ops))
    trace.emit("stage_end", stage=8)
    return valid


# ---------- Pipeline orchestrator ----------


def synthesize_procedural_program(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    registry: GeneratorRegistry | None = None,
    style_packs: Mapping[str, StyleKnowledge] | None = None,
    policy_packs: Mapping[str, CompositionPolicy] | None = None,
    alias_packs: Mapping[str, FamilyAlias] | None = None,
) -> SynthesisResult:
    """Run the full 8-stage procedural compiler pipeline.

    Knowledge packs default to disk-loaded sets via the loader modules.
    Tests may pass pre-loaded mappings to skip disk IO.

    The returned SynthesisResult contains:
      - shape_program: the ShapeIR v2 program ready for lower_to_v1
        and kernel execution.
      - synthesized_graph_nodes: nodes that policies added on top of
        the authored graph.
      - trace: full pipeline trace, JSON-serializable.

    The function does NOT dispatch on family name anywhere. Family
    alias resolution in Stage 1 is metadata-only — family appears in
    the trace and in the output ShapeProgram.family tag, never in
    behavior selection.
    """
    registry = registry if registry is not None else REGISTRY
    trace = TraceBuilder()

    # Stage 1
    ctx = resolve_context(
        asset,
        runtime,
        style_packs=style_packs,
        policy_packs=policy_packs,
        alias_packs=alias_packs,
        trace=trace,
    )

    # Stage 2
    normalized = _normalize_graph(ctx, trace)

    # Stage 3
    expanded = _expand_policies(normalized, ctx, trace)

    # Stage 4
    typed_nodes, typed_edges = _validate_attributes_stage(expanded, ctx, trace)

    # Augment context with typed nodes/edges (immutable replacement)
    ctx_typed = SynthesizerContext(
        asset=ctx.asset,
        runtime=ctx.runtime,
        asset_name=ctx.asset_name,
        parts=ctx.parts,
        intent_tags=ctx.intent_tags,
        brief=ctx.brief,
        domain=ctx.domain,
        style=ctx.style,
        policies=ctx.policies,
        family_alias=ctx.family_alias,
        raw_graph_nodes=ctx.raw_graph_nodes,
        raw_graph_edges=ctx.raw_graph_edges,
        typed_nodes=typed_nodes,
        typed_edges=typed_edges,
    )

    # Stage 5
    ordered_nodes, ordered_edges = _topological_order(typed_nodes, typed_edges, trace)

    # Stage 5b — Anchor-driven placement resolution (research M1).
    # Pre-pass before Stage 6 so resolved transforms feed back into the
    # raw_attributes ``position_cm`` channel that Stage 6's center
    # post-process already honors.
    anchor_positions = _resolve_placement_bindings(ordered_nodes, ordered_edges, trace)

    # Stage 6
    accumulator = _emit_node_ops(
        ordered_nodes, ctx_typed, registry, trace, anchor_positions=anchor_positions
    )

    # Stage 7
    edge_ops = _emit_edge_ops(ordered_edges, ctx_typed, registry, accumulator, trace)

    # Stage 8
    validated = _validate_ops([*accumulator.ops, *edge_ops], trace)

    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=ctx.asset_name,
        family=ctx.family_alias,  # metadata tag, never dispatched on
        ops=tuple(validated),
    )

    # Report policy-added nodes for compatibility with the legacy
    # synthesized_graph_nodes shape.
    synthesized = tuple(
        {
            "node_id": node.node_id,
            "node_type": node.node_type,
            "added_by_policy": node.added_by_policy,
            "attributes": dict(node.raw_attributes),
        }
        for node in typed_nodes
        if node.added_by_policy is not None
    )

    return SynthesisResult(
        shape_program=program,
        synthesized_graph_nodes=synthesized,
        trace=trace.freeze(),
    )
