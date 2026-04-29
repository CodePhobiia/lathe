"""Provenance and safety metadata helpers for Wonder scene payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

ASSET_PROVENANCE_SCENE_VERSION = "lathe.asset_provenance_scene.v1"
ASSET_PROVENANCE_SCENE_SCHEMA_FILENAME = "asset_provenance_scene.schema.json"
ASSET_PROVENANCE_SCENE_CONTRACT = "asset_provenance_scene"

PROVENANCE_SOURCES: tuple[str, ...] = (
    "deterministic_lathe",
    "provider_generated",
    "user_supplied",
    "licensed_reference",
    "mixed",
)

_SECRET_KEY_EXACT = {
    "api_key",
    "apikey",
    "access_key",
    "authorization",
    "bearer",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "passwd",
    "private_key",
    "refresh_token",
    "secret",
    "secret_key",
    "session_token",
    "signing_key",
    "token",
}
_SECRET_KEY_COMPACT = {re.sub(r"[^a-z0-9]", "", key) for key in _SECRET_KEY_EXACT}
_SECRET_VALUE_RE = re.compile(
    r"("
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|\b(?:sk|pk)-[A-Za-z0-9_=-]{8,}"
    r"|\bgh[pousr]_[A-Za-z0-9_]{16,}"
    r"|\bglpat-[A-Za-z0-9_-]{8,}"
    r"|\bxox[baprs]-[A-Za-z0-9-]{8,}"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r")",
    re.IGNORECASE,
)


def _schema_root(filename: str) -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / filename
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{filename}")


def get_asset_provenance_scene_schema() -> dict[str, Any]:
    """Return the committed asset provenance scene JSON Schema."""
    schema_path = _schema_root(ASSET_PROVENANCE_SCENE_SCHEMA_FILENAME) / ASSET_PROVENANCE_SCENE_SCHEMA_FILENAME
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
    contract: str = ASSET_PROVENANCE_SCENE_CONTRACT,
    phase: str = "asset_provenance_scene_semantics",
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


def validate_asset_provenance_scene_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for an asset provenance scene payload."""
    return _schema_diagnostics(
        payload,
        schema=get_asset_provenance_scene_schema(),
        code="ASSET_PROVENANCE_SCHEMA_VALIDATION",
        contract=ASSET_PROVENANCE_SCENE_CONTRACT,
        phase="asset_provenance_scene_schema",
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


def _is_secret_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.strip().lower()
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    return normalized in _SECRET_KEY_EXACT or compact in _SECRET_KEY_COMPACT


def _is_secret_value(value: object) -> bool:
    return isinstance(value, str) and bool(_SECRET_VALUE_RE.search(value))


def _iter_metadata_fields(value: Any, path: str) -> Iterator[tuple[str, str, object, str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_path = f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}" if path != "/" else _json_pointer(key)
            if _is_secret_key(key):
                yield key_path, str(key), item, "key"
            if _is_secret_value(item):
                yield key_path, str(key), item, "value"
            yield from _iter_metadata_fields(item, key_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            child_path = f"{path}/{index}" if path != "/" else _json_pointer(index)
            if _is_secret_value(item):
                yield child_path, str(index), item, "value"
            yield from _iter_metadata_fields(item, child_path)


def find_forbidden_secret_metadata(
    payload: Mapping[str, Any],
    *,
    root_path: str = "/",
    contract: str = ASSET_PROVENANCE_SCENE_CONTRACT,
    phase: str = "provenance_safety_metadata",
    code: str = "PR9001",
) -> list[dict[str, Any]]:
    """Return diagnostics for secret-bearing keys or values in metadata payloads.

    Diagnostics deliberately do not echo the detected value.
    """
    diagnostics: list[dict[str, Any]] = []
    for path, key, _value, reason in _iter_metadata_fields(payload, root_path):
        diagnostics.append(
            _diagnostic(
                code,
                "forbidden_secret_metadata",
                path,
                "Metadata contains a field name or value that looks like a credential.",
                details={"field": key, "reason": reason},
                contract=contract,
                phase=phase,
            )
        )
    return diagnostics


def _metadata_surfaces(scene_graph: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for field in ("metadata", "provenance", "safety", "content_safety", "brand_ip"):
        value = scene_graph.get(field)
        if isinstance(value, Mapping):
            yield _json_pointer(field), value

    for object_index, item in _items(scene_graph, "objects"):
        for field in (
            "provenance",
            "metadata",
            "game_readiness",
            "gameplay",
            "safety",
            "content_safety",
            "brand_ip",
            "state",
        ):
            value = item.get(field)
            if isinstance(value, Mapping):
                yield _json_pointer("objects", object_index, field), value

    for export_index, item in _items(scene_graph, "exports"):
        value = item.get("metadata")
        if isinstance(value, Mapping):
            yield _json_pointer("exports", export_index, "metadata"), value


def _check_object_provenance(item: Mapping[str, Any], index: int) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    object_id = _string_field(item, "object_id")
    provenance = item.get("provenance")
    if not isinstance(provenance, Mapping):
        diagnostics.append(
            _diagnostic(
                "PR1001",
                "missing_object_provenance",
                _json_pointer("objects", index, "provenance"),
                f"Object {object_id!r} is missing provenance metadata.",
                details={"object_id": object_id},
            )
        )
        return diagnostics

    source = _string_field(provenance, "source")
    if source == "provider_generated" and not _string_field(provenance, "provider"):
        diagnostics.append(
            _diagnostic(
                "PR1002",
                "missing_provider_provenance",
                _json_pointer("objects", index, "provenance", "provider"),
                f"Provider-generated object {object_id!r} must name the provider in provenance metadata.",
                details={"object_id": object_id, "source": source},
            )
        )
    if source == "licensed_reference" and not _string_field(provenance, "license"):
        diagnostics.append(
            _diagnostic(
                "PR1003",
                "missing_reference_license",
                _json_pointer("objects", index, "provenance", "license"),
                f"Licensed-reference object {object_id!r} should name the source license.",
                severity="warning",
                details={"object_id": object_id, "source": source},
            )
        )
    return diagnostics


def validate_scene_provenance(
    scene_graph: Mapping[str, Any],
    *,
    provenance_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic provenance and metadata-safety diagnostics for a Scene Graph."""
    diagnostics: list[dict[str, Any]] = []
    if provenance_payload is not None:
        diagnostics.extend(validate_asset_provenance_scene_payload(provenance_payload))
        diagnostics.extend(find_forbidden_secret_metadata(provenance_payload))

    for index, item in _items(scene_graph, "objects"):
        diagnostics.extend(_check_object_provenance(item, index))

    for path, metadata in _metadata_surfaces(scene_graph):
        diagnostics.extend(find_forbidden_secret_metadata(metadata, root_path=path))
    return diagnostics


check_scene_provenance = validate_scene_provenance
validate_provenance_safety = validate_scene_provenance


__all__ = [
    "ASSET_PROVENANCE_SCENE_CONTRACT",
    "ASSET_PROVENANCE_SCENE_SCHEMA_FILENAME",
    "ASSET_PROVENANCE_SCENE_VERSION",
    "PROVENANCE_SOURCES",
    "check_scene_provenance",
    "find_forbidden_secret_metadata",
    "get_asset_provenance_scene_schema",
    "validate_asset_provenance_scene_payload",
    "validate_provenance_safety",
    "validate_scene_provenance",
]
