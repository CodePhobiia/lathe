"""Connection-aware layout controls for procedural families."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .interface_connections import coerce_interface_connection

ROUTE_RELATIONS = {"connects_to", "routes_to", "opens_to"}
ATTACH_RELATIONS = {"attach", "attached_to", "snaps_to", "mounts_to", "auto_attach"}
SUPPORT_RELATIONS = {"supports", "contains", "depends_on"}


def connection_layout_from_authoring(
    *,
    family: str,
    shape_controls: Mapping[str, Any] | None,
    connections: Sequence[Any] | None,
    sockets: Sequence[str] | None = None,
    anchors: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Derive procedural layout controls from authored interface connections."""
    controls = dict(shape_controls or {})
    normalized = [
        coerce_interface_connection(connection, f"connection_{idx}")
        for idx, connection in enumerate(_connection_sequence(connections))
    ]
    if not normalized:
        return {"shape_controls": {}, "connections": [], "summary": _empty_summary()}

    summary = _connection_summary(normalized, sockets=sockets or [], anchors=anchors or [])
    derived: dict[str, Any] = {
        "connection_count": summary["connection_count"],
        "connection_route_count": summary["route_connection_count"],
        "connection_attach_count": summary["attach_connection_count"],
        "connection_support_count": summary["support_connection_count"],
        "connection_external_count": summary["external_connection_count"],
        "connection_branch_count": summary["branch_connection_count"],
        "connection_layout_mode": _layout_mode(summary),
        "connection_segment_count": _segment_count(summary),
        "connection_span_count": _span_count(summary),
        "connection_path_complexity": _path_complexity(summary),
    }
    family_controls = _family_controls(family, summary)
    derived.update(family_controls)
    return {
        "shape_controls": _fill_missing(controls, derived),
        "connections": normalized,
        "summary": summary,
    }


def _connection_summary(
    connections: Sequence[Mapping[str, Any]],
    *,
    sockets: Sequence[str],
    anchors: Sequence[str],
) -> dict[str, Any]:
    relations: dict[str, int] = {}
    endpoint_refs: set[str] = set()
    external_refs: set[str] = set()
    endpoint_degrees: dict[str, int] = {}
    local_refs = {str(item) for item in [*sockets, *anchors] if item}
    for connection in connections:
        relation = str(connection.get("relation") or "attach").lower()
        relations[relation] = relations.get(relation, 0) + 1
        for endpoint_key in ("source", "target"):
            endpoint = str(connection.get(endpoint_key) or "")
            if not endpoint:
                continue
            endpoint_refs.add(endpoint)
            endpoint_degrees[endpoint] = endpoint_degrees.get(endpoint, 0) + 1
            if endpoint not in local_refs and ("." in endpoint or ":" in endpoint):
                external_refs.add(endpoint)

    route_count = sum(count for relation, count in relations.items() if relation in ROUTE_RELATIONS)
    attach_count = sum(count for relation, count in relations.items() if relation in ATTACH_RELATIONS)
    support_count = sum(count for relation, count in relations.items() if relation in SUPPORT_RELATIONS)
    branch_count = sum(1 for degree in endpoint_degrees.values() if degree > 2)
    return {
        "connection_count": len(connections),
        "route_connection_count": route_count,
        "attach_connection_count": attach_count,
        "support_connection_count": support_count,
        "external_connection_count": len(external_refs),
        "branch_connection_count": branch_count,
        "endpoint_count": len(endpoint_refs),
        "relations": dict(sorted(relations.items())),
        "external_refs": sorted(external_refs),
        "route_edges": _route_edges(connections),
        "layout_points": _layout_points(endpoint_refs),
    }


def _connection_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str) or isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [item for item in value if item is not None and item != ""]
    return [value]


def _empty_summary() -> dict[str, Any]:
    return {
        "connection_count": 0,
        "route_connection_count": 0,
        "attach_connection_count": 0,
        "support_connection_count": 0,
        "external_connection_count": 0,
        "branch_connection_count": 0,
        "endpoint_count": 0,
        "relations": {},
        "external_refs": [],
        "route_edges": [],
        "layout_points": [],
    }


def _route_edges(connections: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for connection in connections:
        relation = str(connection.get("relation") or "attach").lower()
        if relation not in ROUTE_RELATIONS and relation not in ATTACH_RELATIONS:
            continue
        source = str(connection.get("source") or "")
        target = str(connection.get("target") or "")
        if not source or not target:
            continue
        edges.append({"source": source, "target": target, "relation": relation})
    return edges


def _layout_points(endpoint_refs: set[str]) -> list[dict[str, Any]]:
    ordered = sorted(endpoint_refs)
    count = max(1, len(ordered) - 1)
    return [
        {
            "endpoint": endpoint,
            "order": index,
            "normalized_position": [0.0, 0.0, round(-0.5 + index / count, 6)],
        }
        for index, endpoint in enumerate(ordered)
    ]


def _layout_mode(summary: Mapping[str, Any]) -> str:
    route_count = int(summary.get("route_connection_count") or 0)
    branch_count = int(summary.get("branch_connection_count") or 0)
    support_count = int(summary.get("support_connection_count") or 0)
    if branch_count >= 3:
        return "network"
    if route_count >= 2:
        return "linear_route"
    if support_count:
        return "mounted"
    return "attached"


def _segment_count(summary: Mapping[str, Any]) -> int:
    return min(16, max(1, int(summary.get("route_connection_count") or 0) * 2 + int(summary.get("attach_connection_count") or 0)))


def _span_count(summary: Mapping[str, Any]) -> int:
    return min(10, max(1, int(summary.get("route_connection_count") or 0) + int(summary.get("branch_connection_count") or 0)))


def _path_complexity(summary: Mapping[str, Any]) -> float:
    connection_count = int(summary.get("connection_count") or 0)
    endpoint_count = int(summary.get("endpoint_count") or 0)
    if not connection_count:
        return 0.0
    return round(min(1.0, (connection_count * 0.18) + (endpoint_count * 0.06)), 6)


def _family_controls(family: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    route_count = int(summary.get("route_connection_count") or 0)
    attach_count = int(summary.get("attach_connection_count") or 0)
    support_count = int(summary.get("support_connection_count") or 0)
    branch_count = int(summary.get("branch_connection_count") or 0)
    external_count = int(summary.get("external_connection_count") or 0)
    segment_count = _segment_count(summary)
    span_count = _span_count(summary)
    if family == "procedural_road":
        return {
            "segments": segment_count,
            "segment_count": segment_count,
            "branches": max(branch_count, max(0, route_count - 1)),
            "branch_count": max(branch_count, max(0, route_count - 1)),
            "junction_count": max(1 if branch_count or route_count > 1 else 0, min(6, branch_count)),
            "road_length": round(1.6 + 0.42 * segment_count, 6),
            "network_type": "connected_route" if route_count else "local_link",
        }
    if family == "procedural_bridge":
        return {
            "spans": span_count,
            "span_count": span_count,
            "piers": max(2, span_count + 1),
            "pier_count": max(2, span_count + 1),
            "bridge_length": round(1.3 + 0.34 * span_count, 6),
        }
    if family == "procedural_access":
        walkway_count = max(1, route_count)
        platform_count = max(1 if attach_count or support_count else 0, external_count)
        return {
            "walkways": walkway_count,
            "walkway_count": walkway_count,
            "span_count": span_count,
            "catwalk_count": max(0, route_count - 1),
            "platform_count": min(10, platform_count),
            "guardrail_count": min(16, max(2, walkway_count * 2)),
            "support_count": min(12, max(support_count, walkway_count)),
            "access_depth": round(1.1 + 0.28 * span_count, 6),
            "traversal_depth": round(1.1 + 0.28 * span_count, 6),
        }
    if family == "procedural_infrastructure":
        service_count = max(1, route_count + attach_count)
        return {
            "pipe_count": service_count,
            "duct_count": max(0, route_count - 1),
            "conduit_count": max(0, attach_count),
            "junction_box_count": max(1 if branch_count else 0, min(8, branch_count + external_count)),
            "service_rail_count": max(0, support_count),
            "support_count": min(12, max(support_count, route_count)),
            "network_depth": round(1.0 + 0.32 * segment_count, 6),
            "infrastructure_depth": round(1.0 + 0.32 * segment_count, 6),
        }
    if family == "procedural_interior":
        corridor_count = max(1, route_count) if route_count else 0
        return {
            "room_layout": "connected_route" if route_count else "linear",
            "corridor_count": corridor_count,
            "corridors": corridor_count,
            "partition_count": max(0, attach_count + branch_count),
            "stair_core_count": 1 if support_count and external_count else 0,
            "room_depth": round(0.9 + 0.18 * segment_count, 6),
        }
    if family == "procedural_building":
        return {
            "facade_style": "connected_facade" if attach_count or route_count else "grid",
            "balcony_count": min(12, attach_count + external_count),
            "stair_core_count": 1 if route_count and support_count else 0,
            "wing_count": min(4, max(0, branch_count)),
        }
    if family == "procedural_city_block":
        return {
            "block_layout": "connected_network" if route_count > 1 else "street_edge",
            "street_count": max(1, route_count),
            "lot_count": max(2, route_count + branch_count + external_count),
            "block_depth": round(1.0 + 0.22 * segment_count, 6),
        }
    if family == "procedural_terrain":
        return {
            "path_count": max(1, route_count),
            "platform_count": max(0, support_count + attach_count),
            "terrain_depth": round(1.0 + 0.18 * segment_count, 6),
        }
    if family == "procedural_setpiece":
        structure_count = max(2, route_count + attach_count + branch_count)
        return {
            "setpiece_layout": "connected_compound" if route_count > 1 else "anchored_cluster",
            "structure_count": min(8, structure_count),
            "building_count": min(6, max(1, structure_count - 1)),
            "road_segment_count": max(1, segment_count),
            "access_count": max(1 if attach_count or support_count else 0, route_count),
            "infrastructure_count": max(1 if external_count else 0, attach_count + support_count),
            "prop_count": max(2, branch_count + external_count),
            "terrain_platforms": max(1 if support_count else 0, min(4, support_count + attach_count)),
            "branch_count": max(branch_count, max(0, route_count - 1)),
            "setpiece_depth": round(1.2 + 0.24 * segment_count, 6),
        }
    return {}


def _fill_missing(author_controls: Mapping[str, Any], derived_controls: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(derived_controls)
    out.update(dict(author_controls))
    return out
