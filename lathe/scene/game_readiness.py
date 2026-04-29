"""Game-readiness metadata helpers for Wonder scenes."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from .provenance import find_forbidden_secret_metadata

GAME_READINESS_VERSION = "lathe.game_readiness.v1"
GAME_READINESS_SCHEMA_FILENAME = "game_readiness.schema.json"
GAME_READINESS_CONTRACT = "game_readiness"

DEFAULT_COLLISION_REQUIRED_ROLES: tuple[str, ...] = (
    "architecture",
    "environment_structure",
    "hero_prop",
    "interactive",
    "navigation",
)
INTERACTABLE_ROLES: tuple[str, ...] = ("interactive",)
_FALSE_MODES = {"", "false", "none", "off", "no", "disabled"}
_SNAP_POINT_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _schema_root(filename: str) -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / filename
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{filename}")


def get_game_readiness_schema() -> dict[str, Any]:
    """Return the committed game-readiness JSON Schema."""
    schema_path = _schema_root(GAME_READINESS_SCHEMA_FILENAME) / GAME_READINESS_SCHEMA_FILENAME
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    contract: str = GAME_READINESS_CONTRACT,
    phase: str = "game_readiness_semantics",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": contract,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _schema_diagnostics(
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    code: str,
    contract: str,
    phase: str,
) -> list[dict[str, Any]]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            _diagnostic(
                code,
                "schema_validation",
                _json_pointer(*error.absolute_path),
                error.message,
                contract=contract,
                phase=phase,
            )
        )
    return diagnostics


def validate_game_readiness_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a game-readiness metadata payload."""
    return _schema_diagnostics(
        payload,
        schema=get_game_readiness_schema(),
        code="GAME_READINESS_SCHEMA_VALIDATION",
        contract=GAME_READINESS_CONTRACT,
        phase="game_readiness_schema",
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
    return value if isinstance(value, str) and value else None


def _bool_field(item: Mapping[str, Any], field: str) -> bool | None:
    value = item.get(field)
    return value if isinstance(value, bool) else None


def _readiness_records(
    game_readiness: Mapping[str, Any] | None,
) -> tuple[dict[str, tuple[int, Mapping[str, Any]]], list[dict[str, Any]]]:
    records: dict[str, tuple[int, Mapping[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    if game_readiness is None:
        return records, diagnostics
    objects = game_readiness.get("objects", [])
    if not isinstance(objects, list):
        return records, diagnostics
    for index, item in enumerate(objects):
        if not isinstance(item, Mapping):
            continue
        object_id = _string_field(item, "object_id")
        if object_id is None:
            continue
        previous = records.get(object_id)
        if previous is not None:
            diagnostics.append(
                _diagnostic(
                    "GR1005",
                    "duplicate_game_readiness_object",
                    _json_pointer("objects", index, "object_id"),
                    f"Game-readiness metadata contains duplicate object_id {object_id!r}.",
                    details={"object_id": object_id, "first_path": _json_pointer("objects", previous[0], "object_id")},
                )
            )
            continue
        records[object_id] = (index, item)
    return records, diagnostics


def _metadata_sources(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if readiness_record is not None:
        record_index, record = readiness_record
        yield _json_pointer("game_readiness", "objects", record_index), record
    for field in ("game_readiness", "gameplay", "metadata", "state"):
        value = item.get(field)
        if isinstance(value, Mapping):
            base_path = _json_pointer("objects", object_index, field)
            yield base_path, value
            for nested in ("game_readiness", "gameplay"):
                nested_value = value.get(nested)
                if isinstance(nested_value, Mapping):
                    yield f"{base_path}/{nested}", nested_value


def _truthy_metadata_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in _FALSE_MODES
    if isinstance(value, Mapping):
        present = value.get("present")
        if isinstance(present, bool):
            return present
        for key in ("type", "mode", "shape"):
            mode = value.get(key)
            if isinstance(mode, str):
                return mode.strip().lower() not in _FALSE_MODES
        return True
    return False


def _has_metadata(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
    *,
    object_keys: Sequence[str],
    mode_keys: Sequence[str],
) -> bool:
    for _base_path, source in _metadata_sources(object_index, item, readiness_record):
        for key in object_keys:
            if key in source and _truthy_metadata_value(source[key]):
                return True
        for key in mode_keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip().lower() not in _FALSE_MODES:
                return True
            if isinstance(value, bool) and value:
                return True
    return False


def _has_collision(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> bool:
    return _has_metadata(
        object_index,
        item,
        readiness_record,
        object_keys=("collision", "has_collision", "collision_present"),
        mode_keys=("collision_type", "collision_mode", "collision_shape"),
    )


def _has_pivot(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> bool:
    return _has_metadata(
        object_index,
        item,
        readiness_record,
        object_keys=("pivot", "has_pivot", "pivot_present", "pivot_point"),
        mode_keys=("pivot_mode", "pivot_type"),
    )


def _is_interactable(
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> bool:
    role = _string_field(item, "role")
    if role in INTERACTABLE_ROLES:
        return True
    affordances = item.get("affordances")
    if isinstance(affordances, list) and affordances:
        return True
    if readiness_record is not None and _bool_field(readiness_record[1], "interactable") is True:
        return True
    for field in ("game_readiness", "gameplay", "metadata", "state"):
        value = item.get(field)
        if isinstance(value, Mapping) and _bool_field(value, "interactable") is True:
            return True
    return False


def _requires_collision(
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
    required_roles: set[str],
) -> bool:
    if readiness_record is not None:
        collision = readiness_record[1].get("collision")
        if isinstance(collision, Mapping) and isinstance(collision.get("required"), bool):
            return bool(collision["required"])
    role = _string_field(item, "role")
    if role in required_roles:
        return True
    for _path, source in _metadata_sources(0, item, readiness_record):
        collision_required = _bool_field(source, "collision_required")
        if collision_required is not None:
            return collision_required
    return False


def _snap_point_entries(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> Iterator[tuple[str, object]]:
    for base_path, source in _metadata_sources(object_index, item, readiness_record):
        value = source.get("snap_points")
        if isinstance(value, list):
            for index, snap_point in enumerate(value):
                if isinstance(snap_point, str):
                    yield f"{base_path}/snap_points/{index}", snap_point
                elif isinstance(snap_point, Mapping):
                    yield f"{base_path}/snap_points/{index}/name", snap_point.get("name")
        socket_value = source.get("sockets")
        if isinstance(socket_value, list):
            for index, socket in enumerate(socket_value):
                if isinstance(socket, str):
                    yield f"{base_path}/sockets/{index}", socket
                elif isinstance(socket, Mapping):
                    yield f"{base_path}/sockets/{index}/name", socket.get("name")


def _check_snap_point_names(
    object_index: int,
    item: Mapping[str, Any],
    readiness_record: tuple[int, Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    object_id = _string_field(item, "object_id")
    for path, name in _snap_point_entries(object_index, item, readiness_record):
        if isinstance(name, str) and _SNAP_POINT_RE.fullmatch(name):
            continue
        diagnostics.append(
            _diagnostic(
                "GR1003",
                "invalid_snap_point_name",
                path,
                "Snap point and socket names must use lower snake-case identifiers.",
                details={"object_id": object_id, "name": name},
            )
        )
    return diagnostics


def _scene_object_ids(scene_graph: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for _index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        if object_id is not None:
            ids.add(object_id)
    return ids


def validate_scene_game_readiness(
    scene_graph: Mapping[str, Any],
    *,
    game_readiness: Mapping[str, Any] | None = None,
    required_collision_roles: Sequence[str] = DEFAULT_COLLISION_REQUIRED_ROLES,
    require_pivots_for_interactables: bool = True,
) -> list[dict[str, Any]]:
    """Return deterministic game-readiness diagnostics for a Scene Graph."""
    diagnostics: list[dict[str, Any]] = []
    if game_readiness is not None:
        diagnostics.extend(validate_game_readiness_payload(game_readiness))
        diagnostics.extend(
            find_forbidden_secret_metadata(
                game_readiness,
                contract=GAME_READINESS_CONTRACT,
                phase="game_readiness_metadata",
                code="GR9001",
            )
        )
    readiness_records, record_diagnostics = _readiness_records(game_readiness)
    diagnostics.extend(record_diagnostics)

    object_ids = _scene_object_ids(scene_graph)
    for object_id, (record_index, _record) in readiness_records.items():
        if object_id not in object_ids:
            diagnostics.append(
                _diagnostic(
                    "GR1004",
                    "unknown_game_readiness_object",
                    _json_pointer("objects", record_index, "object_id"),
                    f"Game-readiness metadata references unknown object_id {object_id!r}.",
                    details={"object_id": object_id},
                )
            )

    required_roles = set(required_collision_roles)
    for object_index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        readiness_record = readiness_records.get(object_id or "")
        role = _string_field(item, "role")
        if _requires_collision(item, readiness_record, required_roles) and not _has_collision(
            object_index, item, readiness_record
        ):
            diagnostics.append(
                _diagnostic(
                    "GR1001",
                    "missing_required_collision",
                    _json_pointer("objects", object_index),
                    f"Object {object_id!r} needs collision metadata for game-ready targets.",
                    details={"object_id": object_id, "role": role},
                )
            )
        if (
            require_pivots_for_interactables
            and _is_interactable(item, readiness_record)
            and not _has_pivot(object_index, item, readiness_record)
        ):
            diagnostics.append(
                _diagnostic(
                    "GR1002",
                    "missing_interactable_pivot",
                    _json_pointer("objects", object_index),
                    f"Interactable object {object_id!r} needs pivot metadata.",
                    details={"object_id": object_id, "role": role},
                )
        )
        diagnostics.extend(_check_snap_point_names(object_index, item, readiness_record))
        for path, metadata in _metadata_sources(object_index, item, readiness_record):
            if game_readiness is not None and path.startswith("/game_readiness/objects/"):
                continue
            diagnostics.extend(
                find_forbidden_secret_metadata(
                    metadata,
                    root_path=path,
                    contract=GAME_READINESS_CONTRACT,
                    phase="game_readiness_metadata",
                    code="GR9001",
                )
            )
    return diagnostics


check_scene_game_readiness = validate_scene_game_readiness
validate_game_readiness = validate_scene_game_readiness


__all__ = [
    "DEFAULT_COLLISION_REQUIRED_ROLES",
    "GAME_READINESS_CONTRACT",
    "GAME_READINESS_SCHEMA_FILENAME",
    "GAME_READINESS_VERSION",
    "INTERACTABLE_ROLES",
    "check_scene_game_readiness",
    "get_game_readiness_schema",
    "validate_game_readiness",
    "validate_game_readiness_payload",
    "validate_scene_game_readiness",
]
