"""Temperature-driven buoyancy (Boussinesq approximation).

Standard buoyancy for hot smoke / fire columns: the body force per unit
volume is

    f_buoy = -alpha * (T - T_ambient) * gravity

where alpha is the buoyancy coefficient and ``gravity`` points down.
Hotter-than-ambient voxels receive an upward force; the resulting
acceleration is integrated into the velocity field, which then advects
density (the advection stage is a separate call).

We additionally apply a vertical density-driven self-rise term
(``f_density = density * buoyancy_coef * up``) so that even without a
temperature field, dense smoke parcels still rise — gives the worked
example a recognizable cloud-rise without forcing a temperature input.
"""

from __future__ import annotations

from typing import Any

import numpy as np

_DEFAULT_GRAVITY = (0.0, 0.0, -9.8)


def simulate_buoyancy(
    volume: Any,
    gravity: tuple[float, float, float] = _DEFAULT_GRAVITY,
    buoyancy_coef: float = 0.5,
    ambient_temperature: float = 0.0,
    dt: float = 0.05,
    steps: int = 1,
    self_advect: bool = True,
    **_: Any,
) -> Any:
    """Integrate buoyancy into ``volume.velocity`` and (optionally) self-advect density.

    If ``self_advect`` is True, after each velocity update the density is
    pushed along the new velocity by ``simulate_advection`` for one substep.
    This makes the buoyancy stage standalone-useful for the smoke-cloud
    worked example without requiring callers to interleave advection.
    """
    res = tuple(volume.resolution)
    if volume.velocity is None:
        volume.velocity = np.zeros((*res, 3), dtype=np.float32)

    g = np.asarray(gravity, dtype=np.float32)
    up = -g  # upward force opposes gravity

    for _ in range(max(0, int(steps))):
        density = volume.density.astype(np.float32, copy=False)

        if volume.temperature is not None:
            temp = volume.temperature.astype(np.float32, copy=False)
            scalar = float(buoyancy_coef) * (temp - float(ambient_temperature))
        else:
            scalar = float(buoyancy_coef) * density

        force = np.empty((*res, 3), dtype=np.float32)
        force[..., 0] = scalar * up[0]
        force[..., 1] = scalar * up[1]
        force[..., 2] = scalar * up[2]

        force[..., 0] += g[0]
        force[..., 1] += g[1]
        force[..., 2] += g[2]

        force *= density[..., None]

        volume.velocity = (volume.velocity + force * dt).astype(np.float32)

        if self_advect:
            from .advection import simulate_advection

            simulate_advection(volume, dt=dt, steps=1)

    return volume
