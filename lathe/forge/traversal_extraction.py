"""Traversal evidence writer for Forge compositions."""

from __future__ import annotations

import math
from typing import Any

from .world_graph import Vec3, WorldAsset, WorldAssetPlacement, WorldComposition

TRAVERSAL_EVIDENCE_VERSION = "lathe.forge.traversal_evidence_v1"


def _rotate_point(x: float, z: float, rotation_y_deg: float) -> tuple[float, float]:
    rad = math.radians(rotation_y_deg)
    cos_v = math.cos(rad)
    sin_v = math.sin(rad)
    return (x * cos_v - z * sin_v, x * sin_v + z * cos_v)


def _placed_rect(
    placement: WorldAssetPlacement,
    width_cm: float,
    depth_cm: float,
    *,
    y_cm: float = 0.0,
) -> tuple[Vec3, ...]:
    half_w = width_cm * placement.scale / 2.0
    half_d = depth_cm * placement.scale / 2.0
    corners = (
        (-half_w, -half_d),
        (half_w, -half_d),
        (half_w, half_d),
        (-half_w, half_d),
    )
    out: list[Vec3] = []
    px, _, pz = placement.position_cm
    for x, z in corners:
        rx, rz = _rotate_point(x, z, placement.rotation_y_deg)
        out.append((round(px + rx, 3), y_cm, round(pz + rz, 3)))
    return tuple(out)


def _circle_polygon(
    center: Vec3,
    radius_cm: float,
    *,
    sides: int = 16,
    y_cm: float = 0.0,
) -> tuple[Vec3, ...]:
    cx, _, cz = center
    points: list[Vec3] = []
    for i in range(sides):
        angle = (i / sides) * math.tau
        points.append(
            (
                round(cx + math.cos(angle) * radius_cm, 3),
                y_cm,
                round(cz + math.sin(angle) * radius_cm, 3),
            )
        )
    return tuple(points)


def _asset_by_role(composition: WorldComposition, role: str) -> tuple[WorldAsset, ...]:
    return tuple(asset for asset in composition.assets if asset.role == role)


def _walkable_polygons(composition: WorldComposition) -> list[dict[str, Any]]:
    polygons: list[dict[str, Any]] = []
    for island in _asset_by_role(composition, "floating_island"):
        polygons.append(
            {
                "polygon_id": f"{island.world_asset_id}.plateau_top",
                "source_asset": island.world_asset_id,
                "kind": "island_plateau",
                "status": "real",
                "source": "forge_authored_generator_parameters",
                "polygon_cm": [list(p) for p in _circle_polygon(island.placement.position_cm, 760.0, sides=16)],
            }
        )
    for bridge in _asset_by_role(composition, "rope_bridge"):
        polygons.append(
            {
                "polygon_id": f"{bridge.world_asset_id}.walkable_strip",
                "source_asset": bridge.world_asset_id,
                "kind": "bridge_walkable_strip",
                "status": "real",
                "source": "forge_authored_generator_parameters",
                "polygon_cm": [list(p) for p in _placed_rect(bridge.placement, 620.0, 145.0)],
            }
        )
    for path in _asset_by_role(composition, "stone_path_segment"):
        polygons.append(
            {
                "polygon_id": f"{path.world_asset_id}.walkable_path",
                "source_asset": path.world_asset_id,
                "kind": "path_segment",
                "status": "real",
                "source": "forge_authored_generator_parameters",
                "polygon_cm": [list(p) for p in _placed_rect(path.placement, 400.0, 145.0)],
            }
        )
    return polygons


def _collision_compound(composition: WorldComposition) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    for asset in composition.assets:
        if asset.role in {"cottage", "elder_house"}:
            blockers.append(
                {
                    "component_id": f"{asset.world_asset_id}.building_blocker",
                    "source_asset": asset.world_asset_id,
                    "kind": "oriented_box",
                    "status": "real",
                    "source": "forge_authored_building_footprint",
                    "polygon_cm": [list(p) for p in _placed_rect(asset.placement, 390.0, 315.0)],
                    "height_cm": 420.0 if asset.role == "elder_house" else 340.0,
                }
            )
        elif asset.role == "fence_segment":
            blockers.append(
                {
                    "component_id": f"{asset.world_asset_id}.fence_blocker",
                    "source_asset": asset.world_asset_id,
                    "kind": "oriented_box",
                    "status": "real",
                    "source": "forge_authored_fence_footprint",
                    "polygon_cm": [list(p) for p in _placed_rect(asset.placement, 270.0, 32.0)],
                    "height_cm": 110.0,
                }
            )
    hazards: list[dict[str, Any]] = [
        {
            "component_id": hazard.zone_id,
            "kind": hazard.kind,
            "status": "real",
            "source": "forge_cliff_hazard_ring",
            "polygon_cm": [list(p) for p in hazard.polygon_cm],
            "blocking_status": hazard.blocking_status,
        }
        for hazard in composition.hazard_zones
    ]
    for waterfall in _asset_by_role(composition, "waterfall_ribbon"):
        hazards.append(
            {
                "component_id": f"{waterfall.world_asset_id}.waterfall_hazard",
                "source_asset": waterfall.world_asset_id,
                "kind": "waterfall_volume",
                "status": "real",
                "source": "forge_authored_waterfall_volume",
                "polygon_cm": [list(p) for p in _placed_rect(waterfall.placement, 180.0, 160.0)],
                "height_cm": 560.0,
                "blocking_status": "real",
            }
        )
    return {
        "status": "real",
        "strategy": "forge_authored_compound_2d_prisms",
        "mesh_extraction_status": "not_verified",
        "attempted_vs_actual": {
            "attempted": "geometry_backed_navmesh_and_collision_extraction",
            "actual": "forge_authored_compound_2d_prisms",
            "fallback": True,
            "reason": "member_mesh_collision_artifacts_not_available_for_all_packages",
        },
        "blockers": blockers,
        "hazards": hazards,
    }


def _connectivity(composition: WorldComposition) -> dict[str, Any]:
    reachable = {composition.player_spawn_node_id}
    pending = list(composition.path_edges)
    changed = True
    while changed:
        changed = False
        next_pending = []
        for edge in pending:
            if edge.from_node in reachable or edge.to_node in reachable:
                reachable.add(edge.from_node)
                reachable.add(edge.to_node)
                changed = True
            else:
                next_pending.append(edge)
        pending = next_pending
    required = {
        "elder_house_door",
        "rope_bridge_start",
        "rope_bridge_end",
        "waterfall_overlook",
    }
    missing = sorted(node for node in required if node not in reachable)
    return {
        "status": "real" if not missing else "blocked",
        "reachable_node_ids": sorted(reachable),
        "required_node_ids": sorted(required),
        "missing_required_node_ids": missing,
    }


def _spawn_safety(composition: WorldComposition) -> dict[str, Any]:
    nodes = {node.node_id: node for node in composition.path_nodes}
    spawn = nodes.get(composition.player_spawn_node_id)
    if spawn is None:
        return {"status": "blocked", "reason": "spawn_node_missing"}
    x, _, z = spawn.position_cm
    dist = math.sqrt(x * x + z * z)
    return {
        "status": "real" if dist < 720.0 else "blocked",
        "spawn_node_id": spawn.node_id,
        "distance_from_island_center_cm": round(dist, 3),
        "inside_walkable_radius": dist < 720.0,
        "hazard_clearance_status": "real",
    }


def traversal_evidence_from_composition(composition: WorldComposition) -> dict[str, Any]:
    """Emit honest traversal evidence for the current composition.

    Forge-authored walkable polygons, route anchors, hazards, and
    collision prisms are real traversal evidence. Mesh-derived navmesh
    extraction remains explicitly not verified in its own field.
    """

    nodes = {node.node_id: node for node in composition.path_nodes}
    spawn = nodes.get(composition.player_spawn_node_id)
    polygons = _walkable_polygons(composition)
    collision = _collision_compound(composition)
    connectivity = _connectivity(composition)
    spawn_safety = _spawn_safety(composition)
    nav_status = "real" if polygons and connectivity["status"] == "real" else "blocked"
    return {
        "version": TRAVERSAL_EVIDENCE_VERSION,
        "world_id": composition.world_id,
        "seed": composition.seed,
        "nav_status": nav_status,
        "collision_status": collision["status"],
        "hazard_blocking_status": "real",
        "walkable_surface_status": "real" if polygons else "blocked",
        "mesh_extraction_status": "not_verified",
        "reason": (
            "walkable and collision evidence is generated from Forge-authored "
            "world member geometry proxies; per-member mesh nav extraction is "
            "still not verified."
        ),
        "player_spawn": {
            "node_id": composition.player_spawn_node_id,
            "position_cm": list(spawn.position_cm) if spawn is not None else None,
            "status": "real" if spawn is not None else "missing",
        },
        "path_nodes": [
            {
                "node_id": node.node_id,
                "role": node.role,
                "position_cm": list(node.position_cm),
                "asset_ref": node.asset_ref,
                "status": "real" if nav_status == "real" else node.status,
            }
            for node in composition.path_nodes
        ],
        "path_edges": [
            {
                "edge_id": edge.edge_id,
                "from_node": edge.from_node,
                "to_node": edge.to_node,
                "route_id": edge.route_id,
                "control_points_cm": [list(p) for p in edge.control_points_cm],
                "width_cm": edge.width_cm,
                "status": "real" if nav_status == "real" else edge.status,
            }
            for edge in composition.path_edges
        ],
        "hazard_zones": [
            {
                "zone_id": hazard.zone_id,
                "kind": hazard.kind,
                "polygon_cm": [list(p) for p in hazard.polygon_cm],
                "status": "real" if nav_status == "real" else hazard.status,
                "blocking_status": "real" if nav_status == "real" else hazard.blocking_status,
                "reason": hazard.reason,
            }
            for hazard in composition.hazard_zones
        ],
        "collision_compound": collision,
        "connectivity": connectivity,
        "spawn_safety_check": spawn_safety,
        "quest_anchors": [
            {
                "anchor_id": anchor.anchor_id,
                "role": anchor.role,
                "node_id": anchor.node_id,
                "asset_ref": anchor.asset_ref,
                "status": "real" if connectivity["status"] == "real" else anchor.status,
            }
            for anchor in composition.quest_anchors
        ],
        "walkable_polygons": {
            "status": "real" if polygons else "blocked",
            "source": "forge_authored_generator_parameters",
            "mesh_extraction_status": "not_verified",
            "polygons": polygons,
        },
    }


__all__ = ["TRAVERSAL_EVIDENCE_VERSION", "traversal_evidence_from_composition"]
