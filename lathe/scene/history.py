"""Scene Patch history records for deterministic Wonder rollback."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from lathe.wonder import validate_contract

from .ids import clamp_id_body

SCENE_HISTORY_VERSION = "lathe.scene_history.v1"
SCENE_HISTORY_SCHEMA_FILENAME = "scene_history.schema.json"
SCENE_HISTORY_CONTRACT = "scene_history"
DETERMINISTIC_HISTORY_TIMESTAMP = "1970-01-01T00:00:00Z"

_ALL_PATCH_CHANGE_CATEGORIES = [
    "affordances",
    "assets",
    "cameras",
    "curiosity_anchors",
    "debris",
    "geometry",
    "hidden_state",
    "layout",
    "lighting",
    "materials",
    "metadata",
    "objects",
    "props",
    "relationships",
    "scale",
    "state",
    "style",
    "transforms",
]


class SceneHistoryError(ValueError):
    """Raised when a scene history record cannot be produced or applied."""


class JsonPatchError(SceneHistoryError):
    """Raised when a JSON Patch operation cannot be applied."""


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def normalized_scene_graph(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-normalized Scene Graph mapping for equality checks."""
    return json.loads(_canonical_json(scene_graph))


def scene_hash(scene_graph: Mapping[str, Any]) -> str:
    """Return a stable content hash for a Scene Graph payload."""
    digest = hashlib.sha256(_canonical_json(scene_graph).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _json_pointer(parts: Sequence[str]) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else ""


def _decode_pointer(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise JsonPatchError("JSON Pointer paths must be empty or start with '/'.")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def _array_index(segment: str, length: int, *, allow_end: bool = False) -> int:
    if not segment.isdigit():
        raise JsonPatchError(f"Array segment {segment!r} is not a non-negative index.")
    index = int(segment)
    upper = length if allow_end else length - 1
    if index < 0 or index > upper:
        raise JsonPatchError(f"Array index {index} is out of bounds for length {length}.")
    return index


def _parent_and_key(document: Any, parts: Sequence[str]) -> tuple[Any, str]:
    if not parts:
        raise JsonPatchError("Root replacement is not supported for scene history JSON Patch operations.")
    current = document
    for segment in parts[:-1]:
        if isinstance(current, list):
            current = current[_array_index(segment, len(current))]
        elif isinstance(current, dict):
            if segment not in current:
                raise JsonPatchError(f"Object key {segment!r} does not exist.")
            current = current[segment]
        else:
            raise JsonPatchError(f"Cannot traverse through {type(current).__name__}.")
    return current, parts[-1]


def _json_get(document: Any, parts: Sequence[str]) -> Any:
    current = document
    for segment in parts:
        if isinstance(current, list):
            current = current[_array_index(segment, len(current))]
        elif isinstance(current, dict):
            if segment not in current:
                raise JsonPatchError(f"Object key {segment!r} does not exist.")
            current = current[segment]
        else:
            raise JsonPatchError(f"Cannot traverse through {type(current).__name__}.")
    return current


def _json_add(document: Any, parts: Sequence[str], value: Any) -> None:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list):
        if key == "-":
            parent.append(value)
            return
        parent.insert(_array_index(key, len(parent), allow_end=True), value)
        return
    if isinstance(parent, dict):
        parent[key] = value
        return
    raise JsonPatchError(f"Cannot add into {type(parent).__name__}.")


def _json_replace(document: Any, parts: Sequence[str], value: Any) -> None:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list):
        parent[_array_index(key, len(parent))] = value
        return
    if isinstance(parent, dict):
        if key not in parent:
            raise JsonPatchError(f"Object key {key!r} does not exist.")
        parent[key] = value
        return
    raise JsonPatchError(f"Cannot replace inside {type(parent).__name__}.")


def _json_remove(document: Any, parts: Sequence[str]) -> Any:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list):
        return parent.pop(_array_index(key, len(parent)))
    if isinstance(parent, dict):
        if key not in parent:
            raise JsonPatchError(f"Object key {key!r} does not exist.")
        return parent.pop(key)
    raise JsonPatchError(f"Cannot remove from {type(parent).__name__}.")


def _concrete_add_path(document: Any, parts: Sequence[str]) -> list[str]:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list) and key == "-":
        return [*parts[:-1], str(len(parent))]
    return list(parts)


def _add_like_inverse(document: Any, parts: Sequence[str]) -> list[dict[str, Any]]:
    concrete = _concrete_add_path(document, parts)
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, dict) and key in parent:
        return [{"op": "replace", "path": _json_pointer(concrete), "value": copy.deepcopy(parent[key])}]
    return [{"op": "remove", "path": _json_pointer(concrete)}]


def _apply_json_operation_in_place(document: Any, operation: Mapping[str, Any]) -> None:
    op_name = operation.get("op")
    path = operation.get("path")
    if not isinstance(op_name, str) or not isinstance(path, str):
        raise JsonPatchError("JSON Patch operation requires string op and path fields.")
    parts = _decode_pointer(path)
    if op_name == "add":
        _json_add(document, parts, copy.deepcopy(operation.get("value")))
        return
    if op_name == "remove":
        _json_remove(document, parts)
        return
    if op_name == "replace":
        _json_replace(document, parts, copy.deepcopy(operation.get("value")))
        return
    if op_name == "copy":
        from_path = operation.get("from")
        if not isinstance(from_path, str):
            raise JsonPatchError("JSON Patch copy operation requires a string from field.")
        _json_add(document, parts, copy.deepcopy(_json_get(document, _decode_pointer(from_path))))
        return
    if op_name == "move":
        from_path = operation.get("from")
        if not isinstance(from_path, str):
            raise JsonPatchError("JSON Patch move operation requires a string from field.")
        value = _json_remove(document, _decode_pointer(from_path))
        _json_add(document, parts, value)
        return
    if op_name == "test":
        expected = operation.get("value")
        actual = _json_get(document, parts)
        if actual != expected:
            raise JsonPatchError(f"JSON Patch test failed at {path!r}.")
        return
    raise JsonPatchError(f"Unsupported JSON Patch operation {op_name!r}.")


def apply_json_patch_operations(scene_graph: Mapping[str, Any], operations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply basic JSON Patch operations to a Scene Graph copy."""
    updated = copy.deepcopy(dict(scene_graph))
    for operation in operations:
        _apply_json_operation_in_place(updated, operation)
    return updated


def _inverse_group_for_operation(document: Any, operation: Mapping[str, Any]) -> list[dict[str, Any]]:
    op_name = operation.get("op")
    path = operation.get("path")
    if not isinstance(op_name, str) or not isinstance(path, str):
        raise JsonPatchError("JSON Patch operation requires string op and path fields.")
    parts = _decode_pointer(path)

    if op_name == "add":
        return _add_like_inverse(document, parts)
    if op_name == "remove":
        return [{"op": "add", "path": path, "value": copy.deepcopy(_json_get(document, parts))}]
    if op_name == "replace":
        return [{"op": "replace", "path": path, "value": copy.deepcopy(_json_get(document, parts))}]
    if op_name == "copy":
        return _add_like_inverse(document, parts)
    if op_name == "test":
        return [{"op": "test", "path": path, "value": copy.deepcopy(operation.get("value"))}]
    if op_name == "move":
        from_path = operation.get("from")
        if not isinstance(from_path, str):
            raise JsonPatchError("JSON Patch move operation requires a string from field.")
        from_parts = _decode_pointer(from_path)
        source_value = copy.deepcopy(_json_get(document, from_parts))
        after_source_remove = copy.deepcopy(document)
        _json_remove(after_source_remove, from_parts)
        destination_parts = _concrete_add_path(after_source_remove, parts)
        destination_parent, destination_key = _parent_and_key(after_source_remove, parts)
        group: list[dict[str, Any]] = []
        if isinstance(destination_parent, list):
            group.append({"op": "remove", "path": _json_pointer(destination_parts)})
        elif isinstance(destination_parent, dict) and destination_key in destination_parent:
            group.append(
                {
                    "op": "replace",
                    "path": _json_pointer(destination_parts),
                    "value": copy.deepcopy(destination_parent[destination_key]),
                }
            )
        else:
            group.append({"op": "remove", "path": _json_pointer(destination_parts)})
        group.append({"op": "add", "path": from_path, "value": source_value})
        return group
    raise JsonPatchError(f"Unsupported JSON Patch operation {op_name!r}.")


def _inverse_operations(before_scene: Mapping[str, Any], forward_operations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    working = copy.deepcopy(dict(before_scene))
    inverse_groups: list[list[dict[str, Any]]] = []
    for operation in forward_operations:
        inverse_groups.append(_inverse_group_for_operation(working, operation))
        _apply_json_operation_in_place(working, operation)
    inverse: list[dict[str, Any]] = []
    for group in reversed(inverse_groups):
        inverse.extend(group)
    return inverse


def _scene_memory_event_remove_op(
    before_scene: Mapping[str, Any],
    after_scene: Mapping[str, Any],
    scene_memory_event: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if scene_memory_event is None:
        return None
    before_events = before_scene.get("memory_events")
    after_events = after_scene.get("memory_events")
    if not isinstance(before_events, list) or not isinstance(after_events, list):
        return None
    if len(after_events) != len(before_events) + 1:
        return None
    for index, event in enumerate(after_events):
        if event != scene_memory_event:
            continue
        if after_events[:index] + after_events[index + 1 :] == before_events:
            return {"op": "remove", "path": f"/memory_events/{index}"}
    return None


def _inverse_patch_id(forward_patch: Mapping[str, Any]) -> str:
    patch_id = forward_patch.get("patch_id")
    body = patch_id if isinstance(patch_id, str) else "patch_unknown"
    return f"patch_{clamp_id_body(f'inverse_{body}')}"


def build_inverse_scene_patch(
    before_scene: Mapping[str, Any],
    forward_patch: Mapping[str, Any],
    after_scene: Mapping[str, Any],
    *,
    scene_memory_event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic inverse patch payload for a successful patch."""
    operations = forward_patch.get("operations", [])
    if operations is None:
        operations = []
    if not isinstance(operations, list):
        raise SceneHistoryError("forward patch operations must be an array when present")
    inverse_operations = _inverse_operations(before_scene, [dict(operation) for operation in operations])
    memory_remove = _scene_memory_event_remove_op(before_scene, after_scene, scene_memory_event)
    if memory_remove is not None:
        inverse_operations.insert(0, memory_remove)
    scene_id = before_scene.get("scene_id")
    if not isinstance(scene_id, str):
        raise SceneHistoryError("Scene Graph scene_id must be a string to build inverse patch")
    forward_patch_id = forward_patch.get("patch_id", "patch_unknown")
    return {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": _inverse_patch_id(forward_patch),
        "scope": "scene",
        "target_id": scene_id,
        "instruction": f"Rollback inverse for {forward_patch_id}.",
        "preserve": [],
        "allowed_changes": list(_ALL_PATCH_CHANGE_CATEGORIES),
        "operations": inverse_operations,
    }


def create_scene_history(
    *,
    history_id: str | None = None,
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create an empty Scene History payload."""
    payload: dict[str, Any] = {
        "schema_version": SCENE_HISTORY_VERSION,
        "records": [copy.deepcopy(dict(record)) for record in records] if records is not None else [],
    }
    if history_id is not None:
        payload["history_id"] = history_id
    return payload


def create_scene_history_record(
    before_scene: Mapping[str, Any],
    forward_patch: Mapping[str, Any],
    patch_result: Any,
    *,
    forward_patch_path: str | None = None,
    timestamp: str = DETERMINISTIC_HISTORY_TIMESTAMP,
    validation_reports: Sequence[Mapping[str, Any]] | None = None,
    render_reports: Sequence[Mapping[str, Any]] | None = None,
    comparison_reports: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create one forward/inverse patch history record."""
    patch_event = getattr(patch_result, "patch_event", None)
    after_scene = getattr(patch_result, "scene_graph", None)
    scene_memory_event = getattr(patch_result, "scene_memory_event", None)
    if not isinstance(patch_event, Mapping) or not isinstance(after_scene, Mapping):
        raise SceneHistoryError("patch_result must expose patch_event and scene_graph mappings")
    event_id = patch_event.get("event_id")
    if not isinstance(event_id, str):
        raise SceneHistoryError("patch_result patch_event must include a string event_id")

    forward_ref: dict[str, Any] = {}
    if forward_patch_path is not None:
        forward_ref["path"] = str(forward_patch_path)
    else:
        forward_ref["payload"] = copy.deepcopy(dict(forward_patch))

    inverse_patch = build_inverse_scene_patch(
        before_scene,
        forward_patch,
        after_scene,
        scene_memory_event=scene_memory_event if isinstance(scene_memory_event, Mapping) else None,
    )
    return {
        "event_id": event_id,
        "forward_patch": forward_ref,
        "inverse_patch": {"payload": inverse_patch},
        "before_scene_hash": scene_hash(before_scene),
        "after_scene_hash": scene_hash(after_scene),
        "timestamp": timestamp,
        "validation_reports": [copy.deepcopy(dict(report)) for report in validation_reports or []],
        "render_reports": [copy.deepcopy(dict(report)) for report in render_reports or []],
        "comparison_reports": [copy.deepcopy(dict(report)) for report in comparison_reports or []],
    }


def append_scene_history_record(
    scene_history: Mapping[str, Any] | None,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Return Scene History with a record inserted or replaced by event_id."""
    if scene_history is None:
        updated = create_scene_history()
    else:
        updated = copy.deepcopy(dict(scene_history))
        updated.setdefault("schema_version", SCENE_HISTORY_VERSION)
        updated.setdefault("records", [])
    records = updated.get("records")
    if not isinstance(records, list):
        raise SceneHistoryError("Scene History records must be an array")
    record_copy = copy.deepcopy(dict(record))
    event_id = record_copy.get("event_id")
    replaced = False
    for index, existing in enumerate(records):
        if isinstance(existing, Mapping) and existing.get("event_id") == event_id:
            records[index] = record_copy
            replaced = True
            break
    if not replaced:
        records.append(record_copy)
    diagnostics = validate_scene_history_payload(updated)
    if diagnostics:
        codes = ", ".join(str(diagnostic.get("code", "unknown")) for diagnostic in diagnostics)
        raise SceneHistoryError(f"Scene History failed validation: {codes}")
    return updated


def validate_scene_history_payload(scene_history: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema diagnostics for a Scene History payload."""
    diagnostics = validate_contract(SCENE_HISTORY_CONTRACT, scene_history)
    if diagnostics:
        return diagnostics
    seen: dict[str, int] = {}
    duplicate_diagnostics: list[dict[str, Any]] = []
    for index, record in enumerate(scene_history.get("records", [])):
        if not isinstance(record, Mapping):
            continue
        event_id = record.get("event_id")
        if not isinstance(event_id, str):
            continue
        first = seen.get(event_id)
        if first is None:
            seen[event_id] = index
            continue
        duplicate_diagnostics.append(
            {
                "code": "SH1001",
                "name": "duplicate_scene_history_event",
                "severity": "error",
                "contract": SCENE_HISTORY_CONTRACT,
                "phase": "scene_history_semantics",
                "path": f"/records/{index}/event_id",
                "message": f"Duplicate Scene History event_id {event_id!r}; first seen at /records/{first}/event_id.",
                "details": {"event_id": event_id, "first_index": first},
            }
        )
    return duplicate_diagnostics


def find_scene_history_record(scene_history: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    """Return the history record matching an event id."""
    records = scene_history.get("records", [])
    if not isinstance(records, list):
        raise SceneHistoryError("Scene History records must be an array")
    for record in records:
        if isinstance(record, Mapping) and record.get("event_id") == event_id:
            return copy.deepcopy(dict(record))
    raise SceneHistoryError(f"Scene History event {event_id!r} was not found")


def branch_history(
    world_memory: Mapping[str, Any],
    branch: str,
    *,
    scene_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return branch-scoped World Memory events plus linked validation/render reports."""
    branch_event_ids: list[str] = []
    for branch_payload in world_memory.get("branches", []):
        if not isinstance(branch_payload, Mapping) or branch_payload.get("branch_id") != branch:
            continue
        raw_event_ids = branch_payload.get("event_ids", [])
        if isinstance(raw_event_ids, list):
            branch_event_ids = [event_id for event_id in raw_event_ids if isinstance(event_id, str)]
        break

    events_by_id = {
        event["event_id"]: event
        for event in world_memory.get("events", [])
        if isinstance(event, Mapping) and isinstance(event.get("event_id"), str)
    }
    selected_ids: list[str] = []
    for event_id in branch_event_ids:
        if event_id in events_by_id and event_id not in selected_ids:
            selected_ids.append(event_id)
    for event in world_memory.get("events", []):
        if not isinstance(event, Mapping):
            continue
        event_id = event.get("event_id")
        if event.get("branch_id") == branch and isinstance(event_id, str) and event_id not in selected_ids:
            selected_ids.append(event_id)

    records_by_id: dict[str, Mapping[str, Any]] = {}
    if scene_history is not None:
        records = scene_history.get("records", [])
        if isinstance(records, list):
            records_by_id = {
                record["event_id"]: record
                for record in records
                if isinstance(record, Mapping) and isinstance(record.get("event_id"), str)
            }

    linked_records = [copy.deepcopy(dict(records_by_id[event_id])) for event_id in selected_ids if event_id in records_by_id]
    validation_reports: list[dict[str, Any]] = []
    render_reports: list[dict[str, Any]] = []
    comparison_reports: list[dict[str, Any]] = []
    for record in linked_records:
        raw_validation = record.get("validation_reports", [])
        if isinstance(raw_validation, list):
            validation_reports.extend(copy.deepcopy(report) for report in raw_validation if isinstance(report, Mapping))
        raw_render = record.get("render_reports", [])
        if isinstance(raw_render, list):
            render_reports.extend(copy.deepcopy(report) for report in raw_render if isinstance(report, Mapping))
        raw_comparison = record.get("comparison_reports", [])
        if isinstance(raw_comparison, list):
            comparison_reports.extend(copy.deepcopy(report) for report in raw_comparison if isinstance(report, Mapping))

    return {
        "schema_version": "lathe.scene_branch_history.v1",
        "branch": branch,
        "event_ids": selected_ids,
        "events": [copy.deepcopy(dict(events_by_id[event_id])) for event_id in selected_ids],
        "history_records": linked_records,
        "validation_reports": validation_reports,
        "render_reports": render_reports,
        "comparison_reports": comparison_reports,
    }


__all__ = [
    "DETERMINISTIC_HISTORY_TIMESTAMP",
    "SCENE_HISTORY_CONTRACT",
    "SCENE_HISTORY_SCHEMA_FILENAME",
    "SCENE_HISTORY_VERSION",
    "JsonPatchError",
    "SceneHistoryError",
    "append_scene_history_record",
    "apply_json_patch_operations",
    "branch_history",
    "build_inverse_scene_patch",
    "create_scene_history",
    "create_scene_history_record",
    "find_scene_history_record",
    "normalized_scene_graph",
    "scene_hash",
    "validate_scene_history_payload",
]
