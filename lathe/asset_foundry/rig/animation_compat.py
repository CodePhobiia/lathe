"""Animation library compatibility.

Per northstar §11 Phase 4. Animations target canonical bone names
and morph slots, so they retarget across compatible rigs without
manual remapping. This module declares typed clip/track shapes +
the canonical idle-breathing clip used as a smoke fixture.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

ANIMATION_COMPAT_VERSION = "lathe.asset_foundry.animation_compat_v1"


@dataclass(frozen=True)
class AnimationTrack:
    """One track = (bone or morph target) -> sampled values."""

    track_id: str
    target_kind: str
    """``bone_rotation`` | ``bone_translation`` | ``bone_scale`` |
    ``morph_weight``."""

    target_name: str
    """Canonical bone name or morph slot."""

    keyframe_times_s: tuple[float, ...]
    """Sample times in seconds. Must be sorted ascending."""

    keyframe_values: tuple[tuple[float, ...], ...]
    """Per-sample values. Length depends on target_kind:
      - bone_rotation: 4 (xyzw quat)
      - bone_translation / bone_scale: 3 (xyz)
      - morph_weight: 1."""

    interpolation: str = "linear"
    """``linear`` | ``step`` | ``cubic_spline``."""


@dataclass(frozen=True)
class AnimationClip:
    """A named clip — collection of tracks + duration."""

    clip_id: str
    duration_s: float
    tracks: tuple[AnimationTrack, ...]
    loop: bool = True
    canonical_template: str = ""
    """Template ID this clip is authored against
    (e.g. ``canonical.biped_v1``)."""


@dataclass(frozen=True)
class AnimationLibrary:
    """Named bundle of clips."""

    library_id: str
    clips: tuple[AnimationClip, ...]
    licensed_for_families: tuple[str, ...] = ()


def build_idle_breathing_clip(
    *,
    canonical_template: str = "canonical.biped_v1",
    duration_s: float = 4.0,
    bone_name: str = "spine_02",
) -> AnimationClip:
    """Build a simple breathing clip targeting the chest bone."""
    samples = 8
    rotation_samples: list[tuple[float, ...]] = []
    times: list[float] = []
    for i in range(samples + 1):
        t = i / samples
        times.append(t * duration_s)
        # Tiny up-down rotation around X.
        breathe = math.sin(t * 2.0 * math.pi) * 0.025
        qx = breathe
        # quaternion from axis-angle around x by breathe radians.
        s = math.sin(breathe / 2.0)
        c = math.cos(breathe / 2.0)
        rotation_samples.append((s, 0.0, 0.0, c))
    track = AnimationTrack(
        track_id="idle_breathing.spine",
        target_kind="bone_rotation",
        target_name=bone_name,
        keyframe_times_s=tuple(times),
        keyframe_values=tuple(rotation_samples),
    )
    return AnimationClip(
        clip_id="idle_breathing_v1",
        duration_s=duration_s,
        tracks=(track,),
        loop=True,
        canonical_template=canonical_template,
    )


__all__ = [
    "ANIMATION_COMPAT_VERSION",
    "AnimationClip",
    "AnimationLibrary",
    "AnimationTrack",
    "build_idle_breathing_clip",
]
