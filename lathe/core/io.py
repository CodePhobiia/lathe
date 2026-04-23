"""Mesh serialization: GLB, glTF, OBJ, and USDA writers.

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import trimesh

from .geometry import runtime_scene_parts
from .mesh import RuntimeMesh


def export_glb(mesh: trimesh.Trimesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = mesh.export(file_type="glb")
    path.write_bytes(blob)


def export_gltf(mesh: trimesh.Trimesh, directory: Path, asset_name: str) -> list[Path]:
    payload = mesh.export(file_type="gltf")
    written: list[Path] = []
    for name, data in payload.items():
        out_path = directory / name.replace("model", asset_name)
        if isinstance(data, str):
            out_path.write_text(data, encoding="utf-8")
        else:
            out_path.write_bytes(data)
        written.append(out_path)
    return written


def export_obj(mesh: trimesh.Trimesh, path: Path) -> None:
    text = mesh.export(file_type="obj")
    path.write_text(text, encoding="utf-8")
    mtl_path = path.with_name("material.mtl")
    if not mtl_path.exists():
        mtl_path.write_text("newmtl material_0\nKd 0.8 0.8 0.8\n", encoding="utf-8")


def export_runtime_scene_glb(runtime_mesh: RuntimeMesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    for part_name, submesh in runtime_scene_parts(runtime_mesh):
        scene.add_geometry(submesh, geom_name=part_name, node_name=part_name)
    path.write_bytes(scene.export(file_type="glb"))


def _vec3(values: Iterable[float]) -> str:
    coords = list(values)
    return f"({coords[0]:.6f}, {coords[1]:.6f}, {coords[2]:.6f})"


def write_usda(mesh: trimesh.Trimesh, path: Path, *, asset_name: str) -> None:
    points = ", ".join(f"({v[0]:.6f}, {v[1]:.6f}, {v[2]:.6f})" for v in mesh.vertices)
    counts = ", ".join("3" for _ in mesh.faces)
    indices = ", ".join(str(int(i)) for i in mesh.faces.reshape(-1))
    uv = None
    if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None:
        uv = mesh.visual.uv
    else:
        uv = np.zeros((len(mesh.vertices), 2), dtype=np.float64)
    st = ", ".join(f"({u:.6f}, {v:.6f})" for u, v in uv)
    st_indices = ", ".join(str(int(i)) for i in mesh.faces.reshape(-1))
    bounds = mesh.bounds
    extent = f"[{_vec3(bounds[0])}, {_vec3(bounds[1])}]"
    text = f'''#usda 1.0
(
    defaultPrim = "{asset_name}"
    upAxis = "Y"
    metersPerUnit = 0.01
)

def Xform "{asset_name}" {{
    def Mesh "mesh" {{
        uniform token subdivisionScheme = "none"
        point3f[] points = [{points}]
        int[] faceVertexCounts = [{counts}]
        int[] faceVertexIndices = [{indices}]
        texCoord2f[] primvars:st = [{st}] (
            interpolation = "vertex"
        )
        int[] primvars:st:indices = [{st_indices}]
        float3[] extent = {extent}
    }}
}}
'''
    path.write_text(text, encoding="utf-8")
