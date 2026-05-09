"""Mesh-level repair operators dispatched by the autonomous repair loop.

Companion to ``repair_executor.py`` (which handles semantic shape-region
repairs) and ``repair_loop.py`` (which orchestrates rounds). The operators
here act on the *runtime* meshes carried by ``BuildExecutor.runtime`` —
mirroring, hole-sealing, decimation, UV re-pack, bake re-run, pivot
normalization, collision proxy generation, and LOD generation.

Each operator returns a :class:`RepairOperatorResult`:

* ``applied_change`` — True if the operator actually mutated runtime state.
* ``score_delta_estimate`` — coarse heuristic; the loop verifies via
  re-validation, so this is for trace/observability only.
* ``evidence`` — operator-specific dict for the trace.
* ``error`` — non-None when the operator could not run safely (e.g. empty
  mesh, missing pivot). The loop treats an error as a no-op rollback.

These operators are deliberately defensive: they never raise on edge cases.
Internal-state guards return ``RepairOperatorResult(applied_change=False,
error="...")`` so the loop can record the attempt and escalate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import trimesh


@dataclass
class RepairOperatorResult:
    """Outcome of one repair-operator invocation."""

    applied_change: bool = False
    score_delta_estimate: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _runtime_mesh_or_none(executor: Any, stage: str) -> trimesh.Trimesh | None:
    """Return the trimesh attached to a runtime stage, or None when missing/empty."""
    payload = executor.runtime.get(stage)
    if not isinstance(payload, dict):
        return None
    rmesh = payload.get("runtime_mesh")
    if rmesh is None:
        return None
    mesh = getattr(rmesh, "mesh", None)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        return None
    return mesh


def _replace_runtime_mesh(executor: Any, stage: str, new_mesh: trimesh.Trimesh) -> None:
    """Replace the trimesh on the runtime mesh wrapper, preserving face_parts when possible."""
    payload = executor.runtime.get(stage) or {}
    rmesh = payload.get("runtime_mesh")
    if rmesh is None:
        return
    rmesh.mesh = new_mesh
    if hasattr(rmesh, "face_parts") and len(rmesh.face_parts) != len(new_mesh.faces):
        # face_parts no longer aligns; clear so downstream stages re-derive.
        rmesh.face_parts = []


# ---------------------------------------------------------------------------
# 1. enforce_symmetry
# ---------------------------------------------------------------------------


def enforce_symmetry(executor: Any, **_: Any) -> RepairOperatorResult:
    """Mirror the larger half over the smaller across the asset's symmetry axis.

    Asset declares e.g. ``intent.symmetry = x``. We split the mesh by the
    plane through the centroid normal to that axis, keep the half with more
    triangles, mirror it, weld with itself, and replace the runtime mesh.
    """
    mesh = _runtime_mesh_or_none(executor, "uv") or _runtime_mesh_or_none(executor, "topology")
    if mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    intent = (executor.asset or {}).get("intent") or {}
    axis_name = str(intent.get("symmetry") or "x").lower()
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis_name)
    if axis_index is None:
        return RepairOperatorResult(error=f"unsupported symmetry axis: {axis_name!r}")

    centroid = np.asarray(mesh.bounding_box.centroid, dtype=np.float64)
    plane_normal = np.zeros(3, dtype=np.float64)
    plane_normal[axis_index] = 1.0
    plane_origin = centroid

    try:
        positive = mesh.slice_plane(plane_origin=plane_origin, plane_normal=plane_normal)
        negative = mesh.slice_plane(plane_origin=plane_origin, plane_normal=-plane_normal)
    except Exception as exc:  # trimesh slice can fail on degenerate meshes
        return RepairOperatorResult(error=f"slice_plane failed: {exc}")

    pos_faces = len(positive.faces) if isinstance(positive, trimesh.Trimesh) else 0
    neg_faces = len(negative.faces) if isinstance(negative, trimesh.Trimesh) else 0
    if pos_faces == 0 and neg_faces == 0:
        return RepairOperatorResult(error="symmetry split produced empty halves")

    larger = positive if pos_faces >= neg_faces else negative
    larger_count = max(pos_faces, neg_faces)
    smaller_count = min(pos_faces, neg_faces)

    mirrored = larger.copy()
    reflect = np.eye(4, dtype=np.float64)
    reflect[axis_index, axis_index] = -1.0
    # Reflect about the plane through ``centroid`` perpendicular to axis.
    translate_to_origin = np.eye(4, dtype=np.float64)
    translate_to_origin[axis_index, 3] = -centroid[axis_index]
    translate_back = np.eye(4, dtype=np.float64)
    translate_back[axis_index, 3] = centroid[axis_index]
    mirror_xform = translate_back @ reflect @ translate_to_origin
    mirrored.apply_transform(mirror_xform)

    try:
        unioned = trimesh.util.concatenate([larger, mirrored])
        unioned.merge_vertices()
    except Exception as exc:
        return RepairOperatorResult(error=f"weld after mirror failed: {exc}")

    _replace_runtime_mesh(executor, "uv", unioned)
    _replace_runtime_mesh(executor, "topology", unioned)

    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.02,
        evidence={
            "axis": axis_name,
            "kept_side_face_count": larger_count,
            "discarded_side_face_count": smaller_count,
            "result_face_count": len(unioned.faces),
        },
    )


# ---------------------------------------------------------------------------
# 2. seal_mesh
# ---------------------------------------------------------------------------


def seal_mesh(executor: Any, **_: Any) -> RepairOperatorResult:
    """Close non-manifold holes via ``trimesh.repair.fill_holes``."""
    mesh = _runtime_mesh_or_none(executor, "uv") or _runtime_mesh_or_none(executor, "topology")
    if mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    before_open_edges = int(np.sum(mesh.edges_unique.shape[0] > 0)) if hasattr(mesh, "edges_unique") else 0
    try:
        # Most trimesh versions expose ``mesh.fill_holes()`` which delegates
        # to ``trimesh.repair.fill_holes`` and mutates the mesh in place.
        if hasattr(mesh, "fill_holes"):
            success = bool(mesh.fill_holes())
        else:
            from trimesh import repair as _repair

            success = bool(_repair.fill_holes(mesh))
    except Exception as exc:
        return RepairOperatorResult(error=f"fill_holes raised: {exc}")

    after_watertight = bool(getattr(mesh, "is_watertight", False))
    holes_closed = success or after_watertight

    return RepairOperatorResult(
        applied_change=holes_closed,
        score_delta_estimate=0.03 if holes_closed else 0.0,
        evidence={
            "fill_holes_returned": success,
            "is_watertight": after_watertight,
            "open_edges_before": before_open_edges,
            "face_count_after": len(mesh.faces),
        },
    )


# ---------------------------------------------------------------------------
# 3. retopo_auto
# ---------------------------------------------------------------------------


def retopo_auto(executor: Any, **_: Any) -> RepairOperatorResult:
    """Re-run the topology stage with stricter target_quads and manifold flag.

    Stricter settings: cut declared ``target_quads`` by 25% and force
    ``manifold_strict``. The topology stage's run() picks up the
    runtime_config overrides; we only patch them here.
    """
    try:
        from .core.stages import topology as stage_topology
    except Exception as exc:  # pragma: no cover - import guard
        return RepairOperatorResult(error=f"cannot import topology stage: {exc}")

    runtime_cfg = getattr(executor, "runtime_config", None)
    if not isinstance(runtime_cfg, dict):
        return RepairOperatorResult(error="executor.runtime_config missing")
    topo_cfg = runtime_cfg.setdefault("topology", {})

    build_topo = (executor.asset.get("build", {}) or {}).get("topology", {}) or {}
    declared_quads = int(topo_cfg.get("target_quads") or build_topo.get("target_quads") or 0)
    new_target = max(64, int(declared_quads * 0.75)) if declared_quads > 0 else 0

    if new_target > 0:
        topo_cfg["target_quads"] = new_target
    topo_cfg["manifold_strict"] = True
    topo_cfg["retopo_pass"] = int(topo_cfg.get("retopo_pass", 0)) + 1

    shape_bundle = executor.runtime.get("shape", {}).get("bundle")
    if shape_bundle is None:
        return RepairOperatorResult(error="shape bundle missing; cannot rerun topology")

    try:
        new_topology_bundle = stage_topology.run(executor, shape_bundle)
    except Exception as exc:
        return RepairOperatorResult(error=f"topology rerun failed: {exc}")

    new_mesh = _runtime_mesh_or_none(executor, "topology")
    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.03,
        evidence={
            "target_quads": new_target,
            "manifold_strict": True,
            "retopo_pass": topo_cfg["retopo_pass"],
            "face_count_after": len(new_mesh.faces) if new_mesh is not None else 0,
            "topology_backend": new_topology_bundle.get("backend_id"),
        },
    )


# ---------------------------------------------------------------------------
# 4. reduce_tris
# ---------------------------------------------------------------------------


def reduce_tris(executor: Any, **_: Any) -> RepairOperatorResult:
    """Decimate the runtime mesh to 70% of the current target via QEM."""
    mesh = _runtime_mesh_or_none(executor, "uv") or _runtime_mesh_or_none(executor, "topology")
    if mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    before_tris = len(mesh.faces)
    if before_tris < 32:
        return RepairOperatorResult(
            error=f"mesh too small to decimate ({before_tris} tris)",
            evidence={"face_count": before_tris},
        )

    target_ratio = 0.70
    target_faces = max(16, int(before_tris * target_ratio))

    new_mesh: trimesh.Trimesh | None = None
    method_used = ""
    try:
        if hasattr(mesh, "simplify_quadric_decimation"):
            new_mesh = mesh.simplify_quadric_decimation(target_faces)
            method_used = "trimesh.simplify_quadric_decimation"
    except Exception:
        new_mesh = None
    if new_mesh is None or len(new_mesh.faces) == 0:
        try:
            from .stages.lod import decimate as _qem_decimate

            new_mesh = _qem_decimate(mesh, target_ratio)
            method_used = "lathe.stages.lod.decimate"
        except Exception as exc:
            return RepairOperatorResult(error=f"decimation failed: {exc}")

    if new_mesh is None or len(new_mesh.faces) == 0:
        return RepairOperatorResult(error="decimation produced empty mesh")

    after_tris = len(new_mesh.faces)
    _replace_runtime_mesh(executor, "uv", new_mesh)
    _replace_runtime_mesh(executor, "topology", new_mesh)

    return RepairOperatorResult(
        applied_change=after_tris < before_tris,
        score_delta_estimate=0.015 if after_tris < before_tris else 0.0,
        evidence={
            "before_tris": before_tris,
            "after_tris": after_tris,
            "target_ratio": target_ratio,
            "method": method_used,
        },
    )


# ---------------------------------------------------------------------------
# 5. repack_uvs
# ---------------------------------------------------------------------------


def repack_uvs(executor: Any, **_: Any) -> RepairOperatorResult:
    """Re-run UV stage with tighter padding and packing settings."""
    try:
        from .core.stages import uv as stage_uv
    except Exception as exc:  # pragma: no cover - import guard
        return RepairOperatorResult(error=f"cannot import uv stage: {exc}")

    runtime_cfg = getattr(executor, "runtime_config", None)
    if not isinstance(runtime_cfg, dict):
        return RepairOperatorResult(error="executor.runtime_config missing")
    uv_cfg = runtime_cfg.setdefault("uv", {})
    prev_padding = uv_cfg.get("padding", 4.0)
    try:
        prev_padding_val = float(prev_padding)
    except (TypeError, ValueError):
        prev_padding_val = 4.0
    # Tighter padding (lower number → tighter pack), capped to a sensible floor.
    new_padding = max(1.0, prev_padding_val * 0.75)
    uv_cfg["padding"] = new_padding
    uv_cfg["pack_resolution"] = int(uv_cfg.get("pack_resolution", 2048))
    uv_cfg["repack_pass"] = int(uv_cfg.get("repack_pass", 0)) + 1

    topology_bundle = executor.runtime.get("topology", {}).get("bundle")
    if topology_bundle is None:
        return RepairOperatorResult(error="topology bundle missing; cannot rerun uv")

    try:
        new_uv_bundle = stage_uv.run(executor, topology_bundle)
    except Exception as exc:
        return RepairOperatorResult(error=f"uv rerun failed: {exc}")

    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.01,
        evidence={
            "padding": new_padding,
            "pack_resolution": uv_cfg["pack_resolution"],
            "repack_pass": uv_cfg["repack_pass"],
            "uv_backend": new_uv_bundle.get("backend_id"),
            "actual_adapter": (new_uv_bundle.get("adapter_report") or {}).get("actual_adapter"),
        },
    )


# ---------------------------------------------------------------------------
# 6. rebake_maps
# ---------------------------------------------------------------------------


def rebake_maps(executor: Any, **_: Any) -> RepairOperatorResult:
    """Re-run high→low bake transfer through the surface stage repair path."""
    try:
        from .core.stages import surface as stage_surface
    except Exception as exc:  # pragma: no cover - import guard
        return RepairOperatorResult(error=f"cannot import surface stage: {exc}")

    uv_bundle = executor.runtime.get("uv", {}).get("bundle")
    if uv_bundle is None:
        return RepairOperatorResult(error="uv bundle missing; cannot rerun bake")

    runtime_cfg = getattr(executor, "runtime_config", None)
    if isinstance(runtime_cfg, dict):
        bake_cfg = runtime_cfg.setdefault("bake", {})
        bake_cfg["rebake_pass"] = int(bake_cfg.get("rebake_pass", 0)) + 1

    try:
        new_surface_bundle = stage_surface.run(executor, uv_bundle, repair_mode="rebake_maps_v1")
    except Exception as exc:
        return RepairOperatorResult(error=f"surface rebake failed: {exc}")

    bake_report = (
        (new_surface_bundle or {}).get("bake_report")
        or (new_surface_bundle or {}).get("bake_transfer")
        or {}
    )
    return RepairOperatorResult(
        applied_change=bool(new_surface_bundle),
        score_delta_estimate=0.02,
        evidence={
            "surface_backend": (new_surface_bundle or {}).get("backend_id"),
            "bake_report_keys": sorted(bake_report.keys()) if isinstance(bake_report, dict) else [],
            "rebake_pass": (
                (runtime_cfg or {}).get("bake", {}).get("rebake_pass") if isinstance(runtime_cfg, dict) else None
            ),
        },
    )


# ---------------------------------------------------------------------------
# 7. normalize_pivots
# ---------------------------------------------------------------------------


def _floor_contact_pivot(asset: dict[str, Any]) -> dict[str, Any] | None:
    interfaces_cfg = (asset.get("build", {}) or {}).get("interfaces", {}) or {}
    pivots = interfaces_cfg.get("pivots") or []
    if not isinstance(pivots, list):
        return None
    for raw in pivots:
        if isinstance(raw, dict):
            pid = str(raw.get("id") or raw.get("name") or "")
            ptype = str(raw.get("pivot_type") or raw.get("type") or "")
            if pid == "floor_contact" or ptype == "contact":
                return raw
    return None


def normalize_pivots(executor: Any, **_: Any) -> RepairOperatorResult:
    """Translate the runtime mesh so origin sits at the floor-contact pivot."""
    pivot_decl = _floor_contact_pivot(executor.asset)
    if pivot_decl is None:
        return RepairOperatorResult(error="no contact pivot declared in interfaces")

    mesh_uv = _runtime_mesh_or_none(executor, "uv")
    mesh_topo = _runtime_mesh_or_none(executor, "topology")
    target_mesh = mesh_uv or mesh_topo
    if target_mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    bounds = target_mesh.bounds
    centroid = target_mesh.bounding_box.centroid
    contact_origin = np.array(
        [float(centroid[0]), float(bounds[0, 1]), float(centroid[2])],
        dtype=np.float64,
    )

    if float(np.linalg.norm(contact_origin)) < 1e-9:
        return RepairOperatorResult(
            applied_change=False,
            evidence={"already_normalized": True, "translation": [0.0, 0.0, 0.0]},
        )

    translation = -contact_origin
    xform = np.eye(4, dtype=np.float64)
    xform[:3, 3] = translation
    if mesh_uv is not None:
        mesh_uv.apply_transform(xform)
    if mesh_topo is not None and mesh_topo is not mesh_uv:
        mesh_topo.apply_transform(xform)

    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.005,
        evidence={
            "pivot_id": str(pivot_decl.get("id") or pivot_decl.get("name") or "floor_contact"),
            "translation": [round(float(translation[0]), 6), round(float(translation[1]), 6), round(float(translation[2]), 6)],
        },
    )


# ---------------------------------------------------------------------------
# 8. create_collision_proxy
# ---------------------------------------------------------------------------


def _try_vhacd_decompose(mesh: trimesh.Trimesh, max_hulls: int) -> list[trimesh.Trimesh] | None:
    """Try V-HACD decomposition via ``pyvhacd`` if installed; None otherwise."""
    try:
        import pyvhacd  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int32)
        hulls = pyvhacd.compute_vhacd(verts, faces, max_convex_hulls=max_hulls)
    except Exception:
        return None
    out: list[trimesh.Trimesh] = []
    for entry in hulls or []:
        try:
            v = np.asarray(entry["vertices"], dtype=np.float64)
            f = np.asarray(entry["faces"], dtype=np.int64)
            if len(v) == 0 or len(f) == 0:
                continue
            out.append(trimesh.Trimesh(vertices=v, faces=f, process=False))
        except Exception:
            continue
    return out or None


def create_collision_proxy(executor: Any, **_: Any) -> RepairOperatorResult:
    """Generate convex-decomposition collision hulls for the runtime mesh."""
    mesh = _runtime_mesh_or_none(executor, "uv") or _runtime_mesh_or_none(executor, "topology")
    if mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    physics_cfg = (executor.asset.get("build", {}) or {}).get("physics", {}) or {}
    max_hulls_raw = physics_cfg.get("max_hulls", 6)
    try:
        max_hulls = max(1, int(max_hulls_raw))
    except (TypeError, ValueError):
        max_hulls = 6

    method = "convex_hull"
    hulls = _try_vhacd_decompose(mesh, max_hulls)
    if hulls is not None and len(hulls) > 0:
        method = "vhacd"
    else:
        # Fall back to per-connected-component convex hulls (deterministic).
        try:
            components = mesh.split(only_watertight=False)
        except Exception:
            components = []
        components_list = list(components) if components else [mesh]
        components_list = components_list[:max_hulls]
        hulls = []
        for comp in components_list:
            try:
                hull = comp.convex_hull
                if isinstance(hull, trimesh.Trimesh) and len(hull.faces) > 0:
                    hulls.append(hull)
            except Exception:
                continue
        if not hulls:
            try:
                hulls = [mesh.convex_hull]
                method = "single_convex_hull_fallback"
            except Exception as exc:
                return RepairOperatorResult(error=f"convex_hull failed: {exc}")
            else:
                if not hulls or len(hulls[0].faces) == 0:
                    return RepairOperatorResult(error="convex hull empty")

    physics_runtime = executor.runtime.setdefault("physics", {})
    bundle = physics_runtime.setdefault("bundle", {})
    proxy_records = []
    for idx, hull in enumerate(hulls):
        bounds = hull.bounds
        proxy_records.append(
            {
                "name": f"hull_{idx:02d}",
                "vertex_count": int(len(hull.vertices)),
                "face_count": int(len(hull.faces)),
                "aabb_min": [float(bounds[0, 0]), float(bounds[0, 1]), float(bounds[0, 2])],
                "aabb_max": [float(bounds[1, 0]), float(bounds[1, 1]), float(bounds[1, 2])],
            }
        )
    bundle["repair_collision_proxy"] = {
        "method": method,
        "max_hulls": max_hulls,
        "hull_count": len(hulls),
        "hulls": proxy_records,
    }

    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.005,
        evidence={
            "method": method,
            "hull_count": len(hulls),
            "max_hulls_requested": max_hulls,
        },
    )


# ---------------------------------------------------------------------------
# 9. generate_lods
# ---------------------------------------------------------------------------


_DEFAULT_LOD_RATIOS = (1.0, 0.5, 0.25, 0.125)


def generate_lods(executor: Any, **_: Any) -> RepairOperatorResult:
    """Generate or backfill the LOD chain via QEM decimation if missing."""
    mesh = _runtime_mesh_or_none(executor, "uv") or _runtime_mesh_or_none(executor, "topology")
    if mesh is None:
        return RepairOperatorResult(error="no runtime mesh available")

    try:
        from .stages.lod import build_lods
    except Exception as exc:  # pragma: no cover - import guard
        return RepairOperatorResult(error=f"cannot import lod builder: {exc}")

    optimize_runtime = executor.runtime.setdefault("optimize", {})
    optimize_bundle = optimize_runtime.setdefault("bundle", {})
    existing_lods = optimize_bundle.get("lods") or []
    existing_levels = {
        int(entry.get("level", entry.get("name", "lod0").lstrip("lod"))) for entry in existing_lods if isinstance(entry, dict)
    } if isinstance(existing_lods, list) else set()
    if {0, 1, 2, 3} <= existing_levels:
        return RepairOperatorResult(
            applied_change=False,
            evidence={"existing_levels": sorted(existing_levels), "skipped": True},
        )

    try:
        results = build_lods(mesh, list(_DEFAULT_LOD_RATIOS))
    except Exception as exc:
        return RepairOperatorResult(error=f"build_lods failed: {exc}")

    lods_summary = []
    for result in results:
        lods_summary.append(
            {
                "name": f"lod{result.level}",
                "level": int(result.level),
                "ratio": float(result.ratio),
                "triangle_count": int(result.tris),
                "vertex_count": int(result.verts),
                "decimation": "quadric_edge_collapse" if result.ratio < 1.0 else "source",
            }
        )
    optimize_bundle["repair_lods"] = lods_summary

    return RepairOperatorResult(
        applied_change=True,
        score_delta_estimate=0.005,
        evidence={
            "ratios": list(_DEFAULT_LOD_RATIOS),
            "level_count": len(lods_summary),
            "levels": [entry["level"] for entry in lods_summary],
        },
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

OPERATOR_REGISTRY: dict[str, Any] = {
    "enforce_symmetry": enforce_symmetry,
    "seal_mesh": seal_mesh,
    "retopo_auto": retopo_auto,
    "reduce_tris": reduce_tris,
    "repack_uvs": repack_uvs,
    "rebake_maps": rebake_maps,
    "normalize_pivots": normalize_pivots,
    "create_collision_proxy": create_collision_proxy,
    "generate_lods": generate_lods,
}


def dispatch_operator(name: str, executor: Any, **kwargs: Any) -> RepairOperatorResult:
    """Look up ``name`` in :data:`OPERATOR_REGISTRY` and invoke it."""
    op = OPERATOR_REGISTRY.get(name)
    if op is None:
        return RepairOperatorResult(error=f"unknown repair operator: {name!r}")
    try:
        return op(executor, **kwargs)
    except Exception as exc:  # pragma: no cover - last-resort guard
        return RepairOperatorResult(error=f"operator {name!r} raised: {exc}")


__all__ = [
    "RepairOperatorResult",
    "OPERATOR_REGISTRY",
    "dispatch_operator",
    "enforce_symmetry",
    "seal_mesh",
    "retopo_auto",
    "reduce_tris",
    "repack_uvs",
    "rebake_maps",
    "normalize_pivots",
    "create_collision_proxy",
    "generate_lods",
]
