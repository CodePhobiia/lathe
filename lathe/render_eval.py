from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


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


def _view_rotation(view: str) -> np.ndarray:
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
    if view == "iso":
        return _rotation_matrix(np.radians(35.264), np.radians(45.0))
    raise ValueError(f"Unknown view '{view}'")


def _perimeter(mask: np.ndarray) -> int:
    padded = np.pad(mask.astype(np.uint8), 1)
    return int(
        np.sum(padded[1:-1, 1:-1] != padded[:-2, 1:-1])
        + np.sum(padded[1:-1, 1:-1] != padded[2:, 1:-1])
        + np.sum(padded[1:-1, 1:-1] != padded[1:-1, :-2])
        + np.sum(padded[1:-1, 1:-1] != padded[1:-1, 2:])
    )


def _component_count(mask: np.ndarray) -> int:
    visited = np.zeros_like(mask, dtype=bool)
    count = 0
    for y in range(mask.shape[0]):
        for x in range(mask.shape[1]):
            if not mask[y, x] or visited[y, x]:
                continue
            count += 1
            queue = deque([(y, x)])
            visited[y, x] = True
            while queue:
                cy, cx = queue.popleft()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if (
                        0 <= ny < mask.shape[0]
                        and 0 <= nx < mask.shape[1]
                        and mask[ny, nx]
                        and not visited[ny, nx]
                    ):
                        visited[ny, nx] = True
                        queue.append((ny, nx))
    return count


def _evaluate_mask(mask: np.ndarray) -> dict[str, float]:
    area = float(mask.sum())
    if area <= 0:
        return {
            "area": 0.0,
            "bbox_area": 0.0,
            "perimeter": 0.0,
            "components": 0.0,
            "complexity": 0.0,
            "primitive_penalty": 1.0,
            "artifact_penalty": 1.0,
            "clutter": 1.0,
        }
    ys, xs = np.where(mask)
    bbox_area = float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
    perimeter = float(_perimeter(mask))
    components = _component_count(mask)
    complexity = min(1.0, (perimeter / max(1.0, area)) * 18.0)
    primitive_penalty = max(0.0, min(1.0, (bbox_area / max(1.0, area) - 1.0) / 2.0))
    artifact_penalty = max(0.0, min(1.0, (components - 1) / 6.0))
    clutter = min(1.0, components / 6.0)
    return {
        "area": area,
        "bbox_area": bbox_area,
        "perimeter": perimeter,
        "components": float(components),
        "complexity": round(complexity, 6),
        "primitive_penalty": round(primitive_penalty, 6),
        "artifact_penalty": round(artifact_penalty, 6),
        "clutter": round(clutter, 6),
    }


def _raster_from_mesh(mesh, view: str, size: int = 128) -> tuple[np.ndarray, np.ndarray]:
    rotation = _view_rotation(view)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    projected = vertices @ rotation.T
    xy = projected[:, :2]
    depth = projected[:, 2]
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    span = np.maximum(bounds_max - bounds_min, 1e-6)
    scale = min((size - 8) / span[0], (size - 8) / span[1])
    screen = (xy - bounds_min) * scale + np.array([4.0, 4.0])
    screen[:, 1] = size - screen[:, 1]
    mask_image = Image.new("L", (size, size), 0)
    shade_image = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask_image, "L")
    shade_draw = ImageDraw.Draw(shade_image, "L")
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    order = np.argsort([depth[face].mean() for face in faces])
    light = np.array([0.4, 0.8, 0.4], dtype=np.float64)
    light /= np.linalg.norm(light)
    for face_index in order:
        face = faces[face_index]
        polygon = [tuple(screen[idx]) for idx in face]
        brightness = int(max(20, min(255, (np.dot(normals[face_index], light) * 0.5 + 0.5) * 255.0)))
        mask_draw.polygon(polygon, fill=255)
        shade_draw.polygon(polygon, fill=brightness)
    return np.asarray(mask_image) > 0, np.asarray(shade_image, dtype=np.uint8)


def _rectangles_from_part_groups(
    part_groups: list[dict[str, Any]], view: str
) -> tuple[list[tuple[float, float, float, float]], tuple[float, float, float, float]]:
    rotation = _view_rotation(view)
    rectangles = []
    mins = []
    maxs = []
    for group in part_groups:
        bmin = np.array(group["bounds_min"], dtype=np.float64)
        bmax = np.array(group["bounds_max"], dtype=np.float64)
        corners = np.array(
            [[x, y, z] for x in (bmin[0], bmax[0]) for y in (bmin[1], bmax[1]) for z in (bmin[2], bmax[2])],
            dtype=np.float64,
        )
        projected = corners @ rotation.T
        xy = projected[:, :2]
        lo = xy.min(axis=0)
        hi = xy.max(axis=0)
        rectangles.append((float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])))
        mins.append(lo)
        maxs.append(hi)
    global_min = np.min(np.array(mins), axis=0)
    global_max = np.max(np.array(maxs), axis=0)
    return rectangles, (
        float(global_min[0]),
        float(global_min[1]),
        float(global_max[0]),
        float(global_max[1]),
    )


def _rasterize_rectangles(
    part_groups: list[dict[str, Any]], view: str, size: int = 128
) -> tuple[np.ndarray, np.ndarray]:
    rectangles, bounds = _rectangles_from_part_groups(part_groups, view)
    x0, y0, x1, y1 = bounds
    span_x = max(1e-6, x1 - x0)
    span_y = max(1e-6, y1 - y0)
    scale = min((size - 8) / span_x, (size - 8) / span_y)
    image = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(image, "L")
    for rx0, ry0, rx1, ry1 in rectangles:
        px0 = max(0, min(size - 1, int((rx0 - x0) * scale) + 4))
        px1 = max(0, min(size - 1, int((rx1 - x0) * scale) + 4))
        py0 = max(0, min(size - 1, size - (int((ry1 - y0) * scale) + 4)))
        py1 = max(0, min(size - 1, size - (int((ry0 - y0) * scale) + 4)))
        if px1 < px0 or py1 < py0:
            continue
        draw.rectangle([px0, py0, px1, py1], fill=255)
    arr = np.asarray(image, dtype=np.uint8)
    return arr > 0, arr


def evaluate_render_views(topology_runtime: dict[str, Any], views: list[str] | None = None) -> dict[str, Any]:
    bundle = topology_runtime.get("bundle", topology_runtime)
    runtime_mesh = topology_runtime.get("runtime_mesh")
    part_groups = bundle.get("part_groups", [])
    views = list(views or ["front", "side", "iso"])
    if runtime_mesh is None and not part_groups:
        return {
            "views": {},
            "metrics": {
                "render_silhouette_complexity": 0.0,
                "render_primitive_penalty": 1.0,
                "render_assembly_artifact_penalty": 1.0,
                "render_component_clutter": 1.0,
                "render_shading_variance": 0.0,
            },
        }

    view_metrics = {}
    complexity_scores = []
    primitive_penalties = []
    artifact_penalties = []
    clutter_scores = []
    shading_scores = []
    for view in views:
        if runtime_mesh is not None:
            mask, shade = _raster_from_mesh(runtime_mesh.mesh, view)
            shading_variance = float(np.std(shade[mask]) / 255.0) if np.any(mask) else 0.0
        else:
            mask, shade = _rasterize_rectangles(part_groups, view)
            shading_variance = 0.0
        metrics = _evaluate_mask(mask)
        metrics["shading_variance"] = round(shading_variance, 6)
        view_metrics[view] = metrics
        complexity_scores.append(metrics["complexity"])
        primitive_penalties.append(metrics["primitive_penalty"])
        artifact_penalties.append(metrics["artifact_penalty"])
        clutter_scores.append(metrics["clutter"])
        shading_scores.append(shading_variance)

    return {
        "views": view_metrics,
        "metrics": {
            "render_silhouette_complexity": round(sum(complexity_scores) / max(1, len(complexity_scores)), 6),
            "render_primitive_penalty": round(sum(primitive_penalties) / max(1, len(primitive_penalties)), 6),
            "render_assembly_artifact_penalty": round(
                sum(artifact_penalties) / max(1, len(artifact_penalties)), 6
            ),
            "render_component_clutter": round(sum(clutter_scores) / max(1, len(clutter_scores)), 6),
            "render_shading_variance": round(sum(shading_scores) / max(1, len(shading_scores)), 6),
        },
    }
