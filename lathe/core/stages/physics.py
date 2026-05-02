"""Physics stage step body (collision proxy + mass).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ...stages import collision as collision_mod
from ..common import dump_json, relpath
from ..geometry import estimate_mass_kg
from ..io import export_glb
from ..mesh import RuntimeMesh


def _token(value: Any) -> str:
    return str(value).lower().replace("-", "_").replace(" ", "_").strip() if value is not None else ""


def _resolve_collision_proxy_mode(physics_cfg: dict[str, Any], shape_cfg: dict[str, Any] | None = None) -> str:
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    authored = _token(shape_cfg.get("collision_proxy"))
    explicit_physics = _token(physics_cfg.get("collision"))
    raw = authored if authored else explicit_physics
    aliases = {
        "": "box",
        "none": "box",
        "auto": "box",
        "bounds": "box",
        "aabb": "box",
        "bounding_box": "box",
        "box_proxy": "box",
        "convex": "convex_hull",
        "hull": "convex_hull",
        "convex_proxy": "convex_hull",
        "convex_decomp": "per_part_hulls",
        "decomp": "per_part_hulls",
        "parts": "per_part_hulls",
        "part_hulls": "per_part_hulls",
        "per_part": "per_part_hulls",
    }
    return aliases.get(raw, raw if raw in {"box", "convex_hull", "per_part_hulls"} else "box")


def _collision_proxy_mesh(runtime_mesh: RuntimeMesh, mode: str) -> tuple[Any, str]:
    if mode == "convex_hull":
        proxy = collision_mod.single_hull(runtime_mesh.mesh)
        return proxy.mesh, "convex_hull"
    if mode == "per_part_hulls":
        proxies = collision_mod.per_part_hulls(runtime_mesh.mesh, list(runtime_mesh.face_parts))
        return collision_mod.combine_hulls(proxies), "per_part_hulls"
    return runtime_mesh.mesh.bounding_box.copy(), "box"


def run(executor: Any, interfaces_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        interfaces_bundle: interfaces_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["physics"]
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    cfg = executor.asset["build"]["physics"]
    shape_cfg = executor.asset.get("build", {}).get("shape", {})
    collision_mode = _resolve_collision_proxy_mode(cfg, shape_cfg)
    collision_mesh, resolved_collision_mode = _collision_proxy_mesh(topology_runtime, collision_mode)
    collision_path = stage_dir / "collision.glb"
    export_glb(collision_mesh, collision_path)
    mass_value = estimate_mass_kg(topology_runtime.mesh)
    bundle = {
        "backend_id": "lathe.physics.proxy_v1",
        "collision": cfg.get("collision"),
        "collision_proxy_type": resolved_collision_mode,
        "collision_proxy_source": "shape.collision_proxy" if shape_cfg.get("collision_proxy") else "build.physics.collision",
        "collision_proxy_uri": relpath(executor.out_dir, collision_path),
        "collision_proxy": True,
        "mass_kg": round(mass_value, 4),
        "center_of_mass": [round(float(v), 6) for v in topology_runtime.mesh.center_mass],
    }
    executor.runtime["physics"] = {"bundle": bundle, "collision_mesh": collision_mesh}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
