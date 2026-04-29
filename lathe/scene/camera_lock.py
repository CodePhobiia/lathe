"""Deterministic camera locks for Wonder before/after comparisons."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from lathe.wonder import validate_contract

CAMERA_LOCK_VERSION = "lathe.camera_lock.v1"
CAMERA_LOCK_SCHEMA_FILENAME = "camera_lock.schema.json"
CAMERA_LOCK_CONTRACT = "camera_lock"


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_hash(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _diagnostic(
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
        "contract": CAMERA_LOCK_CONTRACT,
        "phase": "camera_lock",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _camera_by_id(scene_graph: Mapping[str, Any], camera_id: str) -> tuple[Mapping[str, Any] | None, int | None]:
    cameras = scene_graph.get("cameras")
    if not isinstance(cameras, list):
        return None, None
    for index, camera in enumerate(cameras):
        if isinstance(camera, Mapping) and camera.get("camera_id") == camera_id:
            return camera, index
    return None, None


def lock_camera(scene_graph: Mapping[str, Any], camera_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Extract a deterministic lock payload for a Scene Graph camera."""
    cameras = scene_graph.get("cameras")
    if not isinstance(cameras, list) or not cameras:
        return None, [
            _diagnostic(
                "CL1001",
                "scene_camera_collection_missing",
                "/cameras",
                "Scene Graph does not contain a cameras array with at least one camera.",
                details={"camera_id": camera_id},
            )
        ]

    camera, index = _camera_by_id(scene_graph, camera_id)
    if camera is None or index is None:
        available = [item.get("camera_id") for item in cameras if isinstance(item, Mapping)]
        return None, [
            _diagnostic(
                "CL1002",
                "scene_camera_missing",
                "/cameras",
                f"Scene camera {camera_id!r} does not exist.",
                details={"camera_id": camera_id, "available_camera_ids": available},
            )
        ]

    scene_id = scene_graph.get("scene_id")
    transform = camera.get("transform") if isinstance(camera.get("transform"), Mapping) else None
    position = transform.get("position") if isinstance(transform, Mapping) else None
    rotation = transform.get("rotation") if isinstance(transform, Mapping) else None
    scale = transform.get("scale") if isinstance(transform, Mapping) else None
    projection = str(camera.get("projection") or camera.get("type") or "perspective")

    payload: dict[str, Any] = {
        "schema_version": CAMERA_LOCK_VERSION,
        "scene_id": scene_id,
        "camera_id": camera_id,
        "projection": projection,
        "type": projection,
        "target": camera.get("target"),
        "framing": camera.get("framing"),
        "purpose": camera.get("purpose"),
    }
    if transform is not None:
        payload["transform"] = copy.deepcopy(dict(transform))
    if position is not None:
        payload["position"] = copy.deepcopy(position)
    if rotation is not None:
        payload["rotation"] = copy.deepcopy(rotation)
    if scale is not None:
        payload["scale"] = copy.deepcopy(scale)
    if "fov_degrees" in camera:
        payload["fov_degrees"] = copy.deepcopy(camera.get("fov_degrees"))

    hash_payload = copy.deepcopy(payload)
    payload["camera_hash"] = _stable_hash(hash_payload)
    diagnostics = validate_camera_lock_payload(payload)
    return payload, diagnostics


def validate_camera_lock_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a camera lock payload."""
    return validate_contract(CAMERA_LOCK_CONTRACT, payload)


__all__ = [
    "CAMERA_LOCK_CONTRACT",
    "CAMERA_LOCK_SCHEMA_FILENAME",
    "CAMERA_LOCK_VERSION",
    "lock_camera",
    "validate_camera_lock_payload",
]
