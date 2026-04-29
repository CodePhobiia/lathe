"""World Memory validation helpers for Wonder scene continuity."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from lathe.wonder import load_and_validate_contract, validate_contract

from .graph import SCENE_REF_COLLECTIONS, load_and_check_scene_graph
from .ids import clamp_id_body, is_scene_entity_id, is_snake_id

MEMORY_REF_COLLECTIONS: dict[str, str] = {
    **SCENE_REF_COLLECTIONS,
    "materials": "material_id",
    "relationships": "relationship_id",
}

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|apikey|authorization|bearer|credential|private[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE)
_OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")
_ANTHROPIC_KEY_RE = re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}\b")
_GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_KEY_VALUE_SECRET_RE = re.compile(
    r"\b(password|secret|token|api[_-]?key|authorization|credential)\s*[:=]\s*['\"]?([A-Za-z0-9._~+/=-]{8,})['\"]?",
    re.IGNORECASE,
)
_PHONE_LIKE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{8,}\d)(?!\w)")


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _memory_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": "world_memory",
        "phase": "world_memory_semantics",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _items(payload: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = payload.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) else None


def _world_memory_entity_ref(value: str) -> bool:
    return is_snake_id(value) or any(
        is_scene_entity_id(prefix, value)
        for prefix in ("object", "region", "relationship", "material", "light", "camera", "curiosity", "hidden")
    )


def _redact_sensitive_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redact_sensitive_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_sensitive_value(child) for child in value]
    return _REDACTED


def _redact_text(value: str) -> str:
    redacted = _EMAIL_RE.sub(_REDACTED, value)
    redacted = _BEARER_RE.sub(_REDACTED, redacted)
    redacted = _OPENAI_KEY_RE.sub(_REDACTED, redacted)
    redacted = _ANTHROPIC_KEY_RE.sub(_REDACTED, redacted)
    redacted = _GITHUB_TOKEN_RE.sub(_REDACTED, redacted)
    redacted = _KEY_VALUE_SECRET_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", redacted)

    def redact_phone(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        return _REDACTED if len(digits) >= 10 else match.group(0)

    return _PHONE_LIKE_RE.sub(redact_phone, redacted)


def _redact_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text):
                redacted[key_text] = _redact_sensitive_value(child)
            else:
                redacted[key_text] = _redact_payload(child)
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return copy.deepcopy(value)


def redact_memory_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep redacted copy of a World Memory-related mapping."""
    if isinstance(payload, Mapping):
        return _redact_payload(payload)
    raise TypeError("payload must be a mapping")


def _event_id_locations(world_memory: Mapping[str, Any]) -> dict[str, str]:
    locations: dict[str, str] = {}
    for index, event in _items(world_memory, "events"):
        event_id = _string_field(event, "event_id")
        if event_id is not None and event_id not in locations:
            locations[event_id] = _json_pointer("events", index, "event_id")
    return locations


def _scene_entity_ids(scene_graph: Mapping[str, Any]) -> set[str]:
    entity_ids: set[str] = set()
    scene_id = _string_field(scene_graph, "scene_id")
    if scene_id:
        entity_ids.add(scene_id)
    for collection, field in MEMORY_REF_COLLECTIONS.items():
        for _index, item in _items(scene_graph, collection):
            entity_id = _string_field(item, field)
            if entity_id:
                entity_ids.add(entity_id)
    return entity_ids


def _check_duplicate_event_ids(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for index, event in _items(world_memory, "events"):
        event_id = _string_field(event, "event_id")
        if event_id is None:
            continue
        path = _json_pointer("events", index, "event_id")
        first_path = seen.get(event_id)
        if first_path is None:
            seen[event_id] = path
            continue
        diagnostics.append(
            _memory_diagnostic(
                "M1001",
                "duplicate_memory_event_id",
                path,
                f"Duplicate memory event_id {event_id!r}; first seen at {first_path}.",
                details={"event_id": event_id, "first_path": first_path},
            )
        )
    return diagnostics


def _check_duplicate_branch_ids(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for index, branch in _items(world_memory, "branches"):
        branch_id = _string_field(branch, "branch_id")
        if branch_id is None:
            continue
        path = _json_pointer("branches", index, "branch_id")
        first_path = seen.get(branch_id)
        if first_path is None:
            seen[branch_id] = path
            continue
        diagnostics.append(
            _memory_diagnostic(
                "M1007",
                "duplicate_memory_branch_id",
                path,
                f"Duplicate branch_id {branch_id!r}; first seen at {first_path}.",
                details={"branch_id": branch_id, "first_path": first_path},
            )
        )
    return diagnostics


def _check_current_branch(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    current_branch = _string_field(world_memory, "current_branch")
    if current_branch is None:
        return []
    branch_ids = {_string_field(branch, "branch_id") for _index, branch in _items(world_memory, "branches")}
    if current_branch in branch_ids:
        return []
    return [
        _memory_diagnostic(
            "M1008",
            "current_branch_missing",
            "/current_branch",
            f"Current branch {current_branch!r} does not match any branch_id.",
            details={"current_branch": current_branch},
        )
    ]


def _branch_event_sets(world_memory: Mapping[str, Any]) -> dict[str, set[str]]:
    branches: dict[str, set[str]] = {}
    for _index, branch in _items(world_memory, "branches"):
        branch_id = _string_field(branch, "branch_id")
        if branch_id is None:
            continue
        raw_event_ids = branch.get("event_ids", [])
        event_ids = {event_id for event_id in raw_event_ids if isinstance(event_id, str)} if isinstance(raw_event_ids, list) else set()
        branches[branch_id] = event_ids
    return branches


def _check_parent_branches(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    branch_ids = set(_branch_event_sets(world_memory))
    for branch_index, branch in _items(world_memory, "branches"):
        branch_id = _string_field(branch, "branch_id")
        parent_branch = _string_field(branch, "parent_branch")
        if parent_branch is None or parent_branch in branch_ids:
            continue
        diagnostics.append(
            _memory_diagnostic(
                "M1011",
                "invalid_parent_branch",
                _json_pointer("branches", branch_index, "parent_branch"),
                f"Parent branch {parent_branch!r} does not match any branch_id.",
                details={"branch_id": branch_id, "parent_branch": parent_branch},
            )
        )
    return diagnostics


def _check_event_branch_membership(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    branch_events = _branch_event_sets(world_memory)
    for event_index, event in _items(world_memory, "events"):
        event_id = _string_field(event, "event_id")
        branch_id = _string_field(event, "branch_id")
        if branch_id is None:
            continue
        if branch_id not in branch_events:
            diagnostics.append(
                _memory_diagnostic(
                    "M1012",
                    "invalid_event_branch",
                    _json_pointer("events", event_index, "branch_id"),
                    f"Memory event branch_id {branch_id!r} does not match any branch_id.",
                    details={"event_id": event_id, "branch_id": branch_id},
                )
            )
            continue
        if event_id is not None and event_id not in branch_events[branch_id]:
            diagnostics.append(
                _memory_diagnostic(
                    "M1013",
                    "event_missing_from_branch",
                    _json_pointer("events", event_index, "branch_id"),
                    f"Memory event {event_id!r} is not listed in branch {branch_id!r}.",
                    details={"event_id": event_id, "branch_id": branch_id},
                )
            )
    return diagnostics


def _check_branch_event_ids(world_memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    event_locations = _event_id_locations(world_memory)
    for branch_index, branch in _items(world_memory, "branches"):
        branch_id = _string_field(branch, "branch_id")
        base_event_id = _string_field(branch, "base_event_id")
        if base_event_id is not None and base_event_id not in event_locations:
            diagnostics.append(
                _memory_diagnostic(
                    "M1005",
                    "invalid_branch_base_event",
                    _json_pointer("branches", branch_index, "base_event_id"),
                    f"Branch base_event_id {base_event_id!r} does not match any event_id.",
                    details={"branch_id": branch_id, "base_event_id": base_event_id},
                )
            )
        raw_event_ids = branch.get("event_ids", [])
        if not isinstance(raw_event_ids, list):
            continue
        for event_index, event_id in enumerate(raw_event_ids):
            if not isinstance(event_id, str) or event_id in event_locations:
                continue
            diagnostics.append(
                _memory_diagnostic(
                    "M1006",
                    "invalid_branch_event",
                    _json_pointer("branches", branch_index, "event_ids", event_index),
                    f"Branch event_id {event_id!r} does not match any event_id.",
                    details={"branch_id": branch_id, "event_id": event_id},
                )
            )
    return diagnostics


def _check_scene_binding(
    world_memory: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    memory_scene_id = _string_field(world_memory, "scene_id")
    scene_id = _string_field(scene_graph, "scene_id")
    if memory_scene_id is not None and scene_id is not None and memory_scene_id != scene_id:
        diagnostics.append(
            _memory_diagnostic(
                "M1003",
                "world_memory_scene_mismatch",
                "/scene_id",
                f"World Memory scene_id {memory_scene_id!r} does not match Scene Graph scene_id {scene_id!r}.",
                details={"world_memory_scene_id": memory_scene_id, "scene_graph_scene_id": scene_id},
            )
        )
    memory_scene_version = world_memory.get("scene_version")
    scene_version = scene_graph.get("version")
    if isinstance(memory_scene_version, int) and isinstance(scene_version, int) and memory_scene_version != scene_version:
        diagnostics.append(
            _memory_diagnostic(
                "M1004",
                "world_memory_scene_version_mismatch",
                "/scene_version",
                "World Memory scene_version does not match Scene Graph version.",
                details={"world_memory_scene_version": memory_scene_version, "scene_graph_version": scene_version},
            )
        )
    return diagnostics


def _check_affected_ids(
    world_memory: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_entity_ids = _scene_entity_ids(scene_graph)
    affected_collections = (
        ("events", "event_id"),
        ("continuity_constraints", "constraint_id"),
    )
    for collection, id_field in affected_collections:
        for item_index, item in _items(world_memory, collection):
            item_id = _string_field(item, id_field)
            affected_ids = item.get("affected_ids", [])
            if not isinstance(affected_ids, list):
                continue
            for affected_index, affected_id in enumerate(affected_ids):
                if not isinstance(affected_id, str) or affected_id in scene_entity_ids:
                    continue
                diagnostics.append(
                    _memory_diagnostic(
                        "M1002",
                        "invalid_memory_affected_id",
                        _json_pointer(collection, item_index, "affected_ids", affected_index),
                        f"World Memory affected_id {affected_id!r} does not reference the Scene Graph.",
                        details={id_field: item_id, "affected_id": affected_id},
                    )
                )
    return diagnostics


def check_world_memory(
    world_memory: Mapping[str, Any],
    *,
    scene_graph: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return semantic diagnostics for a schema-valid World Memory payload."""
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_check_duplicate_event_ids(world_memory))
    diagnostics.extend(_check_duplicate_branch_ids(world_memory))
    diagnostics.extend(_check_current_branch(world_memory))
    diagnostics.extend(_check_parent_branches(world_memory))
    diagnostics.extend(_check_branch_event_ids(world_memory))
    diagnostics.extend(_check_event_branch_membership(world_memory))
    if scene_graph is not None:
        diagnostics.extend(_check_scene_binding(world_memory, scene_graph))
        diagnostics.extend(_check_affected_ids(world_memory, scene_graph))
    return diagnostics


def validate_world_memory(
    world_memory: dict[str, Any],
    *,
    scene_graph: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return schema plus semantic diagnostics for a World Memory payload."""
    diagnostics = validate_contract("world_memory", world_memory)
    if diagnostics:
        return diagnostics
    return check_world_memory(world_memory, scene_graph=scene_graph)


def _load_scene_graph(scene_graph: str | Path | Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, list[dict[str, Any]]]:
    if isinstance(scene_graph, Mapping):
        return scene_graph, []
    payload, diagnostics = load_and_check_scene_graph(scene_graph)
    if diagnostics:
        return None, diagnostics
    return payload, []


def load_and_validate_world_memory(
    path: str | Path,
    *,
    scene_graph: str | Path | Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load a World Memory file and return schema plus semantic diagnostics."""
    payload, diagnostics = load_and_validate_contract("world_memory", path)
    if diagnostics:
        return payload, diagnostics
    scene_graph_payload: Mapping[str, Any] | None = None
    if scene_graph is not None:
        scene_graph_payload, scene_diagnostics = _load_scene_graph(scene_graph)
        if scene_diagnostics:
            return payload, scene_diagnostics
    return payload, check_world_memory(payload, scene_graph=scene_graph_payload)


def create_world_memory(
    scene_graph: Mapping[str, Any],
    *,
    memory_id: str | None = None,
    current_branch: str = "main",
    summary: str | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a minimal World Memory payload for a Scene Graph mapping."""
    scene_id = _string_field(scene_graph, "scene_id") or ""
    scene_version = scene_graph.get("version")
    event_list = copy.deepcopy(events) if events is not None else []
    event_ids = [event["event_id"] for event in event_list if isinstance(event.get("event_id"), str)]
    return {
        "schema_version": "lathe.world_memory.v1",
        "memory_id": memory_id or f"worldmem_{scene_id}",
        "scene_id": scene_id,
        "scene_version": scene_version if isinstance(scene_version, int) else 1,
        "current_branch": current_branch,
        "summary": summary or f"World memory for {scene_id}.",
        "branches": [
            {
                "branch_id": current_branch,
                "name": "Main continuity",
                "status": "active",
                "event_ids": event_ids,
            }
        ],
        "events": event_list,
    }


def append_memory_event(
    world_memory: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    scene_graph: Mapping[str, Any] | None = None,
    branch_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a World Memory copy with one event appended and validated."""
    updated = copy.deepcopy(dict(world_memory))
    events = updated.get("events")
    if not isinstance(events, list):
        return updated, [
            _memory_diagnostic(
                "M1009",
                "invalid_events_container",
                "/events",
                "World Memory events must be an array before appending.",
            )
        ]
    new_event = copy.deepcopy(dict(event))
    events.append(new_event)

    new_event_id = _string_field(new_event, "event_id")
    target_branch = branch_id or _string_field(new_event, "branch_id") or _string_field(updated, "current_branch")
    if new_event_id and target_branch:
        for _index, branch in _items(updated, "branches"):
            if _string_field(branch, "branch_id") != target_branch:
                continue
            branch_events = branch.get("event_ids")
            if isinstance(branch_events, list) and new_event_id not in branch_events:
                branch_events.append(new_event_id)
            break

    return updated, validate_world_memory(updated, scene_graph=scene_graph)


def _event_idempotency_key(event: Mapping[str, Any]) -> str | None:
    direct = _string_field(event, "idempotency_key")
    if direct:
        return direct
    metadata = event.get("metadata")
    if isinstance(metadata, Mapping):
        key = metadata.get("idempotency_key")
        return key if isinstance(key, str) else None
    return None


def append_memory_event_idempotent(
    world_memory: Mapping[str, Any],
    event: Mapping[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Return a World Memory copy with a redacted event appended at most once."""
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("idempotency_key must be a non-empty string")

    updated = copy.deepcopy(dict(world_memory))
    events = updated.get("events")
    if not isinstance(events, list):
        raise ValueError("World Memory events must be an array before appending")

    for existing in events:
        if isinstance(existing, Mapping) and _event_idempotency_key(existing) == idempotency_key:
            return updated

    new_event = redact_memory_payload(dict(event))
    if not isinstance(new_event, dict):
        raise ValueError("memory event root must be a JSON object")
    metadata = new_event.get("metadata")
    if isinstance(metadata, Mapping):
        new_metadata = redact_memory_payload(dict(metadata))
    else:
        new_metadata = {}
    if not isinstance(new_metadata, dict):
        new_metadata = {}
    new_metadata["idempotency_key"] = idempotency_key
    new_event["metadata"] = new_metadata

    appended, diagnostics = append_memory_event(updated, new_event)
    if diagnostics:
        codes = ", ".join(str(diagnostic.get("code", "unknown")) for diagnostic in diagnostics)
        raise ValueError(f"World Memory event append failed validation: {codes}")
    return appended


def _rejected_patch_event_id(patch: Mapping[str, Any]) -> str:
    patch_id = patch.get("patch_id")
    body = patch_id if isinstance(patch_id, str) else "patch_unknown"
    return f"mem_{clamp_id_body(f'rejected_{body}')}"


def _patch_affected_ids(patch: Mapping[str, Any]) -> list[str]:
    affected: list[str] = []
    target_id = patch.get("target_id")
    if isinstance(target_id, str):
        affected.append(target_id)
    continuity = patch.get("continuity")
    if isinstance(continuity, Mapping):
        preserved_ids = continuity.get("preserved_ids")
        if isinstance(preserved_ids, list):
            affected.extend(item for item in preserved_ids if isinstance(item, str))

    seen: set[str] = set()
    result: list[str] = []
    for value in affected:
        if value in seen or not _world_memory_entity_ref(value):
            continue
        seen.add(value)
        result.append(value)
    return result


def record_rejected_patch(
    world_memory: Mapping[str, Any],
    patch: Mapping[str, Any],
    diagnostics: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    """Record a rejected Scene Patch attempt as a redacted World Memory event."""
    patch_id = patch.get("patch_id")
    patch_id_text = patch_id if isinstance(patch_id, str) else "patch_unknown"
    scope = patch.get("scope")
    scope_text = scope if isinstance(scope, str) else "scene"
    world_scope = "object" if scope_text == "asset" else scope_text
    if world_scope not in {
        "scene",
        "region",
        "object",
        "camera",
        "material",
        "light",
        "curiosity_anchor",
        "hidden_state",
        "relationship",
        "branch",
        "patch",
        "render",
        "validation",
        "export",
        "build",
    }:
        world_scope = "patch"

    event: dict[str, Any] = {
        "event_id": _rejected_patch_event_id(patch),
        "type": "patch",
        "scope": world_scope,
        "text": f"Rejected Scene Patch {patch_id_text}: {reason}",
        "visibility": "private",
        "source": f"scene_patch:{patch_id_text}:rejected",
        "metadata": {
            "status": "rejected",
            "reason": reason,
            "scene_patch_scope": scope_text,
            "target_id": str(patch.get("target_id", "")),
            "operation_count": len(patch.get("operations", [])) if isinstance(patch.get("operations"), list) else 0,
            "diagnostics": diagnostics,
            "rejected_patch": dict(patch),
        },
    }
    if isinstance(patch_id, str) and patch_id.startswith("patch_"):
        event["patch_id"] = patch_id
    affected_ids = _patch_affected_ids(patch)
    if affected_ids:
        event["affected_ids"] = affected_ids
    continuity = patch.get("continuity")
    if isinstance(continuity, Mapping):
        branch_name = continuity.get("branch_name")
        if isinstance(branch_name, str):
            event["branch_id"] = branch_name

    return append_memory_event_idempotent(
        world_memory,
        event,
        f"rejected_patch:{patch_id_text}:{reason}",
    )


__all__ = [
    "MEMORY_REF_COLLECTIONS",
    "append_memory_event",
    "append_memory_event_idempotent",
    "check_world_memory",
    "create_world_memory",
    "load_and_validate_world_memory",
    "record_rejected_patch",
    "redact_memory_payload",
    "validate_world_memory",
]
