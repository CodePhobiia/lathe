from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


IMAGE_BG = (246, 247, 250, 255)
LINE_COLOR = (30, 36, 44, 255)


def _render_rotation(view: str) -> np.ndarray:
    if view == "front":
        return _rotation_matrix(0.0, 0.0)
    if view == "front_34":
        return _rotation_matrix(np.radians(12.0), np.radians(35.0))
    if view == "side":
        return _rotation_matrix(0.0, np.pi / 2.0)
    if view == "rear":
        return _rotation_matrix(0.0, np.pi)
    if view == "rear_34":
        return _rotation_matrix(np.radians(12.0), np.radians(145.0))
    return _rotation_matrix(np.radians(35.264), np.radians(45.0))


def _rotation_matrix(x_angle: float, y_angle: float) -> np.ndarray:
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(x_angle), -np.sin(x_angle)],
            [0.0, np.sin(x_angle), np.cos(x_angle)],
        ],
        dtype=np.float64,
    )
    ry = np.array(
        [
            [np.cos(y_angle), 0.0, np.sin(y_angle)],
            [0.0, 1.0, 0.0],
            [-np.sin(y_angle), 0.0, np.cos(y_angle)],
        ],
        dtype=np.float64,
    )
    return rx @ ry


def _project_mesh(runtime_mesh: Any, view: str, size: int) -> tuple[np.ndarray, np.ndarray, list[tuple[float, list[tuple[float, float]], int, tuple[int, int, int]]]]:
    mesh = runtime_mesh.mesh
    rotation = _render_rotation(view)
    projected = np.asarray(mesh.vertices, dtype=np.float64) @ rotation.T
    xy = projected[:, :2]
    depth = projected[:, 2]
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    span = np.maximum(bounds_max - bounds_min, 1e-6)
    scale = min((size - 80) / span[0], (size - 80) / span[1])
    screen = (xy - bounds_min) * scale + np.array([40.0, 40.0])
    screen[:, 1] = size - screen[:, 1]
    light = np.array([0.45, 0.78, 0.44], dtype=np.float64)
    light /= np.linalg.norm(light)
    face_parts = list(getattr(runtime_mesh, "face_parts", []))
    colors = dict(getattr(runtime_mesh, "part_colors", {}))
    triangles = []
    for face_index, face in enumerate(mesh.faces):
        pts = [tuple(screen[idx]) for idx in face]
        part = face_parts[min(face_index, len(face_parts) - 1)] if face_parts else "mesh"
        base = colors.get(part, (146, 162, 188))
        brightness = np.clip(np.dot(mesh.face_normals[face_index], light) * 0.5 + 0.5, 0.0, 1.0)
        depth_value = int(np.clip((depth[list(face)].mean() - depth.min()) / max(1e-6, depth.max() - depth.min()) * 255.0, 0.0, 255.0))
        triangles.append((float(depth[list(face)].mean()), pts, depth_value, base, float(brightness)))
    triangles.sort(key=lambda item: item[0])
    return screen, depth, triangles


def _render_mesh_pass(runtime_mesh: Any, path: Path, view: str, mode: str, size: int) -> None:
    _, _, triangles = _project_mesh(runtime_mesh, view, size)
    if mode in {"beauty", "normal"}:
        image = Image.new("RGBA", (size, size), IMAGE_BG)
        draw = ImageDraw.Draw(image, "RGBA")
    else:
        image = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(image, "L")

    for _, pts, depth_value, base, brightness in triangles:
        if mode == "beauty":
            fill = tuple(int(np.clip(channel * (0.72 + brightness * 0.34), 0, 255)) for channel in base) + (255,)
            draw.polygon(pts, fill=fill, outline=LINE_COLOR)
        elif mode == "normal":
            fill = (int(128 + (base[0] - 128) * 0.35), int(128 + (base[1] - 128) * 0.35), 255, 255)
            draw.polygon(pts, fill=fill, outline=LINE_COLOR)
        else:
            draw.polygon(pts, fill=depth_value)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
