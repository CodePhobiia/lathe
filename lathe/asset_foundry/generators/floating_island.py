"""Foundry generator: FloatingIslandSmall.

Per masterplan §16.9 + northstar §5.4. Walkable plateau + faceted
cliff ring + dramatic underside shards. The hardest Golden Asset
because it stitches together the FacetField + HalfSpacePolyhedron
operators with walkable nav + scatter surface metadata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..facet_field import (
    sample_facet_field_3d_radial,
)
from ..polyhedron import build_prism_mesh
from ._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)

_GENERATOR_ID = "floating_island_small"


@dataclass(frozen=True)
class FloatingIslandParameters:
    seed: int = 0
    plateau_radius_cm: float = 800.0
    plateau_sides: int = 12
    """Number of sides on the plateau prism (higher = rounder)."""
    plateau_thickness_cm: float = 90.0
    cliff_ring_height_cm: float = 220.0
    cliff_ring_facets_per_ring: int = 16
    cliff_rings: int = 4
    underside_shard_count: int = 8
    underside_shard_length_cm: float = 380.0
    grass_top_inset_cm: float = 30.0
    """Distance from plateau edge to start grass material zone."""


def build_floating_island_small(
    params: FloatingIslandParameters | None = None,
    *,
    asset_id: str = "floating_island_small_a",
) -> FoundryAsset:
    """Build a FloatingIslandSmall asset spec."""
    p = params if params is not None else FloatingIslandParameters()

    # Plateau prism — wide low cylinder.
    plateau_mesh = build_prism_mesh(
        sides=p.plateau_sides,
        base_radius_cm=p.plateau_radius_cm,
        height_cm=p.plateau_thickness_cm,
        top_radius_cm=p.plateau_radius_cm,
        base_z_cm=0.0,
        zone_prefix=f"{asset_id}.plateau",
    )

    # Faceted cliff ring around the plateau.
    cliff_field = sample_facet_field_3d_radial(
        field_id=f"{asset_id}.cliff",
        axis_origin_cm=(0.0, 0.0, -p.cliff_ring_height_cm),
        axis=(0.0, 0.0, 1.0),
        height_cm=p.cliff_ring_height_cm,
        base_radius_cm=p.plateau_radius_cm * 1.05,
        rings=p.cliff_rings,
        facets_per_ring=p.cliff_ring_facets_per_ring,
        seed=p.seed,
        zone_id_prefix=f"{asset_id}.cliff",
    )

    # Underside shards — radial cones extending downward.
    shard_records: list[dict[str, Any]] = []
    bottom_z = -(p.cliff_ring_height_cm + p.underside_shard_length_cm * 0.55)
    for i in range(p.underside_shard_count):
        theta = i * (2.0 * math.pi / max(1, p.underside_shard_count))
        radial = p.plateau_radius_cm * 0.6
        x = radial * math.cos(theta)
        y = radial * math.sin(theta)
        # Slight inward angle for dramatic shard look.
        shard_records.append(
            {
                "shard_id": f"{asset_id}.shard_{i:02d}",
                "translation_cm": [x * 0.45, y * 0.45, -p.cliff_ring_height_cm],
                "axis_target_cm": [x * 0.1, y * 0.1, bottom_z],
                "length_cm": p.underside_shard_length_cm,
                "base_radius_cm": 60.0,
                "tip_radius_cm": 4.0,
                "zone_id": f"{asset_id}.shard_{i:02d}",
            }
        )

    geometry_payload: dict[str, Any] = {
        "kind": "floating_island_small",
        "plateau": {
            "zone_id_prefix": f"{asset_id}.plateau",
            "radius_cm": p.plateau_radius_cm,
            "sides": p.plateau_sides,
            "thickness_cm": p.plateau_thickness_cm,
            "vertex_count": plateau_mesh.vertex_count(),
            "face_count": plateau_mesh.face_count(),
        },
        "cliff_facet_field": {
            "zone_id_prefix": f"{asset_id}.cliff",
            "ring_count": p.cliff_rings,
            "facets_per_ring": p.cliff_ring_facets_per_ring,
            "sample_count": cliff_field.sample_count(),
            "samples": [
                {
                    "sample_id": s.sample_id,
                    "center_cm": list(s.center_cm),
                    "normal": list(s.normal),
                    "extent_cm": s.extent_cm,
                    "zone_id": s.zone_id,
                }
                for s in cliff_field.samples
            ],
        },
        "underside_shards": shard_records,
        "grass_top_inset_cm": p.grass_top_inset_cm,
    }

    diagnostics: list[str] = []
    if p.underside_shard_count < 4:
        diagnostics.append(
            f"underside_shard_count_low: {p.underside_shard_count} < 4; underside silhouette may read flat"
        )
    if p.cliff_rings < 3:
        diagnostics.append(
            f"cliff_rings_low: {p.cliff_rings} < 3; cliff facets may not read dramatic"
        )

    material_slots = (
        MaterialSlot(
            slot_id="plateau_top",
            zone_id_prefix=f"{asset_id}.plateau.top",
            material_class="grass_emerald",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="plateau_side",
            zone_id_prefix=f"{asset_id}.plateau.side",
            material_class="cliff_purple",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="cliff",
            zone_id_prefix=f"{asset_id}.cliff",
            material_class="cliff_purple",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="shards",
            zone_id_prefix=f"{asset_id}.shard",
            material_class="cliff_lavender",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="path_anchor_n",
            role="path_endpoint",
            position_cm=(0.0, p.plateau_radius_cm - p.grass_top_inset_cm, p.plateau_thickness_cm),
        ),
        SemanticSocket(
            socket_id="path_anchor_s",
            role="path_endpoint",
            position_cm=(0.0, -(p.plateau_radius_cm - p.grass_top_inset_cm), p.plateau_thickness_cm),
        ),
        SemanticSocket(
            socket_id="bridge_anchor_e",
            role="bridge_endpoint",
            position_cm=(p.plateau_radius_cm * 0.85, 0.0, p.plateau_thickness_cm),
        ),
        SemanticSocket(
            socket_id="waterfall_source_w",
            role="waterfall_source",
            position_cm=(-(p.plateau_radius_cm * 0.85), 0.0, p.plateau_thickness_cm),
        ),
        SemanticSocket(
            socket_id="player_spawn_center",
            role="player_spawn",
            position_cm=(0.0, 0.0, p.plateau_thickness_cm),
        ),
    )

    collision = CollisionSpec(
        strategy="compound_hulls",
        walkable_zones=(f"{asset_id}.plateau.top",),
        blocking_zones=(
            f"{asset_id}.plateau.side",
            f"{asset_id}.cliff",
        ),
        hazard_zones=(
            f"{asset_id}.cliff_edge",
            f"{asset_id}.shard",
        ),
    )

    lod_policy = LodPolicy(
        lod_levels=4,
        target_triangle_counts=(22000, 7000, 2000, 600),
        preserve_silhouette=True,
        drop_at_lod_features={
            "underside_shards": 2,
            "cliff_facet_detail": 1,
        },
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "plateau_radius_cm": p.plateau_radius_cm,
            "plateau_sides": p.plateau_sides,
            "plateau_thickness_cm": p.plateau_thickness_cm,
            "cliff_ring_height_cm": p.cliff_ring_height_cm,
            "cliff_ring_facets_per_ring": p.cliff_ring_facets_per_ring,
            "cliff_rings": p.cliff_rings,
            "underside_shard_count": p.underside_shard_count,
            "underside_shard_length_cm": p.underside_shard_length_cm,
            "grass_top_inset_cm": p.grass_top_inset_cm,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="environment_piece",
        semantic_parts=(
            "plateau",
            "cliff_ring",
            "underside_shards",
        ),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=tuple(diagnostics),
    )

    bbox_cm = (
        (-p.plateau_radius_cm * 1.1, -p.plateau_radius_cm * 1.1, bottom_z),
        (p.plateau_radius_cm * 1.1, p.plateau_radius_cm * 1.1, p.plateau_thickness_cm),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=6,
        notes="Foundry F5 — FloatingIslandSmall: plateau + faceted cliff + underside shards.",
    )


__all__ = ["FloatingIslandParameters", "build_floating_island_small"]
