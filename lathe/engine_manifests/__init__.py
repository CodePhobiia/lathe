"""Engine-specific manifest adapters (STAGE-10, V0.2 E3).

Each adapter consumes the package-stage runtime snapshot (LODs, sockets,
pivots, collisions, materials, gameplay tags) and emits a small sidecar file
alongside the main glb that downstream engine importers can read to build a
ready-to-use scene node hierarchy. These files are *hints*, not full asset
conversions — they reference the existing glb/collision artifacts by relative
path and describe how the engine should wire them up (LOD ranges, socket
nodes, collision shapes).

Adapters are registered in the ``ADAPTERS`` mapping and selected by engine id
from the package stage. The mapping is also exported via
``entry_points`` group ``lathe.engine_manifest`` in the package ``pyproject``
so out-of-tree plugins can register additional engines.
"""

from __future__ import annotations

from typing import Callable, Dict, Any

from .godot import emit_godot_manifest
from .unity import emit_unity_manifest
from .unreal import emit_unreal_manifest

EmitFn = Callable[[Dict[str, Any], str], str]
"""Adapter signature: ``emit(context, asset_name) -> file contents``.

``context`` carries:
  - ``lods``: list of ``{level, mesh_uri, distance_min, distance_max, screen_coverage, triangle_count}``
  - ``sockets``: list of ``{id, origin, axis, socket_type, parent_part_id}``
  - ``pivots``: list of ``{id, origin, axis, pivot_type}``
  - ``collisions``: list of ``{id, kind, parent_part_id, uri}``
  - ``materials``: list of ``{id, display_name}``
  - ``gameplay_tags``: list[str]
  - ``main_glb_uri``: str  — relative path of the main glb
"""

ADAPTERS: Dict[str, EmitFn] = {
    "godot": emit_godot_manifest,
    "unity": emit_unity_manifest,
    "unreal": emit_unreal_manifest,
}

FILE_EXTENSIONS: Dict[str, str] = {
    "godot": "json",
    "unity": "yaml",
    "unreal": "json",
}


def manifest_filename(engine: str, asset_name: str) -> str:
    """Return the sidecar filename for a given engine, e.g.
    ``courier_drone.lathe_for_godot.json``."""
    ext = FILE_EXTENSIONS.get(engine, "json")
    return f"{asset_name}.lathe_for_{engine}.{ext}"


__all__ = [
    "ADAPTERS",
    "FILE_EXTENSIONS",
    "EmitFn",
    "manifest_filename",
    "emit_godot_manifest",
    "emit_unity_manifest",
    "emit_unreal_manifest",
]
