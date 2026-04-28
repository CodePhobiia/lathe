"""Mesh finalize: produce the authoritative downstream mesh.

Cleans, welds and normalizes fused geometry so topology, UV and
surface stages can assume a canonical manifold input.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .mesh_ir import MeshIR
from .shape_ir import ShapeIR


def finalize_mesh_ir(
    mesh: trimesh.Trimesh, shape_ir: ShapeIR, face_parts: list[str], *, metadata: dict[str, Any] | None = None
) -> MeshIR:
    """Finalize mesh ir.

    Args:
        mesh: mesh argument.
        shape_ir: shape_ir argument.
        face_parts: face_parts argument.
        metadata: metadata argument.

    Returns:
        The result.
    """
    face_parts = (
        list(face_parts)
        if len(face_parts) == len(mesh.faces)
        else [shape_ir.regions[0].part if shape_ir.regions else "mesh"] * len(mesh.faces)
    )
    seam_classes = [
        {"name": region.name, "part": region.part, "component": region.component, "tags": list(region.tags)}
        for region in shape_ir.regions
        if region.component in {"panel", "frame", "bezel", "door", "lid", "screen_bezel"}
    ]
    hard_edge_classes = [
        {
            "name": region.name,
            "part": region.part,
            "component": region.component,
            "sharp": region.component not in {"vent", "grille"},
        }
        for region in shape_ir.regions
    ]
    bake_groups = [
        {"name": region.name, "part": region.part, "component": region.component, "bake_group": region.part}
        for region in shape_ir.regions
    ]
    material_zones = []
    for region in shape_ir.regions:
        if region.component in {"screen_bezel", "panel", "bezel", "lock_plate", "socket_plate"}:
            material_zones.append(
                {"name": region.name, "part": region.part, "material_hint": region.component}
            )
    return MeshIR(
        asset_name=shape_ir.asset_name,
        family=shape_ir.family,
        vertices=np.asarray(mesh.vertices, dtype=np.float64).round(6).tolist(),
        faces=np.asarray(mesh.faces, dtype=np.int64).tolist(),
        face_parts=face_parts,
        material_zones=material_zones,
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
        bake_groups=bake_groups,
        metadata=metadata or {},
    )
