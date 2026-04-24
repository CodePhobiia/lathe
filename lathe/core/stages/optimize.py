"""Optimize stage step body (LODs + convex collision + draw-call accounting).

Extracted from ``lathe/executor.py`` during Stage 2.IV.

V0.2 E3 (STAGE-1/2): Real QEM decimation + per-part convex collision hulls
replace the previous "cloned LODs + AABB collision" placeholders. All
artifacts are deterministic.
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json, relpath
from ..io import export_glb
from ..mesh import RuntimeMesh
from ...stages import budgets as budgets_mod
from ...stages import collision as collision_mod
from ...stages import lod as lod_mod


DEFAULT_LOD_RATIOS: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1)


def _resolve_lod_ratios(asset_cfg: dict[str, Any], runtime_cfg: dict[str, Any]) -> list[float]:
    """Resolve LOD ratios with precedence: runtime_config > asset build > defaults."""

    runtime_opt = runtime_cfg.get("optimize") if isinstance(runtime_cfg, dict) else None
    if isinstance(runtime_opt, dict):
        ratios = runtime_opt.get("lod_ratios")
        if isinstance(ratios, (list, tuple)) and ratios:
            return [float(r) for r in ratios]
    asset_ratios = asset_cfg.get("lod_ratios")
    if isinstance(asset_ratios, (list, tuple)) and asset_ratios:
        return [float(r) for r in asset_ratios]
    lods_count = asset_cfg.get("lods")
    if isinstance(lods_count, int) and lods_count > 0:
        base = list(DEFAULT_LOD_RATIOS)
        if lods_count <= len(base):
            return base[:lods_count]
        tail = [base[-1] * (0.5 ** (i + 1)) for i in range(lods_count - len(base))]
        return base + tail
    return list(DEFAULT_LOD_RATIOS)


def _resolve_lod_config(asset_cfg: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Resolve the STAGE-9 ``lod_config`` block (per-level distance + coverage hints).

    Expected shape: ``[{level, ratio?, distance_min, distance_max, screen_coverage}, ...]``.
    Missing keys on any entry fall back to the LOD module's defaults inferred
    from ``DEFAULT_DISTANCE_BANDS`` / ``DEFAULT_SCREEN_COVERAGE``.
    """

    raw = asset_cfg.get("lod_config")
    if not isinstance(raw, list):
        return None
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        lvl = entry.get("level")
        if not isinstance(lvl, int) or lvl < 0:
            continue
        out.append(entry)
    return out or None


def run(executor: Any, physics_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        physics_bundle: physics_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["optimize"]
    cfg = executor.asset["build"]["optimize"]
    runtime_cfg = getattr(executor, "runtime_config", {}) or {}
    uv_runtime: RuntimeMesh = executor.runtime["uv"]["runtime_mesh"]

    lod_ratios = _resolve_lod_ratios(cfg, runtime_cfg)
    lod_config = _resolve_lod_config(cfg)
    lod_results = lod_mod.build_lods(uv_runtime.mesh, lod_ratios, lod_config)

    lods: list[dict[str, Any]] = []
    lod_manifest_entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    if len(uv_runtime.mesh.faces) == 0:
        diagnostics.append({
            "code": "LOD_EMPTY_INPUT",
            "level": "warning",
            "message": "uv stage mesh is empty; only LOD0 emitted.",
        })

    for result in lod_results:
        lod_path = stage_dir / f"lod_{result.level}.glb"
        export_glb(result.mesh, lod_path)
        rel = relpath(executor.out_dir, lod_path)
        entry = {
            "level": result.level,
            "ratio": result.ratio,
            "tris": result.tris,
            "verts": result.verts,
            "path": rel,
            "distance_min": result.distance_min,
            "distance_max": result.distance_max,
            "screen_coverage": result.screen_coverage,
        }
        lod_manifest_entries.append(entry)
        # Back-compat shape for downstream code expecting ``lods`` list entries.
        lods.append({
            "name": f"lod{result.level}",
            "mesh_uri": rel,
            "triangle_count": result.tris,
            "vertex_count": result.verts,
            "decimation": "quadric_edge_collapse" if result.ratio < 1.0 else "source",
            "distance_min": result.distance_min,
            "distance_max": result.distance_max,
            "screen_coverage": result.screen_coverage,
        })

    lod_manifest = {
        "schemaVersion": 1,
        "lods": lod_manifest_entries,
    }
    lod_manifest_path = stage_dir / "lod_manifest.json"
    dump_json(lod_manifest_path, lod_manifest)

    # Convex collision proxies — single hull + per-part hulls.
    single = collision_mod.single_hull(uv_runtime.mesh)
    single_path = stage_dir / "collision_hull.glb"
    export_glb(single.mesh, single_path)

    part_proxies = collision_mod.per_part_hulls(uv_runtime.mesh, list(uv_runtime.face_parts))
    parts_mesh = collision_mod.combine_hulls(part_proxies)
    parts_path = stage_dir / "collision_parts.glb"
    export_glb(parts_mesh, parts_path)

    collision_manifest = {
        "schemaVersion": 1,
        "proxies": [
            {
                "name": "hull",
                "tris": int(len(single.mesh.faces)),
                "verts": int(len(single.mesh.vertices)),
                "aabb": {"min": list(single.aabb_min), "max": list(single.aabb_max)},
                "path": relpath(executor.out_dir, single_path),
            },
            {
                "name": "parts",
                "path": relpath(executor.out_dir, parts_path),
                "subproxies": [
                    {
                        "name": p.name,
                        "tris": int(len(p.mesh.faces)),
                        "verts": int(len(p.mesh.vertices)),
                        "aabb": {"min": list(p.aabb_min), "max": list(p.aabb_max)},
                    }
                    for p in part_proxies
                ],
            },
        ],
    }
    collision_manifest_path = stage_dir / "collision_manifest.json"
    dump_json(collision_manifest_path, collision_manifest)

    draw_calls = max(1, int(cfg.get("draw_calls") or 1)) if cfg.get("draw_calls") is not None else 1
    texture_memory_bytes = 0
    bundle = {
        "backend_id": "lathe.optimize.deterministic_lod_v1",
        "lods": lods,
        "lod_manifest_path": relpath(executor.out_dir, lod_manifest_path),
        "collision": {
            "hull_uri": relpath(executor.out_dir, single_path),
            "parts_uri": relpath(executor.out_dir, parts_path),
            "manifest_path": relpath(executor.out_dir, collision_manifest_path),
            "hull_tris": int(len(single.mesh.faces)),
            "parts_count": len(part_proxies),
        },
        "draw_calls": draw_calls,
        "texture_memory_bytes": texture_memory_bytes,
        "mesh_compression": bool(cfg.get("mesh_compression", False)),
        "atlas": bool(cfg.get("atlas", False)),
        "diagnostics": diagnostics,
    }
    # STAGE-7/8: evaluate budgets after LODs/collision so we can reference the
    # real runtime data (surface materials + emitted LODs). The report is
    # written to disk and embedded in the bundle for downstream consumers
    # (reports stage, selector manifest).
    executor.runtime["optimize"] = {"bundle": bundle, "runtime_mesh": uv_runtime}
    budget_report, budget_diagnostics = budgets_mod.evaluate(executor.asset, executor.runtime)
    budget_report_path = stage_dir / "budget_report.json"
    dump_json(budget_report_path, budget_report)
    bundle["budget_report"] = budget_report
    bundle["budget_report_path"] = relpath(executor.out_dir, budget_report_path)
    if budget_diagnostics:
        bundle["diagnostics"] = list(diagnostics) + list(budget_diagnostics)
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
