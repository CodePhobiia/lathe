"""Terrain authoring stdlib (§7.2).

Public API mirrors the four-stage authoring pipeline described in
``procedural_3d_systems §A.4 / §D.4`` (World Machine / Gaea / World
Creator). All entry points are pure-Python + NumPy, deterministic at
fixed seed, and produce a ``Heightfield`` plus the canonical mask
outputs (``slope_mask``, ``flow_mask``, ``deposition_mask``,
``talus_mask``, per-biome zone masks) consumed by the §6.2 Smart Mask
library.

Typical use::

    hf = Heightfield.zeros((256, 256), bounds_xy=(-50, -50, 50, 50),
                           vertical_scale=8.0)
    fbm(hf, octaves=6, seed=1234)
    simulate_hydraulic_erosion(hf, iterations=30, seed=1234)
    simulate_thermal_erosion(hf, iterations=5)
    layer_biomes(hf)
    primitive = hf.to_shape_primitive(part="terrain")

The ``compile_terrain()`` convenience wraps the same pipeline with the
canonical canyon parameters used by the §7.2 worked example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .biome import DEFAULT_BIOMES, BiomeRule, layer_biomes
from .heightfield import Heightfield
from .hydraulic import HydraulicParams, simulate_hydraulic_erosion
from .noise import fbm, ridged_multi, sinusoidal_terrace, worley
from .thermal import simulate_thermal_erosion, weathering_pass

__all__ = [
    "DEFAULT_BIOMES",
    "BiomeRule",
    "Heightfield",
    "HydraulicParams",
    "TerrainProgram",
    "compile_terrain",
    "eroded_canyon",
    "fbm",
    "layer_biomes",
    "ridged_multi",
    "simulate_hydraulic_erosion",
    "simulate_thermal_erosion",
    "sinusoidal_terrace",
    "terraced_terrain",
    "weathering_pass",
    "worley",
]


@dataclass(frozen=True)
class TerrainProgram:
    """Declarative bundle for ``compile_terrain()``.

    Mirrors the ``terrain_program`` grammar block: declares an initial
    surface, an erosion stack, and an optional biome table. Two flavours
    ship in-tree — ``eroded_canyon`` (fractal noise + hydraulic +
    thermal) and ``terraced_terrain`` (sinusoidal + thermal-only).
    """

    name: str
    resolution: tuple[int, int]
    bounds_xy: tuple[float, float, float, float]
    vertical_scale: float = 1.0
    initial: Literal["fbm", "ridged_multi", "worley", "sinusoidal_terrace"] = "fbm"
    initial_amplitude: float = 1.0
    initial_octaves: int = 6
    initial_base_frequency: float = 2.0
    hydraulic_iterations: int = 30
    hydraulic_params: HydraulicParams | None = None
    thermal_iterations: int = 5
    thermal_angle_of_repose_rad: float = 0.6
    weathering_passes: int = 1
    seed: int = 0
    apply_biomes: bool = True


def compile_terrain(program: TerrainProgram) -> Heightfield:
    """Run a TerrainProgram end-to-end and return the eroded heightfield."""
    hf = Heightfield.zeros(
        program.resolution,
        bounds_xy=program.bounds_xy,
        vertical_scale=program.vertical_scale,
    )
    if program.initial == "fbm":
        fbm(
            hf,
            octaves=program.initial_octaves,
            base_frequency=program.initial_base_frequency,
            amplitude=program.initial_amplitude,
            seed=program.seed,
            add=False,
        )
    elif program.initial == "ridged_multi":
        ridged_multi(
            hf,
            octaves=program.initial_octaves,
            base_frequency=program.initial_base_frequency,
            amplitude=program.initial_amplitude,
            seed=program.seed,
            add=False,
        )
    elif program.initial == "worley":
        worley(hf, amplitude=program.initial_amplitude, seed=program.seed, add=False)
    elif program.initial == "sinusoidal_terrace":
        sinusoidal_terrace(hf, step_height=program.initial_amplitude, add=False)
    else:
        raise ValueError(f"unknown initial mode: {program.initial!r}")

    if program.hydraulic_iterations > 0:
        simulate_hydraulic_erosion(
            hf,
            iterations=program.hydraulic_iterations,
            params=program.hydraulic_params,
            seed=program.seed,
        )
    if program.thermal_iterations > 0:
        simulate_thermal_erosion(
            hf,
            iterations=program.thermal_iterations,
            angle_of_repose_rad=program.thermal_angle_of_repose_rad,
        )
    if program.weathering_passes > 0:
        weathering_pass(hf, iterations=program.weathering_passes)
    if program.apply_biomes:
        layer_biomes(hf, flow_mask=hf.get_mask("flow_mask"))
    return hf


def eroded_canyon(
    *,
    resolution: tuple[int, int] = (192, 192),
    bounds_xy: tuple[float, float, float, float] = (-48.0, -48.0, 48.0, 48.0),
    vertical_scale: float = 12.0,
    seed: int = 1337,
) -> Heightfield:
    """Worked example: fractal noise + 30 iter hydraulic + 5 iter thermal.

    Produces a recognisable river-cut canyon: ridges on the high slopes,
    a central drainage channel where the hydraulic flow accumulates, and
    talus-eroded shoulders along the steepest cliffs.
    """
    program = TerrainProgram(
        name="eroded_canyon",
        resolution=resolution,
        bounds_xy=bounds_xy,
        vertical_scale=vertical_scale,
        initial="fbm",
        initial_amplitude=1.5,
        initial_octaves=6,
        initial_base_frequency=2.5,
        hydraulic_iterations=30,
        thermal_iterations=5,
        thermal_angle_of_repose_rad=0.55,
        weathering_passes=1,
        seed=seed,
    )
    return compile_terrain(program)


def terraced_terrain(
    *,
    resolution: tuple[int, int] = (160, 160),
    bounds_xy: tuple[float, float, float, float] = (-40.0, -40.0, 40.0, 40.0),
    vertical_scale: float = 6.0,
    seed: int = 7,
) -> Heightfield:
    """Worked example: sinusoidal stair-steps + low-angle thermal smoothing.

    Produces visible step terraces — useful for paddy-field / agricultural
    plateau setups where the eye expects sharp rim edges and gentle
    in-step relief.
    """
    program = TerrainProgram(
        name="terraced_terrain",
        resolution=resolution,
        bounds_xy=bounds_xy,
        vertical_scale=vertical_scale,
        initial="sinusoidal_terrace",
        initial_amplitude=1.0,
        hydraulic_iterations=0,
        thermal_iterations=8,
        thermal_angle_of_repose_rad=0.30,
        weathering_passes=1,
        seed=seed,
    )
    return compile_terrain(program)
