"""Exception classes for the shape-provider subsystem.

These classes are re-parented under :class:`lathe.errors.LatheError` while
preserving the existing ``RuntimeError`` MRO — ``ShapeProviderError`` is
still ``isinstance(..., RuntimeError)`` via multiple inheritance, so any
call site that catches ``RuntimeError`` continues to work. The authoritative
definitions live in ``lathe/errors.py``; this module re-exports them for
backwards compatibility.
"""

from __future__ import annotations

from ..errors import (  # re-export — authoritative definitions live in lathe/errors.py
    ShapeMeshLoadError,
    ShapeProviderError,
    ShapeProviderExecutionError,
    ShapeProviderUnavailable,
)

__all__ = [
    "ShapeMeshLoadError",
    "ShapeProviderError",
    "ShapeProviderExecutionError",
    "ShapeProviderUnavailable",
]
