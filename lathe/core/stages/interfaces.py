"""Interfaces stage step body (sockets + anchors).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json


def run(executor: Any, rig_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        rig_bundle: rig_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["interfaces"]
    cfg = executor.asset["build"]["interfaces"]
    mesh = executor.runtime["topology"]["runtime_mesh"].mesh
    bounds = mesh.bounds
    center = mesh.bounding_box.centroid
    sockets = []
    for idx, name in enumerate(cfg.get("sockets", [])):
        z_offset = (-0.2 + 0.4 * idx / max(1, len(cfg.get("sockets", [])))) * (bounds[1, 2] - bounds[0, 2])
        sockets.append({
            "name": name,
            "position": [round(float(center[0]), 6), round(float(center[1]), 6), round(float(center[2] + z_offset), 6)],
        })
    anchors = []
    for idx, name in enumerate(cfg.get("anchors", [])):
        anchors.append({
            "name": name,
            "position": [round(float(center[0]), 6), round(float(bounds[0, 1]), 6), round(float(center[2]), 6)],
        })
    bundle = {
        "backend_id": "lathe.interfaces.socket_stub_v1",
        "sockets": sockets,
        "anchors": anchors,
        "clearance": cfg.get("clearance"),
        "snap_grid": cfg.get("snap_grid"),
    }
    executor.runtime["interfaces"] = {"bundle": bundle}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
