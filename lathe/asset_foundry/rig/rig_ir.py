"""Rig IR — typed skeleton data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

RIG_IR_VERSION = "lathe.asset_foundry.rig_ir_v1"


@dataclass(frozen=True)
class RigBone:
    bone_id: str
    parent_bone_id: str | None
    local_translation_cm: tuple[float, float, float]
    local_rotation_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    length_cm: float = 0.0
    bone_kind: str = "general"
    """``general`` | ``ik_chain`` | ``twist_helper`` | ``socket``."""


@dataclass(frozen=True)
class RigConstraint:
    constraint_id: str
    constraint_kind: str
    """``ik`` | ``aim`` | ``parent_constraint`` | ``orient`` | ``point``."""
    affected_bone_ids: tuple[str, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkeletonHierarchy:
    root_bone_id: str
    bones: Mapping[str, RigBone]

    def children_of(self, bone_id: str) -> tuple[str, ...]:
        return tuple(b.bone_id for b in self.bones.values() if b.parent_bone_id == bone_id)

    def depth_of(self, bone_id: str) -> int:
        depth = 0
        current = self.bones.get(bone_id)
        while current is not None and current.parent_bone_id is not None:
            depth += 1
            current = self.bones.get(current.parent_bone_id)
            if depth > 1024:
                return -1
        return depth


@dataclass(frozen=True)
class RigIR:
    rig_id: str
    asset_family: str
    hierarchy: SkeletonHierarchy
    constraints: tuple[RigConstraint, ...] = ()
    rest_pose_units: str = "cm"
    handedness: str = "right"
    """``right`` (glTF, USD) | ``left`` (FBX Maya / Unreal default)."""


__all__ = [
    "RIG_IR_VERSION",
    "RigBone",
    "RigConstraint",
    "RigIR",
    "SkeletonHierarchy",
]
