"""Shape subsystem package.

Public entry points for the shape stage under the stable
``lathe.shape.intent_mesh_handoff_v1`` contract. Back-compat shim
``lathe/shape_backend.py`` re-exports these names; new code should
import directly from ``lathe.shape``.
"""

from __future__ import annotations

from .backend import collect_shape_conditioning, run_shape_backend

__all__ = ["collect_shape_conditioning", "run_shape_backend"]
