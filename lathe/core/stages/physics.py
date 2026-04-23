"""Physics stage step body (collision proxy + mass).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json, relpath
from ..geometry import estimate_mass_kg
from ..io import export_glb
from ..mesh import RuntimeMesh


def run(executor: Any, interfaces_bundle: dict[str, Any]) -> dict[str, Any]:
    stage_dir = executor.stage_dirs["physics"]
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    cfg = executor.asset["build"]["physics"]
    collision_mesh = topology_runtime.mesh.bounding_box.copy()
    collision_path = stage_dir / "collision.glb"
    export_glb(collision_mesh, collision_path)
    mass_value = estimate_mass_kg(topology_runtime.mesh)
    bundle = {
        "backend_id": "lathe.physics.proxy_v1",
        "collision": cfg.get("collision"),
        "collision_proxy_uri": relpath(executor.out_dir, collision_path),
        "collision_proxy": True,
        "mass_kg": round(mass_value, 4),
        "center_of_mass": [round(float(v), 6) for v in topology_runtime.mesh.center_mass],
    }
    executor.runtime["physics"] = {"bundle": bundle, "collision_mesh": collision_mesh}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
