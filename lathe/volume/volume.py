"""Volume container + program compilation + stage dispatch.

`Volume` is a dense numpy-backed sparse grid: density is an
``(nx, ny, nz)`` float32 array, with optional temperature and
3-vector velocity fields. Bounds are an axis-aligned box in
world units (cm by Lathe convention). Stored as dense arrays at
the resolutions used here (typically <= 256^3 = 16M voxels);
the optional OpenVDB backend is the path forward for genuinely
sparse data.

The data IR record `lathe.volume_effects_data_ir.v1` (reserved
in GOAL_PROGRESS.md) is what `compile_volume` emits as a Python
mapping for downstream stages to consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np


_VEC3_LEN = 3
_BOUNDS_LEN = 6
_DEFAULT_RESOLUTION = (32, 32, 32)
_DEFAULT_BOUNDS = (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0)


@dataclass
class Volume:
    """Dense 3D voxel grid with density, temperature, velocity attributes."""

    resolution: tuple[int, int, int] = _DEFAULT_RESOLUTION
    bounds: tuple[float, float, float, float, float, float] = _DEFAULT_BOUNDS
    density: np.ndarray = field(default=None)  # type: ignore[assignment]
    temperature: np.ndarray | None = None
    velocity: np.ndarray | None = None
    seed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.density is None:
            self.density = np.zeros(self.resolution, dtype=np.float32)
        elif self.density.shape != tuple(self.resolution):
            raise ValueError(
                f"density shape {self.density.shape} != resolution {self.resolution}"
            )

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(self.resolution)  # type: ignore[return-value]

    @property
    def voxel_size(self) -> tuple[float, float, float]:
        nx, ny, nz = self.resolution
        x0, y0, z0, x1, y1, z1 = self.bounds
        return ((x1 - x0) / nx, (y1 - y0) / ny, (z1 - z0) / nz)

    def total_density(self) -> float:
        return float(np.sum(self.density))

    def occupied_voxel_count(self, threshold: float = 1e-3) -> int:
        return int(np.count_nonzero(self.density > threshold))

    def summary(self) -> dict[str, Any]:
        return {
            "resolution": list(self.resolution),
            "bounds": list(self.bounds),
            "voxel_size": list(self.voxel_size),
            "density_min": float(np.min(self.density)),
            "density_max": float(np.max(self.density)),
            "density_mean": float(np.mean(self.density)),
            "total_density": self.total_density(),
            "occupied_voxels": self.occupied_voxel_count(),
            "has_temperature": self.temperature is not None,
            "has_velocity": self.velocity is not None,
            "seed": self.seed,
        }


def _coerce_resolution(value: Any) -> tuple[int, int, int]:
    if value is None:
        return _DEFAULT_RESOLUTION
    if isinstance(value, (list, tuple)) and len(value) == _VEC3_LEN:
        nx, ny, nz = (int(v) for v in value)
        if min(nx, ny, nz) < 2:
            raise ValueError(f"volume resolution components must be >= 2 (got {value})")
        return (nx, ny, nz)
    raise ValueError(f"volume resolution must be a 3-tuple of ints, got {value!r}")


def _coerce_bounds(value: Any) -> tuple[float, float, float, float, float, float]:
    if value is None:
        return _DEFAULT_BOUNDS
    if isinstance(value, (list, tuple)) and len(value) == _BOUNDS_LEN:
        x0, y0, z0, x1, y1, z1 = (float(v) for v in value)
        if not (x1 > x0 and y1 > y0 and z1 > z0):
            raise ValueError(f"volume bounds must satisfy max>min on every axis, got {value}")
        return (x0, y0, z0, x1, y1, z1)
    raise ValueError(f"volume bounds must be a 6-tuple (x0,y0,z0,x1,y1,z1), got {value!r}")


def compile_volume(
    program: dict[str, Any] | None = None,
    *,
    resolution: Any = None,
    bounds: Any = None,
    seed: int | None = None,
) -> Volume:
    """Compile a normalized volume_program declaration into a Volume.

    The program mapping accepts these fields (all optional):

        seed: int                       -- determinism anchor
        density_noise: dict             -- {"kind": "fractal"|"worley", ...}
        temperature_noise: dict         -- same shape as density_noise
        initial_velocity: list[3]       -- constant initial velocity vec3

    Asset-side overrides (``volume { resolution = ..., bounds = ... }``)
    are passed via the explicit kwargs which take precedence.
    """
    program = program or {}
    res = _coerce_resolution(resolution if resolution is not None else program.get("resolution"))
    bnd = _coerce_bounds(bounds if bounds is not None else program.get("bounds"))
    eff_seed = int(seed if seed is not None else program.get("seed", 0))

    vol = Volume(resolution=res, bounds=bnd, seed=eff_seed)

    density_noise = program.get("density_noise")
    if isinstance(density_noise, dict):
        vol.density = _build_noise(density_noise, res, eff_seed, salt=0).astype(np.float32)

    temp_noise = program.get("temperature_noise")
    if isinstance(temp_noise, dict):
        vol.temperature = _build_noise(temp_noise, res, eff_seed, salt=1).astype(np.float32)

    initial_velocity = program.get("initial_velocity")
    if isinstance(initial_velocity, (list, tuple)) and len(initial_velocity) == _VEC3_LEN:
        vec = np.asarray(initial_velocity, dtype=np.float32)
        vel = np.zeros((*res, _VEC3_LEN), dtype=np.float32)
        vel[..., :] = vec
        vol.velocity = vel

    vol.metadata["program"] = dict(program)
    vol.metadata["data_ir"] = "lathe.volume_effects_data_ir.v1"
    return vol


def _build_noise(
    spec: dict[str, Any], shape: tuple[int, int, int], base_seed: int, *, salt: int
) -> np.ndarray:
    from . import noise_field

    kind = str(spec.get("kind", "fractal")).lower()
    seed = int(spec.get("seed", base_seed)) ^ salt
    if kind == "fractal":
        return noise_field.fractal_volume(
            shape,
            octaves=int(spec.get("octaves", 4)),
            scale=float(spec.get("scale", 1.0)),
            persistence=float(spec.get("persistence", 0.5)),
            seed=seed,
        )
    if kind == "worley":
        return noise_field.worley_clusters(
            shape,
            cluster_count=int(spec.get("cluster_count", 12)),
            cluster_radius=float(spec.get("cluster_radius", 0.4)),
            seed=seed,
        )
    raise ValueError(f"unknown volume noise kind: {kind!r}")


def simulate_volume(volume: Volume, stages: Sequence[dict[str, Any]]) -> Volume:
    """Apply a sequence of simulator stages to ``volume`` in place.

    Each stage is a mapping ``{"kind": "advection"|"buoyancy"|"diffusion", ...}``;
    extra keys are forwarded to the underlying simulator. Returns the
    same ``volume`` instance so call sites can chain.
    """
    from .advection import simulate_advection
    from .buoyancy import simulate_buoyancy
    from .diffusion import simulate_diffusion

    for stage in stages:
        kind = str(stage.get("kind", "")).lower()
        params = {k: v for k, v in stage.items() if k != "kind"}
        if kind == "advection":
            simulate_advection(volume, **params)
        elif kind == "buoyancy":
            simulate_buoyancy(volume, **params)
        elif kind == "diffusion":
            simulate_diffusion(volume, **params)
        else:
            raise ValueError(f"unknown volume simulator stage: {kind!r}")
    return volume
