"""Unreal engine manifest adapter (STAGE-10).

Emits ``<asset>.lathe_for_unreal.json``. Unreal's Interchange glTF importer
consumes the glb directly; this sidecar describes the Actor class scaffold
the downstream editor utility should spawn:

  - ``ActorClass``: ``AActor`` with a ``USceneComponent`` root
  - Per-LOD ``UStaticMeshComponent`` entries with ``MinDrawDistance`` /
    ``LDMaxDrawDistance`` mirroring the distance bands
  - ``UArrowComponent`` / named ``FTransform`` sockets per socket declaration,
    with the socket type stored in the component's ``Tags`` array
  - ``UBodySetup`` aggregation for collision: one convex hull from
    ``collision_hull.glb`` and per-part hulls from ``collision_parts.glb``
  - ``GameplayTagContainer`` carrying the asset's declared gameplay tags
"""

from __future__ import annotations

import json
from typing import Any


def emit_unreal_manifest(context: dict[str, Any], asset_name: str) -> str:
    """Build the Unreal sidecar JSON as a string (caller writes to disk)."""
    root: dict[str, Any] = {
        "schemaVersion": 1,
        "engine": "unreal",
        "engineVersion": ">=5.3",
        "assetName": asset_name,
        "actor": {
            "class": "AActor",
            "name": asset_name,
            "gameplayTags": list(context.get("gameplay_tags", [])),
            "components": _build_components(context),
        },
        "materials": [
            {"id": mat.get("id"), "displayName": mat.get("display_name") or mat.get("id")}
            for mat in context.get("materials", [])
            if isinstance(mat, dict) and mat.get("id")
        ],
    }
    return json.dumps(root, indent=2, sort_keys=False)


def _build_components(context: dict[str, Any]) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = [
        {"class": "USceneComponent", "name": "Root"},
    ]
    for lod in context.get("lods", []):
        if not isinstance(lod, dict):
            continue
        components.append(
            {
                "class": "UStaticMeshComponent",
                "name": f"LOD{int(lod.get('level', 0))}",
                "meshUri": lod.get("mesh_uri"),
                "minDrawDistance": float(lod.get("distance_min", 0.0) or 0.0),
                "ldMaxDrawDistance": (
                    -1.0 if lod.get("distance_max") is None else float(lod.get("distance_max"))
                ),
                "screenSize": (
                    None if lod.get("screen_coverage") is None else float(lod.get("screen_coverage"))
                ),
                "triangleCount": int(lod.get("triangle_count") or 0),
            }
        )
    for sock in context.get("sockets", []):
        if not isinstance(sock, dict) or not sock.get("id"):
            continue
        components.append(
            {
                "class": "UArrowComponent",
                "name": f"socket_{sock['id']}",
                "socketName": sock["id"],
                "relativeLocation": list(sock.get("origin", [0.0, 0.0, 0.0])),
                "arrowDirection": list(sock.get("axis", [0.0, 1.0, 0.0])),
                "tags": [
                    f"anchor:{sock['id']}",
                    f"socket_type:{sock.get('socket_type') or sock.get('kind') or 'attach'}",
                ],
                "parentPartId": sock.get("parent_part_id"),
            }
        )
    for piv in context.get("pivots", []):
        if not isinstance(piv, dict) or not piv.get("id"):
            continue
        components.append(
            {
                "class": "UArrowComponent",
                "name": f"pivot_{piv['id']}",
                "socketName": piv["id"],
                "relativeLocation": list(piv.get("origin", [0.0, 0.0, 0.0])),
                "arrowDirection": list(piv.get("axis", [0.0, 1.0, 0.0])),
                "tags": [
                    f"anchor:{piv['id']}",
                    f"pivot_type:{piv.get('pivot_type') or 'center'}",
                ],
            }
        )
    for col in context.get("collisions", []):
        if not isinstance(col, dict):
            continue
        components.append(
            {
                "class": "UBodySetup",
                "name": f"body_{col.get('id', 'hull')}",
                "shape": col.get("kind", "hull"),
                "meshUri": col.get("uri"),
                "parentPartId": col.get("parent_part_id"),
            }
        )
    return components
