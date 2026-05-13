"""Lathe runtime contract package.

Carries the target-aware metadata the engine adapters consume to
produce game-ready hierarchies (Roblox MeshParts + HingeConstraints,
Unity LODGroups + colliders, Unreal StaticMesh + sockets, USD variants
+ UsdPhysics, glTF nodes + MSFT_lod sidecar).
"""

from .asset_contract import (
    AssetRuntimeContract,
    CollisionPolicy,
    InterfacePort,
    LODEntry,
    RigJoint,
    SocketBinding,
    StreamingConfig,
)

__all__ = [
    "AssetRuntimeContract",
    "CollisionPolicy",
    "InterfacePort",
    "LODEntry",
    "RigJoint",
    "SocketBinding",
    "StreamingConfig",
]
