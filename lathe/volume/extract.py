"""Marching-cubes isosurface extraction from a Volume.

Prefers ``skimage.measure.marching_cubes`` when scikit-image is
installed; otherwise falls back to a deterministic axis-aligned
density-thresholded box mesh so downstream stages always receive
something they can integrate.

The fallback is intentionally crude: it outputs a hull mesh covering
all voxels above the threshold (one quad per occupied-vs-empty face
boundary). This preserves the volumetric silhouette but obviously
loses the smooth isosurface — flagged via ``method`` in the report
mapping.
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:  # pragma: no cover - import-availability guard
    from skimage import measure as _sk_measure  # type: ignore[import-untyped]

    SKIMAGE_AVAILABLE = True
except Exception:  # pragma: no cover - import-availability guard
    _sk_measure = None
    SKIMAGE_AVAILABLE = False


def extract_isosurface(volume: Any, threshold: float = 0.3) -> dict[str, Any]:
    """Extract a triangle mesh at ``density == threshold``.

    Returns a mapping ``{"vertices", "faces", "method", "vertex_count",
    "face_count", "threshold", "data_ir"}``. The vertices are returned
    in the volume's world-space bounds.
    """
    if SKIMAGE_AVAILABLE and _sk_measure is not None:
        verts, faces, method = _marching_cubes_skimage(volume, threshold)
    else:
        verts, faces, method = _voxel_hull_fallback(volume, threshold)

    return {
        "vertices": verts,
        "faces": faces,
        "method": method,
        "vertex_count": int(verts.shape[0]),
        "face_count": int(faces.shape[0]),
        "threshold": float(threshold),
        "bounds": list(volume.bounds),
        "resolution": list(volume.resolution),
        "data_ir": "lathe.volume_effects_data_ir.v1",
    }


def _marching_cubes_skimage(volume: Any, threshold: float) -> tuple[np.ndarray, np.ndarray, str]:
    density = volume.density
    max_density = float(np.max(density))
    if max_density <= threshold:
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
            "skimage_marching_cubes_empty",
        )

    spacing = volume.voxel_size
    verts, faces, _, _ = _sk_measure.marching_cubes(
        density, level=float(threshold), spacing=spacing, allow_degenerate=False
    )
    x0, y0, z0, _, _, _ = volume.bounds
    verts = verts.astype(np.float32, copy=True)
    verts[:, 0] += x0
    verts[:, 1] += y0
    verts[:, 2] += z0
    return verts, faces.astype(np.int32, copy=False), "skimage_marching_cubes"


def _voxel_hull_fallback(volume: Any, threshold: float) -> tuple[np.ndarray, np.ndarray, str]:
    occupied = volume.density > float(threshold)
    if not np.any(occupied):
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
            "voxel_hull_empty",
        )

    nx, ny, nz = volume.resolution
    vsx, vsy, vsz = volume.voxel_size
    x0, y0, z0, _, _, _ = volume.bounds

    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vert_index: dict[tuple[int, int, int], int] = {}

    def vid(ix: int, iy: int, iz: int) -> int:
        key = (ix, iy, iz)
        idx = vert_index.get(key)
        if idx is None:
            idx = len(verts)
            verts.append(
                (x0 + ix * vsx, y0 + iy * vsy, z0 + iz * vsz)
            )
            vert_index[key] = idx
        return idx

    def emit_quad(corners: tuple[tuple[int, int, int], ...]) -> None:
        a, b, c, d = (vid(*c) for c in corners)
        faces.append((a, b, c))
        faces.append((a, c, d))

    occ = occupied
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                if not occ[ix, iy, iz]:
                    continue
                if ix + 1 == nx or not occ[ix + 1, iy, iz]:
                    emit_quad((
                        (ix + 1, iy, iz), (ix + 1, iy + 1, iz),
                        (ix + 1, iy + 1, iz + 1), (ix + 1, iy, iz + 1),
                    ))
                if ix == 0 or not occ[ix - 1, iy, iz]:
                    emit_quad((
                        (ix, iy, iz), (ix, iy, iz + 1),
                        (ix, iy + 1, iz + 1), (ix, iy + 1, iz),
                    ))
                if iy + 1 == ny or not occ[ix, iy + 1, iz]:
                    emit_quad((
                        (ix, iy + 1, iz), (ix, iy + 1, iz + 1),
                        (ix + 1, iy + 1, iz + 1), (ix + 1, iy + 1, iz),
                    ))
                if iy == 0 or not occ[ix, iy - 1, iz]:
                    emit_quad((
                        (ix, iy, iz), (ix + 1, iy, iz),
                        (ix + 1, iy, iz + 1), (ix, iy, iz + 1),
                    ))
                if iz + 1 == nz or not occ[ix, iy, iz + 1]:
                    emit_quad((
                        (ix, iy, iz + 1), (ix + 1, iy, iz + 1),
                        (ix + 1, iy + 1, iz + 1), (ix, iy + 1, iz + 1),
                    ))
                if iz == 0 or not occ[ix, iy, iz - 1]:
                    emit_quad((
                        (ix, iy, iz), (ix, iy + 1, iz),
                        (ix + 1, iy + 1, iz), (ix + 1, iy, iz),
                    ))

    verts_arr = np.asarray(verts, dtype=np.float32)
    faces_arr = np.asarray(faces, dtype=np.int32)
    return verts_arr, faces_arr, "voxel_hull_fallback"
