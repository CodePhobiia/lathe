"""SpeedTree-class procedural vegetation library (roadmap §7.1).

Public API:

- ``compile_vegetation_species(decl)``: lower a ``vegetation_species``
  declaration into a deterministic ``VegetationSpecies`` record with a
  parametric branch grammar, leaf placement policy, season/wind hooks,
  and an auto-LOD ladder.
- ``compile_vegetation_kit(decl, species_map)``: lower a
  ``vegetation_kit`` declaration into a forest/garden bundle by
  resolving the kit's species references against the program's species
  catalogue.
- ``compile_wind_program(decl)``: lower a ``wind_program`` declaration
  into a ``WindProgram`` record with vertex-band hints and per-engine
  sway parameter recommendations.
- ``generate_lods(species, *, lod_count)``: produce an LOD ladder
  (LOD0..LOD3) for a species, including the billboard imposter.

Vegetation primitives lower to existing stable ShapeIR types:
``branch_segment`` → ``swept_profile`` (curved path, taper),
``leaf_card`` → ``extruded_profile`` (planar quad), ``trunk`` →
``revolved_profile`` (axial taper).
"""

from __future__ import annotations

from .branches import generate_branch_skeleton
from .fronds import generate_frond
from .imposter import generate_imposter
from .leaves import scatter_leaf_cards
from .lod import generate_lods
from .seasons import SEASONAL_PALETTES, apply_season
from .species import (
    SPECIES_PRESETS,
    VegetationSpecies,
    compile_vegetation_kit,
    compile_vegetation_species,
)
from .wind import WindProgram, compile_wind_program

__all__ = [
    "SEASONAL_PALETTES",
    "SPECIES_PRESETS",
    "VegetationSpecies",
    "WindProgram",
    "apply_season",
    "compile_vegetation_kit",
    "compile_vegetation_species",
    "compile_wind_program",
    "generate_branch_skeleton",
    "generate_frond",
    "generate_imposter",
    "generate_lods",
    "scatter_leaf_cards",
]
