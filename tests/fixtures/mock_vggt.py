"""Mock VGGT point-cloud generator.

Provides a seeded, torch-free point-map generator that returns arrays
shaped as ``shape_providers._to_point_map_numpy`` expects downstream:

- ``point_maps``: ``float32`` array, shape ``[V, H, W, 3]``
- ``confidences``: ``float32`` array, shape ``[V, H, W]``

No torch dependency — pure numpy. Deterministic under a fixed seed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest


@dataclass(frozen=True)
class VggtStubPointCloud:
    """Container for deterministic mock VGGT output.

    Attributes:
        point_maps: ``float32`` array shape ``[V, H, W, 3]`` (world-space XYZ
            per-pixel per-view).
        confidences: ``float32`` array shape ``[V, H, W]`` in ``[0, 1]``.
        seed: Seed used for the generator (for reproducibility logging).
    """

    point_maps: np.ndarray
    confidences: np.ndarray
    seed: int


def _make_plane_views(
    *,
    num_views: int,
    height: int,
    width: int,
    seed: int,
) -> VggtStubPointCloud:
    """Generate ``num_views`` slightly-offset planar point maps.

    Each view is a flat ``z ≈ 0`` plane with a small per-view offset in X
    and Z so that downstream merge/weld paths see distinguishable coords
    while still producing a well-formed mesh.
    """
    rng = np.random.default_rng(seed)
    xs = np.linspace(-1.0, 1.0, num=width, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, num=height, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    views: list[np.ndarray] = []
    confs: list[np.ndarray] = []
    for v in range(num_views):
        dx = 0.1 * v
        dz = 0.05 * v
        jitter = rng.normal(0.0, 1e-3, size=grid_x.shape).astype(np.float32)
        plane = np.stack(
            [grid_x + dx + jitter, grid_y, np.zeros_like(grid_x) + dz],
            axis=-1,
        )
        views.append(plane.astype(np.float32))
        confs.append(np.full((height, width), 0.95, dtype=np.float32))
    return VggtStubPointCloud(
        point_maps=np.stack(views, axis=0),
        confidences=np.stack(confs, axis=0),
        seed=seed,
    )


@pytest.fixture()
def vggt_stub_point_cloud() -> VggtStubPointCloud:
    """Default 2-view, 8x8 deterministic point-cloud for smoke cases."""
    return _make_plane_views(num_views=2, height=8, width=8, seed=1234)


@pytest.fixture()
def vggt_stub_factory():
    """Factory for customizing view count, resolution, and seed."""

    def _build(
        *,
        num_views: int = 2,
        height: int = 8,
        width: int = 8,
        seed: int = 1234,
    ) -> VggtStubPointCloud:
        return _make_plane_views(num_views=num_views, height=height, width=width, seed=seed)

    return _build
