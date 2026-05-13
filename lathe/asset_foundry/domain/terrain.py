"""Terrain heightfield + erosion + material zones.

Per northstar §11 Phase 3. Deterministic heightfield generation
+ thermal/hydraulic erosion approximations + per-cell material
zone tagging.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

TERRAIN_VERSION = "lathe.asset_foundry.terrain_v1"


@dataclass(frozen=True)
class TerrainParameters:
    seed: int = 0
    width_cells: int = 64
    height_cells: int = 64
    cell_size_cm: float = 100.0
    base_elevation_cm: float = 0.0
    octaves: int = 4
    base_frequency: float = 0.02
    amplitude_cm: float = 200.0
    persistence: float = 0.5
    lacunarity: float = 2.0
    erosion_iterations: int = 0
    erosion_strength: float = 0.0


@dataclass(frozen=True)
class HeightField:
    parameters: TerrainParameters
    cells: tuple[tuple[float, ...], ...]
    """Row-major float array; row index = y."""
    min_elevation_cm: float
    max_elevation_cm: float


@dataclass(frozen=True)
class TerrainMaterialZone:
    """Per-elevation material binding."""

    zone_id: str
    min_elevation_cm: float
    max_elevation_cm: float
    material_class: str


def _value_noise(x: float, y: float, seed: int) -> float:
    """Tiny deterministic value-noise function."""
    h = (
        (1664525 * (seed if seed != 0 else 0xC0DE) + 1013904223) & 0xFFFFFFFF
    )
    xi = int(math.floor(x))
    yi = int(math.floor(y))
    xf = x - xi
    yf = y - yi
    # Smoothstep for fractional.
    sx = xf * xf * (3 - 2 * xf)
    sy = yf * yf * (3 - 2 * yf)

    def cell_value(cx: int, cy: int) -> float:
        h2 = (h + 374761393 * cx + 668265263 * cy) & 0xFFFFFFFF
        h2 = (h2 ^ (h2 >> 13)) * 1274126177 & 0xFFFFFFFF
        return (h2 / 0xFFFFFFFF) * 2.0 - 1.0

    v00 = cell_value(xi, yi)
    v10 = cell_value(xi + 1, yi)
    v01 = cell_value(xi, yi + 1)
    v11 = cell_value(xi + 1, yi + 1)
    a = v00 + sx * (v10 - v00)
    b = v01 + sx * (v11 - v01)
    return a + sy * (b - a)


def _fbm(x: float, y: float, params: TerrainParameters) -> float:
    total = 0.0
    amplitude = 1.0
    frequency = params.base_frequency
    max_amp = 0.0
    for octave in range(params.octaves):
        total += amplitude * _value_noise(x * frequency, y * frequency, params.seed + octave * 31)
        max_amp += amplitude
        amplitude *= params.persistence
        frequency *= params.lacunarity
    if max_amp <= 0:
        return 0.0
    return total / max_amp


def build_height_field(parameters: TerrainParameters) -> HeightField:
    """Build a deterministic heightfield."""
    if parameters.width_cells < 2 or parameters.height_cells < 2:
        raise ValueError("terrain width_cells and height_cells must be >= 2")
    cells: list[tuple[float, ...]] = []
    elev_min = float("inf")
    elev_max = float("-inf")
    for y in range(parameters.height_cells):
        row: list[float] = []
        for x in range(parameters.width_cells):
            v = _fbm(float(x), float(y), parameters)
            elev = parameters.base_elevation_cm + v * parameters.amplitude_cm
            row.append(elev)
            elev_min = min(elev_min, elev)
            elev_max = max(elev_max, elev)
        cells.append(tuple(row))
    return HeightField(
        parameters=parameters,
        cells=tuple(cells),
        min_elevation_cm=elev_min,
        max_elevation_cm=elev_max,
    )


def apply_erosion(field: HeightField, iterations: int = 4, strength: float = 0.1) -> HeightField:
    """Simple thermal erosion: each cell loses height to its lowest neighbor."""
    if iterations <= 0 or strength <= 0:
        return field
    cells = [list(row) for row in field.cells]
    h = field.parameters.height_cells
    w = field.parameters.width_cells
    for _ in range(iterations):
        new_cells = [row.copy() for row in cells]
        for y in range(h):
            for x in range(w):
                center = cells[y][x]
                min_neighbor = center
                for ny in (y - 1, y, y + 1):
                    for nx in (x - 1, x, x + 1):
                        if nx == x and ny == y:
                            continue
                        if 0 <= nx < w and 0 <= ny < h:
                            min_neighbor = min(min_neighbor, cells[ny][nx])
                delta = (center - min_neighbor) * strength
                new_cells[y][x] = center - delta
        cells = new_cells
    new_min = min(min(row) for row in cells)
    new_max = max(max(row) for row in cells)
    return HeightField(
        parameters=field.parameters,
        cells=tuple(tuple(row) for row in cells),
        min_elevation_cm=new_min,
        max_elevation_cm=new_max,
    )


def material_zones_from_elevation_bands(
    field: HeightField, bands: Sequence[tuple[str, float]]
) -> tuple[TerrainMaterialZone, ...]:
    """Build material zones from elevation bands.

    ``bands`` is a sequence of ``(material_class, max_elevation_fraction)``;
    fractions are relative to (max - min) elevation. The first band
    covers elevation < band[0][1] * range_elev + min_elev, etc.
    """
    if not bands:
        return ()
    range_elev = field.max_elevation_cm - field.min_elevation_cm
    zones: list[TerrainMaterialZone] = []
    prev_max = field.min_elevation_cm
    for i, (material, frac) in enumerate(bands):
        band_max = field.min_elevation_cm + frac * range_elev
        zones.append(
            TerrainMaterialZone(
                zone_id=f"terrain.band_{i:02d}",
                min_elevation_cm=prev_max,
                max_elevation_cm=band_max,
                material_class=material,
            )
        )
        prev_max = band_max
    return tuple(zones)


__all__ = [
    "TERRAIN_VERSION",
    "HeightField",
    "TerrainMaterialZone",
    "TerrainParameters",
    "apply_erosion",
    "build_height_field",
    "material_zones_from_elevation_bands",
]
