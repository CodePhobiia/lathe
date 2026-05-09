"""Marching cubes mesh extraction from an SDF.

Prefers ``skimage.measure.marching_cubes`` when ``scikit-image`` is
installed (faster, well-tested). When that optional dependency is absent,
falls back to Lathe's in-repo dual-contouring extractor instead of the
legacy partial-table marching-cubes scaffold so default F-Rep extraction
still returns one coherent watertight surface for ordinary closed SDFs.
Both code paths return ``(vertices, faces)`` arrays in world-space
coordinates.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .evaluator import sample_grid
from .expressions import SDFExpr
from .mc_tables import EDGE_TABLE, TRI_TABLE, EDGE_VERTEX_INDICES


def _have_skimage() -> bool:
    try:  # pragma: no cover - import probe
        import skimage.measure  # noqa: F401
        return True
    except Exception:
        return False


def extract_marching_cubes(
    expr: SDFExpr,
    *,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    resolution: int | tuple[int, int, int] = 64,
    iso: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract a triangle mesh from the iso-surface of ``expr``.

    Args:
        expr: root :class:`SDFExpr`.
        bounds: evaluation box ``((xmin, ymin, zmin), (xmax, ymax, zmax))``.
        resolution: scalar grid resolution per axis or a 3-tuple.
        iso: iso-value (default 0 — the SDF surface).

    Returns:
        ``(vertices, faces)`` — float64 ``(V, 3)`` and int32 ``(F, 3)``.
    """
    if not _have_skimage():
        from .dual_contouring import extract_dual_contouring

        return extract_dual_contouring(expr, bounds=bounds, resolution=resolution, iso=iso)
    volume, (xs, ys, zs) = sample_grid(expr, bounds=bounds, resolution=resolution)
    return _extract_skimage(volume, xs, ys, zs, iso=iso)


def _extract_skimage(
    volume: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    *,
    iso: float,
) -> tuple[np.ndarray, np.ndarray]:
    """skimage path — convert (z, y, x) verts to world (x, y, z)."""
    import skimage.measure  # type: ignore

    # skimage expects spacing per axis matching the volume's index order.
    spacing = (
        (zs[-1] - zs[0]) / (volume.shape[0] - 1),
        (ys[-1] - ys[0]) / (volume.shape[1] - 1),
        (xs[-1] - xs[0]) / (volume.shape[2] - 1),
    )
    verts, faces, _normals, _values = skimage.measure.marching_cubes(
        volume, level=float(iso), spacing=spacing
    )
    # Translate to world origin and reorder (z, y, x) -> (x, y, z)
    out = np.empty_like(verts)
    out[:, 0] = verts[:, 2] + xs[0]
    out[:, 1] = verts[:, 1] + ys[0]
    out[:, 2] = verts[:, 0] + zs[0]
    return out.astype(np.float64), faces.astype(np.int32)


def _extract_numpy(
    volume: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    *,
    iso: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Pure-numpy marching cubes (Lorensen/Cline).

    Visits every voxel cell, classifies the 8 corners against ``iso``,
    looks up the 12-edge intersection mask in :data:`EDGE_TABLE`, and
    emits triangles per :data:`TRI_TABLE`. Vertices are linearly
    interpolated along the cube edges. Edge dedup is skipped — the
    output is welded later if needed by downstream consumers.
    """
    nz, ny, nx = volume.shape
    # Corner offsets in (dx, dy, dz)
    corner_offsets = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
            [0, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 1, 1],
        ],
        dtype=np.int32,
    )
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    edge_cache: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
    iso_f = float(iso)
    for k in range(nz - 1):
        for j in range(ny - 1):
            for i in range(nx - 1):
                # Corner values in canonical Lorensen order.
                cv = np.empty(8, dtype=np.float64)
                for ci, (dx, dy, dz) in enumerate(corner_offsets):
                    cv[ci] = volume[k + dz, j + dy, i + dx]
                # Cube index encodes which corners are below iso.
                cube_index = 0
                for ci in range(8):
                    if cv[ci] < iso_f:
                        cube_index |= 1 << ci
                edges = EDGE_TABLE[cube_index]
                if edges == 0:
                    continue
                # Compute interpolated edge vertices when needed. Cache by
                # global lattice edge so adjacent cells share the same vertex.
                edge_indices: list[int | None] = [None] * 12
                for e in range(12):
                    if not (edges & (1 << e)):
                        continue
                    a, b = EDGE_VERTEX_INDICES[e]
                    pa = corner_offsets[a]
                    pb = corner_offsets[b]
                    ga = (i + int(pa[0]), j + int(pa[1]), k + int(pa[2]))
                    gb = (i + int(pb[0]), j + int(pb[1]), k + int(pb[2]))
                    key = (ga, gb) if ga <= gb else (gb, ga)
                    cached = edge_cache.get(key)
                    if cached is not None:
                        edge_indices[e] = cached
                        continue
                    va = cv[a]
                    vb = cv[b]
                    denom = vb - va
                    if abs(denom) < 1e-12:
                        t = 0.5
                    else:
                        t = (iso_f - va) / denom
                    t = float(np.clip(t, 0.0, 1.0))
                    px = xs[i + pa[0]] + t * (xs[i + pb[0]] - xs[i + pa[0]])
                    py = ys[j + pa[1]] + t * (ys[j + pb[1]] - ys[j + pa[1]])
                    pz = zs[k + pa[2]] + t * (zs[k + pb[2]] - zs[k + pa[2]])
                    edge_index = len(verts)
                    verts.append((px, py, pz))
                    edge_cache[key] = edge_index
                    edge_indices[e] = edge_index
                tri = TRI_TABLE[cube_index]
                t_idx = 0
                while t_idx < len(tri) and tri[t_idx] != -1:
                    e0, e1, e2 = tri[t_idx], tri[t_idx + 1], tri[t_idx + 2]
                    v0 = edge_indices[e0]
                    v1 = edge_indices[e1]
                    v2 = edge_indices[e2]
                    if v0 is None or v1 is None or v2 is None:
                        t_idx += 3
                        continue
                    faces.append((v0, v1, v2))
                    t_idx += 3
    if not verts:
        return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 3), dtype=np.int32)
    return np.asarray(verts, dtype=np.float64), np.asarray(faces, dtype=np.int32)
