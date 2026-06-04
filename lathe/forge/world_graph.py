"""Typed world graph contract for Lathe Forge.

Forge composes asset packages into an inspectable world artifact. This
module intentionally stays geometry-light: it records placement,
semantic role, traversal anchors, and evidence status without claiming
that collision/nav/render evidence exists before downstream stages
actually produce it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

LTH_FORGE_VERSION = "lathe.forge.world_graph_v1"

Vec3 = tuple[float, float, float]


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _json_ready(value[k]) for k in sorted(value)}
    if isinstance(value, tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


@dataclass(frozen=True)
class StyleContext:
    """World-level style binding propagated to every member asset."""

    style_pack_id: str
    kit_id: str
    director_terms: tuple[str, ...] = ()
    material_palette_id: str = ""


@dataclass(frozen=True)
class WorldAssetPlacement:
    """Deterministic placement for one asset instance."""

    position_cm: Vec3
    rotation_y_deg: float = 0.0
    scale: float = 1.0
    zone_id: str = ""
    anchor_id: str = ""
    socket_ref: str = ""


@dataclass(frozen=True)
class WorldAsset:
    """One world-member asset slot.

    ``package_status`` remains ``planned`` until a real ``.lthpkg`` is
    written or linked for the asset.
    """

    world_asset_id: str
    role: str
    family: str
    generator_id: str
    asset_id: str
    style_pack_id: str
    seed: int
    placement: WorldAssetPlacement
    package_ref: str = ""
    package_status: str = "planned"
    evidence_status: Mapping[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PathGraphNode:
    """Semantic traversal anchor in world space."""

    node_id: str
    role: str
    position_cm: Vec3
    asset_ref: str = ""
    status: str = "planned"


@dataclass(frozen=True)
class PathGraphEdge:
    """Planned path segment between two anchors."""

    edge_id: str
    from_node: str
    to_node: str
    route_id: str
    control_points_cm: tuple[Vec3, ...] = ()
    status: str = "planned"
    width_cm: float = 180.0


@dataclass(frozen=True)
class HazardZone:
    """World-space hazard or blocking region."""

    zone_id: str
    kind: str
    polygon_cm: tuple[Vec3, ...]
    status: str = "planned"
    blocking_status: str = "planned"
    reason: str = ""


@dataclass(frozen=True)
class QuestAnchor:
    """Inspectable world objective marker."""

    anchor_id: str
    role: str
    node_id: str
    asset_ref: str
    status: str = "planned"


@dataclass(frozen=True)
class WorldComposition:
    """A deterministic Forge world composition."""

    world_id: str
    prompt: str
    seed: int
    style: StyleContext
    assets: tuple[WorldAsset, ...]
    path_nodes: tuple[PathGraphNode, ...] = ()
    path_edges: tuple[PathGraphEdge, ...] = ()
    hazard_zones: tuple[HazardZone, ...] = ()
    quest_anchors: tuple[QuestAnchor, ...] = ()
    player_spawn_node_id: str = "village_square"
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    version: str = LTH_FORGE_VERSION

    def asset_count(self) -> int:
        return len(self.assets)

    def role_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(asset.role for asset in self.assets).items()))

    def style_pack_ids(self) -> tuple[str, ...]:
        return tuple(sorted({asset.style_pack_id for asset in self.assets}))

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": self.version,
            "world_id": self.world_id,
            "prompt": self.prompt,
            "seed": self.seed,
            "style": self.style,
            "asset_count": self.asset_count(),
            "role_counts": self.role_counts(),
            "style_pack_ids": self.style_pack_ids(),
            "assets": self.assets,
            "path_nodes": self.path_nodes,
            "path_edges": self.path_edges,
            "hazard_zones": self.hazard_zones,
            "quest_anchors": self.quest_anchors,
            "player_spawn_node_id": self.player_spawn_node_id,
            "diagnostics": self.diagnostics,
        }
        return _json_ready(payload)


__all__ = [
    "LTH_FORGE_VERSION",
    "Vec3",
    "StyleContext",
    "WorldAsset",
    "WorldAssetPlacement",
    "WorldComposition",
    "PathGraphNode",
    "PathGraphEdge",
    "HazardZone",
    "QuestAnchor",
]
