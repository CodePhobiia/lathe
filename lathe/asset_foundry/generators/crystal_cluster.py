"""Foundry generator: VioletCrystalCluster.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §16.3
+ North Star/lathe-floating-fantasy-world-northstar.md §10.3.2.

Reuses ``lathe.asset_foundry.prismatic.build_crystal_cluster``. The
generator wraps the prismatic output with material slots, sockets,
collision spec, and LOD policy.
"""

from __future__ import annotations

from typing import Any

from ..prismatic import CrystalParameters, build_crystal_cluster
from ._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)

_GENERATOR_ID = "violet_crystal_cluster"


def build_violet_crystal_cluster(
    *,
    seed: int = 0,
    crystal_count: int = 5,
    primary_height_cm: float = 32.0,
    primary_radius_cm: float = 6.0,
    cluster_radius_cm: float = 10.0,
    asset_id: str = "violet_crystal_cluster_a",
) -> FoundryAsset:
    """Build a VioletCrystalCluster asset spec."""
    params = CrystalParameters(
        seed=seed,
        crystal_count=crystal_count,
        primary_height_cm=primary_height_cm,
        primary_radius_cm=primary_radius_cm,
        cluster_radius_cm=cluster_radius_cm,
    )
    cluster = build_crystal_cluster(params, cluster_id=asset_id)

    # Geometry payload — typed reference back to the cluster.
    geometry_payload: dict[str, Any] = {
        "kind": "prismatic_cluster",
        "cluster_id": cluster.cluster_id,
        "crystal_count": cluster.crystal_count(),
        "crystals": [
            {
                "crystal_id": c.crystal_id,
                "role": c.role,
                "translation_cm": list(c.translation_cm),
                "rotation_deg": c.rotation_deg,
                "tilt_deg": c.tilt_deg,
                "height_cm": c.height_cm,
                "radius_cm": c.radius_cm,
                "vertex_count": c.mesh.vertex_count(),
                "face_count": c.mesh.face_count(),
                "zone_id_prefix": c.crystal_id,
            }
            for c in cluster.crystals
        ],
    }

    material_slots = (
        MaterialSlot(
            slot_id="crystal_primary",
            zone_id_prefix=f"{asset_id}.primary",
            material_class="crystal_violet_emissive",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="crystal_secondary",
            zone_id_prefix=f"{asset_id}.secondary",
            material_class="crystal_magenta",
            uv_policy="triplanar",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="glow_core",
            role="crystal_glow_source",
            position_cm=(0.0, 0.0, primary_height_cm * 0.6),
        ),
        SemanticSocket(
            socket_id="base_mount",
            role="ground_anchor",
            position_cm=(0.0, 0.0, 0.0),
        ),
    )

    collision = CollisionSpec(
        strategy="compound_hulls",
        walkable_zones=(),
        blocking_zones=tuple(f"{asset_id}.primary",) + tuple(
            f"{asset_id}.secondary_{i:02d}" for i in range(max(0, crystal_count - 1))
        ),
        hazard_zones=(),
    )

    lod_policy = LodPolicy(
        lod_levels=4,
        target_triangle_counts=(4000, 1200, 400, 100),
        preserve_silhouette=True,
        drop_at_lod_features={"secondary_shards": 2},
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": seed,
            "crystal_count": crystal_count,
            "primary_height_cm": primary_height_cm,
            "primary_radius_cm": primary_radius_cm,
            "cluster_radius_cm": cluster_radius_cm,
        },
        seed=seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="environment_piece",
        semantic_parts=("primary_crystal",)
        + tuple(f"secondary_crystal_{i:02d}" for i in range(max(0, crystal_count - 1))),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=cluster.diagnostics,
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=cluster.bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F4+F5 — VioletCrystalCluster MVP.",
    )


__all__ = ["build_violet_crystal_cluster"]
