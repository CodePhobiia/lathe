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


def cook_runtime_artifact(
    asset: FoundryAsset,
    *,
    render_mesh_path: str | Path | None = None,
    collision_proxy_path: str | Path | None = None,
    walkable_polygon_path: str | Path | None = None,
    lod_paths: tuple[str | Path, ...] | None = None,
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
            walkable_zones=spec.collision.walkable_zones,
            blocking_zones=spec.collision.blocking_zones,
            hazard_zones=spec.collision.hazard_zones,
        )
    else:
        proxy_path, proxy_status, proxy_reason = _resolve_render_mesh_status(
            collision_proxy_path
        )
        collision = CollisionProxySpec(
            strategy=collision_strategy,
            proxy_artifact_path=proxy_path,
            proxy_status=proxy_status,
            proxy_status_reason=proxy_reason,
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
        preserve_silhouette=spec.lod_policy.preserve_silhouette,
    )

    # Material-zone manifest from material_slots.
    material_zone_manifest: dict[str, str] = {}
    for slot in spec.material_slots:
        material_zone_manifest[slot.zone_id_prefix] = slot.material_class

    # Engine readiness — default to proxy when LOD/collision are unbuilt.
    engine_readiness: dict[str, str] = {}
    overall_ready = (
        render_status == "real"
        and (
            collision.proxy_status in {"real", "unbuilt"}
            and spec.collision.strategy != "none"
            or spec.collision.strategy == "none"
        )
        and lod.lod_status in {"real", "proxy"}
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
    "cook_runtime_artifact",
    "runtime_manifest_to_dict",
]
