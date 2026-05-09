"""Volumetric noise generators (Perlin sum, Worley sphere clusters).

Pure-numpy reference implementations. Deterministic with seed.
The intent is to seed initial density/temperature fields for the
worked smoke-cloud example; the generators are not meant to compete
with libnoise / FastNoise quality.
"""

from __future__ import annotations

import numpy as np


def fractal_volume(
    shape: tuple[int, int, int],
    octaves: int = 4,
    scale: float = 1.0,
    persistence: float = 0.5,
    seed: int = 0,
) -> np.ndarray:
    """Fractional Brownian motion on a 3D grid using value-noise octaves.

    Returns ``(nx, ny, nz)`` float32 array clipped to ``[0, 1]``.
    Each octave samples a coarse random lattice and trilinearly
    interpolates onto the full grid; octaves are summed with
    decreasing amplitude per ``persistence``.
    """
    nx, ny, nz = shape
    rng_master = np.random.default_rng(seed)
    out = np.zeros(shape, dtype=np.float32)
    amplitude = 1.0
    amp_total = 0.0

    for octave in range(max(1, octaves)):
        freq = max(2, int(8 * (2 ** octave) * scale))
        gx = max(2, min(nx, freq))
        gy = max(2, min(ny, freq))
        gz = max(2, min(nz, freq))
        octave_seed = int(rng_master.integers(0, 2**31 - 1))
        rng = np.random.default_rng(octave_seed)
        coarse = rng.random((gx, gy, gz), dtype=np.float32)
        layer = _trilinear_upsample(coarse, shape)
        out += amplitude * layer
        amp_total += amplitude
        amplitude *= persistence

    if amp_total > 0:
        out /= amp_total
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def worley_clusters(
    shape: tuple[int, int, int],
    cluster_count: int = 12,
    cluster_radius: float = 0.4,
    seed: int = 0,
) -> np.ndarray:
    """Sum of Gaussian falloff spheres at random cluster centers.

    Used to produce blobby cloud or magic-wisp initial density.
    Returns float32 in ``[0, 1]``.
    """
    nx, ny, nz = shape
    rng = np.random.default_rng(seed)
    centers = rng.random((max(1, cluster_count), 3), dtype=np.float32)

    xs = (np.arange(nx, dtype=np.float32) + 0.5) / nx
    ys = (np.arange(ny, dtype=np.float32) + 0.5) / ny
    zs = (np.arange(nz, dtype=np.float32) + 0.5) / nz
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")

    inv_two_sigma_sq = 1.0 / max(2.0 * (cluster_radius ** 2), 1e-6)
    field = np.zeros(shape, dtype=np.float32)
    for cx, cy, cz in centers:
        d2 = (gx - cx) ** 2 + (gy - cy) ** 2 + (gz - cz) ** 2
        field += np.exp(-d2 * inv_two_sigma_sq).astype(np.float32)

    field_max = float(np.max(field))
    if field_max > 0.0:
        field /= field_max
    return field.astype(np.float32)


def _trilinear_upsample(coarse: np.ndarray, target_shape: tuple[int, int, int]) -> np.ndarray:
    cx, cy, cz = coarse.shape
    nx, ny, nz = target_shape
    xs = np.linspace(0.0, cx - 1.0, nx, dtype=np.float32)
    ys = np.linspace(0.0, cy - 1.0, ny, dtype=np.float32)
    zs = np.linspace(0.0, cz - 1.0, nz, dtype=np.float32)

    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    z0 = np.floor(zs).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, cx - 1)
    y1 = np.clip(y0 + 1, 0, cy - 1)
    z1 = np.clip(z0 + 1, 0, cz - 1)
    fx = (xs - x0)[:, None, None]
    fy = (ys - y0)[None, :, None]
    fz = (zs - z0)[None, None, :]

    fx = _smoothstep(fx)
    fy = _smoothstep(fy)
    fz = _smoothstep(fz)

    c000 = coarse[np.ix_(x0, y0, z0)]
    c100 = coarse[np.ix_(x1, y0, z0)]
    c010 = coarse[np.ix_(x0, y1, z0)]
    c110 = coarse[np.ix_(x1, y1, z0)]
    c001 = coarse[np.ix_(x0, y0, z1)]
    c101 = coarse[np.ix_(x1, y0, z1)]
    c011 = coarse[np.ix_(x0, y1, z1)]
    c111 = coarse[np.ix_(x1, y1, z1)]

    c00 = c000 * (1 - fx) + c100 * fx
    c10 = c010 * (1 - fx) + c110 * fx
    c01 = c001 * (1 - fx) + c101 * fx
    c11 = c011 * (1 - fx) + c111 * fx

    c0 = c00 * (1 - fy) + c10 * fy
    c1 = c01 * (1 - fy) + c11 * fy

    return (c0 * (1 - fz) + c1 * fz).astype(np.float32)


def _smoothstep(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)
