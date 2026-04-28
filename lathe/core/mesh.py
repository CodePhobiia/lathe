"""Runtime mesh dataclass shared across the executor pipeline.

Extracted from ``lathe/executor.py`` during Stage 2.IV. Kept in its own
module so that stage modules can import ``RuntimeMesh`` without creating a
circular import against ``lathe.executor``.
"""

from __future__ import annotations

from dataclasses import dataclass

import trimesh


@dataclass
class RuntimeMesh:
    """RuntimeMesh."""

    mesh: trimesh.Trimesh
    face_parts: list[str]
    part_colors: dict[str, tuple[int, int, int]]
    units: str = "cm"
