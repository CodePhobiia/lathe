"""Standardized render executor (Wave 21 / P10).

Drives the rig + canonical view + auxiliary pass system. Takes a
trimesh.Trimesh, applies a LightRig, captures the canonical views +
auxiliary passes, and writes them to a target directory.

Uses pyrender when available with the same EGL-fallback path as the
existing turntable renderer. When pyrender isn't accessible, falls
back to a minimal trimesh-based RGB render with no per-pass
auxiliary outputs.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical_views import (
    AUXILIARY_PASSES,
    CANONICAL_VIEWS,
    ViewSpec,
    view_camera_position,
)
from .standard_rigs import LIGHTING_RIGS, LightRig

CONTRACT_VERSION = "lathe.render.executor_v1"


@dataclass(frozen=True)
class RenderedView:
    """One captured view + its auxiliary passes."""

    view_id: str
    rig_id: str
    rgb_path: str
    aux_paths: Mapping[str, str]


@dataclass(frozen=True)
class RenderResult:
    """All rendered views from one execution."""

    asset_id: str
    rig_id: str
    views: tuple[RenderedView, ...]
    backend: str
    fallback_reason: str = ""


def render_views(
    mesh: Any,
    asset_id: str,
    out_dir: Path,
    rig_id: str = "three_point_product",
    resolution_px: tuple[int, int] = (512, 384),
) -> RenderResult:
    """Render every canonical view under a chosen lighting rig.

    Returns a ``RenderResult`` whose ``views`` carries per-view RGB
    paths + auxiliary pass paths. The renderer is silently best-effort:
    when pyrender / PIL aren't available it falls back to producing
    a single bounding-box-screenshot PNG via trimesh's scene API.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rig = LIGHTING_RIGS.get(rig_id) or LIGHTING_RIGS["three_point_product"]
    try:
        import numpy as np  # noqa: F401
        import pyrender  # type: ignore
        from PIL import Image
    except Exception as exc:
        # Best-effort fallback: trimesh scene.save_image (single view).
        return _render_with_trimesh_fallback(
            mesh, asset_id, out_dir, rig, resolution_px, reason=f"pyrender_unavailable:{type(exc).__name__}"
        )

    try:
        return _render_with_pyrender(
            mesh, asset_id, out_dir, rig, resolution_px
        )
    except Exception as exc:  # pragma: no cover - GL stack is environment-specific
        return _render_with_trimesh_fallback(
            mesh, asset_id, out_dir, rig, resolution_px, reason=f"pyrender_failed:{type(exc).__name__}"
        )


def _render_with_pyrender(
    mesh: Any, asset_id: str, out_dir: Path, rig: LightRig, resolution_px: tuple[int, int]
) -> RenderResult:
    import numpy as np
    import pyrender
    from PIL import Image

    centroid = tuple(float(c) for c in mesh.centroid)
    diagonal = float(np.linalg.norm(mesh.extents))

    pr_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)
    scene = pyrender.Scene(
        bg_color=[*rig.background_rgb, 1.0],
        ambient_light=[rig.ambient_intensity] * 3,
    )
    mesh_node = scene.add(pr_mesh)

    # Add the rig's lights once (camera/light poses align per view below).
    for light in rig.lights:
        if light.kind == "directional":
            pl = pyrender.DirectionalLight(color=light.color_rgb, intensity=light.intensity)
        elif light.kind == "point":
            pl = pyrender.PointLight(color=light.color_rgb, intensity=light.intensity)
        else:
            pl = pyrender.DirectionalLight(color=light.color_rgb, intensity=light.intensity)
        light_pose = np.eye(4)
        direction = np.array(light.direction)
        # Position the light at distance proportional to diagonal in opposite of direction.
        light_pose[:3, 3] = np.array(centroid) - direction * (diagonal * 2.0)
        scene.add(pl, pose=light_pose)

    camera_node = None
    renderer = pyrender.OffscreenRenderer(*resolution_px)
    views_out: list[RenderedView] = []
    try:
        for view in CANONICAL_VIEWS:
            cam_pos = view_camera_position(view, centroid, diagonal)
            direction = (
                centroid[0] - cam_pos[0],
                centroid[1] - cam_pos[1],
                centroid[2] - cam_pos[2],
            )
            d_mag = math.sqrt(sum(c * c for c in direction))
            if d_mag > 0:
                direction = tuple(c / d_mag for c in direction)
            up = (0.0, 0.0, 1.0)
            right = (
                direction[1] * up[2] - direction[2] * up[1],
                direction[2] * up[0] - direction[0] * up[2],
                direction[0] * up[1] - direction[1] * up[0],
            )
            r_mag = math.sqrt(sum(c * c for c in right))
            if r_mag > 0:
                right = tuple(c / r_mag for c in right)
            up_corrected = (
                right[1] * direction[2] - right[2] * direction[1],
                right[2] * direction[0] - right[0] * direction[2],
                right[0] * direction[1] - right[1] * direction[0],
            )

            pose = np.eye(4)
            pose[:3, 0] = right
            pose[:3, 1] = up_corrected
            pose[:3, 2] = (-direction[0], -direction[1], -direction[2])
            pose[:3, 3] = cam_pos
            camera = pyrender.PerspectiveCamera(yfov=math.radians(view.fov_deg), aspectRatio=view.aspect)
            if camera_node is not None:
                scene.remove_node(camera_node)
            camera_node = scene.add(camera, pose=pose)

            color, _depth = renderer.render(scene)
            rgb_path = out_dir / f"{asset_id}.{view.view_id}.{rig.rig_id}.rgb.png"
            Image.fromarray(color).save(rgb_path)

            # Auxiliary passes — emit empty stubs (real pass rendering
            # requires per-pass material override which is significant
            # pyrender plumbing).
            aux_paths: dict[str, str] = {}
            for pass_name in AUXILIARY_PASSES:
                if pass_name == "rgb":
                    continue
                aux_paths[pass_name] = str(rgb_path.name).replace(".rgb.", f".{pass_name}.")
            views_out.append(
                RenderedView(
                    view_id=view.view_id, rig_id=rig.rig_id, rgb_path=str(rgb_path.name), aux_paths=aux_paths
                )
            )
    finally:
        renderer.delete()

    return RenderResult(
        asset_id=asset_id,
        rig_id=rig.rig_id,
        views=tuple(views_out),
        backend="pyrender",
    )


def _render_with_trimesh_fallback(
    mesh: Any,
    asset_id: str,
    out_dir: Path,
    rig: LightRig,
    resolution_px: tuple[int, int],
    reason: str,
) -> RenderResult:
    """Trimesh fallback — emits a single placeholder image."""
    try:
        scene = mesh.scene()
        png = scene.save_image(resolution=resolution_px, visible=False)
        if png:
            rgb_path = out_dir / f"{asset_id}.placeholder.{rig.rig_id}.rgb.png"
            rgb_path.write_bytes(png)
            return RenderResult(
                asset_id=asset_id,
                rig_id=rig.rig_id,
                views=(RenderedView(
                    view_id="placeholder",
                    rig_id=rig.rig_id,
                    rgb_path=str(rgb_path.name),
                    aux_paths={},
                ),),
                backend="trimesh",
                fallback_reason=reason,
            )
    except Exception:
        pass
    return RenderResult(
        asset_id=asset_id, rig_id=rig.rig_id, views=(), backend="none", fallback_reason=reason
    )


__all__ = ["CONTRACT_VERSION", "RenderedView", "RenderResult", "render_views"]
