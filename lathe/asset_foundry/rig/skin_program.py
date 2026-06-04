"""Skin program — vertex-to-bone weights + per-vertex influence cap."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

SKIN_PROGRAM_VERSION = "lathe.asset_foundry.skin_program_v1"


@dataclass(frozen=True)
class VertexWeight:
    vertex_index: int
    bone_id: str
    weight: float


@dataclass(frozen=True)
class SkinBinding:
    """One mesh -> rig skin binding."""

    mesh_id: str
    rig_id: str
    weights: tuple[VertexWeight, ...]
    max_influences_per_vertex: int = 4
    """Engine convention: glTF + Roblox + Unreal use up to 4. Some
    Unity rigs use 8."""


@dataclass(frozen=True)
class SkinProgram:
    """Collection of skin bindings for one asset."""

    asset_id: str
    bindings: tuple[SkinBinding, ...]
    falloff_kind: str = "linear"
    """``linear`` | ``dual_quaternion`` | ``smooth``."""

    def total_influence_count(self) -> int:
        return sum(len(b.weights) for b in self.bindings)


def validate_skin_program(program: SkinProgram) -> tuple[str, ...]:
    """Return a tuple of diagnostic strings for skin-program issues."""
    diagnostics: list[str] = []
    for binding in program.bindings:
        per_vertex_influences: dict[int, list[VertexWeight]] = {}
        for vw in binding.weights:
            per_vertex_influences.setdefault(vw.vertex_index, []).append(vw)
        for vidx, ws in per_vertex_influences.items():
            if len(ws) > binding.max_influences_per_vertex:
                diagnostics.append(
                    f"skin_vertex_{vidx}_too_many_influences: {len(ws)} > {binding.max_influences_per_vertex}"
                )
            total_weight = sum(w.weight for w in ws)
            if total_weight < 0.95 or total_weight > 1.05:
                diagnostics.append(
                    f"skin_vertex_{vidx}_weight_sum_drift: {total_weight:.3f} not in [0.95, 1.05]"
                )
    return tuple(diagnostics)


__all__ = [
    "SKIN_PROGRAM_VERSION",
    "SkinBinding",
    "SkinProgram",
    "VertexWeight",
    "validate_skin_program",
]
