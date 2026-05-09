"""Optional turntable render helper for ``lathe quick --render``.

Best-effort: tries trimesh's pyglet-based ``Scene.save_image`` for a
single front render, falls back to a four-angle 2x2 PIL grid using the
same backend, and finally degrades to a no-op (returning ``False``) so
the CLI command never fails just because no GL stack is present.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

_LOG = logging.getLogger(__name__)


def _render_single(scene, resolution: tuple[int, int]) -> bytes | None:
    try:
        return scene.save_image(resolution=resolution)
    except (BaseException, Exception) as exc:  # pyglet on headless raises BaseException
        _LOG.info("lathe.quick.render.single_failed: %s: %s", type(exc).__name__, exc)
        return None


def _render_grid(scene, resolution: tuple[int, int]) -> bytes | None:
    """Render four 0/90/180/270 yaw views into a 2x2 grid via PIL."""
    try:
        from io import BytesIO

        import numpy as np
        from PIL import Image
    except ImportError:
        return None

    try:
        import trimesh.transformations as tt
    except ImportError:
        return None

    half_w, half_h = resolution[0] // 2, resolution[1] // 2
    sub_resolution = (half_w, half_h)

    centroid = scene.centroid if scene.centroid is not None else np.zeros(3)
    extent = float(np.linalg.norm(scene.extents)) if scene.extents is not None else 1.0
    distance = max(extent * 1.4, 1.0)

    images: list[Image.Image] = []
    for angle_deg in (0, 90, 180, 270):
        try:
            angle_rad = math.radians(angle_deg)
            rot = tt.rotation_matrix(angle_rad, [0, 1, 0], point=centroid)
            cam_pos = np.array([
                centroid[0] + distance * math.sin(angle_rad),
                centroid[1] + distance * 0.4,
                centroid[2] + distance * math.cos(angle_rad),
            ])
            cam_transform = tt.translation_matrix(cam_pos) @ rot
            scene.camera_transform = cam_transform
            blob = scene.save_image(resolution=sub_resolution)
        except (BaseException, Exception) as exc:
            _LOG.info("lathe.quick.render.frame_failed angle=%d: %s", angle_deg, exc)
            return None
        if not blob:
            return None
        try:
            images.append(Image.open(BytesIO(blob)).convert("RGB"))
        except Exception as exc:
            _LOG.info("lathe.quick.render.frame_decode_failed: %s", exc)
            return None

    if len(images) != 4:
        return None
    grid = Image.new("RGB", resolution, (24, 24, 28))
    grid.paste(images[0], (0, 0))
    grid.paste(images[1], (half_w, 0))
    grid.paste(images[2], (0, half_h))
    grid.paste(images[3], (half_w, half_h))
    out = BytesIO()
    grid.save(out, format="PNG")
    return out.getvalue()


def render_turntable(
    glb_path: Path,
    out_png: Path,
    *,
    resolution: tuple[int, int] = (512, 512),
) -> bool:
    """Try to render a turntable preview PNG of ``glb_path`` to ``out_png``.

    Returns ``True`` when a non-empty PNG was written, ``False`` otherwise.
    Never raises — on any failure it logs at INFO and returns ``False``.
    """
    try:
        import trimesh
    except ImportError:
        _LOG.info("lathe.quick.render.skipped: trimesh missing")
        return False

    try:
        loaded = trimesh.load(str(glb_path))
    except Exception as exc:
        _LOG.info("lathe.quick.render.load_failed: %s", exc)
        return False
    scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)

    blob = _render_single(scene, resolution)
    if not blob:
        blob = _render_grid(scene, resolution)
    if not blob:
        _LOG.info(
            "lathe.quick.render.skipped: no GL backend (install pyglet<2 or render in a graphical session)"
        )
        return False

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(blob)
    return out_png.exists() and out_png.stat().st_size > 0
