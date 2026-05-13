"""SpeedTree-inspired vegetation vocabulary.

Per northstar §11 Phase 3. A tree structure is a recursive trunk +
branch system with parametric variation: branch angle, length,
twist, leaf clusters, root flare.

This module emits a typed ``TreeStructure`` (no real mesh) that
downstream stages turn into procedural geometry via the kernel
program + the existing AlpinePine generator pattern.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

VEGETATION_VERSION = "lathe.asset_foundry.vegetation_v1"


@dataclass(frozen=True)
class BranchParameters:
    """Per-branch parametric controls."""

    branch_id: str
    depth: int
    """0 = trunk, 1 = primary branches, 2 = secondary, ..."""

    base_radius_cm: float
    tip_radius_cm: float
    length_cm: float
    angle_from_parent_deg: float
    azimuth_deg: float
    """Around the parent's axis."""

    children_count: int = 0
    leaf_cluster_count: int = 0


@dataclass(frozen=True)
class LeafCluster:
    """A leaf cluster anchored to a branch."""

    cluster_id: str
    branch_id: str
    position_along_branch: float
    """Fraction in [0, 1]."""

    radius_cm: float
    density: float
    """0 (sparse) to 1 (dense)."""

    leaf_archetype: str = "needle"
    """``needle`` | ``broadleaf`` | ``frond`` | ``compound``."""


@dataclass(frozen=True)
class TreeStructure:
    """Full procedural tree definition."""

    tree_id: str
    species: str
    branches: tuple[BranchParameters, ...]
    leaf_clusters: tuple[LeafCluster, ...]
    height_cm: float
    canopy_radius_cm: float
    foliage_seasonal_state: str = "summer"
    """``spring`` | ``summer`` | ``autumn`` | ``winter``."""


def build_tree_structure(
    *,
    tree_id: str,
    species: str = "alpine_pine",
    height_cm: float = 800.0,
    canopy_radius_cm: float = 250.0,
    primary_branches: int = 8,
    secondary_branches_per_primary: int = 3,
    leaf_archetype: str = "needle",
    seed: int = 0,
) -> TreeStructure:
    """Build a deterministic tree structure."""
    trunk = BranchParameters(
        branch_id=f"{tree_id}.trunk",
        depth=0,
        base_radius_cm=height_cm * 0.04,
        tip_radius_cm=height_cm * 0.02,
        length_cm=height_cm,
        angle_from_parent_deg=0.0,
        azimuth_deg=0.0,
        children_count=primary_branches,
        leaf_cluster_count=0,
    )
    branches: list[BranchParameters] = [trunk]
    leaf_clusters: list[LeafCluster] = []
    rng_state = seed if seed != 0 else 0xCAFE
    for i in range(primary_branches):
        rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
        primary = BranchParameters(
            branch_id=f"{tree_id}.primary_{i:02d}",
            depth=1,
            base_radius_cm=trunk.tip_radius_cm * 0.5,
            tip_radius_cm=trunk.tip_radius_cm * 0.1,
            length_cm=canopy_radius_cm * (0.7 + (rng_state / 0xFFFFFFFF) * 0.5),
            angle_from_parent_deg=45.0 + (rng_state / 0xFFFFFFFF) * 25.0,
            azimuth_deg=i * (360.0 / primary_branches),
            children_count=secondary_branches_per_primary,
            leaf_cluster_count=2,
        )
        branches.append(primary)
        for s in range(secondary_branches_per_primary):
            rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
            secondary = BranchParameters(
                branch_id=f"{tree_id}.primary_{i:02d}.secondary_{s:02d}",
                depth=2,
                base_radius_cm=primary.tip_radius_cm * 0.4,
                tip_radius_cm=primary.tip_radius_cm * 0.1,
                length_cm=primary.length_cm * 0.4,
                angle_from_parent_deg=30.0 + (rng_state / 0xFFFFFFFF) * 20.0,
                azimuth_deg=s * 120.0,
                children_count=0,
                leaf_cluster_count=1,
            )
            branches.append(secondary)
            for k in range(secondary.leaf_cluster_count):
                rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
                leaf_clusters.append(
                    LeafCluster(
                        cluster_id=f"{secondary.branch_id}.leaf_{k:02d}",
                        branch_id=secondary.branch_id,
                        position_along_branch=0.5 + 0.5 * (rng_state / 0xFFFFFFFF),
                        radius_cm=8.0 + 4.0 * (rng_state / 0xFFFFFFFF),
                        density=0.7 + 0.25 * (rng_state / 0xFFFFFFFF),
                        leaf_archetype=leaf_archetype,
                    )
                )
        for k in range(primary.leaf_cluster_count):
            rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
            leaf_clusters.append(
                LeafCluster(
                    cluster_id=f"{primary.branch_id}.leaf_{k:02d}",
                    branch_id=primary.branch_id,
                    position_along_branch=0.4 + 0.5 * (rng_state / 0xFFFFFFFF),
                    radius_cm=12.0 + 8.0 * (rng_state / 0xFFFFFFFF),
                    density=0.7 + 0.25 * (rng_state / 0xFFFFFFFF),
                    leaf_archetype=leaf_archetype,
                )
            )
    return TreeStructure(
        tree_id=tree_id,
        species=species,
        branches=tuple(branches),
        leaf_clusters=tuple(leaf_clusters),
        height_cm=height_cm,
        canopy_radius_cm=canopy_radius_cm,
    )


__all__ = [
    "VEGETATION_VERSION",
    "BranchParameters",
    "LeafCluster",
    "TreeStructure",
    "build_tree_structure",
]
