"""Deterministic proxy render comparisons for Wonder scenes."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lathe.wonder import validate_contract

RENDER_COMPARISON_VERSION = "lathe.render_comparison.v1"
RENDER_COMPARISON_SCHEMA_FILENAME = "render_comparison.schema.json"
RENDER_COMPARISON_CONTRACT = "render_comparison"

SEMANTIC_DELTA_NOT_EVALUATED = {
    "status": "not_evaluated",
    "reason": (
        "Wave 3 proxy comparison measures deterministic pixel deltas only; "
        "target-level semantic visual evaluation is not implemented."
    ),
}


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
        "contract": RENDER_COMPARISON_CONTRACT,
        "phase": "render_comparison",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def file_sha256(path: str | Path) -> str:
    """Return a stable sha256 digest for a local file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def compare_renders(
    before: str | Path,
    after: str | Path,
    *,
    camera_lock: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Compare two deterministic local PNG render files."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - normal test/runtime environment includes Pillow.
        return None, [
            _diagnostic(
                "RC1000",
                "image_dependency_missing",
                "/dependencies",
                f"Could not import image dependency Pillow: {exc}",
            )
        ]

    before_path = Path(before)
    after_path = Path(after)
    try:
        with Image.open(before_path) as image:
            before_image = image.convert("RGBA")
    except (OSError, ValueError) as exc:
        return None, [
            _diagnostic(
                "RC1001",
                "before_render_unreadable",
                "/before",
                f"Before render could not be read as an image: {exc}",
                details={"before": str(before_path)},
            )
        ]
    try:
        with Image.open(after_path) as image:
            after_image = image.convert("RGBA")
    except (OSError, ValueError) as exc:
        return None, [
            _diagnostic(
                "RC1002",
                "after_render_unreadable",
                "/after",
                f"After render could not be read as an image: {exc}",
                details={"after": str(after_path)},
            )
        ]

    before_dimensions = before_image.size
    after_dimensions = after_image.size
    if before_dimensions != after_dimensions:
        return None, [
            _diagnostic(
                "RC1003",
                "render_dimension_mismatch",
                "/dimensions",
                (
                    "Before and after render dimensions must match; "
                    f"got {before_dimensions[0]}x{before_dimensions[1]} and {after_dimensions[0]}x{after_dimensions[1]}."
                ),
                details={
                    "before": {"width": before_dimensions[0], "height": before_dimensions[1]},
                    "after": {"width": after_dimensions[0], "height": after_dimensions[1]},
                },
            )
        ]

    bytes_per_pixel = len(before_image.getbands())
    before_bytes = before_image.tobytes()
    after_bytes = after_image.tobytes()
    changed_pixels = sum(
        1
        for offset in range(0, len(before_bytes), bytes_per_pixel)
        if before_bytes[offset : offset + bytes_per_pixel] != after_bytes[offset : offset + bytes_per_pixel]
    )
    width, height = before_dimensions
    total_pixels = width * height
    comparison: dict[str, Any] = {
        "schema_version": RENDER_COMPARISON_VERSION,
        "camera_lock_status": "passed" if camera_lock is not None else "not_provided",
        "before_hash": file_sha256(before_path),
        "after_hash": file_sha256(after_path),
        "dimensions": {"width": width, "height": height},
        "pixel_delta": {
            "changed_pixels": changed_pixels,
            "changed_ratio": changed_pixels / total_pixels if total_pixels else 0.0,
        },
        "semantic_delta": dict(SEMANTIC_DELTA_NOT_EVALUATED),
        "status": "passed",
    }
    if camera_lock is not None:
        comparison["camera_hash"] = camera_lock.get("camera_hash")

    diagnostics = validate_render_comparison_payload(comparison)
    return comparison, diagnostics


def validate_render_comparison_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a render comparison payload."""
    return validate_contract(RENDER_COMPARISON_CONTRACT, payload)


__all__ = [
    "RENDER_COMPARISON_CONTRACT",
    "RENDER_COMPARISON_SCHEMA_FILENAME",
    "RENDER_COMPARISON_VERSION",
    "compare_renders",
    "file_sha256",
    "validate_render_comparison_payload",
]
