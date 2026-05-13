"""``lathe.runtime.asset_contract_v1`` — game-ready runtime metadata.

Per ``docs/research/newresearch.md`` §13: USD/glTF/OBJ packages are
not enough. Lathe needs target-aware metadata for LODs, materials,
colliders, interfaces, rigs, sockets, nav hints, audio emitters, light
probe anchors, streaming groups, and engine adapters.

The runtime_metadata stage (which lives between validate and package)
produces an ``AssetRuntimeContract``. Per-engine adapters (Roblox,
Unity, Unreal, USD, glTF) lower the contract into their native
representations during package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.runtime.asset_contract_v1"


@dataclass(frozen=True)
class LODEntry:
    """One LOD level — path to the LOD's GLB + budget + selection distance."""

    lod_id: str
    glb_path: str
    target_tris: int
    screen_size_threshold: float = 0.0  # 0 = farthest LOD
    representation: str = "geometry"  # geometry | normal_baked | proxy | impostor


@dataclass(frozen=True)
class CollisionPolicy:
    """Per-asset collision recipe."""

    type: str = "compound"  # box | convex | compound | mesh | none
    parts: tuple[Mapping[str, Any], ...] = ()
    mass_kg: float = 1.0
    material: str = "default"
    enabled: bool = True


@dataclass(frozen=True)
class RigJoint:
    """One rigid-constraint joint between two named parts."""

    joint_id: str
    type: str  # hinge | slider | fixed | ball
    parent_part: str
    child_part: str
    pivot_world_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis_world: tuple[float, float, float] = (0.0, 0.0, 1.0)
    limits_deg: tuple[float, float] = (-180.0, 180.0)
    default_angle_deg: float = 0.0
    motorized: bool = False


@dataclass(frozen=True)
class SocketBinding:
    """Engine-side attachment / socket point."""

    socket_id: str
    parent_part: str
    transform_world_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_euler_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    role: str = ""


@dataclass(frozen=True)
class InterfacePort:
    """Asset-to-asset attachment port (KitGraph docking)."""

    interface_id: str
    kind: str  # support_footprint | stack_receive | hinge_attach | latch_target
    frame_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_cm: tuple[float, float, float] = (10.0, 10.0, 10.0)
    snap_points: tuple[str, ...] = ()
    load_capacity_kg: float = 0.0
    texel_density: float = 512.0
    material_transition: str = "allow_contact_shadow"
    collision_policy: str = "compound_hull"


@dataclass(frozen=True)
class StreamingConfig:
    """Asset streaming hints for engine packers."""

    chunk: str = "default"
    memory_budget_mb: float = 16.0
    priority: int = 0
    cull_distance_m: float = 200.0


@dataclass(frozen=True)
class AssetRuntimeContract:
    """The full target-aware runtime contract for one published asset."""

    asset_id: str
    lods: tuple[LODEntry, ...] = ()
    materials: tuple[str, ...] = ()
    texture_sets: tuple[str, ...] = ()
    collision: CollisionPolicy = field(default_factory=CollisionPolicy)
    joints: tuple[RigJoint, ...] = ()
    sockets: tuple[SocketBinding, ...] = ()
    interfaces: tuple[InterfacePort, ...] = ()
    nav_hints: Mapping[str, Any] = field(default_factory=dict)
    audio_emitters: tuple[Mapping[str, Any], ...] = ()
    light_probe_anchors: tuple[Mapping[str, Any], ...] = ()
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    semantic_tags: tuple[str, ...] = ()
    runtime_params: Mapping[str, Any] = field(default_factory=dict)
    engine_adapter_manifests: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "asset_id": self.asset_id,
            "lods": [
                {
                    "lod_id": l.lod_id,
                    "glb_path": l.glb_path,
                    "target_tris": l.target_tris,
                    "screen_size_threshold": l.screen_size_threshold,
                    "representation": l.representation,
                }
                for l in self.lods
            ],
            "materials": list(self.materials),
            "texture_sets": list(self.texture_sets),
            "collision": {
                "type": self.collision.type,
                "parts": [dict(p) for p in self.collision.parts],
                "mass_kg": self.collision.mass_kg,
                "material": self.collision.material,
                "enabled": self.collision.enabled,
            },
            "joints": [
                {
                    "joint_id": j.joint_id,
                    "type": j.type,
                    "parent_part": j.parent_part,
                    "child_part": j.child_part,
                    "pivot_world_cm": list(j.pivot_world_cm),
                    "axis_world": list(j.axis_world),
                    "limits_deg": list(j.limits_deg),
                    "default_angle_deg": j.default_angle_deg,
                    "motorized": j.motorized,
                }
                for j in self.joints
            ],
            "sockets": [
                {
                    "socket_id": s.socket_id,
                    "parent_part": s.parent_part,
                    "transform_world_cm": list(s.transform_world_cm),
                    "rotation_euler_deg": list(s.rotation_euler_deg),
                    "role": s.role,
                }
                for s in self.sockets
            ],
            "interfaces": [
                {
                    "interface_id": i.interface_id,
                    "kind": i.kind,
                    "frame_cm": list(i.frame_cm),
                    "bounds_cm": list(i.bounds_cm),
                    "snap_points": list(i.snap_points),
                    "load_capacity_kg": i.load_capacity_kg,
                    "texel_density": i.texel_density,
                    "material_transition": i.material_transition,
                    "collision_policy": i.collision_policy,
                }
                for i in self.interfaces
            ],
            "nav_hints": dict(self.nav_hints),
            "audio_emitters": [dict(a) for a in self.audio_emitters],
            "light_probe_anchors": [dict(l) for l in self.light_probe_anchors],
            "streaming": {
                "chunk": self.streaming.chunk,
                "memory_budget_mb": self.streaming.memory_budget_mb,
                "priority": self.streaming.priority,
                "cull_distance_m": self.streaming.cull_distance_m,
            },
            "semantic_tags": list(self.semantic_tags),
            "runtime_params": dict(self.runtime_params),
            "engine_adapter_manifests": {
                k: dict(v) for k, v in self.engine_adapter_manifests.items()
            },
        }


__all__ = [
    "CONTRACT_VERSION",
    "AssetRuntimeContract",
    "CollisionPolicy",
    "InterfacePort",
    "LODEntry",
    "RigJoint",
    "SocketBinding",
    "StreamingConfig",
]
