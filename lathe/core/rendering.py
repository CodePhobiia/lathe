"""2D preview image rendering for build outputs (turntable, wireframe, UV, LOD sheets).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..imaging import open_guarded
from .mesh import RuntimeMesh

IMAGE_SIZE = 1024
PREVIEW_BG = (248, 248, 250, 255)
LINE_COLOR = (24, 28, 33, 255)
MAX_PREVIEW_FACES = 25000


def _rotation_matrix(x_angle: float, y_angle: float) -> np.ndarray:
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(x_angle), -math.sin(x_angle)],
            [0.0, math.sin(x_angle), math.cos(x_angle)],
        ]
    )
    ry = np.array(
        [
            [math.cos(y_angle), 0.0, math.sin(y_angle)],
            [0.0, 1.0, 0.0],
            [-math.sin(y_angle), 0.0, math.cos(y_angle)],
        ]
    )
    return rx @ ry


def _sample_face_indices(face_count: int) -> np.ndarray:
    if face_count <= MAX_PREVIEW_FACES:
        return np.arange(face_count, dtype=np.int64)
    return np.linspace(0, face_count - 1, MAX_PREVIEW_FACES, dtype=np.int64)


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    safe_lengths = np.where(lengths > 1e-12, lengths, 1.0)
    return normals / safe_lengths[:, None]


def render_mesh_preview(runtime_mesh: RuntimeMesh, path: Path, *, mode: str = "shaded") -> dict[str, object]:
    """Render mesh preview.

    Args:
        runtime_mesh: runtime_mesh argument.
        path: path argument.
        mode: mode argument.
    """
    mesh = runtime_mesh.mesh
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(vertices) == 0 or len(faces) == 0:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG).save(path)
        return {
            "status": "empty_mesh_preview",
            "mode": mode,
            "face_count": len(faces),
            "rendered_face_count": 0,
            "sampled": False,
        }
    rotation = _rotation_matrix(math.radians(35.264), math.radians(45.0))
    projected = vertices @ rotation.T
    xy = projected[:, :2]
    z = projected[:, 2]
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    span = np.maximum(bounds_max - bounds_min, 1e-6)
    scale = min((IMAGE_SIZE - 120) / span[0], (IMAGE_SIZE - 120) / span[1])
    screen = (xy - bounds_min) * scale + np.array([60.0, 60.0])
    screen[:, 1] = IMAGE_SIZE - screen[:, 1]
    image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
    draw = ImageDraw.Draw(image, "RGBA")

    face_indices = _sample_face_indices(len(faces))
    sampled_faces = faces[face_indices]
    normals = _face_normals(vertices, sampled_faces)
    triangles = []
    for draw_index, (face_index, face) in enumerate(zip(face_indices, sampled_faces, strict=True)):
        pts = [tuple(screen[idx]) for idx in face]
        depth = float(np.mean(z[face]))
        part = (
            runtime_mesh.face_parts[min(face_index, len(runtime_mesh.face_parts) - 1)]
            if runtime_mesh.face_parts
            else "mesh"
        )
        color = runtime_mesh.part_colors.get(part, (140, 160, 190))
        brightness = 0.78 + 0.22 * (
            0.5 + 0.5 * np.clip(np.dot(normals[draw_index], np.array([0.5, 0.7, 0.5])), -1, 1)
        )
        shaded = tuple(min(255, max(0, int(channel * brightness))) for channel in color) + (255,)
        triangles.append((depth, pts, shaded))
    triangles.sort(key=lambda item: item[0])

    if mode in {"shaded", "material_ids"}:
        for _, pts, color in triangles:
            fill = color if mode == "shaded" else color[:3] + (255,)
            draw.polygon(pts, fill=fill, outline=(30, 36, 45, 255))
    if mode == "wireframe":
        for _, pts, _ in triangles:
            draw.line([pts[0], pts[1], pts[2], pts[0]], fill=LINE_COLOR, width=2)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {
        "status": "rendered_sampled_preview" if len(face_indices) < len(faces) else "rendered_preview",
        "mode": mode,
        "face_count": len(faces),
        "rendered_face_count": len(face_indices),
        "sampled": bool(len(face_indices) < len(faces)),
        "max_preview_faces": int(MAX_PREVIEW_FACES),
    }


def render_uv_layout(runtime_mesh: RuntimeMesh, path: Path) -> None:
    """Render uv layout.

    Args:
        runtime_mesh: runtime_mesh argument.
        path: path argument.
    """
    mesh = runtime_mesh.mesh
    uv = getattr(mesh.visual, "uv", None)
    if uv is None:
        image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
        image.save(path)
        return
    image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
    draw = ImageDraw.Draw(image, "RGBA")
    scale = IMAGE_SIZE - 80
    for face_index, face in enumerate(mesh.faces):
        pts = []
        for vertex_idx in face:
            u, v = uv[vertex_idx]
            pts.append((40 + u * scale, IMAGE_SIZE - (40 + v * scale)))
        part = (
            runtime_mesh.face_parts[min(face_index, len(runtime_mesh.face_parts) - 1)]
            if runtime_mesh.face_parts
            else "mesh"
        )
        color = runtime_mesh.part_colors.get(part, (140, 160, 190))
        draw.polygon(pts, outline=(30, 36, 45, 255), fill=color + (140,))
    image.save(path)


def render_lod_sheet(runtime_mesh: RuntimeMesh, lod_count: int, path: Path) -> None:
    """Render lod sheet.

    Args:
        runtime_mesh: runtime_mesh argument.
        lod_count: lod_count argument.
        path: path argument.
    """
    grid = min(4, max(1, lod_count))
    cell = 512
    sheet = Image.new("RGBA", (cell * 2, cell * 2), PREVIEW_BG)
    for idx in range(grid):
        tmp_path = path.parent / f"._lod_{idx}.png"
        render_mesh_preview(runtime_mesh, tmp_path, mode="shaded")
        with open_guarded(tmp_path) as opened:
            img = opened.resize((cell, cell))
        x = (idx % 2) * cell
        y = (idx // 2) * cell
        sheet.paste(img, (x, y))
        tmp_path.unlink(missing_ok=True)
    sheet.save(path)
