"""Density diffusion via separable 3D Gaussian / box blur.

Equivalent to forward-Euler integration of the heat equation on a
regular grid when the diffusion kernel is small. Each step convolves
the density with a 3x3x3 box kernel weighted by ``rate*dt``; this
gives the familiar smoke-spreading behaviour over time without solving
a tridiagonal system.

Scaffolding-grade: not a true implicit diffusion solver, no flux
limiter, and the diffusion coefficient is in voxel units. Sufficient
for the worked smoke-cloud example.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def simulate_diffusion(
    volume: Any,
    rate: float = 0.1,
    dt: float = 0.05,
    steps: int = 1,
    **_: Any,
) -> Any:
    """Diffuse ``volume.density`` in place for ``steps`` substeps.

    Uses an explicit 6-neighbour Laplacian update; the effective
    coefficient is clamped to keep the explicit scheme stable
    (``alpha <= 1/6`` ensures non-negative weights).
    """
    alpha = float(rate) * float(dt)
    alpha = float(np.clip(alpha, 0.0, 1.0 / 6.0))
    if alpha == 0.0:
        return volume

    density = volume.density.astype(np.float32, copy=False)
    for _ in range(max(0, int(steps))):
        density = _laplacian_step(density, alpha)
    volume.density = density.astype(np.float32, copy=False)
    return volume


def _laplacian_step(field: np.ndarray, alpha: float) -> np.ndarray:
    nx, ny, nz = field.shape
    out = field * (1.0 - 6.0 * alpha)

    out[1:, :, :] += alpha * field[:-1, :, :]
    out[:-1, :, :] += alpha * field[1:, :, :]
    out[:, 1:, :] += alpha * field[:, :-1, :]
    out[:, :-1, :] += alpha * field[:, 1:, :]
    out[:, :, 1:] += alpha * field[:, :, :-1]
    out[:, :, :-1] += alpha * field[:, :, 1:]

    out[0, :, :] += alpha * field[0, :, :]
    out[-1, :, :] += alpha * field[-1, :, :]
    out[:, 0, :] += alpha * field[:, 0, :]
    out[:, -1, :] += alpha * field[:, -1, :]
    out[:, :, 0] += alpha * field[:, :, 0]
    out[:, :, -1] += alpha * field[:, :, -1]

    return out
