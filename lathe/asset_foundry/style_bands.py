"""Style bands per northstar §12.

Seven canonical style bands declared as typed records the rest of
the Foundry (style packs, validators, generators) consults to pick
executable defaults.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

STYLE_BANDS_VERSION = "lathe.asset_foundry.style_bands_v1"


@dataclass(frozen=True)
class StyleBand:
    """One style band's executable defaults."""

    band_id: str
    """Stable token (e.g. ``band_a_chunky_low_poly``)."""

    short_name: str
    description: str
    priority: str
    """``near_term`` | ``medium_term`` | ``later``."""

    default_facet_policy: str
    """``flat_normals`` | ``weighted_smooth`` | ``mixed``."""

    default_bevel_policy: str
    """``none`` | ``chunky`` | ``rounded`` | ``shader_only``."""

    default_material_kind: str
    """``vertex_color`` | ``pbr_painted`` | ``pbr_realistic`` |
    ``cel_shader`` | ``painterly_handcrafted``."""

    default_tessellation_profile_id: str
    forbidden_failure_modes: tuple[str, ...]


BAND_A_CHUNKY_LOW_POLY = StyleBand(
    band_id="band_a_chunky_low_poly",
    short_name="Chunky Low-Poly",
    description="Intentional faceted geometry, flat normals, saturated colors.",
    priority="near_term",
    default_facet_policy="flat_normals",
    default_bevel_policy="none",
    default_material_kind="vertex_color",
    default_tessellation_profile_id="low_poly_fantasy",
    forbidden_failure_modes=(
        "random_triangulation",
        "smooth_normals_on_faceted_zones",
    ),
)

BAND_B_ANIME_CEL = StyleBand(
    band_id="band_b_anime_cel",
    short_name="Anime / Cel",
    description="Hard color edges + outline + minimal specular.",
    priority="later",
    default_facet_policy="weighted_smooth",
    default_bevel_policy="rounded",
    default_material_kind="cel_shader",
    default_tessellation_profile_id="hard_surface_game",
    forbidden_failure_modes=("photoreal_pbr_specular", "global_illumination_realistic"),
)

BAND_C_PAINTERLY = StyleBand(
    band_id="band_c_painterly",
    short_name="Painterly Single Asset",
    description="Visible brush strokes; not directed for sequences.",
    priority="later",
    default_facet_policy="weighted_smooth",
    default_bevel_policy="rounded",
    default_material_kind="painterly_handcrafted",
    default_tessellation_profile_id="hero_high_poly",
    forbidden_failure_modes=("uniform_procedural_noise", "photoreal_basecolor"),
)

BAND_D_PBR_HARD_SURFACE = StyleBand(
    band_id="band_d_pbr_hard_surface",
    short_name="Stylized PBR Hard-Surface",
    description="PBR materials + intentional silhouette + clean bevels.",
    priority="near_term",
    default_facet_policy="weighted_smooth",
    default_bevel_policy="chunky",
    default_material_kind="pbr_painted",
    default_tessellation_profile_id="hard_surface_game",
    forbidden_failure_modes=(
        "uncontrolled_random_triangulation",
        "stuck_on_attachments",
        "debug_material_preview",
    ),
)

BAND_E_HARD_SURFACE_REALISTIC = StyleBand(
    band_id="band_e_hard_surface_realistic",
    short_name="Hard-Surface Realistic",
    description="Photoreal materials + tight bevels; not photoreal humans.",
    priority="medium_term",
    default_facet_policy="weighted_smooth",
    default_bevel_policy="rounded",
    default_material_kind="pbr_realistic",
    default_tessellation_profile_id="hero_high_poly",
    forbidden_failure_modes=("cel_shading", "flat_normals_on_curved_zones"),
)

BAND_F_TOY_LEGO_CLAY = StyleBand(
    band_id="band_f_toy_lego_clay",
    short_name="Toy / Lego / Clay",
    description="WFC modular + strict construction grammar.",
    priority="medium_term",
    default_facet_policy="flat_normals",
    default_bevel_policy="none",
    default_material_kind="vertex_color",
    default_tessellation_profile_id="low_poly_fantasy",
    forbidden_failure_modes=("organic_smooth_blends", "wear_grime_masks"),
)

BAND_G_HYBRID = StyleBand(
    band_id="band_g_hybrid",
    short_name="Hybrid",
    description="Astro-like PBR + stylized mixes. Compatible with most bands.",
    priority="later",
    default_facet_policy="mixed",
    default_bevel_policy="rounded",
    default_material_kind="pbr_painted",
    default_tessellation_profile_id="hard_surface_game",
    forbidden_failure_modes=("incoherent_style_band_mix",),
)


ALL_BANDS: tuple[StyleBand, ...] = (
    BAND_A_CHUNKY_LOW_POLY,
    BAND_B_ANIME_CEL,
    BAND_C_PAINTERLY,
    BAND_D_PBR_HARD_SURFACE,
    BAND_E_HARD_SURFACE_REALISTIC,
    BAND_F_TOY_LEGO_CLAY,
    BAND_G_HYBRID,
)


def lookup_style_band(band_id: str) -> StyleBand | None:
    for b in ALL_BANDS:
        if b.band_id == band_id:
            return b
    return None


__all__ = [
    "STYLE_BANDS_VERSION",
    "StyleBand",
    "BAND_A_CHUNKY_LOW_POLY",
    "BAND_B_ANIME_CEL",
    "BAND_C_PAINTERLY",
    "BAND_D_PBR_HARD_SURFACE",
    "BAND_E_HARD_SURFACE_REALISTIC",
    "BAND_F_TOY_LEGO_CLAY",
    "BAND_G_HYBRID",
    "ALL_BANDS",
    "lookup_style_band",
]
