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

The ``latheRuntimeSemantics`` block carries the Lathe runtime_semantics_v1
contract using camelCase + FName-compatible string keys
(``activeSystems``, ``runtimeSemanticsVersion``, etc.). The companion
``<asset>.lathe_runtime.json`` content is duplicated inline as the
``latheRuntimeSemantics`` field so a single sidecar covers both the actor
scaffold and the runtime tag manifest.

Ingestion path: an editor-utility Blueprint or a C++
``UAssetUserData`` / ``FAssetRegistryTagsContext`` helper reads the JSON
and writes the runtime_semantics fields back as ``FAssetData`` tags on the
imported ``UStaticMesh`` so cooked builds can query active systems without
shipping the JSON. (Reference: ``UObject::GetAssetRegistryTags``.)
"""

from __future__ import annotations

import json
from typing import Any

from ._runtime_semantics_compact import runtime_semantics_summary


def emit_unreal_manifest(context: dict[str, Any], asset_name: str) -> str:
    """Build the Unreal sidecar JSON as a string (caller writes to disk)."""
    semantics = runtime_semantics_summary(context.get("runtime_semantics"))
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
        "surfaceMaterialSemantics": context.get("surface_material_semantics") or {},
        "textures": list(context.get("textures") or []),
        "textureConventions": context.get("texture_conventions") or {},
        "latheConstructionProvenance": context.get("construction_provenance") or {},
        "latheRuntimeSemantics": _runtime_semantics_unreal(semantics),
    }
    return json.dumps(root, indent=2, sort_keys=False)


def _runtime_semantics_unreal(semantics: dict[str, Any] | None) -> dict[str, Any]:
    if semantics is None:
        return {}
    systems_out: list[dict[str, Any]] = []
    active_names: list[str] = []
    for system in semantics["systems"]:
        name = system["name"]
        if system["active"]:
            active_names.append(name)
        entry: dict[str, Any] = {
            "name": name,
            "fname": _fname(name),
            "active": system["active"],
            "activeFields": list(system["active_fields"]),
            "counts": dict(system["counts"]),
            "ids": {field: list(values) for field, values in system["ids"].items()},
        }
        if system["source"] is not None:
            entry["source"] = system["source"]
        if system["schema"] is not None:
            entry["irSchema"] = system["schema"]
        systems_out.append(entry)
    return {
        "runtimeSemanticsVersion": semantics["schema"],
        "activeSystems": active_names,
        "assetRegistryTags": _asset_registry_tags(active_names, systems_out),
        "systems": systems_out,
    }


def _fname(value: str) -> str:
    """Normalize a system name to an Unreal FName-compatible string.

    FNames are case-preserving but case-insensitive on lookup; they accept
    ASCII letters/digits/underscore. snake_case Lathe system names already
    satisfy that, so this is a guarded passthrough that strips anything
    that would force ``FName`` to mangle the value.
    """
    return "".join(
        ch if ch.isalnum() or ch == "_" else "_" for ch in value
    )


def _asset_registry_tags(
    active_names: list[str], systems: list[dict[str, Any]]
) -> dict[str, str]:
    """Compact ``FAssetRegistryTag`` shadow of the runtime_semantics block.

    Asset-registry tags must be flat ``FString`` values, so the per-system
    counts are joined into a single comma-separated tag and the active list
    is a single delimited string. The Blueprint helper described in the
    module docstring writes these as ``EAssetRegistryTagType::Hidden`` tags.
    """
    tags: dict[str, str] = {
        "Lathe.RuntimeSemantics.ActiveSystems": ",".join(active_names),
        "Lathe.RuntimeSemantics.SystemCount": str(len(active_names)),
    }
    for system in systems:
        if not system["active"]:
            continue
        name = system["name"]
        counts_summary = ",".join(
            f"{field}={count}" for field, count in system["counts"].items() if count > 0
        )
        if counts_summary:
            tags[f"Lathe.RuntimeSemantics.{_fname(name)}.Counts"] = counts_summary
    return tags


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
