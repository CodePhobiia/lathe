"""Seed hierarchy (research §14).

A single integer ``world_seed`` deterministically derives every
sub-seed (kit, asset archetype, asset instance, surface micro,
decal, wear). The synthesizer reads from the hierarchy rather than
a global RNG so a given (world_seed, asset_id) combination always
produces the same output regardless of run order.

The derivation uses ``hashlib.sha256(parent.to_bytes + scope_id)`` —
fast enough for synthesis, deterministic across platforms, and
collision-resistant within practical scope.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SeedHierarchy:
    """The full seed hierarchy for one build."""

    world_seed: int
    kit_seed: int
    asset_archetype_seed: int
    asset_instance_seed: int
    surface_micro_seed: int
    decal_seed: int
    wear_seed: int

    def to_dict(self) -> dict[str, int]:
        return {
            "world_seed": self.world_seed,
            "kit_seed": self.kit_seed,
            "asset_archetype_seed": self.asset_archetype_seed,
            "asset_instance_seed": self.asset_instance_seed,
            "surface_micro_seed": self.surface_micro_seed,
            "decal_seed": self.decal_seed,
            "wear_seed": self.wear_seed,
        }


def derive_subseed(parent_seed: int, scope_id: str) -> int:
    """Derive a child seed from (parent_seed, scope_id).

    Uses SHA-256 of the parent bytes + scope_id encoded as UTF-8,
    truncates to a 64-bit signed range so the result fits in a typical
    Python ``int`` slot and survives JSON round-trips.
    """
    h = hashlib.sha256()
    h.update(int(parent_seed).to_bytes(8, "little", signed=False))
    h.update(scope_id.encode("utf-8"))
    digest = h.digest()
    value = int.from_bytes(digest[:8], "little", signed=False)
    # Keep within 2^63 so it round-trips cleanly through JSON / sqlite.
    return value & ((1 << 63) - 1)


def derive_hierarchy(world_seed: int, kit_id: str, asset_id: str) -> SeedHierarchy:
    """Build the full hierarchy from (world_seed, kit_id, asset_id)."""
    kit = derive_subseed(world_seed, f"kit:{kit_id}")
    archetype = derive_subseed(kit, f"archetype:{asset_id}")
    instance = derive_subseed(archetype, "instance:0")
    surface = derive_subseed(instance, "surface_micro")
    decal = derive_subseed(instance, "decal")
    wear = derive_subseed(instance, "wear")
    return SeedHierarchy(
        world_seed=world_seed,
        kit_seed=kit,
        asset_archetype_seed=archetype,
        asset_instance_seed=instance,
        surface_micro_seed=surface,
        decal_seed=decal,
        wear_seed=wear,
    )


__all__ = ["SeedHierarchy", "derive_subseed", "derive_hierarchy"]
