"""Interface connection helpers for sockets, pivots, anchors, and scene links."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .interface_entries import coerce_interface_entry

CONNECTION_CONSTRUCTORS = {"connection", "connect", "attachment", "attach"}
EXTERNAL_ENDPOINT_ROLE = "external"
LOCAL_ENDPOINT_ROLES = {"socket", "pivot", "anchor"}
ROUTE_RELATIONS = {"connects_to", "routes_to", "opens_to"}
ATTACH_RELATIONS = {"attach", "attached_to", "snaps_to", "supports", "mounts_to"}


def connection_constructor(entry: Any) -> str | None:
    """Return the source constructor name for a connection call expression."""
    if isinstance(entry, dict) and entry.get("type") == "call":
        name = entry.get("name")
        if isinstance(name, str) and name in CONNECTION_CONSTRUCTORS:
            return name
    return None


def coerce_interface_connection(entry: Any, fallback: str = "connection") -> dict[str, Any]:
    """Coerce string, mapping, or call-expression connections to a mapping."""
    positional: list[Any] = []
    if isinstance(entry, str):
        payload = _connection_from_string(entry)
    elif isinstance(entry, Mapping):
        constructor = connection_constructor(entry)
        if constructor is not None:
            payload = {}
            for arg in entry.get("args") or []:
                if not isinstance(arg, Mapping) or "value" not in arg:
                    continue
                arg_name = arg.get("name")
                if arg_name is None:
                    positional.append(arg["value"])
                else:
                    payload[str(arg_name)] = arg["value"]
        else:
            payload = dict(entry)
    else:
        payload = {"source": str(entry)}

    if positional:
        payload.setdefault("source", positional[0])
    if len(positional) > 1:
        payload.setdefault("target", positional[1])

    source = _first_present(
        payload,
        "source",
        "from",
        "source_socket",
        "from_socket",
        "from_anchor",
        "from_pivot",
        "a",
        "left",
    )
    target = _first_present(
        payload,
        "target",
        "to",
        "target_socket",
        "to_socket",
        "to_anchor",
        "to_pivot",
        "b",
        "right",
    )
    relation = _first_present(payload, "relation", "type", "kind") or "attach"
    out = {
        "id": str(payload.get("id") or payload.get("name") or _connection_id(source, target, fallback)),
        "source": _endpoint_ref(source),
        "target": _endpoint_ref(target),
        "relation": str(relation),
    }
    for key in (
        "socket_type",
        "compat_kind",
        "axis",
        "clearance",
        "snap_grid",
        "parent_part_id",
        "priority",
        "metadata",
    ):
        if key in payload:
            out[key] = payload[key]
    return out


def resolve_interface_connections(
    *,
    sockets: Sequence[Mapping[str, Any]],
    pivots: Sequence[Mapping[str, Any]],
    anchors: Sequence[Mapping[str, Any]],
    raw_connections: Sequence[Any],
    clearance: Any = None,
    snap_grid: Any = None,
    auto_connect: bool = False,
) -> dict[str, Any]:
    """Resolve authored connection declarations against local interface entries."""
    endpoint_index = _endpoint_index(sockets=sockets, pivots=pivots, anchors=anchors)
    connections: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    for idx, raw in enumerate(_connection_sequence(raw_connections)):
        connection = coerce_interface_connection(raw, f"connection_{idx}")
        resolved = _resolve_connection(
            connection,
            endpoint_index=endpoint_index,
            source="authored",
            clearance=clearance,
            snap_grid=snap_grid,
        )
        if resolved["source"]:
            used_sources.add(str(resolved["source"]))
        connections.append(resolved)

    slots = _connection_slots(endpoint_index)
    if auto_connect:
        for slot in slots:
            source_id = str(slot.get("endpoint") or "")
            if not source_id or source_id in used_sources:
                continue
            target = next(iter(slot.get("compatible_targets", []) or []), None)
            if not target:
                continue
            raw = {
                "id": f"auto_{_slug(source_id)}_to_{_slug(str(target))}",
                "source": source_id,
                "target": target,
                "relation": "auto_attach",
            }
            connections.append(
                _resolve_connection(
                    raw,
                    endpoint_index=endpoint_index,
                    source="auto",
                    clearance=clearance,
                    snap_grid=snap_grid,
                )
            )
    return {
        "connections": _dedupe_connections(connections),
        "connection_slots": slots,
    }


def _connection_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, Mapping)):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [item for item in value if item is not None and item != ""]
    return [value]


def _connection_from_string(value: str) -> dict[str, Any]:
    text = value.strip()
    for delimiter in ("->", "=>", "~>"):
        if delimiter in text:
            left, right = text.split(delimiter, 1)
            return {"source": left.strip(), "target": right.strip()}
    return {"source": text}


def _first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if _present(value):
            return value
    return None


def _endpoint_ref(value: Any) -> str:
    if isinstance(value, Mapping):
        coerced = coerce_interface_entry(value)
        value = coerced.get("id") or coerced.get("name")
    if value is None:
        return ""
    return str(value)


def _connection_id(source: Any, target: Any, fallback: str) -> str:
    left = _endpoint_ref(source)
    right = _endpoint_ref(target)
    if left and right:
        return f"{_slug(left)}_to_{_slug(right)}"
    if left:
        return f"{_slug(left)}_connection"
    return fallback


def _endpoint_index(
    *,
    sockets: Sequence[Mapping[str, Any]],
    pivots: Sequence[Mapping[str, Any]],
    anchors: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for role, entries in (("socket", sockets), ("pivot", pivots), ("anchor", anchors)):
        for entry in entries:
            record = _endpoint_record(role, entry)
            if not record["id"]:
                continue
            for alias in _endpoint_aliases(role, record):
                index.setdefault(alias, record)
    return index


def _endpoint_record(role: str, entry: Mapping[str, Any]) -> dict[str, Any]:
    endpoint_id = str(entry.get("id") or entry.get("name") or "")
    return {
        "id": endpoint_id,
        "name": str(entry.get("name") or endpoint_id),
        "role": role,
        "kind": str(entry.get("kind") or entry.get("compat_kind") or entry.get("socket_type") or entry.get("pivot_type") or ""),
        "socket_type": str(entry.get("socket_type") or ""),
        "pivot_type": str(entry.get("pivot_type") or ""),
        "parent_part_id": str(entry.get("parent_part_id") or ""),
        "position": entry.get("position") or entry.get("origin"),
        "transform": entry.get("transform"),
    }


def _endpoint_aliases(role: str, record: Mapping[str, Any]) -> set[str]:
    aliases = {str(record.get("id") or ""), str(record.get("name") or "")}
    aliases.update({f"{role}.{alias}" for alias in list(aliases) if alias})
    aliases.update({f"{role}:{alias}" for alias in list(aliases) if alias})
    return {alias for alias in aliases if alias}


def _resolve_connection(
    connection: Mapping[str, Any],
    *,
    endpoint_index: Mapping[str, Mapping[str, Any]],
    source: str,
    clearance: Any,
    snap_grid: Any,
) -> dict[str, Any]:
    source_ref = str(connection.get("source") or "")
    target_ref = str(connection.get("target") or "")
    source_endpoint = endpoint_index.get(source_ref)
    target_endpoint = endpoint_index.get(target_ref)
    relation = str(connection.get("relation") or "attach")
    compatible, score, reason = _compatibility(connection, source_endpoint, target_endpoint, relation)
    out: dict[str, Any] = {
        "id": str(connection.get("id") or _connection_id(source_ref, target_ref, "connection")),
        "source": source_ref,
        "target": target_ref,
        "relation": relation,
        "source_role": str(source_endpoint.get("role") if source_endpoint else _endpoint_role(source_ref)),
        "target_role": str(target_endpoint.get("role") if target_endpoint else _endpoint_role(target_ref)),
        "compatible": compatible,
        "compatibility_score": score,
        "compatibility_reason": reason,
        "resolution": source,
    }
    if source_endpoint:
        out["source_endpoint"] = _public_endpoint(source_endpoint)
    if target_endpoint:
        out["target_endpoint"] = _public_endpoint(target_endpoint)
    if "socket_type" in connection:
        out["socket_type"] = connection["socket_type"]
    if "compat_kind" in connection:
        out["compat_kind"] = connection["compat_kind"]
    resolved_clearance = connection.get("clearance", clearance)
    if _present(resolved_clearance):
        out["clearance"] = resolved_clearance
    resolved_snap = connection.get("snap_grid", snap_grid)
    if _present(resolved_snap):
        out["snap_grid"] = resolved_snap
    transform_hint = _transform_hint(source_endpoint, target_endpoint)
    if transform_hint:
        out["transform_hint"] = transform_hint
    if isinstance(connection.get("metadata"), Mapping):
        out["metadata"] = dict(connection["metadata"])
    return out


def _endpoint_role(ref: str) -> str:
    if not ref:
        return "missing"
    prefix = ref.split(".", 1)[0].split(":", 1)[0]
    if prefix in LOCAL_ENDPOINT_ROLES:
        return prefix
    return EXTERNAL_ENDPOINT_ROLE if "." in ref or ":" in ref else "unresolved"


def _compatibility(
    connection: Mapping[str, Any],
    source_endpoint: Mapping[str, Any] | None,
    target_endpoint: Mapping[str, Any] | None,
    relation: str,
) -> tuple[bool, float, str]:
    if source_endpoint is None or target_endpoint is None:
        return True, 0.5, "external_or_deferred_endpoint"
    source_role = str(source_endpoint.get("role") or "")
    target_role = str(target_endpoint.get("role") or "")
    source_kind = str(connection.get("compat_kind") or source_endpoint.get("kind") or "")
    target_kind = str(target_endpoint.get("kind") or "")
    socket_type = str(connection.get("socket_type") or source_endpoint.get("socket_type") or "")
    if source_role == "socket" and target_role in {"pivot", "anchor"}:
        return True, 0.9 if socket_type in {"attach", "mount", "attachment_point", "slot"} else 0.75, "socket_to_local_anchor"
    if target_role == "socket" and source_role in {"pivot", "anchor"}:
        return True, 0.9 if socket_type in {"attach", "mount", "attachment_point", "slot"} else 0.75, "local_anchor_to_socket"
    if source_kind and target_kind and source_kind == target_kind:
        return True, 1.0, "matching_kind"
    if _token_overlap(str(source_endpoint.get("id") or ""), str(target_endpoint.get("id") or "")):
        return True, 0.72, "matching_endpoint_tokens"
    if relation in ROUTE_RELATIONS | ATTACH_RELATIONS:
        return True, 0.66, "relation_allows_connection"
    return True, 0.58, "generic_connection"


def _connection_slots(endpoint_index: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, Mapping[str, Any]] = {}
    for endpoint in endpoint_index.values():
        endpoint_id = str(endpoint.get("id") or "")
        if endpoint_id:
            unique.setdefault(endpoint_id, endpoint)
    slots: list[dict[str, Any]] = []
    for endpoint_id, endpoint in sorted(unique.items()):
        role = str(endpoint.get("role") or "")
        if role != "socket":
            continue
        compatible_targets = []
        for target_id, target in sorted(unique.items()):
            if target_id == endpoint_id:
                continue
            compatible, score, _reason = _compatibility({}, endpoint, target, "attach")
            if compatible and score >= 0.66:
                compatible_targets.append(target_id)
        slots.append(
            {
                "endpoint": endpoint_id,
                "role": role,
                "kind": endpoint.get("kind") or endpoint.get("socket_type") or "",
                "parent_part_id": endpoint.get("parent_part_id") or "",
                "compatible_targets": compatible_targets[:8],
            }
        )
    return slots


def _transform_hint(
    source_endpoint: Mapping[str, Any] | None,
    target_endpoint: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if source_endpoint is None or target_endpoint is None:
        return None
    source_pos = _vec3(source_endpoint.get("position"))
    target_pos = _vec3(target_endpoint.get("position"))
    if source_pos is None or target_pos is None:
        return None
    delta = [round(target_pos[idx] - source_pos[idx], 6) for idx in range(3)]
    return {
        "mode": "snap_source_to_target",
        "source_position": source_pos,
        "target_position": target_pos,
        "translation": delta,
    }


def _vec3(value: Any) -> list[float] | None:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray) or len(value) < 3:
        return None
    out: list[float] = []
    for item in value[:3]:
        if not isinstance(item, int | float) or isinstance(item, bool):
            return None
        out.append(round(float(item), 6))
    return out


def _public_endpoint(endpoint: Mapping[str, Any]) -> dict[str, Any]:
    out = {
        "id": endpoint.get("id"),
        "name": endpoint.get("name"),
        "role": endpoint.get("role"),
    }
    for key in ("kind", "socket_type", "pivot_type", "parent_part_id", "position"):
        value = endpoint.get(key)
        if _present(value):
            out[key] = value
    return out


def _dedupe_connections(connections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for connection in connections:
        key = str(connection.get("id") or (connection.get("source"), connection.get("target")))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(connection))
    return out


def _token_overlap(left: str, right: str) -> bool:
    return bool(_tokens(left) & _tokens(right))


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not slug:
        return "connection"
    if not slug[0].isalpha():
        slug = f"x_{slug}"
    return slug[:64].rstrip("_") or "connection"


def _present(value: Any) -> bool:
    return value is not None and value != ""
