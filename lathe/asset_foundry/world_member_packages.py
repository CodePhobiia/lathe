"""Package Forge world-member assets with existing Foundry generators."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..forge import WorldAsset, WorldComposition
from .certificates import compute_asset_certificate
from .generators import (
    AlpinePineParameters,
    CozyCottageParameters,
    FloatingIslandParameters,
    LanternPostParameters,
    RopeBridgeParameters,
    StonePathParameters,
    build_alpine_pine,
    build_cozy_cottage,
    build_floating_island_small,
    build_lantern_post,
    build_rope_bridge,
    build_stone_path_segment,
    build_violet_crystal_cluster,
)
from .generators._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)
from .package_writer import write_lthpkg
from .runtime_cook import cook_generated_runtime_artifact
from .world_member_meshes import write_world_member_mesh_glb

WORLD_MEMBER_PACKAGE_VERSION = "lathe.asset_foundry.world_member_package_v1"


@dataclass(frozen=True)
class WorldMemberPackageResult:
    world_asset_id: str
    asset_id: str
    role: str
    package_dir: str
    status: str
    render_mesh_status: str
    collision_status: str
    nav_status: str
    generator_id: str

    def to_link_dict(self, world_dir: Path) -> dict[str, str]:
        package_path = Path(self.package_dir)
        return {
            "status": self.status,
            "asset_id": self.asset_id,
            "role": self.role,
            "package": str(package_path.relative_to(world_dir)).replace("\\", "/"),
            "render_mesh_status": self.render_mesh_status,
            "collision_status": self.collision_status,
            "nav_status": self.nav_status,
            "generator_id": self.generator_id,
        }


def _build_waterfall_ribbon(asset: WorldAsset) -> FoundryAsset:
    width_cm = 120.0
    height_cm = 520.0
    geometry_payload = {
        "kind": "waterfall_ribbon",
        "curve_cm": [
            [0.0, 0.0, 220.0],
            [35.0, 0.0, 80.0],
            [-20.0, 0.0, -height_cm],
        ],
        "width_cm": width_cm,
        "mist_zone_id": f"{asset.asset_id}.mist",
        "surface_zone_id": f"{asset.asset_id}.water_sheet",
    }
    spec = GeneratorSpec(
        generator_id="waterfall_ribbon",
        parameters={"seed": asset.seed, "width_cm": width_cm, "height_cm": height_cm},
        seed=asset.seed,
        style_pack_id=asset.style_pack_id,
        family="environment_effect",
        semantic_parts=("water_sheet", "mist_volume"),
        geometry_payload=geometry_payload,
        material_slots=(
            MaterialSlot(
                slot_id="water_sheet",
                zone_id_prefix=f"{asset.asset_id}.water_sheet",
                material_class="water_cyan",
                uv_policy="world_scale",
            ),
            MaterialSlot(
                slot_id="mist",
                zone_id_prefix=f"{asset.asset_id}.mist",
                material_class="water_cyan",
            ),
        ),
        sockets=(
            SemanticSocket(
                socket_id="source",
                role="waterfall_source",
                position_cm=(0.0, 0.0, 220.0),
            ),
            SemanticSocket(
                socket_id="overlook_anchor",
                role="hazard_overlook",
                position_cm=(0.0, -120.0, 0.0),
            ),
        ),
        collision=CollisionSpec(
            strategy="none",
            walkable_zones=(),
            blocking_zones=(),
            hazard_zones=(f"{asset.asset_id}.mist", f"{asset.asset_id}.water_sheet"),
        ),
        lod_policy=LodPolicy(
            lod_levels=4,
            target_triangle_counts=(2000, 800, 200, 40),
            preserve_silhouette=True,
        ),
        diagnostics=("waterfall_mesh_lowerer_not_run",),
    )
    return FoundryAsset(
        asset_id=asset.asset_id,
        spec=spec,
        bbox_cm=((-width_cm / 2.0, -40.0, -height_cm), (width_cm / 2.0, 40.0, 220.0)),
        quality_ladder_target=4,
        notes="Forge world-member WaterfallRibbon spec; mesh remains unbuilt until a ribbon lowerer runs.",
    )


def _build_fence_segment(asset: WorldAsset) -> FoundryAsset:
    length_cm = 260.0
    height_cm = 95.0
    geometry_payload = {
        "kind": "fence_segment",
        "length_cm": length_cm,
        "height_cm": height_cm,
        "posts": [
            {"post_id": f"{asset.asset_id}.post_a", "translation_cm": [-length_cm / 2.0, 0.0, 0.0]},
            {"post_id": f"{asset.asset_id}.post_b", "translation_cm": [length_cm / 2.0, 0.0, 0.0]},
        ],
        "rails": [
            {"rail_id": f"{asset.asset_id}.rail_low", "z_cm": 38.0},
            {"rail_id": f"{asset.asset_id}.rail_high", "z_cm": 74.0},
        ],
    }
    spec = GeneratorSpec(
        generator_id="fence_segment",
        parameters={"seed": asset.seed, "length_cm": length_cm, "height_cm": height_cm},
        seed=asset.seed,
        style_pack_id=asset.style_pack_id,
        family="traversal",
        semantic_parts=("posts", "rails"),
        geometry_payload=geometry_payload,
        material_slots=(
            MaterialSlot(
                slot_id="wood",
                zone_id_prefix=asset.asset_id,
                material_class="wood_warm_brown",
                uv_policy="trim_sheet",
            ),
        ),
        sockets=(
            SemanticSocket(
                socket_id="endpoint_a",
                role="fence_endpoint",
                position_cm=(-length_cm / 2.0, 0.0, 0.0),
            ),
            SemanticSocket(
                socket_id="endpoint_b",
                role="fence_endpoint",
                position_cm=(length_cm / 2.0, 0.0, 0.0),
            ),
        ),
        collision=CollisionSpec(
            strategy="box",
            walkable_zones=(),
            blocking_zones=(asset.asset_id,),
            hazard_zones=(),
        ),
        lod_policy=LodPolicy(
            lod_levels=4,
            target_triangle_counts=(1200, 400, 120, 40),
            preserve_silhouette=True,
        ),
    )
    return FoundryAsset(
        asset_id=asset.asset_id,
        spec=spec,
        bbox_cm=((-length_cm / 2.0, -12.0, 0.0), (length_cm / 2.0, 12.0, height_cm)),
        quality_ladder_target=4,
        notes="Forge world-member FenceSegment spec; mesh remains unbuilt until a fence lowerer runs.",
    )


def build_foundry_asset_for_world_member(asset: WorldAsset) -> FoundryAsset:
    """Build a FoundryAsset spec for one Forge world member."""

    if asset.role == "floating_island":
        return build_floating_island_small(
            FloatingIslandParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "cottage":
        return build_cozy_cottage(
            CozyCottageParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "elder_house":
        return build_cozy_cottage(
            CozyCottageParameters(
                seed=asset.seed,
                width_cm=430.0,
                depth_cm=340.0,
                wall_height_cm=250.0,
                roof_pitch_height_cm=220.0,
                window_count=5,
                chimney_present=True,
            ),
            asset_id=asset.asset_id,
        )
    if asset.role == "pine_tree":
        return build_alpine_pine(
            AlpinePineParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "crystal_cluster":
        return build_violet_crystal_cluster(seed=asset.seed, asset_id=asset.asset_id)
    if asset.role == "rope_bridge":
        return build_rope_bridge(
            RopeBridgeParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "stone_path_segment":
        return build_stone_path_segment(
            StonePathParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "lantern":
        return build_lantern_post(
            LanternPostParameters(seed=asset.seed),
            asset_id=asset.asset_id,
        )
    if asset.role == "waterfall_ribbon":
        return _build_waterfall_ribbon(asset)
    if asset.role == "fence_segment":
        return _build_fence_segment(asset)
    raise ValueError(f"unsupported_world_asset_role: {asset.role}")


def _write_world_member_sidecar(
    pkg_dir: Path,
    composition: WorldComposition,
    world_asset: WorldAsset,
) -> None:
    payload = {
        "version": WORLD_MEMBER_PACKAGE_VERSION,
        "world_id": composition.world_id,
        "world_asset_id": world_asset.world_asset_id,
        "role": world_asset.role,
        "placement": asdict(world_asset.placement),
        "style_pack_id": world_asset.style_pack_id,
        "seed": world_asset.seed,
    }
    (pkg_dir / "world-member.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = pkg_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sidecars = dict(manifest.get("sidecar_files") or {})
        sidecars["world_member"] = "world-member.json"
        manifest["sidecar_files"] = sidecars
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=False),
            encoding="utf-8",
        )


def _replace_asset_root_paths(value: Any, assets_dir: Path, pkg_dir: Path) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _replace_asset_root_paths(raw, assets_dir, pkg_dir)
            for key, raw in value.items()
        }
    if isinstance(value, list):
        return [_replace_asset_root_paths(item, assets_dir, pkg_dir) for item in value]
    if isinstance(value, str):
        candidate = Path(value)
        try:
            rel_to_assets = candidate.resolve().relative_to(assets_dir.resolve())
        except ValueError:
            return value
        rel_to_pkg = Path("..") / rel_to_assets
        return str(rel_to_pkg).replace("\\", "/")
    return value


def _normalize_world_member_sidecars(pkg_dir: Path, assets_dir: Path) -> None:
    manifest_path = pkg_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_utc"] = 0.0
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=False),
            encoding="utf-8",
        )
    for filename in ("runtime.json", "evidence.json"):
        path = pkg_dir / filename
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload = _replace_asset_root_paths(payload, assets_dir.resolve(), pkg_dir.resolve())
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=False),
            encoding="utf-8",
        )


def _attach_visible_mesh_sidecars(
    pkg_dir: Path,
    world_asset: WorldAsset,
    foundry_asset: FoundryAsset,
) -> dict[str, Any]:
    mesh_evidence = write_world_member_mesh_glb(
        world_asset=world_asset,
        foundry_asset=foundry_asset,
        pkg_dir=pkg_dir,
    )
    manifest_path = pkg_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sidecars = dict(manifest.get("sidecar_files") or {})
    sidecars["mesh_glb"] = "mesh.glb"
    manifest["sidecar_files"] = sidecars
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False),
        encoding="utf-8",
    )

    runtime_path = pkg_dir / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["render_mesh"] = {
        "artifact_path": "mesh.glb",
        "status": "real",
        "status_reason": "",
    }
    runtime_path.write_text(
        json.dumps(runtime, indent=2, sort_keys=False),
        encoding="utf-8",
    )

    evidence_path = pkg_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    runtime_manifest = dict(evidence.get("runtime_manifest") or {})
    runtime_manifest["render_mesh"] = runtime["render_mesh"]
    evidence["runtime_manifest"] = runtime_manifest
    evidence["visible_mesh_evidence"] = {
        **mesh_evidence,
        "rule_of_truth": (
            "mesh.glb is deterministic low-poly visible geometry emitted for this world member; "
            "it is not imported-engine evidence by itself."
        ),
    }
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return mesh_evidence


def package_world_members(
    composition: WorldComposition,
    assets_dir: str | Path,
) -> dict[str, WorldMemberPackageResult]:
    """Write .lthpkg directories for every world member."""

    output_dir = Path(assets_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, WorldMemberPackageResult] = {}
    for world_asset in composition.assets:
        foundry_asset = build_foundry_asset_for_world_member(world_asset)
        runtime_manifest = cook_generated_runtime_artifact(
            foundry_asset,
            output_dir / "_runtime_artifacts" / foundry_asset.asset_id,
        )
        certificate = compute_asset_certificate(foundry_asset, runtime_manifest)
        pkg_dir = write_lthpkg(
            foundry_asset,
            runtime_manifest,
            certificate,
            output_dir,
        )
        _write_world_member_sidecar(pkg_dir, composition, world_asset)
        _normalize_world_member_sidecars(pkg_dir, output_dir)
        mesh_evidence = _attach_visible_mesh_sidecars(pkg_dir, world_asset, foundry_asset)
        results[world_asset.world_asset_id] = WorldMemberPackageResult(
            world_asset_id=world_asset.world_asset_id,
            asset_id=foundry_asset.asset_id,
            role=world_asset.role,
            package_dir=str(pkg_dir),
            status="linked",
            render_mesh_status=str(mesh_evidence["status"]),
            collision_status=runtime_manifest.collision.proxy_status,
            nav_status=runtime_manifest.nav.nav_status,
            generator_id=foundry_asset.spec.generator_id,
        )
    return results


def package_results_to_links(
    results: Mapping[str, WorldMemberPackageResult],
    world_dir: str | Path,
) -> dict[str, dict[str, str]]:
    root = Path(world_dir)
    return {asset_id: result.to_link_dict(root) for asset_id, result in sorted(results.items())}


__all__ = [
    "WORLD_MEMBER_PACKAGE_VERSION",
    "WorldMemberPackageResult",
    "build_foundry_asset_for_world_member",
    "package_results_to_links",
    "package_world_members",
]
