"""Heightfield — first-class terrain data type for §7.2.

A ``Heightfield`` wraps a 2D numpy array of elevation samples laid out on
a regular grid in the XY plane. It is the working data structure for
terrain authoring (initial fractal noise → erosion solvers →
biome-layered masks) and has a deterministic round-trip with the stable
``ShapePrimitive(primitive_type="heightfield")`` record used by the
shape-stage exact mesh path (``lathe.exact_solids._heightfield_mesh``).

Layout:
    - ``heights`` is shaped ``(ny, nx)`` (rows × cols). ``heights[r, c]``
      is the elevation at ``x = bounds_xy[0] + c * dx``,
      ``y = bounds_xy[1] + r * dy``, where ``dx`` and ``dy`` are the
      cell sizes along X and Y.
    - ``bounds_xy = (xmin, ymin, xmax, ymax)``.
    - ``vertical_scale`` is a multiplier applied to ``heights`` when
      computing world-space Z (slopes/gradients return *unscaled* values
      unless explicitly noted; the multiplier is for mesh emission).

Why this is a class rather than a tuple: the erosion solvers need to
mutate the heights, query slopes, and emit per-cell masks (water flow,
sediment deposition, etc.). Centralising those queries here keeps
``hydraulic.py`` / ``thermal.py`` / ``biome.py`` declarative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...shape_ir import ShapePrimitive


@dataclass
class Heightfield:
    """A regular-grid heightfield in the XY plane.

    Use ``Heightfield.zeros((nx, ny), bounds_xy)`` for blank canvas, then
    overlay procedural noise (``noise.fbm`` etc.), run erosion passes,
    and finally call ``to_shape_primitive(part="terrain", center=...)``
    to embed the result in a ShapeIR.
    """

    heights: np.ndarray  # shape (ny, nx), float64
    bounds_xy: tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    vertical_scale: float = 1.0
    masks: dict[str, np.ndarray] = field(default_factory=dict)

    @classmethod
    def zeros(
        cls,
        resolution: tuple[int, int],
        bounds_xy: tuple[float, float, float, float],
        *,
        vertical_scale: float = 1.0,
    ) -> Heightfield:
        nx, ny = int(resolution[0]), int(resolution[1])
        if nx <= 0 or ny <= 0:
            raise ValueError(
                f"Heightfield resolution must be positive ints, got ({nx}, {ny})"
            )
        xmin, ymin, xmax, ymax = (float(v) for v in bounds_xy)
        if not (xmax > xmin and ymax > ymin):
            raise ValueError(f"Heightfield bounds_xy invalid: {bounds_xy}")
        return cls(
            heights=np.zeros((ny, nx), dtype=np.float64),
            bounds_xy=(xmin, ymin, xmax, ymax),
            vertical_scale=float(vertical_scale),
        )

    @property
    def resolution(self) -> tuple[int, int]:
        ny, nx = self.heights.shape
        return int(nx), int(ny)

    @property
    def cell_size(self) -> tuple[float, float]:
        nx, ny = self.resolution
        xmin, ymin, xmax, ymax = self.bounds_xy
        dx = (xmax - xmin) / max(nx - 1, 1)
        dy = (ymax - ymin) / max(ny - 1, 1)
        return float(dx), float(dy)

    def copy(self) -> Heightfield:
        return Heightfield(
            heights=self.heights.copy(),
            bounds_xy=self.bounds_xy,
            vertical_scale=self.vertical_scale,
            masks={k: v.copy() for k, v in self.masks.items()},
        )

    def gradient(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(dz/dx, dz/dy)`` central differences, shape (ny, nx).

        World-up gradients use the *scaled* heights so downstream
        consumers (slope mask, flow direction) operate in world units.
        """
        z = self.heights * self.vertical_scale
        dx, dy = self.cell_size
        dzdx = np.zeros_like(z)
        dzdy = np.zeros_like(z)
        dzdx[:, 1:-1] = (z[:, 2:] - z[:, :-2]) / (2.0 * dx)
        dzdx[:, 0] = (z[:, 1] - z[:, 0]) / dx
        dzdx[:, -1] = (z[:, -1] - z[:, -2]) / dx
        dzdy[1:-1, :] = (z[2:, :] - z[:-2, :]) / (2.0 * dy)
        dzdy[0, :] = (z[1, :] - z[0, :]) / dy
        dzdy[-1, :] = (z[-1, :] - z[-2, :]) / dy
        return dzdx, dzdy

    def slope(self) -> np.ndarray:
        """Per-cell slope magnitude in *radians* (atan of |grad|)."""
        dzdx, dzdy = self.gradient()
        magnitude = np.sqrt(dzdx * dzdx + dzdy * dzdy)
        return np.arctan(magnitude)

    def slope_mask(self) -> np.ndarray:
        """Slope normalised to ``[0, 1]`` over the full ``[0, pi/2]`` range."""
        return np.clip(self.slope() / (np.pi * 0.5), 0.0, 1.0)

    def normals(self) -> np.ndarray:
        """Per-cell unit normal field, shape (ny, nx, 3)."""
        dzdx, dzdy = self.gradient()
        nx_field = -dzdx
        ny_field = -dzdy
        nz_field = np.ones_like(dzdx)
        stacked = np.stack([nx_field, ny_field, nz_field], axis=-1)
        norms = np.linalg.norm(stacked, axis=-1, keepdims=True)
        norms[norms <= 1e-12] = 1.0
        return stacked / norms

    def lowest_neighbor(self) -> tuple[np.ndarray, np.ndarray]:
        """For each cell, return ``(dr, dc)`` to its lowest 8-neighbor.

        Border cells with no lower neighbor return ``(0, 0)``. Used by
        flow-accumulation and thermal-erosion routines.
        """
        z = self.heights
        ny, nx = z.shape
        best_dh = np.zeros_like(z)
        best_dr = np.zeros_like(z, dtype=np.int8)
        best_dc = np.zeros_like(z, dtype=np.int8)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rs = slice(max(0, dr), ny + min(0, dr))
                cs = slice(max(0, dc), nx + min(0, dc))
                rd = slice(max(0, -dr), ny + min(0, -dr))
                cd = slice(max(0, -dc), nx + min(0, -dc))
                dh = z[rd, cd] - z[rs, cs]  # positive ⇒ neighbor lower
                update = dh > best_dh[rs, cs]
                best_dh[rs, cs] = np.where(update, dh, best_dh[rs, cs])
                best_dr[rs, cs] = np.where(update, dr, best_dr[rs, cs])
                best_dc[rs, cs] = np.where(update, dc, best_dc[rs, cs])
        return best_dr, best_dc

    def set_mask(self, name: str, mask: np.ndarray) -> None:
        if mask.shape != self.heights.shape:
            raise ValueError(
                f"mask {name!r} shape {mask.shape} != heightfield "
                f"shape {self.heights.shape}"
            )
        self.masks[name] = np.ascontiguousarray(mask, dtype=np.float64)

    def get_mask(self, name: str) -> np.ndarray | None:
        return self.masks.get(name)

    def to_shape_primitive(
        self,
        *,
        part: str,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        component: str | None = None,
        region: str | None = None,
        tags: list[str] | None = None,
    ) -> ShapePrimitive:
        """Lower this heightfield into a stable ``ShapePrimitive`` record."""
        from ...shape_ir import ShapePrimitive

        return ShapePrimitive(
            primitive_type="heightfield",
            part=part,
            center=center,
            resolution=self.resolution,
            height_data=self.heights.tolist(),
            bounds_xy=self.bounds_xy,
            vertical_scale=self.vertical_scale,
            tags=list(tags or []),
            component=component,
            region=region,
        )
