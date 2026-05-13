"""Foundry F4 — prismatic / crystal cluster builder.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §16.3
(VioletCrystalCluster spec): a crystal cluster has 3-9 faceted prisms
with varied heights, radii, rotations, plus optional base rocks.

This module composes ``PrismMesh`` instances from ``polyhedron.py``
into a deterministic, seedable cluster. Each prism carries zone IDs
that downstream material wiring (LowPolyFantasy palette: violet/
magenta/cyan) binds to.

The module is pure-Python and deterministic — the same
``CrystalParameters`` always produces the same cluster, which is the
basis of the Foundry's variant-stability certificate (masterplan §7.4).

Reference: gemeini_research.md (Prismatic Kernel) +
gpt_research.md (Facet Fields).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .polyhedron import PrismMesh, build_prism_mesh

PRISMATIC_VERSION = "lathe.asset_foundry.prismatic_v1"


@dataclass(frozen=True)
class CrystalPrism:
    """One faceted crystal in a cluster — a prism + placement."""

    crystal_id: str
    mesh: PrismMesh
    """The faceted prism mesh."""
    translation_cm: tuple[float, float, float]
    """Cluster-local placement."""
    rotation_deg: float
    """Rotation around the vertical axis (Z)."""
    tilt_deg: float
    """Tilt from vertical (radial)."""
    height_cm: float
    radius_cm: float
    role: str = "secondary"
    """``primary`` for the hero crystal, ``secondary`` for shards,
    ``base`` for cluster base rocks."""


@dataclass(frozen=True)
class CrystalParameters:
    """Inputs for a deterministic crystal cluster build.

    The ``seed`` field is the canonical determinism handle. Two
    builds with the same params produce identical clusters — the
    basis for Foundry variant-stability scoring.
    """

    seed: int = 0
    crystal_count: int = 5
    primary_height_cm: float = 32.0
    primary_radius_cm: float = 6.0
    secondary_height_range_cm: tuple[float, float] = (12.0, 22.0)
    secondary_radius_range_cm: tuple[float, float] = (2.0, 4.5)
    cluster_radius_cm: float = 10.0
    sides_per_prism: int = 6
    top_taper: float = 0.35
    """``top_radius = base_radius * (1 - top_taper)``."""
    tilt_max_deg: float = 18.0
    base_z_cm: float = 0.0
    palette_id: str = "lowpoly_fantasy.violet_crystal_v1"


@dataclass(frozen=True)
class PrismaticCluster:
    """A faceted prismatic cluster of crystals."""

    cluster_id: str
    crystals: tuple[CrystalPrism, ...]
    parameters: CrystalParameters
    palette_id: str
    bbox_cm: tuple[tuple[float, float, float], tuple[float, float, float]]
    """``((min_x, min_y, min_z), (max_x, max_y, max_z))``."""
    diagnostics: tuple[str, ...] = ()

    def crystal_count(self) -> int:
        return len(self.crystals)


def _seeded_random(seed: int) -> "_SeededRng":
    return _SeededRng(seed)


class _SeededRng:
    """Tiny deterministic LCG for reproducible cluster builds.

    Using a custom LCG (not ``random.Random``) keeps the cluster
    deterministic regardless of Python's RNG implementation changes.
    """

    def __init__(self, seed: int) -> None:
        self.state = seed if seed != 0 else 0xDEADBEEF
        # Advance once so seed=0 still produces varied output.
        self._advance()

    def _advance(self) -> int:
        # Numerical Recipes LCG constants.
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def uniform(self, lo: float, hi: float) -> float:
        r = self._advance() / 0xFFFFFFFF
        return lo + r * (hi - lo)

    def randint(self, lo: int, hi: int) -> int:
        r = self._advance()
        span = hi - lo + 1
        return lo + (r % span)


def build_crystal_cluster(
    params: CrystalParameters | None = None,
    *,
    cluster_id: str = "violet_crystal_cluster",
) -> PrismaticCluster:
    """Build a deterministic crystal cluster from parameters.

    Pure function. Same params -> same cluster.
    """
    params = params if params is not None else CrystalParameters()
    rng = _seeded_random(params.seed)
    crystals: list[CrystalPrism] = []

    # Primary crystal at center.
    primary_top_radius = params.primary_radius_cm * max(0.0, 1.0 - params.top_taper)
    primary_mesh = build_prism_mesh(
        sides=params.sides_per_prism,
        base_radius_cm=params.primary_radius_cm,
        height_cm=params.primary_height_cm,
        top_radius_cm=primary_top_radius,
        base_z_cm=params.base_z_cm,
        twist_deg=12.0,
        zone_prefix=f"{cluster_id}.primary",
    )
    crystals.append(
        CrystalPrism(
            crystal_id=f"{cluster_id}.primary",
            mesh=primary_mesh,
            translation_cm=(0.0, 0.0, 0.0),
            rotation_deg=0.0,
            tilt_deg=0.0,
            height_cm=params.primary_height_cm,
            radius_cm=params.primary_radius_cm,
            role="primary",
        )
    )

    # Secondary crystals around the primary.
    n_secondary = max(0, params.crystal_count - 1)
    sec_h_lo, sec_h_hi = params.secondary_height_range_cm
    sec_r_lo, sec_r_hi = params.secondary_radius_range_cm
    for i in range(n_secondary):
        angle = i * (2.0 * math.pi / max(1, n_secondary))
        radial_jitter = rng.uniform(0.6, 1.0)
        x = math.cos(angle) * params.cluster_radius_cm * radial_jitter
        y = math.sin(angle) * params.cluster_radius_cm * radial_jitter
        h = rng.uniform(sec_h_lo, sec_h_hi)
        r = rng.uniform(sec_r_lo, sec_r_hi)
        tilt = rng.uniform(-params.tilt_max_deg, params.tilt_max_deg)
        twist = rng.uniform(0.0, 30.0)
        top_r = r * max(0.0, 1.0 - params.top_taper)
        sides = params.sides_per_prism
        mesh = build_prism_mesh(
            sides=sides,
            base_radius_cm=r,
            height_cm=h,
            top_radius_cm=top_r,
            base_z_cm=params.base_z_cm,
            twist_deg=twist,
            zone_prefix=f"{cluster_id}.secondary_{i:02d}",
        )
        crystals.append(
            CrystalPrism(
                crystal_id=f"{cluster_id}.secondary_{i:02d}",
                mesh=mesh,
                translation_cm=(x, y, 0.0),
                rotation_deg=math.degrees(angle),
                tilt_deg=tilt,
                height_cm=h,
                radius_cm=r,
                role="secondary",
            )
        )

    # Compute cluster bbox.
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    for crystal in crystals:
        tx, ty, tz = crystal.translation_cm
        for vx, vy, vz in crystal.mesh.vertices:
            wx, wy, wz = vx + tx, vy + ty, vz + tz
            min_x = min(min_x, wx)
            min_y = min(min_y, wy)
            min_z = min(min_z, wz)
            max_x = max(max_x, wx)
            max_y = max(max_y, wy)
            max_z = max(max_z, wz)

    diagnostics: list[str] = []
    if params.crystal_count < 3:
        diagnostics.append(
            f"crystal_count_below_recommended_min: got {params.crystal_count}, recommended >= 3"
        )
    if params.crystal_count > 9:
        diagnostics.append(
            f"crystal_count_above_recommended_max: got {params.crystal_count}, recommended <= 9"
        )

    return PrismaticCluster(
        cluster_id=cluster_id,
        crystals=tuple(crystals),
        parameters=params,
        palette_id=params.palette_id,
        bbox_cm=((min_x, min_y, min_z), (max_x, max_y, max_z)),
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "PRISMATIC_VERSION",
    "CrystalParameters",
    "CrystalPrism",
    "PrismaticCluster",
    "build_crystal_cluster",
]
