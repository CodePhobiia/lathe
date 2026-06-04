"""Foundry F4 — FacetField 2D/3D sampler.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md
§10.4 (Foundry v0.1 Prismatic subset) and §16.9 (FloatingIslandSmall
faceted cliff), the Foundry needs controlled planar facets for:

- floating island faceted cliff undersides;
- stylized roof chunks;
- angular rock outcrops;
- chunky path stone slabs.

A FacetField is a parametric sampler that snaps a continuous surface
into intentional planar cells with bounded facet size + controlled
sliver triangle rejection. Conceptually a discrete-Voronoi/seeded-
grid approximation.

The module is pure-Python. It does NOT mesh anything itself — it
produces a sequence of FacetSample records (center + plane + zone)
that downstream mesh builders consume to bake real geometry.

Reference: gpt_research.md "Facet Fields" + gemeini_research.md
"Voronoi-cellular meshing for faceted terrain".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

FACET_FIELD_VERSION = "lathe.asset_foundry.facet_field_v1"


@dataclass(frozen=True)
class FacetSample:
    """One facet in the field: a planar cell + zone attribution."""

    sample_id: str
    center_cm: tuple[float, float, float]
    normal: tuple[float, float, float]
    """Unit-length facet plane normal."""
    extent_cm: float
    """Approximate facet half-extent (in-plane)."""
    zone_id: str
    """Material/zone label."""


@dataclass(frozen=True)
class FacetField2D:
    """A planar facet field — grid + seed jitter -> intentional facets."""

    field_id: str
    samples: tuple[FacetSample, ...]
    bbox_cm: tuple[tuple[float, float], tuple[float, float]]
    cell_size_cm: float
    seed: int

    def sample_count(self) -> int:
        return len(self.samples)


@dataclass(frozen=True)
class FacetField3D:
    """A volumetric facet field — radial seeds around an axis."""

    field_id: str
    samples: tuple[FacetSample, ...]
    bbox_cm: tuple[tuple[float, float, float], tuple[float, float, float]]
    axis: tuple[float, float, float]
    seed: int

    def sample_count(self) -> int:
        return len(self.samples)


def _seeded_random(seed: int) -> "_LcgRng":
    return _LcgRng(seed)


class _LcgRng:
    """Local deterministic LCG (no Python ``random`` dependency)."""

    def __init__(self, seed: int) -> None:
        self.state = seed if seed != 0 else 0xC0FFEE

    def next_float(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


def sample_facet_field(
    *,
    field_id: str,
    bbox_cm: tuple[tuple[float, float], tuple[float, float]],
    cell_size_cm: float,
    seed: int = 0,
    jitter: float = 0.25,
    sliver_threshold: float = 0.15,
    zone_id_prefix: str = "facet_field",
) -> FacetField2D:
    """Sample a 2D facet field with controlled cell jitter.

    Per ``newresearch.md`` §1 and §10.4, facets should look authored,
    not random. The jitter is bounded relative to the cell size, and
    samples that would produce a sliver-thin facet are rejected.

    Args:
        field_id: stable name for the field.
        bbox_cm: ``((min_x, min_y), (max_x, max_y))`` extent.
        cell_size_cm: grid resolution. Smaller -> denser facets.
        seed: deterministic RNG seed.
        jitter: fraction of cell_size_cm to jitter cell centers
            (0.0 = perfect grid).
        sliver_threshold: minimum aspect ratio for a facet to be
            emitted (rejects pathological cases).
        zone_id_prefix: prefix for facet zone IDs.
    """
    rng = _seeded_random(seed)
    (min_x, min_y), (max_x, max_y) = bbox_cm
    if cell_size_cm <= 0:
        raise ValueError("cell_size_cm must be positive")
    cells_x = max(1, int(math.ceil((max_x - min_x) / cell_size_cm)))
    cells_y = max(1, int(math.ceil((max_y - min_y) / cell_size_cm)))
    samples: list[FacetSample] = []
    for iy in range(cells_y):
        for ix in range(cells_x):
            base_x = min_x + (ix + 0.5) * cell_size_cm
            base_y = min_y + (iy + 0.5) * cell_size_cm
            dx = (rng.next_float() - 0.5) * 2.0 * jitter * cell_size_cm
            dy = (rng.next_float() - 0.5) * 2.0 * jitter * cell_size_cm
            cx, cy = base_x + dx, base_y + dy
            # Tiny variation in normal to make facets look chunky-faceted.
            tilt_x = (rng.next_float() - 0.5) * 0.2
            tilt_y = (rng.next_float() - 0.5) * 0.2
            n_len = math.sqrt(tilt_x * tilt_x + tilt_y * tilt_y + 1.0)
            normal = (tilt_x / n_len, tilt_y / n_len, 1.0 / n_len)
            # Sliver check: a heavily-jittered facet near the bbox edge
            # could pinch. Use jitter magnitude vs cell size.
            aspect = 1.0 - (
                math.sqrt(dx * dx + dy * dy) / max(0.001, cell_size_cm)
            )
            if aspect < sliver_threshold:
                continue
            sample_id = f"{field_id}.cell_{ix:03d}_{iy:03d}"
            samples.append(
                FacetSample(
                    sample_id=sample_id,
                    center_cm=(cx, cy, 0.0),
                    normal=normal,
                    extent_cm=cell_size_cm * 0.5,
                    zone_id=f"{zone_id_prefix}.row_{iy:03d}",
                )
            )
    return FacetField2D(
        field_id=field_id,
        samples=tuple(samples),
        bbox_cm=bbox_cm,
        cell_size_cm=cell_size_cm,
        seed=seed,
    )


def sample_facet_field_3d_radial(
    *,
    field_id: str,
    axis_origin_cm: tuple[float, float, float],
    axis: tuple[float, float, float],
    height_cm: float,
    base_radius_cm: float,
    rings: int = 6,
    facets_per_ring: int = 12,
    seed: int = 0,
    zone_id_prefix: str = "facet_field_3d",
) -> FacetField3D:
    """Sample a 3D radial facet field around a vertical axis.

    Used for faceted cliff sides + floating-island undersides. Each
    ring is a horizontal slice; each facet is one radial wedge.

    Args:
        field_id: stable name.
        axis_origin_cm: bottom-center of the axis.
        axis: axis direction (typically ``(0,0,1)``).
        height_cm: extent along the axis.
        base_radius_cm: radius at the base ring.
        rings: number of horizontal slices.
        facets_per_ring: facets in each ring.
        seed: deterministic RNG.
        zone_id_prefix: facet zone prefix.
    """
    rng = _seeded_random(seed)
    samples: list[FacetSample] = []
    ox, oy, oz = axis_origin_cm
    ax, ay, az = axis
    a_len = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / a_len, ay / a_len, az / a_len
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    for ring_idx in range(rings):
        t = ring_idx / max(1, rings - 1) if rings > 1 else 0.5
        z = oz + t * height_cm
        # Taper: top is narrower than bottom.
        radius = base_radius_cm * (1.0 - 0.4 * t)
        for f in range(facets_per_ring):
            theta = f * (2.0 * math.pi / facets_per_ring)
            jitter = (rng.next_float() - 0.5) * 0.1
            theta += jitter
            cx = ox + radius * math.cos(theta)
            cy = oy + radius * math.sin(theta)
            cz = z
            n_radial = (math.cos(theta), math.sin(theta), 0.0)
            sample = FacetSample(
                sample_id=f"{field_id}.ring_{ring_idx:02d}.face_{f:02d}",
                center_cm=(cx, cy, cz),
                normal=n_radial,
                extent_cm=(2.0 * math.pi * radius) / max(1, facets_per_ring) * 0.5,
                zone_id=f"{zone_id_prefix}.ring_{ring_idx:02d}",
            )
            samples.append(sample)
            min_x, min_y, min_z = min(min_x, cx), min(min_y, cy), min(min_z, cz)
            max_x, max_y, max_z = max(max_x, cx), max(max_y, cy), max(max_z, cz)
    return FacetField3D(
        field_id=field_id,
        samples=tuple(samples),
        bbox_cm=((min_x, min_y, min_z), (max_x, max_y, max_z)),
        axis=(ax, ay, az),
        seed=seed,
    )


__all__ = [
    "FACET_FIELD_VERSION",
    "FacetField2D",
    "FacetField3D",
    "FacetSample",
    "sample_facet_field",
    "sample_facet_field_3d_radial",
]
