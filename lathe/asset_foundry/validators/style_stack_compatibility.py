"""Style-stack compatibility validator.

Per northstar §10 Lane G later-tasks + §12 Style Band Priorities.
The validator rejects incoherent style mixes (e.g. PBR realistic
materials on a flat-normal LowPolyFantasy mesh; cel-shaded materials
mixed with photoreal metals).

The compatibility matrix lives in this module + is consulted at
validation time. Style packs declare a ``style_band`` token; the
matrix says which bands compose cleanly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

STYLE_STACK_COMPATIBILITY_VERSION = (
    "lathe.asset_foundry.style_stack_compatibility_v1"
)


# Style band tokens (per northstar §12).
_STYLE_BANDS: frozenset[str] = frozenset(
    {
        "band_a_chunky_low_poly",
        "band_b_anime_cel",
        "band_c_painterly",
        "band_d_pbr_hard_surface",
        "band_e_hard_surface_realistic",
        "band_f_toy_lego_clay",
        "band_g_hybrid",
    }
)


# Per-band compatibility set. Bands not listed in a band's set are
# considered incompatible and produce a diagnostic.
_COMPATIBLE_BANDS: Mapping[str, frozenset[str]] = {
    "band_a_chunky_low_poly": frozenset({"band_a_chunky_low_poly", "band_f_toy_lego_clay", "band_g_hybrid"}),
    "band_b_anime_cel": frozenset({"band_b_anime_cel", "band_c_painterly", "band_g_hybrid"}),
    "band_c_painterly": frozenset({"band_c_painterly", "band_b_anime_cel"}),
    "band_d_pbr_hard_surface": frozenset(
        {"band_d_pbr_hard_surface", "band_e_hard_surface_realistic", "band_g_hybrid"}
    ),
    "band_e_hard_surface_realistic": frozenset(
        {"band_e_hard_surface_realistic", "band_d_pbr_hard_surface", "band_g_hybrid"}
    ),
    "band_f_toy_lego_clay": frozenset({"band_f_toy_lego_clay", "band_a_chunky_low_poly", "band_g_hybrid"}),
    "band_g_hybrid": _STYLE_BANDS,  # hybrid composes with anything by design
}


# Style pack -> declared band.
_STYLE_PACK_BAND: Mapping[str, str] = {
    "lowpoly_fantasy_sunset_crystal_v1": "band_a_chunky_low_poly",
    "hard_surface_pbr_v1": "band_d_pbr_hard_surface",
    "industrial_realistic_v1": "band_e_hard_surface_realistic",
    "toy_lego_v1": "band_f_toy_lego_clay",
    "anime_cel_v1": "band_b_anime_cel",
    "painterly_solo_v1": "band_c_painterly",
}


@dataclass(frozen=True)
class StyleStackCompatibilityReport:
    version: str
    asset_id: str
    declared_style_packs: tuple[str, ...]
    declared_bands: tuple[str, ...]
    incompatible_pairs: tuple[tuple[str, str], ...]
    compatible: bool
    diagnostics: tuple[str, ...]


def evaluate_style_stack_compatibility(
    *,
    asset_id: str,
    declared_style_packs: Iterable[str],
) -> StyleStackCompatibilityReport:
    packs = tuple(declared_style_packs)
    if not packs:
        return StyleStackCompatibilityReport(
            version=STYLE_STACK_COMPATIBILITY_VERSION,
            asset_id=asset_id,
            declared_style_packs=(),
            declared_bands=(),
            incompatible_pairs=(),
            compatible=True,
            diagnostics=("no_style_packs_declared",),
        )
    bands: list[str] = []
    diagnostics: list[str] = []
    for pack in packs:
        band = _STYLE_PACK_BAND.get(pack)
        if band is None:
            diagnostics.append(f"unknown_style_pack: {pack!r}")
            continue
        bands.append(band)
    incompatible: list[tuple[str, str]] = []
    for i, a in enumerate(bands):
        for j in range(i + 1, len(bands)):
            b = bands[j]
            if b not in _COMPATIBLE_BANDS.get(a, frozenset()):
                incompatible.append((a, b))
                diagnostics.append(
                    f"style_band_incompatible: {a!r} + {b!r} (no overlap in compatibility set)"
                )
    return StyleStackCompatibilityReport(
        version=STYLE_STACK_COMPATIBILITY_VERSION,
        asset_id=asset_id,
        declared_style_packs=packs,
        declared_bands=tuple(bands),
        incompatible_pairs=tuple(incompatible),
        compatible=not incompatible,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "STYLE_STACK_COMPATIBILITY_VERSION",
    "StyleStackCompatibilityReport",
    "evaluate_style_stack_compatibility",
]
