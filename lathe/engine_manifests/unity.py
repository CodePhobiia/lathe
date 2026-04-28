"""Unity engine manifest adapter (STAGE-10).

Emits ``<asset>.lathe_for_unity.yaml``. Unity's GLTFast/UnityGLTF importers
consume the glb directly; this sidecar describes the LODGroup component and
Transform hierarchy the downstream ScriptedImporter should construct:

  - A root ``GameObject`` with ``tags`` on the Unity ``Tag`` / ``Label`` system
  - A ``LODGroup`` component with per-LOD ``screenRelativeTransitionHeight``
    and the mesh reference for each LOD
  - Empty ``GameObject`` nodes for each socket/pivot (Unity attachment convention)
  - ``MeshCollider`` entries for ``collision_hull.glb`` and per-part hulls

The YAML is hand-formatted (no third-party yaml dependency required in the
core package) to keep the adapter self-contained.
"""

from __future__ import annotations

from typing import Any


def emit_unity_manifest(context: dict[str, Any], asset_name: str) -> str:
    """Build the Unity sidecar YAML as a string (caller writes to disk)."""
    lines: list[str] = []
    lines.append("%YAML 1.1")
    lines.append("# Lathe Unity import manifest (schemaVersion 1)")
    lines.append("schemaVersion: 1")
    lines.append("engine: unity")
    lines.append('engineVersion: ">=2022.3"')
    lines.append(f"assetName: {asset_name}")
    lines.append("rootGameObject:")
    lines.append(f"  name: {asset_name}")
    tags = list(context.get("gameplay_tags", []))
    lines.append("  tags:")
    for tag in tags:
        lines.append(f"    - {tag}")
    lines.append("  components:")
    lines.append("    - type: LODGroup")
    lines.append("      lods:")
    for lod in context.get("lods", []):
        if not isinstance(lod, dict):
            continue
        coverage = lod.get("screen_coverage")
        if coverage is None:
            coverage = 0.0
        lines.append(f"        - level: {int(lod.get('level', 0))}")
        lines.append(f"          meshUri: {lod.get('mesh_uri')}")
        lines.append(f"          screenRelativeTransitionHeight: {float(coverage):.4f}")
        lines.append(f"          distanceMin: {float(lod.get('distance_min', 0.0) or 0.0):.3f}")
        dist_max = lod.get("distance_max")
        if dist_max is None:
            lines.append("          distanceMax: ~")
        else:
            lines.append(f"          distanceMax: {float(dist_max):.3f}")
        lines.append(f"          triangleCount: {int(lod.get('triangle_count') or 0)}")
    # Sockets
    lines.append("  sockets:")
    for sock in context.get("sockets", []):
        if not isinstance(sock, dict) or not sock.get("id"):
            continue
        lines.append(f"    - name: socket_{sock['id']}")
        lines.append(f"      anchorId: {sock['id']}")
        lines.append(f"      socketType: {sock.get('socket_type') or sock.get('kind') or 'attach'}")
        origin = list(sock.get("origin", [0.0, 0.0, 0.0]))
        lines.append(f"      origin: [{origin[0]}, {origin[1]}, {origin[2]}]")
        axis = list(sock.get("axis", [0.0, 1.0, 0.0]))
        lines.append(f"      axis: [{axis[0]}, {axis[1]}, {axis[2]}]")
        parent = sock.get("parent_part_id")
        if parent:
            lines.append(f"      parentPartId: {parent}")
    # Pivots
    lines.append("  pivots:")
    for piv in context.get("pivots", []):
        if not isinstance(piv, dict) or not piv.get("id"):
            continue
        lines.append(f"    - name: pivot_{piv['id']}")
        lines.append(f"      anchorId: {piv['id']}")
        lines.append(f"      pivotType: {piv.get('pivot_type') or 'center'}")
        origin = list(piv.get("origin", [0.0, 0.0, 0.0]))
        lines.append(f"      origin: [{origin[0]}, {origin[1]}, {origin[2]}]")
    # Collisions
    lines.append("  collision:")
    for col in context.get("collisions", []):
        if not isinstance(col, dict):
            continue
        lines.append(f"    - id: {col.get('id', 'hull')}")
        lines.append(f"      kind: {col.get('kind', 'hull')}")
        lines.append(f"      meshUri: {col.get('uri')}")
        parent = col.get("parent_part_id")
        if parent:
            lines.append(f"      parentPartId: {parent}")
    # Materials
    lines.append("  materials:")
    for mat in context.get("materials", []):
        if not isinstance(mat, dict) or not mat.get("id"):
            continue
        lines.append(f"    - id: {mat['id']}")
        display = mat.get("display_name") or mat["id"]
        lines.append(f'      displayName: "{display}"')
    return "\n".join(lines) + "\n"
