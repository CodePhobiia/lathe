"""Vectorized SDF evaluator.

Walks an :class:`SDFExpr` tree and evaluates the signed distance field
over either an arbitrary point array or a regular axis-aligned grid.
Grid sampling is the form consumed by the marching-cubes extractor.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .expressions import SDFExpr


def evaluate_sdf(expr: SDFExpr, points: Any) -> np.ndarray:
    """Evaluate ``expr`` at one or many query points.

    Args:
        expr: root SDF expression.
        points: ``(3,)`` or ``(N, 3)`` array of points.

    Returns:
        Scalar or ``(N,)`` numpy array of signed distances.
    """
    return expr.distance(points)


def sample_grid(
    expr: SDFExpr,
    *,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    resolution: int | tuple[int, int, int] = 64,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Sample ``expr`` on a regular axis-aligned grid.

    Args:
        expr: root SDF expression.
        bounds: ``((xmin, ymin, zmin), (xmax, ymax, zmax))``.
        resolution: scalar or per-axis cell counts. The output volume
            has shape ``(nz, ny, nx)`` matching numpy / MC conventions.

    Returns:
        ``(volume, (xs, ys, zs))`` — the SDF volume and the axis
        coordinate arrays.
    """
    (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
    if isinstance(resolution, int):
        nx = ny = nz = int(resolution)
    else:
        nx, ny, nz = (int(v) for v in resolution)
    if nx < 2 or ny < 2 or nz < 2:
        raise ValueError("Grid resolution must be >= 2 along every axis")
    xs = np.linspace(xmin, xmax, nx, dtype=np.float64)
    ys = np.linspace(ymin, ymax, ny, dtype=np.float64)
    zs = np.linspace(zmin, zmax, nz, dtype=np.float64)
    # Build (N, 3) point batch in (z, y, x) order so reshape -> (nz, ny, nx)
    zz, yy, xx = np.meshgrid(zs, ys, xs, indexing="ij")
    points = np.stack([xx.reshape(-1), yy.reshape(-1), zz.reshape(-1)], axis=1)
    flat = expr.distance(points)
    arr = np.asarray(flat, dtype=np.float64).reshape(nz, ny, nx)
    return arr, (xs, ys, zs)


def evaluate_program(
    expr: SDFExpr,
    points: Any,
) -> np.ndarray:
    """Convenience wrapper matching the §A.5 spec naming.

    Equivalent to :func:`evaluate_sdf` — provided so external callers can
    refer to "evaluate program" as the action verb on a compiled f_rep
    program.
    """
    return evaluate_sdf(expr, points)
