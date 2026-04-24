"""Blender integration package.

Houses the in-process Blender plan adapter, driver scripts, render
helpers and execution result objects used by the V1.3 Blender-backed
execution stage.
"""

from __future__ import annotations

from ..errors import BlenderExecutionError
from .drivers import BACKEND_IDS
from .execution import build_execution_bundle
from .results import (
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
