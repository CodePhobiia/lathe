"""Foundry F6 — runtime asset cooking.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §6.4
+ §18.F6, the runtime cooker turns a generator's declarative spec
(``FoundryAsset``) into a ``RuntimeArtifactManifest`` recording:

- render mesh path (or unbuilt status with reason);
- collision proxy spec + path;
- nav contribution spec + walkable polygon set;
- LOD chain spec + per-level paths;
- material zone manifest (zone -> material slot);
- semantic sockets;
- scale/pivot/unit validation;
- per-engine export readiness.

This module is purely declarative. It does NOT build meshes; it
produces a manifest that downstream stages (the .lthpkg writer, the
@lathe/three loader) consume.

Per masterplan §3 (no-fake-quality): every artifact path is either
``"real"`` (artifact exists), ``"proxy"`` (placeholder labeled), or
``"unbuilt"`` (status with reason). Never invented.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .generators._base import (
    CollisionSpec,
    FoundryAsset,
    LodPolicy,
)

RUNTIME_COOK_VERSION = "lathe.asset_foundry.runtime_cook_v1"


@dataclass(frozen=True)
class CollisionProxySpec:
    """Cooked collision proxy descriptor."""

    strategy: str
    """``hull``, ``compound_hulls``, ``box``, ``capsule``,
    ``walkable_surface_only``, ``none``."""

    proxy_artifact_path: str | None
    """Path to the collision proxy artifact when present; else None."""

    proxy_status: str
    """``real``, ``proxy``, ``unbuilt``."""

    proxy_status_reason: str = ""
    decomposition_strategy: str = ""
    proxy_component_count: int = 0
    walkable_zones: tuple[str, ...] = ()
    blocking_zones: tuple[str, ...] = ()
    hazard_zones: tuple[str, ...] = ()


@dataclass(frozen=True)
class NavContributionSpec:
    """Cooked nav-contribution descriptor."""

    contributes: bool
    walkable_polygon_artifact_path: str | None
    nav_status: str
    """``real``, ``proxy``, ``unbuilt``."""

    nav_status_reason: str = ""
    walkable_zones: tuple[str, ...] = ()


@dataclass(frozen=True)
class LodPolicySpec:
    """Cooked LOD chain descriptor."""

    lod_levels: int
    target_triangle_counts: tuple[int, ...]
    lod_artifact_paths: tuple[str, ...]
    lod_status: str
    lod_status_reason: str = ""
    actual_triangle_counts: tuple[int, ...] = ()
    preserve_silhouette: bool = True


@dataclass(frozen=True)
class RuntimeArtifactManifest:
    """The cooked runtime manifest emitted into the .lthpkg sidecar."""

    version: str
    asset_id: str
    style_pack_id: str
    family: str
    bbox_cm: tuple[tuple[float, float, float], tuple[float, float, float]]
    units: str
    """Always ``"cm"`` at the manifest layer (engine adapters convert)."""

    pivot_cm: tuple[float, float, float]
    scale_anchor: str
    """e.g. ``third_person_player``."""

    render_mesh_artifact_path: str | None
    render_mesh_status: str
    """``real`` | ``proxy`` | ``unbuilt``."""

    render_mesh_status_reason: str

    collision: CollisionProxySpec
    nav: NavContributionSpec
    lod: LodPolicySpec
    material_zone_manifest: Mapping[str, str]
    """zone_id_prefix -> material_class."""

    semantic_sockets: tuple[dict[str, Any], ...]
    semantic_parts: tuple[str, ...]
    quality_ladder_target: int
    diagnostics: tuple[str, ...]
    engine_readiness: Mapping[str, str]
    """engine_id -> ``"ready"`` | ``"proxy"`` | ``"unsupported"``."""


def _resolve_render_mesh_status(
    render_mesh_path: str | Path | None,
) -> tuple[str | None, str, str]:
    """Resolve render mesh path/status/reason from an optional path."""
    if render_mesh_path is None:
        return None, "unbuilt", "no_render_mesh_path_provided"
    path = Path(render_mesh_path)
    if path.exists():
        return str(path).replace("\\", "/"), "real", ""
    return str(path).replace("\\", "/"), "unbuilt", "path_does_not_exist"


def _resolve_lod_paths(
    lod_paths: tuple[str | Path, ...] | None, expected_levels: int
) -> tuple[tuple[str, ...], str, str]:
    """Resolve LOD chain artifact paths/status."""
    if not lod_paths:
        return (), "unbuilt", "no_lod_paths_provided"
    artifact_paths: list[str] = []
    real_count = 0
    for p in lod_paths:
        path = Path(p)
        if path.exists():
            real_count += 1
        artifact_paths.append(str(path).replace("\\", "/"))
    if real_count == expected_levels and real_count > 0:
        return tuple(artifact_paths), "real", ""
    if real_count == 0:
        return tuple(artifact_paths), "unbuilt", f"none_of_{len(artifact_paths)}_paths_exist"
    return (
        tuple(artifact_paths),
        "proxy",
        f"partial_{real_count}_of_{expected_levels}_lods_present",
    )


def _face_triangle_count(face: list[int]) -> int:
    return max(0, len(face) - 2)


def _bbox_for_vertices(
    vertices: list[list[float]],
) -> tuple[list[float], list[float]] | None:
    if not vertices:
        return None
    min_corner = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    max_corner = [max(vertex[axis] for vertex in vertices) for axis in range(3)]
    return min_corner, max_corner


def _compound_collision_components_for_prismatic_payload(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    for crystal in payload.get("crystals") or []:
        if not isinstance(crystal, Mapping):
            continue
        raw_vertices = crystal.get("vertices")
        if not isinstance(raw_vertices, list):
            continue
        translation = crystal.get("translation_cm")
        tx, ty, tz = (0.0, 0.0, 0.0)
        if isinstance(translation, list) and len(translation) >= 3:
            tx, ty, tz = (
                float(translation[0]),
                float(translation[1]),
                float(translation[2]),
            )
        vertices: list[list[float]] = []
        for vertex in raw_vertices:
            if isinstance(vertex, list) and len(vertex) >= 3:
                vertices.append(
                    [
                        float(vertex[0]) + tx,
                        float(vertex[1]) + ty,
                        float(vertex[2]) + tz,
                    ]
                )
        bbox = _bbox_for_vertices(vertices)
        if bbox is None:
            continue
        min_corner, max_corner = bbox
        component_id = str(crystal.get("crystal_id") or f"component_{len(components):03d}")
        components.append(
            {
                "component_id": component_id,
                "proxy_kind": "convex_aabb_hull",
                "semantic_part": str(crystal.get("role") or component_id),
                "bbox_cm": [min_corner, max_corner],
                "vertex_count": len(vertices),
            }
        )
    return components


def lower_foundry_asset_runtime_artifacts(
    asset: FoundryAsset,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Lower one supported Foundry geometry payload into real JSON artifacts.

    This is intentionally narrow: it currently supports the Golden Asset
    `prismatic_cluster` payload produced by `build_violet_crystal_cluster`.
    The artifacts are deterministic Lathe mesh JSON files, not GLB exports.
    They are sufficient for runtime sidecar truth: paths exist, face counts
    are recorded, collision and LOD files are explicit.
    """
    payload = asset.spec.geometry_payload
    if not isinstance(payload, Mapping) or payload.get("kind") != "prismatic_cluster":
        return {
            "status": "unsupported",
            "blocker": "runtime_lowering_payload_not_supported",
            "artifact_paths": {},
        }

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    face_zone_ids: list[str] = []
    for crystal in payload.get("crystals") or []:
        if not isinstance(crystal, Mapping):
            continue
        raw_vertices = crystal.get("vertices")
        raw_faces = crystal.get("faces")
        raw_zones = crystal.get("face_zone_ids")
        if not isinstance(raw_vertices, list) or not isinstance(raw_faces, list):
            continue
        translation = crystal.get("translation_cm")
        tx, ty, tz = (0.0, 0.0, 0.0)
        if isinstance(translation, list) and len(translation) >= 3:
            tx, ty, tz = (float(translation[0]), float(translation[1]), float(translation[2]))
        vertex_offset = len(vertices)
        for vertex in raw_vertices:
            if isinstance(vertex, list) and len(vertex) >= 3:
                vertices.append(
                    [
                        float(vertex[0]) + tx,
                        float(vertex[1]) + ty,
                        float(vertex[2]) + tz,
                    ]
                )
        for index, face in enumerate(raw_faces):
            if not isinstance(face, list) or len(face) < 3:
                continue
            faces.append([int(i) + vertex_offset for i in face])
            if isinstance(raw_zones, list) and index < len(raw_zones):
                face_zone_ids.append(str(raw_zones[index]))
            else:
                face_zone_ids.append(str(crystal.get("zone_id_prefix") or "crystal"))

    render_mesh_path = output_root / "render_mesh.lathe-mesh.json"
    render_payload = {
        "version": "lathe.asset_foundry.runtime_mesh_json_v1",
        "asset_id": asset.asset_id,
        "status": "real",
        "format": "lathe_mesh_json",
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "triangle_count": sum(_face_triangle_count(face) for face in faces),
        "vertices": vertices,
        "faces": faces,
        "face_zone_ids": face_zone_ids,
        "material_zone_manifest": {
            slot.zone_id_prefix: slot.material_class for slot in asset.spec.material_slots
        },
        "semantic_parts": list(asset.spec.semantic_parts),
    }
    render_mesh_path.write_text(json.dumps(render_payload, indent=2), encoding="utf-8")

    collision_path = output_root / "collision_proxy.lathe-collision.json"
    collision_components = _compound_collision_components_for_prismatic_payload(payload)
    collision_payload = {
        "version": "lathe.asset_foundry.collision_proxy_v1",
        "asset_id": asset.asset_id,
        "status": "real",
        "strategy": asset.spec.collision.strategy,
        "bbox_cm": [list(asset.bbox_cm[0]), list(asset.bbox_cm[1])],
        "blocking_zones": list(asset.spec.collision.blocking_zones),
        "walkable_zones": list(asset.spec.collision.walkable_zones),
        "proxy_kind": (
            "compound_convex_aabb_decomposition"
            if collision_components
            else "asset_bbox_proxy"
        ),
        "decomposition_strategy": (
            "per_prismatic_component_aabb_hulls_v1"
            if collision_components
            else "single_asset_bbox_v1"
        ),
        "component_count": len(collision_components) if collision_components else 1,
        "components": collision_components
        if collision_components
        else [
            {
                "component_id": f"{asset.asset_id}.bbox",
                "proxy_kind": "convex_aabb_hull",
                "semantic_part": "asset_bounds",
                "bbox_cm": [list(asset.bbox_cm[0]), list(asset.bbox_cm[1])],
            }
        ],
    }
    collision_path.write_text(json.dumps(collision_payload, indent=2), encoding="utf-8")

    lod_paths: list[Path] = []
    lod_actual_counts: list[int] = []
    target_counts = asset.spec.lod_policy.target_triangle_counts
    for level in range(asset.spec.lod_policy.lod_levels):
        target = target_counts[min(level, len(target_counts) - 1)] if target_counts else 0
        tri_count = 0
        lod_faces: list[list[int]] = []
        lod_zones: list[str] = []
        for face, zone in zip(faces, face_zone_ids):
            face_tris = _face_triangle_count(face)
            if lod_faces and target > 0 and tri_count + face_tris > target:
                break
            lod_faces.append(face)
            lod_zones.append(zone)
            tri_count += face_tris
        if not lod_faces and faces:
            lod_faces = [faces[0]]
            lod_zones = [face_zone_ids[0] if face_zone_ids else "lod"]
            tri_count = _face_triangle_count(faces[0])
        lod_path = output_root / f"lod_{level:02d}.lathe-mesh.json"
        lod_payload = {
            "version": "lathe.asset_foundry.runtime_lod_mesh_json_v1",
            "asset_id": asset.asset_id,
            "level": level,
            "status": "real",
            "target_triangle_count": target,
            "actual_triangle_count": tri_count,
            "preserve_silhouette": asset.spec.lod_policy.preserve_silhouette,
            "vertices": vertices,
            "faces": lod_faces,
            "face_zone_ids": lod_zones,
        }
        lod_path.write_text(json.dumps(lod_payload, indent=2), encoding="utf-8")
        lod_paths.append(lod_path)
        lod_actual_counts.append(tri_count)

    return {
        "status": "real",
        "render_mesh_path": render_mesh_path,
        "collision_proxy_path": collision_path,
        "lod_paths": tuple(lod_paths),
        "lod_actual_triangle_counts": tuple(lod_actual_counts),
        "artifact_paths": {
            "render_mesh": str(render_mesh_path),
            "collision_proxy": str(collision_path),
            "lod": [str(path) for path in lod_paths],
        },
    }


def cook_generated_runtime_artifact(
    asset: FoundryAsset,
    output_dir: str | Path,
    **cook_kwargs: Any,
) -> RuntimeArtifactManifest:
    """Lower supported generator payloads, then cook the runtime manifest."""
    lowered = lower_foundry_asset_runtime_artifacts(asset, output_dir)
    if lowered.get("status") != "real":
        return cook_runtime_artifact(asset, **cook_kwargs)
    return cook_runtime_artifact(
        asset,
        render_mesh_path=lowered["render_mesh_path"],
        collision_proxy_path=lowered["collision_proxy_path"],
        lod_paths=lowered["lod_paths"],
        lod_actual_triangle_counts=lowered["lod_actual_triangle_counts"],
        **cook_kwargs,
    )


def _inspect_collision_proxy_artifact(path: str) -> tuple[str, int]:
    """Read collision proxy metadata without treating malformed files as ready."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", 0
    if not isinstance(payload, Mapping):
        return "", 0
    strategy = str(payload.get("decomposition_strategy") or "")
    component_count = payload.get("component_count")
    if not isinstance(component_count, int):
        components = payload.get("components")
        component_count = len(components) if isinstance(components, list) else 0
    return strategy, max(0, int(component_count))


def cook_runtime_artifact(
    asset: FoundryAsset,
    *,
    render_mesh_path: str | Path | None = None,
    collision_proxy_path: str | Path | None = None,
    walkable_polygon_path: str | Path | None = None,
    lod_paths: tuple[str | Path, ...] | None = None,
    lod_actual_triangle_counts: tuple[int, ...] | None = None,
    pivot_cm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale_anchor: str = "third_person_player",
    target_engines: tuple[str, ...] = ("roblox", "unity", "unreal", "usd", "gltf"),
) -> RuntimeArtifactManifest:
    """Cook a FoundryAsset spec into a RuntimeArtifactManifest.

    Pure function. Does NOT build geometry. Resolves the artifact
    paths (if provided) into truthful status records, and emits the
    full manifest the .lthpkg writer consumes.
    """
    spec = asset.spec

    render_path, render_status, render_reason = _resolve_render_mesh_status(
        render_mesh_path
    )

    # Collision.
    collision_strategy = spec.collision.strategy
    if collision_strategy == "none":
        collision = CollisionProxySpec(
            strategy=collision_strategy,
            proxy_artifact_path=None,
            proxy_status="unbuilt",
            proxy_status_reason="strategy_none_no_proxy_needed",
            decomposition_strategy="none",
            proxy_component_count=0,
            walkable_zones=spec.collision.walkable_zones,
            blocking_zones=spec.collision.blocking_zones,
            hazard_zones=spec.collision.hazard_zones,
        )
    else:
        proxy_path, proxy_status, proxy_reason = _resolve_render_mesh_status(
            collision_proxy_path
        )
        decomposition_strategy = ""
        proxy_component_count = 0
        if proxy_status == "real" and proxy_path:
            (
                decomposition_strategy,
                proxy_component_count,
            ) = _inspect_collision_proxy_artifact(proxy_path)
        collision = CollisionProxySpec(
            strategy=collision_strategy,
            proxy_artifact_path=proxy_path,
            proxy_status=proxy_status,
            proxy_status_reason=proxy_reason,
            decomposition_strategy=decomposition_strategy,
            proxy_component_count=proxy_component_count,
            walkable_zones=spec.collision.walkable_zones,
            blocking_zones=spec.collision.blocking_zones,
            hazard_zones=spec.collision.hazard_zones,
        )

    # Nav.
    nav_contributes = bool(spec.collision.walkable_zones)
    if nav_contributes:
        nav_path, nav_status, nav_reason = _resolve_render_mesh_status(walkable_polygon_path)
        nav = NavContributionSpec(
            contributes=True,
            walkable_polygon_artifact_path=nav_path,
            nav_status=nav_status,
            nav_status_reason=nav_reason,
            walkable_zones=spec.collision.walkable_zones,
        )
    else:
        nav = NavContributionSpec(
            contributes=False,
            walkable_polygon_artifact_path=None,
            nav_status="unbuilt",
            nav_status_reason="no_walkable_zones_declared",
            walkable_zones=(),
        )

    # LOD.
    lod_artifact_paths, lod_status, lod_reason = _resolve_lod_paths(
        lod_paths, spec.lod_policy.lod_levels
    )
    lod = LodPolicySpec(
        lod_levels=spec.lod_policy.lod_levels,
        target_triangle_counts=spec.lod_policy.target_triangle_counts,
        lod_artifact_paths=lod_artifact_paths,
        lod_status=lod_status,
        lod_status_reason=lod_reason,
        actual_triangle_counts=lod_actual_triangle_counts or (),
        preserve_silhouette=spec.lod_policy.preserve_silhouette,
    )

    # Material-zone manifest from material_slots.
    material_zone_manifest: dict[str, str] = {}
    for slot in spec.material_slots:
        material_zone_manifest[slot.zone_id_prefix] = slot.material_class

    # Engine readiness is intentionally conservative. A real render mesh is
    # not enough to claim engine readiness when a declared collision proxy,
    # LOD chain, or material-zone manifest is missing.
    engine_readiness: dict[str, str] = {}
    collision_ready = (
        spec.collision.strategy == "none" or collision.proxy_status == "real"
    )
    material_ready = bool(material_zone_manifest)
    overall_ready = (
        render_status == "real"
        and collision_ready
        and lod.lod_status == "real"
        and material_ready
    )
    for engine in target_engines:
        if overall_ready:
            engine_readiness[engine] = "ready"
        elif render_status == "proxy":
            engine_readiness[engine] = "proxy"
        else:
            engine_readiness[engine] = "unsupported"

    # Semantic sockets — flatten for serialization.
    sockets = tuple(
        {
            "socket_id": s.socket_id,
            "role": s.role,
            "position_cm": list(s.position_cm),
            "orientation_quat": list(s.orientation_quat),
            "capacity": s.capacity,
            "allowed_attachments": list(s.allowed_attachments),
        }
        for s in spec.sockets
    )

    return RuntimeArtifactManifest(
        version=RUNTIME_COOK_VERSION,
        asset_id=asset.asset_id,
        style_pack_id=spec.style_pack_id,
        family=spec.family,
        bbox_cm=asset.bbox_cm,
        units="cm",
        pivot_cm=pivot_cm,
        scale_anchor=scale_anchor,
        render_mesh_artifact_path=render_path,
        render_mesh_status=render_status,
        render_mesh_status_reason=render_reason,
        collision=collision,
        nav=nav,
        lod=lod,
        material_zone_manifest=material_zone_manifest,
        semantic_sockets=sockets,
        semantic_parts=spec.semantic_parts,
        quality_ladder_target=asset.quality_ladder_target,
        diagnostics=spec.diagnostics,
        engine_readiness=engine_readiness,
    )


def runtime_manifest_to_dict(manifest: RuntimeArtifactManifest) -> dict[str, Any]:
    """Serialize a RuntimeArtifactManifest to a JSON-compatible dict."""
    return {
        "version": manifest.version,
        "asset_id": manifest.asset_id,
        "style_pack_id": manifest.style_pack_id,
        "family": manifest.family,
        "bbox_cm": [list(manifest.bbox_cm[0]), list(manifest.bbox_cm[1])],
        "units": manifest.units,
        "pivot_cm": list(manifest.pivot_cm),
        "scale_anchor": manifest.scale_anchor,
        "render_mesh": {
            "artifact_path": manifest.render_mesh_artifact_path,
            "status": manifest.render_mesh_status,
            "status_reason": manifest.render_mesh_status_reason,
        },
        "collision": {
            "strategy": manifest.collision.strategy,
            "proxy_artifact_path": manifest.collision.proxy_artifact_path,
            "proxy_status": manifest.collision.proxy_status,
            "proxy_status_reason": manifest.collision.proxy_status_reason,
            "decomposition_strategy": manifest.collision.decomposition_strategy,
            "proxy_component_count": manifest.collision.proxy_component_count,
            "walkable_zones": list(manifest.collision.walkable_zones),
            "blocking_zones": list(manifest.collision.blocking_zones),
            "hazard_zones": list(manifest.collision.hazard_zones),
        },
        "nav": {
            "contributes": manifest.nav.contributes,
            "walkable_polygon_artifact_path": manifest.nav.walkable_polygon_artifact_path,
            "nav_status": manifest.nav.nav_status,
            "nav_status_reason": manifest.nav.nav_status_reason,
            "walkable_zones": list(manifest.nav.walkable_zones),
        },
        "lod": {
            "lod_levels": manifest.lod.lod_levels,
            "target_triangle_counts": list(manifest.lod.target_triangle_counts),
            "actual_triangle_counts": list(manifest.lod.actual_triangle_counts),
            "lod_artifact_paths": list(manifest.lod.lod_artifact_paths),
            "lod_status": manifest.lod.lod_status,
            "lod_status_reason": manifest.lod.lod_status_reason,
            "preserve_silhouette": manifest.lod.preserve_silhouette,
        },
        "material_zone_manifest": dict(manifest.material_zone_manifest),
        "semantic_sockets": list(manifest.semantic_sockets),
        "semantic_parts": list(manifest.semantic_parts),
        "quality_ladder_target": manifest.quality_ladder_target,
        "diagnostics": list(manifest.diagnostics),
        "engine_readiness": dict(manifest.engine_readiness),
    }


__all__ = [
    "RUNTIME_COOK_VERSION",
    "CollisionProxySpec",
    "LodPolicySpec",
    "NavContributionSpec",
    "RuntimeArtifactManifest",
    "cook_generated_runtime_artifact",
    "cook_runtime_artifact",
    "lower_foundry_asset_runtime_artifacts",
    "runtime_manifest_to_dict",
]
