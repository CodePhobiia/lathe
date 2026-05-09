"""Roadmap §5.9 — box-stack detector validator.

Detects "shoebox stack" geometry: meshes whose face normals are
overwhelmingly axis-aligned, whose unique-normal count is tiny, and
whose mesh volume packs the bounding box almost completely. These
three signals together identify the failure mode where the asset is
visibly composed of unbeveled cubes with no silhouette break-up.

Operates directly on the authoritative runtime mesh emitted by the
topology stage. No renderer dependency.

Score formula (from roadmap §5.9):

    score = 1.0 - clamp(
        0.4 * (axis_aligned_face_pct > 0.85)
      + 0.4 * (unique_normals < 8)
      + 0.2 * (bbox_fill > 0.85),
        0, 1,
    )

Hard reject (severity ``error``) when score < 0.5 *and* the asset opts
into ``intent.asset_class ∈ {"hero", "aaa_hero"}``. Otherwise
``severity = warning``.

Emits a ``lathe.validate.box_stack_detector_v1`` record under the
``quality_diagnostics.findings`` aggregate.
"""

from __future__ import annotations

from typing import Any

import numpy as np

VERSION = "lathe.validate.box_stack_detector_v1"

_AXIS_ALIGNED_THRESHOLD = 0.85
_UNIQUE_NORMALS_THRESHOLD = 8
_BBOX_FILL_THRESHOLD = 0.85
_HARD_REJECT_SCORE = 0.5
_HERO_ASSET_CLASSES = frozenset({"hero", "aaa_hero"})
_AXIS_DOT_EPSILON = 0.985  # cos(~10°)
_NORMAL_ROUND_DECIMALS = 3


def _hero_asset_class(asset: dict[str, Any]) -> str | None:
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    raw = intent.get("asset_class")
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().lower()
    return candidate if candidate in _HERO_ASSET_CLASSES else None


def _axis_aligned_face_pct(face_normals: np.ndarray) -> float:
    if len(face_normals) == 0:
        return 0.0
    abs_n = np.abs(face_normals)
    max_axis = np.max(abs_n, axis=1)
    aligned = np.sum(max_axis >= _AXIS_DOT_EPSILON)
    return float(aligned) / float(len(face_normals))


def _unique_normal_count(face_normals: np.ndarray) -> int:
    if len(face_normals) == 0:
        return 0
    rounded = np.round(face_normals, decimals=_NORMAL_ROUND_DECIMALS)
    unique = np.unique(rounded, axis=0)
    return int(len(unique))


def _bbox_fill(mesh: Any) -> float:
    try:
        volume = float(abs(mesh.volume))
    except (AttributeError, ValueError, RuntimeError):
        volume = 0.0
    extents = getattr(mesh, "extents", None)
    if extents is None or len(extents) != 3:
        return 0.0
    bbox_volume = float(extents[0]) * float(extents[1]) * float(extents[2])
    if bbox_volume <= 1e-12:
        return 0.0
    return min(1.0, max(0.0, volume / bbox_volume))


def evaluate_box_stack_detector(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate the box-stack detector against the runtime mesh."""
    topology = runtime.get("topology") if isinstance(runtime.get("topology"), dict) else {}
    runtime_mesh = topology.get("runtime_mesh")
    mesh = getattr(runtime_mesh, "mesh", None) if runtime_mesh is not None else None
    if mesh is None or not hasattr(mesh, "face_normals") or len(mesh.faces) == 0:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "skipped",
            "evidence": {"reason": "topology runtime mesh unavailable"},
        }

    face_normals = np.asarray(mesh.face_normals, dtype=np.float64)
    axis_aligned_pct = _axis_aligned_face_pct(face_normals)
    unique_normals = _unique_normal_count(face_normals)
    fill = _bbox_fill(mesh)

    raw_penalty = (
        0.4 * (1.0 if axis_aligned_pct > _AXIS_ALIGNED_THRESHOLD else 0.0)
        + 0.4 * (1.0 if unique_normals < _UNIQUE_NORMALS_THRESHOLD else 0.0)
        + 0.2 * (1.0 if fill > _BBOX_FILL_THRESHOLD else 0.0)
    )
    raw_penalty = max(0.0, min(1.0, raw_penalty))
    score = round(1.0 - raw_penalty, 6)

    asset_class = _hero_asset_class(asset)
    if score < _HARD_REJECT_SCORE and asset_class is not None:
        status = "fail"
        severity = "error"
    elif score < _HARD_REJECT_SCORE:
        status = "warn"
        severity = "warning"
    else:
        status = "pass"
        severity = "info"

    return {
        "version": VERSION,
        "score": score,
        "status": status,
        "severity": severity,
        "evidence": {
            "axis_aligned_face_pct": round(axis_aligned_pct, 6),
            "unique_normals": int(unique_normals),
            "bbox_fill": round(fill, 6),
            "axis_aligned_threshold": _AXIS_ALIGNED_THRESHOLD,
            "unique_normals_threshold": _UNIQUE_NORMALS_THRESHOLD,
            "bbox_fill_threshold": _BBOX_FILL_THRESHOLD,
            "hard_reject_score": _HARD_REJECT_SCORE,
            "asset_class": asset_class,
            "face_count": int(len(mesh.faces)),
        },
    }
