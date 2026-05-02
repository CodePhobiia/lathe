"""Optimize stage step body (LODs + convex collision + draw-call accounting).

Extracted from ``lathe/executor.py`` during Stage 2.IV.

V0.2 E3 (STAGE-1/2): Real QEM decimation + per-part convex collision hulls
replace the previous "cloned LODs + AABB collision" placeholders. All
artifacts are deterministic.
"""

from __future__ import annotations

from typing import Any

from ...stages import budgets as budgets_mod
from ...stages import collision as collision_mod
from ...stages import lod as lod_mod
from ...highlow import HighLowRelation
from ..common import dump_json, relpath
from ..io import export_glb
from ..mesh import RuntimeMesh

DEFAULT_LOD_RATIOS: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1)


def _count_lod_levels(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    token = str(value).lower().replace("-", "_").strip()
    levels = {
        "off": 0,
        "none": 0,
        "low": 2,
        "medium": 3,
        "standard": 3,
        "high": 4,
        "hero": 5,
    }
    if token in levels:
        return levels[token]
    try:
        return max(0, int(round(float(token))))
    except ValueError:
        return 0


def _resolve_lod_ratios(
    asset_cfg: dict[str, Any], runtime_cfg: dict[str, Any], shape_cfg: dict[str, Any] | None = None
) -> list[float]:
    """Resolve LOD ratios with precedence: runtime_config > asset build > defaults."""
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    runtime_opt = runtime_cfg.get("optimize") if isinstance(runtime_cfg, dict) else None
    if isinstance(runtime_opt, dict):
        ratios = runtime_opt.get("lod_ratios")
        if isinstance(ratios, (list, tuple)) and ratios:
            return [float(r) for r in ratios]
    asset_ratios = asset_cfg.get("lod_ratios")
    if isinstance(asset_ratios, (list, tuple)) and asset_ratios:
        return [float(r) for r in asset_ratios]
    shape_ratios = shape_cfg.get("lod_ratios")
    if isinstance(shape_ratios, (list, tuple)) and shape_ratios:
        return [float(r) for r in shape_ratios]
    lods_count = asset_cfg.get("lods")
    authored_lod_levels = _count_lod_levels(shape_cfg.get("lod_levels"))
    if isinstance(lods_count, int) and authored_lod_levels:
        lods_count = max(lods_count, authored_lod_levels)
    elif authored_lod_levels:
        lods_count = authored_lod_levels
    if isinstance(lods_count, int) and lods_count > 0:
        base = list(DEFAULT_LOD_RATIOS)
        if lods_count <= len(base):
            return base[:lods_count]
        tail = [base[-1] * (0.5 ** (i + 1)) for i in range(lods_count - len(base))]
        return base + tail
    return list(DEFAULT_LOD_RATIOS)


def _resolve_lod_config(
    asset_cfg: dict[str, Any], shape_cfg: dict[str, Any] | None = None
) -> list[dict[str, Any]] | None:
    """Resolve the STAGE-9 ``lod_config`` block (per-level distance + coverage hints).

    Expected shape: ``[{level, ratio?, distance_min, distance_max, screen_coverage}, ...]``.
    Missing keys on any entry fall back to the LOD module's defaults inferred
    from ``DEFAULT_DISTANCE_BANDS`` / ``DEFAULT_SCREEN_COVERAGE``.
    """
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    raw = asset_cfg.get("lod_config")
    if not isinstance(raw, list):
        raw = shape_cfg.get("lod_config")
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


def _token(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_").strip()


def _count(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    try:
        return max(0, int(round(float(str(value).strip()))))
    except ValueError:
        return default


def _level(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    token = _token(value)
    levels = {
        "none": 0.0,
        "off": 0.0,
        "low": 0.6,
        "medium": 1.0,
        "standard": 1.0,
        "high": 1.35,
        "hero": 1.75,
    }
    if token in levels:
        return levels[token]
    try:
        return max(0.0, float(token))
    except ValueError:
        return default


def _highlow_requested(shape_cfg: dict[str, Any]) -> bool:
    mode = _token(shape_cfg.get("highlow_mode"))
    return mode in {"lod_pair", "real_lod", "runtime_lod", "high_to_low"} or any(
        field in shape_cfg for field in ("highlow_low_lod", "highlow_bake_cage_offset_cm")
    )


def _publish_lod_highlow_relation(
    executor: Any,
    *,
    shape_cfg: dict[str, Any],
    lods: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not _highlow_requested(shape_cfg) or len(lods) < 2:
        return None
    requested_level = _count(shape_cfg.get("highlow_low_lod"), len(lods) - 1)
    if requested_level <= 0:
        requested_level = len(lods) - 1
    low_entry = next((entry for entry in lods if int(entry.get("name", "lod0").removeprefix("lod") or 0) == requested_level), None)
    if low_entry is None:
        low_entry = lods[-1]
    surface_bundle = executor.runtime.get("surface", {}).get("bundle", {})
    previous_relation = surface_bundle.get("highlow_relation", {}) if isinstance(surface_bundle, dict) else {}
    high_mesh_uri = previous_relation.get("high_mesh_uri")
    high_triangle_count = int(previous_relation.get("high_triangle_count", 0) or 0)
    low_triangle_count = int(low_entry.get("triangle_count", 0) or 0)
    if high_triangle_count > low_triangle_count >= 0:
        distinction_ratio = round((high_triangle_count - low_triangle_count) / max(1, high_triangle_count), 6)
    else:
        distinction_ratio = 0.0
    relation = HighLowRelation(
        high_mesh_uri=high_mesh_uri,
        low_mesh_uri=low_entry.get("mesh_uri"),
        bake_cage_offset_cm=_level(shape_cfg.get("highlow_bake_cage_offset_cm"), 1.25),
        source="optimize_lod_highlow_v1",
        high_triangle_count=high_triangle_count,
        low_triangle_count=low_triangle_count,
        distinction_ratio=distinction_ratio,
        bake_groups=previous_relation.get("bake_groups"),
        authoritative=True,
    ).to_dict()
    relation["low_lod_level"] = int(str(low_entry.get("name", "lod0")).removeprefix("lod") or 0)
    relation["highlow_mode"] = _token(shape_cfg.get("highlow_mode")) or "lod_pair"
    if isinstance(surface_bundle, dict):
        surface_bundle["highlow_relation"] = relation
        surface_dir = executor.stage_dirs.get("surface")
        surface_path = surface_dir / "bundle.json" if surface_dir is not None else None
        if surface_path is not None and surface_path.exists():
            dump_json(surface_path, surface_bundle)
    executor.runtime["highlow_relation"] = relation
    return relation


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
    shape_cfg = executor.asset.get("build", {}).get("shape", {})
    runtime_cfg = getattr(executor, "runtime_config", {}) or {}
    uv_runtime: RuntimeMesh = executor.runtime["uv"]["runtime_mesh"]

    lod_ratios = _resolve_lod_ratios(cfg, runtime_cfg, shape_cfg)
    lod_config = _resolve_lod_config(cfg, shape_cfg)
    lod_results = lod_mod.build_lods(uv_runtime.mesh, lod_ratios, lod_config)

    lods: list[dict[str, Any]] = []
    lod_manifest_entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    if len(uv_runtime.mesh.faces) == 0:
        diagnostics.append(
            {
                "code": "LOD_EMPTY_INPUT",
                "level": "warning",
                "message": "uv stage mesh is empty; only LOD0 emitted.",
            }
        )

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
        lods.append(
            {
                "name": f"lod{result.level}",
                "mesh_uri": rel,
                "triangle_count": result.tris,
                "vertex_count": result.verts,
                "decimation": "quadric_edge_collapse" if result.ratio < 1.0 else "source",
                "distance_min": result.distance_min,
                "distance_max": result.distance_max,
                "screen_coverage": result.screen_coverage,
            }
        )

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
                "tris": len(single.mesh.faces),
                "verts": len(single.mesh.vertices),
                "aabb": {"min": list(single.aabb_min), "max": list(single.aabb_max)},
                "path": relpath(executor.out_dir, single_path),
            },
            {
                "name": "parts",
                "path": relpath(executor.out_dir, parts_path),
                "subproxies": [
                    {
                        "name": p.name,
                        "tris": len(p.mesh.faces),
                        "verts": len(p.mesh.vertices),
                        "aabb": {"min": list(p.aabb_min), "max": list(p.aabb_max)},
                    }
                    for p in part_proxies
                ],
            },
        ],
    }
    collision_manifest_path = stage_dir / "collision_manifest.json"
    dump_json(collision_manifest_path, collision_manifest)
    highlow_relation = _publish_lod_highlow_relation(executor, shape_cfg=shape_cfg, lods=lods)

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
            "hull_tris": len(single.mesh.faces),
            "parts_count": len(part_proxies),
        },
        "draw_calls": draw_calls,
        "texture_memory_bytes": texture_memory_bytes,
        "mesh_compression": bool(cfg.get("mesh_compression", False)),
        "atlas": bool(cfg.get("atlas", False)),
        "authored_lod_controls": {
            "shape_lod_levels": shape_cfg.get("lod_levels"),
            "shape_lod_ratios": list(shape_cfg.get("lod_ratios", []))
            if isinstance(shape_cfg.get("lod_ratios"), list)
            else [],
            "resolved_ratios": list(lod_ratios),
        },
        "authored_highlow_controls": {
            "highlow_mode": shape_cfg.get("highlow_mode", ""),
            "highlow_low_lod": shape_cfg.get("highlow_low_lod", None),
            "highlow_bake_cage_offset_cm": shape_cfg.get("highlow_bake_cage_offset_cm", None),
        },
        "diagnostics": diagnostics,
    }
    if highlow_relation is not None:
        bundle["highlow_relation"] = highlow_relation
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
