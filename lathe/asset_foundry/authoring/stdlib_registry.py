"""Versioned stdlib kit registry.

Per northstar §10 Lane I priority task #2. The stdlib registry holds
versioned kit entries (hardsurface, lowpoly_fantasy, ...) keyed by
``(name, major.minor.patch)``. Each entry declares its kit parts +
director vocabulary contributions + style-pack references.

Lookups support exact-version + semver-compatible matching. The
registry is deterministic and serializable.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

STDLIB_REGISTRY_VERSION = "lathe.asset_foundry.stdlib_registry_v1"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True, order=True)
class StdlibVersion:
    """Semantic version triple."""

    major: int
    minor: int
    patch: int

    def to_str(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, s: str) -> "StdlibVersion":
        m = _SEMVER_RE.match(s.strip())
        if not m:
            raise ValueError(f"invalid semver: {s!r}")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))


@dataclass(frozen=True)
class StdlibEntry:
    """One registered kit / pack entry."""

    name: str
    """Kit / pack name (e.g. ``hardsurface``, ``lowpoly_fantasy``)."""

    version: StdlibVersion
    kit_id: str
    """Unique kit identifier (e.g. ``std.kit.hardsurface.v1``)."""

    style_pack_ids: tuple[str, ...] = ()
    """Style packs this kit references."""

    director_terms: tuple[str, ...] = ()
    """Director vocabulary terms this kit contributes."""

    category_index: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """category -> tuple of part names. e.g. fasteners -> (hex_bolt_m6, flat_rivet_4mm)."""

    family_compatibility: tuple[str, ...] = ()
    """Asset families this kit serves (e.g.
    ``("industrial_crate", "service_cabinet")``)."""

    license: str = "internal"
    notes: str = ""


@dataclass
class StdlibRegistry:
    """Mutable registry. Use the module-level
    ``stdlib_registry_v1`` factory for the canonical v1 set."""

    entries: list[StdlibEntry] = field(default_factory=list)

    def register(self, entry: StdlibEntry) -> None:
        for existing in self.entries:
            if existing.name == entry.name and existing.version == entry.version:
                raise ValueError(
                    f"stdlib entry {entry.name}@{entry.version.to_str()} already registered"
                )
        self.entries.append(entry)

    def lookup_exact(self, name: str, version_str: str) -> StdlibEntry | None:
        target = StdlibVersion.parse(version_str)
        for entry in self.entries:
            if entry.name == name and entry.version == target:
                return entry
        return None

    def lookup_compatible(self, name: str, min_version_str: str) -> StdlibEntry | None:
        """Return the highest version that is ``>= min_version`` and
        shares the same major. Returns None if none match."""
        target = StdlibVersion.parse(min_version_str)
        best: StdlibEntry | None = None
        for entry in self.entries:
            if entry.name != name:
                continue
            if entry.version.major != target.major:
                continue
            if entry.version < target:
                continue
            if best is None or entry.version > best.version:
                best = entry
        return best

    def list_by_family(self, family: str) -> tuple[StdlibEntry, ...]:
        return tuple(
            e
            for e in self.entries
            if family in e.family_compatibility or "*" in e.family_compatibility
        )


def register_stdlib_kit(
    registry: StdlibRegistry,
    *,
    name: str,
    version: str,
    kit_id: str,
    category_index: Mapping[str, tuple[str, ...]],
    style_pack_ids: tuple[str, ...] = (),
    director_terms: tuple[str, ...] = (),
    family_compatibility: tuple[str, ...] = ("*",),
    license: str = "internal",
    notes: str = "",
) -> StdlibEntry:
    """Convenience factory that constructs + registers + returns an entry."""
    entry = StdlibEntry(
        name=name,
        version=StdlibVersion.parse(version),
        kit_id=kit_id,
        style_pack_ids=style_pack_ids,
        director_terms=director_terms,
        category_index=dict(category_index),
        family_compatibility=family_compatibility,
        license=license,
        notes=notes,
    )
    registry.register(entry)
    return entry


def stdlib_registry_v1() -> StdlibRegistry:
    """Build the canonical v1 stdlib registry."""
    reg = StdlibRegistry()
    register_stdlib_kit(
        reg,
        name="hardsurface",
        version="1.0.0",
        kit_id="std.kit.hardsurface.v1",
        category_index={
            "fasteners": ("hex_bolt_m6", "flat_rivet_4mm"),
            "corner_guards": ("welded_steel_l_bracket", "stamped_corner_cap"),
            "handles": ("recessed_inset_grip",),
            "rails": ("foot_rail_bar", "trim_band_strip"),
            "warning_labels": ("caution_yellow_strip", "biohazard_orange_decal"),
        },
        director_terms=(
            "industrial_paneling",
            "factory_hardsurface",
            "warning_decal_grid",
        ),
        family_compatibility=(
            "industrial_crate",
            "service_cabinet",
            "control_pedestal",
            "mechanical_door",
            "supply_container",
        ),
        notes="MVP hard-surface kit shipped with Phase 12.",
    )
    register_stdlib_kit(
        reg,
        name="lowpoly_fantasy",
        version="1.0.0",
        kit_id="std.kit.lowpoly_fantasy.v1",
        style_pack_ids=("lowpoly_fantasy_sunset_crystal_v1",),
        category_index={
            "crystals": ("violet_prism_small", "violet_prism_hero"),
            "trees": ("alpine_pine_small", "alpine_pine_tall"),
            "lanterns": ("lantern_post_warm",),
            "bridges": ("rope_bridge_short", "rope_bridge_long"),
            "path_stones": ("stone_slab_warm",),
            "cottages": ("cottage_small_cozy", "cottage_elder"),
            "islands": ("floating_island_small",),
        },
        director_terms=(
            "stylized_low_poly_fantasy",
            "sunset_crystal_palette",
            "faceted_cliffside",
        ),
        family_compatibility=(
            "violet_crystal_cluster",
            "alpine_pine",
            "lantern_post",
            "rope_bridge",
            "stone_path_segment",
            "cozy_cottage",
            "floating_island_small",
        ),
        notes="Foundry F5 lowpoly_fantasy kit pairs with the SunsetCrystal style pack.",
    )
    return reg


__all__ = [
    "STDLIB_REGISTRY_VERSION",
    "StdlibEntry",
    "StdlibRegistry",
    "StdlibVersion",
    "register_stdlib_kit",
    "stdlib_registry_v1",
]
