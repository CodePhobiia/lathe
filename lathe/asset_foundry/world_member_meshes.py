"""Deterministic visible meshes for Forge world-member packages."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

from ..forge import WorldAsset
from .generators._base import FoundryAsset

WORLD_MEMBER_MESH_VERSION = "lathe.asset_foundry.world_member_mesh_v1"

Color = tuple[float, float, float, float]
Vertex = tuple[float, float, float]

ROLE_COLORS: dict[str, Color] = {
    "floating_island": (0.35, 0.52, 0.36, 1.0),
    "cottage": (0.76, 0.48, 0.32, 1.0),
    "elder_house": (0.9, 0.58, 0.34, 1.0),
    "pine_tree": (0.18, 0.45, 0.25, 1.0),
    "crystal_cluster": (0.48, 0.34, 0.9, 1.0),
    "rope_bridge": (0.55, 0.34, 0.18, 1.0),
    "waterfall_ribbon": (0.34, 0.72, 0.9, 0.86),
    "stone_path_segment": (0.48, 0.46, 0.42, 1.0),
    "lantern": (0.95, 0.68, 0.28, 1.0),
    "fence_segment": (0.5, 0.32, 0.18, 1.0),
}


class MeshBuilder:
    def __init__(self) -> None:
        self.vertices: list[Vertex] = []
        self.indices: list[int] = []

    def add_box(self, center: Vertex, size: Vertex) -> None:
        cx, cy, cz = center
        sx, sy, sz = (max(0.01, value) / 2.0 for value in size)
        base = len(self.vertices)
        self.vertices.extend(
            [
                (cx - sx, cy - sy, cz - sz),
                (cx + sx, cy - sy, cz - sz),
                (cx + sx, cy + sy, cz - sz),
                (cx - sx, cy + sy, cz - sz),
                (cx - sx, cy - sy, cz + sz),
                (cx + sx, cy - sy, cz + sz),
                (cx + sx, cy + sy, cz + sz),
                (cx - sx, cy + sy, cz + sz),
            ]
        )
        self.indices.extend(
            [
                base + i
                for i in (
                    0,
                    1,
                    2,
                    0,
                    2,
                    3,
                    4,
                    6,
                    5,
                    4,
                    7,
                    6,
                    0,
                    4,
                    5,
                    0,
                    5,
                    1,
                    1,
                    5,
                    6,
                    1,
                    6,
                    2,
                    2,
                    6,
                    7,
                    2,
                    7,
                    3,
                    3,
                    7,
                    4,
                    3,
                    4,
                    0,
                )
            ]
        )

    def add_roof_prism(self, center: Vertex, size: Vertex) -> None:
        cx, cy, cz = center
        sx, sy, sz = (max(0.01, value) / 2.0 for value in size)
        base = len(self.vertices)
        self.vertices.extend(
            [
                (cx - sx, cy - sy, cz - sz),
                (cx + sx, cy - sy, cz - sz),
                (cx, cy - sy, cz + sz),
                (cx - sx, cy + sy, cz - sz),
                (cx + sx, cy + sy, cz - sz),
                (cx, cy + sy, cz + sz),
            ]
        )
        self.indices.extend(
            [
                base + i
                for i in (
                    0,
                    1,
                    2,
                    3,
                    5,
                    4,
                    0,
                    3,
                    4,
                    0,
                    4,
                    1,
                    1,
                    4,
                    5,
                    1,
                    5,
                    2,
                    2,
                    5,
                    3,
                    2,
                    3,
                    0,
                )
            ]
        )

    def add_cone(self, center: Vertex, radius: float, height: float, segments: int = 8) -> None:
        cx, cy, cz = center
        base = len(self.vertices)
        self.vertices.append((cx, cy, cz + height / 2.0))
        for i in range(segments):
            angle = (math.tau * i) / segments
            self.vertices.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius, cz - height / 2.0))
        for i in range(segments):
            a = base + 1 + i
            b = base + 1 + ((i + 1) % segments)
            self.indices.extend([base, a, b])


def _bbox_size(asset: FoundryAsset) -> Vertex:
    lo, hi = asset.bbox_cm
    return (
        max(20.0, float(hi[0]) - float(lo[0])) / 100.0,
        max(20.0, float(hi[1]) - float(lo[1])) / 100.0,
        max(20.0, float(hi[2]) - float(lo[2])) / 100.0,
    )


def _mesh_for_role(role: str, foundry_asset: FoundryAsset) -> MeshBuilder:
    b = MeshBuilder()
    sx, sy, sz = _bbox_size(foundry_asset)
    if role in {"cottage", "elder_house"}:
        b.add_box((0, 0, sz * 0.28), (sx * 0.72, sy * 0.7, sz * 0.52))
        b.add_roof_prism((0, 0, sz * 0.72), (sx * 0.86, sy * 0.82, sz * 0.42))
        b.add_box((sx * 0.18, -sy * 0.36, sz * 0.54), (sx * 0.08, sy * 0.08, sz * 0.36))
    elif role == "floating_island":
        b.add_cone((0, 0, -sz * 0.24), max(sx, sy) * 0.5, sz * 0.8, 10)
        b.add_box((0, 0, sz * 0.18), (sx, sy, sz * 0.22))
    elif role == "pine_tree":
        b.add_box((0, 0, sz * 0.24), (sx * 0.12, sy * 0.12, sz * 0.48))
        b.add_cone((0, 0, sz * 0.48), max(sx, sy) * 0.42, sz * 0.56, 8)
        b.add_cone((0, 0, sz * 0.72), max(sx, sy) * 0.32, sz * 0.48, 8)
    elif role == "crystal_cluster":
        for i, offset in enumerate((-0.22, 0.0, 0.22)):
            b.add_cone((offset * sx, 0, sz * (0.25 + i * 0.08)), max(sx, sy) * (0.16 - i * 0.02), sz * (0.55 + i * 0.12), 5)
    elif role == "rope_bridge":
        for i in range(7):
            x = (i - 3) * sx * 0.12
            b.add_box((x, 0, sz * 0.05), (sx * 0.08, sy, sz * 0.08))
        b.add_box((0, -sy * 0.46, sz * 0.16), (sx, sy * 0.06, sz * 0.08))
        b.add_box((0, sy * 0.46, sz * 0.16), (sx, sy * 0.06, sz * 0.08))
    elif role == "waterfall_ribbon":
        b.add_box((0, 0, 0), (sx * 0.24, sy * 0.04, sz))
    elif role == "stone_path_segment":
        b.add_box((0, 0, sz * 0.04), (sx, sy * 0.72, sz * 0.08))
    elif role == "lantern":
        b.add_box((0, 0, sz * 0.35), (sx * 0.12, sy * 0.12, sz * 0.7))
        b.add_box((0, 0, sz * 0.78), (sx * 0.34, sy * 0.34, sz * 0.18))
    elif role == "fence_segment":
        b.add_box((-sx * 0.45, 0, sz * 0.42), (sx * 0.08, sy * 0.18, sz * 0.84))
        b.add_box((sx * 0.45, 0, sz * 0.42), (sx * 0.08, sy * 0.18, sz * 0.84))
        b.add_box((0, 0, sz * 0.36), (sx, sy * 0.12, sz * 0.08))
        b.add_box((0, 0, sz * 0.68), (sx, sy * 0.12, sz * 0.08))
    else:
        b.add_box((0, 0, sz * 0.5), (sx, sy, sz))
    return b


def _write_glb(path: Path, vertices: list[Vertex], indices: list[int], color: Color) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = bytearray()
    index_offset = 0
    for index in indices:
        binary.extend(struct.pack("<H", index))
    while len(binary) % 4:
        binary.append(0)
    position_offset = len(binary)
    for vertex in vertices:
        binary.extend(struct.pack("<fff", *vertex))
    json_payload = {
        "asset": {"version": "2.0", "generator": WORLD_MEMBER_MESH_VERSION},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(indices) * 2, "target": 34963},
            {"buffer": 0, "byteOffset": position_offset, "byteLength": len(vertices) * 12, "target": 34962},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
                "min": [min(indices) if indices else 0],
                "max": [max(indices) if indices else 0],
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(vertices),
                "type": "VEC3",
                "min": [min(v[i] for v in vertices) for i in range(3)],
                "max": [max(v[i] for v in vertices) for i in range(3)],
            },
        ],
        "materials": [
            {
                "name": "Lathe visible role material",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(color),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.78,
                },
            }
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 1}, "indices": 0, "material": 0}]}],
    }
    json_bytes = json.dumps(json_payload, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "
    while len(binary) % 4:
        binary.append(0)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
    path.write_bytes(
        b"".join(
            [
                b"glTF",
                struct.pack("<II", 2, total_length),
                struct.pack("<I4s", len(json_bytes), b"JSON"),
                json_bytes,
                struct.pack("<I4s", len(binary), b"BIN\x00"),
                bytes(binary),
            ]
        )
    )


def write_world_member_mesh_glb(
    *,
    world_asset: WorldAsset,
    foundry_asset: FoundryAsset,
    pkg_dir: str | Path,
) -> dict[str, Any]:
    """Write visible low-poly mesh.glb for one world member."""

    target = Path(pkg_dir) / "mesh.glb"
    mesh = _mesh_for_role(world_asset.role, foundry_asset)
    color = ROLE_COLORS.get(world_asset.role, (0.72, 0.72, 0.72, 1.0))
    _write_glb(target, mesh.vertices, mesh.indices, color)
    return {
        "status": "real",
        "path": "mesh.glb",
        "format": "glb",
        "vertex_count": len(mesh.vertices),
        "triangle_count": len(mesh.indices) // 3,
        "role": world_asset.role,
        "generator": WORLD_MEMBER_MESH_VERSION,
    }


__all__ = [
    "WORLD_MEMBER_MESH_VERSION",
    "write_world_member_mesh_glb",
]
