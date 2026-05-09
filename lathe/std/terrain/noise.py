"""Deterministic procedural noise generators for terrain initialisation.

Pure NumPy / pure-Python implementations so erosion runs do not depend
on noise toolkits being present. All noise calls take an explicit
``seed`` so two runs with the same seed produce byte-identical output.

Three flavours are provided:

- ``fbm`` — fractional Brownian motion / sum-of-octave Perlin-style
  value noise, the workhorse for rolling hills.
- ``ridged_multi`` — ridged-multifractal noise, the ``1 - |perlin|`` /
  weight-stack trick that produces sharp ridges suitable for mountain
  canyons.
- ``worley`` — Worley/cellular noise (F1) for desert pebble-fields and
  cracked-clay-style detail.

These return raw arrays; the caller is responsible for biasing,
normalising, or compositing them onto a Heightfield.
"""

from __future__ import annotations

import numpy as np

from .heightfield import Heightfield


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _value_lattice(seed: int, gx: int, gy: int) -> np.ndarray:
    rng = np.random.default_rng(np.uint64(seed) & np.uint64(0xFFFFFFFF))
    return rng.random((gy, gx), dtype=np.float64) * 2.0 - 1.0


def _value_noise_2d(
    nx: int,
    ny: int,
    *,
    frequency: float,
    seed: int,
) -> np.ndarray:
    """Single-octave value-noise, smoothstep-interpolated."""
    gx = max(int(np.ceil(frequency)) + 1, 2)
    gy = max(int(np.ceil(frequency)) + 1, 2)
    lattice = _value_lattice(seed, gx, gy)
    xs = np.linspace(0.0, frequency, nx, dtype=np.float64)
    ys = np.linspace(0.0, frequency, ny, dtype=np.float64)
    xv, yv = np.meshgrid(xs, ys)
    x0 = np.floor(xv).astype(np.int64) % (gx - 1)
    y0 = np.floor(yv).astype(np.int64) % (gy - 1)
    x1 = (x0 + 1) % gx
    y1 = (y0 + 1) % gy
    tx = _fade(xv - np.floor(xv))
    ty = _fade(yv - np.floor(yv))
    v00 = lattice[y0, x0]
    v10 = lattice[y0, x1]
    v01 = lattice[y1, x0]
    v11 = lattice[y1, x1]
    a = v00 * (1.0 - tx) + v10 * tx
    b = v01 * (1.0 - tx) + v11 * tx
    return a * (1.0 - ty) + b * ty


def fbm(
    heightfield: Heightfield,
    *,
    octaves: int = 6,
    base_frequency: float = 2.0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
    amplitude: float = 1.0,
    seed: int = 0,
    add: bool = True,
) -> Heightfield:
    """Apply fractional-Brownian-motion (sum of value-noise octaves).

    Returns the *same* heightfield instance (mutated in place when
    ``add=True``, else replaced) so callers can fluently chain.
    """
    nx, ny = heightfield.resolution
    accum = np.zeros((ny, nx), dtype=np.float64)
    freq = float(base_frequency)
    amp = float(amplitude)
    for octave in range(int(octaves)):
        layer = _value_noise_2d(nx, ny, frequency=freq, seed=seed + octave * 1009)
        accum = accum + layer * amp
        freq = freq * float(lacunarity)
        amp = amp * float(gain)
    if add:
        heightfield.heights = heightfield.heights + accum
    else:
        heightfield.heights = accum
    return heightfield


def ridged_multi(
    heightfield: Heightfield,
    *,
    octaves: int = 5,
    base_frequency: float = 2.0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
    offset: float = 1.0,
    amplitude: float = 1.0,
    seed: int = 0,
    add: bool = True,
) -> Heightfield:
    """Ridged-multifractal noise (sharp ridges from absolute value)."""
    nx, ny = heightfield.resolution
    accum = np.zeros((ny, nx), dtype=np.float64)
    freq = float(base_frequency)
    amp = float(amplitude)
    weight = np.ones((ny, nx), dtype=np.float64)
    for octave in range(int(octaves)):
        layer = _value_noise_2d(nx, ny, frequency=freq, seed=seed + octave * 2179)
        signal = offset - np.abs(layer)
        signal = signal * signal
        signal = signal * np.clip(weight, 0.0, 1.0)
        weight = signal * 2.0
        accum = accum + signal * amp
        freq = freq * float(lacunarity)
        amp = amp * float(gain)
    if add:
        heightfield.heights = heightfield.heights + accum
    else:
        heightfield.heights = accum
    return heightfield


def worley(
    heightfield: Heightfield,
    *,
    cell_count: int = 12,
    amplitude: float = 1.0,
    seed: int = 0,
    add: bool = True,
) -> Heightfield:
    """Worley / cellular noise — F1 distance to nearest seed point."""
    nx, ny = heightfield.resolution
    rng = np.random.default_rng(np.uint64(seed) & np.uint64(0xFFFFFFFF))
    points = rng.random((int(cell_count) * int(cell_count), 2), dtype=np.float64)
    xs = np.linspace(0.0, 1.0, nx, dtype=np.float64)
    ys = np.linspace(0.0, 1.0, ny, dtype=np.float64)
    xv, yv = np.meshgrid(xs, ys)
    grid = np.stack([xv.ravel(), yv.ravel()], axis=1)
    # F1 distance — vectorised via broadcasting (cell_count^2 is small).
    diffs = grid[:, None, :] - points[None, :, :]
    distances = np.sqrt(np.einsum("ijk,ijk->ij", diffs, diffs))
    f1 = np.min(distances, axis=1).reshape(ny, nx)
    f1 = (f1 / np.max(f1) if np.max(f1) > 0.0 else f1) * amplitude
    if add:
        heightfield.heights = heightfield.heights + f1
    else:
        heightfield.heights = f1
    return heightfield


def sinusoidal_terrace(
    heightfield: Heightfield,
    *,
    step_height: float = 1.0,
    period_cells: int = 16,
    axis: str = "x",
    add: bool = True,
) -> Heightfield:
    """Deterministic stair-step pattern for terraced-terrain examples.

    Sinusoidal source quantised to discrete steps. ``axis="x"`` produces
    east-facing terraces; ``axis="y"`` north-facing. Useful as the
    *initial* surface that thermal erosion then smooths.
    """
    nx, ny = heightfield.resolution
    if axis not in {"x", "y"}:
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")
    indices = np.arange(nx if axis == "x" else ny, dtype=np.float64)
    wave = np.sin(indices / max(1.0, float(period_cells)) * 2.0 * np.pi)
    quantised = np.round(wave * 2.0) * 0.5  # 5 discrete levels
    quantised = quantised * float(step_height)
    pattern = np.broadcast_to(
        quantised if axis == "x" else quantised[:, None],
        (ny, nx) if axis == "x" else (ny, nx),
    ).copy()
    if add:
        heightfield.heights = heightfield.heights + pattern
    else:
        heightfield.heights = pattern
    return heightfield
