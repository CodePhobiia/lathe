"""Optimize stage step body (LODs + draw-call accounting).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json, relpath
from ..io import export_glb
from ..mesh import RuntimeMesh


def run(executor: Any, physics_bundle: dict[str, Any]) -> dict[str, Any]:
    stage_dir = executor.stage_dirs["optimize"]
    cfg = executor.asset["build"]["optimize"]
    uv_runtime: RuntimeMesh = executor.runtime["uv"]["runtime_mesh"]
    lod_count = max(1, int(cfg.get("lods", 1)))
    lods = []
    for lod_index in range(lod_count):
        lod_path = stage_dir / f"lod{lod_index}.glb"
        export_glb(uv_runtime.mesh, lod_path)
        lods.append({
            "name": f"lod{lod_index}",
            "mesh_uri": relpath(executor.out_dir, lod_path),
            "triangle_count": int(len(uv_runtime.mesh.faces)),
            "vertex_count": int(len(uv_runtime.mesh.vertices)),
            "decimation": "cloned",
        })
    draw_calls = max(1, int(cfg.get("draw_calls") or 1)) if cfg.get("draw_calls") is not None else 1
    texture_memory_bytes = 0
    bundle = {
        "backend_id": "lathe.optimize.deterministic_clone_v1",
        "lods": lods,
        "draw_calls": draw_calls,
        "texture_memory_bytes": texture_memory_bytes,
        "mesh_compression": bool(cfg.get("mesh_compression", False)),
        "atlas": bool(cfg.get("atlas", False)),
    }
    executor.runtime["optimize"] = {"bundle": bundle, "runtime_mesh": uv_runtime}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
