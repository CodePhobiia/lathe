"""Rig stage step body.

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json
from ..geometry import part_centroids
from ..mesh import RuntimeMesh


def run(executor: Any, surface_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        surface_bundle: surface_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["rig"]
    rig_cfg = executor.asset["build"]["rig"]
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    centroids = part_centroids(topology_runtime.mesh, topology_runtime.face_parts)
    joints = []
    for joint_name in rig_cfg.get("joints", []):
        centroid = centroids.get(joint_name, [0.0, 0.0, 0.0])
        joints.append({
            "name": joint_name,
            "pivot": [round(float(v), 6) for v in centroid],
        })
    bundle = {
        "backend_id": "lathe.rig.rigid_mechanical_stub_v1",
        "type": rig_cfg.get("type"),
        "pivot_policy": rig_cfg.get("pivot_policy", "auto"),
        "joints": joints,
    }
    executor.runtime["rig"] = {"bundle": bundle}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
