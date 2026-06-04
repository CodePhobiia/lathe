"""Deterministic path and hazard skeletons for Skyborne worlds."""

from __future__ import annotations

import math

from .world_graph import (
    HazardZone,
    PathGraphEdge,
    PathGraphNode,
    QuestAnchor,
    Vec3,
    WorldAsset,
)


def _asset_by_role(assets: tuple[WorldAsset, ...], role: str) -> tuple[WorldAsset, ...]:
    return tuple(asset for asset in assets if asset.role == role)


def _towards_square(position: Vec3, distance_cm: float = 80.0) -> Vec3:
    x, y, z = position
    length = math.sqrt(x * x + z * z)
    if length <= 0.001:
        return position
    return (
        x - (x / length) * distance_cm,
        y,
        z - (z / length) * distance_cm,
    )


def build_skyborne_path_graph(
    assets: tuple[WorldAsset, ...],
) -> tuple[tuple[PathGraphNode, ...], tuple[PathGraphEdge, ...]]:
    """Build planned traversal anchors from deterministic asset placements."""

    nodes: list[PathGraphNode] = [
        PathGraphNode(
            node_id="village_square",
            role="player_spawn",
            position_cm=(0.0, 0.0, 0.0),
            status="planned",
        )
    ]

    for index, asset in enumerate(_asset_by_role(assets, "cottage")):
        nodes.append(
            PathGraphNode(
                node_id=f"cottage_door_{index + 1:02d}",
                role="cottage_door",
                position_cm=_towards_square(asset.placement.position_cm),
                asset_ref=asset.world_asset_id,
                status="planned",
            )
        )

    elder_assets = _asset_by_role(assets, "elder_house")
    if elder_assets:
        elder = elder_assets[0]
        nodes.append(
            PathGraphNode(
                node_id="elder_house_door",
                role="quest_destination",
                position_cm=_towards_square(elder.placement.position_cm),
                asset_ref=elder.world_asset_id,
                status="planned",
            )
        )

    bridge_assets = _asset_by_role(assets, "rope_bridge")
    if bridge_assets:
        bridge = bridge_assets[0]
        x, y, z = bridge.placement.position_cm
        nodes.extend(
            [
                PathGraphNode(
                    node_id="rope_bridge_start",
                    role="bridge_endpoint",
                    position_cm=(x - 220.0, y, z),
                    asset_ref=bridge.world_asset_id,
                    status="planned",
                ),
                PathGraphNode(
                    node_id="rope_bridge_end",
                    role="bridge_endpoint",
                    position_cm=(x + 220.0, y, z),
                    asset_ref=bridge.world_asset_id,
                    status="planned",
                ),
            ]
        )

    waterfall_assets = _asset_by_role(assets, "waterfall_ribbon")
    if waterfall_assets:
        waterfall = waterfall_assets[0]
        nodes.append(
            PathGraphNode(
                node_id="waterfall_overlook",
                role="overlook",
                position_cm=_towards_square(waterfall.placement.position_cm, 140.0),
                asset_ref=waterfall.world_asset_id,
                status="planned",
            )
        )

    edges: list[PathGraphEdge] = []
    node_by_id = {node.node_id: node for node in nodes}
    for node in nodes:
        if node.node_id == "village_square":
            continue
        from_id = "village_square"
        to_id = node.node_id
        if node.node_id == "rope_bridge_end" and "rope_bridge_start" in node_by_id:
            from_id = "rope_bridge_start"
        start = node_by_id[from_id].position_cm
        end = node.position_cm
        mid = ((start[0] + end[0]) / 2.0, 0.0, (start[2] + end[2]) / 2.0)
        edges.append(
            PathGraphEdge(
                edge_id=f"path_{from_id}_to_{to_id}",
                from_node=from_id,
                to_node=to_id,
                route_id="main_village_loop",
                control_points_cm=(start, mid, end),
                status="planned",
            )
        )

    return tuple(nodes), tuple(edges)


def build_cliff_hazard_zones(radius_cm: float = 920.0) -> tuple[HazardZone, ...]:
    """Return planned hazard bands around the floating-island rim."""

    quadrants = (
        ("north_cliff_drop", -45.0, 45.0),
        ("east_cliff_drop", 45.0, 135.0),
        ("south_cliff_drop", 135.0, 225.0),
        ("west_cliff_drop", 225.0, 315.0),
    )
    hazards: list[HazardZone] = []
    for zone_id, start_deg, end_deg in quadrants:
        points: list[Vec3] = []
        for deg in (start_deg, (start_deg + end_deg) / 2.0, end_deg):
            rad = math.radians(deg)
            points.append((math.cos(rad) * radius_cm, 0.0, math.sin(rad) * radius_cm))
        hazards.append(
            HazardZone(
                zone_id=zone_id,
                kind="cliff_edge_drop",
                polygon_cm=tuple(points),
                status="planned",
                blocking_status="planned",
                reason="geometry_backed_cliff_collision_not_extracted_yet",
            )
        )
    return tuple(hazards)


def build_skyborne_quest_anchors(
    assets: tuple[WorldAsset, ...],
) -> tuple[QuestAnchor, ...]:
    elder_assets = _asset_by_role(assets, "elder_house")
    if not elder_assets:
        return ()
    return (
        QuestAnchor(
            anchor_id="elder_house_intro_marker",
            role="primary_quest_marker",
            node_id="elder_house_door",
            asset_ref=elder_assets[0].world_asset_id,
            status="planned",
        ),
    )


__all__ = [
    "build_cliff_hazard_zones",
    "build_skyborne_path_graph",
    "build_skyborne_quest_anchors",
]
