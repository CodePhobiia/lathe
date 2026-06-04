"""KitGraph → multi-asset scene composition (Wave 24 / P8).

Takes a ``KitGraph`` + ``world_seed`` and produces a scene composition
record: N asset instances per archetype, docked via ``InterfacePort``
relations, with stratified seed sampling + repetition limits +
condition distributions.

The output is a ``SceneComposition`` record the build executor reads
to drive N parallel asset builds.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..determinism.seeds import derive_subseed
from .kit_graph import ArchetypeReference, KitGraph

CONTRACT_VERSION = "lathe.scene.compose_v1"


@dataclass(frozen=True)
class AssetInstance:
    """One asset instance in the composition."""

    instance_id: str
    archetype_role: str
    source_lth: str
    asset_name: str
    seed: int
    condition: float
    transform_world_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class SceneComposition:
    """The full composed scene — N asset instances + scene metadata."""

    kit_id: str
    world_seed: int
    instances: tuple[AssetInstance, ...]
    visual_language_id: str
    texel_density_px_per_m: float

    def instance_count(self) -> int:
        return len(self.instances)


def _condition_for_index(
    index: int, count: int, distribution: tuple[float, float]
) -> float:
    """Stratified sampling: evenly distribute condition across the range."""
    if count <= 1:
        return (distribution[0] + distribution[1]) / 2.0
    frac = index / (count - 1)
    return distribution[0] + frac * (distribution[1] - distribution[0])


def compose_scene_from_kit(
    kit: KitGraph,
    world_seed: int,
    instance_counts: Mapping[str, int] | None = None,
) -> SceneComposition:
    """Compose a scene from a KitGraph + world seed.

    ``instance_counts`` maps archetype.role → requested count. Defaults
    to ``archetype.repetition_limit`` per archetype.

    Per-instance seeds derive deterministically from
    ``derive_subseed(world_seed, "kit:{kit_id}/role:{role}/i:{idx}")``.
    """
    instances: list[AssetInstance] = []
    for archetype in kit.archetypes:
        count = (
            int(instance_counts.get(archetype.role, archetype.repetition_limit))
            if instance_counts
            else int(archetype.repetition_limit)
        )
        for i in range(count):
            seed = derive_subseed(world_seed, f"kit:{kit.kit_id}/role:{archetype.role}/i:{i}")
            condition = _condition_for_index(i, count, archetype.condition_distribution)
            instance_id = f"{archetype.role}_{i:03d}"
            instances.append(
                AssetInstance(
                    instance_id=instance_id,
                    archetype_role=archetype.role,
                    source_lth=archetype.source_lth,
                    asset_name=archetype.asset_name,
                    seed=seed,
                    condition=condition,
                    transform_world_cm=(0.0, 0.0, 0.0),  # placement is downstream
                )
            )
    return SceneComposition(
        kit_id=kit.kit_id,
        world_seed=world_seed,
        instances=tuple(instances),
        visual_language_id=kit.visual_language_id,
        texel_density_px_per_m=kit.texel_density_px_per_m,
    )


def composition_to_dict(composition: SceneComposition) -> dict[str, Any]:
    """Serialize a SceneComposition for build_report inclusion."""
    return {
        "contract_version": CONTRACT_VERSION,
        "kit_id": composition.kit_id,
        "world_seed": composition.world_seed,
        "visual_language_id": composition.visual_language_id,
        "texel_density_px_per_m": composition.texel_density_px_per_m,
        "instance_count": composition.instance_count(),
        "instances": [
            {
                "instance_id": inst.instance_id,
                "archetype_role": inst.archetype_role,
                "source_lth": inst.source_lth,
                "asset_name": inst.asset_name,
                "seed": inst.seed,
                "condition": inst.condition,
                "transform_world_cm": list(inst.transform_world_cm),
            }
            for inst in composition.instances
        ],
    }


__all__ = [
    "CONTRACT_VERSION",
    "AssetInstance",
    "SceneComposition",
    "compose_scene_from_kit",
    "composition_to_dict",
]
