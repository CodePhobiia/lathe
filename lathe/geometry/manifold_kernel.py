"""Manifold geometry kernel factory (GEO-3).

Thin wrapper that promotes the evaluation-era adapter in
``lathe.adapters.manifold_kernel`` to a first-class kernel under the
``lathe.geometry.manifold_v1`` ID. The adapter supplies all CSG ops —
this module only adds the factory entry point the registry expects and
maps ``ManifoldKernelUnavailable`` onto the geometry-package exception
type so the resolver's fallback logic works.
"""

from __future__ import annotations

from typing import Any

from ..adapters.manifold_kernel import (
    ManifoldKernel as _ManifoldKernel,
    ManifoldKernelUnavailable,
    manifold_available,
)
from .kernel import GeometryKernel, GeometryKernelUnavailable, MANIFOLD_KERNEL_ID

MANIFOLD_ID = MANIFOLD_KERNEL_ID

__all__ = ["manifold_kernel", "manifold_available", "MANIFOLD_ID", "ManifoldKernel"]


def manifold_kernel() -> GeometryKernel:
    """Instantiate the Manifold-backed geometry kernel.

    Raises:
        GeometryKernelUnavailable: when ``manifold3d`` is not importable.
            The resolver catches this and falls back to the reference
            kernel.
    """
    try:
        return _ManifoldKernel()  # type: ignore[return-value]
    except ManifoldKernelUnavailable as exc:
        raise GeometryKernelUnavailable(str(exc)) from exc


# Backward-compatible public alias: older call sites (tests, bench harness)
# import the concrete class; re-export it so they continue to work while
# new code flows through the factory.
ManifoldKernel: Any = _ManifoldKernel
