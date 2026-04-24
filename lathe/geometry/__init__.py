"""Geometry kernel subpackage (GEO-2/3).

Exposes the :class:`GeometryKernel` Protocol, the kernel registry,
:func:`resolve_geometry_kernel`, and the two built-in kernels
(``lathe.geometry.manifold_v1``, ``lathe.geometry.reference_v1``).
"""

from __future__ import annotations

from .kernel import (
    GeometryKernel,
    GeometryKernelUnavailable,
    UnknownGeometryKernel,
    list_registered_kernels,
    register_geometry_kernel,
    resolve_geometry_kernel,
)

__all__ = [
    "GeometryKernel",
    "GeometryKernelUnavailable",
    "UnknownGeometryKernel",
    "list_registered_kernels",
    "register_geometry_kernel",
    "resolve_geometry_kernel",
]
