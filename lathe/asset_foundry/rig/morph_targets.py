"""Morph targets / blend shapes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

MORPH_TARGETS_VERSION = "lathe.asset_foundry.morph_targets_v1"


@dataclass(frozen=True)
class MorphTarget:
    """One morph target = a per-vertex displacement."""

    morph_id: str
    mesh_id: str
    displacements: Mapping[int, tuple[float, float, float]]
    """``vertex_index -> (dx, dy, dz)`` in cm. Sparse — only vertices
    that actually move are listed."""
    default_weight: float = 0.0
    weight_range: tuple[float, float] = (0.0, 1.0)
    morph_kind: str = "blend_shape"
    """``blend_shape`` | ``corrective`` | ``visemes`` | ``emote``."""


@dataclass(frozen=True)
class MorphTargetSet:
    asset_id: str
    morphs: tuple[MorphTarget, ...]
    semantic_groups: Mapping[str, tuple[str, ...]] = ()
    """e.g. ``{"face_emotes": ("smile", "frown", "blink_left", "blink_right")}``."""


__all__ = [
    "MORPH_TARGETS_VERSION",
    "MorphTarget",
    "MorphTargetSet",
]
