"""Foundry generators — per-family deterministic asset builders.

Each generator turns a parameter set into a typed Foundry-asset
container (mesh data + zones + sockets + collision spec + material
slots + style binding + diagnostics) that the runtime cooker and
package writer consume.

Generators are pure Python. They MUST be deterministic given a seed,
and they MUST emit no real geometry beyond what the parameters
authorize. No fake-quality (per masterplan §3).

MVP set (per masterplan §15.4 Golden Asset Set):
  - VioletCrystalCluster (generators/crystal_cluster.py)
  - AlpinePine (generators/pine_tree.py)
  - StonePathSegment (generators/stone_path.py)
  - LanternPost (generators/lantern.py)
  - RopeBridge (generators/bridge.py)
  - CozyCottage (generators/cottage.py)
  - FloatingIslandSmall (generators/floating_island.py)
"""

from __future__ import annotations

from ._base import (
    GENERATOR_BASE_VERSION,
    FoundryAsset,
    GeneratorSpec,
    SemanticSocket,
)
from .bridge import RopeBridgeParameters, build_rope_bridge
from .cottage import CozyCottageParameters, build_cozy_cottage
from .crystal_cluster import build_violet_crystal_cluster
from .floating_island import (
    FloatingIslandParameters,
    build_floating_island_small,
)
from .lantern import LanternPostParameters, build_lantern_post
from .pine_tree import AlpinePineParameters, build_alpine_pine
from .stone_path import StonePathParameters, build_stone_path_segment

__all__ = [
    "GENERATOR_BASE_VERSION",
    "FoundryAsset",
    "GeneratorSpec",
    "SemanticSocket",
    # MVP generators
    "RopeBridgeParameters",
    "CozyCottageParameters",
    "FloatingIslandParameters",
    "LanternPostParameters",
    "AlpinePineParameters",
    "StonePathParameters",
    "build_alpine_pine",
    "build_cozy_cottage",
    "build_floating_island_small",
    "build_lantern_post",
    "build_rope_bridge",
    "build_stone_path_segment",
    "build_violet_crystal_cluster",
]
