"""Dual Contouring (Schaefer & Warren) extraction — scaffold.

Marching cubes places vertices on cube edges and produces a uniform
quad-strip-style mesh that loses sharp features. Dual contouring instead
places one vertex per cell, positioned by minimizing a quadric error
metric (QEF) fit to the surface samples + their gradients, then
connects vertices across shared edges to form quads. This preserves
sharp creases (machined parts, blocky terrain) that MC rounds off.

This module provides the public entry point :func:`extract_dual_contouring`
and a compact implementation: per-edge intersection sampling,
finite-difference Hermite normals, per-cell QEF least-squares vertex
placement with centroid fallback, and adjacency-based quad generation. It
is smaller than a production DCC dual-contouring stack, but it preserves
sharp-cell placement better than the old centroid-only fallback while
keeping Lathe's no-skimage path coherent and watertight for ordinary
closed SDFs.

Reference: Schaefer & Warren, "Dual Contouring of Hermite Data" (2002).
"""

from __future__ import annotations

import numpy as np

from .evaluator import sample_grid
from .expressions import SDFExpr


def extract_dual_contouring(
    expr: SDFExpr,
    *,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    resolution: int | tuple[int, int, int] = 64,
    iso: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract a triangle mesh from ``expr`` using dual contouring.

    Args:
        expr: root :class:`SDFExpr`.
        bounds: evaluation box ``((xmin, ymin, zmin), (xmax, ymax, zmax))``.
        resolution: scalar grid resolution per axis or a 3-tuple.
        iso: iso-value (default 0).

    Returns:
        ``(vertices, faces)`` — float64 ``(V, 3)`` and int32 ``(F, 3)``.

    Notes:
        Vertex placement uses a compact QEF least-squares solve over
        finite-difference normals. If the solve is ill-conditioned or
        leaves the cell, the extractor falls back to a clipped centroid.
    """
    volume, (xs, ys, zs) = sample_grid(expr, bounds=bounds, resolution=resolution)
    nz, ny, nx = volume.shape
    iso_f = float(iso)
    inside = volume < iso_f

    step_x = abs(float(xs[1] - xs[0])) if len(xs) > 1 else 1.0
    step_y = abs(float(ys[1] - ys[0])) if len(ys) > 1 else 1.0
    step_z = abs(float(zs[1] - zs[0])) if len(zs) > 1 else 1.0
    grad_z, grad_y, grad_x = np.gradient(
        volume,
        step_z,
        step_y,
        step_x,
        edge_order=1,
    )

    def _gradient(point: tuple[float, float, float]) -> np.ndarray:
        px, py, pz = (float(value) for value in point)

        def axis_fraction(value: float, coords: np.ndarray, step: float) -> tuple[int, int, float]:
            if len(coords) <= 1 or step <= 0.0:
                return 0, 0, 0.0
            raw = (value - float(coords[0])) / float(step)
            raw = float(np.clip(raw, 0.0, float(len(coords) - 1)))
            lo = int(np.floor(raw))
            hi = min(lo + 1, len(coords) - 1)
            return lo, hi, raw - float(lo)

        ix0, ix1, tx = axis_fraction(px, xs, step_x)
        iy0, iy1, ty = axis_fraction(py, ys, step_y)
        iz0, iz1, tz = axis_fraction(pz, zs, step_z)

        def trilinear(grid: np.ndarray) -> float:
            c000 = float(grid[iz0, iy0, ix0])
            c100 = float(grid[iz0, iy0, ix1])
            c010 = float(grid[iz0, iy1, ix0])
            c110 = float(grid[iz0, iy1, ix1])
            c001 = float(grid[iz1, iy0, ix0])
            c101 = float(grid[iz1, iy0, ix1])
            c011 = float(grid[iz1, iy1, ix0])
            c111 = float(grid[iz1, iy1, ix1])
            c00 = c000 * (1.0 - tx) + c100 * tx
            c10 = c010 * (1.0 - tx) + c110 * tx
            c01 = c001 * (1.0 - tx) + c101 * tx
            c11 = c011 * (1.0 - tx) + c111 * tx
            c0 = c00 * (1.0 - ty) + c10 * ty
            c1 = c01 * (1.0 - ty) + c11 * ty
            return c0 * (1.0 - tz) + c1 * tz

        normal = np.asarray(
            (
                trilinear(grad_x),
                trilinear(grad_y),
                trilinear(grad_z),
            ),
            dtype=np.float64,
        )
        norm = float(np.linalg.norm(normal))
        if norm <= 1e-12 or not np.isfinite(norm):
            return np.zeros(3, dtype=np.float64)
        return normal / norm

    def _qef_vertex(
        crossings: list[tuple[float, float, float]],
        normals: list[np.ndarray],
        *,
        cell_min: tuple[float, float, float],
        cell_max: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        centroid = np.asarray(
            (
                sum(p[0] for p in crossings) / len(crossings),
                sum(p[1] for p in crossings) / len(crossings),
                sum(p[2] for p in crossings) / len(crossings),
            ),
            dtype=np.float64,
        )
        valid_pairs = [
            (point, normal)
            for point, normal in zip(crossings, normals, strict=False)
            if np.linalg.norm(normal) > 1e-12
        ]
        if len(valid_pairs) < 3:
            return (float(centroid[0]), float(centroid[1]), float(centroid[2]))
        points = np.asarray([point for point, _normal in valid_pairs], dtype=np.float64)
        a = np.asarray([normal for _point, normal in valid_pairs], dtype=np.float64)
        b = np.einsum("ij,ij->i", a, points)
        try:
            solved, *_ = np.linalg.lstsq(a, b, rcond=None)
        except np.linalg.LinAlgError:
            return (float(centroid[0]), float(centroid[1]), float(centroid[2]))
        if not np.all(np.isfinite(solved)):
            return (float(centroid[0]), float(centroid[1]), float(centroid[2]))
        lo = np.asarray(cell_min, dtype=np.float64)
        hi = np.asarray(cell_max, dtype=np.float64)
        if np.any(solved < lo - 1e-7) or np.any(solved > hi + 1e-7):
            solved = np.clip(solved, lo, hi)
        return (float(solved[0]), float(solved[1]), float(solved[2]))

    # Per-cell vertex placement: fit a QEF to Hermite samples on
    # iso-crossing edges, falling back to the crossing centroid when needed.
    cell_vertices: dict[tuple[int, int, int], int] = {}
    verts: list[tuple[float, float, float]] = []

    corner_offsets = (
        (0, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (0, 1, 0),
        (0, 0, 1),
        (1, 0, 1),
        (1, 1, 1),
        (0, 1, 1),
    )
    cube_edges = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )

    def _cell_vertex(i: int, j: int, k: int) -> int | None:
        # Returns the index of this cell's vertex if any iso-crossing
        # edges exist; otherwise None.
        crossings: list[tuple[float, float, float]] = []
        normals: list[np.ndarray] = []
        cv = []
        for dx, dy, dz in corner_offsets:
            cv.append(volume[k + dz, j + dy, i + dx])
        for ea, eb in cube_edges:
            va, vb = cv[ea], cv[eb]
            if (va < iso_f) == (vb < iso_f):
                continue
            denom = vb - va
            t = 0.5 if abs(denom) < 1e-12 else (iso_f - va) / denom
            t = float(np.clip(t, 0.0, 1.0))
            pa = corner_offsets[ea]
            pb = corner_offsets[eb]
            px = xs[i + pa[0]] + t * (xs[i + pb[0]] - xs[i + pa[0]])
            py = ys[j + pa[1]] + t * (ys[j + pb[1]] - ys[j + pa[1]])
            pz = zs[k + pa[2]] + t * (zs[k + pb[2]] - zs[k + pa[2]])
            point = (float(px), float(py), float(pz))
            crossings.append(point)
            normals.append(_gradient(point))
        if not crossings:
            return None
        cx, cy, cz = _qef_vertex(
            crossings,
            normals,
            cell_min=(float(xs[i]), float(ys[j]), float(zs[k])),
            cell_max=(float(xs[i + 1]), float(ys[j + 1]), float(zs[k + 1])),
        )
        idx = len(verts)
        verts.append((cx, cy, cz))
        return idx

    for k in range(nz - 1):
        for j in range(ny - 1):
            for i in range(nx - 1):
                v = _cell_vertex(i, j, k)
                if v is not None:
                    cell_vertices[(i, j, k)] = v

    # Quad generation: each edge of the dual grid produces a quad of the
    # 4 cells incident to that edge if the underlying SDF edge is iso-
    # crossing. Each quad is split into 2 triangles for downstream
    # consumers.
    faces: list[tuple[int, int, int]] = []

    def _emit_quad(c0, c1, c2, c3):
        if any(c not in cell_vertices for c in (c0, c1, c2, c3)):
            return
        v0, v1, v2, v3 = (cell_vertices[c] for c in (c0, c1, c2, c3))
        faces.append((v0, v1, v2))
        faces.append((v0, v2, v3))

    # Edge along +x: cells (i, j-1, k-1), (i, j, k-1), (i, j, k), (i, j-1, k)
    for k in range(1, nz - 1):
        for j in range(1, ny - 1):
            for i in range(nx - 1):
                a = inside[k, j, i]
                b = inside[k, j, i + 1]
                if a == b:
                    continue
                _emit_quad(
                    (i, j - 1, k - 1),
                    (i, j, k - 1),
                    (i, j, k),
                    (i, j - 1, k),
                )

    # Edge along +y
    for k in range(1, nz - 1):
        for j in range(ny - 1):
            for i in range(1, nx - 1):
                a = inside[k, j, i]
                b = inside[k, j + 1, i]
                if a == b:
                    continue
                _emit_quad(
                    (i - 1, j, k - 1),
                    (i, j, k - 1),
                    (i, j, k),
                    (i - 1, j, k),
                )

    # Edge along +z
    for k in range(nz - 1):
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                a = inside[k, j, i]
                b = inside[k + 1, j, i]
                if a == b:
                    continue
                _emit_quad(
                    (i - 1, j - 1, k),
                    (i, j - 1, k),
                    (i, j, k),
                    (i - 1, j, k),
                )

    if not verts:
        return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 3), dtype=np.int32)
    return np.asarray(verts, dtype=np.float64), np.asarray(faces, dtype=np.int32)
