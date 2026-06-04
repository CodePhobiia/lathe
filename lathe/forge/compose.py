"""Deterministic Forge composition for the Skyborne Village capstone."""

from __future__ import annotations

import random
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..determinism.seeds import derive_subseed
from .path_graph import (
    build_cliff_hazard_zones,
    build_skyborne_path_graph,
    build_skyborne_quest_anchors,
)
from .world_graph import (
    StyleContext,
    WorldAsset,
    WorldAssetPlacement,
    WorldComposition,
)

SKYBORNE_STYLE_PACK_ID = "lowpoly_fantasy_sunset_crystal_v1"
SKYBORNE_KIT_ID = "lowpoly_fantasy_skyborne_village_v1"

DEFAULT_SKYBORNE_COUNTS: dict[str, int] = {
    "floating_island": 1,
    "cottage": 3,
    "elder_house": 1,
    "pine_tree": 12,
    "crystal_cluster": 3,
    "rope_bridge": 1,
    "waterfall_ribbon": 1,
    "stone_path_segment": 5,
    "lantern": 6,
    "fence_segment": 4,
}

ROLE_META: dict[str, dict[str, str]] = {
    "floating_island": {
        "family": "terrain",
        "generator_id": "floating_island_small",
        "asset_id": "floating_island_small",
    },
    "cottage": {
        "family": "architecture",
        "generator_id": "cozy_cottage",
        "asset_id": "cozy_cottage",
    },
    "elder_house": {
        "family": "architecture",
        "generator_id": "cozy_cottage.hero_inn_variant",
        "asset_id": "hero_elder_house",
    },
    "pine_tree": {
        "family": "vegetation",
        "generator_id": "alpine_pine",
        "asset_id": "alpine_pine",
    },
    "crystal_cluster": {
        "family": "prop",
        "generator_id": "violet_crystal_cluster",
        "asset_id": "violet_crystal_cluster",
    },
    "rope_bridge": {
        "family": "traversal",
        "generator_id": "rope_bridge",
        "asset_id": "rope_bridge",
    },
    "waterfall_ribbon": {
        "family": "environment_effect",
        "generator_id": "waterfall_ribbon",
        "asset_id": "waterfall_ribbon",
    },
    "stone_path_segment": {
        "family": "traversal",
        "generator_id": "stone_path_segment",
        "asset_id": "stone_path_segment",
    },
    "lantern": {
        "family": "prop_light",
        "generator_id": "lantern_post",
        "asset_id": "lantern_post",
    },
    "fence_segment": {
        "family": "traversal",
        "generator_id": "fence_segment",
        "asset_id": "fence_segment",
    },
}


@dataclass(frozen=True)
class SkyborneIntent:
    """Prompt-derived intent for a small floating fantasy village."""

    prompt: str
    asset_counts: Mapping[str, int] = field(default_factory=lambda: dict(DEFAULT_SKYBORNE_COUNTS))
    style_pack_id: str = SKYBORNE_STYLE_PACK_ID
    kit_id: str = SKYBORNE_KIT_ID
    director_terms: tuple[str, ...] = (
        "stylized_low_poly_fantasy",
        "sunset_crystal_palette",
        "faceted_cliffside",
    )
    world_kind: str = "floating_fantasy_village"
    requested_inventory_label: str = "skyborne_village_capstone_v1"

    def normalized_counts(self) -> dict[str, int]:
        counts = dict(DEFAULT_SKYBORNE_COUNTS)
        counts.update({str(k): max(0, int(v)) for k, v in self.asset_counts.items()})
        return counts


def default_skyborne_intent(prompt: str = "") -> SkyborneIntent:
    return SkyborneIntent(
        prompt=prompt
        or "small floating fantasy village at sunset with waterfall, rope bridge, three cottages, hero inn"
    )


def _jittered(
    rng: random.Random,
    x: float,
    z: float,
    *,
    jitter_cm: float = 30.0,
) -> tuple[float, float, float]:
    return (
        round(x + rng.uniform(-jitter_cm, jitter_cm), 3),
        0.0,
        round(z + rng.uniform(-jitter_cm, jitter_cm), 3),
    )


def _role_position(role: str, index: int, count: int, rng: random.Random) -> tuple[float, float, float]:
    if role == "floating_island":
        return (0.0, -80.0, 0.0)
    if role == "cottage":
        pads = ((-380.0, -170.0), (360.0, -160.0), (-120.0, 330.0))
        x, z = pads[index % len(pads)]
        return _jittered(rng, x, z, jitter_cm=35.0)
    if role == "elder_house":
        return _jittered(rng, 120.0, -520.0, jitter_cm=20.0)
    if role == "rope_bridge":
        return _jittered(rng, 720.0, 40.0, jitter_cm=15.0)
    if role == "waterfall_ribbon":
        return _jittered(rng, -520.0, 560.0, jitter_cm=20.0)
    if role == "stone_path_segment":
        path = ((0.0, 0.0), (-190.0, -90.0), (175.0, -90.0), (30.0, -265.0), (-85.0, 180.0))
        x, z = path[index % len(path)]
        return _jittered(rng, x, z, jitter_cm=18.0)
    if role == "lantern":
        lanterns = ((-120.0, -70.0), (130.0, -70.0), (-250.0, -130.0), (250.0, -125.0), (35.0, -340.0), (-120.0, 235.0))
        x, z = lanterns[index % len(lanterns)]
        return _jittered(rng, x, z, jitter_cm=12.0)
    if role == "fence_segment":
        fences = ((-610.0, -190.0), (560.0, -210.0), (-500.0, 480.0), (410.0, 510.0))
        x, z = fences[index % len(fences)]
        return _jittered(rng, x, z, jitter_cm=16.0)
    if role == "crystal_cluster":
        crystals = ((-665.0, 300.0), (-560.0, 430.0), (-725.0, 515.0))
        x, z = crystals[index % len(crystals)]
        return _jittered(rng, x, z, jitter_cm=25.0)
    if role == "pine_tree":
        angle = (index / max(1, count)) * 6.283185307179586
        radius = 590.0 + rng.uniform(-45.0, 40.0)
        return (
            round(radius * math.cos(angle), 3),
            0.0,
            round(radius * math.sin(angle), 3),
        )
    return _jittered(rng, 0.0, 0.0, jitter_cm=50.0)


def _rotation_for(role: str, index: int, rng: random.Random) -> float:
    if role in {"stone_path_segment", "fence_segment", "rope_bridge"}:
        return round((index * 23.0 + rng.uniform(-8.0, 8.0)) % 360.0, 3)
    if role in {"cottage", "elder_house"}:
        return round(rng.choice((0.0, 45.0, 90.0, 180.0, 270.0)) + rng.uniform(-5.0, 5.0), 3)
    return round(rng.uniform(0.0, 360.0), 3)


def _scale_for(role: str, index: int) -> float:
    if role == "floating_island":
        return 1.0
    if role == "elder_house":
        return 1.25
    if role == "pine_tree":
        return 0.85 + (index % 4) * 0.08
    return 1.0


def _inventory_diagnostics(counts: Mapping[str, int]) -> tuple[Mapping[str, Any], ...]:
    total = sum(counts.values())
    diagnostics: list[Mapping[str, Any]] = []
    if total != 22:
        diagnostics.append(
            {
                "code": "SV0001",
                "severity": "info",
                "claim_level": "real",
                "message": (
                    "Capstone prose says '22 assets total', but the enumerated "
                    "role counts add up to a different instance count."
                ),
                "expected_claim_text_count": 22,
                "actual_role_instance_count": total,
                "resolution": "world_manifest_records_actual_role_instance_count",
            }
        )
    planned_generators = [
        role for role, meta in ROLE_META.items() if str(meta["generator_id"]).endswith(".planned")
    ]
    for role in planned_generators:
        if counts.get(role, 0):
            diagnostics.append(
                {
                    "code": "SV0002",
                    "severity": "warning",
                    "role": role,
                    "claim_level": "planned",
                    "message": "Role has a planned generator id until a real Foundry generator lands.",
                }
            )
    return tuple(diagnostics)


def compose_world(intent: SkyborneIntent | None = None, *, seed: int = 0) -> WorldComposition:
    """Compose a Skyborne Village world graph without generating meshes."""

    resolved_intent = intent or default_skyborne_intent()
    counts = resolved_intent.normalized_counts()
    rng = random.Random(seed)
    style = StyleContext(
        style_pack_id=resolved_intent.style_pack_id,
        kit_id=resolved_intent.kit_id,
        director_terms=tuple(resolved_intent.director_terms),
        material_palette_id=resolved_intent.style_pack_id,
    )
    assets: list[WorldAsset] = []
    for role in sorted(counts):
        count = counts[role]
        meta = ROLE_META.get(
            role,
            {"family": "unknown", "generator_id": f"{role}.planned", "asset_id": role},
        )
        for index in range(count):
            world_asset_id = f"skyborne_{role}_{index + 1:02d}"
            asset_seed = derive_subseed(seed, f"skyborne:{role}:{index}")
            placement = WorldAssetPlacement(
                position_cm=_role_position(role, index, count, rng),
                rotation_y_deg=_rotation_for(role, index, rng),
                scale=_scale_for(role, index),
                zone_id=f"{role}_zone",
                anchor_id=f"{world_asset_id}_anchor",
            )
            package_status = "planned"
            evidence_status = {
                "geometry": "planned",
                "package": "planned",
                "render": "not_verified",
                "engine_import": "not_verified",
            }
            assets.append(
                WorldAsset(
                    world_asset_id=world_asset_id,
                    role=role,
                    family=meta["family"],
                    generator_id=meta["generator_id"],
                    asset_id=f"{meta['asset_id']}_{index + 1:02d}",
                    style_pack_id=resolved_intent.style_pack_id,
                    seed=asset_seed,
                    placement=placement,
                    package_status=package_status,
                    evidence_status=evidence_status,
                    tags=("collectible_crystal",) if role == "crystal_cluster" else (),
                )
            )

    asset_tuple = tuple(assets)
    path_nodes, path_edges = build_skyborne_path_graph(asset_tuple)
    hazards = build_cliff_hazard_zones()
    quest_anchors = build_skyborne_quest_anchors(asset_tuple)
    return WorldComposition(
        world_id="skyborne_village",
        prompt=resolved_intent.prompt,
        seed=seed,
        style=style,
        assets=asset_tuple,
        path_nodes=path_nodes,
        path_edges=path_edges,
        hazard_zones=hazards,
        quest_anchors=quest_anchors,
        player_spawn_node_id="village_square",
        diagnostics=_inventory_diagnostics(counts),
    )


__all__ = [
    "DEFAULT_SKYBORNE_COUNTS",
    "SKYBORNE_KIT_ID",
    "SKYBORNE_STYLE_PACK_ID",
    "SkyborneIntent",
    "compose_world",
    "default_skyborne_intent",
]
