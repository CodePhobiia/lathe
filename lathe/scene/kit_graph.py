"""``lathe.scene.kit_graph_v1`` — world / scene composition substrate.

Per research §9: world generation should compose through a KitGraph,
not 100 standalone .lth files or one .lth with 100 raw seeds. The kit
defines a visual language + material palette + texel density target +
asset archetypes + variation strategy.

This module is the contract surface. The SceneProgram parser
extension (grammar work) is a follow-up.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.scene.kit_graph_v1"


@dataclass(frozen=True)
class ArchetypeReference:
    """One archetype in a kit: maps a role to a source .lth + variation."""

    role: str
    source_lth: str
    asset_name: str
    seed_strategy: str = "stratified"
    repetition_limit: int = 5
    condition_distribution: tuple[float, float] = (0.1, 0.8)


@dataclass(frozen=True)
class KitGraph:
    """A kit graph composing compatible archetypes for one world slice."""

    kit_id: str
    visual_language_id: str
    material_palette_id: str = ""
    texel_density_px_per_m: float = 512.0
    archetypes: tuple[ArchetypeReference, ...] = ()
    variation_seed: int = 0
    description: str = ""

    def archetype_count(self) -> int:
        return len(self.archetypes)


def kit_graph_from_dict(payload: Mapping[str, Any]) -> KitGraph:
    archetypes_raw = payload.get("archetypes") or []
    archetypes: list[ArchetypeReference] = []
    if isinstance(archetypes_raw, list):
        for entry in archetypes_raw:
            if not isinstance(entry, Mapping):
                continue
            condition = entry.get("condition_distribution") or [0.1, 0.8]
            if isinstance(condition, list) and len(condition) == 2:
                try:
                    cond_tuple = (float(condition[0]), float(condition[1]))
                except (TypeError, ValueError):
                    cond_tuple = (0.1, 0.8)
            else:
                cond_tuple = (0.1, 0.8)
            archetypes.append(
                ArchetypeReference(
                    role=str(entry.get("role") or ""),
                    source_lth=str(entry.get("source_lth") or ""),
                    asset_name=str(entry.get("asset_name") or entry.get("role") or ""),
                    seed_strategy=str(entry.get("seed_strategy") or "stratified"),
                    repetition_limit=int(entry.get("repetition_limit") or 5),
                    condition_distribution=cond_tuple,
                )
            )
    return KitGraph(
        kit_id=str(payload.get("id") or payload.get("kit_id") or ""),
        visual_language_id=str(payload.get("visual_language_id") or "utility_industrial_v1"),
        material_palette_id=str(payload.get("material_palette_id") or ""),
        texel_density_px_per_m=float(payload.get("texel_density_px_per_m") or 512.0),
        archetypes=tuple(archetypes),
        variation_seed=int(payload.get("variation_seed") or 0),
        description=str(payload.get("description") or ""),
    )


__all__ = [
    "CONTRACT_VERSION",
    "ArchetypeReference",
    "KitGraph",
    "kit_graph_from_dict",
]
