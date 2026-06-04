"""Compatibility shim for the renamed ShapeIR lowering module.

The canonical module is :mod:`lathe.geometry.shape_ir_lowering`. This file
keeps older direct imports such as ``lathe.geometry.shape_ir_program`` working
while callers migrate to the new name.
"""

from __future__ import annotations

from . import shape_ir_lowering as _shape_ir_lowering
from .shape_ir_lowering import *  # noqa: F403

__all__ = [name for name in dir(_shape_ir_lowering) if not name.startswith("__")]
globals().update({name: getattr(_shape_ir_lowering, name) for name in __all__})
