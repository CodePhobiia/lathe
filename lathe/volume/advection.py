"""Semi-Lagrangian density advection.

For each voxel ``x`` at the new timestep, trace its position back along
the velocity field by ``dt`` (``x_prev = x - v*dt``), then sample the
old density at ``x_prev`` via trilinear interpolation. This is the
canonical Stam (1999) "Stable Fluids" advection step, except we
operate only on density and only with an externally supplied velocity
field — there is no pressure projection or vorticity confinement.

Scaffolding-grade: no MAC grid, no boundary conditions beyond clamp,
no flux limiter. Sufficient to push smoke along a buoyant updraft.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def simulate_advection(
    volume: Any,
    velocity_field: np.ndarray | None = None,
    dt: float = 0.05,
    steps: int = 1,
    **_: Any,
) -> Any:
    """Move density along a velocity field for ``steps`` substeps.

    ``velocity_field`` defaults to ``volume.velocity``. Shape must be
    ``(nx, ny, nz, 3)`` in world units per second. Density is updated
    in place.
    """
    if velocity_field is None:
        velocity_field = volume.velocity
    if velocity_field is None:
        return volume
    if velocity_field.shape[:3] != tuple(volume.resolution) or velocity_field.shape[-1] != 3:
        raise ValueError(
            f"velocity_field shape {velocity_field.shape} does not match volume {volume.resolution}"
        )

    nx, ny, nz = volume.resolution
    vsx, vsy, vsz = volume.voxel_size
    inv_voxel = np.array([1.0 / vsx, 1.0 / vsy, 1.0 / vsz], dtype=np.float32)

    ix = np.arange(nx, dtype=np.float32)[:, None, None]
    iy = np.arange(ny, dtype=np.float32)[None, :, None]
    iz = np.arange(nz, dtype=np.float32)[None, None, :]

    density = volume.density.astype(np.float32, copy=False)
    for _ in range(max(0, int(steps))):
        vx = velocity_field[..., 0] * inv_voxel[0]
        vy = velocity_field[..., 1] * inv_voxel[1]
        vz = velocity_field[..., 2] * inv_voxel[2]

        sx = np.clip(ix - vx * dt, 0.0, nx - 1.0001)
        sy = np.clip(iy - vy * dt, 0.0, ny - 1.0001)
        sz = np.clip(iz - vz * dt, 0.0, nz - 1.0001)

        density = _trilinear_sample(density, sx, sy, sz)

    volume.density = density.astype(np.float32, copy=False)
    return volume


def _trilinear_sample(field: np.ndarray, sx: np.ndarray, sy: np.ndarray, sz: np.ndarray) -> np.ndarray:
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    z0 = np.floor(sz).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    z1 = z0 + 1
    fx = sx - x0
    fy = sy - y0
    fz = sz - z0

    c000 = field[x0, y0, z0]
    c100 = field[x1, y0, z0]
    c010 = field[x0, y1, z0]
    c110 = field[x1, y1, z0]
    c001 = field[x0, y0, z1]
    c101 = field[x1, y0, z1]
    c011 = field[x0, y1, z1]
    c111 = field[x1, y1, z1]

    c00 = c000 * (1 - fx) + c100 * fx
    c10 = c010 * (1 - fx) + c110 * fx
    c01 = c001 * (1 - fx) + c101 * fx
    c11 = c011 * (1 - fx) + c111 * fx
    c0 = c00 * (1 - fy) + c10 * fy
    c1 = c01 * (1 - fy) + c11 * fy
    return (c0 * (1 - fz) + c1 * fz).astype(np.float32)
