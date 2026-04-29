"""Apply continuity-aware Scene Patch payloads to Scene Graph mappings."""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .ids import clamp_id_body, is_scene_entity_id, is_snake_id

SCENE_PATCH_PHASE = "scene_patch_semantics"
SCENE_PATCH_CONTRACT = "scene_patch"

SCENE_PATCH_SCOPES: tuple[str, ...] = (
    "asset",
    "object",
    "region",
    "scene",
    "camera",
    "light",
    "curiosity_anchor",
    "hidden_state",
)

_TARGET_COLLECTIONS: dict[str, tuple[str, str]] = {
    "object": ("objects", "object_id"),
    "region": ("regions", "region_id"),
    "camera": ("cameras", "camera_id"),
    "light": ("lights", "light_id"),
    "curiosity_anchor": ("curiosity_anchors", "anchor_id"),
    "hidden_state": ("hidden_state", "hidden_id"),
}

_ENTITY_COLLECTIONS: dict[str, str] = {
    "regions": "region_id",
    "objects": "object_id",
    "lights": "light_id",
    "cameras": "camera_id",
    "curiosity_anchors": "anchor_id",
    "hidden_state": "hidden_id",
    "materials": "material_id",
    "relationships": "relationship_id",
}

_SCENE_REF_PREFIXES = ("object", "region", "camera", "light", "curiosity", "hidden")
_ASSET_FIELDS = ("lathe_asset", "source_family", "source_kit", "variant")

_MISSING = object()


@dataclass(frozen=True)
class ScenePatchResult:
    """Result returned by :func:`apply_scene_patch`."""

    scene_graph: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    patch_event: dict[str, Any]
    scene_memory_event: dict[str, Any] | None
    applied_operations: list[dict[str, Any]] = field(default_factory=list)
    rejected_operations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _PatchTarget:
    scope: str
    target_id: str
    collection: str | None
    index: int | None
    id_field: str | None
    affected_ids: tuple[str, ...]


@dataclass(frozen=True)
class _TargetItem:
    entity_id: str
    pointer_parts: tuple[object, ...]
    item: Mapping[str, Any]


class _PatchPointerError(ValueError):
    """Internal JSON Pointer failure."""


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _decode_pointer(pointer: str) -> list[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise _PatchPointerError("JSON Pointer paths must start with '/'.")
    if pointer == "":
        return []
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def _diag(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": SCENE_PATCH_CONTRACT,
        "phase": SCENE_PATCH_PHASE,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field_name: str) -> str | None:
    value = item.get(field_name)
    return value if isinstance(value, str) else None


def _entity_id_locations(scene_graph: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    locations: dict[str, tuple[str, ...]] = {}
    scene_id = scene_graph.get("scene_id")
    if isinstance(scene_id, str):
        locations[scene_id] = (_json_pointer("scene_id"),)
    for collection, field_name in _ENTITY_COLLECTIONS.items():
        for index, item in _items(scene_graph, collection):
            entity_id = _string_field(item, field_name)
            if entity_id is None:
                continue
            path = _json_pointer(collection, index, field_name)
            locations.setdefault(entity_id, tuple())
            locations[entity_id] = (*locations[entity_id], path)
    return locations


def _scene_ref_id(value: str) -> bool:
    return any(is_scene_entity_id(prefix, value) for prefix in _SCENE_REF_PREFIXES)


def _world_memory_entity_ref(value: str) -> bool:
    return is_snake_id(value) or any(
        is_scene_entity_id(prefix, value)
        for prefix in ("object", "region", "relationship", "material", "light", "camera", "curiosity", "hidden")
    )


def _unique_ids(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _resolve_patch_target(scene_graph: Mapping[str, Any], patch: Mapping[str, Any]) -> tuple[_PatchTarget | None, list[dict[str, Any]]]:
    scope = patch.get("scope")
    target_id = patch.get("target_id")
    if not isinstance(scope, str) or scope not in SCENE_PATCH_SCOPES:
        return None, [
            _diag(
                "SP1500",
                "unsupported_patch_scope",
                "/scope",
                f"Unsupported Scene Patch scope {scope!r}.",
                details={"scope": scope, "supported": list(SCENE_PATCH_SCOPES)},
            )
        ]
    if not isinstance(target_id, str):
        return None, [
            _diag("SP1503", "invalid_patch_operation", "/target_id", "Scene Patch target_id must be a string.")
        ]

    if scope == "scene":
        scene_id = scene_graph.get("scene_id")
        if scene_id == target_id:
            return _PatchTarget(scope, target_id, None, None, None, (target_id,)), []
        return None, [
            _diag(
                "SP1501",
                "patch_target_missing",
                "/target_id",
                f"Scene Patch target_id {target_id!r} does not match scene_id {scene_id!r}.",
                details={"scope": scope, "target_id": target_id, "scene_id": scene_id},
            )
        ]

    if scope == "asset":
        affected: list[str] = []
        for _index, item in _items(scene_graph, "objects"):
            if any(item.get(field_name) == target_id for field_name in _ASSET_FIELDS):
                object_id = _string_field(item, "object_id")
                if object_id is not None:
                    affected.append(object_id)
        if affected:
            return _PatchTarget(scope, target_id, "objects", None, None, tuple(affected)), []
        return None, [
            _diag(
                "SP1501",
                "patch_target_missing",
                "/target_id",
                f"Scene Patch asset target {target_id!r} is not referenced by any object asset field.",
                details={"scope": scope, "target_id": target_id, "asset_fields": list(_ASSET_FIELDS)},
            )
        ]

    collection, field_name = _TARGET_COLLECTIONS[scope]
    for index, item in _items(scene_graph, collection):
        if item.get(field_name) == target_id:
            return _PatchTarget(scope, target_id, collection, index, field_name, (target_id,)), []
    return None, [
        _diag(
            "SP1501",
            "patch_target_missing",
            "/target_id",
            f"Scene Patch {scope} target {target_id!r} was not found.",
            details={"scope": scope, "target_id": target_id, "collection": collection},
        )
    ]


def _operation_categories(parts: Sequence[str]) -> set[str]:
    if not parts:
        return {"metadata"}
    top = parts[0]
    if top == "objects":
        if len(parts) <= 2:
            return {"objects", "props"}
        field_name = parts[2]
        if field_name == "transform":
            if len(parts) >= 4 and parts[3] == "scale":
                return {"transforms", "scale"}
            return {"transforms"}
        if field_name in {"lathe_asset", "source_family", "source_kit", "variant"}:
            return {"assets"}
        if field_name == "material_bindings":
            return {"materials"}
        if field_name == "semantic_tags":
            return {"style", "metadata"}
        if field_name == "state":
            return {"state"}
        if field_name == "affordances":
            return {"affordances"}
        if field_name == "region":
            return {"layout", "objects"}
        if field_name == "provenance":
            return {"metadata"}
        return {"objects", "metadata"}
    if top == "regions":
        if len(parts) >= 3 and parts[2] in {"mood", "semantic_tags"}:
            return {"style", "metadata"}
        return {"layout", "metadata"}
    if top == "layout":
        return {"layout"}
    if top == "style_bible":
        return {"style"}
    if top == "materials":
        return {"materials"}
    if top == "lights":
        return {"lighting"}
    if top == "cameras":
        return {"cameras"}
    if top == "relationships":
        return {"relationships"}
    if top == "curiosity_anchors":
        return {"curiosity_anchors"}
    if top == "hidden_state":
        return {"hidden_state"}
    if top in {"prompt", "version", "brief_id", "exports", "build_artifacts", "memory_events"}:
        return {"metadata"}
    return {"metadata"}


def _operation_change_parts(operation: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    op_name = operation.get("op")
    paths: list[tuple[str, list[str]]] = []
    path = operation.get("path")
    if isinstance(path, str):
        paths.append(("path", _decode_pointer(path)))
    if op_name in {"move", "copy"}:
        from_path = operation.get("from")
        if isinstance(from_path, str):
            paths.append(("from", _decode_pointer(from_path)))
    return paths


def _collection_item(scene_graph: Mapping[str, Any], collection: str, index_part: str) -> Mapping[str, Any] | None:
    if not index_part.isdigit():
        return None
    index = int(index_part)
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list) or index >= len(raw):
        return None
    item = raw[index]
    return item if isinstance(item, Mapping) else None


def _target_object_materials(scene_graph: Mapping[str, Any], target_id: str) -> set[str]:
    for _index, item in _items(scene_graph, "objects"):
        if item.get("object_id") != target_id:
            continue
        bindings = item.get("material_bindings", [])
        if not isinstance(bindings, list):
            return set()
        return {
            binding["material"]
            for binding in bindings
            if isinstance(binding, Mapping) and isinstance(binding.get("material"), str)
        }
    return set()


def _path_matches_scope(parts: Sequence[str], target: _PatchTarget, scene_graph: Mapping[str, Any], operation: Mapping[str, Any]) -> bool:
    if target.scope == "scene":
        return True
    if not parts:
        return False
    top = parts[0]
    if target.collection is not None and top == target.collection and len(parts) >= 2:
        return parts[1] == str(target.index)
    if target.scope == "asset" and top == "objects" and len(parts) >= 2:
        if parts[1] == "-" and operation.get("op") == "add":
            value = operation.get("value")
            return isinstance(value, Mapping) and any(value.get(field_name) == target.target_id for field_name in _ASSET_FIELDS)
        item = _collection_item(scene_graph, "objects", parts[1])
        return item is not None and any(item.get(field_name) == target.target_id for field_name in _ASSET_FIELDS)
    if target.scope == "object":
        if top == "materials" and len(parts) >= 2:
            item = _collection_item(scene_graph, "materials", parts[1])
            material_id = _string_field(item, "material_id") if item is not None else None
            return material_id in _target_object_materials(scene_graph, target.target_id)
        if top in {"lights", "cameras"} and len(parts) >= 2:
            item = _collection_item(scene_graph, top, parts[1])
            return item is not None and item.get("target") == target.target_id
        if top in {"curiosity_anchors", "hidden_state"} and len(parts) >= 2:
            item = _collection_item(scene_graph, top, parts[1])
            return item is not None and item.get("attached_to") == target.target_id
        if top == "relationships" and len(parts) >= 2:
            item = _collection_item(scene_graph, "relationships", parts[1])
            return item is not None and (item.get("from") == target.target_id or item.get("to") == target.target_id)
    if target.scope == "region":
        if top == "layout":
            return True
        if top == "objects" and len(parts) >= 2:
            item = _collection_item(scene_graph, "objects", parts[1])
            return item is not None and item.get("region") == target.target_id
    return False


def _has_allowed_changes(operation: Mapping[str, Any], patch: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    if operation.get("op") == "test":
        return True, []
    allowed = set(patch.get("allowed_changes", []))
    diagnostics: list[dict[str, Any]] = []
    try:
        change_parts = _operation_change_parts(operation)
    except _PatchPointerError as exc:
        return False, [
            _diag("SP1503", "invalid_patch_operation", "/operations", str(exc), details={"operation": dict(operation)})
        ]
    for role, parts in change_parts:
        categories = _operation_categories(parts)
        if categories.isdisjoint(allowed):
            path = operation.get("from") if role == "from" else operation.get("path")
            diagnostics.append(
                _diag(
                    "SP1504",
                    "patch_change_not_allowed",
                    "/operations",
                    f"Patch operation changes {sorted(categories)} but allowed_changes is {sorted(allowed)}.",
                    details={
                        "op": operation.get("op"),
                        "path": path,
                        "path_role": role,
                        "change_categories": sorted(categories),
                        "allowed_changes": sorted(allowed),
                    },
                )
            )
    return not diagnostics, diagnostics


def _scope_diagnostics(
    operation: Mapping[str, Any],
    target: _PatchTarget,
    scene_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    paths = [("path", operation.get("path"))]
    if operation.get("op") in {"move", "copy"}:
        paths.append(("from", operation.get("from")))
    for role, raw_path in paths:
        if not isinstance(raw_path, str):
            continue
        parts = _decode_pointer(raw_path)
        if _path_matches_scope(parts, target, scene_graph, operation):
            continue
        diagnostics.append(
            _diag(
                "SP1508",
                "patch_operation_scope_mismatch",
                "/operations",
                f"Patch operation {role} {raw_path!r} is outside {target.scope} target {target.target_id!r}.",
                details={
                    "op": operation.get("op"),
                    "path": raw_path,
                    "path_role": role,
                    "scope": target.scope,
                    "target_id": target.target_id,
                },
            )
        )
    return diagnostics


def _array_index(segment: str, length: int, *, allow_end: bool = False) -> int:
    if not segment.isdigit():
        raise _PatchPointerError(f"Array segment {segment!r} is not a non-negative index.")
    index = int(segment)
    upper = length if allow_end else length - 1
    if index < 0 or index > upper:
        raise _PatchPointerError(f"Array index {index} is out of bounds for length {length}.")
    return index


def _parent_and_key(document: Any, parts: Sequence[str]) -> tuple[Any, str]:
    if not parts:
        raise _PatchPointerError("Scene Patch operations cannot replace the Scene Graph root.")
    current = document
    for segment in parts[:-1]:
        if isinstance(current, list):
            current = current[_array_index(segment, len(current))]
        elif isinstance(current, dict):
            if segment not in current:
                raise _PatchPointerError(f"Object key {segment!r} does not exist.")
            current = current[segment]
        else:
            raise _PatchPointerError(f"Cannot traverse through {type(current).__name__}.")
    return current, parts[-1]


def _json_get(document: Any, parts: Sequence[str]) -> Any:
    current = document
    for segment in parts:
        if isinstance(current, list):
            current = current[_array_index(segment, len(current))]
        elif isinstance(current, dict):
            if segment not in current:
                raise _PatchPointerError(f"Object key {segment!r} does not exist.")
            current = current[segment]
        else:
            raise _PatchPointerError(f"Cannot traverse through {type(current).__name__}.")
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
    raise _PatchPointerError(f"Cannot add into {type(parent).__name__}.")


def _json_replace(document: Any, parts: Sequence[str], value: Any) -> None:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list):
        parent[_array_index(key, len(parent))] = value
        return
    if isinstance(parent, dict):
        if key not in parent:
            raise _PatchPointerError(f"Object key {key!r} does not exist.")
        parent[key] = value
        return
    raise _PatchPointerError(f"Cannot replace inside {type(parent).__name__}.")


def _json_remove(document: Any, parts: Sequence[str]) -> Any:
    parent, key = _parent_and_key(document, parts)
    if isinstance(parent, list):
        return parent.pop(_array_index(key, len(parent)))
    if isinstance(parent, dict):
        if key not in parent:
            raise _PatchPointerError(f"Object key {key!r} does not exist.")
        return parent.pop(key)
    raise _PatchPointerError(f"Cannot remove from {type(parent).__name__}.")


def _parts_start_with(parts: Sequence[str], prefix: Sequence[str]) -> bool:
    return len(parts) > len(prefix) and list(parts[: len(prefix)]) == list(prefix)


def _apply_json_operation(
    scene_graph: Mapping[str, Any],
    operation: Mapping[str, Any],
    operation_index: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    op_name = operation.get("op")
    path = operation.get("path")
    if op_name not in {"add", "remove", "replace", "move", "copy", "test"} or not isinstance(path, str):
        return dict(scene_graph), [
            _diag(
                "SP1503",
                "invalid_patch_operation",
                _json_pointer("operations", operation_index),
                "Scene Patch operation must contain a supported op and JSON Pointer path.",
                details={"operation": dict(operation)},
            )
        ]

    try:
        path_parts = _decode_pointer(path)
        document = copy.deepcopy(dict(scene_graph))
        if op_name in {"add", "replace", "test"} and "value" not in operation:
            raise _PatchPointerError(f"{op_name!r} operation requires a value.")
        if op_name == "add":
            _json_add(document, path_parts, copy.deepcopy(operation["value"]))
        elif op_name == "replace":
            _json_replace(document, path_parts, copy.deepcopy(operation["value"]))
        elif op_name == "remove":
            _json_remove(document, path_parts)
        elif op_name == "test":
            actual = _json_get(document, path_parts)
            expected = operation["value"]
            if actual != expected:
                return document, [
                    _diag(
                        "SP1507",
                        "patch_test_failed",
                        _json_pointer("operations", operation_index, "path"),
                        f"Scene Patch test operation failed at {path!r}.",
                        details={"path": path, "expected": expected, "actual": actual},
                    )
                ]
        elif op_name in {"move", "copy"}:
            from_path = operation.get("from")
            if not isinstance(from_path, str):
                raise _PatchPointerError(f"{op_name!r} operation requires a from path.")
            from_parts = _decode_pointer(from_path)
            if op_name == "move" and _parts_start_with(path_parts, from_parts):
                raise _PatchPointerError("Cannot move a value into one of its own descendants.")
            value = copy.deepcopy(_json_get(document, from_parts))
            if op_name == "move":
                value = _json_remove(document, from_parts)
            _json_add(document, path_parts, copy.deepcopy(value))
    except _PatchPointerError as exc:
        return dict(scene_graph), [
            _diag(
                "SP1503",
                "invalid_patch_operation",
                _json_pointer("operations", operation_index, "path"),
                str(exc),
                details={"operation": dict(operation)},
            )
        ]
    return document, []


def _target_items(scene_graph: Mapping[str, Any], target: _PatchTarget) -> list[_TargetItem]:
    if target.scope == "scene":
        return [_TargetItem(target.target_id, tuple(), scene_graph)]
    if target.scope == "asset":
        items: list[_TargetItem] = []
        for index, item in _items(scene_graph, "objects"):
            object_id = _string_field(item, "object_id")
            if object_id is not None and any(item.get(field_name) == target.target_id for field_name in _ASSET_FIELDS):
                items.append(_TargetItem(object_id, ("objects", index), item))
        return items
    if target.collection is None or target.id_field is None:
        return []
    for index, item in _items(scene_graph, target.collection):
        entity_id = _string_field(item, target.id_field)
        if entity_id == target.target_id:
            return [_TargetItem(entity_id, (target.collection, index), item)]
    return []


def _find_item_by_id(scene_graph: Mapping[str, Any], entity_id: str) -> _TargetItem | None:
    if scene_graph.get("scene_id") == entity_id:
        return _TargetItem(entity_id, tuple(), scene_graph)
    for collection, field_name in _ENTITY_COLLECTIONS.items():
        for index, item in _items(scene_graph, collection):
            if item.get(field_name) == entity_id:
                return _TargetItem(entity_id, (collection, index), item)
    return None


def _nested_value(item: Mapping[str, Any], parts: Sequence[str]) -> Any:
    current: Any = item
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _find_key_paths(value: Any, key: str, prefix: tuple[object, ...] = tuple()) -> list[tuple[tuple[object, ...], Any]]:
    found: list[tuple[tuple[object, ...], Any]] = []
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            child_path = (*prefix, child_key)
            if child_key == key:
                found.append((child_path, child_value))
            found.extend(_find_key_paths(child_value, key, child_path))
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            found.extend(_find_key_paths(child_value, key, (*prefix, index)))
    return found


def _preserved_ids(patch: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> set[str]:
    preserved: set[str] = set()
    continuity = patch.get("continuity")
    if isinstance(continuity, Mapping):
        raw_ids = continuity.get("preserved_ids", [])
        if isinstance(raw_ids, list):
            preserved.update(value for value in raw_ids if isinstance(value, str))
    id_locations = _entity_id_locations(scene_graph)
    raw_preserve = patch.get("preserve", [])
    if isinstance(raw_preserve, list):
        preserved.update(value for value in raw_preserve if isinstance(value, str) and value in id_locations)
    return preserved


def _preserved_field_diagnostics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    patch: Mapping[str, Any],
    target: _PatchTarget,
    operation_index: int,
) -> list[dict[str, Any]]:
    raw_preserve = patch.get("preserve", [])
    if not isinstance(raw_preserve, list):
        return []
    diagnostics: list[dict[str, Any]] = []
    before_items = _target_items(before, target)
    for token in raw_preserve:
        if not isinstance(token, str) or not token or token in _entity_id_locations(before):
            continue
        if token.startswith("/"):
            try:
                before_value = _json_get(before, _decode_pointer(token))
            except _PatchPointerError:
                continue
            try:
                after_value = _json_get(after, _decode_pointer(token))
            except _PatchPointerError:
                diagnostics.append(
                    _diag(
                        "SP1505",
                        "patch_preserve_violation",
                        _json_pointer("operations", operation_index),
                        f"Patch operation removed preserved path {token!r}.",
                        details={"preserve": token, "path": token},
                    )
                )
                continue
            if before_value != after_value:
                diagnostics.append(
                    _diag(
                        "SP1505",
                        "patch_preserve_violation",
                        _json_pointer("operations", operation_index),
                        f"Patch operation altered preserved path {token!r}.",
                        details={"preserve": token, "path": token},
                    )
                )
            continue

        token_parts = tuple(token.split("."))
        for before_item in before_items:
            after_item = _find_item_by_id(after, before_item.entity_id)
            if after_item is None:
                continue
            before_value = _nested_value(before_item.item, token_parts)
            after_value = _nested_value(after_item.item, token_parts)
            if before_value is not _MISSING:
                if before_value != after_value:
                    diagnostics.append(
                        _diag(
                            "SP1505",
                            "patch_preserve_violation",
                            _json_pointer("operations", operation_index),
                            f"Patch operation altered preserved field {token!r}.",
                            details={
                                "preserve": token,
                                "target_id": before_item.entity_id,
                                "path": _json_pointer(*after_item.pointer_parts, *token_parts),
                            },
                        )
                    )
                continue
            if "." in token:
                continue
            for relative_path, before_nested_value in _find_key_paths(before_item.item, token):
                after_nested_value = _nested_value(after_item.item, [str(part) for part in relative_path])
                if before_nested_value == after_nested_value:
                    continue
                diagnostics.append(
                    _diag(
                        "SP1505",
                        "patch_preserve_violation",
                        _json_pointer("operations", operation_index),
                        f"Patch operation altered preserved field {token!r}.",
                        details={
                            "preserve": token,
                            "target_id": before_item.entity_id,
                            "path": _json_pointer(*after_item.pointer_parts, *relative_path),
                        },
                    )
                )
    return diagnostics


def _object_transforms(scene_graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    transforms: dict[str, Mapping[str, Any]] = {}
    for _index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        transform = item.get("transform")
        if object_id is not None and isinstance(transform, Mapping):
            transforms[object_id] = transform
    return transforms


def _component_allowed(component: str, allowed_changes: set[str]) -> bool:
    return "transforms" in allowed_changes or (component == "scale" and "scale" in allowed_changes)


def _transform_diagnostics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    patch: Mapping[str, Any],
    operation_index: int,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    allowed_changes = set(patch.get("allowed_changes", []))
    after_transforms = _object_transforms(after)
    for object_id, before_transform in _object_transforms(before).items():
        after_transform = after_transforms.get(object_id)
        if after_transform is None or before_transform == after_transform:
            continue
        changed = [
            component
            for component in ("position", "rotation", "scale")
            if before_transform.get(component) != after_transform.get(component)
        ]
        forbidden = [component for component in changed if not _component_allowed(component, allowed_changes)]
        if not forbidden:
            continue
        diagnostics.append(
            _diag(
                "SP1506",
                "patch_continuity_violation",
                _json_pointer("operations", operation_index),
                f"Patch operation altered object transform components without explicit allowance: {forbidden}.",
                details={"object_id": object_id, "components": forbidden},
            )
        )
    return diagnostics


def _stable_id_diagnostics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    patch: Mapping[str, Any],
    operation_index: int,
) -> list[dict[str, Any]]:
    continuity = patch.get("continuity")
    free_revision = isinstance(continuity, Mapping) and continuity.get("mode") == "free_revision"
    before_ids = _entity_id_locations(before)
    after_ids = _entity_id_locations(after)
    diagnostics: list[dict[str, Any]] = []
    if not free_revision:
        for entity_id, paths in sorted(before_ids.items()):
            if entity_id in after_ids:
                continue
            diagnostics.append(
                _diag(
                    "SP1506",
                    "patch_continuity_violation",
                    _json_pointer("operations", operation_index),
                    f"Patch operation removed or changed stable ID {entity_id!r}.",
                    details={"entity_id": entity_id, "previous_paths": list(paths)},
                )
            )
    for entity_id in sorted(_preserved_ids(patch, before)):
        if entity_id in after_ids:
            continue
        diagnostics.append(
            _diag(
                "SP1505",
                "patch_preserve_violation",
                _json_pointer("operations", operation_index),
                f"Patch operation removed preserved ID {entity_id!r}.",
                details={"entity_id": entity_id, "preserved_ids": sorted(_preserved_ids(patch, before))},
            )
        )
    return diagnostics


def _continuity_diagnostics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    patch: Mapping[str, Any],
    target: _PatchTarget,
    operation_index: int,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_stable_id_diagnostics(before, after, patch, operation_index))
    diagnostics.extend(_transform_diagnostics(before, after, patch, operation_index))
    diagnostics.extend(_preserved_field_diagnostics(before, after, patch, target, operation_index))
    return diagnostics


def _event_id_for_patch(patch_id: str) -> str:
    return f"mem_{clamp_id_body(patch_id)}"


def _affected_ids_for_patch(
    patch: Mapping[str, Any],
    target: _PatchTarget | None,
    scene_graph: Mapping[str, Any],
) -> list[str]:
    affected: list[str] = []
    target_id = patch.get("target_id")
    if isinstance(target_id, str):
        affected.append(target_id)
    if target is not None:
        affected.extend(target.affected_ids)
    for preserved_id in _preserved_ids(patch, scene_graph):
        affected.append(preserved_id)
    return _unique_ids([entity_id for entity_id in affected if _world_memory_entity_ref(entity_id)])


def _branch_name(patch: Mapping[str, Any]) -> str | None:
    continuity = patch.get("continuity")
    if not isinstance(continuity, Mapping):
        return None
    branch_name = continuity.get("branch_name")
    return branch_name if isinstance(branch_name, str) else None


def _patch_event(
    patch: Mapping[str, Any],
    target: _PatchTarget | None,
    scene_graph: Mapping[str, Any],
    *,
    status: str,
    applied_count: int,
    rejected_count: int,
) -> dict[str, Any]:
    patch_id = str(patch.get("patch_id", "patch_unknown"))
    scope = str(patch.get("scope", "scene"))
    world_scope = "object" if scope == "asset" else scope
    instruction = str(patch.get("instruction", "Scene patch requested."))
    event: dict[str, Any] = {
        "event_id": _event_id_for_patch(patch_id),
        "type": "patch",
        "scope": world_scope,
        "text": f"Scene patch {patch_id} {status}: {instruction}",
        "affected_ids": _affected_ids_for_patch(patch, target, scene_graph),
        "visibility": "private",
        "patch_id": patch_id,
        "source": f"scene_patch:{patch_id}",
        "metadata": {
            "status": status,
            "scene_patch_scope": scope,
            "target_id": str(patch.get("target_id", "")),
            "operation_count": len(patch.get("operations", [])) if isinstance(patch.get("operations"), list) else 0,
            "applied_operation_count": applied_count,
            "rejected_operation_count": rejected_count,
        },
    }
    branch = _branch_name(patch)
    if branch is not None:
        event["branch_id"] = branch
    if not event["affected_ids"]:
        event.pop("affected_ids")
    return event


def _scene_memory_event(patch: Mapping[str, Any], patch_event: Mapping[str, Any]) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_id": patch_event["event_id"],
        "type": "patch",
        "text": str(patch_event["text"]),
        "source": str(patch_event["source"]),
    }
    affected_ids = [
        entity_id
        for entity_id in patch_event.get("affected_ids", [])
        if isinstance(entity_id, str) and _scene_ref_id(entity_id)
    ]
    if affected_ids:
        event["affected_ids"] = _unique_ids(affected_ids)
    return event


def _append_scene_memory_event(
    scene_graph: Mapping[str, Any],
    event: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    updated = copy.deepcopy(dict(scene_graph))
    events = updated.get("memory_events")
    if not isinstance(events, list):
        return updated, [
            _diag(
                "SP1503",
                "invalid_patch_operation",
                "/memory_events",
                "Scene Graph memory_events must be an array before recording a patch event.",
            )
        ], False
    event_id = event.get("event_id")
    for index, existing in enumerate(events):
        if not isinstance(existing, Mapping) or existing.get("event_id") != event_id:
            continue
        if dict(existing) == dict(event):
            return updated, [], False
        return updated, [
            _diag(
                "SP1509",
                "patch_event_conflict",
                _json_pointer("memory_events", index, "event_id"),
                f"Scene Graph already contains a different memory event {event_id!r}.",
                details={"event_id": event_id},
            )
        ], False
    events.append(copy.deepcopy(dict(event)))
    return updated, [], True


def apply_scene_patch(scene_graph: Mapping[str, Any], patch: Mapping[str, Any]) -> ScenePatchResult:
    """Return a Scene Graph copy with a schema-valid Scene Patch applied.

    The helper does not invoke mesh, Blender, provider, or scene-source parsing
    code. It applies explicit JSON Patch operations when present, records
    semantic-only instructions as patch memory, and rejects operations that
    violate preserve or continuity constraints.
    """
    working: dict[str, Any] = copy.deepcopy(dict(scene_graph))
    diagnostics: list[dict[str, Any]] = []
    applied_operations: list[dict[str, Any]] = []
    rejected_operations: list[dict[str, Any]] = []

    target, target_diagnostics = _resolve_patch_target(working, patch)
    diagnostics.extend(target_diagnostics)
    operations = patch.get("operations", [])
    if operations is None:
        operations = []
    if not isinstance(operations, list):
        operations = []

    if target is not None:
        for operation_index, raw_operation in enumerate(operations):
            if not isinstance(raw_operation, Mapping):
                operation_diagnostics = [
                    _diag(
                        "SP1503",
                        "invalid_patch_operation",
                        _json_pointer("operations", operation_index),
                        "Scene Patch operation entries must be JSON objects.",
                    )
                ]
                diagnostics.extend(operation_diagnostics)
                rejected_operations.append({"index": operation_index, "diagnostics": operation_diagnostics})
                continue
            operation = dict(raw_operation)
            operation_diagnostics: list[dict[str, Any]] = []
            try:
                allowed, allowed_diagnostics = _has_allowed_changes(operation, patch)
                operation_diagnostics.extend(allowed_diagnostics)
                operation_diagnostics.extend(_scope_diagnostics(operation, target, working))
            except _PatchPointerError as exc:
                operation_diagnostics.append(
                    _diag(
                        "SP1503",
                        "invalid_patch_operation",
                        _json_pointer("operations", operation_index, "path"),
                        str(exc),
                        details={"operation": operation},
                    )
                )
                allowed = False
            if operation_diagnostics or not allowed:
                diagnostics.extend(operation_diagnostics)
                rejected_operations.append({"index": operation_index, "operation": operation, "diagnostics": operation_diagnostics})
                continue

            trial, operation_diagnostics = _apply_json_operation(working, operation, operation_index)
            if not operation_diagnostics:
                operation_diagnostics = _continuity_diagnostics(working, trial, patch, target, operation_index)
            if operation_diagnostics:
                diagnostics.extend(operation_diagnostics)
                rejected_operations.append({"index": operation_index, "operation": operation, "diagnostics": operation_diagnostics})
                continue
            working = trial
            applied_operations.append({"index": operation_index, "operation": operation})

    status = "rejected" if diagnostics else "applied"
    patch_event = _patch_event(
        patch,
        target,
        working,
        status=status,
        applied_count=len(applied_operations),
        rejected_count=len(rejected_operations),
    )
    scene_event = _scene_memory_event(patch, patch_event)
    if not diagnostics:
        working, append_diagnostics, appended = _append_scene_memory_event(working, scene_event)
        diagnostics.extend(append_diagnostics)
        if not appended and append_diagnostics:
            status = "rejected"
            patch_event = _patch_event(
                patch,
                target,
                working,
                status=status,
                applied_count=len(applied_operations),
                rejected_count=len(rejected_operations),
            )
            scene_event = None
    else:
        scene_event = None

    return ScenePatchResult(
        scene_graph=working,
        diagnostics=diagnostics,
        patch_event=patch_event,
        scene_memory_event=scene_event,
        applied_operations=applied_operations,
        rejected_operations=rejected_operations,
    )


__all__ = [
    "SCENE_PATCH_SCOPES",
    "ScenePatchResult",
    "apply_scene_patch",
]
