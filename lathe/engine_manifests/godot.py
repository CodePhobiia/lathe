"""Godot engine manifest adapter (STAGE-10).

Emits ``<asset>.lathe_for_godot.json``. Godot's glTF importer picks up the
glb + collision meshes directly; this sidecar tells the downstream
EditorImportPlugin how to wire them into a Node3D hierarchy:

  - An outer ``Node3D`` root (tagged with ``gameplay_tags``)
  - A ``LODGroup`` (via ``visibility_range_begin/end`` metadata per LOD) wrapping
    the LOD ``MeshInstance3D`` nodes that point at ``lod_{0..3}.glb``
  - ``Marker3D``-style socket nodes (Position3D pattern) carrying ``anchor_id``
    and ``socket_type`` in the ``meta`` dict, one per declared socket
  - A ``StaticBody3D`` whose ``shape`` child references ``collision_hull.glb`` and
    a ``CollisionShape3D`` array for per-part hulls (``collision_parts.glb``)

Keeping the JSON deliberately minimal (plain scene-graph facts) — the
EditorImportPlugin does the actual Node construction.
"""

from __future__ import annotations

import json
from typing import Any


def emit_godot_manifest(context: dict[str, Any], asset_name: str) -> str:
    """Build the Godot sidecar JSON as a string (caller writes to disk)."""

    root: dict[str, Any] = {
        "schemaVersion": 1,
        "engine": "godot",
        "engineVersion": ">=4.2",
        "assetName": asset_name,
        "rootNode": {
            "type": "Node3D",
            "name": asset_name,
            "meta": {
                "gameplay_tags": list(context.get("gameplay_tags", [])),
            },
        },
        "lodGroup": _lod_nodes(context),
        "sockets": _socket_nodes(context),
        "pivots": _pivot_nodes(context),
        "collision": _collision_nodes(context),
        "materials": [
            {"id": mat.get("id"), "displayName": mat.get("display_name") or mat.get("id")}
            for mat in context.get("materials", [])
            if isinstance(mat, dict) and mat.get("id")
        ],
    }
    return json.dumps(root, indent=2, sort_keys=False)


def _lod_nodes(context: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for lod in context.get("lods", []):
        if not isinstance(lod, dict):
            continue
        nodes.append(
            {
                "type": "MeshInstance3D",
                "name": f"LOD{lod.get('level', 0)}",
                "meshUri": lod.get("mesh_uri"),
                "visibilityRangeBegin": float(lod.get("distance_min", 0.0) or 0.0),
                "visibilityRangeEnd": (
                    None
                    if lod.get("distance_max") is None
                    else float(lod.get("distance_max"))
                ),
                "screenCoverage": (
                    None
                    if lod.get("screen_coverage") is None
                    else float(lod.get("screen_coverage"))
                ),
                "triangleCount": int(lod.get("triangle_count") or 0),
            }
        )
    return nodes


def _socket_nodes(context: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sock in context.get("sockets", []):
        if not isinstance(sock, dict) or not sock.get("id"):
            continue
        out.append(
            {
                "type": "Marker3D",
                "name": f"socket_{sock['id']}",
                "origin": list(sock.get("origin", [0.0, 0.0, 0.0])),
                "axis": list(sock.get("axis", [0.0, 1.0, 0.0])),
                "meta": {
                    "anchor_id": sock["id"],
                    "socket_type": sock.get("socket_type") or sock.get("kind") or "attach",
                    "parent_part_id": sock.get("parent_part_id"),
                },
            }
        )
    return out


def _pivot_nodes(context: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for piv in context.get("pivots", []):
        if not isinstance(piv, dict) or not piv.get("id"):
            continue
        out.append(
            {
                "type": "Marker3D",
                "name": f"pivot_{piv['id']}",
                "origin": list(piv.get("origin", [0.0, 0.0, 0.0])),
                "axis": list(piv.get("axis", [0.0, 1.0, 0.0])),
                "meta": {
                    "anchor_id": piv["id"],
                    "pivot_type": piv.get("pivot_type") or "center",
                },
            }
        )
    return out


def _collision_nodes(context: dict[str, Any]) -> dict[str, Any]:
    collisions = context.get("collisions", [])
    shapes: list[dict[str, Any]] = []
    for col in collisions:
        if not isinstance(col, dict):
            continue
        shapes.append(
            {
                "type": "CollisionShape3D",
                "name": f"shape_{col.get('id', 'hull')}",
                "shape": col.get("kind", "hull"),
                "meshUri": col.get("uri"),
                "parentPartId": col.get("parent_part_id"),
            }
        )
    return {
        "type": "StaticBody3D",
        "name": "collision",
        "shapes": shapes,
    }
