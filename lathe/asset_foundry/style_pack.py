"""Foundry style packs — LowPolyFantasy.SunsetCrystal as the first.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §11
+ North Star/lathe-floating-fantasy-world-northstar.md §4.1, the
first style pack is a tight palette + facet/bevel/material policy
that LowPolyFantasy assets compile against.

StylePack is the typed runtime container; ``lowpoly_fantasy_sunset_crystal``
is the canonical instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

STYLE_PACK_VERSION = "lathe.asset_foundry.style_pack_v1"


@dataclass(frozen=True)
class LowPolyFantasyPalette:
    """The LowPolyFantasy color palette per northstar §4.1."""

    grass_emerald_hex: str = "#3fa55a"
    grass_olive_hex: str = "#92a02b"
    tree_teal_hex: str = "#226c5a"
    tree_deep_green_hex: str = "#1e4a36"
    roof_golden_hex: str = "#d99933"
    roof_ochre_hex: str = "#a36e26"
    wood_warm_brown_hex: str = "#6b4226"
    wood_reddish_brown_hex: str = "#8a3a20"
    wall_cream_hex: str = "#ead7b4"
    wall_tan_hex: str = "#c9a772"
    cliff_purple_hex: str = "#5e3a8a"
    cliff_lavender_hex: str = "#9f80c2"
    crystal_violet_hex: str = "#7b3fd2"
    crystal_magenta_hex: str = "#c43fa5"
    crystal_cyan_hex: str = "#3fd2c4"
    waterfall_cyan_hex: str = "#4ac2d2"
    waterfall_turquoise_hex: str = "#2ea395"
    window_emissive_hex: str = "#f5b03d"
    lantern_emissive_hex: str = "#ffba5a"
    sky_peach_hex: str = "#f5ad7a"
    sky_lavender_hex: str = "#9a7dbd"
    sky_violet_hex: str = "#6a4cb5"


@dataclass(frozen=True)
class StylePack:
    """A style pack — palette + facet policy + material policy + composition policy."""

    style_id: str
    palette: LowPolyFantasyPalette
    facet_policy: Mapping[str, str]
    """Per zone -> facet rule (e.g. ``"flat_normals"``, ``"smooth"``)."""

    bevel_policy: Mapping[str, str]
    """Per edge class -> bevel rule (``"none"``, ``"chunky_industrial"``,
    ``"rounded_2seg"``, etc.)."""

    material_policy: Mapping[str, str]
    """Per zone -> material class (e.g. ``"wall_plaster"``)."""

    forbidden_failure_modes: tuple[str, ...]
    """Failure modes that, if detected, fail certification."""

    composition_policy: Mapping[str, str]
    """Composition rules (e.g. ``"lantern_along_path"``,
    ``"fence_at_cliff_hazard"``)."""

    runtime_policy: Mapping[str, str]
    """Runtime conventions (``"third_person_scale"``, etc.)."""


def lowpoly_fantasy_sunset_crystal() -> StylePack:
    """The canonical LowPolyFantasy.SunsetCrystal style pack."""
    return StylePack(
        style_id="lowpoly_fantasy_sunset_crystal_v1",
        palette=LowPolyFantasyPalette(),
        facet_policy={
            "cottage.wall": "flat_normals",
            "cottage.roof": "flat_normals",
            "cottage.timber": "flat_normals",
            "crystal.body": "flat_normals",
            "crystal.shard": "flat_normals",
            "tree.trunk": "flat_normals",
            "tree.foliage": "flat_normals",
            "island.cliff": "flat_normals",
            "island.top": "flat_normals",
            "waterfall.ribbon": "smooth",
        },
        bevel_policy={
            "cottage.wall_edge": "none",
            "cottage.roof_ridge": "none",
            "cottage.timber_edge": "chunky_2mm",
            "crystal.facet_edge": "none",
            "tree.foliage_layer_edge": "none",
            "island.cliff_top_edge": "none",
            "island.path_stone_edge": "chunky_5mm",
        },
        material_policy={
            "cottage.wall": "wall_plaster",
            "cottage.roof": "roof_thatch_golden",
            "cottage.timber": "wood_warm_brown",
            "cottage.window": "window_emissive_warm",
            "cottage.door": "wood_reddish_brown",
            "crystal.primary": "crystal_violet_emissive",
            "crystal.secondary": "crystal_magenta",
            "crystal.shard": "crystal_cyan_dim",
            "tree.trunk": "wood_warm_brown",
            "tree.foliage_high": "tree_teal",
            "tree.foliage_mid": "tree_deep_green",
            "tree.foliage_low": "tree_olive",
            "island.cliff": "cliff_purple",
            "island.cliff_lower": "cliff_lavender",
            "island.top_grass": "grass_emerald",
            "island.path_stone": "stone_warm_gray",
            "waterfall.ribbon": "water_cyan",
            "lantern.housing": "metal_warm",
            "lantern.glass": "lantern_emissive_warm",
            "lantern.post": "wood_warm_brown",
        },
        forbidden_failure_modes=(
            "primitive_blockout_appearance",
            "debug_material_preview",
            "uncontrolled_random_triangulation",
            "fake_high_low_distinction",
            "stuck_on_attachments",
            "weak_silhouette",
            "uniform_random_wear",
        ),
        composition_policy={
            "lantern_placement": "along_path_every_2m_to_4m",
            "fence_placement": "at_cliff_hazard_or_property_boundary",
            "crystal_placement": "as_landmark_accents_not_decoration",
            "path_connection": "must_connect_door_to_door_or_door_to_overlook",
            "tree_placement": "frame_sightlines_no_block_traversal",
        },
        runtime_policy={
            "scale_anchor": "third_person_player",
            "path_width_min_cm": "120",
            "collision_required_for": "walkable_paths,bridges,buildings,fences,lanterns",
            "nav_extracts_from": "walkable_surface_label",
            "lod_chain_required": "true",
        },
    )


__all__ = [
    "STYLE_PACK_VERSION",
    "LowPolyFantasyPalette",
    "StylePack",
    "lowpoly_fantasy_sunset_crystal",
]
