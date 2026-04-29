"""Hash-guarded Scene Graph rollback helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .history import (
    SceneHistoryError,
    apply_json_patch_operations,
    find_scene_history_record,
    scene_hash,
)


class RollbackHashMismatch(SceneHistoryError):
    """Raised when current scene content does not match the history guard."""


def rollback_scene(
    scene_graph: Mapping[str, Any],
    scene_history: Mapping[str, Any],
    to_event: str,
) -> dict[str, Any]:
    """Return a rolled-back Scene Graph if the current hash matches history."""
    record = find_scene_history_record(scene_history, to_event)
    expected_after = record.get("after_scene_hash")
    actual_after = scene_hash(scene_graph)
    if actual_after != expected_after:
        raise RollbackHashMismatch(
            f"Scene hash mismatch for rollback to {to_event!r}: expected {expected_after}, got {actual_after}."
        )

    inverse_patch_ref = record.get("inverse_patch")
    if not isinstance(inverse_patch_ref, Mapping):
        raise SceneHistoryError("Scene History record inverse_patch must be an object")
    inverse_patch = inverse_patch_ref.get("payload")
    if not isinstance(inverse_patch, Mapping):
        raise SceneHistoryError("Scene History rollback requires an embedded inverse_patch payload")
    operations = inverse_patch.get("operations", [])
    if not isinstance(operations, list):
        raise SceneHistoryError("Scene History inverse_patch operations must be an array")

    rolled_back = apply_json_patch_operations(scene_graph, [dict(operation) for operation in operations])
    expected_before = record.get("before_scene_hash")
    actual_before = scene_hash(rolled_back)
    if actual_before != expected_before:
        raise SceneHistoryError(
            f"Rollback inverse patch did not restore before_scene_hash for {to_event!r}: "
            f"expected {expected_before}, got {actual_before}."
        )
    return rolled_back


__all__ = ["RollbackHashMismatch", "rollback_scene"]
