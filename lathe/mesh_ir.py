from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import trimesh


@dataclass
class MeshIR:
    asset_name: str
    family: str
    vertices: list[list[float]]
    faces: list[list[int]]
    face_parts: list[str]
    material_zones: list[dict[str, Any]] = field(default_factory=list)
    seam_classes: list[dict[str, Any]] = field(default_factory=list)
    hard_edge_classes: list[dict[str, Any]] = field(default_factory=list)
    bake_groups: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_trimesh(self) -> trimesh.Trimesh:
        return trimesh.Trimesh(vertices=np.array(self.vertices, dtype=np.float64), faces=np.array(self.faces, dtype=np.int64), process=False)
