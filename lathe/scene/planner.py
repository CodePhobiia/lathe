"""Deterministic Scene Graph planning helpers for Phase 8."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Literal

SCENE_PLAN_VERSION = "lathe.scene_plan.v1"
SCENE_PLAN_SCHEMA_FILENAME = "scene_plan.schema.json"
ScenePlanMode = Literal["preview", "final"]

_SOURCE_FIELDS = ("source_asset", "lathe_asset", "source_family", "source_kit")
_EMPTY_OVERRIDE_FINGERPRINT = "44136fa355b3678a"
_COMPOSITION_GROUP_FIELDS = (
    "composition_group",
    "scene_composition_group",
    "setpiece_group",
    "compose_group",
)
_COMPOSITION_OPT_IN_FIELDS = (
    "compose_as_setpiece",
    "scene_composition",
    "generate_setpiece_parent",
)

_MODE_BUDGETS: dict[ScenePlanMode, dict[str, Any]] = {
    "preview": {
        "max_objects": 32,
        "max_complexity": 320,
        "render_resolution": [1280, 720],
        "texture_resolution": 1024,
        "quality": "preview",
    },
    "final": {
        "max_objects": 128,
        "max_complexity": 1280,
        "render_resolution": [2048, 1152],
        "texture_resolution": 4096,
        "quality": "final",
    },
}

_RENDER_PASSES: dict[ScenePlanMode, list[str]] = {
    "preview": ["beauty", "object_id"],
    "final": ["beauty", "object_id", "depth", "normal", "material_id"],
}


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / SCENE_PLAN_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{SCENE_PLAN_SCHEMA_FILENAME}")


def get_scene_plan_schema() -> dict[str, Any]:
    """Return the committed Scene Plan JSON Schema."""
    return json.loads((_schema_root() / SCENE_PLAN_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def validate_scene_plan_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Scene Plan payload."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_scene_plan_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": "SCENE_PLAN_SCHEMA_VALIDATION",
                "severity": "error",
                "contract": "scene_plan",
                "path": _json_pointer(*error.absolute_path),
                "message": error.message,
            }
        )
    diagnostics.extend(_check_required_render_tasks(payload))
    diagnostics.extend(_check_unique_task_ids(payload))
    diagnostics.extend(_check_cache_key_entries(payload))
    return diagnostics


def compare_scene_plan_asset_reuse(
    base_plan: Mapping[str, Any],
    branch_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deterministic cross-branch asset cache reuse report."""
    base_cache = _cache_entries_by_key(base_plan)
    branch_cache = _cache_entries_by_key(branch_plan)
    diagnostics: list[dict[str, Any]] = []
    if base_plan.get("mode") != branch_plan.get("mode"):
        diagnostics.append(
            _diagnostic(
                "SP3101",
                "branch_reuse_mode_mismatch",
                "/branch_reuse",
                "Scene Plan branch reuse compares plans with different build modes.",
                details={"base_mode": base_plan.get("mode"), "branch_mode": branch_plan.get("mode")},
            )
        )

    reusable: list[dict[str, Any]] = []
    new: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []

    for cache_key in sorted(branch_cache):
        branch_entry = branch_cache[cache_key]
        if not branch_entry.get("shareable", False):
            skipped.append(_reuse_entry("non_shareable", cache_key, branch_entry=branch_entry))
            continue
        base_entry = base_cache.get(cache_key)
        if base_entry is None:
            new.append(_reuse_entry("new_asset_build", cache_key, branch_entry=branch_entry))
            continue
        if not base_entry.get("shareable", False):
            skipped.append(
                _reuse_entry(
                    "base_not_shareable",
                    cache_key,
                    base_entry=base_entry,
                    branch_entry=branch_entry,
                )
            )
            continue
        reusable.append(
            _reuse_entry(
                "reusable_asset_build",
                cache_key,
                base_entry=base_entry,
                branch_entry=branch_entry,
            )
        )

    for cache_key in sorted(set(base_cache) - set(branch_cache)):
        expired.append(_reuse_entry("base_only_asset_build", cache_key, base_entry=base_cache[cache_key]))

    return {
        "schema_version": "lathe.scene_plan_branch_reuse.v1",
        "base_plan_id": _string_field(base_plan, "plan_id") or "",
        "branch_plan_id": _string_field(branch_plan, "plan_id") or "",
        "mode": _string_field(branch_plan, "mode") or "",
        "summary": {
            "base_asset_tasks": len(base_cache),
            "branch_asset_tasks": len(branch_cache),
            "reusable_asset_tasks": len(reusable),
            "new_asset_tasks": len(new),
            "skipped_asset_tasks": len(skipped),
            "base_only_asset_tasks": len(expired),
            "reuse_ratio": round(len(reusable) / len(branch_cache), 4) if branch_cache else 0.0,
        },
        "reusable_asset_tasks": reusable,
        "new_asset_tasks": new,
        "skipped_asset_tasks": skipped,
        "base_only_asset_tasks": expired,
        "diagnostics": diagnostics,
    }


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "warning",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": "scene_plan",
        "phase": "scene_planning",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _collection_count(scene_graph: Mapping[str, Any], collection: str) -> int:
    raw = scene_graph.get(collection, [])
    return len(raw) if isinstance(raw, list) else 0


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _cache_entries_by_key(plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = plan.get("cache_keys", [])
    if not isinstance(entries, list):
        return {}
    by_key: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        cache_key = _string_field(entry, "cache_key")
        if cache_key is not None and cache_key not in by_key:
            by_key[cache_key] = entry
    return by_key


def _reuse_entry(
    status: str,
    cache_key: str,
    *,
    base_entry: Mapping[str, Any] | None = None,
    branch_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_entry = branch_entry or base_entry or {}
    return {
        "status": status,
        "cache_key": cache_key,
        "base_asset_task_id": _string_field(base_entry or {}, "asset_task_id") or "",
        "branch_asset_task_id": _string_field(branch_entry or {}, "asset_task_id") or "",
        "base_object_ids": list(base_entry.get("object_ids", [])) if isinstance(base_entry, Mapping) else [],
        "branch_object_ids": list(branch_entry.get("object_ids", [])) if isinstance(branch_entry, Mapping) else [],
        "source": dict(source_entry.get("source", {})) if isinstance(source_entry.get("source"), Mapping) else {},
    }


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


def _slug(value: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not slug:
        slug = "item"
    if not slug[0].isalpha():
        slug = f"x_{slug}"
    return slug[:max_length].rstrip("_") or "item"


def _slug_with_digest(value: str, *, max_slug: int = 64, digest_size: int = 10) -> str:
    slug = _slug(value, max_length=max_slug)
    return f"{slug}_{_fingerprint(value, size=digest_size)}"


def _check_unique_task_ids(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for collection in ("asset_tasks", "assembly_tasks", "render_tasks", "export_tasks"):
        tasks = payload.get(collection, [])
        if not isinstance(tasks, list):
            continue
        for index, task in enumerate(tasks):
            if not isinstance(task, Mapping):
                continue
            task_id = _string_field(task, "task_id")
            if task_id is None:
                continue
            path = _json_pointer(collection, index, "task_id")
            first_path = seen.get(task_id)
            if first_path is None:
                seen[task_id] = path
                continue
            diagnostics.append(
                _diagnostic(
                    "SP3001",
                    "duplicate_scene_plan_task_id",
                    path,
                    f"Scene Plan task_id {task_id!r} duplicates the task at {first_path}.",
                    severity="error",
                    details={"task_id": task_id, "first_path": first_path},
                )
            )
    return diagnostics


def _check_required_render_tasks(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    render_tasks = payload.get("render_tasks")
    if isinstance(render_tasks, list) and render_tasks:
        return []
    return [
        _diagnostic(
            "SP3002",
            "missing_render_task",
            "/render_tasks",
            "Scene Plan must include at least one deterministic render task for LLM authoring review.",
            severity="error",
        )
    ]


def _check_cache_key_entries(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    asset_tasks = payload.get("asset_tasks", [])
    cache_entries = payload.get("cache_keys", [])
    if not isinstance(asset_tasks, list) or not isinstance(cache_entries, list):
        return diagnostics

    tasks_by_cache_key: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for index, task in enumerate(asset_tasks):
        if not isinstance(task, Mapping):
            continue
        cache_key = _string_field(task, "cache_key")
        if cache_key is None:
            continue
        if cache_key in tasks_by_cache_key:
            first_index, _first_task = tasks_by_cache_key[cache_key]
            diagnostics.append(
                _diagnostic(
                    "SP3003",
                    "duplicate_asset_task_cache_key",
                    _json_pointer("asset_tasks", index, "cache_key"),
                    (
                        f"Scene Plan asset task cache_key {cache_key!r} duplicates "
                        f"asset_tasks/{first_index}."
                    ),
                    severity="error",
                    details={"cache_key": cache_key, "first_path": _json_pointer("asset_tasks", first_index)},
                )
            )
            continue
        tasks_by_cache_key[cache_key] = (index, task)

    seen_cache_entries: dict[str, int] = {}
    for index, entry in enumerate(cache_entries):
        if not isinstance(entry, Mapping):
            continue
        cache_key = _string_field(entry, "cache_key")
        if cache_key is None:
            continue
        if cache_key in seen_cache_entries:
            diagnostics.append(
                _diagnostic(
                    "SP3004",
                    "duplicate_scene_plan_cache_key_entry",
                    _json_pointer("cache_keys", index, "cache_key"),
                    (
                        f"Scene Plan cache_keys entry {cache_key!r} duplicates "
                        f"cache_keys/{seen_cache_entries[cache_key]}."
                    ),
                    severity="error",
                    details={"cache_key": cache_key, "first_path": _json_pointer("cache_keys", seen_cache_entries[cache_key])},
                )
            )
            continue
        seen_cache_entries[cache_key] = index
        task_record = tasks_by_cache_key.get(cache_key)
        if task_record is None:
            diagnostics.append(
                _diagnostic(
                    "SP3005",
                    "cache_key_entry_without_asset_task",
                    _json_pointer("cache_keys", index),
                    f"Scene Plan cache_keys entry {cache_key!r} has no matching asset task.",
                    severity="error",
                    details={"cache_key": cache_key},
                )
            )
            continue
        task_index, task = task_record
        mismatches = _cache_entry_mismatches(entry, task)
        if mismatches:
            diagnostics.append(
                _diagnostic(
                    "SP3006",
                    "cache_key_entry_asset_task_mismatch",
                    _json_pointer("cache_keys", index),
                    (
                        f"Scene Plan cache_keys entry {cache_key!r} does not match "
                        f"asset_tasks/{task_index}."
                    ),
                    severity="error",
                    details={"cache_key": cache_key, "asset_task_path": _json_pointer("asset_tasks", task_index), "fields": mismatches},
                )
            )

    for cache_key, (task_index, _task) in sorted(tasks_by_cache_key.items()):
        if cache_key in seen_cache_entries:
            continue
        diagnostics.append(
            _diagnostic(
                "SP3007",
                "missing_cache_key_entry_for_asset_task",
                _json_pointer("asset_tasks", task_index, "cache_key"),
                f"Scene Plan asset task cache_key {cache_key!r} is missing from cache_keys.",
                severity="error",
                details={"cache_key": cache_key, "asset_task_path": _json_pointer("asset_tasks", task_index)},
            )
        )
    return diagnostics


def _cache_entry_mismatches(entry: Mapping[str, Any], task: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    expected_shareable = (
        isinstance(task.get("source"), Mapping) and task["source"].get("kind") != "generated_fallback"
    )
    comparisons = {
        "asset_task_id": task.get("task_id"),
        "cache_key": task.get("cache_key"),
        "object_ids": task.get("object_ids"),
        "source": _normal_json(task.get("source", {})),
        "shareable": expected_shareable,
    }
    for field, expected in comparisons.items():
        actual = _normal_json(entry.get(field)) if field == "source" else entry.get(field)
        if actual != expected:
            mismatches.append(field)
    return mismatches


def _stable_object_id(index: int, item: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    object_id = _string_field(item, "object_id")
    if object_id is not None:
        return object_id, []
    fallback = f"obj_unidentified_{index:03d}"
    return fallback, [
        _diagnostic(
            "SP1000",
            "missing_object_id",
            _json_pointer("objects", index),
            f"Object at index {index} is missing object_id; using {fallback!r} for planning.",
            details={"fallback_object_id": fallback},
        )
    ]


def _generated_intent(object_id: str, item: Mapping[str, Any]) -> dict[str, Any]:
    tags = item.get("semantic_tags")
    return {
        "object_id": object_id,
        "name": _string_field(item, "name") or object_id,
        "role": _string_field(item, "role") or "dressing_prop",
        "semantic_tags": sorted(tag for tag in tags if isinstance(tag, str)) if isinstance(tags, list) else [],
    }


def _object_source(
    index: int,
    object_id: str,
    item: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provided = {field: item[field] for field in _SOURCE_FIELDS if isinstance(item.get(field), str) and item[field]}
    for field in _SOURCE_FIELDS:
        value = provided.get(field)
        if isinstance(value, str):
            source = {
                "kind": field,
                "ref": value,
                "generated": False,
                **provided,
            }
            return source, []

    source = {
        "kind": "generated_fallback",
        "ref": object_id,
        "generated": True,
        "generated_intent": _generated_intent(object_id, item),
    }
    return source, [
        _diagnostic(
            "SP1001",
            "missing_object_source_reference",
            _json_pointer("objects", index),
            (
                f"Object {object_id!r} has no source_asset, lathe_asset, source_family, or source_kit; "
                "planning a deterministic generated fallback asset task."
            ),
            details={"object_id": object_id, "fallback_source": "generated_fallback"},
        )
    ]


def _material_bindings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    bindings = [_normal_json(item) for item in value if isinstance(item, Mapping)]
    return sorted(bindings, key=lambda item: (str(item.get("slot", "")), str(item.get("material", "")), _canonical_json(item)))


def _asset_overrides(item: Mapping[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    bindings = _material_bindings(item.get("material_bindings"))
    if bindings:
        overrides["material_bindings"] = bindings

    state = item.get("state")
    if isinstance(state, Mapping) and state:
        overrides["state"] = _normal_json(state)
    surface_overrides = item.get("surface_overrides")
    if isinstance(surface_overrides, Mapping) and surface_overrides:
        overrides["surface_overrides"] = _normal_json(surface_overrides)
    return overrides


def _instance_overrides(item: Mapping[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for field in ("name", "role", "semantic_tags", "surface_overrides", "affordances", "provenance"):
        if field in item:
            overrides[field] = _normal_json(item[field])
    return overrides


def _object_complexity(item: Mapping[str, Any]) -> int:
    bindings = item.get("material_bindings")
    state = item.get("state")
    surface_overrides = item.get("surface_overrides")
    affordances = item.get("affordances")
    score = 8
    score += len(bindings) * 2 if isinstance(bindings, list) else 0
    score += len(state) if isinstance(state, Mapping) else 0
    score += len(surface_overrides) if isinstance(surface_overrides, Mapping) else 0
    score += len(affordances) * 2 if isinstance(affordances, list) else 0
    score += 3 if _string_field(item, "variant") else 0
    return score


def _object_state(item: Mapping[str, Any]) -> Mapping[str, Any]:
    state = item.get("state")
    return state if isinstance(state, Mapping) else {}


def _composition_group_id(item: Mapping[str, Any]) -> str:
    state = _object_state(item)
    for field in _COMPOSITION_GROUP_FIELDS:
        value = state.get(field)
        if isinstance(value, str) and value.strip():
            return _slug(value, max_length=48)
    if any(state.get(field) is True for field in _COMPOSITION_OPT_IN_FIELDS):
        for field in ("parent_object", "parent", "assembly_parent", "assembly_target"):
            value = state.get(field)
            if isinstance(value, str) and value.strip():
                return _slug(value, max_length=48)
        return "scene_setpiece"
    return ""


def _composition_asset_source(
    *,
    scene_id: str,
    group_id: str,
    object_ids: list[str],
) -> dict[str, Any]:
    ref = _slug(f"{scene_id}_{group_id}_setpiece", max_length=72)
    return {
        "kind": "generated_fallback",
        "ref": ref,
        "generated": True,
        "source_family": "procedural_setpiece",
        "generated_intent": {
            "composition_group": group_id,
            "composition_kind": "scene_connected_setpiece",
            "object_ids": list(object_ids),
            "object_count": len(object_ids),
        },
    }


def _composition_asset_overrides(
    *,
    group_id: str,
    object_ids: list[str],
) -> dict[str, Any]:
    return {
        "state": {
            "object_archetype": "setpiece",
            "setpiece": group_id,
            "scene_composition_group": group_id,
            "scene_composition_member_count": len(object_ids),
            "child_socket_count": len(object_ids),
            "module_socket_count": len(object_ids),
        }
    }


def _composition_groups(object_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in object_records:
        item = record.get("item")
        if not isinstance(item, Mapping):
            continue
        group_id = _composition_group_id(item)
        if not group_id:
            continue
        groups.setdefault(group_id, []).append(record)
    return {
        group_id: records
        for group_id, records in sorted(groups.items())
        if len([record for record in records if str(record.get("object_id") or "")]) >= 2
    }


def _vector3_from_transform(item: Mapping[str, Any], field: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    transform = item.get("transform")
    raw = transform.get(field) if isinstance(transform, Mapping) else None
    if not isinstance(raw, list | tuple):
        return default
    padded = list(raw[:3]) + [default[0], default[1], default[2]]
    out: list[float] = []
    for index, fallback in enumerate(default):
        try:
            out.append(float(padded[index]))
        except (TypeError, ValueError):
            out.append(float(fallback))
    return (out[0], out[1], out[2])


def _composition_object_id(scene_id: str, group_id: str) -> str:
    body = _slug(f"{scene_id}_{group_id}_setpiece", max_length=76)
    return f"obj_{body}"


def _composition_group_transform(records: list[dict[str, Any]]) -> dict[str, list[float]]:
    items = [record.get("item") for record in records if isinstance(record.get("item"), Mapping)]
    positions = [_vector3_from_transform(item, "position", (0.0, 0.0, 0.0)) for item in items]
    scales = [_vector3_from_transform(item, "scale", (1.0, 1.0, 1.0)) for item in items]
    if not positions:
        return {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    mins = [
        min(float(position[axis]) - max(0.5, float(scale[axis]) * 0.5) for position, scale in zip(positions, scales))
        for axis in range(3)
    ]
    maxs = [
        max(float(position[axis]) + max(0.5, float(scale[axis]) * 0.5) for position, scale in zip(positions, scales))
        for axis in range(3)
    ]
    center = [round((mins[axis] + maxs[axis]) * 0.5, 6) for axis in range(3)]
    extents = [round(max(1.0, maxs[axis] - mins[axis]), 6) for axis in range(3)]
    return {"position": center, "rotation": [0.0, 0.0, 0.0], "scale": extents}


def _composition_group_region(records: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for record in records:
        item = record.get("item")
        if not isinstance(item, Mapping):
            continue
        region = _string_field(item, "region")
        if region is not None:
            counts[region] = counts.get(region, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _cache_key(
    *,
    mode: ScenePlanMode,
    source: Mapping[str, Any],
    variant: str | None,
    overrides: Mapping[str, Any],
) -> str:
    components = {
        "schema_version": SCENE_PLAN_VERSION,
        "mode": mode,
        "source": source,
        "variant": variant or "default",
        "asset_overrides": overrides,
    }
    return (
        f"scene_asset.v1:{mode}:{_slug(str(source['kind']))}:"
        f"{_slug(str(source['ref']))}:{_slug(variant or 'default')}:{_fingerprint(components)}"
    )


def _composition_asset_tasks(
    *,
    mode: ScenePlanMode,
    scene_id: str,
    composition_groups: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for group_id, records in sorted(composition_groups.items()):
        object_ids = sorted(str(record["object_id"]) for record in records if str(record.get("object_id") or ""))
        source = _composition_asset_source(scene_id=scene_id, group_id=group_id, object_ids=object_ids)
        overrides = _composition_asset_overrides(group_id=group_id, object_ids=object_ids)
        cache_key = _cache_key(mode=mode, source=source, variant=None, overrides=overrides)
        group = {
            "source": source,
            "variant": None,
            "asset_overrides": overrides,
            "override_fingerprint": _fingerprint(overrides),
            "estimated_complexity": sum(int(record.get("estimated_complexity") or 0) for record in records)
            + len(object_ids) * 2,
            "object_ids": object_ids,
        }
        task = _asset_task(
            task_id=_asset_task_id(source, cache_key),
            mode=mode,
            cache_key=cache_key,
            group=group,
        )
        task["requires_unique_build"] = True
        task["uniqueness_reasons"] = ["scene_composition_group", group_id]
        tasks.append(task)
    return tasks


def _composition_assembly_tasks(
    *,
    mode: ScenePlanMode,
    scene_id: str,
    composition_tasks: list[dict[str, Any]],
    composition_groups: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for asset_task in sorted(composition_tasks, key=lambda task: str(task.get("task_id") or "")):
        source = asset_task.get("source") if isinstance(asset_task.get("source"), Mapping) else {}
        generated_intent = source.get("generated_intent") if isinstance(source.get("generated_intent"), Mapping) else {}
        group_id = str(generated_intent.get("composition_group") or "")
        records = list(composition_groups.get(group_id, []))
        if not group_id or not records:
            continue
        object_ids = sorted(str(record["object_id"]) for record in records if str(record.get("object_id") or ""))
        object_id = _composition_object_id(scene_id, group_id)
        task_id = f"assembly_task_{_slug_with_digest(object_id, max_slug=72, digest_size=10)}"
        transform = _composition_group_transform(records)
        instance_overrides = {
            "name": f"{group_id.replace('_', ' ').title()} Setpiece",
            "role": "environment_structure",
            "semantic_tags": [
                "scene_composition",
                "generated_setpiece",
                f"composition_group:{group_id}",
            ],
            "provenance": {
                "created_by": "lathe.scene.planner",
                "created_from": "scene_composition_group",
                "composition_group": group_id,
                "member_object_ids": object_ids,
            },
        }
        tasks.append(
            {
                "task_id": task_id,
                "task_type": "scene_assembly",
                "mode": mode,
                "object_id": object_id,
                "asset_task_id": str(asset_task.get("task_id") or ""),
                "cache_key": str(asset_task.get("cache_key") or ""),
                "region": _composition_group_region(records),
                "transform": _normal_json(transform),
                "asset_overrides": dict(asset_task.get("asset_overrides") or {}),
                "instance_overrides": _normal_json(instance_overrides),
                "depends_on": [str(asset_task.get("task_id") or "")],
            }
        )
    return tasks


def _plan_id(scene_graph: Mapping[str, Any], *, mode: ScenePlanMode, scene_id: str) -> str:
    digest = _fingerprint({"mode": mode, "scene_graph": scene_graph}, size=12)
    body = _slug(scene_id, max_length=64)
    return f"plan_{body}_{digest}"


def _asset_task_id(source: Mapping[str, Any], cache_key: str) -> str:
    return f"asset_task_{_slug(str(source['ref']), max_length=36)}_{_fingerprint(cache_key, size=12)}"


def _asset_group_sort_key(item: tuple[str, Mapping[str, Any]]) -> tuple[str, str, str, str]:
    cache_key, group = item
    object_ids = sorted(str(object_id) for object_id in group["object_ids"])
    source = group["source"]
    return (
        object_ids[0] if object_ids else "",
        str(source["kind"]),
        str(source["ref"]),
        cache_key,
    )


def _asset_task(
    *,
    task_id: str,
    mode: ScenePlanMode,
    cache_key: str,
    group: Mapping[str, Any],
) -> dict[str, Any]:
    object_ids = sorted(str(object_id) for object_id in group["object_ids"])
    source = dict(group["source"])
    variant = group["variant"]
    overrides = dict(group["asset_overrides"])
    uniqueness_reasons: list[str] = []
    if source.get("kind") == "generated_fallback":
        uniqueness_reasons.append("generated_fallback")
    if variant is not None:
        uniqueness_reasons.append("variant")
    if group["override_fingerprint"] != _EMPTY_OVERRIDE_FINGERPRINT:
        uniqueness_reasons.append("asset_overrides")
    return {
        "task_id": task_id,
        "task_type": "asset_build",
        "mode": mode,
        "cache_key": cache_key,
        "source": source,
        "object_ids": object_ids,
        "variant": variant,
        "asset_overrides": overrides,
        "override_fingerprint": str(group["override_fingerprint"]),
        "estimated_complexity": int(group["estimated_complexity"]),
        "requires_unique_build": len(object_ids) == 1 and bool(uniqueness_reasons),
        "uniqueness_reasons": uniqueness_reasons,
    }


def _assembly_task(
    *,
    mode: ScenePlanMode,
    record: Mapping[str, Any],
    asset_task_id: str,
) -> dict[str, Any]:
    object_id = str(record["object_id"])
    item = record["item"]
    region = _string_field(item, "region")
    return {
        "task_id": f"assembly_task_{_slug_with_digest(object_id, max_slug=64)}",
        "task_type": "scene_assembly",
        "mode": mode,
        "object_id": object_id,
        "asset_task_id": asset_task_id,
        "cache_key": record["cache_key"],
        "region": region,
        "transform": _normal_json(item.get("transform", {})),
        "asset_overrides": dict(record["asset_overrides"]),
        "instance_overrides": _instance_overrides(item),
        "depends_on": [asset_task_id],
    }


def _render_tasks(scene_graph: Mapping[str, Any], *, mode: ScenePlanMode, depends_on: list[str]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    budget = _MODE_BUDGETS[mode]
    has_topdown_debug = False
    for _index, camera in sorted(_items(scene_graph, "cameras"), key=lambda item: _string_field(item[1], "camera_id") or ""):
        camera_id = _string_field(camera, "camera_id")
        if camera_id is None:
            continue
        framing = _string_field(camera, "framing")
        has_topdown_debug = has_topdown_debug or camera_id == "camera_topdown_debug" or framing == "topdown"
        tasks.append(
            {
                "task_id": f"render_task_{_slug_with_digest(camera_id, max_slug=64)}",
                "task_type": "scene_render",
                "mode": mode,
                "camera_id": camera_id,
                "target": _string_field(camera, "target"),
                "framing": framing,
                "passes": list(_RENDER_PASSES[mode]),
                "resolution": list(budget["render_resolution"]),
                "depends_on": list(depends_on),
            }
        )
    if not has_topdown_debug:
        camera_id = "camera_topdown_debug"
        tasks.append(
            {
                "task_id": f"render_task_{_slug_with_digest(camera_id, max_slug=64)}",
                "task_type": "scene_render",
                "mode": mode,
                "camera_id": camera_id,
                "target": _layout_focal_point(scene_graph),
                "framing": "topdown",
                "passes": list(_RENDER_PASSES[mode]),
                "resolution": list(budget["render_resolution"]),
                "depends_on": list(depends_on),
            }
        )
    return tasks


def _layout_focal_point(scene_graph: Mapping[str, Any]) -> str | None:
    layout = scene_graph.get("layout")
    if isinstance(layout, Mapping):
        focal_point = _string_field(layout, "focal_point")
        if focal_point is not None:
            return focal_point
    for _index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        if object_id is not None:
            return object_id
    return None


def _export_tasks(
    scene_graph: Mapping[str, Any],
    *,
    mode: ScenePlanMode,
    render_task_ids: list[str],
    assembly_task_ids: list[str],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    export_items = sorted(
        _items(scene_graph, "exports"),
        key=lambda item: (
            _string_field(item[1], "target") or "",
            _string_field(item[1], "format") or "",
            _string_field(item[1], "path") or "",
            item[0],
        ),
    )
    for index, export in export_items:
        target = _string_field(export, "target") or "scene_graph"
        export_format = _string_field(export, "format") or target
        path = _string_field(export, "path") or f"exports/{target}.{export_format}"
        fingerprint = _fingerprint({"target": target, "format": export_format, "path": path}, size=10)
        depends_on = render_task_ids if target in {"render", "scene_package"} else assembly_task_ids
        tasks.append(
            {
                "task_id": f"export_task_{_slug(target, max_length=32)}_{_slug(export_format, max_length=24)}_{fingerprint}",
                "task_type": "scene_export",
                "mode": mode,
                "target": target,
                "format": export_format,
                "path": path,
                "metadata": _normal_json(export.get("metadata", {})),
                "source_index": index,
                "depends_on": list(depends_on),
            }
        )
    return tasks


def _budget_warnings(
    *,
    mode: ScenePlanMode,
    object_count: int,
    estimated_complexity: int,
) -> list[dict[str, Any]]:
    budget = _MODE_BUDGETS[mode]
    warnings: list[dict[str, Any]] = []
    if object_count > budget["max_objects"]:
        warnings.append(
            _diagnostic(
                "SP2001",
                "object_count_exceeds_mode_budget",
                "/objects",
                (
                    f"Scene has {object_count} objects, above the {mode} mode budget "
                    f"of {budget['max_objects']} objects."
                ),
                details={"object_count": object_count, "max_objects": budget["max_objects"], "mode": mode},
            )
        )
    if estimated_complexity > budget["max_complexity"]:
        warnings.append(
            _diagnostic(
                "SP2002",
                "complexity_exceeds_mode_budget",
                "/",
                (
                    f"Scene rough complexity score {estimated_complexity} is above the {mode} mode budget "
                    f"of {budget['max_complexity']}."
                ),
                details={
                    "estimated_complexity": estimated_complexity,
                    "max_complexity": budget["max_complexity"],
                    "mode": mode,
                },
            )
        )
    return warnings


def plan_scene(
    scene_graph: Mapping[str, Any],
    *,
    mode: ScenePlanMode = "preview",
    reuse_from_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic Scene Plan from existing Scene Graph JSON."""
    if mode not in _MODE_BUDGETS:
        supported = ", ".join(sorted(_MODE_BUDGETS))
        raise ValueError(f"mode must be one of: {supported}")

    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    diagnostics: list[dict[str, Any]] = []
    object_records: list[dict[str, Any]] = []
    asset_groups: dict[str, dict[str, Any]] = {}

    sorted_objects = sorted(
        _items(scene_graph, "objects"),
        key=lambda item: (_string_field(item[1], "object_id") is None, _string_field(item[1], "object_id") or item[0]),
    )
    for index, item in sorted_objects:
        object_id, id_diagnostics = _stable_object_id(index, item)
        diagnostics.extend(id_diagnostics)
        source, source_diagnostics = _object_source(index, object_id, item)
        diagnostics.extend(source_diagnostics)
        variant = _string_field(item, "variant")
        asset_overrides = _asset_overrides(item)
        override_fingerprint = _fingerprint(asset_overrides)
        cache_key = _cache_key(mode=mode, source=source, variant=variant, overrides=asset_overrides)
        object_complexity = _object_complexity(item)

        group = asset_groups.setdefault(
            cache_key,
            {
                "source": source,
                "variant": variant,
                "asset_overrides": asset_overrides,
                "override_fingerprint": override_fingerprint,
                "estimated_complexity": 0,
                "object_ids": [],
            },
        )
        group["estimated_complexity"] = int(group["estimated_complexity"]) + object_complexity
        group["object_ids"].append(object_id)
        object_records.append(
            {
                "object_id": object_id,
                "item": item,
                "cache_key": cache_key,
                "asset_overrides": asset_overrides,
                "estimated_complexity": object_complexity,
            }
        )

    asset_task_ids: dict[str, str] = {
        cache_key: _asset_task_id(group["source"], cache_key) for cache_key, group in asset_groups.items()
    }
    asset_tasks = [
        _asset_task(task_id=asset_task_ids[cache_key], mode=mode, cache_key=cache_key, group=group)
        for cache_key, group in sorted(asset_groups.items(), key=_asset_group_sort_key)
    ]
    composition_groups = _composition_groups(object_records)
    composition_asset_tasks = _composition_asset_tasks(
        mode=mode,
        scene_id=scene_id,
        composition_groups=composition_groups,
    )
    asset_tasks.extend(composition_asset_tasks)
    assembly_tasks = [
        _assembly_task(mode=mode, record=record, asset_task_id=asset_task_ids[str(record["cache_key"])])
        for record in sorted(object_records, key=lambda item: str(item["object_id"]))
    ]
    assembly_tasks.extend(
        _composition_assembly_tasks(
            mode=mode,
            scene_id=scene_id,
            composition_tasks=composition_asset_tasks,
            composition_groups=composition_groups,
        )
    )
    assembly_tasks = sorted(assembly_tasks, key=lambda item: str(item.get("task_id") or ""))
    assembly_task_ids = [task["task_id"] for task in assembly_tasks]
    render_tasks = _render_tasks(scene_graph, mode=mode, depends_on=assembly_task_ids)
    render_task_ids = [task["task_id"] for task in render_tasks]
    export_tasks = _export_tasks(
        scene_graph,
        mode=mode,
        render_task_ids=render_task_ids,
        assembly_task_ids=assembly_task_ids,
    )
    estimated_complexity = (
        sum(int(task["estimated_complexity"]) for task in asset_tasks)
        + _collection_count(scene_graph, "relationships") * 2
        + _collection_count(scene_graph, "lights") * 4
        + _collection_count(scene_graph, "cameras") * 6
    )
    budget_warnings = _budget_warnings(
        mode=mode,
        object_count=len(object_records),
        estimated_complexity=estimated_complexity,
    )
    diagnostics.extend(budget_warnings)
    warnings = [diagnostic for diagnostic in diagnostics if diagnostic["severity"] == "warning"]

    cache_keys = [
        {
            "cache_key": task["cache_key"],
            "asset_task_id": task["task_id"],
            "object_ids": list(task["object_ids"]),
            "source": dict(task["source"]),
            "shareable": task["source"].get("kind") != "generated_fallback",
        }
        for task in asset_tasks
    ]

    plan: dict[str, Any] = {
        "schema_version": SCENE_PLAN_VERSION,
        "plan_id": _plan_id(scene_graph, mode=mode, scene_id=scene_id),
        "scene_id": scene_id,
    }
    source_brief_id = _string_field(scene_graph, "brief_id")
    if source_brief_id is not None:
        plan["source_brief_id"] = source_brief_id
    source_prompt = _string_field(scene_graph, "prompt")
    if source_prompt is not None:
        plan["source_prompt"] = source_prompt
    plan.update(
        {
            "mode": mode,
            "metadata": {
                "planner": "lathe.scene.planner",
                "planner_version": 1,
                "budgets": dict(_MODE_BUDGETS[mode]),
                "counts": {
                    "objects": len(object_records),
                    "asset_tasks": len(asset_tasks),
                    "assembly_tasks": len(assembly_tasks),
                    "render_tasks": len(render_tasks),
                    "export_tasks": len(export_tasks),
                    "materials": _collection_count(scene_graph, "materials"),
                    "lights": _collection_count(scene_graph, "lights"),
                    "cameras": _collection_count(scene_graph, "cameras"),
                },
                "estimated_complexity": estimated_complexity,
            },
            "asset_tasks": asset_tasks,
            "assembly_tasks": assembly_tasks,
            "render_tasks": render_tasks,
            "export_tasks": export_tasks,
            "warnings": warnings,
            "diagnostics": diagnostics,
            "cache_keys": cache_keys,
        }
    )
    if reuse_from_plan is not None:
        plan["branch_reuse"] = compare_scene_plan_asset_reuse(reuse_from_plan, plan)
    return plan


def load_and_plan_scene_graph(path: str | Path, *, mode: ScenePlanMode = "preview") -> dict[str, Any]:
    """Load a Scene Graph JSON file and return its deterministic Scene Plan."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Scene Graph root must be a JSON object: {path}")
    return plan_scene(payload, mode=mode)


__all__ = [
    "SCENE_PLAN_SCHEMA_FILENAME",
    "SCENE_PLAN_VERSION",
    "ScenePlanMode",
    "compare_scene_plan_asset_reuse",
    "get_scene_plan_schema",
    "load_and_plan_scene_graph",
    "plan_scene",
    "validate_scene_plan_payload",
]
