"""Pure Scene Graph branch, diff, and merge helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .ids import clamp_id_body, is_snake_id, snake_id

SCENE_BRANCH_VERSION = "lathe.scene_branch.v1"
SCENE_BRANCH_SCHEMA_FILENAME = "scene_branch.schema.json"
SCENE_DIFF_VERSION = "lathe.scene_diff.v1"
SCENE_DIFF_SCHEMA_FILENAME = "scene_diff.schema.json"

_SCENE_BRANCH_CONTRACT = "scene_branch"
_SCENE_DIFF_CONTRACT = "scene_diff"
_SCENE_MERGE_CONTRACT = "scene_merge"

_ENTITY_COLLECTIONS: dict[str, str] = {
    "regions": "region_id",
    "materials": "material_id",
    "objects": "object_id",
    "relationships": "relationship_id",
    "lights": "light_id",
    "cameras": "camera_id",
    "curiosity_anchors": "anchor_id",
    "hidden_state": "hidden_id",
}

_ENTITY_TYPE_BY_COLLECTION: dict[str, str] = {
    "regions": "region",
    "materials": "material",
    "objects": "object",
    "relationships": "relationship",
    "lights": "light",
    "cameras": "camera",
    "curiosity_anchors": "curiosity_anchor",
    "hidden_state": "hidden_state",
}

_MERGE_COLLECTION_ORDER: tuple[str, ...] = (
    "regions",
    "materials",
    "objects",
    "relationships",
    "lights",
    "cameras",
    "curiosity_anchors",
    "hidden_state",
)

_TOP_LEVEL_ENTITY_COLLECTIONS = set(_ENTITY_COLLECTIONS)
_OBJECT_MERGE_FIELDS = {"transform", "material_bindings", "state"}
_MISSING = object()


@dataclass(frozen=True)
class SceneMergeResult:
    """Result returned by :func:`merge_scene_graphs`."""

    scene_graph: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    diff: dict[str, Any]
    applied_changes: list[dict[str, Any]] = field(default_factory=list)
    skipped_changes: list[dict[str, Any]] = field(default_factory=list)


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _schema_root(schema_filename: str) -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / schema_filename
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{schema_filename}")


@lru_cache(maxsize=1)
def get_scene_branch_schema() -> dict[str, Any]:
    """Return the committed Scene Branch JSON Schema."""
    path = _schema_root(SCENE_BRANCH_SCHEMA_FILENAME) / SCENE_BRANCH_SCHEMA_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_scene_diff_schema() -> dict[str, Any]:
    """Return the committed Scene Diff JSON Schema."""
    path = _schema_root(SCENE_DIFF_SCHEMA_FILENAME) / SCENE_DIFF_SCHEMA_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_diagnostics(
    *,
    schema: Mapping[str, Any],
    contract: str,
    code: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": code,
                "severity": "error",
                "contract": contract,
                "path": _json_pointer(*error.absolute_path),
                "message": error.message,
            }
        )
    return diagnostics


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    contract: str,
    phase: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": contract,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _branch_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _diagnostic(
        code,
        name,
        path,
        message,
        contract=_SCENE_BRANCH_CONTRACT,
        phase="scene_branch_semantics",
        details=details,
    )


def _diff_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _diagnostic(
        code,
        name,
        path,
        message,
        contract=_SCENE_DIFF_CONTRACT,
        phase="scene_diff_semantics",
        details=details,
    )


def _merge_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _diagnostic(
        code,
        name,
        path,
        message,
        contract=_SCENE_MERGE_CONTRACT,
        phase="scene_merge",
        details=details,
    )


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) else None


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_normal_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, *, size: int = 16) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:size]


def _scene_ref(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    version = scene_graph.get("version")
    return {
        "scene_id": scene_id,
        "version": version if isinstance(version, int) and version >= 1 else 1,
        "fingerprint": _fingerprint(scene_graph),
    }


def _version_id(scene_id: str, branch_id: str, scene_version: int, scene_fingerprint: str) -> str:
    body = clamp_id_body(f"{scene_id}_{branch_id}_{scene_version:03d}_{scene_fingerprint}", max_body=118)
    return f"version_{body}"


def _diff_id(left: Mapping[str, Any], right: Mapping[str, Any], changes: Sequence[Mapping[str, Any]]) -> str:
    left_id = str(left.get("scene_id", "scene"))
    right_id = str(right.get("scene_id", "scene"))
    body = clamp_id_body(f"{left_id}_{right_id}_{_fingerprint(changes, size=16)}", max_body=123)
    return f"diff_{body}"


def _change_id(
    *,
    kind: str,
    operation: str,
    entity_type: str,
    entity_id: str,
    path: str,
    left: Any,
    right: Any,
) -> str:
    fingerprint = _fingerprint(
        {
            "kind": kind,
            "operation": operation,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "path": path,
            "left": left,
            "right": right,
        },
        size=16,
    )
    return f"change_{fingerprint}"


def _version_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    versions = payload.get("versions", [])
    if not isinstance(versions, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for version in versions:
        if not isinstance(version, Mapping):
            continue
        version_id = _string_field(version, "version_id")
        if version_id is not None and version_id not in result:
            result[version_id] = version
    return result


def validate_scene_branch_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema plus semantic diagnostics for a Scene Branch payload."""
    diagnostics = _schema_diagnostics(
        schema=get_scene_branch_schema(),
        contract=_SCENE_BRANCH_CONTRACT,
        code="SCENE_BRANCH_SCHEMA_VALIDATION",
        payload=payload,
    )
    if diagnostics:
        return diagnostics

    branch_id = _string_field(payload, "branch_id")
    parent_branch = _string_field(payload, "parent_branch")
    base_version_id = _string_field(payload, "base_version_id")
    head_version_id = _string_field(payload, "head_version_id")
    versions = payload.get("versions", [])
    version_by_id = _version_by_id(payload)
    seen: dict[str, str] = {}
    semantic: list[dict[str, Any]] = []

    if isinstance(versions, list):
        for index, version in enumerate(versions):
            if not isinstance(version, Mapping):
                continue
            version_id = _string_field(version, "version_id")
            if version_id is None:
                continue
            path = _json_pointer("versions", index, "version_id")
            first_path = seen.get(version_id)
            if first_path is None:
                seen[version_id] = path
            else:
                semantic.append(
                    _branch_diagnostic(
                        "SB1601",
                        "duplicate_version_id",
                        path,
                        f"Scene Branch version_id {version_id!r} duplicates the version at {first_path}.",
                        details={"version_id": version_id, "first_path": first_path},
                    )
                )
            parents = version.get("parents", [])
            if not isinstance(parents, list):
                continue
            for parent_index, parent_version_id in enumerate(parents):
                if not isinstance(parent_version_id, str) or parent_version_id in version_by_id:
                    continue
                semantic.append(
                    _branch_diagnostic(
                        "SB1605",
                        "invalid_parent_version",
                        _json_pointer("versions", index, "parents", parent_index),
                        f"Parent version {parent_version_id!r} does not match any version_id in this payload.",
                        details={"version_id": version_id, "parent_version_id": parent_version_id},
                    )
                )
            if version_id in parents:
                semantic.append(
                    _branch_diagnostic(
                        "SB1606",
                        "self_parent_version",
                        _json_pointer("versions", index, "parents"),
                        f"Version {version_id!r} cannot list itself as a parent.",
                        details={"version_id": version_id},
                    )
                )

    if base_version_id not in version_by_id:
        semantic.append(
            _branch_diagnostic(
                "SB1602",
                "missing_base_version",
                "/base_version_id",
                f"Base version {base_version_id!r} does not match any version_id.",
                details={"base_version_id": base_version_id},
            )
        )
    elif parent_branch is not None and _string_field(version_by_id[base_version_id], "branch_id") != parent_branch:
        semantic.append(
            _branch_diagnostic(
                "SB1604",
                "base_version_parent_branch_mismatch",
                "/base_version_id",
                "Base version branch_id must match parent_branch.",
                details={
                    "base_version_id": base_version_id,
                    "parent_branch": parent_branch,
                    "base_version_branch_id": _string_field(version_by_id[base_version_id], "branch_id"),
                },
            )
        )
    if head_version_id not in version_by_id:
        semantic.append(
            _branch_diagnostic(
                "SB1603",
                "missing_head_version",
                "/head_version_id",
                f"Head version {head_version_id!r} does not match any version_id.",
                details={"head_version_id": head_version_id},
            )
        )
    elif branch_id is not None and _string_field(version_by_id[head_version_id], "branch_id") != branch_id:
        semantic.append(
            _branch_diagnostic(
                "SB1607",
                "head_version_branch_mismatch",
                "/head_version_id",
                "Head version branch_id must match branch_id.",
                details={
                    "head_version_id": head_version_id,
                    "branch_id": branch_id,
                    "head_version_branch_id": _string_field(version_by_id[head_version_id], "branch_id"),
                },
            )
        )
    return semantic


def _change(
    *,
    kind: str,
    operation: str,
    entity_type: str,
    entity_id: str,
    path: str,
    left: Any = _MISSING,
    right: Any = _MISSING,
) -> dict[str, Any]:
    normalized_left = _normal_json(left) if left is not _MISSING else _MISSING
    normalized_right = _normal_json(right) if right is not _MISSING else _MISSING
    change_left = normalized_left if normalized_left is not _MISSING else {"__lathe_missing__": True}
    change_right = normalized_right if normalized_right is not _MISSING else {"__lathe_missing__": True}
    payload: dict[str, Any] = {
        "change_id": _change_id(
            kind=kind,
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            path=path,
            left=change_left,
            right=change_right,
        ),
        "kind": kind,
        "operation": operation,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "path": path,
    }
    if normalized_left is not _MISSING:
        payload["left"] = normalized_left
    if normalized_right is not _MISSING:
        payload["right"] = normalized_right
    return payload


def _indexed_items(scene_graph: Mapping[str, Any], collection: str) -> dict[str, Mapping[str, Any]]:
    field = _ENTITY_COLLECTIONS[collection]
    items: dict[str, Mapping[str, Any]] = {}
    for _index, item in _items(scene_graph, collection):
        entity_id = _string_field(item, field)
        if entity_id is not None and entity_id not in items:
            items[entity_id] = item
    return items


def _object_rest(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _normal_json(value) for key, value in item.items() if key not in _OBJECT_MERGE_FIELDS}


def _diff_object(left_item: Mapping[str, Any], right_item: Mapping[str, Any], object_id: str) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    if _normal_json(left_item.get("transform")) != _normal_json(right_item.get("transform")):
        changes.append(
            _change(
                kind="object_transform_changed",
                operation="replace",
                entity_type="object",
                entity_id=object_id,
                path=_json_pointer("objects", object_id, "transform"),
                left=left_item.get("transform"),
                right=right_item.get("transform"),
            )
        )
    if _normal_json(left_item.get("material_bindings", [])) != _normal_json(right_item.get("material_bindings", [])):
        changes.append(
            _change(
                kind="object_material_changed",
                operation="replace",
                entity_type="object",
                entity_id=object_id,
                path=_json_pointer("objects", object_id, "material_bindings"),
                left=left_item.get("material_bindings", []),
                right=right_item.get("material_bindings", []),
            )
        )
    if _normal_json(left_item.get("state", {})) != _normal_json(right_item.get("state", {})):
        changes.append(
            _change(
                kind="object_state_changed",
                operation="replace",
                entity_type="object",
                entity_id=object_id,
                path=_json_pointer("objects", object_id, "state"),
                left=left_item.get("state", {}),
                right=right_item.get("state", {}),
            )
        )
    if _object_rest(left_item) != _object_rest(right_item):
        changes.append(
            _change(
                kind="object_changed",
                operation="replace",
                entity_type="object",
                entity_id=object_id,
                path=_json_pointer("objects", object_id),
                left=_object_rest(left_item),
                right=_object_rest(right_item),
            )
        )
    return changes


def _diff_collection(left: Mapping[str, Any], right: Mapping[str, Any], collection: str) -> list[dict[str, Any]]:
    entity_type = _ENTITY_TYPE_BY_COLLECTION[collection]
    left_items = _indexed_items(left, collection)
    right_items = _indexed_items(right, collection)
    changes: list[dict[str, Any]] = []

    for entity_id in sorted(set(right_items) - set(left_items)):
        changes.append(
            _change(
                kind=f"{entity_type}_added",
                operation="add",
                entity_type=entity_type,
                entity_id=entity_id,
                path=_json_pointer(collection, entity_id),
                right=right_items[entity_id],
            )
        )
    for entity_id in sorted(set(left_items) - set(right_items)):
        changes.append(
            _change(
                kind=f"{entity_type}_removed",
                operation="remove",
                entity_type=entity_type,
                entity_id=entity_id,
                path=_json_pointer(collection, entity_id),
                left=left_items[entity_id],
            )
        )
    for entity_id in sorted(set(left_items) & set(right_items)):
        left_item = left_items[entity_id]
        right_item = right_items[entity_id]
        if collection == "objects":
            changes.extend(_diff_object(left_item, right_item, entity_id))
        elif _normal_json(left_item) != _normal_json(right_item):
            changes.append(
                _change(
                    kind=f"{entity_type}_changed",
                    operation="replace",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    path=_json_pointer(collection, entity_id),
                    left=left_item,
                    right=right_item,
                )
            )
    return changes


def _top_level_metadata_changes(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    keys = sorted((set(left) | set(right)) - _TOP_LEVEL_ENTITY_COLLECTIONS)
    for key in keys:
        left_value = left.get(key, _MISSING)
        right_value = right.get(key, _MISSING)
        if _normal_json(left_value) == _normal_json(right_value):
            continue
        operation = "replace"
        if left_value is _MISSING:
            operation = "add"
        elif right_value is _MISSING:
            operation = "remove"
        changes.append(
            _change(
                kind="scene_metadata_changed",
                operation=operation,
                entity_type="scene",
                entity_id=str(left.get("scene_id") or right.get("scene_id") or "scene"),
                path=_json_pointer(key),
                left=left_value,
                right=right_value,
            )
        )
    return changes


def _diff_summary(changes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    kinds = [str(change.get("kind", "")) for change in changes]
    return {
        "total_changes": len(changes),
        "objects_added": kinds.count("object_added"),
        "objects_removed": kinds.count("object_removed"),
        "object_transform_changes": kinds.count("object_transform_changed"),
        "object_material_changes": kinds.count("object_material_changed"),
        "object_state_changes": kinds.count("object_state_changed"),
        "materials_added": kinds.count("material_added"),
        "materials_removed": kinds.count("material_removed"),
    }


def validate_scene_diff_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema plus semantic diagnostics for a Scene Diff payload."""
    diagnostics = _schema_diagnostics(
        schema=get_scene_diff_schema(),
        contract=_SCENE_DIFF_CONTRACT,
        code="SCENE_DIFF_SCHEMA_VALIDATION",
        payload=payload,
    )
    if diagnostics:
        return diagnostics

    semantic: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    changes = payload.get("changes", [])
    if isinstance(changes, list):
        for index, change in enumerate(changes):
            if not isinstance(change, Mapping):
                continue
            change_id = _string_field(change, "change_id")
            if change_id is None:
                continue
            path = _json_pointer("changes", index, "change_id")
            first_path = seen.get(change_id)
            if first_path is None:
                seen[change_id] = path
            else:
                semantic.append(
                    _diff_diagnostic(
                        "SD1601",
                        "duplicate_change_id",
                        path,
                        f"Scene Diff change_id {change_id!r} duplicates the change at {first_path}.",
                        details={"change_id": change_id, "first_path": first_path},
                    )
                )
            operation = _string_field(change, "operation")
            has_left = "left" in change
            has_right = "right" in change
            if operation == "add" and has_left:
                semantic.append(
                    _diff_diagnostic(
                        "SD1603",
                        "invalid_change_payload",
                        _json_pointer("changes", index, "left"),
                        "Add changes must not include a left value.",
                        details={"change_id": change_id},
                    )
                )
            if operation == "remove" and has_right:
                semantic.append(
                    _diff_diagnostic(
                        "SD1603",
                        "invalid_change_payload",
                        _json_pointer("changes", index, "right"),
                        "Remove changes must not include a right value.",
                        details={"change_id": change_id},
                    )
                )
            if operation == "replace" and (not has_left or not has_right):
                semantic.append(
                    _diff_diagnostic(
                        "SD1603",
                        "invalid_change_payload",
                        _json_pointer("changes", index),
                        "Replace changes must include both left and right values.",
                        details={"change_id": change_id},
                    )
                )

    expected_summary = _diff_summary(changes if isinstance(changes, list) else [])
    summary = payload.get("summary", {})
    if isinstance(summary, Mapping):
        for key, expected in expected_summary.items():
            actual = summary.get(key)
            if actual == expected:
                continue
            semantic.append(
                _diff_diagnostic(
                    "SD1602",
                    "diff_summary_mismatch",
                    _json_pointer("summary", key),
                    f"Scene Diff summary {key}={actual!r} does not match computed value {expected!r}.",
                    details={"summary_key": key, "actual": actual, "expected": expected},
                )
            )
    left_ref = payload.get("left", {})
    right_ref = payload.get("right", {})
    if isinstance(left_ref, Mapping) and isinstance(right_ref, Mapping):
        left_scene_id = _string_field(left_ref, "scene_id")
        right_scene_id = _string_field(right_ref, "scene_id")
        if left_scene_id is not None and right_scene_id is not None and left_scene_id != right_scene_id:
            semantic.append(
                _diff_diagnostic(
                    "SD1604",
                    "diff_scene_mismatch",
                    "/right/scene_id",
                    "Scene Diff endpoints must describe the same scene_id.",
                    details={"left_scene_id": left_scene_id, "right_scene_id": right_scene_id},
                )
            )
    return semantic


def create_branch(scene_graph: Mapping[str, Any], name: str, parent: str = "main") -> dict[str, Any]:
    """Create a deterministic branch/version graph payload for a Scene Graph."""
    if not is_snake_id(parent):
        raise ValueError(f"parent branch must be a snake_id: {parent!r}")

    scene = _scene_ref(scene_graph)
    branch_id = snake_id(name, fallback="branch")
    scene_id = str(scene["scene_id"])
    scene_version = int(scene["version"])
    scene_fingerprint = str(scene["fingerprint"])
    base_version_id = _version_id(scene_id, parent, scene_version, scene_fingerprint)
    head_version_id = _version_id(scene_id, branch_id, scene_version, scene_fingerprint)
    return {
        "schema_version": SCENE_BRANCH_VERSION,
        "scene_id": scene_id,
        "branch_id": branch_id,
        "name": name,
        "parent_branch": parent,
        "base_version_id": base_version_id,
        "head_version_id": head_version_id,
        "versions": [
            {
                "version_id": base_version_id,
                "branch_id": parent,
                "scene_version": scene_version,
                "scene_fingerprint": scene_fingerprint,
                "parents": [],
            },
            {
                "version_id": head_version_id,
                "branch_id": branch_id,
                "scene_version": scene_version,
                "scene_fingerprint": scene_fingerprint,
                "parents": [base_version_id],
            },
        ],
        "metadata": {
            "created_by": "lathe.scene.versioning.create_branch",
        },
    }


def diff_scene_graphs(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic Scene Diff payload from ``left`` to ``right``."""
    changes: list[dict[str, Any]] = []
    for collection in _MERGE_COLLECTION_ORDER:
        changes.extend(_diff_collection(left, right, collection))
    changes.extend(_top_level_metadata_changes(left, right))
    left_ref = _scene_ref(left)
    right_ref = _scene_ref(right)
    return {
        "schema_version": SCENE_DIFF_VERSION,
        "diff_id": _diff_id(left_ref, right_ref, changes),
        "left": left_ref,
        "right": right_ref,
        "summary": _diff_summary(changes),
        "changes": changes,
    }


def _mutable_item_by_id(scene_graph: Mapping[str, Any], collection: str, entity_id: str) -> dict[str, Any] | None:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return None
    field = _ENTITY_COLLECTIONS[collection]
    for item in raw:
        if isinstance(item, dict) and item.get(field) == entity_id:
            return item
    return None


def _append_entity(
    working: dict[str, Any],
    collection: str,
    item: Mapping[str, Any],
) -> bool:
    raw = working.get(collection)
    if not isinstance(raw, list):
        return False
    raw.append(copy.deepcopy(dict(item)))
    return True


def _collection_additions(source: Mapping[str, Any], target: Mapping[str, Any], collection: str) -> list[Mapping[str, Any]]:
    source_items = _indexed_items(source, collection)
    target_items = _indexed_items(target, collection)
    field = _ENTITY_COLLECTIONS[collection]
    return [
        source_items[entity_id]
        for entity_id in sorted(set(source_items) - set(target_items))
        if _string_field(source_items[entity_id], field) is not None
    ]


def _binding_slots(bindings: Any) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    slots: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    if not isinstance(bindings, list):
        return slots, duplicates
    for binding in bindings:
        if not isinstance(binding, Mapping):
            continue
        slot = _string_field(binding, "slot")
        if slot is None:
            continue
        if slot in slots:
            duplicates.add(slot)
            continue
        slots[slot] = binding
    return slots, duplicates


def _material_ids_for_object(item: Mapping[str, Any]) -> set[str]:
    bindings = item.get("material_bindings", [])
    if not isinstance(bindings, list):
        return set()
    return {
        str(binding["material"])
        for binding in bindings
        if isinstance(binding, Mapping) and isinstance(binding.get("material"), str)
    }


def _merge_materials(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    working: dict[str, Any],
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    conflicted: set[str] = set()
    source_items = _indexed_items(source, "materials")
    target_items = _indexed_items(target, "materials")

    for material_id in sorted(set(source_items) & set(target_items)):
        if _normal_json(source_items[material_id]) == _normal_json(target_items[material_id]):
            continue
        conflicted.add(material_id)
        diagnostics.append(
            _merge_diagnostic(
                "SM1605",
                "material_conflict",
                _json_pointer("materials", material_id),
                f"Material {material_id!r} differs in both merge inputs.",
                details={"material_id": material_id},
            )
        )
        skipped.append({"kind": "material_conflict", "material_id": material_id})

    for item in _collection_additions(source, target, "materials"):
        material_id = str(item["material_id"])
        if _append_entity(working, "materials", item):
            applied.append({"kind": "material_added", "material_id": material_id})
    return conflicted, diagnostics, applied, skipped


def _merge_object_material_bindings(
    source_item: Mapping[str, Any],
    target_item: dict[str, Any],
    object_id: str,
    conflicted_materials: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    target_bindings = target_item.setdefault("material_bindings", [])
    if not isinstance(target_bindings, list):
        diagnostics.append(
            _merge_diagnostic(
                "SM1603",
                "object_material_conflict",
                _json_pointer("objects", object_id, "material_bindings"),
                f"Object {object_id!r} target material_bindings is not an array.",
                details={"object_id": object_id},
            )
        )
        skipped.append({"kind": "object_material_conflict", "object_id": object_id})
        return diagnostics, applied, skipped

    source_slots, source_duplicates = _binding_slots(source_item.get("material_bindings", []))
    target_slots, target_duplicates = _binding_slots(target_bindings)
    for slot in sorted(source_duplicates | target_duplicates):
        diagnostics.append(
            _merge_diagnostic(
                "SM1603",
                "object_material_conflict",
                _json_pointer("objects", object_id, "material_bindings"),
                f"Object {object_id!r} has duplicate material binding slot {slot!r}.",
                details={"object_id": object_id, "slot": slot},
            )
        )
        skipped.append({"kind": "object_material_conflict", "object_id": object_id, "slot": slot})

    for slot in sorted(source_slots):
        source_binding = source_slots[slot]
        target_binding = target_slots.get(slot)
        material_id = _string_field(source_binding, "material")
        if material_id in conflicted_materials:
            diagnostics.append(
                _merge_diagnostic(
                    "SM1603",
                    "object_material_conflict",
                    _json_pointer("objects", object_id, "material_bindings", slot),
                    f"Object {object_id!r} binding slot {slot!r} depends on conflicted material {material_id!r}.",
                    details={"object_id": object_id, "slot": slot, "material_id": material_id},
                )
            )
            skipped.append({"kind": "object_material_conflict", "object_id": object_id, "slot": slot})
            continue
        if target_binding is None:
            target_bindings.append(copy.deepcopy(dict(source_binding)))
            applied.append({"kind": "object_material_binding_added", "object_id": object_id, "slot": slot})
            continue
        if _normal_json(source_binding) == _normal_json(target_binding):
            continue
        diagnostics.append(
            _merge_diagnostic(
                "SM1603",
                "object_material_conflict",
                _json_pointer("objects", object_id, "material_bindings", slot),
                f"Object {object_id!r} material binding slot {slot!r} differs in both merge inputs.",
                details={"object_id": object_id, "slot": slot},
            )
        )
        skipped.append({"kind": "object_material_conflict", "object_id": object_id, "slot": slot})
    return diagnostics, applied, skipped


def _merge_object_state(
    source_item: Mapping[str, Any],
    target_item: dict[str, Any],
    object_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    source_state = source_item.get("state", {})
    target_state = target_item.setdefault("state", {})
    if not isinstance(source_state, Mapping) or not isinstance(target_state, dict):
        diagnostics.append(
            _merge_diagnostic(
                "SM1604",
                "object_state_conflict",
                _json_pointer("objects", object_id, "state"),
                f"Object {object_id!r} state must be an object in both merge inputs.",
                details={"object_id": object_id},
            )
        )
        skipped.append({"kind": "object_state_conflict", "object_id": object_id})
        return diagnostics, applied, skipped

    for key in sorted(source_state, key=str):
        source_value = source_state[key]
        if key not in target_state:
            target_state[str(key)] = copy.deepcopy(source_value)
            applied.append({"kind": "object_state_added", "object_id": object_id, "state_key": str(key)})
            continue
        if _normal_json(source_value) == _normal_json(target_state[key]):
            continue
        diagnostics.append(
            _merge_diagnostic(
                "SM1604",
                "object_state_conflict",
                _json_pointer("objects", object_id, "state", key),
                f"Object {object_id!r} state key {key!r} differs in both merge inputs.",
                details={"object_id": object_id, "state_key": str(key)},
            )
        )
        skipped.append({"kind": "object_state_conflict", "object_id": object_id, "state_key": str(key)})
    return diagnostics, applied, skipped


def _merge_existing_object(
    source_item: Mapping[str, Any],
    target_item: dict[str, Any],
    object_id: str,
    conflicted_materials: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if _normal_json(source_item.get("transform")) != _normal_json(target_item.get("transform")):
        diagnostics.append(
            _merge_diagnostic(
                "SM1602",
                "object_transform_conflict",
                _json_pointer("objects", object_id, "transform"),
                f"Object {object_id!r} transform differs in both merge inputs.",
                details={"object_id": object_id},
            )
        )
        skipped.append({"kind": "object_transform_conflict", "object_id": object_id})

    binding_diagnostics, binding_applied, binding_skipped = _merge_object_material_bindings(
        source_item,
        target_item,
        object_id,
        conflicted_materials,
    )
    diagnostics.extend(binding_diagnostics)
    applied.extend(binding_applied)
    skipped.extend(binding_skipped)

    state_diagnostics, state_applied, state_skipped = _merge_object_state(source_item, target_item, object_id)
    diagnostics.extend(state_diagnostics)
    applied.extend(state_applied)
    skipped.extend(state_skipped)

    source_rest = _object_rest(source_item)
    target_rest = _object_rest(target_item)
    if source_rest != target_rest:
        diagnostics.append(
            _merge_diagnostic(
                "SM1606",
                "object_field_conflict",
                _json_pointer("objects", object_id),
                f"Object {object_id!r} has non-mergeable field differences.",
                details={"object_id": object_id},
            )
        )
        skipped.append({"kind": "object_field_conflict", "object_id": object_id})

    return diagnostics, applied, skipped


def _merge_objects(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    working: dict[str, Any],
    conflicted_materials: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    source_items = _indexed_items(source, "objects")
    target_items = _indexed_items(target, "objects")

    for object_id in sorted(set(source_items) & set(target_items)):
        target_item = _mutable_item_by_id(working, "objects", object_id)
        if target_item is None:
            continue
        object_diagnostics, object_applied, object_skipped = _merge_existing_object(
            source_items[object_id],
            target_item,
            object_id,
            conflicted_materials,
        )
        diagnostics.extend(object_diagnostics)
        applied.extend(object_applied)
        skipped.extend(object_skipped)

    for item in _collection_additions(source, target, "objects"):
        object_id = str(item["object_id"])
        blocked_materials = sorted(_material_ids_for_object(item) & conflicted_materials)
        if blocked_materials:
            diagnostics.append(
                _merge_diagnostic(
                    "SM1603",
                    "object_material_conflict",
                    _json_pointer("objects", object_id, "material_bindings"),
                    f"Object {object_id!r} depends on conflicted materials and was not added.",
                    details={"object_id": object_id, "material_ids": blocked_materials},
                )
            )
            skipped.append({"kind": "object_added", "object_id": object_id})
            continue
        if _append_entity(working, "objects", item):
            applied.append({"kind": "object_added", "object_id": object_id})
    return diagnostics, applied, skipped


def _merge_generic_collection(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    working: dict[str, Any],
    collection: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    source_items = _indexed_items(source, collection)
    target_items = _indexed_items(target, collection)
    entity_type = _ENTITY_TYPE_BY_COLLECTION[collection]

    for entity_id in sorted(set(source_items) & set(target_items)):
        if _normal_json(source_items[entity_id]) == _normal_json(target_items[entity_id]):
            continue
        diagnostics.append(
            _merge_diagnostic(
                "SM1607",
                "entity_conflict",
                _json_pointer(collection, entity_id),
                f"{entity_type} {entity_id!r} differs in both merge inputs.",
                details={"entity_type": entity_type, "entity_id": entity_id},
            )
        )
        skipped.append({"kind": f"{entity_type}_conflict", "entity_id": entity_id})

    for item in _collection_additions(source, target, collection):
        entity_id = str(item[_ENTITY_COLLECTIONS[collection]])
        if _append_entity(working, collection, item):
            applied.append({"kind": f"{entity_type}_added", "entity_id": entity_id})
    return diagnostics, applied, skipped


def _merge_top_level_metadata(source: Mapping[str, Any], target: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    keys = sorted((set(source) | set(target)) - _TOP_LEVEL_ENTITY_COLLECTIONS - {"version"})
    for key in keys:
        if _normal_json(source.get(key, _MISSING)) == _normal_json(target.get(key, _MISSING)):
            continue
        diagnostics.append(
            _merge_diagnostic(
                "SM1608",
                "scene_metadata_conflict",
                _json_pointer(key),
                f"Scene metadata field {key!r} differs in both merge inputs.",
                details={"field": key},
            )
        )
    return diagnostics


def _bump_version(working: dict[str, Any], source: Mapping[str, Any], target: Mapping[str, Any]) -> None:
    source_version = source.get("version")
    target_version = target.get("version")
    versions = [value for value in (source_version, target_version) if isinstance(value, int) and value >= 1]
    working["version"] = (max(versions) if versions else 1) + 1


def merge_scene_graphs(source: Mapping[str, Any], target: Mapping[str, Any]) -> SceneMergeResult:
    """Merge non-overlapping Scene Graph changes from ``source`` into ``target``.

    Same-ID object transforms, material binding slots, and state keys are never
    overwritten with different values. Source-only entities and non-overlapping
    object material/state additions are copied into a target-shaped result.
    """
    working = copy.deepcopy(dict(target))
    source_diff = diff_scene_graphs(target, source)
    diagnostics: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    source_scene_id = _string_field(source, "scene_id")
    target_scene_id = _string_field(target, "scene_id")
    if source_scene_id is not None and target_scene_id is not None and source_scene_id != target_scene_id:
        diagnostics.append(
            _merge_diagnostic(
                "SM1601",
                "scene_merge_scene_mismatch",
                "/scene_id",
                "Cannot merge Scene Graphs with different scene_id values.",
                details={"source_scene_id": source_scene_id, "target_scene_id": target_scene_id},
            )
        )
        return SceneMergeResult(
            scene_graph=working,
            diagnostics=diagnostics,
            diff=source_diff,
            applied_changes=applied,
            skipped_changes=[{"kind": "scene_merge_scene_mismatch"}],
        )

    diagnostics.extend(_merge_top_level_metadata(source, target))

    for collection in ("regions",):
        collection_diagnostics, collection_applied, collection_skipped = _merge_generic_collection(
            source,
            target,
            working,
            collection,
        )
        diagnostics.extend(collection_diagnostics)
        applied.extend(collection_applied)
        skipped.extend(collection_skipped)

    conflicted_materials, material_diagnostics, material_applied, material_skipped = _merge_materials(
        source,
        target,
        working,
    )
    diagnostics.extend(material_diagnostics)
    applied.extend(material_applied)
    skipped.extend(material_skipped)

    object_diagnostics, object_applied, object_skipped = _merge_objects(
        source,
        target,
        working,
        conflicted_materials,
    )
    diagnostics.extend(object_diagnostics)
    applied.extend(object_applied)
    skipped.extend(object_skipped)

    for collection in ("relationships", "lights", "cameras", "curiosity_anchors", "hidden_state"):
        collection_diagnostics, collection_applied, collection_skipped = _merge_generic_collection(
            source,
            target,
            working,
            collection,
        )
        diagnostics.extend(collection_diagnostics)
        applied.extend(collection_applied)
        skipped.extend(collection_skipped)

    if applied:
        _bump_version(working, source, target)

    return SceneMergeResult(
        scene_graph=working,
        diagnostics=diagnostics,
        diff=source_diff,
        applied_changes=applied,
        skipped_changes=skipped,
    )


__all__ = [
    "SCENE_BRANCH_SCHEMA_FILENAME",
    "SCENE_BRANCH_VERSION",
    "SCENE_DIFF_SCHEMA_FILENAME",
    "SCENE_DIFF_VERSION",
    "SceneMergeResult",
    "create_branch",
    "diff_scene_graphs",
    "get_scene_branch_schema",
    "get_scene_diff_schema",
    "merge_scene_graphs",
    "validate_scene_branch_payload",
    "validate_scene_diff_payload",
]
