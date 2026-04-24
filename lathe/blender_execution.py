"""Backwards-compatible shim for the decomposed ``lathe.blender`` subpackage.

The real implementation now lives under ``lathe/blender/``. External callers
and tests continue to import the public surface from this module.
"""
from __future__ import annotations

from .blender import (
    BACKEND_IDS,
    BlenderExecutionError,
    build_execution_bundle,
    build_library_sync_manifest,
    export_blend_artifact,
    inspect_blend_artifact,
)

__all__ = [
    "BACKEND_IDS",
    "BlenderExecutionError",
    "build_execution_bundle",
    "build_library_sync_manifest",
    "export_blend_artifact",
    "inspect_blend_artifact",
]
